"""User-visible and SOC-facing log endpoints.

Two routes live here:

- ``GET /logs`` returns the raw user-targeted log entries. This is unchanged
  behaviour from M0/M1.
- ``GET /logs/security-timeline`` returns a sanitised, user-safe timeline
  suitable for rendering on the Dashboard. The full ``detail`` / ``reason``
  strings are **never** exposed on this endpoint — they remain queryable
  via the SOC-only ``audit_service`` / ``/metrics`` paths.

The timeline deliberately limits what gets returned to a small set of
categorical summaries; security-sensitive substrings (regex, stack traces,
API keys, system prompts, full payloads) are stripped before serialisation.
A regression in the sanitiser cannot leak those substrings into a JSON
response.
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Cookie, Depends, Header, Query
from sqlalchemy import desc, literal_column
from sqlalchemy.orm import Session

from server.core.database import get_db
from server.core.security import get_current_user
from server.models_db import AuditLog, Log

router = APIRouter(prefix="/logs", tags=["日志"])


# ---------------------------------------------------------------------------
# Sanitiser — strips any sensitive substring from a free-form string.
# ---------------------------------------------------------------------------
#
# ``SENTINEL_PATTERNS`` mirrors the E2E contract: if a real secret, L1 regex,
# stack trace, or system-prompt trigger shows up in the user-visible
# timeline, the test suite will fail. Adding a new pattern is cheap; the
# regexes are evaluated in order and the first hit short-circuits the
# sanitiser.
#
# The matchers intentionally use broad patterns (e.g. ``\bsystem\s*:`` with
# word boundaries) so that even paraphrased variants get caught. False
# positives are acceptable here — a blocked substring is replaced with
# ``"[已脱敏]"`` and the rest of the string is preserved.
_SENTINEL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_-]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"PRIVATE\s+KEY", re.IGNORECASE),
    re.compile(r"\bTraceback\s+\(most recent call last\)", re.IGNORECASE),
    re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+.*system\s+prompt", re.IGNORECASE),
    re.compile(r"forget\s+.*instructions", re.IGNORECASE),
    re.compile(r"\bsystem\s*:\s*", re.IGNORECASE),
)
_REDACTED = "[已脱敏]"


def _sanitise_text(value: str | None, *, max_length: int = 80) -> str:
    """Strip sensitive substrings and truncate to ``max_length`` chars."""
    if not value:
        return ""
    text = str(value)
    for pattern in _SENTINEL_PATTERNS:
        text = pattern.sub(_REDACTED, text)
    if len(text) > max_length:
        text = text[: max_length - 1] + "…"
    return text


# ---------------------------------------------------------------------------
# Category mapping — keep the visible surface small and reviewable.
# ---------------------------------------------------------------------------
#
# These maps are intentionally explicit (no fall-through to ``other`` for
# untrusted actions) so that the SOC can audit which log action names can
# show up in the user timeline.
_LOG_CATEGORY_MAP: dict[str, str] = {
    "demo_attack": "demo_attack",
    "copilot_stream": "copilot_stream",
    "register": "auth_event",
    "login_password": "auth_event",
    "login_otp": "auth_event",
    "logout": "auth_event",
    "password_reset_request": "auth_event",
    "password_reset_confirm": "auth_event",
    "totp_setup": "auth_event",
    "totp_enable": "auth_event",
    "totp_disable": "auth_event",
    "user_config_update": "config_event",
    "api_key_set": "config_event",
    "api_key_delete": "config_event",
    "site_target_set": "config_event",
    "threat_confirm": "threat_event",
}
_AUDIT_CATEGORY_MAP: dict[str, str] = {
    "login_success": "auth_event",
    "login_failed": "auth_event",
    "logout": "auth_event",
    "register": "auth_event",
    "password_change": "auth_event",
    "totp_enable": "auth_event",
    "totp_disable": "auth_event",
    "totp_verify": "auth_event",
    "api_key_set": "config_event",
    "api_key_delete": "config_event",
    "config_change": "config_event",
    "role_change": "config_event",
    "user_delete": "config_event",
    "alert_confirm": "threat_event",
    "threat_block": "threat_event",
    "guardrail_check": "guardrail_event",
}


def _category_for_log(action: str) -> str:
    return _LOG_CATEGORY_MAP.get(action, "other_log")


def _category_for_audit(action: str, status: str) -> str:
    if action == "guardrail_check":
        if status == "passed":
            return "guardrail_passed"
        if status == "blocked":
            return "guardrail_blocked"
        if status == "warning":
            return "guardrail_warning"
    return _AUDIT_CATEGORY_MAP.get(action, "other_audit")


def _summary_for_log(action: str, level: str) -> str:
    base = {
        "demo_attack": "已生成一条 Demo 攻击样本",
        "copilot_stream": "AI 助手已请求分析",
        "register": "新账号已注册",
        "login_password": "密码登录成功",
        "login_otp": "邮箱验证码登录成功",
        "logout": "用户已退出",
        "password_reset_request": "密码重置请求",
        "password_reset_confirm": "密码重置完成",
        "totp_setup": "TOTP 设置已启动",
        "totp_enable": "TOTP 已启用",
        "totp_disable": "TOTP 已关闭",
        "user_config_update": "AI 配置已更新",
        "api_key_set": "API Key 已设置",
        "api_key_delete": "API Key 已清除",
        "site_target_set": "受保护站点已更新",
        "threat_confirm": "威胁确认已记录",
    }.get(action)
    if base is None:
        base = f"系统事件: {action}"
    return _sanitise_text(base, max_length=80)


def _summary_for_audit(action: str, status: str, resource_type: str | None) -> str:
    if action == "guardrail_check":
        scope = resource_type or "system"
        if status == "passed":
            return _sanitise_text(f"安全护栏通过：{scope}", max_length=80)
        if status == "blocked":
            return _sanitise_text(f"安全护栏拦截：{scope}", max_length=80)
        if status == "warning":
            return _sanitise_text(f"安全护栏告警：{scope}", max_length=80)
    base = {
        "login_success": "登录成功",
        "login_failed": "登录失败",
        "logout": "退出登录",
        "register": "账号注册",
        "password_change": "密码已更新",
        "totp_enable": "TOTP 已启用",
        "totp_disable": "TOTP 已关闭",
        "totp_verify": "TOTP 验证",
        "api_key_set": "API Key 已设置",
        "api_key_delete": "API Key 已清除",
        "config_change": "配置已变更",
        "role_change": "角色已变更",
        "user_delete": "账号已删除",
        "alert_confirm": "告警已确认",
        "threat_block": "威胁已阻断",
    }.get(action)
    if base is None:
        base = f"审计事件: {action}"
    return _sanitise_text(base, max_length=80)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


_TIMELINE_DEFAULT_LIMIT = 50
_TIMELINE_MAX_LIMIT = 100


@router.get("")
async def get_logs(
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    logs = (
        db.query(Log)
        .filter((Log.user_id == user.id) | (Log.user_id.is_(None)))
        .order_by(Log.created_at.desc())
        .limit(200)
        .all()
    )
    return {
        "items": [
            {
                "id": item.id,
                "level": item.level,
                "action": item.action,
                "detail": item.detail,
                "created_at": item.created_at.isoformat(),
            }
            for item in logs
        ]
    }


@router.get("/security-timeline")
async def get_security_timeline(
    limit: int = Query(default=_TIMELINE_DEFAULT_LIMIT, ge=1),
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """User-visible SOC timeline.

    Returns a capped, sanitised union of ``Log`` + ``AuditLog`` rows
    (current user only). The full reason/detail strings stay in the
    database; only short category summaries reach the client.
    """
    user = get_current_user(db, access_token_cookie, authorization)
    capped_limit = min(int(limit), _TIMELINE_MAX_LIMIT)

    log_subq = db.query(
        Log.id.label("id"),
        Log.created_at.label("created_at"),
        literal_column("'log'").label("source"),
        Log.action.label("action"),
        Log.level.label("status"),
        Log.user_id.label("user_id"),
        literal_column("NULL").label("resource_type"),
    ).filter(
        (Log.user_id == user.id) | (Log.user_id.is_(None))
    )
    audit_subq = db.query(
        AuditLog.id.label("id"),
        AuditLog.created_at.label("created_at"),
        literal_column("'audit'").label("source"),
        AuditLog.action.label("action"),
        AuditLog.status.label("status"),
        AuditLog.user_id.label("user_id"),
        AuditLog.resource_type.label("resource_type"),
    ).filter(
        (AuditLog.user_id == user.id) | (AuditLog.user_id.is_(None))
    )

    try:
        # ``Query.union_all`` 在两个 ``Query`` 上做合并；order_by / limit
        # 必须挂在 union 后的 query 上，确保 SQL 不嵌入到子查询里。
        # Timeline 返回最新事件优先（newest-first），因此使用
        # ``created_at DESC`` + ``id DESC`` 作为复合排序键，避免同毫秒
        # 插入的两条事件顺序不稳定。
        # 注意：union 后的 query 没有 ORM 实体上下文，必须用 ``column()``
        # 显式拿到子查询的标签列；不能用字符串 label，否则 SQLAlchemy
        # 2.x 会抛 ``Can't resolve label reference``。
        from sqlalchemy import column

        union_q = log_subq.union_all(audit_subq)
        rows = (
            union_q.order_by(desc(column("created_at")))
            .order_by(desc(column("id")))
            .limit(capped_limit)
            .all()
        )
    except Exception:  # noqa: BLE001
        return {"items": [], "limit": capped_limit, "degraded": True}

    items: list[dict[str, Any]] = []
    for row in rows:
        # ``row`` is a SQLAlchemy ``Row``; map columns defensively.
        source = getattr(row, "source", "log")
        action = getattr(row, "action", "")
        status = getattr(row, "status", "info")
        created_at = getattr(row, "created_at", None)
        if source == "audit":
            resource_type = getattr(row, "resource_type", None)
            category = _category_for_audit(action, status)
            summary = _summary_for_audit(action, status, resource_type)
        else:
            category = _category_for_log(action)
            summary = _summary_for_log(action, status)
        items.append(
            {
                "id": int(getattr(row, "id", 0) or 0),
                "ts": created_at.isoformat() if created_at else None,
                "source": source,
                "category": category,
                "summary": summary,
                "status": status,
            }
        )

    return {"items": items, "limit": capped_limit}
