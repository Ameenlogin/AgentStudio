from fastapi import APIRouter
from pydantic import BaseModel
from tools import permissions

router = APIRouter()


class Decision(BaseModel):
    id: str
    decision: str   # "allow" | "allow_all" | "deny"


@router.post("/resolve")
def resolve(d: Decision):
    ok = permissions.resolve(d.id, d.decision)
    return {"status": "ok" if ok else "expired", "id": d.id, "decision": d.decision}
