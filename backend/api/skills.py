"""Skills API — list installed skills and install new ones from a GitHub repo."""
from fastapi import APIRouter
from pydantic import BaseModel
from services import skills as skills_service

router = APIRouter()


class InstallReq(BaseModel):
    url: str


@router.get("/")
def list_skills():
    return {"skills": skills_service.list_skills()}


@router.post("/install")
def install(req: InstallReq):
    result = skills_service.install_from_github(req.url)
    ok = result.lower().startswith(("installed", "skill '")) and "error" not in result.lower()
    return {"ok": ok, "message": result, "skills": skills_service.list_skills()}


@router.get("/{name}")
def read_skill(name: str):
    return {"name": name, "guide": skills_service.read_skill(name)}
