# Datasets

The three datasets are **not tracked in this repo** — together they are ~450 MB, and all
three are publicly available. Download them here, then follow the loading steps in the
[main README](../README.md#2-databases).

Expected layout:

```
data/
├── movielens/            *.csv          (links, movies, ratings, tags)
├── olist/                *.csv          (9 files, olist_*_dataset.csv)
└── soccer/database.sqlite
```

## 1. MovieLens (ml-latest-small)

- **Source:** https://grouplens.org/datasets/movielens/
- **File:** `ml-latest-small.zip` (~1 MB)
- **Extract to:** `data/movielens/` — keep `movies.csv`, `ratings.csv`, `tags.csv`, `links.csv`
- ~9,742 movies, ~100,836 ratings, 4 tables

Loaded into PostgreSQL. Note `genres` is a pipe-delimited string (`'Action|Comedy'`) and the
release year is embedded in `title` (`'Toy Story (1995)'`) — both are deliberate difficulties
in the benchmark.

## 2. Olist Brazilian E-Commerce

- **Source:** https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
- **Size:** ~120 MB across 9 CSVs
- **Extract to:** `data/olist/` — keep the original `olist_*_dataset.csv` names plus
  `product_category_name_translation.csv` (the loader strips the prefix/suffix)
- ~99,441 orders, ~1.55M rows total, 9 tables

Real, slightly messy data: a misspelled column (`product_name_lenght`), Portuguese category
names needing a translation join, 32-character hash IDs, and 2 orphan categories that break a
foreign key (repaired by `fix_olist_orphans.sql`).

## 3. European Soccer Database

- **Source:** https://www.kaggle.com/datasets/hugomathien/soccer
- **File:** `database.sqlite` (~310 MB)
- **Place at:** `data/soccer/database.sqlite`
- 25,979 matches, 11,060 players, 7 tables

**Kept as SQLite on purpose** — no conversion to PostgreSQL. It is what proves the agent is
engine-agnostic: the same code path, a different connection URL. It also contains the
hardest schema in the set (`Match` has 115 columns).

## Verifying a load

```bash
docker exec analytics-pg psql -U postgres -d movielens -c "SELECT COUNT(*) FROM movies;"   -- 9742
docker exec analytics-pg psql -U postgres -d olist     -c "SELECT COUNT(*) FROM orders;"   -- 99441
python -c "import sqlite3;print(sqlite3.connect('data/soccer/database.sqlite').execute('SELECT COUNT(*) FROM \"Match\"').fetchone())"  # 25979
```

If these three counts match, the gold answers in `gold_answers.json` are reproducible.
