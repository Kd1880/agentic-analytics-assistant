# Backend — deployment guide

FastAPI service that answers plain-English questions over a SQL database.
The LLM provider and the database URLs are **configuration**, not code:

| | development | deployment |
|---|---|---|
| LLM | Ollama `qwen2.5-coder:7b` (local, free) | Google Gemini Flash (hosted) |
| switch | `LLM_PROVIDER=ollama` | `LLM_PROVIDER=gemini` |

Both providers speak the **OpenAI-compatible** API, so only `base_url`, `api_key`
and `model` change — the prompt, the schema introspection, the guardrails and the
self-correction loop are identical in both.

## 1. Get a Gemini API key (free tier)

1. Go to **https://aistudio.google.com/apikey**
2. Sign in with a Google account and click **Create API key**.
3. Copy the key. It is shown once.

The free tier has per-minute and per-day request limits (the exact numbers for your
account are on your AI Studio rate-limit page). The backend retries `429` responses with
backoff (2s, 8s, 20s) and returns a `503` with a clear message rather than crashing.

Observed in testing: three back-to-back requests hit the per-minute limit and, with
`LLM_FALLBACK=true`, the third was answered by Ollama instead. That is reported in
`providerFallback` — a fallback answers with a **different model**, so it is never silent.
Spacing requests ~20s apart avoided the limit entirely. Set `LLM_FALLBACK=false` to fail
loudly rather than substitute a model (recommended when measuring model quality).

## 2. Configure locally

```bash
cp .env.example .env          # .env is gitignored -- never commit it
```

Edit `.env`:

```ini
LLM_PROVIDER=gemini
GEMINI_API_KEY=<paste your key>
GEMINI_MODEL=gemini-3.8-flash

DB_MOVIELENS=postgresql+psycopg2://postgres:pass@localhost:5432/movielens
DB_OLIST=postgresql+psycopg2://postgres:pass@localhost:5432/olist
DB_SOCCER=sqlite:///data/soccer/database.sqlite
```

Confirm the model id against the live endpoint rather than trusting the default:

```bash
python llm_provider.py --list-models          # prints text-flash candidates
python llm_provider.py                        # prints config; keys are MASKED
```

## 3. Run

```bash
uvicorn backend.app:app --reload --port 8000
# http://localhost:8000/docs  for the interactive API
```

## 4. Deploy

Set the same variables in the host's **environment settings dashboard** (Render, Railway,
Fly.io, Cloud Run...). Do not ship `.env`.

```
LLM_PROVIDER=gemini
GEMINI_API_KEY=...            <- the host's secret store
GEMINI_MODEL=gemini-3.8-flash
DB_OLIST=postgresql+psycopg2://user:pass@managed-host:5432/olist?sslmode=require
ALLOWED_ORIGINS=https://your-frontend.example.com
```

Start command:

```
uvicorn backend.app:app --host 0.0.0.0 --port $PORT
```

Notes for a hosted deployment:

- **SQLite (Soccer) needs the file on disk.** Either ship `data/soccer/database.sqlite`,
  mount a volume, or omit `DB_SOCCER` — the API only exposes the databases that are
  configured.
- **Set `ALLOWED_ORIGINS`** to your frontend's origin. `*` is convenient locally and too
  permissive in production.
- The database user should be **read-only**. The `SELECT`-only guardrail is defence in
  depth, not a substitute for database permissions.

## 5. API

### `GET /health`
```json
{"status":"ok","provider":"gemini","databases":["movielens","olist","soccer"],"memory":true}
```

### `GET /config`
Effective settings. **Contains no secret values** — the key is reported only as
`key_present` and a masked fragment.

### `GET /databases`
```json
{"databases":[{"name":"olist","dialect":"postgresql","tables":9,"schema_chars":5712,"status":"ready"}]}
```

### `POST /ask`

Request:
```json
{"db": "olist", "question": "What are the top 10 product categories by revenue?"}
```

Response (the frontend contract):
```json
{
  "sql": "SELECT t.product_category_name_english AS category, SUM(oi.price) ...",
  "columns": ["category", "revenue"],
  "rows": [["health_beauty", 1258681.34], ["watches_gifts", 1205005.68]],
  "attempts": 1,
  "succeeded": true,
  "insight": "10 rows returned; top: health_beauty (1,258,681.34).",
  "chartHint": {"type": "bar", "x": "category", "y": "revenue"},
  "provider": "gemini",
  "truncated": false,
  "elapsedMs": 1840,
  "history": []
}
```

| field | meaning |
|---|---|
| `sql` | the SQL that was executed, unmodified |
| `attempts` | 1 = first try worked; >1 = self-correction was used |
| `succeeded` | **the SQL executed** — not a guarantee that the answer is right |
| `insight` | one factual sentence derived from the rows (no LLM call, no speculation) |
| `chartHint` | `bar` / `line` / `scalar` / `table` / `none` for the frontend |
| `provider` | which provider actually answered |
| `providerFallback` | `null` normally; a reason string if the primary failed and the OTHER provider (a different model) answered instead |
| `truncated` | display cap hit; the query itself was never limited |
| `history` | per-attempt SQL + error, when retries happened |

On failure `succeeded` is `false` and `insight` explains whether it was a query problem or
an infrastructure problem. A provider outage returns **503**, never a fabricated answer.

## 6. What the request pipeline does

```
question
  -> db.get_schema_text()          introspect tables/columns/PKs/FKs   (frozen)
  -> context.enrich_schema()       + sample values per column          (Phase 4a)
  -> memory.retrieve(k=3)          + worked examples, same database    (Phase 4b)
  -> llm_provider.generate_sql_via()  Gemini or Ollama, temperature 0  (Phase 7)
  -> guardrails.run_sql_safe()     SELECT-only, timeout, fetch cap     (Phase 5)
       |- SQL error  -> feed the error back, retry (max 3)             (Phase 3)
       |- operational error -> fail fast, do not retry
  -> {sql, columns, rows, insight, chartHint, provider}
```

Evidence for these defaults from the Phase 6 evaluation (45 questions x 3 runs):

- `USE_MEMORY=true` is the setting that matters: **+28.9 accuracy points**, and 92% of that
  gain is attributable to retrieval alone.
- `K_EXAMPLES=3` — dropping to 1 costs **~23 accuracy points**.
- `MAX_RETRIES=3` raises the execution rate (+8.9 pts) but barely changes accuracy
  (+2.2 pts). Keep it as a safety net; it is not an accuracy feature.
- `MAX_ROWS` is a **display** cap applied at fetch time. It is never injected into the SQL,
  so it cannot corrupt an aggregate.

## 7. Secret hygiene

- The key is read **only** from the `GEMINI_API_KEY` environment variable (via `.env`
  locally, the host's secret store in deployment).
- `.env` and `.env.*` are in `.gitignore`; `.env.example` (placeholders only) is tracked.
- `llm_provider.provider_status()` masks the key, and `/config` returns only
  `key_present` plus a masked fragment. Nothing logs a raw key.
- If a key is ever exposed, revoke it in AI Studio and issue a new one — rotation is free.
