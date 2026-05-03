import hmac
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import Cookie, Depends, Header, HTTPException, Request, Response
from loguru import logger
from sqlalchemy.orm import Session

from server.core.config import cookie_secure, cookie_samesite, LLM_ADMIN_TOKEN_ENV, LLM_ADMIN_TOKEN_HEADER, INTERNAL_ALERT_TOKEN_ENV, INTERNAL_ALERT_TOKEN_HEADER
from server.security_utils import decode_access_token, issue_access_token, DecryptionError, decrypt_api_key
from server.models_db import User
from server.core.database import get_db


def _issue_token_for_user(user: User) -> str:
    pwd_ts = None
    if user.password_changed_at:
        if user.password_changed_at.tzinfo is None:
            pwd_ts = user.password_changed_at.replace(tzinfo=timezone.utc).timestamp()
        else:
            pwd_ts = user.password_changed_at.timestamp()
    return issue_access_token(str(user.id), password_changed_at=pwd_ts, token_version=user.token_version)


def set_access_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        samesite=cookie_samesite(),
        secure=cookie_secure(),
    )


def clear_access_cookie(response: Response) -> None:
    response.delete_cookie(
        "access_token",
        httponly=True,
        samesite=cookie_samesite(),
        secure=cookie_secure(),
    )


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    text = authorization.strip()
    if not text.lower().startswith("bearer "):
        return None
    return text[7:].strip() or None


def resolve_token(access_token_cookie: str | None, authorization: str | None) -> str:
    bearer = _extract_bearer_token(authorization)
    token = bearer or access_token_cookie
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token


def get_current_user(
    db: Session,
    access_token_cookie: str | None,
    authorization: str | None,
) -> User:
    token = resolve_token(access_token_cookie, authorization)
    logger.debug("[auth] token received")
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub", "0"))
        logger.debug("[auth] decoded user_id: {}", user_id)
    except Exception as exc:
        logger.debug("[auth] decode error: {}", exc)
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    token_pwd_iat = payload.get("pwd_iat")
    if user.password_changed_at is not None:
        if token_pwd_iat is None:
            raise HTTPException(status_code=401, detail="密码已更改，请重新登录")
        if user.password_changed_at.tzinfo is None:
            changed_ts = user.password_changed_at.replace(tzinfo=timezone.utc).timestamp()
        else:
            changed_ts = user.password_changed_at.timestamp()
        if int(changed_ts) > int(token_pwd_iat):
            raise HTTPException(status_code=401, detail="密码已更改，请重新登录")

    token_version = payload.get("tv", 0)
    if token_version != user.token_version:
        raise HTTPException(status_code=401, detail="会话已失效，请重新登录")

    return user


def require_auth_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
) -> User:
    return get_current_user(db, access_token_cookie, authorization)


def require_llm_admin_token(token: str | None = Header(default=None, alias=LLM_ADMIN_TOKEN_HEADER)) -> None:
    expected = os.getenv(LLM_ADMIN_TOKEN_ENV, "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail=f"{LLM_ADMIN_TOKEN_ENV} not configured")
    if len(expected) < 32:
        raise HTTPException(status_code=503, detail=f"{LLM_ADMIN_TOKEN_ENV} too short (min 32 chars)")
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid admin token")


def require_alert_ingest_token(token: str | None = Header(default=None, alias=INTERNAL_ALERT_TOKEN_HEADER)) -> None:
    expected = os.getenv(INTERNAL_ALERT_TOKEN_ENV, "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail=f"{INTERNAL_ALERT_TOKEN_ENV} not configured")
    if len(expected) < 32:
        raise HTTPException(status_code=503, detail=f"{INTERNAL_ALERT_TOKEN_ENV} too short (min 32 chars)")
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid alerts token")


def _safe_decrypt(encrypted: str | None) -> str | None:
    try:
        return decrypt_api_key(encrypted)
    except DecryptionError:
        return None


def _mask_key(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:3]}***{value[-3:]}"
