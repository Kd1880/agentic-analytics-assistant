"""
guardrails.py — Phase 5: an execution WRAPPER around the model's SQL.

Design principle: the model's SQL is executed UNCHANGED. Every guard lives at
the execution layer, never in the generation prompt.

The baseline's prompt rule "always add a LIMIT" put a display concern into
query semantics and truncated MovieLens #6 (10 arbitrary rows of 951 groups).
Here, max_rows caps the FETCH; the database still answers the whole question.
"""

import re
import time

from sqlalchemy import text

TIMEOUT_DEFAULT_S = 10

# statement-initial keywords we allow
ALLOWED_START = re.compile(r"^\s*(SELECT|WITH)\b", re.I)

# anything that writes or changes structure
FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|"
    r"COPY|VACUUM|ATTACH|DETACH|PRAGMA|REINDEX|CALL|DO|SET|COMMIT|ROLLBACK)\b", re.I)


class GuardrailError(Exception):
    """The SQL was rejected before execution. Never sent to the database."""


def _strip_literals_and_comments(sql: str) -> str:
    """Blank out string literals and comments so keyword/;-scanning is safe.

    Without this, `WHERE status = 'delete'` would look like a DELETE statement
    and `SELECT 'a;b'` would look like two statements.
    """
    sql = re.sub(r"--[^\n]*", " ", sql)              # line comments
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)  # block comments
    sql = re.sub(r"'(?:''|[^'])*'", "''", sql)        # single-quoted literals
    sql = re.sub(r'"(?:""|[^"])*"', '""', sql)        # quoted identifiers
    return sql


def validate_sql(sql: str) -> str:
    """Return the SQL unchanged, or raise GuardrailError. Read-only + single statement."""
    if not sql or not sql.strip():
        raise GuardrailError("empty SQL")

    scan = _strip_literals_and_comments(sql).strip().rstrip(";").strip()

    if ";" in scan:
        raise GuardrailError("multiple statements are not allowed (stacked query)")
    if not ALLOWED_START.match(scan):
        first = scan.split()[0] if scan.split() else "?"
        raise GuardrailError(f"only SELECT/WITH queries are allowed, got '{first.upper()}'")
    bad = FORBIDDEN.search(scan)
    if bad:
        raise GuardrailError(f"forbidden keyword '{bad.group(1).upper()}' in a read-only query")
    return sql                                        # unchanged: we never rewrite SQL


# --- dialect-specific timeouts ---------------------------------------------
# Postgres has a server-side statement_timeout. SQLite has NO equivalent, so we
# interrupt from the client with a progress handler. Engine-agnosticism ends here.
def _apply_timeout(conn, dialect: str, timeout_s: float):
    """Arm a timeout. Returns a cleanup callable."""
    if dialect == "postgresql":
        conn.execute(text(f"SET LOCAL statement_timeout = {int(timeout_s * 1000)}"))
        return lambda: None                           # SET LOCAL dies with the transaction

    if dialect == "sqlite":
        raw = getattr(conn.connection, "dbapi_connection", conn.connection)
        deadline = time.monotonic() + timeout_s
        raw.set_progress_handler(
            lambda: 1 if time.monotonic() > deadline else 0, 1000)
        return lambda: raw.set_progress_handler(None, 0)

    return lambda: None                               # unknown dialect: no timeout


def run_sql_safe(engine, sql: str, max_rows: int | None = None,
                 timeout_s: float = TIMEOUT_DEFAULT_S):
    """Validate, execute with a timeout, fetch at most max_rows.

    Returns (cols, rows, truncated). max_rows=None fetches everything (eval path).
    max_rows caps the FETCH only -- it is never injected into the SQL.
    """
    validate_sql(sql)

    with engine.connect() as conn:
        with conn.begin():                            # so SET LOCAL has a scope
            cleanup = _apply_timeout(conn, engine.dialect.name, timeout_s)
            try:
                result = conn.execute(text(sql))
                cols = list(result.keys())
                if max_rows is None:
                    rows, truncated = result.fetchall(), False
                else:
                    batch = result.fetchmany(max_rows + 1)   # +1 detects "there is more"
                    truncated = len(batch) > max_rows
                    rows = batch[:max_rows]
                return cols, rows, truncated
            finally:
                cleanup()


# --- error classification (Phase 3 finding #4) ------------------------------
# Exception CLASS is not enough: Postgres raises ProgrammingError for a bad
# column, but SQLite raises OperationalError for a missing table. Same kind of
# mistake, different class. So we look at the driver's code/message.
_SQLITE_SQL_ERRORS = re.compile(
    r"no such (table|column|function|module)|syntax error|ambiguous column|"
    r"wrong number of arguments|misuse of aggregate|no such collation", re.I)

_PG_OPERATIONAL_CLASSES = ("08", "53", "57", "58")     # connection, resources, cancelled, system


def classify_error(exc: Exception) -> str:
    """'sql' -> the model can fix it, feed to the retry loop.
       'operational' -> infrastructure/timeout, fail fast; retrying is meaningless."""
    orig = getattr(exc, "orig", exc)

    pgcode = getattr(orig, "pgcode", None)             # psycopg2 SQLSTATE
    if pgcode:
        return "operational" if pgcode[:2] in _PG_OPERATIONAL_CLASSES else "sql"

    msg = str(orig)
    if _SQLITE_SQL_ERRORS.search(msg):
        return "sql"
    if re.search(r"interrupted|database is locked|unable to open database|"
                 r"connection|timeout|refused|terminat", msg, re.I):
        return "operational"

    # SQLAlchemy class as a last resort
    return "operational" if type(exc).__name__ in (
        "OperationalError", "InterfaceError", "DisconnectionError") else "sql"
