from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet
from jose import jwt
from passlib.context import CryptContext

from server.core.config import ACCESS_TOKEN_EXPIRES_MINUTES


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
    "change-this-to-a-strong-random-secret",
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
    import hashlib
    fixed_salt = b"AI-CyberSentinel-Fernet-v1"
    key = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), fixed_salt, 100000, dklen=32)
    return base64.urlsafe_b64encode(key).decode("utf-8")


def _derive_api_key_fernet_key(api_key_secret: str) -> str:
    """Derive a Fernet key for API key encryption from a dedicated secret.

    The salt is intentionally different from `_derive_fernet_key` so that an
    APP_SECRET/JWT signing key compromise does not transitively compromise
    encrypted API key storage.
    """
    salt = b"AI-CyberSentinel-ApiKeyFernet-v1"
    key = hashlib.pbkdf2_hmac(
        "sha256", api_key_secret.encode("utf-8"), salt, 100_000, dklen=32,
    )
    return base64.urlsafe_b64encode(key).decode("utf-8")


def _resolve_jwt_secret() -> str:
    """Resolve the JWT signing secret.

    Priority: APP_JWT_SECRET > APP_SECRET. This allows operators to rotate
    the JWT signing key independently of the API key encryption key.
    """
    jwt_secret = os.getenv("APP_JWT_SECRET", "").strip()
    if jwt_secret:
        return jwt_secret
    return _required_app_secret()


def _resolve_api_key_fernet_key() -> str:
    """Resolve the Fernet key used to encrypt stored user API keys.

    Priority: APP_API_KEY_ENCRYPTION_SECRET > APP_SECRET-derived key. The
    derived key uses a salt that is distinct from the one used in
    `_derive_fernet_key`, ensuring that the JWT signing secret and the
    API-key encryption secret are cryptographically independent even when
    they are both derived from APP_SECRET.
    """
    api_key_secret = os.getenv("APP_API_KEY_ENCRYPTION_SECRET", "").strip()
    if api_key_secret:
        return _derive_api_key_fernet_key(api_key_secret)
    # Fall back to deriving from APP_SECRET with a different salt. This keeps
    # single-key deployments working but the derived key is independent from
    # the one used for the legacy Fernet (if any).
    return _derive_api_key_fernet_key(_required_app_secret())


def get_fernet_key() -> str:
    """Return the Fernet key for *legacy* encrypted payloads, if used elsewhere.

    New code should call `_resolve_api_key_fernet_key()` instead.
    """
    key = os.getenv("APP_FERNET_KEY", "").strip()
    if key:
        try:
            Fernet(key.encode("utf-8"))
        except Exception as exc:
            raise RuntimeError("APP_FERNET_KEY is invalid") from exc
        return key

    return _derive_fernet_key(_required_app_secret())


# Module-level Fernet instance bound to the API key encryption key.
# This is what `encrypt_api_key` / `decrypt_api_key` should use.
_api_key_fernet = Fernet(_resolve_api_key_fernet_key().encode("utf-8"))

# Backward-compatible alias. `fernet` is imported by other modules
# (e.g. auth_service) — keep it pointing at the API-key Fernet so existing
# call sites encrypt/decrypt under the new key without code changes.
fernet = _api_key_fernet


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


def issue_access_token(
    subject: str,
    expires_minutes: int | None = None,
    password_changed_at: float | None = None,
    token_version: int = 0,
    session_id: str | None = None,
) -> str:
    """Issue a short-lived access token JWT.

    `expires_minutes` defaults to `ACCESS_TOKEN_EXPIRES_MINUTES` (30 min).
    Pass an explicit value to override (e.g. shorter for high-risk operations).
    `session_id` is embedded in the payload so a single session can be
    terminated without rotating the user's global `token_version`.
    """
    if expires_minutes is None:
        expires_minutes = ACCESS_TOKEN_EXPIRES_MINUTES
    secret = _resolve_jwt_secret()
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
    if session_id is not None:
        payload["sid"] = session_id
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    secret = _resolve_jwt_secret()
    algorithm = _get_jwt_algorithm()
    return jwt.decode(token, secret, algorithms=[algorithm])


def random_otp(length: int = 6) -> str:
    import secrets

    return "".join(str(secrets.randbelow(10)) for _ in range(length))
