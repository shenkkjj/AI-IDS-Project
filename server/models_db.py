from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.db import Base, TimestampMixin


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    auth_provider: Mapped[str] = mapped_column(String(32), default="password", nullable=False)
    provider_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="analyst", nullable=False, index=True)
    # 双因素认证
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 登录安全
    login_notify_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Eager-loadable relationship to the per-user config. Used to avoid the
    # previous N+1 in the alert pipeline.
    config: Mapped["UserConfig | None"] = relationship(
        "UserConfig",
        primaryjoin="User.id == foreign(UserConfig.user_id)",
        uselist=False,
        viewonly=True,
    )


class UserConfig(Base, TimestampMixin):
    __tablename__ = "user_configs"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_configs_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ai_provider: Mapped[str] = mapped_column(String(24), default="openai", nullable=False)
    model: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    alert_email_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    alert_voice_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    webhook_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    webhook_type: Mapped[str] = mapped_column(String(16), default="generic", nullable=False)
    ui_theme: Mapped[str] = mapped_column(String(32), default="dark", nullable=False)
    ui_density: Mapped[str] = mapped_column(String(16), default="comfortable", nullable=False)


class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    level: Mapped[str] = mapped_column(String(16), default="info", nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class AuthChallenge(Base):
    __tablename__ = "auth_challenges"
    __table_args__ = (
        Index("ix_auth_challenges_email_type_consumed", "email", "challenge_type", "consumed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    challenge_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_action", "user_id", "action"),
        Index("ix_audit_logs_created_at", "created_at"),
        # SC-22: supports `get_stats` and any SOC query that aggregates
        # guardrail events by status within a time window. Leading column
        # is the most selective (`action='guardrail_check'`) so the
        # planner can use the index for both the WHERE filter and the
        # GROUP BY status sort.
        Index("ix_audit_logs_action_status_created", "action", "status", "created_at"),
        # SC-22: supports the "which user tried this attack" join from
        # the SOC dashboard — user_id, action, and time all in one
        # covering index, so a `WHERE user_id=? AND action=?
        # AND created_at >= ?` hits an index-only scan.
        Index("ix_audit_logs_user_action_created", "user_id", "action", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="success", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class RefreshToken(Base):
    """Long-lived refresh token paired with a short-lived access token.

    The opaque token value (256-bit random, base64url) is stored as a SHA-256
    hash — never in cleartext — so a database leak does not directly expose
    live refresh tokens. Revocation works by setting `revoked_at`.

    Each `session_id` is embedded in the access-token JWT, allowing a single
    session to be terminated without rotating the global `token_version`.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_user_revoked", "user_id", "revoked_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # 32-byte random session id, base64url. Embedded in the access-token JWT
    # so we can map an access token back to its refresh token.
    session_id: Mapped[str] = mapped_column(String(48), unique=True, nullable=False, index=True)
    # SHA-256 hash of the opaque refresh token value.
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    replaced_by_id: Mapped[int | None] = mapped_column(ForeignKey("refresh_tokens.id"), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
