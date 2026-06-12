from typing import Any

from fastapi import APIRouter, Body, Cookie, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from server.core.database import get_db, create_log
from server.core.security import decode_access_token, get_current_user
from server.core import refresh_tokens
from server.models.schemas import (LoginPasswordIn, OAuthLoginIn, OTPRequestIn, OTPVerifyIn,
                                   PasswordResetConfirmIn, PasswordResetRequestIn, UserRegisterIn)
from server.services import auth_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/totp/setup")
async def auth_totp_setup(
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    from server.services.totp_service import generate_totp_secret, get_totp_uri
    secret = generate_totp_secret()
    uri = get_totp_uri(user.email, secret)
    user.totp_secret = secret
    db.add(user)
    db.commit()
    create_log(db, user_id=user.id, level="info", action="totp_setup", detail="TOTP setup initiated")
    return {"totp_uri": uri}


@router.post("/totp/enable")
async def auth_totp_enable(
    code: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    if not user.totp_secret:
        raise HTTPException(status_code=400, detail="请先设置 TOTP")
    from server.services.totp_service import verify_totp, generate_backup_codes, hash_backup_code
    from server.core.database import create_log
    if not verify_totp(user.totp_secret, code):
        raise HTTPException(status_code=400, detail="验证码错误")
    backup_codes = generate_backup_codes()
    user.totp_enabled = True
    db.add(user)
    from server.models_db import AuthChallenge
    for code in backup_codes:
        challenge = AuthChallenge(
            user_id=user.id,
            email=user.email,
            challenge_type="backup_code",
            code_hash=hash_backup_code(code),
            expires_at=None,
        )
        db.add(challenge)
    db.commit()
    create_log(db, user_id=user.id, level="info", action="totp_enable", detail="TOTP enabled")
    return {"status": "ok", "backup_codes": backup_codes}


@router.post("/totp/disable")
async def auth_totp_disable(
    code: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    if not user.totp_enabled:
        raise HTTPException(status_code=400, detail="TOTP 未启用")
    from server.services.totp_service import verify_totp
    if not verify_totp(user.totp_secret, code):
        raise HTTPException(status_code=400, detail="验证码错误")
    user.totp_enabled = False
    user.totp_secret = None
    db.add(user)
    db.commit()
    create_log(db, user_id=user.id, level="info", action="totp_disable", detail="TOTP disabled")
    return {"status": "ok"}


@router.post("/totp/verify")
async def auth_totp_verify(
    code: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    if not user.totp_enabled:
        raise HTTPException(status_code=400, detail="TOTP 未启用")
    from server.services.totp_service import verify_totp
    if not verify_totp(user.totp_secret, code):
        raise HTTPException(status_code=400, detail="验证码错误")
    return {"status": "ok", "verified": True}


@router.post("/register")
async def auth_register(
    data: UserRegisterIn, response: Response,
    request: Request, db: Session = Depends(get_db),
) -> dict[str, Any]:
    return await auth_service.register_user(data, request, response, db)


@router.post("/login/password")
async def auth_login_password(
    data: LoginPasswordIn, response: Response,
    request: Request, db: Session = Depends(get_db),
) -> dict[str, Any]:
    return await auth_service.login_password(data, response, request, db)


@router.post("/login/oauth")
async def auth_login_oauth(
    data: OAuthLoginIn, response: Response,
    request: Request, db: Session = Depends(get_db),
) -> dict[str, Any]:
    return await auth_service.login_oauth(data, response, request, db)


@router.post("/login/otp/request")
async def auth_login_otp_request(data: OTPRequestIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    return await auth_service.otp_request(data, db)


@router.post("/login/otp/verify")
async def auth_login_otp_verify(
    data: OTPVerifyIn, response: Response,
    request: Request, db: Session = Depends(get_db),
) -> dict[str, Any]:
    return await auth_service.otp_verify(data, response, request, db)


@router.post("/refresh")
async def auth_refresh(
    response: Response,
    refresh_token_cookie: str | None = Cookie(default=None, alias="refresh_token"),
    refresh_token_body: str | None = Body(default=None, embed=True),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Rotate the refresh token and issue a new access token.

    Accepts the refresh token from either the HttpOnly cookie (preferred) or
    the request body (for non-cookie clients). Returns the new session id and
    expiry, plus sets the new cookies.
    """
    value = refresh_token_cookie or refresh_token_body
    if not value:
        raise HTTPException(status_code=401, detail="缺少 refresh token")
    return auth_service.refresh_session(db, response, value)


@router.post("/logout")
async def auth_logout(
    response: Response,
    revoke_all: bool = False,
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    current_session_id: str | None = None
    if access_token_cookie:
        try:
            payload = decode_access_token(access_token_cookie)
            current_session_id = payload.get("sid")
        except Exception:
            current_session_id = None
    return auth_service.logout(
        response,
        db,
        user,
        current_session_id=current_session_id,
        revoke_all=revoke_all,
    )


@router.get("/session")
async def auth_session(
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    return auth_service.get_session(user, db)


@router.get("/sessions")
async def auth_sessions(
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List active sessions for the current user (for a "devices" view)."""
    user = get_current_user(db, access_token_cookie, authorization)
    sessions = refresh_tokens.list_active_sessions(db, user.id)
    return {"sessions": sessions}


@router.delete("/sessions/{session_id}")
async def auth_revoke_session(
    session_id: str,
    response: Response,
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Revoke a specific session by id."""
    user = get_current_user(db, access_token_cookie, authorization)
    refresh_tokens.revoke_session(db, session_id)
    db.commit()
    return {"status": "ok", "revoked": session_id}


@router.post("/password/reset/request")
async def auth_password_reset_request(data: PasswordResetRequestIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    return await auth_service.password_reset_request(data, db)


@router.post("/password/reset/confirm")
async def auth_password_reset_confirm(data: PasswordResetConfirmIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    return await auth_service.password_reset_confirm(data, db)
