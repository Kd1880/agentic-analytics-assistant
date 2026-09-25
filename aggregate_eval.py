"""
aggregate_eval.py — Phase 6b Stage 3: aggregate the 3 runs.

AGGREGATION CHOICE
  mean of the 3 runs, spread reported as min-max range (not std: with n=3 a
  standard deviation implies precision the data does not support).

NOISE BAND
  Deltas are computed PER RUN (paired), then summarised as mean [min, max].
  If a delta's range includes 0, it is WITHIN run-to-run noise and is not claimed.
  Run-to-run variation is real here: temperature 0 is greedy, but GPU/serving
  non-determinism can flip near-tied logits (Phase 6 Finding 7).
"""

import json
from collections import Counter, defaultdict
from statistics import mean

CFG = ["A", "B", "C", "D"]
LABEL = {"A": "A baseline", "B": "B +self-correct", "C": "C +ctx/memory", "D": "D both"}


def load():
    recs = list(json.load(open("phase6_raw.json")).values())
    by_run = defaultdict(list)
    for r in recs:
        by_run[r["run_id"]].append(r)
    return by_run


def metrics(recs):
    n = len(recs)
    c = Counter(r["category"] for r in recs)
    return dict(n=n,
                execution=100 * (n - c["loud"]) / n,
                strict=100 * c["correct"] / n,
                lenient=100 * (c["correct"] + c["format"]) / n,
                gap=100 * (n - c["loud"]) / n - 100 * c["correct"] / n,
                **{k: c[k] for k in ("correct", "format", "silent", "loud")})


def ms(values):
    """mean [min, max] formatted."""
    return f"{mean(values):.1f} [{min(values):.1f}-{max(values):.1f}]"


def per_run(by_run, cfg, key=None, val=None):
    """metrics per run for one config, optionally filtered by db/difficulty."""
    out = []
    for run in sorted(by_run):
        sub = [r for r in by_run[run] if r["config"] == cfg
               and (val is None or r[key] == val)]
        out.append(metrics(sub))
    return out


def main():
    by_run = load()
    runs = sorted(by_run)
    print(f"runs: {runs} | records per run: {[len(by_run[r]) for r in runs]}\n")

    print("## Headline (mean [min-max] over 3 runs, n=45 per config per run)\n")
    print("| config | execution % | strict accuracy % | lenient % | gap (pts) |")
    print("|---|---|---|---|---|")
    agg = {}
    for c in CFG:
        m = per_run(by_run, c)
        agg[c] = m
        print(f"| {LABEL[c]} | {ms([x['execution'] for x in m])} | "
              f"{ms([x['strict'] for x in m])} | {ms([x['lenient'] for x in m])} | "
              f"{ms([x['gap'] for x in m])} |")

    print("\n## Outcome counts per run (correct / format / silent / loud)\n")
    print("| config | " + " | ".join(f"run {r}" for r in runs) + " |")
    print("|---|" + "|".join("---" for _ in runs) + "|")
    for c in CFG:
        cells = [f"{x['correct']} / {x['format']} / {x['silent']} / {x['loud']}" for x in agg[c]]
        print(f"| {LABEL[c]} | " + " | ".join(cells) + " |")

    print("\n## Paired deltas (computed per run, then summarised)\n")
    print("| delta | execution (pts) | strict accuracy (pts) | verdict |")
    print("|---|---|---|---|")
    for a, b in (("A", "B"), ("A", "C"), ("A", "D"), ("C", "D")):
        de = [agg[b][i]["execution"] - agg[a][i]["execution"] for i in range(len(runs))]
        da = [agg[b][i]["strict"] - agg[a][i]["strict"] for i in range(len(runs))]
        within = min(da) <= 0 <= max(da)
        verdict = ("accuracy delta WITHIN noise (range spans 0)" if within
                   else "accuracy delta ROBUST (range excludes 0)")
        print(f"| {a} -> {b} | {ms(de)} | {ms(da)} | {verdict} |")

    for dim, key in (("database", "db"), ("difficulty", "difficulty")):
        vals = sorted({r[key] for r in by_run[runs[0]]},
                      key=lambda v: "EMH".index(v) if key == "difficulty" else v)
        print(f"\n## By {dim} — strict accuracy % / execution %, mean [min-max]\n")
        print("| config | " + " | ".join(vals) + " |")
        print("|---|" + "|".join("---" for _ in vals) + "|")
        for c in CFG:
            cells = []
            for v in vals:
                m = per_run(by_run, c, key, v)
                cells.append(f"{ms([x['strict'] for x in m])} / {ms([x['execution'] for x in m])}")
            print(f"| {LABEL[c]} | " + " | ".join(cells) + " |")

    print("\n## Per-question stability across runs (direct noise measurement)\n")
    idx = defaultdict(dict)
    for run in runs:
        for r in by_run[run]:
            idx[(r["config"], r["id"])][run] = r["category"]
    unstable = {k: v for k, v in idx.items() if len(set(v.values())) > 1}
    print(f"- (config, question) cells: {len(idx)}")
    print(f"- **cells whose category changed across runs: {len(unstable)} "
          f"({100*len(unstable)/len(idx):.1f}%)**")
    per_cfg = Counter(k[0] for k in unstable)
    print(f"- by config: {dict(sorted(per_cfg.items()))}")
    print("\n| config \\| question | run1 | run2 | run3 |")
    print("|---|---|---|---|")
    for k in sorted(unstable, key=lambda t: (t[0], t[1])):
        v = unstable[k]
        print(f"| {k[0]} \\| {k[1]} | " + " | ".join(v.get(r, "-") for r in runs) + " |")

    print("\n## Retry + memory stats (mean over runs)\n")
    for c in ("B", "D"):
        att, fixed, corr = Counter(), [], []
        for run in runs:
            sub = [r for r in by_run[run] if r["config"] == c]
            att.update(r["attempts"] for r in sub)
            fixed.append(sum(1 for r in sub if r["attempts"] > 1 and r["category"] != "loud"))
            corr.append(sum(1 for r in sub if r["attempts"] > 1 and r["category"] == "correct"))
        print(f"- **{LABEL[c]}**: attempts {dict(sorted(att.items()))} (3 runs pooled); "
              f"retried-and-ran {ms(fixed)}; retried-and-correct {ms(corr)}")

    import re
    from seed_memory import TECHNIQUE_COVERAGE
    exp = defaultdict(set)
    for db, t in TECHNIQUE_COVERAGE.items():
        for tech, spec in t.items():
            p = spec.split("#")[0]
            for num in re.findall(r"\d+", spec):
                exp[f"{p}#{num}"].add(tech)
    for c in ("C", "D"):
        hits, accs_hit, accs_miss, leaks = [], [], [], 0
        for run in runs:
            sub = [r for r in by_run[run] if r["config"] == c]
            h = [r for r in sub if {e["technique"] for e in r["examples"]} & exp.get(r["id"], set())]
            m = [r for r in sub if r not in h]
            hits.append(100 * len(h) / len(sub))
            accs_hit.append(100 * sum(1 for r in h if r["category"] == "correct") / len(h))
            accs_miss.append(100 * sum(1 for r in m if r["category"] == "correct") / len(m) if m else 0)
            leaks += sum(1 for r in sub for e in r["examples"] if not str(e["id"]).startswith("tp:"))
        print(f"- **{LABEL[c]}**: same-technique hit {ms(hits)}% | accuracy when hit "
              f"{ms(accs_hit)}% | when miss {ms(accs_miss)}% | gold leaks {leaks}")

    print("\n## Cost (mean over runs; wall clock excludes >600s idle outliers)\n")
    print("| config | llm calls | prompt tokens | completion tokens | median s/question |")
    print("|---|---|---|---|---|")
    from statistics import median
    for c in CFG:
        calls, pt, ct, med = [], [], [], []
        for run in runs:
            sub = [r for r in by_run[run] if r["config"] == c]
            calls.append(sum(r["llm_calls"] for r in sub))
            pt.append(sum(r["prompt_tokens"] for r in sub))
            ct.append(sum(r["completion_tokens"] for r in sub))
            el = [r["elapsed_s"] for r in sub if r["elapsed_s"] < 600]
            med.append(median(el))
        print(f"| {LABEL[c]} | {ms(calls)} | {mean(pt):,.0f} | {mean(ct):,.0f} | {ms(med)} |")


if __name__ == "__main__":
    main()
