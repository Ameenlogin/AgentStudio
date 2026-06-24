"""Agent Studio session billing + usage tracking.

The hosted Agent Studio is login-gated and billed once per working *session*.
A session opens on the user's first agent run and stays current while they keep
using it; once they're idle past the gap window, the next run opens (and charges)
a fresh session. Admins ride free. The ``AgentStudioSession`` rows double as the
admin usage ledger (count, recency, credits spent).

Kept separate from ``api.site`` so the Agent Studio chat router can charge without
importing the marketing-site router (no import cycle)."""
import datetime

from sqlalchemy.orm import Session

from database.site_models import (
    SiteUser, CreditTxn, SiteSetting, AgentStudioSession, DEFAULT_SETTINGS,
)


class InsufficientCredits(Exception):
    """Raised when the account can't afford to open a new session."""
    def __init__(self, need: int, have: int):
        self.need, self.have = need, have
        super().__init__(f"Need {need} credits to start an Agent Studio session; you have {have}.")


def _setting(db: Session, key: str) -> str:
    row = db.query(SiteSetting).filter(SiteSetting.key == key).first()
    if row and row.value not in (None, ""):
        return row.value
    return DEFAULT_SETTINGS.get(key, "")


def session_cost(db: Session) -> int:
    try:
        return max(0, int(_setting(db, "cost_agentstudio_session") or 0))
    except (TypeError, ValueError):
        return 10


def _gap(db: Session) -> datetime.timedelta:
    try:
        hours = float(_setting(db, "agentstudio_session_gap_hours") or 12)
    except (TypeError, ValueError):
        hours = 12.0
    return datetime.timedelta(hours=max(0.0, hours))


def ensure_session(db: Session, user: SiteUser) -> tuple[AgentStudioSession, int]:
    """Open or continue this account's Agent Studio session.

    Returns ``(session, charged)`` where ``charged`` is the credits deducted now
    (0 when continuing an open session or for admins). Raises
    ``InsufficientCredits`` when a new session is needed but unaffordable."""
    now = datetime.datetime.utcnow()
    last = (
        db.query(AgentStudioSession)
        .filter(AgentStudioSession.user_id == user.id)
        .order_by(AgentStudioSession.last_active_at.desc())
        .first()
    )
    if last and (now - (last.last_active_at or last.started_at)) < _gap(db):
        last.last_active_at = now            # still inside the window — free
        db.commit()
        return last, 0

    cost = 0 if user.is_admin else session_cost(db)
    if cost and (user.credits or 0) < cost:
        raise InsufficientCredits(cost, user.credits or 0)
    if cost:
        user.credits = max(0, (user.credits or 0) - cost)
        db.add(CreditTxn(user_id=user.id, delta=-cost, reason="Agent Studio session",
                         balance_after=user.credits))
    sess = AgentStudioSession(user_id=user.id, cost=cost, started_at=now, last_active_at=now)
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess, cost


def usage_by_user(db: Session) -> dict:
    """Aggregate Agent Studio usage per account, for the admin dashboard:
    ``{user_id: {"sessions": n, "credits": spent, "last_active": iso|None}}``."""
    from sqlalchemy import func
    rows = (
        db.query(
            AgentStudioSession.user_id,
            func.count(AgentStudioSession.id),
            func.coalesce(func.sum(AgentStudioSession.cost), 0),
            func.max(AgentStudioSession.last_active_at),
        )
        .group_by(AgentStudioSession.user_id)
        .all()
    )
    out = {}
    for uid, sessions, credits, last in rows:
        out[uid] = {
            "sessions": int(sessions or 0),
            "credits": int(credits or 0),
            "last_active": last.isoformat() if last else None,
        }
    return out
