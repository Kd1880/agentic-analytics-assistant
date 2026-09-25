"""
agent.py — the Phase 2 spine: question -> SQL -> execute -> rows.

NO self-correction here on purpose. This is the experimental BASELINE
(Config A). Phase 3 will wrap run_sql() in a retry loop; nothing in this
file should need rewriting when it does.
"""

import re
import sys

from openai import OpenAI

from db import DATABASES, get_engine, get_schema_text, run_sql

# --- model config seam -----------------------------------------------------
LLM_BASE_URL = "http://localhost:11434/v1"
LLM_API_KEY = "ollama"          # Ollama ignores it; the client requires one
LLM_MODEL = "qwen2.5-coder:7b"

client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)


SYSTEM_PROMPT = """You are an expert SQL analyst.

Given a database schema and a question, reply with ONE {dialect} SQL query
that answers it.

Rules:
- Output ONLY the SQL. No explanation, no markdown, no commentary.
- Use only tables and columns that appear in the schema below.
- Follow the FOREIGN KEY lines to decide how to join tables.
- Always add a LIMIT unless the question asks for a single aggregate value.

Schema:
{schema}"""


def clean_sql(raw: str) -> str:
    """Strip markdown fences / stray prose so the text can actually execute."""
    text = raw.strip()
    fence = re.search(r"```(?:sql)?\s*(.*?)```", text, re.S | re.I)
    if fence:
        text = fence.group(1)
    # keep from the first SQL keyword onward, in case prose leaks in
    start = re.search(r"\b(SELECT|WITH)\b", text, re.I)
    if start:
        text = text[start.start():]
    return text.strip().rstrip(";").strip()


def generate_sql(question: str, schema: str, dialect: str) -> str:
    """Ask the LLM for SQL. One shot, no feedback -- that is the point."""
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT.format(schema=schema, dialect=dialect)},
            {"role": "user", "content": question},
        ],
        temperature=0,     # deterministic: same question -> same SQL, so evals are repeatable
    )
    return clean_sql(resp.choices[0].message.content)


def print_rows(cols, rows, limit=20):
    print(" | ".join(str(c) for c in cols))
    print("-" * 60)
    for r in rows[:limit]:
        print(" | ".join("NULL" if v is None else str(v) for v in r))
    if len(rows) > limit:
        print(f"... {len(rows) - limit} more rows")
    print(f"({len(rows)} rows)")


def ask(db_name: str, question: str):
    engine = get_engine(DATABASES[db_name])
    dialect = engine.dialect.name          # 'sqlite' or 'postgresql'
    schema = get_schema_text(engine)

    print(f"\nQ: {question}   [{db_name} / {dialect}]")
    sql = generate_sql(question, schema, dialect)
    print(f"\nSQL:\n{sql}\n")

    cols, rows = run_sql(engine, sql)      # Phase 3 will wrap THIS in try/except
    print_rows(cols, rows)


if __name__ == "__main__":
    ask(sys.argv[1], " ".join(sys.argv[2:]))
