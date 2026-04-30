import hashlib
import hmac
import time
from datetime import timedelta
from typing import Any

import httpx
from fastapi import HTTPException, Request, Response
from loguru import logger
from sqlalchemy.orm import Session

from server.core.config import OTP_EXPIRES_MINUTES, PASSWORD_RESET_EXPIRES_MINUTES, OTP_VERIFY_MAX_ATTEMPTS
from server.core.database import create_log
from server.core.security import set_access_cookie, _issue_token_for_user, _safe_decrypt, _mask_key
from server.core.state import app_state
from server.core.utils import _sanitize_for_log
from server.mailer import send_otp_email, send_reset_email
from server.models.schemas import LoginPasswordIn, OAuthLoginIn, OTPRequestIn, OTPVerifyIn, PasswordResetConfirmIn, PasswordResetRequestIn, UserRegisterIn
from server.models_db import AuthChallenge, User
from server.security_utils import hash_password, verify_password, random_otp


async def register_user(data: UserRegisterIn, request: Request, db: Session) -> dict[str, Any]:
    from server.core.utils import _get_client_ip
    from server.core.config import REGISTER_RATE_LIMIT_WINDOW, REGISTER_RATE_LIMIT_MAX

    client_ip = _get_client_ip(request)
    async with app_state.rate_limit.register_lock:
        if not app_state.rate_limit._check_rate_limit(app_state.rate_limit.register_attempts, client_ip, REGISTER_RATE_LIMIT_WINDOW, REGISTER_RATE_LIMIT_MAX):
            raise HTTPException(status_code=429, detail="注册尝试过于频繁，请1小时后再试")

    existing = db.query(User).filter(User.email == data.email.lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="邮箱已注册")

    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        display_name=data.display_name,
        auth_provider="password",
        provider_user_id=None,
        encrypted_api_key=None,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = _issue_token_for_user(user)
    set_access_cookie(Response(), token)

    from server.services.user_service import get_or_create_user_config
    config = get_or_create_user_config(db, user.id)
    create_log(db, user_id=user.id, level="info", action="register", detail="password register")

    from server.core.llm_utils import choose_provider
    provider = choose_provider(getattr(config, "ai_provider", None), config.model, config.base_url)
    payload = {
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "auth_provider": user.auth_provider,
        },
        "config": {
            "ai_provider": provider,
            "model": config.model,
            "base_url": config.base_url,
            "timeout_seconds": config.timeout_seconds,
            "alert_email_enabled": config.alert_email_enabled,
            "alert_voice_enabled": config.alert_voice_enabled,
            "ui_theme": config.ui_theme,
            "ui_density": config.ui_density,
            "has_api_key": bool(_safe_decrypt(user.encrypted_api_key)),
            "api_key_masked": _mask_key(_safe_decrypt(user.encrypted_api_key)),
        },
    }
    if token:
        payload["access_token"] = token
    return payload


async def login_password(data: LoginPasswordIn, response: Response, db: Session) -> dict[str, Any]:
    if not await app_state.rate_limit.check_login_limit(data.email):
        raise HTTPException(status_code=429, detail="登录尝试过于频繁，请5分钟后再试")

    user = db.query(User).filter(User.email == data.email.lower(), User.is_active.is_(True)).first()
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    token = _issue_token_for_user(user)
    set_access_cookie(response, token)

    from server.services.user_service import get_or_create_user_config
    config = get_or_create_user_config(db, user.id)
    create_log(db, user_id=user.id, level="info", action="login_password", detail="password login")

    from server.core.llm_utils import choose_provider
    provider = choose_provider(getattr(config, "ai_provider", None), config.model, config.base_url)
    payload = {
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "auth_provider": user.auth_provider,
        },
        "config": {
            "ai_provider": provider,
            "model": config.model,
            "base_url": config.base_url,
            "timeout_seconds": config.timeout_seconds,
            "alert_email_enabled": config.alert_email_enabled,
            "alert_voice_enabled": config.alert_voice_enabled,
            "ui_theme": config.ui_theme,
            "ui_density": config.ui_density,
            "has_api_key": bool(_safe_decrypt(user.encrypted_api_key)),
            "api_key_masked": _mask_key(_safe_decrypt(user.encrypted_api_key)),
        },
    }
    if token:
        payload["access_token"] = token
    return payload


async def _verify_google_token(id_token: str) -> dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": id_token},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get("email_verified") != "true" and data.get("email_verified") is not True:
                return None
            return {"email": data.get("email", "").lower(), "sub": data.get("sub", ""), "name": data.get("name")}
    except Exception:
        return None


async def _verify_github_token(access_token: str) -> dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_token}", "User-Agent": "AI-CyberSentinel"},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            email = data.get("email") or ""
            emails_resp = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"Bearer {access_token}", "User-Agent": "AI-CyberSentinel"},
            )
            if emails_resp.status_code == 200:
                for e in emails_resp.json():
                    if e.get("primary") and e.get("verified"):
                        email = e.get("email", email)
            return {"email": email.lower(), "sub": str(data.get("id", "")), "name": data.get("name") or data.get("login")}
    except Exception:
        return None


async def login_oauth(data: OAuthLoginIn, response: Response, request: Request, db: Session) -> dict[str, Any]:
    from server.core.utils import _get_client_ip
    from server.core.config import REGISTER_RATE_LIMIT_WINDOW, REGISTER_RATE_LIMIT_MAX

    client_ip = _get_client_ip(request)
    async with app_state.rate_limit.register_lock:
        if not app_state.rate_limit._check_rate_limit(app_state.rate_limit.register_attempts, client_ip, REGISTER_RATE_LIMIT_WINDOW, REGISTER_RATE_LIMIT_MAX):
            raise HTTPException(status_code=429, detail="注册尝试过于频繁，请稍后再试")

    if not data.provider_user_id or len(data.provider_user_id) < 2:
        raise HTTPException(status_code=400, detail="OAuth 身份验证信息无效")

    verified: dict[str, Any] | None = None
    if data.provider == "google":
        verified = await _verify_google_token(data.id_token)
    elif data.provider == "github":
        verified = await _verify_github_token(data.id_token)

    if not verified:
        raise HTTPException(status_code=401, detail="OAuth 身份验证失败，请重新登录")

    if verified["email"].lower() != data.email.lower():
        raise HTTPException(status_code=401, detail="OAuth 邮箱与请求不匹配")

    if str(verified["sub"]) != str(data.provider_user_id):
        raise HTTPException(status_code=401, detail="OAuth 用户标识与请求不匹配")

    user = db.query(User).filter(User.email == data.email.lower()).first()
    if user is None:
        logger.warning(
            "OAuth auto-register: provider={} email={} ip={} — "
            "ensure OAuth callback verification is enabled on the frontend",
            data.provider, _sanitize_for_log(data.email), client_ip,
        )
        user = User(
            email=data.email.lower(),
            password_hash=None,
            display_name=data.display_name,
            auth_provider=data.provider,
            provider_user_id=data.provider_user_id,
            encrypted_api_key=None,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if user.auth_provider and user.auth_provider != data.provider:
            raise HTTPException(status_code=409, detail="该邮箱已使用其他方式注册")
        user.auth_provider = data.provider
        user.provider_user_id = data.provider_user_id
        if data.display_name:
            user.display_name = data.display_name
        db.add(user)
        db.commit()
        db.refresh(user)

    token = _issue_token_for_user(user)
    set_access_cookie(response, token)

    from server.services.user_service import get_or_create_user_config
    config = get_or_create_user_config(db, user.id)
    create_log(db, user_id=user.id, level="info", action="login_oauth", detail=f"oauth login {data.provider}")

    from server.core.llm_utils import choose_provider
    provider = choose_provider(getattr(config, "ai_provider", None), config.model, config.base_url)
    payload = {
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "auth_provider": user.auth_provider,
        },
        "config": {
            "ai_provider": provider,
            "model": config.model,
            "base_url": config.base_url,
            "timeout_seconds": config.timeout_seconds,
            "alert_email_enabled": config.alert_email_enabled,
            "alert_voice_enabled": config.alert_voice_enabled,
            "ui_theme": config.ui_theme,
            "ui_density": config.ui_density,
            "has_api_key": bool(_safe_decrypt(user.encrypted_api_key)),
            "api_key_masked": _mask_key(_safe_decrypt(user.encrypted_api_key)),
        },
    }
    if token:
        payload["access_token"] = token
    return payload


async def otp_request(data: OTPRequestIn, db: Session) -> dict[str, Any]:
    if not await app_state.rate_limit.check_otp_limit(data.email):
        raise HTTPException(status_code=429, detail="验证码请求过于频繁，请10分钟后再试")

    async with app_state.rate_limit.otp_verify_lock:
        app_state.rate_limit.otp_verify_failures.pop(data.email.lower(), None)

    user = db.query(User).filter(User.email == data.email.lower(), User.is_active.is_(True)).first()
    code = _issue_challenge(db, data.email.lower(), "otp", user.id if user else None)
    try:
        await send_otp_email(data.email.lower(), code)
    except Exception as exc:
        logger.warning("send otp email failed: {}", exc)
        raise HTTPException(status_code=500, detail="邮件发送失败，请检查 SMTP 配置") from exc
    create_log(db, user_id=user.id if user else None, level="info", action="otp_request", detail="otp requested")
    return {"status": "ok", "message": "验证码已发送"}


async def otp_verify(data: OTPVerifyIn, response: Response, db: Session) -> dict[str, Any]:
    email_key = data.email.lower()
    async with app_state.rate_limit.otp_verify_lock:
        failures = app_state.rate_limit.otp_verify_failures.get(email_key, 0)
        if failures >= OTP_VERIFY_MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail="验证码错误次数过多，请重新获取验证码")

    user = db.query(User).filter(User.email == email_key, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在，请先注册")

    try:
        _consume_valid_challenge(db, email_key, "otp", data.code)
    except HTTPException:
        async with app_state.rate_limit.otp_verify_lock:
            app_state.rate_limit.otp_verify_failures[email_key] = app_state.rate_limit.otp_verify_failures.get(email_key, 0) + 1
        raise

    async with app_state.rate_limit.otp_verify_lock:
        app_state.rate_limit.otp_verify_failures.pop(email_key, None)

    token = _issue_token_for_user(user)
    set_access_cookie(response, token)

    from server.services.user_service import get_or_create_user_config
    config = get_or_create_user_config(db, user.id)
    create_log(db, user_id=user.id, level="info", action="login_otp", detail="otp login")

    from server.core.llm_utils import choose_provider
    provider = choose_provider(getattr(config, "ai_provider", None), config.model, config.base_url)
    payload = {
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "auth_provider": user.auth_provider,
        },
        "config": {
            "ai_provider": provider,
            "model": config.model,
            "base_url": config.base_url,
            "timeout_seconds": config.timeout_seconds,
            "alert_email_enabled": config.alert_email_enabled,
            "alert_voice_enabled": config.alert_voice_enabled,
            "ui_theme": config.ui_theme,
            "ui_density": config.ui_density,
            "has_api_key": bool(_safe_decrypt(user.encrypted_api_key)),
            "api_key_masked": _mask_key(_safe_decrypt(user.encrypted_api_key)),
        },
    }
    if token:
        payload["access_token"] = token
    return payload


async def password_reset_request(data: PasswordResetRequestIn, db: Session) -> dict[str, Any]:
    if not await app_state.rate_limit.check_otp_limit(data.email):
        raise HTTPException(status_code=429, detail="请求过于频繁，请10分钟后再试")

    async with app_state.rate_limit.otp_verify_lock:
        app_state.rate_limit.otp_verify_failures.pop(data.email.lower(), None)

    user = db.query(User).filter(User.email == data.email.lower(), User.is_active.is_(True)).first()
    if not user:
        return {"status": "ok", "message": "如果邮箱存在，验证码已发送"}

    code = _issue_challenge(db, data.email.lower(), "reset", user.id)
    try:
        await send_reset_email(data.email.lower(), code)
    except Exception as exc:
        logger.warning("send reset email failed: {}", exc)
        raise HTTPException(status_code=500, detail="邮件发送失败，请检查 SMTP 配置") from exc
    create_log(db, user_id=user.id, level="info", action="password_reset_request", detail="reset requested")
    return {"status": "ok", "message": "如果邮箱存在，验证码已发送"}


async def password_reset_confirm(data: PasswordResetConfirmIn, db: Session) -> dict[str, Any]:
    if not await app_state.rate_limit.check_otp_limit(data.email):
        raise HTTPException(status_code=429, detail="请求过于频繁，请10分钟后再试")

    email_key = data.email.lower()
    async with app_state.rate_limit.otp_verify_lock:
        failures = app_state.rate_limit.otp_verify_failures.get(email_key, 0)
        if failures >= OTP_VERIFY_MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail="验证码错误次数过多，请重新获取验证码")

    user = db.query(User).filter(User.email == email_key, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    try:
        _consume_valid_challenge(db, email_key, "reset", data.code)
    except HTTPException:
        async with app_state.rate_limit.otp_verify_lock:
            app_state.rate_limit.otp_verify_failures[email_key] = app_state.rate_limit.otp_verify_failures.get(email_key, 0) + 1
        raise

    async with app_state.rate_limit.otp_verify_lock:
        app_state.rate_limit.otp_verify_failures.pop(email_key, None)

    user.password_hash = hash_password(data.new_password)
    from server.core.utils import _now
    user.password_changed_at = _now()
    user.token_version = user.token_version + 1
    db.add(user)
    db.commit()
    create_log(db, user_id=user.id, level="info", action="password_reset_confirm", detail="password reset")
    return {"status": "ok", "message": "密码已更新"}


def logout(response: Response) -> dict[str, Any]:
    from server.core.security import clear_access_cookie
    clear_access_cookie(response)
    return {"status": "ok"}


def get_session(user: User, db: Session) -> dict[str, Any]:
    from server.services.user_service import get_or_create_user_config
    config = get_or_create_user_config(db, user.id)

    from server.core.llm_utils import choose_provider
    provider = choose_provider(getattr(config, "ai_provider", None), config.model, config.base_url)
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "auth_provider": user.auth_provider,
        },
        "config": {
            "ai_provider": provider,
            "model": config.model,
            "base_url": config.base_url,
            "timeout_seconds": config.timeout_seconds,
            "alert_email_enabled": config.alert_email_enabled,
            "alert_voice_enabled": config.alert_voice_enabled,
            "ui_theme": config.ui_theme,
            "ui_density": config.ui_density,
            "has_api_key": bool(_safe_decrypt(user.encrypted_api_key)),
            "api_key_masked": _mask_key(_safe_decrypt(user.encrypted_api_key)),
        },
    }


def _challenge_hash_material(email: str, challenge_type: str, code: str) -> str:
    return hashlib.sha256(f"{email.lower()}:{challenge_type}:{code}".encode("utf-8")).hexdigest()


def _issue_challenge(db: Session, email: str, challenge_type: str, user_id: int | None) -> str:
    code = random_otp(6)
    code_hash = _challenge_hash_material(email, challenge_type, code)
    from server.core.utils import _now
    expires_at = _now() + timedelta(minutes=OTP_EXPIRES_MINUTES if challenge_type == "otp" else PASSWORD_RESET_EXPIRES_MINUTES)
    challenge = AuthChallenge(
        user_id=user_id,
        email=email.lower(),
        challenge_type=challenge_type,
        code_hash=code_hash,
        expires_at=expires_at,
        consumed_at=None,
        metadata_json=None,
    )
    db.add(challenge)
    db.commit()
    return code


def _consume_valid_challenge(db: Session, email: str, challenge_type: str, code: str) -> AuthChallenge:
    challenge = (
        db.query(AuthChallenge)
        .filter(
            AuthChallenge.email == email.lower(),
            AuthChallenge.challenge_type == challenge_type,
            AuthChallenge.consumed_at.is_(None),
        )
        .order_by(AuthChallenge.created_at.desc())
        .first()
    )
    from server.core.utils import _now
    if not challenge:
        raise HTTPException(status_code=400, detail="验证码不存在，请先获取验证码")
    if challenge.expires_at < _now():
        raise HTTPException(status_code=400, detail="验证码已过期")

    expected = _challenge_hash_material(email, challenge_type, code)
    if not hmac.compare_digest(expected, challenge.code_hash):
        raise HTTPException(status_code=400, detail="验证码错误")

    challenge.consumed_at = _now()
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge
