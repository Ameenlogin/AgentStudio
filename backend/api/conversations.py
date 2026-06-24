import os

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database.database import get_db
from database.models import Conversation, Message, message_hash
from services import site_auth as auth

router = APIRouter()

# Hosted: conversations are private per account. Desktop: single-user, open.
HOSTED = bool(os.environ.get("AGENT_STUDIO_HOSTED"))


def _guard(user):
    if HOSTED and not user:
        raise HTTPException(401, "Please sign in.")


def _mine(query, user):
    """Restrict a Conversation query to the caller's own rows when hosted."""
    if HOSTED and user:
        return query.filter(Conversation.user_id == user.id)
    return query


@router.get("/")
def list_conversations(db: Session = Depends(get_db), user=Depends(auth.current_user)):
    _guard(user)
    rows = _mine(db.query(Conversation), user).order_by(Conversation.updated_at.desc()).all()
    return [{"id": c.id, "title": c.title,
             "updated_at": c.updated_at.isoformat() if c.updated_at else None} for c in rows]


@router.get("/{cid}")
def get_conversation(cid: int, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    _guard(user)
    c = _mine(db.query(Conversation).filter(Conversation.id == cid), user).first()
    if not c:
        raise HTTPException(404, "Conversation not found")
    msgs = []
    for m in c.messages:
        # Verify SHA-256 integrity: flag any message whose stored hash no longer
        # matches its content (tampering / storage corruption).
        intact = (m.content_hash is None) or (m.content_hash == message_hash(m.role, m.content))
        msgs.append({"role": m.role, "content": m.content, "blocks": m.blocks,
                     "intact": intact})
    return {"id": c.id, "title": c.title, "messages": msgs}


@router.get("/{cid}/verify")
def verify_conversation(cid: int, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    """Re-hash every message and report any integrity mismatches."""
    _guard(user)
    c = _mine(db.query(Conversation).filter(Conversation.id == cid), user).first()
    if not c:
        raise HTTPException(404, "Conversation not found")
    tampered = []
    for i, m in enumerate(c.messages):
        if m.content_hash and m.content_hash != message_hash(m.role, m.content):
            tampered.append(i)
    return {"id": c.id, "messages": len(c.messages),
            "tampered": tampered, "ok": not tampered}


@router.post("/")
async def save_conversation(request: Request, db: Session = Depends(get_db),
                            user=Depends(auth.current_user)):
    _guard(user)
    data = await request.json()
    cid = data.get("id")
    title = (data.get("title") or "New chat")[:80]
    messages = data.get("messages", [])
    owner = user.id if user else None

    c = None
    if cid:
        c = _mine(db.query(Conversation).filter(Conversation.id == cid), user).first()
    if not c:
        c = Conversation(title=title, user_id=owner)
        db.add(c)
    db.commit()
    db.refresh(c)

    c.title = title
    db.query(Message).filter(Message.conversation_id == c.id).delete()
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        db.add(Message(conversation_id=c.id, role=role, content=content,
                       blocks=m.get("blocks"),
                       content_hash=message_hash(role, content)))
    db.commit()
    return {"id": c.id, "title": c.title}


@router.delete("/{cid}")
def delete_conversation(cid: int, db: Session = Depends(get_db), user=Depends(auth.current_user)):
    _guard(user)
    c = _mine(db.query(Conversation).filter(Conversation.id == cid), user).first()
    if c:
        db.delete(c)
        db.commit()
    return {"status": "deleted"}
