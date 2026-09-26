"""
migrate_to_cloud.py — copy the three local databases into a hosted Postgres.

Run this LOCALLY. It reads from your local Docker Postgres (MovieLens, Olist)
and the local SQLite file (European Soccer), and writes into one target
Postgres database as three SCHEMAS, so DB_MOVIELENS / DB_OLIST / DB_SOCCER each
resolve to their own namespace.

    TARGET_PG='postgresql+psycopg2://user:pass@host/neondb?sslmode=require' \
        python migrate_to_cloud.py                 # PLAN: measure + report, copy nothing
    TARGET_PG=... python migrate_to_cloud.py --apply

Only the HOST changes. Table names, column names and rows are identical, so the
agent's introspection, the gold answers and the grader all still apply.

NOTHING IS DROPPED OR TRIMMED unless you pass an explicit flag. Plan mode tells
you what it would recommend and why; it never decides for you.

    --skip-table olist.geolocation        omit a table entirely
    --skip-match-xml                     omit Match's 8 XML event columns (~269 MB)
    --apply                              actually copy
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

# Sources are the local development stack (db.py's frozen URLs are the same hosts).
SOURCES = {
    "movielens": "postgresql+psycopg2://postgres:pass@localhost:5432/movielens",
    "olist": "postgresql+psycopg2://postgres:pass@localhost:5432/olist",
    "soccer": "sqlite:///data/soccer/database.sqlite",
}

KEYS_SQL = {
    "movielens": ["keys_movielens.sql"],
    "olist": ["keys_olist.sql", "fix_olist_orphans.sql"],
    "soccer": [],  # SQLite source carries its own keys; nothing to re-apply
}

# Match's event columns hold XML blobs: ~269 MB of the 313 MB SQLite file.
# No gold question uses them (they use home_team_goal / away_team_goal / season).
MATCH_XML_COLUMNS = [
    "goal", "shoton", "shotoff", "foulcommit", "card", "cross", "corner", "possession",
]

NEON_FREE_BYTES = 512 * 1024 * 1024          # 0.5 GB
WARN_AT = 0.80                                # warn from 80% of the quota
CHUNK = 20_000                                # rows per insert batch


# --------------------------------------------------------------------------- #
# measuring
# --------------------------------------------------------------------------- #
def pg_table_sizes(engine) -> dict[str, int]:
    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT c.relname, pg_total_relation_size(c.oid)
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
        """)).fetchall()
    return {r[0]: int(r[1]) for r in rows}


def sqlite_table_sizes(engine, skip_cols: dict[str, list[str]]) -> dict[str, int]:
    """dbstat is not always compiled in, so estimate from real column lengths."""
    insp = inspect(engine)
    out: dict[str, int] = {}
    with engine.connect() as c:
        for t in insp.get_table_names():
            if t.startswith("sqlite_"):
                continue
            cols = [col["name"] for col in insp.get_columns(t)]
            drop = set(skip_cols.get(t, []))
            keep = [col for col in cols if col not in drop]
            if not keep:
                out[t] = 0
                continue
            expr = " + ".join(f'COALESCE(LENGTH(CAST("{col}" AS TEXT)),0)' for col in keep)
            total = c.execute(text(f'SELECT COALESCE(SUM({expr}),0) FROM "{t}"')).scalar()
            out[t] = int(total or 0)
    return out


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024 or unit == "GB":
            return f"{n:,.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0
    return f"{n:.1f} GB"


# --------------------------------------------------------------------------- #
# copying
# --------------------------------------------------------------------------- #
def copy_table(src_engine, tgt_engine, schema: str, table: str,
               skip_cols: list[str]) -> int:
    """Stream one table across in batches. Returns rows copied."""
    import pandas as pd

    insp = inspect(src_engine)
    cols = [c["name"] for c in insp.get_columns(table)]
    keep = [c for c in cols if c not in set(skip_cols)]
    quoted = ", ".join(f'"{c}"' for c in keep)
    select = f'SELECT {quoted} FROM "{table}"'

    total = 0
    first = True
    for chunk in pd.read_sql(select, src_engine, chunksize=CHUNK):
        chunk.to_sql(table.lower(), tgt_engine, schema=schema,
                     if_exists="replace" if first else "append",
                     index=False, method="multi", chunksize=1000)
        total += len(chunk)
        first = False
        print(f"      {table}: {total:,} rows", end="\r", flush=True)
    if first:  # empty table: still create it
        import pandas as pd
        pd.DataFrame(columns=keep).to_sql(table.lower(), tgt_engine, schema=schema,
                                          if_exists="replace", index=False)
    print(f"      {table}: {total:,} rows copied      ")
    return total


def apply_keys(tgt_engine, schema: str, files: list[str]) -> None:
    """Re-apply the keys/index scripts inside the target schema.

    Statements run one at a time and failures are reported but do not stop the
    run, mirroring psql's default: keys_olist.sql has one FK that legitimately
    fails on orphan rows, which fix_olist_orphans.sql then repairs.
    """
    for fname in files:
        path = Path(fname)
        if not path.exists():
            print(f"      ! {fname} not found, skipping")
            continue
        sql = path.read_text(encoding="utf-8")
        statements = [s.strip() for s in sql.split(";") if s.strip() and
                      not all(line.strip().startswith("--")
                              for line in s.strip().splitlines() if line.strip())]
        ok = fail = 0
        for stmt in statements:
            try:
                with tgt_engine.begin() as c:
                    c.execute(text(f"SET LOCAL search_path TO {schema}"))
                    c.execute(text(stmt))
                ok += 1
            except Exception as exc:
                fail += 1
                msg = str(getattr(exc, "orig", exc)).splitlines()[0][:110]
                print(f"      ! {msg}")
        print(f"      {fname}: {ok} ok, {fail} failed")


def target_url_for(base: str, schema: str) -> str:
    """The same target database, with search_path pinned to one schema."""
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}options=-csearch_path%3D{schema}"


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="actually copy (default is a dry-run plan)")
    ap.add_argument("--skip-table", action="append", default=[],
                    metavar="DB.TABLE", help="e.g. --skip-table olist.geolocation")
    ap.add_argument("--skip-match-xml", action="store_true",
                    help="omit Match's 8 XML event columns (~269 MB, unused by every gold question)")
    ap.add_argument("--quota-bytes", type=int, default=NEON_FREE_BYTES)
    args = ap.parse_args()

    target = os.getenv("TARGET_PG")
    if not target:
        print("TARGET_PG is not set.\n"
              "  TARGET_PG='postgresql+psycopg2://user:pass@host/neondb?sslmode=require' \\\n"
              "      python migrate_to_cloud.py")
        return 2
    if target.startswith("postgres://"):
        target = target.replace("postgres://", "postgresql+psycopg2://", 1)

    skip_tables = {s.lower() for s in args.skip_table}
    skip_cols = {"Match": MATCH_XML_COLUMNS} if args.skip_match_xml else {}

    print("=" * 74)
    print(f"{'PLAN (nothing will be copied)' if not args.apply else 'APPLY'}"
          f"  ->  target host: {target.split('@')[-1].split('/')[0]}")
    print("=" * 74)

    # ---------------- measure ----------------
    plan: dict[str, dict[str, int]] = {}
    grand = 0
    for name, url in SOURCES.items():
        try:
            eng = create_engine(url)
            sizes = (sqlite_table_sizes(eng, skip_cols) if url.startswith("sqlite")
                     else pg_table_sizes(eng))
        except Exception as exc:
            print(f"\n  {name}: CANNOT READ SOURCE -> {type(exc).__name__}: "
                  f"{str(getattr(exc, 'orig', exc))[:90]}")
            return 1
        sizes = {t: s for t, s in sizes.items()
                 if f"{name}.{t}".lower() not in skip_tables}
        plan[name] = sizes
        sub = sum(sizes.values())
        grand += sub
        est = " (estimated)" if url.startswith("sqlite") else ""
        print(f"\n  {name}  [{'SQLite' if url.startswith('sqlite') else 'PostgreSQL'}]"
              f"  ->  schema \"{name}\"{est}")
        for t, s in sorted(sizes.items(), key=lambda kv: -kv[1]):
            print(f"      {t:<40}{human(s):>12}")
        print(f"      {'— subtotal':<40}{human(sub):>12}")

    print("\n" + "-" * 74)
    print(f"  {'TOTAL':<40}{human(grand):>12}")
    print(f"  {'quota':<40}{human(args.quota_bytes):>12}"
          f"   ({100 * grand / args.quota_bytes:.0f}% used)")

    # ---------------- warn ----------------
    over = grand > args.quota_bytes
    near = grand > args.quota_bytes * WARN_AT
    if over or near:
        print("\n" + ("!" * 74))
        print("  OVER QUOTA" if over else "  APPROACHING QUOTA")
        print("!" * 74)
        print("  Nothing has been dropped. These are the candidates, largest first,")
        print("  with what each costs you:\n")
        if not args.skip_match_xml and "Match" in plan.get("soccer", {}):
            print("   --skip-match-xml")
            print("      Match's goal/shoton/shotoff/foulcommit/card/cross/corner/possession")
            print("      columns hold XML event feeds: ~269 MB, about 86% of the Soccer data.")
            print("      NO gold question reads them (they use home_team_goal, away_team_goal,")
            print("      season, league_id, team ids). Strongly recommended.\n")
        geo = plan.get("olist", {}).get("geolocation")
        if geo and "olist.geolocation" not in skip_tables:
            print("   --skip-table olist.geolocation")
            print(f"      {human(geo)}. No gold question joins it; the Olist questions use")
            print("      orders, order_items, customers, products, sellers, payments, reviews.\n")
        pa = plan.get("soccer", {}).get("Player_Attributes")
        if pa:
            print("   (last resort) subset soccer.Player_Attributes")
            print(f"      {human(pa)}, but gold sc#9 DOES use it — trimming changes answers.")
            print("      Prefer the two options above.\n")
        if over and args.apply:
            print("  Refusing to copy while over quota. Re-run with the flags above,")
            print("  or raise --quota-bytes if your plan is larger.")
            return 1

    if not args.apply:
        print("\n  This was a plan. Re-run with --apply to copy.")
        return 0

    # ---------------- copy ----------------
    tgt = create_engine(target, pool_pre_ping=True)
    try:
        with tgt.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as exc:
        print(f"\n  cannot reach the target: {type(exc).__name__}: "
              f"{str(getattr(exc, 'orig', exc))[:120]}")
        return 1

    for name, url in SOURCES.items():
        print(f"\n  ---- {name} -> schema \"{name}\" ----")
        with tgt.begin() as c:
            c.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{name}"'))
        src = create_engine(url)
        for table in plan[name]:
            copy_table(src, tgt, name, table, skip_cols.get(table, []))
        if KEYS_SQL[name]:
            print(f"    re-applying keys/indexes:")
            apply_keys(tgt, name, KEYS_SQL[name])

    # ---------------- verify + report ----------------
    print("\n" + "=" * 74)
    print("  TARGET SIZES AFTER LOAD")
    print("=" * 74)
    total_after = 0
    with tgt.connect() as c:
        for name in SOURCES:
            rows = c.execute(text("""
                SELECT c.relname, pg_total_relation_size(c.oid)
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = :s AND c.relkind = 'r'
                ORDER BY 2 DESC
            """), {"s": name}).fetchall()
            sub = sum(int(r[1]) for r in rows)
            total_after += sub
            print(f"\n  {name}")
            for r in rows:
                print(f"      {r[0]:<40}{human(int(r[1])):>12}")
            print(f"      {'— subtotal':<40}{human(sub):>12}")
    print(f"\n  {'TOTAL ON TARGET':<40}{human(total_after):>12}"
          f"   ({100 * total_after / args.quota_bytes:.0f}% of quota)")

    base = target
    print("\n" + "=" * 74)
    print("  PASTE THESE INTO RENDER'S ENVIRONMENT (use your READ-ONLY role's password)")
    print("=" * 74)
    for name in SOURCES:
        print(f"\nDB_{name.upper()}={target_url_for(base, name)}")

    print("\n" + "=" * 74)
    print("  SECURITY — do this before going live")
    print("=" * 74)
    print("""
  1. Create a READ-ONLY role and use IT in the DB_* URLs above. The SELECT-only
     guardrail in guardrails.py is defence in depth, not a substitute for
     database permissions — if it is ever bypassed, the role must still refuse
     to write:

       CREATE ROLE askdb_ro LOGIN PASSWORD '<a strong password>';
       GRANT CONNECT ON DATABASE <db> TO askdb_ro;
       GRANT USAGE ON SCHEMA movielens, olist, soccer TO askdb_ro;
       GRANT SELECT ON ALL TABLES IN SCHEMA movielens, olist, soccer TO askdb_ro;
       ALTER DEFAULT PRIVILEGES IN SCHEMA movielens, olist, soccer
         GRANT SELECT ON TABLES TO askdb_ro;
       -- and make sure it cannot create anything:
       REVOKE CREATE ON SCHEMA movielens, olist, soccer FROM askdb_ro;

  2. Every secret goes in Render's dashboard (Environment), never in the repo:
     GEMINI_API_KEY, DB_MOVIELENS, DB_OLIST, DB_SOCCER. render.yaml marks them
     sync:false precisely so Render prompts for them instead of storing them here.

  3. Set ALLOWED_ORIGINS to your frontend's origin. With APP_ENV=production the
     backend refuses to start on "*", so this is not something you can forget.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
