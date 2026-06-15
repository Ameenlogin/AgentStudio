"""Dependency-free local text embeddings.

Used by the semantic response cache and the conversation search index. We
deliberately do NOT call any remote embedding API here — that would consume the
NVIDIA NIM rate budget we are trying to protect. Instead we build a sparse
lexical vector from word tokens + character trigrams and compare with cosine
similarity. This is cheap, instant, and good enough to recognise "the same
question asked slightly differently" or "find similar past chats".
"""
from __future__ import annotations

import math
import re
from collections import Counter

_WORD_RE = re.compile(r"[a-z0-9]+")


def _normalize(text: str) -> str:
    return (text or "").lower().strip()


def embed(text: str) -> Counter:
    """Return a sparse term-frequency vector (Counter) for `text`.

    Features = word unigrams + word bigrams + character trigrams. The mix makes
    the similarity robust to small edits, word reordering and typos.
    """
    norm = _normalize(text)
    words = _WORD_RE.findall(norm)
    vec: Counter = Counter()

    # word unigrams + bigrams
    for w in words:
        vec[f"w:{w}"] += 1
    for a, b in zip(words, words[1:]):
        vec[f"b:{a}_{b}"] += 1

    # character trigrams over the collapsed text (typo tolerance)
    collapsed = " ".join(words)
    for i in range(len(collapsed) - 2):
        tri = collapsed[i : i + 3]
        if tri.strip():
            vec[f"c:{tri}"] += 1
    return vec


def cosine(a: Counter, b: Counter) -> float:
    """Cosine similarity between two sparse vectors in [0, 1]."""
    if not a or not b:
        return 0.0
    # iterate over the smaller vector for speed
    small, large = (a, b) if len(a) <= len(b) else (b, a)
    dot = sum(v * large.get(k, 0) for k, v in small.items())
    if dot == 0:
        return 0.0
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def similarity(text_a: str, text_b: str) -> float:
    return cosine(embed(text_a), embed(text_b))
