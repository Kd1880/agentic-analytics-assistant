# Agentic Analytics Assistant

**Ask a database a question in plain English. The agent writes the SQL, runs it, and corrects itself when the SQL fails.**

It is also a controlled experiment. The same agent was run in four configurations over 45
hand-verified questions across three real databases, three times each, to answer one
question: **which agent mechanisms actually make the answers *right*, and which only make
them *run*?**

> **See `report.pdf` for the full write-up.** (Drop it in `docs/`.)

---

## The research question, and the answer

> Do self-correction and retrieved memory improve a text-to-SQL agent, and *why*?

The starting hypothesis came from the literature: Huang et al. (2024) show that LLMs cannot
reliably self-correct *intrinsically*, while CRITIC / Self-Debug / Reflexion show that
**external** feedback helps. A SQL executor is a perfect external critic — it tells you
precisely why a query is invalid.

**What the experiment found:**

| Mechanism | Effect on **execution rate** | Effect on **accuracy** |
|---|---|---|
| **Self-correction** (feed the DB error back, retry) | **+8.9 points** | **+2.2 points** — one question |
| **Context + memory** (sample values + retrieved worked examples) | +5.2 points | **+28.9 points** — 13 questions |

**The two mechanisms act on different axes.** Self-correction makes queries *run*; retrieval
makes them *correct*. They are not interchangeable and they do not stack — adding retries on
top of good context changed accuracy by **−1.5 [−4.4, 0.0] points**, i.e. nothing.

The reason is structural. A database can only report **invalidity**, never **wrongness**. So
execution feedback fixes broken SQL and is blind to SQL that runs and answers the wrong
question. In this study self-correction converted loud failures into *silent* ones: errors
fell 5 → 1 while silent wrong answers rose 23 → **26**.

**The headline number for the thesis is the gap between them:** Config B executes 97.8% of
queries and answers 40.0% correctly — a **57.8-point** gap. Any evaluation reporting only
"did the SQL run" would overstate this system by more than half.

A cross-model probe on Gemini (a much stronger model) showed both effects shrink but the
central one survives: context still added **+11.1** points, and the execution-vs-accuracy gap
was still ~18 points. **Memory's value is inversely related to how much the base model
already knows — but the gap never closes.**

---

## What it does

```
"Which product categories earn the most revenue?"
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│ 1. INTROSPECT   read the live schema: tables, columns, types, │
│                 primary keys, foreign keys          (db.py)   │
│ 2. ENRICH       add 2-3 real sample values per column         │
│                 ('Action|Comedy' reveals its format) (context)│
│ 3. RETRIEVE     find the k=3 most similar solved questions     │
│                 and show their SQL as worked examples (memory)│
│ 4. GENERATE     LLM writes ONE SQL query, temperature 0 (agent)│
│ 5. GUARD        SELECT-only, no stacked statements, statement  │
│                 timeout, fetch cap              (guardrails)   │
│ 6. EXECUTE      run it                                (db.py) │
│ 7. SELF-CORRECT on a SQL error, feed the error back and retry  │
│                 (max 3); infra errors fail fast  (self_correct)│
└───────────────────────────────────────────────────────────────┘
        ▼
  table + insight + chart hint
```

**Schema-agnostic by design.** No table name appears anywhere in the code. The agent
introspects whatever database it is pointed at, so switching databases — or switching from
PostgreSQL to SQLite — is a **connection-string change**, nothing more. It is tested on both
engines simultaneously.

**Agentic + RAG, and the distinction is deliberate.** Self-correction is *agentic*: a tool
executes the model's output and the result becomes new input. Memory is *RAG*: a store is
searched by relevance and the matches condition generation. They solve different failure
classes, which is exactly what the results show.

---

## The experiment

### Four configurations, one code path

| Config | Sample values | Retrieved examples | Retries |
|---|---|---|---|
| **A** baseline | off | off | 0 |
| **B** +self-correction | off | off | 3 |
| **C** +context/memory | **on** | **on** | 0 |
| **D** both | **on** | **on** | 3 |

All four are the same function with different flags, so no config can differ by accident.
Config A is frozen and SHA-256 hashed as the experimental control.

### Three databases, 45 questions

| Database | Engine | Tables | Rows | Why |
|---|---|---|---|---|
| MovieLens | PostgreSQL (Docker) | 4 | ~124k | simple star-ish schema |
| Olist e-commerce | PostgreSQL (Docker) | 9 | ~1.55M | messy real data, 9-table joins |
| European Soccer | **SQLite file** | 7 | ~222k | second engine; one 115-column table |

45 questions (15 per database), labelled easy / medium / hard, each with **hand-verified
reference SQL** whose result is frozen as the gold answer.

### How grading works

**Results are compared, never SQL text.** Many different queries are correct; comparing SQL
would measure "did the model write it my way". The grader:

- compares **values and order**, but row order only for order-sensitive questions (top-N, trends);
- uses a **relative float tolerance** (1e-6), because Postgres parallel aggregation is not bit-reproducible;
- normalises **representation only** — numeric types, label case/whitespace, column order — never identity;
- classifies every outcome as **correct** / **silent** (ran, wrong) / **loud** (errored) / **format** (right values, wrong shape).

A match that needs a column permutation is graded `format`, never `correct`, so strict
accuracy can never be inflated by normalisation. 14 grader self-tests cover these rules.

---

## Results

Local model: `qwen2.5-coder:7b` (Q4_K_M) via Ollama, temperature 0, **3 runs × 4 configs × 45 questions = 540 records**.
Spread is shown as `mean [min–max]`; with n=3 a standard deviation would imply false precision.

### Headline: execution vs accuracy

| Config | Execution % | Strict accuracy % | **Gap (pts)** |
|---|---|---|---|
| A baseline | 88.9 [88.9–88.9] | 37.8 [37.8–37.8] | 51.1 |
| B +self-correction | **97.8 [97.8–97.8]** | 40.0 [40.0–40.0] | **57.8** |
| C +context/memory | 94.1 [93.3–95.6] | **66.7 [66.7–66.7]** | 27.4 |
| D both | 95.6 [93.3–97.8] | 65.2 [62.2–66.7] | 30.4 |

Paired deltas (computed per run, then summarised):

| Delta | Execution | Strict accuracy | Verdict |
|---|---|---|---|
| A → B | **+8.9** | +2.2 | reproducible, but **one question** |
| A → C | +5.2 | **+28.9** | **robust** — 13 questions, identical in all 3 runs |
| C → D | +1.5 | **−1.5 [−4.4, 0.0]** | **within noise** |

Run-to-run stability: of 180 (config, question) cells, **8 changed category across runs (4.4%)**.
Config A was identical in all three runs.

### By difficulty (strict accuracy / execution)

| Config | Easy (n=7) | Medium (n=20) | Hard (n=18) |
|---|---|---|---|
| A | 85.7 / 100.0 | 30.0 / 90.0 | 27.8 / 83.3 |
| B | 85.7 / 100.0 | 30.0 / 95.0 | 33.3 / **100.0** |
| C | **100.0** / 100.0 | **65.0** / 95.0 | **55.6** / 90.7 |
| D | 100.0 / 100.0 | 63.3 / 96.7 | 53.7 / 92.6 |

Hard questions are the clearest case: self-correction takes their **execution to 100%** while
accuracy stays at 33.3%; context takes **accuracy** to 55.6%.

### By database (strict accuracy)

| Config | MovieLens | Olist | Soccer |
|---|---|---|---|
| A | 46.7 | 26.7 | 40.0 |
| B | 46.7 | 37.8 | 35.6 |
| C | **73.3** | **73.3** | **53.3** |
| D | 73.3 | 73.3 | 48.9 |

Olist gains most from context (+46.6) — its schema is the least self-explanatory
(`product_name_lenght`, Portuguese category names, hash IDs). Soccer gains least (+13.3).

### Ablation: what actually drives the accuracy gain

On the **13 questions where context changed the outcome**, 3 runs each, 0 retries:

| Config | Correct / 13 | Accuracy |
|---|---|---|
| A baseline | 0.0 [0–0] | 0% |
| **S — sample values only** | **1.0 [1–1]** | **7.7%** |
| **M — retrieved examples only** | **12.0 [12–12]** | **92.3%** |
| C — both, k=3 | 13.0 [13–13] | 100% |
| **K1 — both, k=1** | **10.0 [10–10]** | **76.9%** |

**Worked examples do essentially all of the work.** Showing the model what the *data* looks
like fixed 1 of 13; showing it a *solved similar problem* fixed 12 of 13. And retrieval depth
matters: dropping from k=3 to k=1 costs **−23.1 points**, because TF-IDF rarely ranks the
same-technique example first.

Retrieval quality (Config C): a same-technique example was retrieved for **84.4%** of
questions. Accuracy was **73.7% when it was** vs **28.6% when it wasn't** — 2.6× higher.

### Retry behaviour

| Config | Attempts (3 runs pooled) | Retried → ran | Retried → **correct** |
|---|---|---|---|
| B | `{1: 121, 2: 9, 3: 2, 4: 3}` | ~3.7 | **1.0** |
| D | `{1: 129, 2: 1, 3: 1, 4: 4}` | ~0.7 | **0.0** |

In Config D the retry loop is **almost inert** — 129 of 135 cells never retry and none becomes
correct. Better context leaves nothing to fix. Self-correction is a safety net for weak
generation, not an accuracy mechanism.

### Cross-model probe: local 7B vs Gemini

Configs A and C only, single Gemini run (`gemini-3.8-flash`, temperature 0, no fallback) vs
the qwen 3-run means. The LIMIT adjustment below is applied to **both** models.

| Model | Config | Execution % | Accuracy (raw) | Accuracy (LIMIT-adjusted) |
|---|---|---|---|---|
| qwen2.5-coder:7b — 3-run mean | A | 88.9 | 37.8 | 40.0 |
| qwen2.5-coder:7b — 3-run mean | C | 94.1 | 66.7 | 68.9 |
| **gemini-3.8-flash — single probe** | A | **100.0** | **77.8** | **82.2** |
| **gemini-3.8-flash — single probe** | C | **100.0** | **88.9** | **93.3** |

- **Gemini with no context beats the local model with context** (82.2% vs 68.9%).
- **Gemini produced zero loud failures** across 90 questions — the entire failure class that
  motivated self-correction disappears with a stronger model.
- **Context still helps: +11.1 points.** Smaller than +28.9, but real.
- **The gap survives:** 100% execution vs 82.2% accuracy is still ~18 points of overstatement.

*The LIMIT adjustment:* the baseline prompt says "always add a LIMIT", which truncates
otherwise-correct answers. A trailing `LIMIT k` is stripped and re-graded only when the
question has no top-N intent **and** gold row count > k (so the limit provably truncated the
result). 4 Gemini answers and 6 qwen records flipped to correct.

---

## Key findings

1. **Execution rate is not accuracy.** The two diverge by up to 57.8 points. Report both, or
   overstate your system by half.
2. **External execution feedback fixes validity, not meaning.** A database reports invalid
   SQL, never wrong SQL — so self-correction reliably turns errors into runnable queries
   (+8.9 execution) and reliably fails to make them right (+2.2 accuracy). It converts loud
   failures into silent ones.
3. **Retrieved worked examples are what move accuracy** (+28.9 points; 92% of the gain from
   retrieval alone in the ablation). **Showing a solution beats showing the data**: sample
   values alone fixed 1 of 13 questions.
4. **The mechanisms don't stack.** With good context the retry loop fires almost never.
   Order matters in deployment: fix context first, keep retries as a cheap safety net.
5. **Memory's value is inversely related to base-model strength** — +28.9 on a 7B, +11.1 on
   Gemini — but it does not vanish, and the execution-vs-accuracy gap never closes.
6. **Evaluation infrastructure needs the same error taxonomy as the agent.** Three separate
   incidents would each have produced confidently wrong published numbers:
   - a harness that logged **LLM outages as model failures** (20 fake `loud` records);
   - an Ollama server that **silently truncated** oversized prompts to 2,050 tokens, invalidating
     12 Soccer records (caught by a `prompt_tokens` ceiling, not by the results looking odd);
   - Gemini's free tier capping at **20 requests/day/model**, producing 23 more fake failures.

   All three were caught by integrity checks, not by intuition. Distinguishing
   *infrastructure failure* from *model failure* is a first-class requirement.
7. **A stronger model follows a flawed instruction more faithfully.** Gemini solved the
   hardest reasoning question (extracting a year from inside a title string) with no context
   at all — then scored wrong because it obeyed the prompt's LIMIT rule and returned 100 of
   106 rows. The defect was in the prompt layer, and its cost rose with model quality.

---

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.13 |
| DB access | SQLAlchemy 2.0 (engine-agnostic introspection + execution) |
| Databases | PostgreSQL 16 (Docker), SQLite 3.45 |
| Local LLM | Ollama + `qwen2.5-coder:7b` (OpenAI-compatible endpoint) |
| Hosted LLM | Google Gemini `gemini-3.8-flash` (OpenAI-compatible endpoint) |
| Retrieval | scikit-learn TF-IDF cosine (embedding swap behind a one-function seam) |
| API | FastAPI + Uvicorn |
| Loading | pandas → `to_sql` |

Both LLM providers speak the OpenAI-compatible API, so the provider is a **config value**,
not a code path — the same principle that makes the databases swappable.

---

## Repo structure

```
agent.py                 FROZEN baseline: prompt, LLM call, clean_sql  (Config A control)
db.py                    FROZEN: connection URLs, schema introspection, run_sql
context.py               Phase 4a: sample values appended to the schema
memory.py                Phase 4b: TF-IDF retrieval store + leakage guards
self_correct.py          Phase 3 retry loop + Phase 4/5 wiring; all four configs
guardrails.py            Phase 5: SELECT-only, dialect-specific timeout, error classification
llm_provider.py          Phase 7: Ollama / Gemini provider seam
backend/app.py           FastAPI deployment API (/ask, /databases, /health, /config)

seed_memory.py           builds + verifies the 78-pair disjoint training pool
gold_eval.py             the 45 gold questions + verified reference SQL → gold_answers.json
grade.py                 the grader (5 rules, 14 self-tests)
run_eval.py              4 configs × 45 questions, resumable, run_id-aware
run_soccer_until_done.py supervisor: restarts Ollama, resumes the harness, never fabricates
run_gemini_probe.py      cross-model probe + LIMIT-adjusted re-grading
aggregate_eval.py        3-run aggregation with mean [min–max]
report_eval.py           single-run tables

load_csv_to_postgres.py  generic CSV → Postgres loader (no table names hardcoded)
keys_movielens.sql       primary/foreign keys + indexes
keys_olist.sql           keys, indexes, timestamp casts
fix_olist_orphans.sql    repairs 2 orphan categories blocking a foreign key

gold_questions.md        the 45 benchmark questions
gold_answers.json        frozen gold results + metadata
memory_store.json        the 78-pair training pool (disjoint from the gold set)
phase6_raw.json          every (run, config, question) outcome — 657 records
phase6_gemini_raw.json   the Gemini probe — 90 records
docs/                    full report (report.pdf)
data/                    datasets — NOT tracked, see data/README.md
```

---

## How to run

### 1. Prerequisites

```bash
pip install sqlalchemy psycopg2-binary pandas scikit-learn openai python-dotenv fastapi uvicorn
ollama pull qwen2.5-coder:7b        # local model
```

### 2. Databases

Download the three datasets — see [`data/README.md`](data/README.md) — then:

```bash
docker run -d --name analytics-pg -e POSTGRES_PASSWORD=pass -p 5432:5432 \
  -v analytics-pgdata:/var/lib/postgresql/data postgres:16
docker exec analytics-pg psql -U postgres -c "CREATE DATABASE movielens;" -c "CREATE DATABASE olist;"

python load_csv_to_postgres.py --csv-dir data/movielens --db movielens
python load_csv_to_postgres.py --csv-dir data/olist --db olist --strip-prefix olist_ --strip-suffix _dataset

docker exec -i analytics-pg psql -U postgres -d movielens < keys_movielens.sql
docker exec -i analytics-pg psql -U postgres -d olist     < keys_olist.sql        # 1 FK error expected
docker exec -i analytics-pg psql -U postgres -d olist     < fix_olist_orphans.sql
```

European Soccer needs no loading — it is read directly as a SQLite file.

### 3. Ask a question

```bash
python agent.py olist "What are the top 10 product categories by revenue?"          # Config A
python self_correct.py olist --samples --memory "How many movies are there per genre?"   # Config C/D
```

### 4. Run the API

```bash
cp .env.example .env         # then add GEMINI_API_KEY if using Gemini
uvicorn backend.app:app --reload --port 8000     # http://localhost:8000/docs
```

See [`README_backend.md`](README_backend.md) for the deployment guide and the `/ask` contract.

### 5. Reproduce the experiment

```bash
python gold_eval.py                     # freeze the 45 gold answers
python grade.py                         # grader self-tests (14)
python seed_memory.py                   # build + verify the 78-pair training pool
python run_soccer_until_done.py --run 1 # resumable, supervised pass (repeat --run 2, --run 3)
python run_eval.py --run N --configs S,M,K1 --ids "$(cat ablation_ids.txt)"   # ablations
python aggregate_eval.py                # all result tables

LLM_FALLBACK=false python run_gemini_probe.py    # cross-model probe
python run_gemini_probe.py --limit-adjust
```

**Pinned serving configuration** (any change invalidates cross-run comparison):

```
Ollama 0.34.3   OLLAMA_CONTEXT_LENGTH=8192   OLLAMA_NUM_PARALLEL=1
                OLLAMA_KEEP_ALIVE=-1         OLLAMA_MAX_LOADED_MODELS=1
```

Ollama's auto-updater lives in the tray app (`ollama app.exe`); it must stay closed during a
run, or the server version can change mid-study — which happened twice here.

---

## Integrity anchors

The experimental control is byte-frozen and verifiable:

```
3973d29529a4267fa6b6775d6e669a60a53703a0c69f963ddd3efa22aaa4dbf4  agent.py
39e1128f6d1e6320cf520ca4ecce4b2586f74b4206934f70ca9bc6bcff36179e  db.py
```

`sha256sum agent.py db.py` — unchanged from Phase 2 through Phase 7. Later phases **wrap**
these files, never edit them, so every result stays comparable to the baseline.

| Anchor | Value |
|---|---|
| Model digest | `dae161e27b0e` (`qwen2.5-coder:7b`, unchanged for the whole study) |
| Temperature | 0 everywhere |
| Training pool | 78 pairs, **disjoint** from the 45 gold questions — 0 leaks across 540 records |
| Gold answers | 45, each verified by execution before freezing |
| Eval integrity | full fetch (`max_rows=None`); every record stores `prompt_tokens`; a connection failure records **nothing** |

**A note on `db.py`'s password.** `db.py` contains `postgres:pass` for the local Docker
container. It is a throwaway credential for a disposable local database, never a real one.
Because `db.py` is the hashed experimental control, **it cannot be edited without
invalidating every recorded result**, so the literal stays. Deployment does not use it:
`backend/app.py` reads database URLs from environment variables.

---

## Limitations

- 45 questions, 3 runs, one 7B local model; outcome-level run-to-run variation is 4.4%.
- One retriever (TF-IDF). Embedding retrieval is a clean follow-up, behind an existing seam.
- The Gemini comparison is a **single-run probe**, not a second full study; configs B and D
  were not probed on Gemini.
- 4 gold questions were concretised from ambiguous originals ("for a given team" → Arsenal).
- Difficulty labels are the benchmark's own, not independently validated.
- 15 of 45 questions were never answered correctly by any local-model configuration — the
  residual error class is multi-table semantic reasoning.
