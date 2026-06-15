import os
import shutil
from fastapi import APIRouter, UploadFile, File, Query, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import Setting
from tools.sandbox import set_workspace, get_workspace, resolve, rel

router = APIRouter()


def _sync_workspace(db: Session):
    s = db.query(Setting).first()
    set_workspace((s.workspace_path if s else None) or "./workspace")


@router.post("/upload")
async def upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    _sync_workspace(db)
    safe_name = os.path.basename(file.filename or "upload.bin")
    dest = resolve(safe_name)
    try:
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        return {"status": "ok", "path": rel(dest), "size": os.path.getsize(dest)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download")
def download(path: str = Query(...), db: Session = Depends(get_db)):
    _sync_workspace(db)
    try:
        p = resolve(path)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not os.path.isfile(p):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(p, filename=os.path.basename(p), media_type="application/octet-stream")


@router.get("/list")
def list_files(path: str = ".", db: Session = Depends(get_db)):
    _sync_workspace(db)
    try:
        p = resolve(path)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not os.path.isdir(p):
        return {"path": rel(p), "entries": []}
    entries = []
    for name in sorted(os.listdir(p)):
        full = os.path.join(p, name)
        entries.append({
            "name": name,
            "is_dir": os.path.isdir(full),
            "size": os.path.getsize(full) if os.path.isfile(full) else None,
            "path": rel(full),
        })
    return {"path": rel(p), "entries": entries}


@router.get("/paths")
def system_paths():
    """Suggested locations for granting workspace access."""
    home = os.path.expanduser("~")
    candidates = {
        "home": home,
        "desktop": os.path.join(home, "Desktop"),
        "documents": os.path.join(home, "Documents"),
        "downloads": os.path.join(home, "Downloads"),
        "workspace": os.path.abspath("./workspace"),
        "current": get_workspace(),
    }
    return {k: v for k, v in candidates.items()}
