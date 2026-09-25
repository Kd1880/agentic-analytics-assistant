"""
db.py — database connection + schema introspection.

Engine-agnostic by design: every function below works identically against
PostgreSQL and SQLite. The ONLY thing that differs is the connection URL.
"""

from sqlalchemy import create_engine, inspect, text

# --- config seam -----------------------------------------------------------
# Switching the agent to another database is a change HERE, never in the code.
DATABASES = {
    "soccer":    "sqlite:///data/soccer/database.sqlite",
    "movielens": "postgresql+psycopg2://postgres:pass@localhost:5432/movielens",
    "olist":     "postgresql+psycopg2://postgres:pass@localhost:5432/olist",
}


def get_engine(db_url: str):
    """Build a SQLAlchemy Engine (a connection factory + pool) from a URL."""
    return create_engine(db_url)


def _is_internal(table_name: str) -> bool:
    """True for engine bookkeeping tables that are not the user's data."""
    return table_name.startswith(("sqlite_", "pg_", "sql_"))


def get_schema_text(engine, max_cols_per_table: int | None = None) -> str:
    """
    Introspect the database and render it as CREATE TABLE-style DDL text.

    This string is what the LLM sees. It is the model's entire knowledge of
    the database, so anything missing here, the model will have to guess.
    """
    insp = inspect(engine)
    tables = [t for t in sorted(insp.get_table_names()) if not _is_internal(t)]

    blocks = []
    for table in tables:
        cols = insp.get_columns(table)
        pk_cols = set(insp.get_pk_constraint(table).get("constrained_columns") or [])
        fks = insp.get_foreign_keys(table)

        shown, hidden = cols, 0
        if max_cols_per_table and len(cols) > max_cols_per_table:
            shown, hidden = cols[:max_cols_per_table], len(cols) - max_cols_per_table

        lines = [f"CREATE TABLE {table} ("]
        for c in shown:
            flag = " PRIMARY KEY" if c["name"] in pk_cols else ""
            lines.append(f"    {c['name']} {c['type']}{flag},")
        if hidden:
            lines.append(f"    -- ... {hidden} more columns omitted")

        for fk in fks:
            src = ", ".join(fk["constrained_columns"])
            dst_cols = ", ".join(fk["referred_columns"])
            lines.append(f"    FOREIGN KEY ({src}) REFERENCES {fk['referred_table']}({dst_cols}),")

        lines[-1] = lines[-1].rstrip(",")
        lines.append(");")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def run_sql(engine, sql: str):
    """Execute SQL and return (column_names, rows)."""
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        return list(result.keys()), result.fetchall()


if __name__ == "__main__":
    import sys

    name = sys.argv[1] if len(sys.argv) > 1 else "soccer"
    eng = get_engine(DATABASES[name])
    schema = get_schema_text(eng)
    print(schema)
    print(f"\n--- {name}: {len(schema)} chars, ~{len(schema)//4} tokens ---")
