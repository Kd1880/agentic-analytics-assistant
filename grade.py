"""
grade.py — compare an agent result to a frozen gold result.

Five rules:
 1. Compare VALUES AND ORDER -- but row order only when order_sensitive.
 2. Relative float tolerance (never equality): Postgres parallel SUM is not
    bit-reproducible (Phase 5 finding).
 3. Normalise REPRESENTATION before comparing: numeric casting (Decimal/float/int),
    whitespace and case on labels, 1x1 table == scalar, column order.
 4. Full fetch is guaranteed upstream (max_rows=None on the eval path).
 5. Classify: correct | loud | silent | format.

RULE 1 vs RULE 3 (the conflict):
    Normalisation must never touch IDENTITY, only representation.
    - Row order is governed ONLY by order_sensitive. The grader never sorts rows
      on its own, because sorting would make Olist #3's wrong ranking (right
      categories, wrong values/order) compare equal to gold -- turning the exact
      silent failure this project studies into a pass.
    - Column order is handled by looking for ONE CONSISTENT column permutation
      that works for every row, not by treating each row as a bag of cells.
      A per-row bag would let Soccer #7's swapped home/away wins pass.
    - A match that needs a permutation (or drops extra columns) is graded
      'format', never 'correct', so strict accuracy stays honest.
"""

from decimal import Decimal
from itertools import combinations, permutations

REL_TOL = 1e-6
ABS_TOL = 1e-9
MAX_COLS_FOR_PERMUTATION = 6      # guards against factorial blow-up


def _norm_cell(v):
    """Normalise one cell to None | float | str (lowercased, whitespace-collapsed)."""
    if v is None:
        return None
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, (int, float, Decimal)):
        return float(v)
    s = " ".join(str(v).split()).strip().lower()
    # a numeric-looking string compares as a number ('1234' == 1234)
    try:
        return float(s)
    except ValueError:
        return s


def _norm_rows(rows):
    return [tuple(_norm_cell(v) for v in row) for row in rows]


def _cells_equal(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, float) and isinstance(b, float):
        if a == b:
            return True
        return abs(a - b) <= max(ABS_TOL, REL_TOL * max(abs(a), abs(b)))
    return a == b


def _rows_equal(r1, r2) -> bool:
    return len(r1) == len(r2) and all(_cells_equal(a, b) for a, b in zip(r1, r2))


def _sort_key(row):
    """Stable canonical key for multiset comparison; numbers rounded so that
    float wobble cannot change the sort order."""
    out = []
    for v in row:
        if v is None:
            out.append((0, ""))
        elif isinstance(v, float):
            out.append((1, f"{v:.6g}"))
        else:
            out.append((2, v))
    return out


def _match(agent_rows, gold_rows, order_sensitive: bool) -> bool:
    """Positional comparison. Row order enforced only when order_sensitive."""
    if len(agent_rows) != len(gold_rows):
        return False
    if order_sensitive:
        return all(_rows_equal(a, g) for a, g in zip(agent_rows, gold_rows))
    a_sorted = sorted(agent_rows, key=_sort_key)
    g_sorted = sorted(gold_rows, key=_sort_key)
    return all(_rows_equal(a, g) for a, g in zip(a_sorted, g_sorted))


def _match_any_column_layout(agent_rows, gold_rows, order_sensitive: bool):
    """Is there ONE consistent choice of columns (subset + order) that matches?

    Returns the winning column index tuple, or None. Applied to every row
    identically, so it cannot rescue a row-level semantic error.
    """
    if not agent_rows or not gold_rows:
        return None
    n_agent, n_gold = len(agent_rows[0]), len(gold_rows[0])
    if n_agent < n_gold or n_agent > MAX_COLS_FOR_PERMUTATION:
        return None
    for subset in combinations(range(n_agent), n_gold):
        for perm in permutations(subset):
            if perm == tuple(range(n_gold)) and n_agent == n_gold:
                continue                      # already tried as the exact match
            projected = [tuple(r[i] for i in perm) for r in agent_rows]
            if _match(projected, gold_rows, order_sensitive):
                return perm
    return None


def grade(gold: dict, succeeded: bool, rows) -> dict:
    """Return {'category', 'detail'} for one (config, question) outcome.

    category: 'loud'    -- did not execute
              'correct' -- values (and order where required) match
              'format'  -- right values, different shape (column layout/extras)
              'silent'  -- executed, wrong answer
    """
    if not succeeded:
        return {"category": "loud", "detail": "did not execute"}

    agent_rows = _norm_rows(rows or [])
    gold_rows = _norm_rows(gold["gold_rows"])
    order_sensitive = bool(gold["order_sensitive"])

    if _match(agent_rows, gold_rows, order_sensitive):
        return {"category": "correct", "detail": "exact match"}

    perm = _match_any_column_layout(agent_rows, gold_rows, order_sensitive)
    if perm is not None:
        return {"category": "format",
                "detail": f"matched after column re-layout {perm}"}

    if len(agent_rows) != len(gold_rows):
        detail = f"row count {len(agent_rows)} != gold {len(gold_rows)}"
    else:
        diffs = sum(0 if _rows_equal(a, g) else 1
                    for a, g in zip(sorted(agent_rows, key=_sort_key),
                                    sorted(gold_rows, key=_sort_key)))
        detail = (f"same row count, {diffs} rows differ"
                  if diffs else "same values, wrong ORDER (order-sensitive question)")
    return {"category": "silent", "detail": detail}


# --------------------------- self-test ---------------------------
if __name__ == "__main__":
    def g(rows, order_sensitive=True):
        return {"gold_rows": rows, "order_sensitive": order_sensitive}

    tests = [
        ("exact scalar", g([[9742]], False), True, [(9742,)], "correct"),
        ("float wobble within tolerance", g([[36689303.31359986]], False), True,
         [(36689303.3135999,)], "correct"),
        ("float difference beyond tolerance", g([[1258681.34]], False), True,
         [(36689303.31,)], "silent"),
        ("Decimal vs float", g([[12.55821709805197]], False), True,
         [(Decimal("12.55821709805197547514"),)], "correct"),
        ("label case/whitespace", g([["Health Beauty", 10]], False), True,
         [("  health beauty ", 10)], "correct"),
        ("numeric string vs number", g([[1996.0, 6040]], True), True,
         [("1996", 6040)], "correct"),
        ("unordered set, shuffled rows", g([["a", 1], ["b", 2]], False), True,
         [("b", 2), ("a", 1)], "correct"),
        ("ORDERED list, shuffled rows -> silent", g([["a", 1], ["b", 2]], True), True,
         [("b", 2), ("a", 1)], "silent"),
        ("columns swapped -> format", g([["sp", 41746]], False), True,
         [(41746, "sp")], "format"),
        ("extra column -> format", g([["a", 1]], False), True,
         [("a", 1, 99)], "format"),
        ("Olist #3 style: right set, wrong values -> silent",
         g([["health_beauty", 1258681.34], ["watches_gifts", 1205005.68]], True), True,
         [("health_beauty", 36689303.31), ("watches_gifts", 24662365.82)], "silent"),
        ("truncated result -> silent", g([["a", 1], ["b", 2], ["c", 3]], False), True,
         [("a", 1)], "silent"),
        ("errored -> loud", g([[1]], False), False, [], "loud"),
        ("NULL handling", g([["a", None]], False), True, [("a", None)], "correct"),
    ]
    passed = 0
    for name, gold, ok, rows, want in tests:
        got = grade(gold, ok, rows)
        mark = "ok  " if got["category"] == want else "FAIL"
        passed += got["category"] == want
        print(f"  [{mark}] {name:<48} -> {got['category']:<8} ({got['detail']})")
    print(f"\n{passed}/{len(tests)} grader self-tests passed")
    assert passed == len(tests)
