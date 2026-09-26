# Deploying to Railway

Backend on Railway (nixpacks), data in a Railway Postgres. No volume and no SQLite file
are needed on the host — the migration script copies all three databases into Postgres as
three schemas.

---

## ⚠️ Root Directory must stay at the repo root

Railway's **Root Directory must be `/` (the default)**, *not* `backend`.

`backend/app.py` imports six modules that live at the repo root:

```python
from context import enrich_schema
from db import get_engine, get_schema_text          # frozen experiment control
from guardrails import GuardrailError, classify_error, run_sql_safe
from llm_provider import ...
from memory import Memory
from self_correct import CORRECTION_PROMPT          # which imports agent.py
```

With Root Directory = `backend`, those files are outside the build context and the app dies
at startup with `ModuleNotFoundError: No module named 'context'`. A second reason: `memory.py`
loads `memory_store.json` **relative to the working directory**, so the 78-pair retrieval pool
is only found when the process starts at the repo root.

That is why the start command is `uvicorn backend.app:app` (module path from the root) and not
`uvicorn app:app`, and why there is no `backend/requirements.txt` or `backend/Procfile` —
they would only take effect under a configuration that cannot work.

---

## Files Railway uses

| File | Role |
|---|---|
`railway.json` | builder = NIXPACKS, start command, health check on `/health` |
`Procfile` | `web: uvicorn backend.app:app --host 0.0.0.0 --port $PORT` (same command; harmless duplication, works if `railway.json` is ignored) |
`requirements.txt` | repo root — nixpacks detects Python from it |
`runtime.txt` | `python-3.13` — the version the study was run on |

`--host 0.0.0.0` is required (Railway routes to the container's external interface) and
`--port $PORT` uses the port Railway injects. Both are already set.

---

## Step 1 — create the Postgres database

1. https://railway.app → **New Project**
2. **+ Create** → **Database** → **Add PostgreSQL**
3. Open the Postgres service → **Variables** tab. Note these two:
   - `DATABASE_URL` — the **internal** URL (`postgres.railway.internal`). Only reachable
     *inside* Railway. **This is what the backend uses.**
   - `DATABASE_PUBLIC_URL` — the **external** proxy URL (`...proxy.rlwy.net:PORT`).
     Reachable from your laptop. **This is what the migration uses.**

The database is named `railway`. The migration creates three **schemas** inside it
(`movielens`, `olist`, `soccer`), so one database serves all three.

---

## Step 2 — migrate the data (run locally, script unchanged)

Your local Docker Postgres must be running, and `data/soccer/database.sqlite` present.

```bash
# use the PUBLIC url — the internal one is not reachable from your machine
export TARGET_PG='postgresql+psycopg2://postgres:PASS@HOST.proxy.rlwy.net:PORT/railway?sslmode=require'

python migrate_to_cloud.py                              # plan only: measures, copies nothing
python migrate_to_cloud.py --skip-match-xml --apply     # recommended
```

`migrate_to_cloud.py` is used **unchanged**: it already reads `TARGET_PG`, converts a
`postgres://` URL to `postgresql+psycopg2://`, runs `CREATE SCHEMA IF NOT EXISTS` per
database, streams every table in 20k-row batches, re-applies `keys_movielens.sql`,
`keys_olist.sql` and `fix_olist_orphans.sql` inside each schema, then prints the three
ready-to-paste `DB_*` URLs.

### Why `--skip-match-xml`

| Scenario | Raw data |
|---|---|
Everything | **478.8 MB** |
`--skip-match-xml` | **222.3 MB** |
`--skip-match-xml --skip-table olist.geolocation` | **154.7 MB** |

`Match`'s eight XML event columns (`goal`, `shoton`, `shotoff`, `foulcommit`, `card`,
`cross`, `corner`, `possession`) are 263 MB — 86% of the Soccer data — and **no gold question
reads them**. Same for Olist's `geolocation` (67.6 MB). Plan mode prints these options and
copies nothing until you pass a flag; it never drops anything on its own.

> Note: skipping those columns means the deployed agent sees a slightly smaller Soccer schema
> than the frozen experiment did. It cannot change any gold answer, but don't re-run the
> evaluation against the cloud copy and compare it with Phase 6.

---

## Step 3 — deploy the backend

1. In the same project: **+ Create** → **GitHub Repo** → pick this repository.
2. Open the new service → **Settings**:
   - **Root Directory**: leave **empty** (`/`). ⚠️ Do not set `backend`. See the warning above.
   - **Build**: nixpacks detects Python from `requirements.txt`; no build command needed.
   - **Start Command**: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
     (already in `railway.json` / `Procfile`; set it here only if Railway ignores both).
   - **Healthcheck Path**: `/health`
3. **Variables** tab → add the table below.
4. **Settings** → **Networking** → **Generate Domain** to get the public URL.

First build takes 3–5 minutes: `scikit-learn` pulls in numpy and scipy.

---

## Step 4 — environment variables

Set these in the service's **Variables** tab. **Never in the repo.**

| Variable | Value | Notes |
|---|---|---|
| `GEMINI_API_KEY` | *your key* | **secret** — from https://aistudio.google.com/apikey |
| `LLM_PROVIDER` | `gemini` | no Ollama exists on the host |
| `LLM_FALLBACK` | `false` | there is nothing to fall back to; report outages instead of silently swapping models |
| `GEMINI_MODEL` | `gemini-3.8-flash` | pinned; avoid the floating `gemini-flash-latest` |
| `DB_MOVIELENS` | `${{Postgres.DATABASE_URL}}` + `?sslmode=require&options=-csearch_path%3Dmovielens` | **internal** URL |
| `DB_OLIST` | same base + `options=-csearch_path%3Dolist` | **internal** URL |
| `DB_SOCCER` | same base + `options=-csearch_path%3Dsoccer` | **internal** URL |
| `ALLOWED_ORIGINS` | your frontend's origin, e.g. `https://askdb.vercel.app` | comma-separated for several |
| `APP_ENV` | `production` | makes the backend **refuse to start** on a missing or `*` CORS origin |
| `USE_SAMPLES` | `true` | sample values in the schema |
| `USE_MEMORY` | `true` | retrieved worked examples: +28.9 accuracy points in the study |
| `K_EXAMPLES` | `3` | k=1 costs ~23 accuracy points |
| `MAX_RETRIES` | `3` | self-correction: raises execution rate, not accuracy |
| `MAX_ROWS` | `200` | display cap applied at fetch — never injected into the SQL |
| `SQL_TIMEOUT_S` | `30` | |

Railway variable references (`${{Postgres.DATABASE_URL}}`) work, but the `search_path` option
must be appended, so the full value looks like:

```
postgresql://postgres:PASS@postgres.railway.internal:5432/railway?sslmode=require&options=-csearch_path%3Dolist
```

`search_path` matters: `db.py`'s introspection reads the **default** schema, so pinning it makes
each `DB_*` resolve to exactly one database's tables — and the bare table names in
`keys_*.sql` resolve too.

---

## Step 5 — security before going live

**Create a read-only role and use it in the three `DB_*` URLs.** The SELECT-only guardrail in
`guardrails.py` is defence in depth, not a substitute for database permissions — if it is ever
bypassed, the role must still refuse to write.

```sql
CREATE ROLE askdb_ro LOGIN PASSWORD '<a strong password>';
GRANT CONNECT ON DATABASE railway TO askdb_ro;
GRANT USAGE ON SCHEMA movielens, olist, soccer TO askdb_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA movielens, olist, soccer TO askdb_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA movielens, olist, soccer GRANT SELECT ON TABLES TO askdb_ro;
REVOKE CREATE ON SCHEMA movielens, olist, soccer FROM askdb_ro;
```

Then swap `postgres:PASS` for `askdb_ro:<password>` in `DB_MOVIELENS` / `DB_OLIST` / `DB_SOCCER`.
Migrate with the owner role; **serve** with the read-only one.

---

## Step 6 — verify the deployment

```bash
curl https://<your-service>.up.railway.app/health
```

Expect:

```json
{
  "status": "ok",
  "provider": "gemini",
  "databases": ["movielens", "olist", "soccer"],
  "memory": true,
  "env": "production",
  "allowedOrigins": ["https://your-frontend..."]
}
```

Then a real question:

```bash
curl -X POST https://<your-service>.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"db":"olist","question":"What are the top 10 product categories by revenue, using the English category names?"}'
```

The first row should be `health_beauty, 1258681.34` — the verified gold answer.

Finally point the frontend at it:

```ini
# frontend/.env.local  (or the host's env settings)
VITE_API_URL=https://<your-service>.up.railway.app
VITE_USE_MOCK=false
```

---

## Troubleshooting

| Symptom | Cause |
|---|---|
`ModuleNotFoundError: No module named 'context'` | Root Directory is set to `backend`. Clear it. |
Startup crash: `ALLOWED_ORIGINS is '*'` | `APP_ENV=production` refuses the wildcard. Set your real origin. |
`/databases` returns `[]` | none of `DB_MOVIELENS` / `DB_OLIST` / `DB_SOCCER` is set, or all failed to connect. |
Tables not found, but the DB connects | the `options=-csearch_path%3D<schema>` fragment is missing from the URL. |
Browser fetch fails, backend logs nothing | CORS: the frontend origin isn't in `ALLOWED_ORIGINS`. |
Migration hangs or times out | you used `DATABASE_URL` (internal) instead of `DATABASE_PUBLIC_URL`. |
503 from `/ask`, `provider unavailable` | `GEMINI_API_KEY` missing/invalid, or the free tier's 20 requests/day/model is exhausted. |
