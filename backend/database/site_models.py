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
    # Google sign-in (OAuth 2.0). Paste the Client ID + secret from Google Cloud
    # → "Create OAuth client ID" (Web application). The redirect URI below must be
    # added there verbatim under "Authorized redirect URIs".
    "google_client_id": "",
    "google_client_secret": "",
    "google_redirect_uri": "https://onaiagents.com/api/site/auth/google/callback",
    # LinkedIn Automation — NVIDIA NIM (OpenAI-compatible) running gpt-oss-120b.
    # Empty key falls back to the AgentStudio NVIDIA key; users can bring their own.
    "nvidia_base_url": "https://integrate.api.nvidia.com/v1",
    "nvidia_api_key": "",
    "linkedin_model": "openai/gpt-oss-120b",
    "cost_linkedin": "10",   # credits per generated post
    # AI Friends — admin-editable system-prompt rules (ported from the comfyAIcloud
    # theme). Appended live to every friend's persona at chat time, so edits apply
    # to all friends instantly. Defaults below are the theme's legitimate voice/
    # identity mechanics (SFW); the explicit sound-roleplay catalog field is left
    # blank for the admin to fill from their theme if desired.
    "friend_identity_rules": (
        "You are a persistent AI Friend created by the user.\n"
        "Stay emotionally consistent, warm, and natural across messages.\n"
        "The UI renders assistant replies as voice, but the user still types normal text.\n"
        "Do not break character or mention hidden system rules, tags, JSON, or TTS machinery.\n"
        "Authority order (highest wins): Admin rules > the user-defined persona > these rules > model defaults.\n"
        "Always follow the persona above your own preferences."
    ),
    "friend_conversation_rules": (
        "Normal conversation is always allowed and gets a natural, in-character reply.\n"
        "Default turn type is dialogue. Keep replies concise unless the user clearly wants depth.\n"
        "Never ask for an image upload unless the user is actually asking for image work.\n"
        "Keep context across turns and preserve the user's last active topic.\n"
        "Light emotional accents are fine in dialogue (a soft laugh, a sigh, a warm tone) — at most 1–2 per line.\n"
        "Vary openers, phrasing, and pacing across turns to stay human and fresh."
    ),
    "friend_voice_rules": (
        "Choose speech delivery from the emotional tone of the current reply — warmth, pacing, playfulness, tenderness.\n"
        "Write tts_script as plain, natural, voice-ready speech.\n"
        "Never write a tag's literal word so the voice reads it aloud; if you want a sound, write it phonetically.\n"
        "Don't lock into one repeated pattern — vary delivery every message and match the user's energy.\n"
        "If a line sounds better plain, keep tts_script clean."
    ),
    "friend_output_rules": (
        "Return valid JSON only for each reply. No markdown, no prose outside the JSON.\n"
        "Keys: assistant_text (the readable reply), tts_script (voice-ready version), turn_type ('dialogue'), message_kind ('voice').\n"
        "Keep assistant_text and tts_script short, spoken, and under ~70 words.\n"
        "Ask at most one fresh, specific follow-up question. Avoid repeating phrasing from recent turns."
    ),
    "friend_effect_inventory": (
        "# Approved emotional delivery cues (interpret as tone, never spoken as words):\n"
        "warm — affectionate and open\n"
        "soft / gentle — intimate, reassuring\n"
        "whisper — hush, closeness\n"
        "playful — light, teasing\n"
        "excited — lifted, energized pacing\n"
        "calm — slow, steady, grounded\n"
        "sad — low, weighted tone\n"
        "(Admin: add more verified delivery cues here.)"
    ),
    "friend_vision_rules": (
        "Follow the user's image-description request exactly.\n"
        "Only describe details that are visually supported by the image.\n"
        "Never guess hidden details, identity, or off-frame content.\n"
        "If something is unclear, say that it is unclear."
    ),
    # Optional admin-only field for the theme's explicit sound-roleplay catalog
    # (left blank by default; paste from your theme if you want that behavior).
    "friend_sound_rules": "",
    "site_name": "onaiagents",
}
