"""
run_gemini_probe.py — Phase 7 SCOPED cross-model probe: Gemini vs the local 7B.

SCOPE: Config A (baseline) and Config C (context+memory), 45 gold questions,
SINGLE run. This is a preliminary probe, not a second full study.

FAIRNESS: only the MODEL changes. Schema introspection (db.py), sample-value
enrichment (context.py), the 78-pair disjoint memory pool (memory.py),
guardrails (guardrails.py), the frozen SYSTEM_PROMPT (agent.py), the gold
answers (gold_answers.json) and the grader (grade.py) are all reused unchanged.

INTEGRITY: writes ONLY to phase6_gemini_raw.json. No qwen artefact is touched.
Pure Gemini: allow_fallback=False, so a failure is recorded, never substituted
with another model. Quota/connection exhaustion is tagged error_kind='provider'
so it can be told apart from a genuine model error.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from context import enrich_schema
from db import DATABASES, get_engine, get_schema_text
from grade import grade
from guardrails import GuardrailError, classify_error, run_sql_safe
from llm_provider import ProviderError, build_client, generate_sql_via
from memory import Memory

RAW = Path("phase6_gemini_raw.json")
GOLD = Path("gold_answers.json")            # read-only
PROVIDER = "gemini"
TIMEOUT_S = 30                              # same as the qwen study
SPACING_S = 1                               # paid tier: high RPM, minimal spacing
OUTER_RETRIES = (15, 45)                    # on top of llm_provider's 2/8/20 backoff

CONFIGS = {
    "A": dict(use_samples=False, use_memory=False),
    "C": dict(use_samples=True, use_memory=True),
}


def load_raw() -> dict:
    return json.loads(RAW.read_text(encoding="utf-8")) if RAW.exists() else {}


def save_raw(raw: dict) -> None:
    tmp = RAW.with_suffix(".tmp")
    tmp.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    tmp.replace(RAW)


_schema_cache: dict[tuple[str, bool], str] = {}


def schema_for(db: str, engine, enriched: bool) -> str:
    key = (db, enriched)
    if key not in _schema_cache:
        s = get_schema_text(engine)
        if enriched:
            s = enrich_schema(engine, s, k=3)
        _schema_cache[key] = s
    return _schema_cache[key]


def generate(question: str, schema: str, dialect: str, examples: list):
    """Gemini only. Retries quota/transient errors, then raises ProviderError."""
    last = None
    for wait in (0,) + OUTER_RETRIES:
        if wait:
            print(f"      provider backoff {wait}s ...", flush=True)
            time.sleep(wait)
        try:
            sql, prov, fb = generate_sql_via(question, schema, dialect,
                                             provider=PROVIDER, examples=examples,
                                             allow_fallback=False)
            assert prov == PROVIDER and fb is None, f"fallback leaked: {prov} {fb}"
            return sql
        except ProviderError as exc:
            last = exc
    raise ProviderError(str(last))


def main(only_config: str | None = None):
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    mem = Memory()
    raw = load_raw()
    _, model_id = build_client(PROVIDER)
    print(f"probe | provider={PROVIDER} model={model_id} fallback=OFF | "
          f"records on file: {len(raw)}", flush=True)

    todo = [(c, g) for g in gold for c in (CONFIGS if not only_config else [only_config])
            if f"{c}|{g['id']}" not in raw]
    print(f"to run: {len(todo)}\n", flush=True)

    for n, (cfg, g) in enumerate(todo, 1):
        key = f"{cfg}|{g['id']}"
        flags = CONFIGS[cfg]
        engine = get_engine(DATABASES[g["db"]])
        dialect = engine.dialect.name
        schema = schema_for(g["db"], engine, flags["use_samples"])
        examples = (mem.retrieve(g["db"], g["question"], k=3)
                    if flags["use_memory"] else [])

        t0 = time.monotonic()
        try:
            sql = generate(g["question"], schema, dialect, examples)
        except ProviderError as exc:
            raw[key] = dict(config=cfg, id=g["id"], db=g["db"], difficulty=g["difficulty"],
                            model=model_id, provider=PROVIDER, category="loud",
                            detail="provider unavailable", succeeded=False,
                            error_kind="provider", error=str(exc)[:200], sql=None,
                            n_rows=0, rows=[], examples=[], elapsed_s=round(time.monotonic()-t0, 1))
            save_raw(raw)
            print(f"[{n}/{len(todo)}] {key:<10} PROVIDER-FAIL", flush=True)
            continue

        try:
            cols, rows, _ = run_sql_safe(engine, sql, max_rows=None, timeout_s=TIMEOUT_S)
        except GuardrailError as exc:
            err, kind, cols, rows = f"Rejected by guardrails: {exc}", "guardrail", [], []
        except Exception as exc:
            err = str(getattr(exc, "orig", exc)).strip()
            kind, cols, rows = classify_error(exc), [], []
        else:
            err, kind = None, None

        verdict = grade(g, kind is None, rows)
        raw[key] = dict(
            config=cfg, id=g["id"], db=g["db"], difficulty=g["difficulty"],
            model=model_id, provider=PROVIDER,
            category=verdict["category"], detail=verdict["detail"],
            succeeded=kind is None, error_kind=kind,
            error=(err.splitlines()[0][:200] if err else None),
            sql=sql, n_rows=len(rows),
            rows=[[str(v) for v in r] for r in rows[:5]],
            examples=[{"id": e["id"], "technique": e.get("technique")} for e in examples],
            elapsed_s=round(time.monotonic() - t0, 1))
        save_raw(raw)
        print(f"[{n}/{len(todo)}] {key:<10} {verdict['category']:<8} "
              f"{raw[key]['elapsed_s']:>6}s  rows={len(rows)}", flush=True)
        time.sleep(SPACING_S)

    print(f"\ndone. records: {len(raw)}", flush=True)


# --------------------- LIMIT-adjusted re-grading ---------------------------
TOP_N = re.compile(
    r"\btop\s+\d+|\bfirst\s+\d+|\blast\s+\d+|\bwhich\s+\d+\b|"
    r"\b\d+\s+(?:most|least|highest|lowest|largest|biggest|smallest|best|worst|"
    r"tallest|heaviest|longest|shortest|top)\b|\bwho\s+are\s+the\s+\d+", re.I)
TRAILING_LIMIT = re.compile(r"\s+LIMIT\s+(\d+)\s*(?:OFFSET\s+\d+\s*)?;?\s*$", re.I)


def limit_adjust():
    """For each 'silent' answer, strip a LIMIT the question never asked for,
    re-execute, and re-grade. Reports how many flip to correct.

    A LIMIT is treated as unrequested only when ALL hold:
      1. it is the TRAILING clause of the query;
      2. the question contains no top-N intent;
      3. gold row count > k, i.e. the limit demonstrably truncated the answer.
    """
    raw = load_raw()
    gold = {g["id"]: g for g in json.loads(GOLD.read_text(encoding="utf-8"))}
    flips, examined = [], []

    for key, rec in sorted(raw.items()):
        if rec["category"] != "silent" or not rec.get("sql"):
            continue
        g = gold[rec["id"]]
        m = TRAILING_LIMIT.search(rec["sql"])
        if not m:
            continue
        k = int(m.group(1))
        asked = bool(TOP_N.search(g["question"]))
        truncating = g["n_rows"] > k
        examined.append((key, k, asked, truncating, g["n_rows"]))
        if asked or not truncating:
            continue

        stripped = TRAILING_LIMIT.sub("", rec["sql"]).strip()
        engine = get_engine(DATABASES[rec["db"]])
        try:
            cols, rows, _ = run_sql_safe(engine, stripped, max_rows=None, timeout_s=60)
        except Exception as exc:
            rec["limit_adjusted"] = {"stripped_limit": k, "outcome": "error",
                                     "error": str(getattr(exc, "orig", exc))[:120]}
            continue
        v2 = grade(g, True, rows)
        rec["limit_adjusted"] = {"stripped_limit": k, "sql": stripped,
                                 "category": v2["category"], "n_rows": len(rows)}
        if v2["category"] == "correct":
            flips.append((key, k, g["n_rows"]))
    save_raw(raw)

    print("=== LIMIT-adjusted pass ===")
    print(f"silent answers with a trailing LIMIT: {len(examined)}")
    for key, k, asked, trunc, gn in examined:
        why = ("question asks for top-N -> KEEP" if asked else
               (f"gold has {gn} rows > {k} -> STRIP" if trunc else
                f"gold has {gn} rows <= {k} -> limit was not the cause"))
        print(f"   {key:<10} LIMIT {k:<5} {why}")
    print(f"\nflipped to CORRECT after stripping: {len(flips)} -> "
          f"{[(k, f'LIMIT {n} vs gold {g}') for k, n, g in flips]}")


if __name__ == "__main__":
    if "--limit-adjust" in sys.argv:
        limit_adjust()
    else:
        cfg = sys.argv[sys.argv.index("--config") + 1] if "--config" in sys.argv else None
        main(only_config=cfg)
