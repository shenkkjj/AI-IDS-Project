from typing import Any

from fastapi import APIRouter, Cookie, Depends, Header
from sqlalchemy.orm import Session

from server.core.database import get_db
from server.core.security import get_current_user, require_auth_user
from server.models.schemas import UserConfigIn
from server.models_db import User
from server.services import user_service

router = APIRouter(prefix="/user", tags=["用户配置"])


@router.get("/config")
async def get_user_config(
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    return user_service.get_user_config(user, db)


@router.put("/config")
async def put_user_config(
    data: UserConfigIn,
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    return user_service.update_user_config(user, data, db)
