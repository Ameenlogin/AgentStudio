"""onaiagents.com site API: accounts, credits, admin settings, credit-gated tools."""
import re
import os
import json
import hmac
import uuid
import hashlib
import base64
import secrets
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.database import get_db
from database.site_models import SiteUser, CreditTxn, SiteSetting, Order, Friend, PACKAGES, DEFAULT_SETTINGS
from services import site_auth as auth

_UPLOAD_DIR = os.path.join(os.path.dirname(os.environ.get("AGENT_STUDIO_DB") or "/data/agent_studio.db") or ".", "uploads")

router = APIRouter()
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ── settings helpers ──────────────────────────────────────────────────────────
def _settings(db: Session) -> dict:
    out = dict(DEFAULT_SETTINGS)
    for s in db.query(SiteSetting).all():
        out[s.key] = s.value
    return out


def _set(db: Session, key: str, value: str):
    row = db.query(SiteSetting).filter(SiteSetting.key == key).first()
    if not row:
        row = SiteSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value


def _grant(db: Session, user: SiteUser, delta: int, reason: str):
    user.credits = max(0, (user.credits or 0) + delta)
    db.add(CreditTxn(user_id=user.id, delta=delta, reason=reason, balance_after=user.credits))
    db.commit()


def _public_user(u: SiteUser):
    return {"id": u.id, "email": u.email, "name": u.name, "credits": u.credits, "is_admin": u.is_admin}


# ── auth ──────────────────────────────────────────────────────────────────────
class Creds(BaseModel):
    email: str
    password: str
    name: str | None = None


@router.post("/register")
def register(body: Creds, response: Response, db: Session = Depends(get_db)):
    email = (body.email or "").strip().lower()
    if not _EMAIL.match(email):
        raise HTTPException(400, "Enter a valid email.")
    if len(body.password or "") < 6:
        raise HTTPException(400, "Password must be at least 6 characters.")
    if db.query(SiteUser).filter(SiteUser.email == email).first():
        raise HTTPException(400, "That email is already registered.")
    free = int(_settings(db).get("free_credits", "100") or 0)
    u = SiteUser(email=email, name=(body.name or "").strip() or email.split("@")[0],
                 password_hash=auth.hash_password(body.password), credits=0)
    db.add(u); db.commit(); db.refresh(u)
    if free:
        _grant(db, u, free, "Welcome credits")
    response.set_cookie(auth.COOKIE, auth.make_token(u.id), max_age=60*60*24*30,
                        httponly=True, samesite="lax", secure=True)
    return {"status": "ok", "user": _public_user(u)}


@router.post("/login")
def login(body: Creds, response: Response, db: Session = Depends(get_db)):
    email = (body.email or "").strip().lower()
    u = db.query(SiteUser).filter(SiteUser.email == email).first()
    if not u or not auth.verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Wrong email or password.")
    response.set_cookie(auth.COOKIE, auth.make_token(u.id), max_age=60*60*24*30,
                        httponly=True, samesite="lax", secure=True)
    return {"status": "ok", "user": _public_user(u)}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(auth.COOKIE)
    return {"status": "ok"}


@router.get("/me")
def me(user=Depends(auth.current_user)):
    return {"user": _public_user(user) if user else None}


@router.get("/config")
def config(user=Depends(auth.current_user), db: Session = Depends(get_db)):
    """Public, non-secret config for the frontend (nav state + tool costs)."""
    s = _settings(db)
    costs = {k: int(v or 0) for k, v in s.items() if k.startswith("cost_")}
    return {
        "logged_in": bool(user),
        "user": _public_user(user) if user else None,
        "free_credits": int(s.get("free_credits", "100") or 0),
        "costs": costs,
        "img_ready": bool(s.get("img_base_url") and s.get("img_api_key")),
        "pay_ready": bool(s.get("razorpay_key_id") and s.get("razorpay_key_secret")),
        "google_ready": bool(s.get("google_client_id") and s.get("google_client_secret")),
        "packages": PACKAGES,
        "site_name": s.get("site_name", "onaiagents"),
    }


# ── Google sign-in (OAuth 2.0 authorization-code flow) ────────────────────────
def _find_or_create_google_user(db: Session, email: str, name: str) -> SiteUser:
    email = (email or "").strip().lower()
    u = db.query(SiteUser).filter(SiteUser.email == email).first()
    if u:
        return u
    free = int(_settings(db).get("free_credits", "100") or 0)
    u = SiteUser(email=email, name=(name or email.split("@")[0]),
                 password_hash=auth.hash_password(secrets.token_urlsafe(24)), credits=0)
    db.add(u); db.commit(); db.refresh(u)
    if free:
        _grant(db, u, free, "Welcome credits")
    return u


@router.get("/auth/google/start")
def google_start(request: Request, next: str = "/", db: Session = Depends(get_db)):
    s = _settings(db)
    cid = s.get("google_client_id")
    if not cid:
        return RedirectResponse("/login?error=google_not_configured")
    state = secrets.token_urlsafe(16)
    nxt = next if (next or "").startswith("/") else "/"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": cid,
        "redirect_uri": s.get("google_redirect_uri") or "https://onaiagents.com/api/site/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    })
    resp = RedirectResponse(url)
    resp.set_cookie("oa_oauth", state + "|" + nxt, max_age=600, httponly=True, samesite="lax", secure=True)
    return resp


@router.get("/auth/google/callback")
def google_callback(request: Request, db: Session = Depends(get_db)):
    s = _settings(db)
    cid, csec = s.get("google_client_id"), s.get("google_client_secret")
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    cookie = request.cookies.get("oa_oauth") or ""
    saved_state, _, nxt = cookie.partition("|")
    if not (cid and csec):
        return RedirectResponse("/login?error=google_not_configured")
    if not code or not state or not hmac.compare_digest(state, saved_state):
        return RedirectResponse("/login?error=google_state")
    try:
        import requests
        tok = requests.post("https://oauth2.googleapis.com/token", data={
            "code": code, "client_id": cid, "client_secret": csec,
            "redirect_uri": s.get("google_redirect_uri") or "https://onaiagents.com/api/site/auth/google/callback",
            "grant_type": "authorization_code"}, timeout=30)
        tok.raise_for_status()
        access = tok.json().get("access_token")
        info = requests.get("https://www.googleapis.com/oauth2/v3/userinfo",
                            headers={"Authorization": f"Bearer {access}"}, timeout=30).json()
        email = info.get("email")
        if not email:
            return RedirectResponse("/login?error=google_email")
        user = _find_or_create_google_user(db, email, info.get("name") or "")
    except Exception:
        return RedirectResponse("/login?error=google_failed")
    dest = nxt if (nxt or "").startswith("/") else "/"
    resp = RedirectResponse(dest)
    resp.set_cookie(auth.COOKIE, auth.make_token(user.id), max_age=60*60*24*30,
                    httponly=True, samesite="lax", secure=True)
    resp.delete_cookie("oa_oauth")
    return resp


# ── credit-gated tool call ────────────────────────────────────────────────────
class GenReq(BaseModel):
    tool: str
    prompt: str | None = None
    scale: str | None = None
    model_cost: int | None = None
    image: str | None = None  # data URL, for vision (deconstruct) / source (upscale)
    face: bool | None = None  # upscale: gentler sharpening to keep faces natural


def _cost_for(tool: str, scale: str | None, s: dict) -> int:
    if tool == "upscale":
        return int(s.get(f"cost_upscale_{scale or '4x'}", s.get("cost_upscale_4x", "60")) or 0)
    if tool == "deconstruct":
        return int(s.get("cost_deconstruct", "5") or 0)
    return int(s.get("cost_playground", "40") or 0)


_PREVIEW = "Live generation isn't enabled yet. Add an AI provider in admin Settings."


@router.post("/generate")
def generate(body: GenReq, user=Depends(auth.require_user), db: Session = Depends(get_db)):
    s = _settings(db)
    cost = body.model_cost if body.model_cost else _cost_for(body.tool, body.scale, s)
    if user.is_admin:
        cost = 0   # admin = unlimited
    if (user.credits or 0) < cost:
        raise HTTPException(402, f"Not enough credits. Need {cost}, you have {user.credits}.")
    base = (s.get("img_base_url") or "").rstrip("/")
    key = s.get("img_api_key")
    H = {"Authorization": f"Bearer {key}"}

    # ── Image generation (OpenAI-compatible /images/generations) ──
    if body.tool in ("playground", "image"):
        if not (base and key):
            return {"status": "preview", "credits": user.credits, "message": _PREVIEW}
        try:
            import requests
            r = requests.post(base + "/images/generations", headers=H,
                              json={"model": s.get("img_model") or "grok-2-image",
                                    "prompt": body.prompt or "", "n": 1}, timeout=180)
            r.raise_for_status()
            d = r.json().get("data", [{}])[0]
            url = d.get("url") or (("data:image/png;base64," + d["b64_json"]) if d.get("b64_json") else None)
            if not url:
                raise ValueError("No image returned")
            _grant(db, user, -cost, "image generation")
            return {"status": "ok", "image": url, "credits": user.credits}
        except Exception as e:
            raise HTTPException(502, f"Generation failed: {e}")

    # ── Deconstruct (vision → prompt, OpenAI-compatible /chat/completions) ──
    if body.tool == "deconstruct":
        if not (base and key and body.image):
            return {"status": "preview", "credits": user.credits, "message": _PREVIEW}
        try:
            import requests
            r = requests.post(base + "/chat/completions", headers=H, json={
                "model": s.get("vision_model") or s.get("img_model") or "grok-2-vision-latest",
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": "Reverse-engineer this image into ONE detailed text-to-image prompt. Output only the prompt."},
                    {"type": "image_url", "image_url": {"url": body.image}}]}],
                "max_tokens": 500}, timeout=120)
            r.raise_for_status()
            text = (r.json()["choices"][0]["message"]["content"] or "").strip()
            _grant(db, user, -cost, "deconstruct")
            return {"status": "ok", "text": text, "credits": user.credits}
        except Exception as e:
            raise HTTPException(502, f"Deconstruct failed: {e}")

    # ── Upscale (real, local — Lanczos resample + detail enhance via Pillow) ──
    if body.tool == "upscale":
        if not body.image:
            raise HTTPException(400, "Upload an image to upscale.")
        try:
            import io
            from PIL import Image, ImageFilter, ImageEnhance
            raw = body.image.split(",", 1)[1] if body.image.startswith("data:") else body.image
            im = Image.open(io.BytesIO(base64.b64decode(raw)))
            im.load()
            has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
            im = im.convert("RGBA" if has_alpha else "RGB")
            w, h = im.size
            scale = (body.scale or "4x").lower()
            if scale in ("8x", "8k"):
                factor = min(8.0, 7680.0 / max(w, h))   # reach ~8K on the long edge, capped at 8×
            elif scale == "2x":
                factor = 2.0
            else:
                factor = 4.0
            tw, th = int(w * max(1.0, factor)), int(h * max(1.0, factor))
            # safety caps: never exceed 7680px long edge or ~40MP total
            longest = max(tw, th)
            if longest > 7680:
                k = 7680.0 / longest; tw, th = max(1, int(tw * k)), max(1, int(th * k))
            if tw * th > 40_000_000:
                k = (40_000_000 / (tw * th)) ** 0.5; tw, th = max(1, int(tw * k)), max(1, int(th * k))
            up = im.resize((tw, th), Image.LANCZOS)
            # gentle, natural detail enhancement (softer when face mode keeps skin smooth)
            face = body.face is None or body.face
            radius, percent = (1.0, 55) if face else (1.4, 95)
            up = up.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=2))
            up = ImageEnhance.Contrast(up).enhance(1.04)
            up = ImageEnhance.Color(up).enhance(1.05)
            buf = io.BytesIO()
            if has_alpha:
                up.save(buf, "PNG", optimize=True); mime = "image/png"
            else:
                up.save(buf, "JPEG", quality=92, optimize=True, progressive=True); mime = "image/jpeg"
            out = "data:%s;base64,%s" % (mime, base64.b64encode(buf.getvalue()).decode())
            _grant(db, user, -cost, f"upscale {scale}")
            return {"status": "ok", "image": out, "width": tw, "height": th,
                    "src_w": w, "src_h": h, "credits": user.credits}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"Upscale failed: {e}")

    # Other tools — preview until a provider is wired.
    return {"status": "preview", "credits": user.credits, "message": _PREVIEW}


# ── AI Friends reply parsing (the model returns the theme's JSON contract) ─────
def _parse_friend_reply(raw: str):
    """Extract (assistant_text, tts_script, message_kind) from the model output.

    The friend system prompt asks for JSON {assistant_text, tts_script, ...}.
    We parse it server-side so the chat shows a clean reply + speaks clean
    speech — never raw JSON. Falls back to the raw text if it isn't JSON."""
    text = (raw or "").strip()
    if text.startswith("```"):                      # strip ```json fences
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    data = None
    try:
        data = json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)         # first {...} block
        if m:
            try:
                data = json.loads(m.group(0))
            except Exception:
                data = None
    if isinstance(data, dict):
        at = str(data.get("assistant_text") or "").strip()
        ts = str(data.get("tts_script") or "").strip()
        kind = str(data.get("message_kind") or "voice").strip()
        if at or ts:
            return (at or ts), _clean_tts(ts or at), kind
    return text, _clean_tts(text), "voice"


def _clean_tts(t: str) -> str:
    """Drop markup/cue tags (<soft>, [pause], *laughs*) so TTS speaks clean
    prose instead of reading the tag words aloud."""
    t = re.sub(r"<[^>\n]{0,40}>", " ", t or "")
    t = re.sub(r"\[[^\]\n]{0,40}\]", " ", t)
    t = re.sub(r"\*[^*\n]{0,40}\*", " ", t)
    return re.sub(r"\s{2,}", " ", t).strip()


# ── AI Friends: persistence + persona builder ─────────────────────────────────
_FRIEND_PRESETS = {
    "Dominant":  {"traits": "decisive, leads conversation, direct, confident", "voice": "leo"},
    "Assertive": {"traits": "clear, confident, concise, expressive", "voice": "rex"},
    "Fantasy":   {"traits": "imaginative, story-driven, whimsical or mystical", "voice": "eve"},
    "Submissive":{"traits": "agreeable, gentle, asks for direction, non-sexual interpretation only", "voice": "ara"},
    "Romantic":  {"traits": "affectionate, warm, connection-focused, keep within safe product boundaries", "voice": "sal"},
    "Shy":       {"traits": "reserved at first, hesitant, softer pacing", "voice": "ara"},
    "Caring":    {"traits": "nurturing, reassuring, supportive, comforting", "voice": "ara"},
}
# Full xAI voice library (slug → exact xAI voice_id), ported pin-to-pin from the
# comfyAIcloud theme. The frontend sends the slug; TTS must send the exact id.
_VOICE_ID_MAP = {"ara":"ara", "eve":"eve", "leo":"leo", "rex":"rex", "sal":"sal", "jian":"jpi39icg", "hao":"d18jlf6v", "xia":"33g9t0jl", "pavel":"26w6ihxi", "andrei":"dr8gqysu", "dmitri":"wy0m9l5w", "irina":"om17cury", "enzo":"x7avnu1k", "matteo":"bcs7l2c3", "luca":"hqxr4yub", "alessandro":"h27ltdnz", "karan":"89q2pnko", "ananya":"73xd5dum", "remi":"0p0rt7o1", "hugo":"hbxkrnwm", "camille":"69smp8rm", "manuel":"yis75yfp", "javier":"ekhwx401", "diego":"jupvcf34", "andres":"0hhfxxqq", "kasper":"0ih5oi34", "lars":"gwnexu6y", "ida":"97zmdc6s", "duc":"fc7de6afcf6c", "grace":"f8cf5c2c78d4", "axel":"e22152e06fd8", "valtteri":"dfe7b9e7d217", "aylin":"d634b6da3d3b", "sakura":"d0cb9ff07d95", "helmi":"c3a2c594479e", "jun-seo":"bf9fe5b5f981", "min-jun":"b5ae17439907", "ren":"b1a7441b97a1", "mateus":"abfbdf26f115", "thijs":"a13662ba951c", "seo-yeon":"a0401c9101f8", "katarzyna":"97fabd54445f", "daniel":"96819d0bd28d", "krit":"908c4626660f", "eero":"83c6f4fea98e", "minh":"7a9ee820b342", "claire":"79f3a8b96d43", "james":"78a495fdbb39", "khalid":"70013edeb8e8", "beatriz":"6da5baee46d0", "emre":"670a0c3ac005", "femke":"58d27475085e", "aroon":"4ff93971bfdc", "saga":"490ea3be50b1", "clara":"458705c07139", "moritz":"41321eb41295", "niklas":"40f31906b23d", "rafael":"3d030bc92a87", "lena":"3a7889066fa2", "mateusz":"37329fd8895a", "layla":"35c8d7f60dc8", "elina":"34fd4dce1ba3", "jakub":"34fd4dce1ba3", "noor":"247783ebdd51", "ruben":"244e27b39200", "ji-yeon":"23be42535a45", "tariq":"23468361b4ef", "erik":"1f046a033914", "aleksandra":"1b12d5daee6b", "kaan":"182a91893636", "mai":"0895a5b8ce5c"}
_VALID_VOICES = set(_VOICE_ID_MAP)

# Voice (TTS) duration tiers: seconds → settings key (mirrors cat_cost_voice_*).
_VOICE_TIERS = {15: "cost_voice_15s", 30: "cost_voice_30s", 60: "cost_voice_60s",
                120: "cost_voice_120s", 300: "cost_voice_300s"}
_VOICE_TIER_DEFAULT = {15: "30", 30: "60", 60: "120", 120: "240", 300: "600"}


def _voice_tier_cost(s: dict, duration) -> int:
    try:
        dur = int(duration or 15)
    except Exception:
        dur = 15
    if dur not in _VOICE_TIERS:
        dur = 15
    return int(s.get(_VOICE_TIERS[dur], _VOICE_TIER_DEFAULT[dur]) or 0)


def _friend_system_prompt(name, primary, secondary, custom, voice, lang):
    """Server-side port of the theme's buildSys — the exact pin-to-pin contract."""
    pt = _FRIEND_PRESETS.get(primary, {}).get("traits", primary)
    st = _FRIEND_PRESETS.get(secondary, {}).get("traits", secondary) if secondary else ""
    s = f"You are an AI Friend named {name}.\n\nIdentity:\n"
    s += "- Keep the same personality, tone, and speaking style across messages.\n"
    s += "- Use the selected personality as your emotional anchor in every reply.\n"
    s += "- Sound human, fresh, and naturally varied instead of repeating the same catchphrases or reply rhythm.\n"
    s += f"\nSelected personality:\n- Primary: {primary} ({pt})\n"
    if secondary:
        s += f"- Secondary: {secondary} ({st})\n"
    if custom:
        s += f"\nCustom personality:\n- {custom}\n"
    s += f"\nVoice style:\n- Preferred voice: {voice or 'ara'}\n"
    s += "- Match delivery to the emotional tone of the current reply; vary it across turns.\n"
    s += f"\nBehavior rules:\n- Always respond in {lang or 'en'}.\n"
    s += "- Keep the exchange moving with one natural follow-up question when it fits.\n"
    s += "- Do not recycle the same opener, reassurance, or closing across nearby turns.\n"
    s += "- Vary sentence length and phrasing while staying in character.\n"
    s += "\nOUTPUT CONTRACT:\nReturn valid JSON only. No markdown. Use exactly these keys:\n"
    s += '{"assistant_text":"spoken reply","tts_script":"voice-ready version of the same reply","turn_type":"dialogue","message_kind":"voice"}\n'
    s += "Rules:\n- assistant_text and tts_script stay short and spoken, usually under 70 words.\n"
    s += "- Write tts_script as plain natural speech: NO markup tags, NO bracketed cues, NO stage directions.\n"
    s += "- Ask at most one fresh follow-up question specific to the user's latest topic.\n"
    s += "- Avoid repeating phrasing from the last few turns."
    return s


def _friend_public(f: Friend):
    return {"id": f.id, "name": f.name, "avatar_url": f.avatar_url, "tagline": f.tagline,
            "primary": f.primary_personality, "secondary": f.secondary_personality,
            "voice": f.voice_id, "language": f.language}


class FriendReq(BaseModel):
    name: str
    avatar_url: str | None = ""
    tagline: str | None = ""
    primary: str | None = ""
    secondary: str | None = ""
    custom: str | None = ""
    voice: str | None = "ara"
    language: str | None = "en"


@router.get("/friends")
def friends_list(user=Depends(auth.require_user), db: Session = Depends(get_db)):
    rows = db.query(Friend).filter(Friend.user_id == user.id).order_by(Friend.created_at.desc()).all()
    return {"friends": [_friend_public(f) for f in rows]}


@router.post("/friends")
def friends_create(body: FriendReq, user=Depends(auth.require_user), db: Session = Depends(get_db)):
    name = (body.name or "").strip()[:60]
    if not name:
        raise HTTPException(400, "Give your friend a name.")
    primary = (body.primary or "Caring").strip()
    secondary = (body.secondary or "").strip()
    voice = (body.voice or "ara").strip().lower()
    if voice not in _VALID_VOICES:
        voice = "ara"
    custom = (body.custom or "").strip()[:1200]
    lang = (body.language or "en").strip()[:8]
    avatar = (body.avatar_url or "").strip()[:600]
    tagline = (body.tagline or "").strip()[:160] or (primary + (" & " + secondary if secondary else "") + " companion")
    sys = _friend_system_prompt(name, primary, secondary, custom, voice, lang)
    slug = (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "friend") + "-" + uuid.uuid4().hex[:6]
    f = Friend(user_id=user.id, slug=slug, name=name, avatar_url=avatar, tagline=tagline,
               primary_personality=primary, secondary_personality=secondary, custom_personality=custom,
               voice_id=voice, language=lang, system_prompt=sys)
    db.add(f); db.commit(); db.refresh(f)
    return {"status": "ok", "friend": _friend_public(f)}


@router.delete("/friends/{fid}")
def friends_delete(fid: int, user=Depends(auth.require_user), db: Session = Depends(get_db)):
    f = db.query(Friend).filter(Friend.id == fid, Friend.user_id == user.id).first()
    if not f:
        raise HTTPException(404, "Friend not found.")
    db.delete(f); db.commit()
    return {"status": "ok"}


# ── image upload (friend avatars + in-chat attachments) ───────────────────────
@router.post("/upload")
def upload_image(image: UploadFile = File(...), user=Depends(auth.require_user)):
    ext = os.path.splitext(image.filename or "")[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        raise HTTPException(400, "Use a JPG, PNG, WEBP or GIF image.")
    data = image.file.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(400, "Image is too large (max 8MB).")
    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    name = uuid.uuid4().hex + (ext if ext != ".jpeg" else ".jpg")
    with open(os.path.join(_UPLOAD_DIR, name), "wb") as fh:
        fh.write(data)
    return {"status": "ok", "url": f"/api/site/uploads/{name}"}


@router.get("/uploads/{name}")
def serve_upload(name: str):
    path = os.path.join(_UPLOAD_DIR, os.path.basename(name))
    if not os.path.isfile(path):
        raise HTTPException(404, "Not found.")
    return FileResponse(path)


class ChatReq(BaseModel):
    messages: list
    persona: str | None = None
    friend_id: int | None = None     # if set + owned, server uses its stored persona
    image: str | None = None         # data URL or /api/site/uploads/.. for in-chat vision


@router.post("/chat")
def chat(body: ChatReq, user=Depends(auth.require_user), db: Session = Depends(get_db)):
    s = _settings(db)
    base = (s.get("img_base_url") or "").rstrip("/")
    key = s.get("img_api_key")
    if not (base and key):
        raise HTTPException(503, "Chat isn't enabled yet. Add an AI provider in admin Settings.")
    cost = 0 if user.is_admin else int(s.get("cost_chat", "1") or 0)
    if (user.credits or 0) < cost:
        raise HTTPException(402, f"Not enough credits. Need {cost}, you have {user.credits}.")
    # Persona: prefer a stored (saved) friend's prompt over any client-supplied one.
    persona = body.persona
    if body.friend_id:
        fr = db.query(Friend).filter(Friend.id == body.friend_id, Friend.user_id == user.id).first()
        if fr and fr.system_prompt:
            persona = fr.system_prompt
    msgs = []
    if persona:
        msgs.append({"role": "system", "content": str(persona)[:4000]})
    history = [m for m in (body.messages or [])[-12:]
               if isinstance(m, dict) and m.get("role") in ("user", "assistant") and m.get("content")]
    for i, m in enumerate(history):
        content = str(m["content"])[:4000]
        # attach the uploaded image to the latest user turn for in-chat vision
        if body.image and m["role"] == "user" and i == len(history) - 1:
            msgs.append({"role": "user", "content": [
                {"type": "text", "text": content or "Look at this image and respond in character."},
                {"type": "image_url", "image_url": {"url": body.image}}]})
        else:
            msgs.append({"role": m["role"], "content": content})
    model = (s.get("vision_model") if body.image else None) or s.get("chat_model") or "grok-2-latest"
    try:
        import requests
        r = requests.post(base + "/chat/completions", headers={"Authorization": f"Bearer {key}"},
                          json={"model": model, "messages": msgs, "max_tokens": 700}, timeout=150)
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"] or ""
        reply, tts, kind = _parse_friend_reply(raw)
        if cost:
            _grant(db, user, -cost, "ai friends chat")
        return {"status": "ok", "reply": reply, "tts": tts, "kind": kind, "credits": user.credits}
    except Exception as e:
        raise HTTPException(502, f"Chat failed: {e}")


class TTSReq(BaseModel):
    text: str
    voice: str | None = "ara"
    duration: int | None = 15     # voice tier (seconds): 15/30/60/120/300
    preview: bool | None = False  # wizard voice sample — free, short


@router.post("/tts")
def tts(body: TTSReq, user=Depends(auth.require_user), db: Session = Depends(get_db)):
    s = _settings(db)
    base = (s.get("img_base_url") or "").rstrip("/")
    key = s.get("img_api_key")
    if not (base and key):
        raise HTTPException(503, "Voice isn't enabled yet. Add an AI provider in admin Settings.")
    cost = 0 if (body.preview or user.is_admin) else _voice_tier_cost(s, body.duration)
    if (user.credits or 0) < cost:
        raise HTTPException(402, f"Not enough credits. Need {cost}, you have {user.credits}.")
    slug = (body.voice or "ara").strip().lower()
    voice_id = _VOICE_ID_MAP.get(slug, slug)          # exact xAI id
    try:
        import requests
        cap = 200 if body.preview else 6000
        say = _clean_tts(body.text)[:cap] or (body.text or "")[:cap]
        r = requests.post(base + "/tts", headers={"Authorization": f"Bearer {key}"},
                          json={"text": say, "voice_id": voice_id, "language": "en"}, timeout=180)
        r.raise_for_status()
        if cost:
            _grant(db, user, -cost, "voice")
        return Response(content=r.content, media_type=r.headers.get("content-type", "audio/mpeg"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Voice failed: {e}")


# ── buy credits ───────────────────────────────────────────────────────────────
class BuyReq(BaseModel):
    package: str


@router.post("/buy")
def buy(body: BuyReq, user=Depends(auth.require_user), db: Session = Depends(get_db)):
    s = _settings(db)
    kid, ksec = s.get("razorpay_key_id"), s.get("razorpay_key_secret")
    if not (kid and ksec):
        raise HTTPException(503, "Payments aren't enabled yet. Add Razorpay keys in admin Settings.")
    pkg = next((p for p in PACKAGES if p["key"] == body.package), None)
    if not pkg:
        raise HTTPException(400, "Unknown package.")
    amount = pkg["inr"] * 100  # paise
    try:
        import requests
        token = base64.b64encode(f"{kid}:{ksec}".encode()).decode()
        r = requests.post("https://api.razorpay.com/v1/orders",
                          headers={"Authorization": f"Basic {token}"},
                          json={"amount": amount, "currency": "INR", "receipt": f"u{user.id}-{pkg['key']}",
                                "notes": {"user_id": str(user.id), "credits": str(pkg["credits"])}},
                          timeout=30)
        r.raise_for_status()
        oid = r.json()["id"]
    except Exception as e:
        raise HTTPException(502, f"Could not start checkout: {e}")
    db.add(Order(rzp_order_id=oid, user_id=user.id, credits=pkg["credits"], amount=amount))
    db.commit()
    return {"order_id": oid, "key_id": kid, "amount": amount, "currency": "INR",
            "credits": pkg["credits"], "name": user.name, "email": user.email}


class VerifyReq(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/pay/verify")
def pay_verify(body: VerifyReq, user=Depends(auth.require_user), db: Session = Depends(get_db)):
    ksec = _settings(db).get("razorpay_key_secret")
    if not ksec:
        raise HTTPException(503, "Payments not configured.")
    order = db.query(Order).filter(Order.rzp_order_id == body.razorpay_order_id).first()
    if not order or order.user_id != user.id:
        raise HTTPException(404, "Order not found.")
    if order.status == "paid":
        return {"status": "ok", "credits": user.credits, "already": True}
    expected = hmac.new(ksec.encode(), f"{body.razorpay_order_id}|{body.razorpay_payment_id}".encode(),
                        hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, body.razorpay_signature):
        raise HTTPException(400, "Payment verification failed.")
    order.status = "paid"
    _grant(db, user, order.credits, f"Purchased {order.credits} credits")
    return {"status": "ok", "credits": user.credits}


# ── admin ─────────────────────────────────────────────────────────────────────
@router.get("/admin/settings")
def admin_settings(admin=Depends(auth.require_admin), db: Session = Depends(get_db)):
    return {"settings": _settings(db)}


class SettingsUpdate(BaseModel):
    settings: dict


@router.post("/admin/settings")
def admin_settings_save(body: SettingsUpdate, admin=Depends(auth.require_admin), db: Session = Depends(get_db)):
    for k, v in (body.settings or {}).items():
        if k in DEFAULT_SETTINGS:
            _set(db, k, "" if v is None else str(v))
    db.commit()
    return {"status": "ok", "settings": _settings(db)}


@router.get("/admin/users")
def admin_users(admin=Depends(auth.require_admin), db: Session = Depends(get_db)):
    rows = db.query(SiteUser).order_by(SiteUser.created_at.desc()).limit(500).all()
    return {"users": [{**_public_user(u), "created_at": u.created_at.isoformat() if u.created_at else None} for u in rows]}


class GrantReq(BaseModel):
    user_id: int
    amount: int


@router.post("/admin/grant")
def admin_grant(body: GrantReq, admin=Depends(auth.require_admin), db: Session = Depends(get_db)):
    u = db.query(SiteUser).get(body.user_id)
    if not u:
        raise HTTPException(404, "User not found.")
    _grant(db, u, int(body.amount), f"Admin grant by {admin.email}")
    return {"status": "ok", "user": _public_user(u)}
