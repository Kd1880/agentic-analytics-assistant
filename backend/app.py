"""
backend/app.py — Phase 7 deployment API (FastAPI).

Fully env-driven so it runs on a deploy host:
  - database URLs come from DB_MOVIELENS / DB_OLIST / DB_SOCCER (NOT db.py's
    DATABASES dict, which hardcodes localhost and is frozen).
  - the LLM provider comes from LLM_PROVIDER (gemini for prod, ollama for dev).

It REUSES the project's engine-agnostic pieces read-only:
  db.get_engine / get_schema_text / run_sql   (frozen)
  context.enrich_schema                       (Phase 4a sample values)
  memory.Memory                               (Phase 4b retrieved examples)
  guardrails.run_sql_safe / classify_error    (Phase 5)
  self_correct.CORRECTION_PROMPT              (Phase 3 wording, for parity)
  llm_provider.generate_sql_via / continue_via (Phase 7 provider layer)

Nothing here modifies agent.py or db.py, and no experiment file is touched.
"""

from __future__ import annotations

import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from context import enrich_schema
from db import get_engine, get_schema_text
from guardrails import GuardrailError, classify_error, run_sql_safe
from llm_provider import (ProviderError, continue_via, default_provider,
                          generate_sql_via, provider_status)
from memory import Memory
from self_correct import CORRECTION_PROMPT

load_dotenv()

# --- config (all from env) --------------------------------------------------
DB_ENV = {"movielens": "DB_MOVIELENS", "olist": "DB_OLIST", "soccer": "DB_SOCCER"}
DATABASES = {name: os.getenv(var) for name, var in DB_ENV.items() if os.getenv(var)}

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
MAX_ROWS = int(os.getenv("MAX_ROWS", "200"))        # display cap; never injected into SQL
TIMEOUT_S = float(os.getenv("SQL_TIMEOUT_S", "30"))
USE_SAMPLES = os.getenv("USE_SAMPLES", "true").lower() == "true"
USE_MEMORY = os.getenv("USE_MEMORY", "true").lower() == "true"
K_EXAMPLES = int(os.getenv("K_EXAMPLES", "3"))
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]

app = FastAPI(title="Agentic Analytics Assistant", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

_memory = Memory() if USE_MEMORY else None
_schema_cache: dict[str, str] = {}                 # introspection is stable per process


class AskRequest(BaseModel):
    db: str = Field(..., examples=["olist"])
    question: str = Field(..., examples=["What are the top 10 product categories by revenue?"])


def _engine(db: str):
    url = DATABASES.get(db)
    if not url:
        raise HTTPException(404, f"unknown database {db!r}; configured: {list(DATABASES)}")
    return get_engine(url)


def _schema_for(db: str, engine) -> str:
    if db not in _schema_cache:
        schema = get_schema_text(engine)
        if USE_SAMPLES:
            schema = enrich_schema(engine, schema, k=3)
        _schema_cache[db] = schema
    return _schema_cache[db]


def _chart_hint(cols: list[str], rows: list) -> dict:
    """Deterministic hint for the frontend. No extra LLM call."""
    if not rows:
        return {"type": "none"}
    if len(rows) == 1 and len(cols) == 1:
        return {"type": "scalar", "label": cols[0]}
    if len(cols) < 2:
        return {"type": "none"}
    label, value = cols[0], cols[1]
    numeric = all(isinstance(r[1], (int, float)) or r[1] is None for r in rows[:10])
    if not numeric:
        return {"type": "table"}
    time_like = any(k in label.lower() for k in ("year", "month", "date", "season", "time"))
    return {"type": "line" if time_like else "bar", "x": label, "y": value}


def _insight(cols: list[str], rows: list, truncated: bool) -> str:
    """One factual sentence derived from the rows; no LLM, no speculation."""
    if not rows:
        return "The query ran successfully but returned no rows."
    if len(rows) == 1 and len(cols) == 1:
        return f"{cols[0]}: {rows[0][0]}."
    parts = [f"{len(rows)} row{'s' if len(rows) != 1 else ''} returned"]
    if len(cols) >= 2 and isinstance(rows[0][1], (int, float)):
        parts.append(f"top: {rows[0][0]} ({rows[0][1]:,.2f})" if isinstance(rows[0][1], float)
                     else f"top: {rows[0][0]} ({rows[0][1]:,})")
    if truncated:
        parts.append(f"display limited to {MAX_ROWS} rows (the query itself was not limited)")
    return "; ".join(parts) + "."


@app.get("/health")
def health():
    return {"status": "ok", "provider": default_provider(),
            "databases": list(DATABASES), "memory": bool(_memory)}


@app.get("/config")
def config():
    """Safe-to-expose configuration. Contains no secret values."""
    return {"providers": provider_status(),
            "use_samples": USE_SAMPLES, "use_memory": USE_MEMORY,
            "k_examples": K_EXAMPLES, "max_retries": MAX_RETRIES,
            "max_rows": MAX_ROWS, "sql_timeout_s": TIMEOUT_S}


@app.get("/databases")
def databases():
    out = []
    for name in DATABASES:
        try:
            engine = _engine(name)
            schema = _schema_for(name, engine)
            out.append({"name": name, "dialect": engine.dialect.name,
                        "tables": schema.count("CREATE TABLE "),
                        "schema_chars": len(schema), "status": "ready"})
        except Exception as exc:
            out.append({"name": name, "status": "error",
                        "error": f"{type(exc).__name__}: {str(exc)[:120]}"})
    return {"databases": out}


@app.post("/ask")
def ask(req: AskRequest):
    """question -> SQL -> guarded execution -> (retry on SQL error) -> rows."""
    engine = _engine(req.db)
    dialect = engine.dialect.name
    schema = _schema_for(req.db, engine)

    examples = []
    if _memory:
        examples = _memory.retrieve(req.db, req.question, k=K_EXAMPLES)

    t0 = time.monotonic()
    try:
        sql, provider, fb_reason = generate_sql_via(
            req.question, schema, dialect, examples=examples)
    except ProviderError as exc:
        raise HTTPException(503, f"LLM provider unavailable: {exc}")

    messages = None          # built lazily, only if a retry is needed
    history = []

    for attempt in range(1, MAX_RETRIES + 2):
        try:
            cols, rows, truncated = run_sql_safe(engine, sql, max_rows=MAX_ROWS,
                                                 timeout_s=TIMEOUT_S)
        except GuardrailError as exc:
            err, kind = f"Rejected by guardrails: {exc}", "guardrail"
        except Exception as exc:
            err, kind = str(getattr(exc, "orig", exc)).strip(), classify_error(exc)
        else:
            return {
                "sql": sql, "columns": cols,
                "rows": [[None if v is None else v for v in r] for r in rows],
                "attempts": attempt, "succeeded": True,
                "insight": _insight(cols, rows, truncated),
                "chartHint": _chart_hint(cols, rows),
                "provider": provider,
                "providerFallback": fb_reason,
                "truncated": truncated,
                "elapsedMs": int((time.monotonic() - t0) * 1000),
                "history": history,
            }

        history.append({"attempt": attempt, "sql": sql, "error": err, "kind": kind})

        # operational = infrastructure, not the model's fault: fail fast (Phase 5)
        if kind == "operational" or attempt > MAX_RETRIES:
            return {
                "sql": sql, "columns": [], "rows": [],
                "attempts": attempt, "succeeded": False,
                "insight": (f"The query could not be executed ({kind}). " +
                            ("This looks like a database/infrastructure problem, not a "
                             "query problem." if kind == "operational" else
                             f"Last error: {err.splitlines()[0][:160]}")),
                "chartHint": {"type": "none"}, "provider": provider,
                "providerFallback": fb_reason,
                "truncated": False,
                "elapsedMs": int((time.monotonic() - t0) * 1000),
                "history": history,
            }

        # feed the error back as a new turn (Phase 3)
        if messages is None:
            from agent import SYSTEM_PROMPT
            messages = [{"role": "system",
                         "content": SYSTEM_PROMPT.format(schema=schema, dialect=dialect)}]
            for ex in examples:
                messages.append({"role": "user", "content": ex["question"]})
                messages.append({"role": "assistant", "content": ex["sql"]})
            messages.append({"role": "user", "content": req.question})
        messages.append({"role": "assistant", "content": sql})
        messages.append({"role": "user", "content": CORRECTION_PROMPT.format(error=err)})
        try:
            sql, provider, fb2 = continue_via(messages)
            fb_reason = fb2 or fb_reason
        except ProviderError as exc:
            raise HTTPException(503, f"LLM provider unavailable during retry: {exc}")
