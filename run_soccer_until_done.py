"""
run_soccer_until_done.py — ops supervisor for the Phase 6b evaluation.

WHY: on this machine (Intel Iris Xe, no CUDA, CPU inference) the Ollama server
has dropped mid-run. It also silently TRUNCATED oversized prompts until
OLLAMA_CONTEXT_LENGTH was raised to 8192, which invalidated 12 Soccer records.

WHAT THIS DOES
  loop:
    1. verify the LLM can actually GENERATE (a port check is not enough --
       a loaded-but-wedged server still answers the port)
    2. if not, (re)start `ollama serve` with the correct environment and wait
       for a warm-up generate to return real tokens
    3. run the existing resumable run_eval.py as a subprocess
    4. if it exits non-zero (its clean connection-failure abort), back off and loop
  until every (config, question) pair exists, or the attempt cap is hit.

WHAT THIS NEVER DOES
  It never writes to phase6_raw.json and never fabricates a record. All results
  come from run_eval.py, which records nothing on a connection failure. The
  experiment is untouched: temperature 0, the same 78-pair disjoint training
  pool, the same four configs.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
RAW = ROOT / "phase6_raw.json"
GOLD = ROOT / "gold_answers.json"
OLLAMA_EXE = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Ollama" / "ollama.exe"

OLLAMA_ENV = {
    "OLLAMA_CONTEXT_LENGTH": "8192",   # Soccer Config C/D prompts are ~4,550 tokens
    "OLLAMA_KEEP_ALIVE": "-1",         # never unload mid-run
    "OLLAMA_NUM_PARALLEL": "1",        # one slot gets the whole context
    "OLLAMA_MAX_LOADED_MODELS": "1",
}

MAX_ATTEMPTS = 15
BACKOFF_S = 30
MIN_PROMPT_TOKENS = 3000              # a real Soccer C/D prompt must exceed this


RUN = int(sys.argv[sys.argv.index("--run") + 1]) if "--run" in sys.argv else 1


def _key(cfg, qid):
    return f"{cfg}|{qid}" if RUN == 1 else f"r{RUN}|{cfg}|{qid}"


def remaining_pairs():
    raw = json.loads(RAW.read_text(encoding="utf-8")) if RAW.exists() else {}
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    return [_key(c, g["id"]) for g in gold for c in "ABCD" if _key(c, g["id"]) not in raw]


def can_generate(timeout=120):
    """True only if the model returns REAL TOKENS. Port checks are not enough."""
    try:
        from agent import LLM_MODEL, client
        r = client.chat.completions.create(
            model=LLM_MODEL, temperature=0, timeout=timeout,
            messages=[{"role": "user", "content": "Reply with the single word OK"}])
        return bool((r.choices[0].message.content or "").strip())
    except Exception as exc:
        print(f"    warm-up generate failed: {type(exc).__name__}: {str(exc)[:80]}", flush=True)
        return False


def start_ollama():
    env = dict(os.environ, **OLLAMA_ENV)
    print(f"    starting {OLLAMA_EXE} serve with {OLLAMA_ENV}", flush=True)
    subprocess.Popen([str(OLLAMA_EXE), "serve"], env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for i in range(30):
        time.sleep(5)
        if can_generate(timeout=60):
            print(f"    server generating after ~{(i + 1) * 5}s", flush=True)
            return True
    return False


def ensure_llm():
    if can_generate():
        return True
    print("    LLM not generating -- restarting ollama", flush=True)
    return start_ollama()


def main():
    print(f"supervisor start | RUN #{RUN} | remaining pairs: {len(remaining_pairs())}", flush=True)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        todo = remaining_pairs()
        if not todo:
            print("\nALL PAIRS COMPLETE", flush=True)
            return 0

        print(f"\n=== attempt {attempt}/{MAX_ATTEMPTS} | {len(todo)} pairs left ===", flush=True)
        if not ensure_llm():
            print(f"    could not get a working LLM; backing off {BACKOFF_S}s", flush=True)
            time.sleep(BACKOFF_S)
            continue

        rc = subprocess.run([sys.executable, "-u", "run_eval.py", "--run", str(RUN)],
                            cwd=str(ROOT)).returncode
        print(f"    run_eval.py exited {rc}", flush=True)
        if rc != 0:
            print(f"    clean abort (nothing recorded); backing off {BACKOFF_S}s", flush=True)
            time.sleep(BACKOFF_S)

    left = remaining_pairs()
    print(f"\nSTOPPED after {MAX_ATTEMPTS} attempts | {len(left)} pairs still missing: {left[:10]}",
          flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
