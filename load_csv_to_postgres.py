import argparse
import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


def clean_table_name(fname: str, strip_prefix: str, strip_suffix: str) -> str:
    name = Path(fname).stem.lower()
    if strip_prefix and name.startswith(strip_prefix):
        name = name[len(strip_prefix):]
    if strip_suffix and name.endswith(strip_suffix):
        name = name[: -len(strip_suffix)]
    return re.sub(r"[^a-z0-9_]", "_", name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv-dir", required=True, help="folder containing .csv files")
    ap.add_argument("--db", required=True, help="target Postgres database name")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", default="5432")
    ap.add_argument("--user", default="postgres")
    ap.add_argument("--password", default="pass")
    ap.add_argument("--strip-prefix", default="")
    ap.add_argument("--strip-suffix", default="")
    ap.add_argument("--chunksize", type=int, default=10000)
    args = ap.parse_args()

    url = f"postgresql+psycopg2://{args.user}:{args.password}@{args.host}:{args.port}/{args.db}"
    engine = create_engine(url)

    csvs = sorted(Path(args.csv_dir).glob("*.csv"))
    if not csvs:
        raise SystemExit(f"No CSV files found in {args.csv_dir}")

    for csv in csvs:
        table = clean_table_name(csv.name, args.strip_prefix, args.strip_suffix)
        print(f"Loading {csv.name} -> table '{table}' ...", flush=True)
        # low_memory=False avoids mixed-type inference warnings on big files
        df = pd.read_csv(csv, low_memory=False)
        df.columns = [re.sub(r"[^a-z0-9_]", "_", c.strip().lower()) for c in df.columns]
        df.to_sql(table, engine, if_exists="replace", index=False,
                  chunksize=args.chunksize, method="multi")
        print(f"  {len(df):,} rows.", flush=True)

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' ORDER BY table_name"))
        print("\nTables now in DB:", [r[0] for r in rows])
    print("\nDone. Next: run the per-dataset keys SQL to add primary/foreign keys + indexes.")


if __name__ == "__main__":
    main()
