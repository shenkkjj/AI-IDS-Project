from typing import Any

from fastapi import APIRouter, Cookie, Depends, Header
from sqlalchemy.orm import Session

from server.core.database import get_db
from server.core.security import get_current_user
from server.models_db import Log

router = APIRouter(prefix="/logs", tags=["日志"])


@router.get("")
async def get_logs(
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    logs = (
        db.query(Log)
        .filter((Log.user_id == user.id) | (Log.user_id.is_(None)))
        .order_by(Log.created_at.desc())
        .limit(200)
        .all()
    )
    return {
        "items": [
            {
                "id": item.id,
                "level": item.level,
                "action": item.action,
                "detail": item.detail,
                "created_at": item.created_at.isoformat(),
            }
            for item in logs
        ]
    }
