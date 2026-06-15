"""Semantic response cache.

Caches answers from the fast conversational path keyed by the *meaning* of the
question (embedding similarity), not an exact string match. A near-duplicate
question is served instantly from disk — zero NVIDIA NIM calls — which both
reduces latency and protects the rate budget.

Only the stateless "simple" path is cached. Agentic turns (which touch the
workspace, run code, fetch the web, etc.) are never cached because their
correct answer depends on live side effects.
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import Counter

from services.embeddings import embed, cosine

_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "response_cache.json"
)
_LOCK = threading.Lock()
_MAX_ENTRIES = 400
_SIM_THRESHOLD = 0.93  # high bar — only serve genuinely equivalent questions


class SemanticCache:
    def __init__(self, path: str = _CACHE_PATH):
        self.path = path
        self._entries: list[dict] = []  # {q, a, model, ts, hits}
        self._vectors: list[Counter] = []
        self._load()

    # ── persistence ────────────────────────────────────────────────────────
    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._entries = json.load(f)
        except Exception:
            self._entries = []
        self._vectors = [embed(e.get("q", "")) for e in self._entries]

    def _save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._entries[-_MAX_ENTRIES:], f, ensure_ascii=False)
        except Exception:
            pass

    # ── api ────────────────────────────────────────────────────────────────
    def lookup(self, question: str, model: str = "") -> dict | None:
        """Return {answer, similarity, age} for a semantically-matching cached
        question, or None. Thread-safe."""
        if not question or not question.strip():
            return None
        qv = embed(question)
        best, best_sim = None, 0.0
        with _LOCK:
            for entry, vec in zip(self._entries, self._vectors):
                if model and entry.get("model") and entry["model"] != model:
                    continue
                sim = cosine(qv, vec)
                if sim > best_sim:
                    best, best_sim = entry, sim
            if best and best_sim >= _SIM_THRESHOLD:
                best["hits"] = best.get("hits", 0) + 1
                return {
                    "answer": best["a"],
                    "similarity": round(best_sim, 4),
                    "age": time.time() - best.get("ts", time.time()),
                }
        return None

    def store(self, question: str, answer: str, model: str = "") -> None:
        question = (question or "").strip()
        answer = (answer or "").strip()
        if not question or not answer:
            return
        # Don't cache error-ish or trivially short replies.
        if len(answer) < 8 or answer.startswith(("**Error", "Error", "I finished without")):
            return
        with _LOCK:
            # de-dupe near-identical existing question
            qv = embed(question)
            for vec in self._vectors:
                if cosine(qv, vec) >= 0.98:
                    return
            self._entries.append(
                {"q": question, "a": answer, "model": model, "ts": time.time(), "hits": 0}
            )
            self._vectors.append(qv)
            if len(self._entries) > _MAX_ENTRIES:
                self._entries = self._entries[-_MAX_ENTRIES:]
                self._vectors = self._vectors[-_MAX_ENTRIES:]
            self._save()

    def stats(self) -> dict:
        with _LOCK:
            return {
                "entries": len(self._entries),
                "total_hits": sum(e.get("hits", 0) for e in self._entries),
            }


# Singleton used by the agent loop.
cache = SemanticCache()
