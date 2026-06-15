from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database.database import get_db
from database.models import Conversation, Message, message_hash

router = APIRouter()


@router.get("/")
def list_conversations(db: Session = Depends(get_db)):
    rows = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    return [{"id": c.id, "title": c.title,
             "updated_at": c.updated_at.isoformat() if c.updated_at else None} for c in rows]


@router.get("/{cid}")
def get_conversation(cid: int, db: Session = Depends(get_db)):
    c = db.query(Conversation).get(cid)
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
def verify_conversation(cid: int, db: Session = Depends(get_db)):
    """Re-hash every message and report any integrity mismatches."""
    c = db.query(Conversation).get(cid)
    if not c:
        raise HTTPException(404, "Conversation not found")
    tampered = []
    for i, m in enumerate(c.messages):
        if m.content_hash and m.content_hash != message_hash(m.role, m.content):
            tampered.append(i)
    return {"id": c.id, "messages": len(c.messages),
            "tampered": tampered, "ok": not tampered}


@router.post("/")
async def save_conversation(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    cid = data.get("id")
    title = (data.get("title") or "New chat")[:80]
    messages = data.get("messages", [])

    if cid:
        c = db.query(Conversation).get(cid)
        if not c:
            c = Conversation(title=title)
            db.add(c)
    else:
        c = Conversation(title=title)
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
def delete_conversation(cid: int, db: Session = Depends(get_db)):
    c = db.query(Conversation).get(cid)
    if c:
        db.delete(c)
        db.commit()
    return {"status": "deleted"}
