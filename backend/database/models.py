import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship
from database.database import Base


# Non-secret defaults always ship. The API key column defaults to empty so a
# fresh install boots keyless and prompts the user in-app; main.py overlays an
# optional local config/keys.py if present.
from config.defaults import BASE_URL as _BASE_URL, DEFAULT_MODEL as _MODEL


class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    api_key = Column(String, nullable=True, default="")
    api_key_2 = Column(String, nullable=True, default="")
    api_key_3 = Column(String, nullable=True, default="")
    base_url = Column(String, default=_BASE_URL)
    model_name = Column(String, default=_MODEL)
    temperature = Column(Float, default=0.6)
    system_prompt = Column(Text, default=None)  # None → agent uses its built-in prompt
    max_steps = Column(Integer, default=50)
    tools_enabled = Column(Boolean, default=True)
    workspace_path = Column(String, default="./workspace")
    permission_mode = Column(String, default="ask")   # "ask" | "auto"
    swarm_mode = Column(String, default="auto")        # "auto" | "off"
    mode = Column(String, default="sandbox")           # "sandbox" | "desktop" | "workspace"
    desktop_granted = Column(Boolean, default=True)


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, default="New chat")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    messages = relationship(
        "Message", back_populates="conversation",
        cascade="all, delete-orphan", order_by="Message.id",
    )


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    role = Column(String)            # user | assistant
    content = Column(Text)           # rendered text content
    blocks = Column(Text, nullable=True)  # JSON: timeline blocks (thinking/tools)
    content_hash = Column(String, nullable=True)  # SHA-256 integrity hash
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    conversation = relationship("Conversation", back_populates="messages")


def message_hash(role: str, content: str) -> str:
    """SHA-256 over the message role + content for tamper/corruption detection."""
    import hashlib
    h = hashlib.sha256()
    h.update((role or "").encode("utf-8"))
    h.update(b"\x00")
    h.update((content or "").encode("utf-8"))
    return h.hexdigest()
