from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import Setting
from tools.sandbox import set_workspace
from agents.agent import run_agent

router = APIRouter()


@router.post("/")
async def chat_endpoint(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    messages = data.get("messages", [])
    model_override = data.get("model_name", None)

    settings = db.query(Setting).first()
    if not settings or not settings.api_key:
        raise HTTPException(status_code=400, detail="API key not configured. Open Settings and add your NVIDIA key.")

    set_workspace(settings.workspace_path or "./workspace")

    api_keys = [k for k in [settings.api_key, settings.api_key_2, settings.api_key_3] if k]

    cfg = dict(
        api_keys=api_keys,
        base_url=settings.base_url,
        model_name=model_override or settings.model_name,
        # Temperature & step budget are smart built-in defaults (no UI sliders).
        temperature=settings.temperature if settings.temperature is not None else 0.6,
        system_prompt=(settings.system_prompt or None),
        max_steps=settings.max_steps or 80,
        tools_enabled=bool(settings.tools_enabled),
        permission_mode=settings.permission_mode or "ask",
        swarm_mode=settings.swarm_mode or "auto",
    )

    async def gen():
        async for ev in run_agent(messages, **cfg):
            yield ev

    return StreamingResponse(gen(), media_type="application/x-ndjson")
