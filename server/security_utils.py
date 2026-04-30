from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet
from jose import jwt
from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALLOWED_JWT_ALGORITHMS = {"HS256", "HS384", "HS512"}

_CACHED_JWT_ALGORITHM: str | None = None


def _get_jwt_algorithm() -> str:
    global _CACHED_JWT_ALGORITHM
    if _CACHED_JWT_ALGORITHM is not None:
        return _CACHED_JWT_ALGORITHM
    algorithm = os.getenv("APP_JWT_ALG", "HS256")
    if algorithm not in ALLOWED_JWT_ALGORITHMS:
        raise ValueError(f"APP_JWT_ALG must be one of {ALLOWED_JWT_ALGORITHMS}")
    _CACHED_JWT_ALGORITHM = algorithm
    return algorithm

WEAK_APP_SECRETS = {
    "dev-secret-change-me",
    "change-me-to-a-long-random-secret",
    "changeme",
    "change-me",
    "default",
    "secret",
}


def _required_app_secret() -> str:
    secret = os.getenv("APP_SECRET", "").strip()
    if not secret:
        raise RuntimeError("APP_SECRET must be configured")
    if secret.lower() in WEAK_APP_SECRETS:
        app_env = os.getenv("APP_ENV", "development").strip().lower()
        if app_env in ("prod", "production"):
            raise RuntimeError("APP_SECRET must be configured with a strong non-default value in production")
        import warnings
        warnings.warn("APP_SECRET uses a weak default value — change it before deploying to production", stacklevel=2)
    return secret


def _derive_fernet_key(secret: str) -> str:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8")


def get_fernet_key() -> str:
    key = os.getenv("APP_FERNET_KEY", "").strip()
    if key:
        try:
            Fernet(key.encode("utf-8"))
        except Exception as exc:
            raise RuntimeError("APP_FERNET_KEY is invalid") from exc
        return key

    return _derive_fernet_key(_required_app_secret())


fernet = Fernet(get_fernet_key().encode("utf-8"))


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def encrypt_api_key(value: str | None) -> str | None:
    if not value:
        return None
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


class DecryptionError(Exception):
    pass


def decrypt_api_key(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        raise DecryptionError("存储的配置无法读取，请重新设置") from exc


def hash_otp_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def verify_otp_code(code: str, code_hash: str) -> bool:
    import hmac as _hmac
    return _hmac.compare_digest(hash_otp_code(code), code_hash)


def issue_access_token(subject: str, expires_minutes: int = 60 * 24 * 7, password_changed_at: float | None = None, token_version: int = 0) -> str:
    secret = _required_app_secret()
    algorithm = _get_jwt_algorithm()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
        "tv": token_version,
    }
    if password_changed_at is not None:
        payload["pwd_iat"] = int(password_changed_at)
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    secret = _required_app_secret()
    algorithm = _get_jwt_algorithm()
    return jwt.decode(token, secret, algorithms=[algorithm])


def random_otp(length: int = 6) -> str:
    import secrets

    return "".join(str(secrets.randbelow(10)) for _ in range(length))
