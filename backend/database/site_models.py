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
    # Image generation provider (OpenAI-compatible /images/generations). Empty =
    # tools run in preview mode until configured here in admin Settings.
    "img_base_url": "",
    "img_api_key": "",
    "img_model": "",
    # Payment gateway keys (empty = "buy credits" shows coming-soon).
    "razorpay_key_id": "",
    "razorpay_key_secret": "",
    "stripe_pk": "",
    "stripe_sk": "",
    "site_name": "onaiagents",
}
