"""
run_eval.py — Phase 6b: 4 configs x 45 gold questions through ONE code path.

    A: samples off, memory off, retries 0   (frozen baseline)
    B: samples off, memory off, retries 3   (+self-correction)
    C: samples ON,  memory ON,  retries 0   (+context/memory)
    D: samples ON,  memory ON,  retries 3   (both)

Guardrails ON for all configs, max_rows=None (full fetch, so grading is
unaffected), temperature 0 throughout. Memory draws only from the Phase 6a
training pool, which is disjoint from these 45 questions; exclude_ids is passed
anyway as a dead-man's guard and should never fire.

Resumable: every (config, question) outcome is appended to phase6_raw.json as
soon as it is graded, and completed pairs are skipped on a re-run.
"""

import json
import sys
import time
from pathlib import Path

import agent                      # for token accounting (does not modify the file)
from grade import grade
from memory import Memory
from self_correct import ask_with_correction

RAW = Path("phase6_raw.json")
GOLD = Path("gold_answers.json")
TIMEOUT_S = 30                    # above the 10s default: some gold queries are heavy

CONFIGS = {
    "A": dict(use_samples=False, use_memory=False, max_retries=0),
    "B": dict(use_samples=False, use_memory=False, max_retries=3),
    "C": dict(use_samples=True,  use_memory=True,  max_retries=0),
    "D": dict(use_samples=True,  use_memory=True,  max_retries=3),
    # --- Stage 5 ablations (0 retries, so they decompose C cleanly) ---
    "S":  dict(use_samples=True,  use_memory=False, max_retries=0),  # samples only
    "M":  dict(use_samples=False, use_memory=True,  max_retries=0),  # memory only
    "K1": dict(use_samples=True,  use_memory=True,  max_retries=0, k_examples=1),
}

# --- token accounting: wrap the shared client without touching agent.py ------
TOK = {"prompt": 0, "completion": 0, "calls": 0}
_orig_create = agent.client.chat.completions.create


def _counting_create(*a, **kw):
    resp = _orig_create(*a, **kw)
    u = getattr(resp, "usage", None)
    if u:
        TOK["prompt"] += u.prompt_tokens or 0
        TOK["completion"] += u.completion_tokens or 0
    TOK["calls"] += 1
    return resp


agent.client.chat.completions.create = _counting_create


def _key(run: int, cfg: str, qid: str) -> str:
    """Run 1 keeps the original 'CONFIG|id' key so existing records still resume."""
    return f"{cfg}|{qid}" if run == 1 else f"r{run}|{cfg}|{qid}"


def load_raw():
    if RAW.exists():
        return json.loads(RAW.read_text(encoding="utf-8"))
    return {}


def save_raw(raw):
    tmp = RAW.with_suffix(".tmp")
    tmp.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    tmp.replace(RAW)


def main(only_config=None, limit=None, run=1, ids=None, configs_csv=None):
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    if limit:
        gold = gold[:limit]
    if ids:
        want = set(ids)
        gold = [g for g in gold if g["id"] in want]
    mem = Memory()
    raw = load_raw()

    if configs_csv:
        configs = {c: CONFIGS[c] for c in configs_csv}
    elif only_config:
        configs = {only_config: CONFIGS[only_config]}
    else:
        configs = {c: CONFIGS[c] for c in "ABCD"}      # ablations only run when asked
    todo = [(c, g) for g in gold for c in configs
            if _key(run, c, g["id"]) not in raw]
    print(f"RUN #{run} | gold questions: {len(gold)} | configs: {list(configs)} | "
          f"records on file: {len(raw)} | to run: {len(todo)}", flush=True)

    t_start = time.monotonic()
    for n, (cfg, g) in enumerate(todo, 1):
        key = _key(run, cfg, g["id"])
        flags = CONFIGS[cfg]
        before = dict(TOK)
        t0 = time.monotonic()
        try:
            r = ask_with_correction(
                g["db"], g["question"], verbose=False, memory=mem,
                exclude_ids=[g["id"]],          # dead-man's guard: pool is disjoint
                use_guardrails=True, max_rows=None, timeout_s=TIMEOUT_S, **flags)
            verdict = grade(g, r.succeeded, r.rows)
            rec = dict(
                run_id=run, config=cfg, id=g["id"], db=g["db"], difficulty=g["difficulty"],
                shape=g["shape"], order_sensitive=g["order_sensitive"],
                category=verdict["category"], detail=verdict["detail"],
                succeeded=r.succeeded, attempts=r.attempts, error_kind=r.error_kind,
                error=(r.error or "").splitlines()[0][:200] if r.error else None,
                sql_final=r.sql_final, n_rows=len(r.rows),
                rows_preview=[[str(v) for v in row] for row in r.rows[:3]],
                examples=[{"id": e["id"], "technique": e.get("technique"),
                           "score": e.get("score")} for e in r.examples],
                elapsed_s=round(time.monotonic() - t0, 1),
                prompt_tokens=TOK["prompt"] - before["prompt"],
                completion_tokens=TOK["completion"] - before["completion"],
                llm_calls=TOK["calls"] - before["calls"],
            )
        except Exception as exc:
            # An LLM/infrastructure outage is NOT a model failure. Recording it as
            # 'loud' would contaminate the results (it did, for sc#4..sc#9, until
            # those records were purged). Retry, then abort so a resume picks it up.
            print(f"    !! {key}: {type(exc).__name__}: {str(exc)[:80]}", flush=True)
            recovered = False
            for wait in (15, 30, 60):
                print(f"    retrying in {wait}s ...", flush=True)
                time.sleep(wait)
                try:
                    r = ask_with_correction(
                        g["db"], g["question"], verbose=False, memory=mem,
                        exclude_ids=[g["id"]], use_guardrails=True, max_rows=None,
                        timeout_s=TIMEOUT_S, **flags)
                    recovered = True
                    break
                except Exception as exc2:
                    print(f"    still failing: {type(exc2).__name__}", flush=True)
            if not recovered:
                print("",  flush=True)
                print(f"ABORTING: the LLM endpoint is unreachable. NOTHING was "
                      f"recorded for {key}. Check Ollama, then re-run to resume.",
                      flush=True)
                sys.exit(4)
            verdict = grade(g, r.succeeded, r.rows)
            rec = dict(
                run_id=run, config=cfg, id=g["id"], db=g["db"], difficulty=g["difficulty"],
                shape=g["shape"], order_sensitive=g["order_sensitive"],
                category=verdict["category"], detail=verdict["detail"],
                succeeded=r.succeeded, attempts=r.attempts, error_kind=r.error_kind,
                error=(r.error or "").splitlines()[0][:200] if r.error else None,
                sql_final=r.sql_final, n_rows=len(r.rows),
                rows_preview=[[str(v) for v in row] for row in r.rows[:3]],
                examples=[{"id": e["id"], "technique": e.get("technique"),
                           "score": e.get("score")} for e in r.examples],
                elapsed_s=round(time.monotonic() - t0, 1),
                prompt_tokens=TOK["prompt"] - before["prompt"],
                completion_tokens=TOK["completion"] - before["completion"],
                llm_calls=TOK["calls"] - before["calls"])

        raw[key] = rec
        save_raw(raw)
        done, total = n, len(todo)
        rate = (time.monotonic() - t_start) / n
        eta = (total - n) * rate / 60
        tech = ",".join(sorted({e["technique"] for e in rec["examples"] if e["technique"]}))
        print(f"[{done:>3}/{total}] {key:<10} {rec['category']:<8} "
              f"att={rec['attempts']} {rec['elapsed_s']:>5}s "
              f"{'ex:' + tech if tech else '':<40} eta~{eta:.0f}m", flush=True)

    print(f"\ndone in {(time.monotonic() - t_start)/60:.1f} min | "
          f"llm calls {TOK['calls']} | prompt tok {TOK['prompt']:,} | "
          f"completion tok {TOK['completion']:,}", flush=True)


if __name__ == "__main__":
    cfg = None
    lim = None
    args = sys.argv[1:]
    if "--config" in args:
        i = args.index("--config"); cfg = args[i + 1]
    if "--limit" in args:
        i = args.index("--limit"); lim = int(args[i + 1])
    run = 1
    if "--run" in args:
        i = args.index("--run"); run = int(args[i + 1])
    ids = None
    if "--ids" in args:
        i = args.index("--ids"); ids = [x for x in args[i + 1].split(",") if x]
    ccsv = None
    if "--configs" in args:
        i = args.index("--configs"); ccsv = [x for x in args[i + 1].split(",") if x]
    main(only_config=cfg, limit=lim, run=run, ids=ids, configs_csv=ccsv)
