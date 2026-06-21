"""Site auth: password hashing + HMAC-signed session cookies (stdlib only).

No third-party crypto deps (keeps the slim Docker image reliable). Passwords use
PBKDF2-HMAC-SHA256; sessions are signed tokens "uid.ts.sig" in an HttpOnly cookie.
"""
import os
import hmac
import time
import base64
import hashlib
import secrets

from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session

from database.database import get_db
from database.site_models import SiteUser

COOKIE = "oa_session"
_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def _secret() -> bytes:
    """Stable secret for signing — env override, else persisted next to the DB."""
    env = os.environ.get("AGENT_STUDIO_SECRET")
    if env:
        return env.encode()
    db_path = os.environ.get("AGENT_STUDIO_DB") or "/data/agent_studio.db"
    path = os.path.join(os.path.dirname(db_path) or ".", ".session_secret")
    try:
        if os.path.isfile(path):
            return open(path, "rb").read()
        val = secrets.token_bytes(32)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "wb") as f:
            f.write(val)
        return val
    except Exception:
        return b"onaiagents-dev-secret-change-me"


# ── Passwords ─────────────────────────────────────────────────────────────────
def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000)
    return f"{salt}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$", 1)
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000)
        return hmac.compare_digest(dk.hex(), h)
    except Exception:
        return False


# ── Session tokens ────────────────────────────────────────────────────────────
def make_token(uid: int) -> str:
    payload = f"{uid}.{int(time.time())}"
    sig = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    raw = f"{payload}.{sig}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def parse_token(token: str):
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        uid, ts, sig = raw.rsplit(".", 2)
        expect = hmac.new(_secret(), f"{uid}.{ts}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect, sig):
            return None
        if int(time.time()) - int(ts) > _MAX_AGE:
            return None
        return int(uid)
    except Exception:
        return None


# ── Dependencies ──────────────────────────────────────────────────────────────
def current_user(request: Request, db: Session = Depends(get_db)):
    tok = request.cookies.get(COOKIE)
    if not tok:
        return None
    uid = parse_token(tok)
    if not uid:
        return None
    return db.query(SiteUser).get(uid)


def require_user(user=Depends(current_user)) -> SiteUser:
    if not user:
        raise HTTPException(status_code=401, detail="Please sign in.")
    return user


def require_admin(user=Depends(current_user)) -> SiteUser:
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only.")
    return user
