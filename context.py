"""
context.py — Phase 4a: schema linking with sample values.

The baseline schema text gives the model column NAMES and TYPES but never
shows what the values LOOK like, so it could not know that `genres` holds
'Action|Comedy' or that `title` holds 'Toy Story (1995)'. Both Phase 2
silent failures came from that blind spot.

enrich_schema() appends a few real sample values per column as SQL comments.
It does not modify db.py; it takes db.py's schema text and annotates it.
"""

import re
from decimal import Decimal

from db import run_sql

MAX_VALUE_CHARS = 40      # truncate long text so one column can't flood the prompt
BLOB_CHARS = 200          # values longer than this are treated as blobs and skipped


def _fmt(value) -> str | None:
    """Render one sampled value compactly, or None if it should be skipped."""
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray, memoryview)):
        return None                                    # blob: never useful in a prompt
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    text = re.sub(r"\s+", " ", str(value)).strip()      # collapse newlines/tabs
    if not text:
        return None
    if len(text) > BLOB_CHARS:
        return None
    if len(text) > MAX_VALUE_CHARS:
        text = text[:MAX_VALUE_CHARS] + "..."
    return f"'{text}'"


def sample_values(engine, table: str, k: int = 3, max_rows: int = 50) -> dict:
    """{column: [up to k distinct sample values]} from one pass over the table."""
    try:
        cols, rows = run_sql(engine, f'SELECT * FROM "{table}" LIMIT {max_rows}')
    except Exception:
        return {}                                      # unreadable table: enrich nothing

    out = {}
    for i, col in enumerate(cols):
        seen = []
        for row in rows:
            v = _fmt(row[i])
            if v is not None and v not in seen:
                seen.append(v)
                if len(seen) == k:
                    break
        if seen:
            out[col] = seen
    return out


def enrich_schema(engine, schema_text: str, k: int = 3) -> str:
    """Annotate db.py's DDL text with 'e.g.' sample values per column."""
    table_re = re.compile(r"^CREATE TABLE (\S+) \($")
    col_re = re.compile(r"^    (\w+) ")

    samples, table = {}, None
    out_lines = []

    for line in schema_text.split("\n"):
        m = table_re.match(line)
        if m:
            table = m.group(1)
            samples = sample_values(engine, table, k)
            out_lines.append(line)
            continue

        cm = col_re.match(line)
        if cm and table and not line.startswith("    FOREIGN KEY"):
            vals = samples.get(cm.group(1))
            if vals:
                out_lines.append(f"{line}   -- e.g. {', '.join(vals)}")
                continue
        out_lines.append(line)

    return "\n".join(out_lines)


if __name__ == "__main__":
    import sys
    from db import DATABASES, get_engine, get_schema_text

    name = sys.argv[1] if len(sys.argv) > 1 else "movielens"
    eng = get_engine(DATABASES[name])
    base = get_schema_text(eng)
    rich = enrich_schema(eng, base)
    print(rich)
    print(f"\n--- {name}: {len(base)} -> {len(rich)} chars "
          f"(~{len(base)//4} -> ~{len(rich)//4} tokens, "
          f"+{round(100*(len(rich)-len(base))/len(base))}%) ---")
