"""
self_correct.py — Phase 3 self-correction + Phase 4 context/memory + Phase 5 guardrails.

Wraps the FROZEN baseline (agent.py / db.py) without modifying it.

Phase 3: when execution fails, the database's error message is sent back to the
model as a new turn in the same conversation, and the model tries again.

Phase 4 adds two GENERATION-time helpers, both DEFAULT OFF so Configs A and B
behave exactly as before: use_samples (sample values in the schema text) and
use_memory (retrieved worked examples).

    A: use_samples=False, use_memory=False, max_retries=0   (baseline)
    B: use_samples=False, use_memory=False, max_retries=3   (+self-correction)
    C: use_samples=True,  use_memory=True,  max_retries=0   (+context/memory)
    D: use_samples=True,  use_memory=True,  max_retries=3   (both)

Phase 5 executes through guardrails.run_sql_safe (SELECT-only, statement
timeout, fetch cap) and retries ONLY on errors the model can actually fix.
max_rows=None on the eval path, so scoring is unaffected.
"""

import sys
from dataclasses import dataclass, field

from agent import (LLM_MODEL, SYSTEM_PROMPT, clean_sql, client,
                   generate_sql, print_rows)
from db import DATABASES, get_engine, get_schema_text, run_sql
from guardrails import GuardrailError, classify_error, run_sql_safe

CORRECTION_PROMPT = """That query failed with this error:

{error}

Fix the query. Output ONLY the corrected SQL."""


@dataclass
class Result:
    question: str
    sql_final: str
    succeeded: bool                 # True = the SQL executed. NOT "the answer is correct".
    attempts: int                   # 1 = first try worked (or max_retries=0)
    cols: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    error: str | None = None
    history: list = field(default_factory=list)   # [(sql, error_or_None), ...] per attempt
    examples: list = field(default_factory=list)  # retrieved memory examples (Phase 4)
    truncated: bool = False         # Phase 5: fetch cap hit (never affects the SQL)
    error_kind: str | None = None   # Phase 5: 'sql' | 'operational' | 'guardrail'


def _error_text(exc: Exception) -> str:
    """The database's own message (plus HINT), without SQLAlchemy's wrapper."""
    return str(getattr(exc, "orig", exc)).strip()


def _regenerate(messages: list) -> str:
    resp = client.chat.completions.create(model=LLM_MODEL, messages=messages, temperature=0)
    return clean_sql(resp.choices[0].message.content)


def ask_with_correction(db_name: str, question: str, max_retries: int = 3,
                        verbose: bool = True,
                        use_samples: bool = False,      # Phase 4a: sample values
                        use_memory: bool = False,       # Phase 4b: retrieved examples
                        memory=None,
                        k_examples: int = 3,
                        exclude_ids: tuple | list = (),
                        use_guardrails: bool = True,    # Phase 5 wrapper
                        max_rows: int | None = None,    # None = full fetch (eval path)
                        timeout_s: float = 10) -> Result:
    engine = get_engine(DATABASES[db_name])
    dialect = engine.dialect.name
    schema = get_schema_text(engine)

    # --- Phase 4a: annotate the schema with real sample values --------------
    if use_samples:
        from context import enrich_schema            # imported only when enabled
        schema = enrich_schema(engine, schema, k=3)

    # --- Phase 4b: retrieve worked examples (leave-one-out by id) ----------
    examples = []
    if use_memory and memory is not None:
        examples = memory.retrieve(db_name, question, k=k_examples, exclude_ids=exclude_ids)

    # Same system + user turns the baseline sends, plus examples if any.
    # Retries extend this list.
    messages = [{"role": "system",
                 "content": SYSTEM_PROMPT.format(schema=schema, dialect=dialect)}]
    if examples:
        from memory import as_messages
        messages += as_messages(examples)
    messages.append({"role": "user", "content": question})

    if verbose:
        flags = (f"samples={'on' if use_samples else 'off'} "
                 f"memory={'on' if use_memory else 'off'} "
                 f"guardrails={'on' if use_guardrails else 'off'}")
        print(f"\nQ: {question}   [{db_name} / {dialect}]  max_retries={max_retries}  {flags}")
        for ex in examples:
            print(f"    retrieved (sim={ex['score']}, id={ex['id']}): {ex['question']}")

    # attempt 1: with no examples this is the frozen baseline call, unchanged
    sql = _regenerate(messages) if examples else generate_sql(question, schema, dialect)
    history = []

    for attempt in range(1, max_retries + 2):
        if verbose:
            print(f"\n--- attempt {attempt} ---\n{sql}")

        truncated = False
        try:
            if use_guardrails:
                cols, rows, truncated = run_sql_safe(engine, sql, max_rows=max_rows,
                                                     timeout_s=timeout_s)
            else:
                cols, rows = run_sql(engine, sql)
        except GuardrailError as exc:
            # the model wrote something we refuse to run: its mistake, so feed it back
            err, kind = f"Rejected by guardrails: {exc}", "guardrail"
        except Exception as exc:
            err = _error_text(exc)
            kind = classify_error(exc) if use_guardrails else "sql"
        else:
            kind = None

        if kind is not None:
            history.append((sql, err))
            if verbose:
                print(f"\n  {kind.upper()} ERROR -> {err}")
            # operational = DB down / timeout: the SQL was fine, so retrying is meaningless
            if kind == "operational" or attempt > max_retries:
                return Result(question, sql, False, attempt, error=err,
                              history=history, examples=examples, error_kind=kind)
            # feed the failure back as the next turn in the same conversation
            messages.append({"role": "assistant", "content": sql})
            messages.append({"role": "user", "content": CORRECTION_PROMPT.format(error=err)})
            sql = _regenerate(messages)
            continue

        history.append((sql, None))
        if verbose:
            cap = f", truncated at {max_rows}" if truncated else ""
            print(f"\n  OK on attempt {attempt}  ({attempt - 1} retries{cap})\n")
            print_rows(cols, rows)
        return Result(question, sql, True, attempt, cols, rows,
                      history=history, examples=examples, truncated=truncated)


if __name__ == "__main__":
    # python self_correct.py <db> [--retries N] [--samples] [--memory]
    #        [--max-rows N] [--no-guardrails] <question...>
    args = sys.argv[1:]
    retries, samples, mem_on = 3, False, False
    guards, cap = True, None
    if "--retries" in args:
        i = args.index("--retries"); retries = int(args[i + 1]); del args[i:i + 2]
    if "--max-rows" in args:
        i = args.index("--max-rows"); cap = int(args[i + 1]); del args[i:i + 2]
    if "--samples" in args:
        samples = True; args.remove("--samples")
    if "--memory" in args:
        mem_on = True; args.remove("--memory")
    if "--no-guardrails" in args:
        guards = False; args.remove("--no-guardrails")

    store = None
    if mem_on:
        from memory import Memory
        store = Memory()

    ask_with_correction(args[0], " ".join(args[1:]), max_retries=retries,
                        use_samples=samples, use_memory=mem_on, memory=store,
                        use_guardrails=guards, max_rows=cap)
