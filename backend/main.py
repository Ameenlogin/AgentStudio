import os
import sys

# Make the backend directory importable no matter where the process is launched.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="Agent Studio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "Agent Studio"}


# ── Database ────────────────────────────────────────────────────────────────
from database.database import engine, Base
from database.models import Setting
from sqlalchemy.orm import Session

Base.metadata.create_all(bind=engine)

# Lightweight migration: add columns introduced after a DB may have been created.
from sqlalchemy import text as _sql_text
with engine.begin() as _conn:
    for _table, _col, _decl in [
        ("messages", "content_hash", "VARCHAR"),
        ("settings", "swarm_mode", "VARCHAR DEFAULT 'auto'"),
        ("settings", "mode", "VARCHAR DEFAULT 'sandbox'"),
        ("settings", "custom_models", "TEXT DEFAULT '[]'"),
    ]:
        try:
            _cols = [r[1] for r in _conn.execute(_sql_text(f"PRAGMA table_info({_table})"))]
            if _col not in _cols:
                _conn.execute(_sql_text(f"ALTER TABLE {_table} ADD COLUMN {_col} {_decl}"))
        except Exception:
            pass

with Session(engine) as session:
    row = session.query(Setting).first()
    if not row:
        row = Setting()
        session.add(row)
    # Non-secret defaults always ship; the API key is optional and stays local.
    # A fresh install boots with NO key — the UI then prompts the user to add
    # their NVIDIA NIM key in Settings (in-app onboarding).
    from config.defaults import BASE_URL as _BASE_URL, DEFAULT_MODEL as _MODEL
    try:
        from config.keys import NVIDIA_API_KEYS as _KEYS  # optional, gitignored
    except Exception:
        _KEYS = []
    # Ignore blanks and the example placeholder so a copied template never seeds.
    _KEYS = [k for k in (_KEYS or []) if k and k.strip() and "YOUR_KEY" not in k]
    # Seed any empty key slots from a local keys.py (optional), but NEVER wipe
    # keys the user saved — extra keys multiply the rate-limit head-room.
    for _i, _attr in enumerate(("api_key", "api_key_2", "api_key_3")):
        if not (getattr(row, _attr, "") or "").strip() and _i < len(_KEYS):
            setattr(row, _attr, _KEYS[_i])
    if not (row.base_url or "").strip():
        row.base_url = _BASE_URL
    if not (row.model_name or "").strip():
        row.model_name = _MODEL
    row.desktop_granted = True
    session.commit()

# ── Routers (absolute imports — the original crash was here) ──────────────────
from api import (chat, settings as settings_router, conversations,
                 permissions as permissions_router, files as files_router,
                 search as search_router, skills as skills_router)
app.include_router(chat.router, prefix="/api/chat")
app.include_router(settings_router.router, prefix="/api/settings")
app.include_router(conversations.router, prefix="/api/conversations")
app.include_router(permissions_router.router, prefix="/api/permissions")
app.include_router(files_router.router, prefix="/api/files")
app.include_router(search_router.router, prefix="/api/search")
app.include_router(skills_router.router, prefix="/api/skills")

# ── Serve the built frontend ──────────────────────────────────────────────────
frontend_dist = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
)

if os.path.isdir(frontend_dist):
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"error": "Not found"}, status_code=404)
        target = os.path.join(frontend_dist, full_path)
        if full_path and os.path.isfile(target):
            return FileResponse(target)
        index = os.path.join(frontend_dist, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)
        return JSONResponse({"error": "Frontend not built"}, status_code=404)
else:
    @app.get("/")
    async def no_frontend():
        return JSONResponse(
            {"error": "Frontend not built", "hint": "Run START.bat or: cd frontend && npm install && npm run build"},
            status_code=503,
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
