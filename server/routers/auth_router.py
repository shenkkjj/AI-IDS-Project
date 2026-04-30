from typing import Any

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from server.core.database import get_db
from server.core.security import get_current_user, require_auth_user
from server.models.schemas import LoginPasswordIn, OAuthLoginIn, OTPRequestIn, OTPVerifyIn, PasswordResetConfirmIn, PasswordResetRequestIn, UserRegisterIn
from server.models_db import User
from server.services import auth_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register")
async def auth_register(data: UserRegisterIn, response: Response, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    return await auth_service.register_user(data, request, db)


@router.post("/login/password")
async def auth_login_password(data: LoginPasswordIn, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    return await auth_service.login_password(data, response, db)


@router.post("/login/oauth")
async def auth_login_oauth(data: OAuthLoginIn, response: Response, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
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
async def auth_logout(response: Response) -> dict[str, Any]:
    return auth_service.logout(response)


@router.get("/session")
async def auth_session(
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    return auth_service.get_session(user, db)
