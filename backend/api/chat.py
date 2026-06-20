from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import Setting
from tools.sandbox import set_workspace, workspace_for_client
from agents.agent import run_agent

router = APIRouter()


@router.post("/")
async def chat_endpoint(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    messages = data.get("messages", [])
    model_override = data.get("model_name", None)
    skill = (data.get("skill") or "").strip() or None

    # ── Bring-your-own-key (browser-local) ────────────────────────────────────
    # The hosted deployment has no login and no shared server key: each visitor
    # keeps their own NVIDIA NIM key in their own browser and sends it per
    # request, so concurrent users never share or overwrite a key. We use those
    # creds when present and otherwise fall back to any server-side key (the
    # classic single-user desktop install).
    body_keys = data.get("api_keys") or data.get("api_key") or []
    if isinstance(body_keys, str):
        body_keys = [body_keys]
    body_keys = [k.strip() for k in body_keys if isinstance(k, str) and k.strip()]
    body_base_url = (data.get("base_url") or "").strip()

    settings = db.query(Setting).first()
    server_keys = [k for k in [settings.api_key, settings.api_key_2, settings.api_key_3] if k] if settings else []
    api_keys = body_keys or server_keys
    if not api_keys:
        raise HTTPException(status_code=400, detail="API key not configured. Open Settings and add your NVIDIA NIM key.")

    # Each browser (anonymous X-Client-Id) gets its own private workspace; the
    # desktop app sends no id and falls back to the configured single-user dir.
    client_ws = workspace_for_client(request.headers.get("X-Client-Id"))
    set_workspace(client_ws or (settings.workspace_path if settings else None) or "./workspace")

    cfg = dict(
        api_keys=api_keys,
        base_url=body_base_url or (settings.base_url if settings else None) or "https://integrate.api.nvidia.com/v1",
        model_name=model_override or (settings.model_name if settings else None),
        # Temperature & step budget are smart built-in defaults (no UI sliders).
        temperature=settings.temperature if settings.temperature is not None else 0.6,
        # The system prompt is the app's built-in, tuned instruction set — not a
        # user-editable field. Always use it (run_agent falls back to _AGENT_SYSTEM).
        system_prompt=None,
        max_steps=settings.max_steps or 80,
        tools_enabled=bool(settings.tools_enabled),
        permission_mode=settings.permission_mode or "ask",
        swarm_mode=settings.swarm_mode or "auto",
        skill=skill,
    )

    async def gen():
        async for ev in run_agent(messages, **cfg):
            yield ev

    return StreamingResponse(gen(), media_type="application/x-ndjson")
