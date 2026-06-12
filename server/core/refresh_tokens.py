"""刷新令牌签发、轮换与撤销。

设计要点：
- access_token: 短期（默认 30 分钟），存于 HttpOnly Cookie。
- refresh_token: 长期（默认 7 天），单次使用（rotation）。
- 数据库只存 refresh_token 的 SHA-256 哈希值；泄露库不等于泄露令牌。
- `session_id` 嵌入 access_token 的 JWT 载荷，按 session 选择性撤销。
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from server.core.config import REFRESH_TOKEN_EXPIRES_DAYS
from server.models_db import RefreshToken, User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _new_session_id() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(24)).rstrip(b"=").decode("utf-8")


def _new_token_value() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("utf-8")


def _hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def issue_refresh_token(
    db: Session,
    user: User,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> dict[str, str]:
    """Create a new refresh token row and return its `value` and `session_id`.

    The caller is responsible for delivering the returned `value` to the
    client (cookie or response body). The DB only persists the hash.
    """
    session_id = _new_session_id()
    value = _new_token_value()
    expires_at = _utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRES_DAYS)
    record = RefreshToken(
        user_id=user.id,
        session_id=session_id,
        token_hash=_hash_token(value),
        expires_at=expires_at,
        revoked_at=None,
        replaced_by_id=None,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(record)
    db.flush()  # ensure record.id is populated for follow-up writes
    return {"value": value, "session_id": session_id, "expires_at": expires_at.isoformat()}


def consume_refresh_token(
    db: Session,
    value: str,
) -> tuple[RefreshToken, dict[str, str]] | None:
    """Atomically rotate a refresh token.

    Returns the consumed record plus the new (value, session_id) pair, or
    `None` if the token is unknown, expired or already revoked. The consumed
    record's `revoked_at` is set and `replaced_by_id` will be wired up by the
    caller after the new record has been flushed.
    """
    token_hash = _hash_token(value)
    record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .one_or_none()
    )
    if record is None:
        return None
    if record.revoked_at is not None:
        # Token reuse after revocation — likely theft. Revoke the entire
        # token family as a safety measure.
        revoke_user_sessions(db, record.user_id, except_session_id=None)
        return None
    if record.expires_at < _utcnow():
        record.revoked_at = _utcnow()
        db.add(record)
        db.flush()
        return None

    # Mint the replacement token (rotation).
    user = db.query(User).filter(User.id == record.user_id).one_or_none()
    if user is None:
        return None
    new_pair = issue_refresh_token(
        db,
        user,
        user_agent=record.user_agent,
        ip_address=record.ip_address,
    )
    record.revoked_at = _utcnow()
    db.add(record)
    db.flush()
    # Wire up the chain so we can trace rotations.
    new_record = (
        db.query(RefreshToken)
        .filter(RefreshToken.session_id == new_pair["session_id"])
        .one()
    )
    new_record.replaced_by_id = None  # terminal until next rotation
    record.replaced_by_id = new_record.id
    db.add(new_record)
    db.add(record)
    db.flush()
    return record, new_pair


def revoke_session(db: Session, session_id: str) -> bool:
    """Revoke a single refresh-token session by its id. Returns True if revoked."""
    record = (
        db.query(RefreshToken)
        .filter(RefreshToken.session_id == session_id, RefreshToken.revoked_at.is_(None))
        .one_or_none()
    )
    if record is None:
        return False
    record.revoked_at = _utcnow()
    db.add(record)
    db.flush()
    return True


def revoke_user_sessions(
    db: Session,
    user_id: int,
    *,
    except_session_id: str | None = None,
) -> int:
    """Revoke all active refresh-token sessions for a user.

    Used on password change, explicit "log out everywhere", and when a refresh
    token is reused after revocation. Pass `except_session_id` to skip a
    single session (e.g. the one currently rotating).
    """
    query = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked_at.is_(None),
    )
    if except_session_id is not None:
        query = query.filter(RefreshToken.session_id != except_session_id)
    count = 0
    now = _utcnow()
    for record in query.all():
        record.revoked_at = now
        db.add(record)
        count += 1
    db.flush()
    return count


def is_session_active(db: Session, session_id: str) -> bool:
    """Check whether a session (embedded in a JWT) still has a live refresh token.

    Called from `get_current_user` so that an admin-triggered logout on a
    single session takes effect on the next API call.
    """
    record = (
        db.query(RefreshToken)
        .filter(RefreshToken.session_id == session_id)
        .one_or_none()
    )
    if record is None:
        return False
    return record.revoked_at is None and record.expires_at > _utcnow()


def list_active_sessions(db: Session, user_id: int) -> list[dict[str, Any]]:
    """Return metadata for all live sessions of a user (for a "devices" view)."""
    now = _utcnow()
    records = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
        .order_by(RefreshToken.created_at.desc())
        .all()
    )
    return [
        {
            "session_id": r.session_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            "user_agent": r.user_agent,
            "ip_address": r.ip_address,
        }
        for r in records
    ]
