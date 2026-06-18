import os
import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database.database import get_db
from database.models import Setting

router = APIRouter()


def _parse_custom_models(raw) -> list:
    """Custom models are stored as a JSON string of [{"id","label"}]. Be lenient
    about legacy/blank values so a malformed row never breaks the picker."""
    if not raw:
        return []
    if isinstance(raw, list):
        items = raw
    else:
        try:
            items = json.loads(raw)
        except Exception:
            return []
    out = []
    seen = set()
    for it in items if isinstance(items, list) else []:
        if isinstance(it, str):
            it = {"id": it, "label": it}
        if not isinstance(it, dict):
            continue
        mid = str(it.get("id") or "").strip()
        if not mid or mid in seen:
            continue
        seen.add(mid)
        out.append({"id": mid, "label": str(it.get("label") or mid).strip() or mid})
    return out

# Each mode picks where the agent may work and how it handles risky actions.
MODE_MAP = {
    "sandbox":   {"workspace_path": "./workspace",         "permission_mode": "ask"},
    "desktop":   {"workspace_path": os.path.expanduser("~/Desktop"), "permission_mode": "auto"},
    "workspace": {"workspace_path": os.path.expanduser("~"),         "permission_mode": "auto"},
}


class SettingUpdate(BaseModel):
    api_key: str | None = None
    api_key_2: str | None = None
    api_key_3: str | None = None
    base_url: str | None = None
    model_name: str | None = None
    custom_models: list | None = None
    temperature: float | None = None
    system_prompt: str | None = None
    max_steps: int | None = None
    tools_enabled: bool | None = None
    workspace_path: str | None = None
    permission_mode: str | None = None
    swarm_mode: str | None = None
    mode: str | None = None
    desktop_granted: bool | None = None


def _row(db):
    s = db.query(Setting).first()
    if not s:
        s = Setting()
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def _serialize(s):
    return {
        "api_key": s.api_key,
        "api_key_2": s.api_key_2,
        "api_key_3": s.api_key_3,
        "base_url": s.base_url,
        "model_name": s.model_name,
        "custom_models": _parse_custom_models(getattr(s, "custom_models", "[]")),
        "temperature": s.temperature,
        "system_prompt": s.system_prompt,
        "max_steps": s.max_steps,
        "tools_enabled": s.tools_enabled,
        "workspace_path": s.workspace_path,
        "permission_mode": s.permission_mode,
        "swarm_mode": s.swarm_mode,
        "mode": s.mode,
        "desktop_granted": s.desktop_granted,
    }


@router.get("/")
def get_settings(db: Session = Depends(get_db)):
    return _serialize(_row(db))


@router.post("/")
def update_settings(update: SettingUpdate, db: Session = Depends(get_db)):
    s = _row(db)
    for field, val in update.model_dump().items():
        if val is None:
            continue
        # Custom models arrive as a list but the column stores JSON text. Clean +
        # dedupe before persisting so a junk entry can never poison the picker.
        if field == "custom_models":
            s.custom_models = json.dumps(_parse_custom_models(val))
            continue
        setattr(s, field, val)
    db.commit()
    db.refresh(s)
    return {"status": "success", "settings": _serialize(s)}


@router.delete("/custom-models")
def clear_custom_models(db: Session = Depends(get_db)):
    """Remove every user-added custom model in one shot (the 'clear all' button)."""
    s = _row(db)
    s.custom_models = "[]"
    db.commit()
    db.refresh(s)
    return {"status": "success", "settings": _serialize(s)}


class ModeReq(BaseModel):
    mode: str


@router.post("/mode")
def set_mode(req: ModeReq, db: Session = Depends(get_db)):
    """Switch working mode — sets the workspace folder + permission policy."""
    cfg = MODE_MAP.get(req.mode)
    if not cfg:
        return {"status": "error", "detail": f"unknown mode '{req.mode}'"}
    s = _row(db)
    s.mode = req.mode
    s.workspace_path = cfg["workspace_path"]
    s.permission_mode = cfg["permission_mode"]
    s.desktop_granted = True
    # Make sure the target folder exists so file creation works immediately.
    try:
        os.makedirs(os.path.expanduser(cfg["workspace_path"]), exist_ok=True)
    except Exception:
        pass
    db.commit()
    db.refresh(s)
    return {"status": "success", "settings": _serialize(s)}
