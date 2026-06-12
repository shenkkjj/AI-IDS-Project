import hashlib
import hmac
from datetime import timedelta
from typing import Any

import httpx
from fastapi import HTTPException, Request, Response
from loguru import logger
from sqlalchemy.orm import Session

from server.core.config import (
    OTP_EXPIRES_MINUTES,
    PASSWORD_RESET_EXPIRES_MINUTES,
    OTP_VERIFY_MAX_ATTEMPTS,
    REFRESH_TOKEN_EXPIRES_DAYS,
)
from server.core.database import create_log
from server.core.exceptions import (
    AuthException,
    TotpRequiredException,
)
from server.core import refresh_tokens
from server.core.security import (
    set_access_cookie,
    set_refresh_cookie,
    _issue_token_for_user,
    _safe_decrypt,
    _mask_key,
)
from server.core.state import app_state
from server.core.utils import _sanitize_for_log
from server.mailer import send_otp_email, send_reset_email
from server.models.schemas import (
    LoginPasswordIn, OAuthLoginIn, OTPRequestIn, OTPVerifyIn,
    PasswordResetConfirmIn, PasswordResetRequestIn, UserRegisterIn,
)
from server.models_db import AuthChallenge, User
from server.security_utils import hash_password, verify_password, random_otp


def _build_auth_payload(user: User, config: Any, token: str | None = None) -> dict[str, Any]:
    from server.core.llm_utils import choose_provider
    provider = choose_provider(getattr(config, "ai_provider", None), config.model, config.base_url)
    payload: dict[str, Any] = {
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "auth_provider": user.auth_provider,
            "totp_enabled": bool(user.totp_enabled),
        },
        "config": {
            "ai_provider": provider,
            "model": config.model,
            "base_url": config.base_url,
            "timeout_seconds": config.timeout_seconds,
            "alert_email_enabled": config.alert_email_enabled,
            "alert_voice_enabled": config.alert_voice_enabled,
            "webhook_url": config.webhook_url,
            "webhook_type": config.webhook_type,
            "ui_theme": config.ui_theme,
            "ui_density": config.ui_density,
            "has_api_key": bool(_safe_decrypt(user.encrypted_api_key)),
            "api_key_masked": _mask_key(_safe_decrypt(user.encrypted_api_key)),
        },
    }
    if token:
        payload["access_token"] = token
    return payload


def _enforce_totp_or_raise(user: User, totp_code: str | None) -> None:
    """If the user has TOTP enabled, require a valid code. Otherwise no-op.

    Raises:
        TotpRequiredException: when TOTP is enabled but the caller did not
            supply a `totp_code`. The global exception handler converts this
            into a 401 response with `extra.code = "totp_required"` so the
            frontend can switch to the TOTP input UI.
        AuthException: when a code was supplied but did not match.
    """
    if not user.totp_enabled:
        return
    if not totp_code:
        raise TotpRequiredException()
    from server.services.totp_service import verify_totp
    if not verify_totp(user.totp_secret, totp_code):
        raise AuthException("TOTP 验证码错误")


def _issue_session(
    db: Session,
    user: User,
    response: Response,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> dict[str, str]:
    """Mint a refresh-token row, then issue an access-token bound to it.

    Returns `{"session_id": ..., "access_token": ...}` so the caller can
    include both in the response body when the client wants explicit
    session management (the cookies are set for browser flows regardless).
    """
    refresh_pair = refresh_tokens.issue_refresh_token(
        db,
        user,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    access_token = _issue_token_for_user(user, session_id=refresh_pair["session_id"])
    set_access_cookie(response, access_token)
    set_refresh_cookie(
        response,
        refresh_pair["value"],
        max_age_seconds=REFRESH_TOKEN_EXPIRES_DAYS * 24 * 3600,
    )
    return {
        "session_id": refresh_pair["session_id"],
        "access_token": access_token,
    }


def refresh_session(
    db: Session,
    response: Response,
    refresh_token_value: str,
) -> dict[str, Any]:
    """Atomically rotate a refresh token and issue a new access token.

    Raises AuthException if the token is unknown, expired, or revoked.
    """
    result = refresh_tokens.consume_refresh_token(db, refresh_token_value)
    if result is None:
        raise AuthException("Refresh token 无效或已过期")
    consumed, new_pair = result
    user = db.query(User).filter(User.id == consumed.user_id).one()
    access_token = _issue_token_for_user(user, session_id=new_pair["session_id"])
    set_access_cookie(response, access_token)
    set_refresh_cookie(
        response,
        new_pair["value"],
        max_age_seconds=REFRESH_TOKEN_EXPIRES_DAYS * 24 * 3600,
    )
    return {"session_id": new_pair["session_id"], "expires_at": new_pair["expires_at"]}


async def register_user(data: UserRegisterIn, request: Request, response: Response, db: Session) -> dict[str, Any]:
    from server.core.utils import _get_client_ip

    client_ip = _get_client_ip(request)
    if not await app_state.rate_limit.check_register_limit(client_ip):
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

    user_agent = request.headers.get("user-agent") if request else None
    _issue_session(db, user, response, user_agent=user_agent, ip_address=client_ip)
    db.commit()

    from server.services.user_service import get_or_create_user_config
    config = get_or_create_user_config(db, user.id)
    create_log(db, user_id=user.id, level="info", action="register", detail="password register")

    # access_token is delivered via cookie; payload can still expose it for
    # clients that prefer header-based access (e.g. the NextAuth bridge).
    from server.core.config import ACCESS_TOKEN_EXPIRES_MINUTES
    from server.security_utils import issue_access_token
    from datetime import timezone
    pwd_ts = user.password_changed_at.replace(tzinfo=timezone.utc).timestamp() if user.password_changed_at else None
    token = issue_access_token(
        str(user.id),
        password_changed_at=pwd_ts,
        token_version=user.token_version,
    )
    return _build_auth_payload(user, config, token)


async def login_password(data: LoginPasswordIn, response: Response, request: Request, db: Session) -> dict[str, Any]:
    if not await app_state.rate_limit.check_login_limit(data.email):
        raise HTTPException(status_code=429, detail="登录尝试过于频繁，请5分钟后再试")

    user = db.query(User).filter(User.email == data.email.lower(), User.is_active.is_(True)).first()
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    # Activate MFA: require TOTP code if the user has enabled it.
    _enforce_totp_or_raise(user, data.totp_code)

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent") if request else None
    session = _issue_session(db, user, response, user_agent=user_agent, ip_address=client_ip)
    db.commit()

    from server.services.user_service import get_or_create_user_config
    config = get_or_create_user_config(db, user.id)
    create_log(db, user_id=user.id, level="info", action="login_password", detail="password login")

    return _build_auth_payload(user, config, session["access_token"])


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
            return {
                "email": email.lower(),
                "sub": str(data.get("id", "")),
                "name": data.get("name") or data.get("login"),
            }
    except Exception:
        return None


async def login_oauth(data: OAuthLoginIn, response: Response, request: Request, db: Session) -> dict[str, Any]:
    from server.core.utils import _get_client_ip

    client_ip = _get_client_ip(request)
    if not await app_state.rate_limit.check_register_limit(client_ip):
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
        import os
        oauth_auto_register = os.getenv("OAUTH_AUTO_REGISTER", "false").strip().lower() in {"1", "true", "yes", "on"}
        oauth_allowed_domains = os.getenv("OAUTH_ALLOWED_DOMAINS", "").strip().lower()
        if not oauth_auto_register:
            logger.warning(
                "OAuth login rejected (auto-register disabled): provider={} email={} ip={}",
                data.provider, _sanitize_for_log(data.email), client_ip,
            )
            raise HTTPException(status_code=403, detail="该邮箱未注册，请联系管理员开通账号")

        if oauth_allowed_domains:
            allowed_list = [d.strip() for d in oauth_allowed_domains.split(",") if d.strip()]
            email_domain = data.email.lower().split("@")[-1] if "@" in data.email.lower() else ""
            if email_domain not in allowed_list:
                logger.warning(
                    "OAuth login rejected (domain not allowed): provider={} email={} domain={} ip={}",
                    data.provider, _sanitize_for_log(data.email), email_domain, client_ip,
                )
                raise HTTPException(status_code=403, detail="该邮箱域名未在允许列表中，请联系管理员")

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

    # OAuth 登录同样受 TOTP 保护：用户若已启用 2FA，必须提供动态码。
    _enforce_totp_or_raise(user, data.totp_code)

    token = _issue_token_for_user(user)
    set_access_cookie(response, token)

    from server.services.user_service import get_or_create_user_config
    config = get_or_create_user_config(db, user.id)
    create_log(
        db, user_id=user.id, level="info", action="login_oauth",
        detail=f"oauth login {data.provider} from {client_ip}",
    )

    return _build_auth_payload(user, config, token)


async def otp_request(data: OTPRequestIn, db: Session) -> dict[str, Any]:
    if not await app_state.rate_limit.check_otp_limit(data.email):
        raise HTTPException(status_code=429, detail="验证码请求过于频繁，请10分钟后再试")

    async with app_state.rate_limit.otp_verify_lock:
        app_state.rate_limit.otp_verify_failures.pop(data.email.lower(), None)

    user = db.query(User).filter(User.email == data.email.lower(), User.is_active.is_(True)).first()
    code = _issue_challenge(db, data.email.lower(), "otp", user.id if user else None)

    import os
    mail_user = os.getenv("MAIL_USERNAME", "").strip()
    mail_pass = os.getenv("MAIL_PASSWORD", "").strip()
    mail_server = os.getenv("MAIL_SERVER", "").strip()
    mail_configured = bool(mail_user and mail_pass and mail_server and mail_server != "smtp.example.com")

    if mail_configured:
        try:
            await send_otp_email(data.email.lower(), code)
        except Exception as exc:
            logger.warning("send otp email failed: {}", exc)
            raise HTTPException(status_code=500, detail="邮件发送失败，请检查 SMTP 配置") from exc
        create_log(db, user_id=user.id if user else None, level="info", action="otp_request", detail="otp requested")
        return {"status": "ok", "message": "验证码已发送至邮箱"}
    else:
        raise HTTPException(status_code=500, detail="邮件服务未配置")


async def otp_verify(data: OTPVerifyIn, response: Response, request: Request, db: Session) -> dict[str, Any]:
    email_key = data.email.lower()
    async with app_state.rate_limit.otp_verify_lock:
        failures = app_state.rate_limit.otp_verify_failures.get(email_key, 0)
        if failures >= OTP_VERIFY_MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail="验证码错误次数过多，请重新获取验证码")

    user = db.query(User).filter(User.email == email_key, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=400, detail="验证码无效或已过期")

    try:
        _consume_valid_challenge(db, email_key, "otp", data.code)
    except HTTPException:
        async with app_state.rate_limit.otp_verify_lock:
            app_state.rate_limit.otp_verify_failures[email_key] = (
                app_state.rate_limit.otp_verify_failures.get(email_key, 0) + 1
            )
        raise

    async with app_state.rate_limit.otp_verify_lock:
        app_state.rate_limit.otp_verify_failures.pop(email_key, None)

    # OTP 登录流程同样受 TOTP 保护。
    _enforce_totp_or_raise(user, data.totp_code)

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent") if request else None
    _issue_session(db, user, response, user_agent=user_agent, ip_address=client_ip)
    db.commit()

    from server.services.user_service import get_or_create_user_config
    config = get_or_create_user_config(db, user.id)
    create_log(db, user_id=user.id, level="info", action="login_otp", detail="otp login")

    return _build_auth_payload(user, config, token)


async def password_reset_request(data: PasswordResetRequestIn, db: Session) -> dict[str, Any]:
    if not await app_state.rate_limit.check_otp_limit(data.email):
        raise HTTPException(status_code=429, detail="请求过于频繁，请10分钟后再试")

    async with app_state.rate_limit.otp_verify_lock:
        app_state.rate_limit.otp_verify_failures.pop(data.email.lower(), None)

    user = db.query(User).filter(User.email == data.email.lower(), User.is_active.is_(True)).first()

    code = _issue_challenge(db, data.email.lower(), "reset", user.id if user else None)

    import os
    mail_user = os.getenv("MAIL_USERNAME", "").strip()
    mail_pass = os.getenv("MAIL_PASSWORD", "").strip()
    mail_server = os.getenv("MAIL_SERVER", "").strip()
    mail_configured = bool(mail_user and mail_pass and mail_server and mail_server != "smtp.example.com")

    if mail_configured:
        try:
            await send_reset_email(data.email.lower(), code)
        except Exception as exc:
            logger.warning("send reset email failed: {}", exc)
            raise HTTPException(status_code=500, detail="邮件发送失败，请检查 SMTP 配置") from exc
        create_log(db, user_id=user.id, level="info", action="password_reset_request", detail="reset requested")
        return {"status": "ok", "message": "验证码已发送至邮箱"}
    else:
        raise HTTPException(status_code=500, detail="邮件服务未配置")


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
        raise HTTPException(status_code=400, detail="验证码无效或已过期")

    try:
        _consume_valid_challenge(db, email_key, "reset", data.code)
    except HTTPException:
        async with app_state.rate_limit.otp_verify_lock:
            app_state.rate_limit.otp_verify_failures[email_key] = (
                app_state.rate_limit.otp_verify_failures.get(email_key, 0) + 1
            )
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


def logout(
    response: Response,
    db: Session,
    user: User,
    *,
    current_session_id: str | None = None,
    revoke_all: bool = False,
) -> dict[str, Any]:
    """Log out the current session.

    - `revoke_all=False` (default): revoke only the current session, leave
      other devices logged in. Access token is invalidated because the
      session_id is no longer active.
    - `revoke_all=True`: revoke every active session for this user and bump
      the global token_version so all access tokens issued previously stop
      working. Use this on "log out everywhere" or password change.
    """
    from server.core.security import clear_access_cookie, clear_refresh_cookie

    if revoke_all:
        refresh_tokens.revoke_user_sessions(db, user.id)
        user.token_version = user.token_version + 1
    elif current_session_id is not None:
        refresh_tokens.revoke_session(db, current_session_id)
    else:
        # No session binding (e.g. legacy token); fall back to bumping
        # token_version so this token is invalidated.
        user.token_version = user.token_version + 1

    db.add(user)
    db.commit()
    clear_access_cookie(response)
    clear_refresh_cookie(response)
    create_log(db, user_id=user.id, level="info", action="logout", detail="user logged out")
    return {"status": "ok"}


def get_session(user: User, db: Session) -> dict[str, Any]:
    from server.services.user_service import get_or_create_user_config
    config = get_or_create_user_config(db, user.id)
    return _build_auth_payload(user, config)


def _challenge_hash_material(email: str, challenge_type: str, code: str) -> str:
    return hashlib.sha256(f"{email.lower()}:{challenge_type}:{code}".encode("utf-8")).hexdigest()


def _issue_challenge(db: Session, email: str, challenge_type: str, user_id: int | None) -> str:
    code = random_otp(6)
    code_hash = _challenge_hash_material(email, challenge_type, code)
    from server.core.utils import _now
    expires_at = _now() + timedelta(  # noqa: E501
        minutes=OTP_EXPIRES_MINUTES if challenge_type == "otp" else PASSWORD_RESET_EXPIRES_MINUTES
    )
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
