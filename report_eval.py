"""
report_eval.py — turn phase6_raw.json into the Phase 6 tables.

Metrics per config:
  execution rate = ran without error            (category != 'loud')
  strict accuracy = 'correct'                   (the honest number)
  lenient accuracy = 'correct' + 'format'       (right value, any shape)
  gap = execution rate - strict accuracy        (the thesis number)
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from seed_memory import TECHNIQUE_COVERAGE

CONFIG_LABEL = {"A": "A baseline", "B": "B +self-correct",
                "C": "C +ctx/memory", "D": "D both"}


def expected_techniques() -> dict:
    """gold id -> {techniques whose training examples would help it}."""
    out = defaultdict(set)
    for db, techs in TECHNIQUE_COVERAGE.items():
        for tech, gold_spec in techs.items():
            prefix = gold_spec.split("#")[0]
            for num in re.findall(r"\d+", gold_spec):
                out[f"{prefix}#{num}"].add(tech)
    return out


def load():
    raw = json.loads(Path("phase6_raw.json").read_text(encoding="utf-8"))
    return list(raw.values())


def rates(recs):
    n = len(recs)
    if not n:
        return None
    c = Counter(r["category"] for r in recs)
    ex = n - c["loud"]
    return dict(n=n, correct=c["correct"], format=c["format"], silent=c["silent"],
                loud=c["loud"], exec_pct=100 * ex / n,
                strict_pct=100 * c["correct"] / n,
                lenient_pct=100 * (c["correct"] + c["format"]) / n,
                gap=100 * ex / n - 100 * c["correct"] / n)


def table(rows, headers):
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join("---" for _ in headers) + "|")
    for r in rows:
        print("| " + " | ".join(str(x) for x in r) + " |")
    print()


def main():
    recs = load()
    by_cfg = defaultdict(list)
    for r in recs:
        by_cfg[r["config"]].append(r)
    configs = [c for c in "ABCD" if c in by_cfg]
    print(f"records: {len(recs)}  configs: {configs}  "
          f"questions per config: {[len(by_cfg[c]) for c in configs]}\n")

    print("## Headline: execution vs accuracy\n")
    table([[CONFIG_LABEL[c], rates(by_cfg[c])["n"],
            f"{rates(by_cfg[c])['exec_pct']:.1f}%",
            f"{rates(by_cfg[c])['strict_pct']:.1f}%",
            f"{rates(by_cfg[c])['lenient_pct']:.1f}%",
            f"{rates(by_cfg[c])['gap']:.1f} pts"] for c in configs],
          ["config", "n", "execution", "strict accuracy", "lenient", "gap"])

    print("## Outcome categories\n")
    table([[CONFIG_LABEL[c]] + [rates(by_cfg[c])[k]
           for k in ("correct", "format", "silent", "loud")] for c in configs],
          ["config", "correct", "format", "silent", "loud"])

    for dim, key in (("database", "db"), ("difficulty", "difficulty")):
        print(f"## By {dim}\n")
        vals = sorted({r[key] for r in recs},
                      key=lambda v: "EMH".index(v) if key == "difficulty" else v)
        rows = []
        for c in configs:
            row = [CONFIG_LABEL[c]]
            for v in vals:
                sub = rates([r for r in by_cfg[c] if r[key] == v])
                row.append("-" if not sub else
                           f"{sub['strict_pct']:.0f}% / {sub['exec_pct']:.0f}% (n={sub['n']})")
            rows.append(row)
        table(rows, ["config (accuracy / execution)"] + list(vals))

    print("## Retry distribution (B, D)\n")
    rows = []
    for c in configs:
        if CONFIGS_WITH_RETRY(c):
            att = Counter(r["attempts"] for r in by_cfg[c])
            fixed = sum(1 for r in by_cfg[c] if r["attempts"] > 1 and r["category"] != "loud")
            correct_after = sum(1 for r in by_cfg[c]
                               if r["attempts"] > 1 and r["category"] == "correct")
            rows.append([CONFIG_LABEL[c], dict(sorted(att.items())),
                         fixed, correct_after])
    table(rows, ["config", "attempts histogram", "made to run by a retry",
                 "...and CORRECT after retry"])

    print("## Memory hit rate (C, D)\n")
    exp = expected_techniques()
    rows = []
    for c in configs:
        if c in ("C", "D"):
            sub = by_cfg[c]
            with_ex = [r for r in sub if r["examples"]]
            hits = [r for r in sub
                    if exp.get(r["id"]) and
                    {e["technique"] for e in r["examples"]} & exp[r["id"]]]
            leaks = [r for r in sub for e in r["examples"]
                     if not str(e["id"]).startswith("tp:")]
            acc_hit = rates([r for r in hits]) if hits else None
            nonhit = [r for r in sub if r not in hits]
            acc_non = rates(nonhit) if nonhit else None
            rows.append([CONFIG_LABEL[c], f"{len(with_ex)}/{len(sub)}",
                         f"{len(hits)}/{len(sub)} ({100*len(hits)/len(sub):.0f}%)",
                         f"{acc_hit['strict_pct']:.0f}%" if acc_hit else "-",
                         f"{acc_non['strict_pct']:.0f}%" if acc_non else "-",
                         len(leaks)])
    table(rows, ["config", "questions with examples", "same-technique hit",
                 "accuracy when hit", "accuracy when miss", "GOLD LEAKS (must be 0)"])

    print("## Cost\n")
    rows = []
    for c in configs:
        sub = by_cfg[c]
        rows.append([CONFIG_LABEL[c], sum(r["llm_calls"] for r in sub),
                     f"{sum(r['prompt_tokens'] for r in sub):,}",
                     f"{sum(r['completion_tokens'] for r in sub):,}",
                     f"{sum(r['elapsed_s'] for r in sub)/60:.1f} min",
                     f"{sum(r['elapsed_s'] for r in sub)/len(sub):.1f} s"])
    table(rows, ["config", "llm calls", "prompt tokens", "completion tokens",
                 "wall clock", "per question"])

    print("## Per-question outcomes\n")
    ids = sorted({r["id"] for r in recs},
                 key=lambda i: (i.split("#")[0], int(i.split("#")[1])))
    idx = {(r["config"], r["id"]): r for r in recs}
    sym = {"correct": "OK", "format": "fmt", "silent": "SIL", "loud": "ERR"}
    rows = []
    for qid in ids:
        any_rec = next(r for r in recs if r["id"] == qid)
        rows.append([qid, any_rec["difficulty"],
                     *[sym.get(idx[(c, qid)]["category"], "-") if (c, qid) in idx else "-"
                       for c in configs]])
    table(rows, ["question", "diff"] + configs)

    print("## Movement between configs (strict accuracy)\n")
    for a, b in (("A", "B"), ("A", "C"), ("C", "D"), ("A", "D")):
        if a in by_cfg and b in by_cfg:
            gained = [q for q in ids if (a, q) in idx and (b, q) in idx
                      and idx[(a, q)]["category"] != "correct"
                      and idx[(b, q)]["category"] == "correct"]
            lost = [q for q in ids if (a, q) in idx and (b, q) in idx
                    and idx[(a, q)]["category"] == "correct"
                    and idx[(b, q)]["category"] != "correct"]
            print(f"- **{a} -> {b}**: gained {len(gained)} {gained}, lost {len(lost)} {lost}")
    print()


def CONFIGS_WITH_RETRY(c):
    return c in ("B", "D")


if __name__ == "__main__":
    main()
