"""
memory.py — Phase 4b: retrieval-augmented example memory (RAG).

A JSON store of verified (question -> SQL) pairs. For a new question we
retrieve the k most SIMILAR past questions and show them as worked examples.

LEAKAGE GUARDS (the whole validity of the evaluation rests on these):
  1. exclude_ids       -- leave-one-out by ID. The honest guard: use it in eval.
  2. exclude_question  -- exact-text match; DEFAULTS to the query itself.
  3. dup_threshold     -- drops near-identical questions (paraphrase safety net).
Text guards cannot catch every paraphrase, so evaluation must pass exclude_ids.
"""

import json
import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

STORE_PATH = Path("memory_store.json")
DUP_THRESHOLD = 0.92


def _norm(text: str) -> str:
    """Lowercase, drop punctuation, collapse spaces -- for exact-match comparison."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


# --- the swappable similarity seam -----------------------------------------
# TF-IDF scores by SHARED WORDS: fast, no model, but blind to meaning
# ("count the purchases" vs "how many orders" ~ 0). To swap in embeddings
# (Ollama nomic-embed-text), replace this one function with a call that embeds
# `query` + `docs` and returns cosine similarities. Nothing else changes.
def score_tfidf(query: str, docs: list[str]) -> list[float]:
    if not docs:
        return []
    vec = TfidfVectorizer().fit(docs + [query])
    sims = cosine_similarity(vec.transform([query]), vec.transform(docs))[0]
    return [float(s) for s in sims]


class Memory:
    def __init__(self, path: Path | str = STORE_PATH, score_fn=score_tfidf):
        self.path = Path(path)
        self.score_fn = score_fn
        self.entries: list[dict] = []
        if self.path.exists():
            self.entries = json.loads(self.path.read_text(encoding="utf-8"))

    def save(self):
        self.path.write_text(json.dumps(self.entries, indent=2), encoding="utf-8")

    def add(self, db: str, question: str, sql: str, id: str | None = None,
            technique: str | None = None, save=True):
        if id is not None:
            self.entries = [e for e in self.entries if e.get("id") != id]
        self.entries.append({"id": id, "db": db, "question": question,
                             "sql": sql, "technique": technique})
        if save:
            self.save()

    def retrieve(self, db: str, question: str, k: int = 3,
                 exclude_question: str | None = None,
                 exclude_ids: tuple | list = (),
                 dup_threshold: float = DUP_THRESHOLD) -> list[dict]:
        """k most similar stored examples for the SAME db, with leakage guards."""
        drop_text = _norm(exclude_question if exclude_question is not None else question)

        pool = [e for e in self.entries
                if e["db"] == db
                and e.get("id") not in exclude_ids
                and _norm(e["question"]) != drop_text]

        if not pool:
            return []

        sims = self.score_fn(question, [e["question"] for e in pool])
        scored = [(s, e) for s, e in zip(sims, pool) if s < dup_threshold and s > 0]
        scored.sort(key=lambda t: t[0], reverse=True)
        return [dict(e, score=round(s, 3)) for s, e in scored[:k]]


def as_messages(examples: list[dict]) -> list[dict]:
    """Retrieved examples as worked-example chat turns, placed before the question."""
    msgs = []
    for ex in examples:
        msgs.append({"role": "user", "content": ex["question"]})
        msgs.append({"role": "assistant", "content": ex["sql"]})
    return msgs
