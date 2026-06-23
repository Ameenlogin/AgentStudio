"""Site (onaiagents.com) backend models: accounts, credit ledger, settings.

Separate from the AgentStudio chat models. The marketing/tools site uses real
accounts + a credit balance; AgentStudio itself stays free/no-login.
"""
import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from database.database import Base


class SiteUser(Base):
    __tablename__ = "site_users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, default="")
    password_hash = Column(String, nullable=False)   # "salt$hash" (pbkdf2-sha256)
    credits = Column(Integer, default=0)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class CreditTxn(Base):
    __tablename__ = "credit_txns"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("site_users.id"), index=True)
    delta = Column(Integer)              # + grant/purchase, - spend
    reason = Column(String, default="")
    balance_after = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Order(Base):
    """A credit-purchase order (Razorpay). Created on checkout, marked paid after
    the payment signature is verified server-side."""
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    rzp_order_id = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("site_users.id"), index=True)
    credits = Column(Integer)
    amount = Column(Integer)          # in paise
    status = Column(String, default="created")  # created | paid
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


# Credit packs (INR via Razorpay). Editable here; amounts charged are derived
# server-side from this list so the client can't tamper with price↔credits.
PACKAGES = [
    {"key": "starter", "inr": 99,  "credits": 500,  "label": "Starter"},
    {"key": "creator", "inr": 399, "credits": 2500, "label": "Creator"},
    {"key": "studio",  "inr": 799, "credits": 6000, "label": "Studio"},
]


class Friend(Base):
    """A user-created AI Friend (companion). Persists per account so a visitor's
    friends survive across sessions/devices, like the comfyAIcloud theme."""
    __tablename__ = "ai_friends"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("site_users.id"), index=True)
    slug = Column(String, index=True)
    name = Column(String, default="")
    avatar_url = Column(Text, default="")          # /api/site/uploads/.. or a starter path
    tagline = Column(String, default="")
    primary_personality = Column(String, default="")
    secondary_personality = Column(String, default="")
    custom_personality = Column(Text, default="")
    voice_id = Column(String, default="ara")
    language = Column(String, default="en")
    system_prompt = Column(Text, default="")       # built server-side from the fields
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class SiteSetting(Base):
    """Key/value store for admin-tunable settings (costs, free credits, provider
    + payment keys). Strings; callers parse ints where needed."""
    __tablename__ = "site_settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(Text, default="")


# Defaults seeded on first boot. Costs mirror the original ComfyAI theme.
DEFAULT_SETTINGS = {
    "free_credits": "100",
    "cost_playground": "40",
    "cost_gen_fast": "15",
    "cost_upscale_2x": "40",
    "cost_upscale_4x": "60",
    "cost_upscale_8x": "90",
    "cost_deconstruct": "5",
    # AI provider (OpenAI-compatible — works with xAI/Grok, NVIDIA NIM, etc.).
    # One base URL + key powers image, vision (deconstruct) and chat (AI friends).
    # Empty = those tools run in preview mode until configured in admin Settings.
    "img_base_url": "",   # e.g. https://api.x.ai/v1  or  https://integrate.api.nvidia.com/v1
    "img_api_key": "",
    "img_model": "",      # image model, e.g. grok-2-image
    "vision_model": "",   # vision model for Deconstruct, e.g. grok-2-vision-latest
    "chat_model": "",     # chat model for AI Friends, e.g. grok-2-latest
    "cost_chat": "1",
    "cost_voice": "2",    # legacy single voice cost (fallback for the 15s tier)
    # Voice (TTS) per-duration billing tiers — mirror the theme's cat_cost_voice_*.
    # The selected tier sets both the spoken-reply length and the credit cost.
    "cost_voice_15s": "30",    # ~70 words
    "cost_voice_30s": "60",    # ~150 words
    "cost_voice_60s": "120",   # ~300 words  (1 min)
    "cost_voice_120s": "240",  # ~600 words  (2 min)
    "cost_voice_300s": "600",  # ~1500 words (5 min)
    # Payment gateway keys (empty = "buy credits" shows coming-soon).
    "razorpay_key_id": "",
    "razorpay_key_secret": "",
    "stripe_pk": "",
    "stripe_sk": "",
    "site_name": "onaiagents",
}
