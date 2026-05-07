from typing import Any

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from server.core.database import get_db, create_log
from server.core.security import get_current_user
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
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return await auth_service.login_password(data, response, db)


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
async def auth_login_otp_verify(data: OTPVerifyIn, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    return await auth_service.otp_verify(data, response, db)


@router.post("/password/reset/request")
async def auth_password_reset_request(data: PasswordResetRequestIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    return await auth_service.password_reset_request(data, db)


@router.post("/password/reset/confirm")
async def auth_password_reset_confirm(data: PasswordResetConfirmIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    return await auth_service.password_reset_confirm(data, db)


@router.post("/logout")
async def auth_logout(
    response: Response,
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    return auth_service.logout(response, db, user)


@router.get("/session")
async def auth_session(
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    return auth_service.get_session(user, db)
