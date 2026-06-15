"""Semantic search across all saved conversations ("find similar past chats")
and a peek at the semantic response-cache stats. Uses the local, dependency-free
embedding index — no remote calls, so it never touches the rate budget."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import Conversation
from services.embeddings import embed, cosine
from services.cache import cache

router = APIRouter()


@router.get("/")
def search(q: str = Query(...), limit: int = 8, db: Session = Depends(get_db)):
    qv = embed(q)
    rows = db.query(Conversation).all()
    scored = []
    for c in rows:
        # Index the title + a window of each message's content.
        text = c.title or ""
        for m in c.messages:
            text += "\n" + (m.content or "")[:600]
        sim = cosine(qv, embed(text))
        if sim > 0.04:
            snippet = ""
            for m in c.messages:
                if m.role == "user" and m.content:
                    snippet = m.content[:140]
                    break
            scored.append({
                "id": c.id, "title": c.title, "score": round(sim, 4),
                "snippet": snippet,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"query": q, "results": scored[:limit]}


@router.get("/cache")
def cache_stats():
    return cache.stats()
