from enum import StrEnum
from typing import Callable

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from server.core.database import get_db
from server.core.security import get_current_user
from server.models_db import User


class Role(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


ROLE_HIERARCHY: dict[Role, int] = {
    Role.ADMIN: 3,
    Role.ANALYST: 2,
    Role.VIEWER: 1,
}


def has_role(user: User, required: Role) -> bool:
    try:
        user_role = Role(user.role)
    except ValueError:
        user_role = None
    user_level = ROLE_HIERARCHY.get(user_role, 0)
    required_level = ROLE_HIERARCHY.get(required, 999)
    return user_level >= required_level


def require_role(*roles: Role) -> Callable:
    async def _check(
        authorization: str | None = Header(default=None, alias="Authorization"),
        access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
        db: Session = Depends(get_db),
    ) -> User:
        user = get_current_user(db, access_token_cookie, authorization)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未认证")
        allowed = any(has_role(user, r) for r in roles) if roles else True
        if not allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return user
    return _check


require_admin = require_role(Role.ADMIN)
require_analyst = require_role(Role.ADMIN, Role.ANALYST)
require_viewer = require_role(Role.ADMIN, Role.ANALYST, Role.VIEWER)
