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


# ---------------------------------------------------------------------------
# 告警研判持久化 (M3-03)
# ---------------------------------------------------------------------------
#
# 设计要点 (docs/agent/M3_03_ALERT_TRIAGE_PERSISTENCE_AND_HISTORY_TASK.md §4):
# - ``AlertRecord`` 是每条告警的持久化快照,事实来源。
#   ``(user_id, alert_id)`` 唯一;保存 raw alert JSON、LLM analysis JSON、
#   analysis error、processed_at、最新 triage 字段。``GET /alerts`` 重启后走它。
# - ``AlertTriageEvent`` 是每次 triage 状态变化的历史事件。
#   按 alert_record_id 关联;保存 from/to、disposition、analyst_note、
#   updated_by、created_at。``GET /alerts/{alert_id}/triage/history`` 走它。
# - raw alert 与 LLM analysis 使用 ``Text`` 存 JSON 字符串(``json.dumps(...,
#   ensure_ascii=False)``),不依赖 PostgreSQL JSONB,以便 SQLite / Compose
#   PostgreSQL 走同一份代码;``_json_loads_dict`` 反序列化失败回退空 dict。
# - 不引入新的 env 变量;不在日志打印完整 raw payload;不触碰 ``server/security/**``。


class AlertRecord(Base, TimestampMixin):
    """每条告警的持久化快照(M3-03 事实来源)。"""

    __tablename__ = "alert_records"
    __table_args__ = (
        UniqueConstraint("user_id", "alert_id", name="uq_alert_records_user_alert"),
        Index("ix_alert_records_user_processed", "user_id", "processed_at"),
        Index(
            "ix_alert_records_user_status_processed",
            "user_id",
            "triage_status",
            "processed_at",
        ),
        Index("ix_alert_records_alert_id", "alert_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alert_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    raw_alert_json: Mapped[str] = mapped_column(Text, nullable=False)
    llm_analysis_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    triage_status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    triage_disposition: Mapped[str | None] = mapped_column(String(64), nullable=True)
    triage_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    triage_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    triage_updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    events: Mapped[list["AlertTriageEvent"]] = relationship(
        "AlertTriageEvent",
        primaryjoin="AlertRecord.id == foreign(AlertTriageEvent.alert_record_id)",
        backref="record",
        cascade="all, delete-orphan",
        order_by="AlertTriageEvent.id",
    )


class AlertTriageEvent(Base):
    """每次 triage 状态变化的历史事件(M3-03 事实来源)。"""

    __tablename__ = "alert_triage_events"
    __table_args__ = (
        Index(
            "ix_alert_triage_events_user_alert_created",
            "user_id",
            "alert_id",
            "created_at",
        ),
        Index("ix_alert_triage_events_record_created", "alert_record_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alert_record_id: Mapped[int] = mapped_column(
        ForeignKey("alert_records.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    alert_id: Mapped[str] = mapped_column(String(64), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    disposition: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analyst_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
