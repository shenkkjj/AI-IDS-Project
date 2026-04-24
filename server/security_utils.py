from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timedelta
from typing import Any

from cryptography.fernet import Fernet
from fastapi import HTTPException
from jose import jwt
from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_fernet_key() -> str:
    key = os.getenv("APP_FERNET_KEY", "").strip()
    if key:
        return key

    secret = os.getenv("APP_SECRET", "dev-secret-change-me")
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8")


fernet = Fernet(get_fernet_key().encode("utf-8"))


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def encrypt_api_key(value: str | None) -> str | None:
    if not value:
        return None
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_api_key(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Stored API key cannot be decrypted") from exc


def hash_otp_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def verify_otp_code(code: str, code_hash: str) -> bool:
    return hash_otp_code(code) == code_hash


def issue_access_token(subject: str, expires_minutes: int = 60 * 24 * 7) -> str:
    secret = os.getenv("APP_SECRET", "dev-secret-change-me")
    algorithm = os.getenv("APP_JWT_ALG", "HS256")
    now = datetime.utcnow()
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    secret = os.getenv("APP_SECRET", "dev-secret-change-me")
    algorithm = os.getenv("APP_JWT_ALG", "HS256")
    return jwt.decode(token, secret, algorithms=[algorithm])


def random_otp(length: int = 6) -> str:
    import random

    return "".join(str(random.randint(0, 9)) for _ in range(length))
