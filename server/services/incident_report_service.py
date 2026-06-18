"""案件证据报告 service (M3-07)。

设计要点（docs/agent/M3_07_INCIDENT_EVIDENCE_REPORT_EXPORT_TASK.md §6/§7/§8）:

- **纯函数**:不依赖 ORM / DB,只接收 ``incident_service.get_incident_detail``
  返回的 dict 派生 Markdown 报告;便于单测。
- **脱敏**:复用 ``server.routers.logs_router._SENTINEL_PATTERNS`` 集合,并新增
  ``developer:`` 触发;``sanitize_report_text`` 返回 (处理后文本, 本次脱敏命中次数)。
- **截断限制**:
  - incident summary: 1000 字符
  - alert summary: 240 字符
  - payload preview: 180 字符
  - event detail: 240 字符
  - event note preview: 160 字符
  - linked alerts: 最多 20(超出时报告里写明"仅展示前 20 条,共 N 条")
  - events: 最多 50 newest-first(超出时写明"仅展示最近 50 条,共 N 条或至少 N 条")
- **filename 派生**:只由 ``incident_id`` 派生,绝不包含 title(避免文件名注入 / 泄密)。
- **报告内容严格禁止**:
  - 完整 raw payload(只放 ``payload_length`` + preview)
  - 完整 ``IncidentEvent.note``(只放 ``note_length`` + preview)
  - fake secret / system prompt / stack trace / Guardrails regex
- **不调用 LLM**:纯服务端拼装。
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------


# 报告内容字段长度限制(与任务文档 §6 完全对齐)
SUMMARY_MAX_CHARS = 1000
ALERT_SUMMARY_MAX_CHARS = 240
PAYLOAD_PREVIEW_MAX_CHARS = 180
EVENT_DETAIL_MAX_CHARS = 240
EVENT_NOTE_PREVIEW_MAX_CHARS = 160

# 报告里关联告警 / 事件上限
LINKED_ALERT_LIMIT = 20
EVENT_LIMIT = 50

# 报告文件名由 incident_id 派生,绝不包含 title
_FILENAME_PREFIX = "incident-"
_FILENAME_SUFFIX = "-report.md"


# ---------------------------------------------------------------------------
# 脱敏 sentinel
# ---------------------------------------------------------------------------
#
# 复用 ``server.routers.logs_router._SENTINEL_PATTERNS`` 的所有 pattern,
# 并新增 ``developer:`` 触发,避免 prompt injection 通过 system / developer
# 角色泄漏到对外报告。
_REPORT_SENTINEL_PATTERNS: tuple[re.Pattern[str], ...] = (
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
    re.compile(r"\bdeveloper\s*:\s*", re.IGNORECASE),
)
_REDACTED = "[已脱敏]"


def sanitize_report_text(value: str | None, *, max_chars: int) -> tuple[str, int]:
    """对一段文本先做脱敏再截断,返回 (处理后文本, 脱敏命中次数)。

    - 命中 sentinel 的子串替换为 ``[已脱敏]``;
    - 截断按字符数;超过 max_chars 时保留前 max_chars - 1 字符并补 ``…``;
    - ``value`` 为 None / 空串时返回 ``("", 0)``。
    """
    if not value:
        return ("", 0)
    text = str(value)
    redaction_count = 0
    for pattern in _REPORT_SENTINEL_PATTERNS:
        new_text, count = pattern.subn(_REDACTED, text)
        if count > 0:
            redaction_count += count
            text = new_text
    if len(text) > max_chars:
        text = text[: max_chars - 1] + "…"
    return (text, redaction_count)


# ---------------------------------------------------------------------------
# 时间 / filename helpers
# ---------------------------------------------------------------------------


def _format_utc_timestamp(epoch: float | None) -> str:
    """epoch 秒 → ``YYYY-MM-DD HH:MM:SS UTC``;空值返回 ``"-"``。"""
    if not epoch or float(epoch) <= 0:
        return "-"
    try:
        dt = datetime.fromtimestamp(float(epoch), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _build_filename(incident_id: str) -> str:
    """filename 只由 incident_id 派生;若 incident_id 含非法字符,降级为 safe 形式。"""
    safe_id = re.sub(r"[^A-Za-z0-9_]", "_", str(incident_id or "unknown"))
    return f"{_FILENAME_PREFIX}{safe_id}{_FILENAME_SUFFIX}"


# ---------------------------------------------------------------------------
# Markdown 构造 helpers
# ---------------------------------------------------------------------------


def _build_alert_block(alert: dict[str, Any]) -> tuple[str, int]:
    """构造一条关联告警的 Markdown 片段:表行 + 证据摘录。"""
    redaction_count = 0
    raw = alert.get("raw_alert") or {}
    analysis = alert.get("llm_analysis") or {}
    triage = alert.get("triage") or {}

    alert_id = str(alert.get("alert_id", ""))
    source = raw.get("source_ip") or "-"
    target = raw.get("destination_ip") or "-"
    blocked = "是" if raw.get("blocked") else "否"
    risk = (analysis.get("risk_level") or "unknown") or "unknown"
    triage_status = (triage.get("status") or "-") or "-"

    summary_text, s_count = sanitize_report_text(
        analysis.get("summary"), max_chars=ALERT_SUMMARY_MAX_CHARS
    )
    redaction_count += s_count
    summary_display = summary_text or "-"

    row = (
        f"| `{alert_id}` | {source} | {target} | {risk} | {blocked} | "
        f"{triage_status} | {summary_display} |"
    )

    payload_raw = raw.get("payload")
    payload_length = len(str(payload_raw)) if payload_raw is not None else 0
    payload_preview, p_count = sanitize_report_text(
        payload_raw, max_chars=PAYLOAD_PREVIEW_MAX_CHARS
    )
    redaction_count += p_count

    evidence = [
        "",
        "### 告警证据摘录",
        "",
        f"- alert_id: `{alert_id}`",
        f"  - payload_length: {payload_length}",
        f"  - payload_preview: {payload_preview if payload_preview else '-'}",
    ]
    return row + "\n" + "\n".join(evidence), redaction_count


def _build_event_block(event: dict[str, Any]) -> tuple[str, int]:
    """构造一条事件时间线 Markdown 行。"""
    redaction_count = 0
    event_type = str(event.get("event_type", ""))
    ts = _format_utc_timestamp(event.get("created_at"))
    from_status = event.get("from_status")
    to_status = event.get("to_status")
    actor = event.get("actor_user_id")

    if event_type == "status_changed" and from_status and to_status:
        prefix = f"- {ts} · status_changed · {from_status} -> {to_status}"
    else:
        prefix = f"- {ts} · {event_type or '-'}"

    lines = [prefix]

    detail_text, d_count = sanitize_report_text(
        event.get("detail"), max_chars=EVENT_DETAIL_MAX_CHARS
    )
    redaction_count += d_count
    if detail_text:
        lines.append(f"  - detail: {detail_text}")

    note = event.get("note")
    note_length = len(str(note)) if note is not None else 0
    if note is not None and note != "":
        note_preview, n_count = sanitize_report_text(
            note, max_chars=EVENT_NOTE_PREVIEW_MAX_CHARS
        )
        redaction_count += n_count
        lines.append(f"  - note_length: {note_length}")
        lines.append(f"  - note_preview: {note_preview if note_preview else '-'}")

    if actor is not None:
        lines.append(f"  - actor: #{int(actor)}")

    return "\n".join(lines) + "\n", redaction_count


# ---------------------------------------------------------------------------
# Public service API
# ---------------------------------------------------------------------------


def build_incident_report(
    detail: dict[str, Any],
    *,
    generated_at: float | None = None,
) -> dict[str, Any]:
    """接收 ``incident_service.get_incident_detail`` 的 dict 派生 Markdown 报告。

    返回::

        {
            "filename": "incident-<id>-report.md",
            "markdown": "# 案件证据报告 ...",
            "meta": {
                "generated_at": float,
                "alert_count": int,
                "included_alerts": int,
                "event_count": int,
                "included_events": int,
                "redaction_count": int,
                "truncated": bool,
            },
        }
    """
    if not isinstance(detail, dict):
        raise ValueError("detail must be a dict from incident_service.get_incident_detail")

    incident = detail.get("incident") or {}
    linked_alerts = detail.get("linked_alerts") or []
    events = detail.get("events") or []

    incident_id = str(incident.get("incident_id", "unknown"))
    title_text, _t_count = sanitize_report_text(
        incident.get("title"), max_chars=SUMMARY_MAX_CHARS
    )
    summary_text, s_count = sanitize_report_text(
        incident.get("summary"), max_chars=SUMMARY_MAX_CHARS
    )

    redaction_count = _t_count + s_count

    # 截断
    included_alerts = linked_alerts[:LINKED_ALERT_LIMIT]
    included_events = events[:EVENT_LIMIT]
    truncated = (len(linked_alerts) > LINKED_ALERT_LIMIT) or (
        len(events) > EVENT_LIMIT
    )

    # 头部
    gen_at = float(generated_at) if generated_at else datetime.now(timezone.utc).timestamp()
    status_label = str(incident.get("status", "-"))
    severity_label = str(incident.get("severity", "-"))
    alert_count = int(incident.get("alert_count", len(linked_alerts)) or 0)
    event_count = int(detail.get("event_count", len(events)) or 0)

    lines: list[str] = []
    lines.append("# 案件证据报告")
    lines.append("")
    lines.append(f"生成时间: {_format_utc_timestamp(gen_at)}")
    lines.append(f"案件 ID: {incident_id}")
    lines.append(f"状态: {status_label}")
    lines.append(f"严重度: {severity_label}")
    lines.append(f"关联告警: {alert_count}")
    lines.append("")

    # 1. 案件摘要
    lines.append("## 1. 案件摘要")
    lines.append("")
    if title_text:
        lines.append(f"- 标题: {title_text}")
    if summary_text:
        lines.append("")
        lines.append(summary_text)
    elif not title_text:
        lines.append("(无摘要)")
    lines.append("")

    # 2. 关联告警
    lines.append("## 2. 关联告警")
    lines.append("")
    if len(linked_alerts) > LINKED_ALERT_LIMIT:
        lines.append(
            f"> 仅展示前 {LINKED_ALERT_LIMIT} 条,共 {len(linked_alerts)} 条。"
        )
        lines.append("")
    if not included_alerts:
        lines.append("(无关联告警)")
        lines.append("")
    else:
        lines.append(
            "| alert_id | source | target | risk | blocked | triage | summary |"
        )
        lines.append("|---|---|---|---|---|---|---|")
        for alert in included_alerts:
            block, r_count = _build_alert_block(alert)
            redaction_count += r_count
            lines.append(block)
        lines.append("")

    # 3. 案件时间线(newest-first)
    lines.append("## 3. 案件时间线")
    lines.append("")
    if len(events) > EVENT_LIMIT:
        lines.append(
            f"> 仅展示最近 {EVENT_LIMIT} 条,共 {len(events)} 条。"
        )
        lines.append("")
    if not included_events:
        lines.append("(无事件)")
        lines.append("")
    else:
        for event in included_events:
            block, r_count = _build_event_block(event)
            redaction_count += r_count
            lines.append(block.rstrip("\n"))
            lines.append("")

    # 4. 安全与脱敏说明
    lines.append("## 4. 安全与脱敏说明")
    lines.append("")
    lines.append(
        "本报告由 AI-CyberSentinel 自动生成。"
        "报告已对密钥、系统提示词、堆栈、完整 payload 和完整处置备注做脱敏或截断。"
    )
    lines.append("")

    markdown = "\n".join(lines)
    return {
        "filename": _build_filename(incident_id),
        "markdown": markdown,
        "meta": {
            "generated_at": gen_at,
            "alert_count": int(alert_count),
            "included_alerts": len(included_alerts),
            "event_count": int(event_count),
            "included_events": len(included_events),
            "redaction_count": int(redaction_count),
            "truncated": bool(truncated),
        },
    }


__all__ = [
    "SUMMARY_MAX_CHARS",
    "ALERT_SUMMARY_MAX_CHARS",
    "PAYLOAD_PREVIEW_MAX_CHARS",
    "EVENT_DETAIL_MAX_CHARS",
    "EVENT_NOTE_PREVIEW_MAX_CHARS",
    "LINKED_ALERT_LIMIT",
    "EVENT_LIMIT",
    "sanitize_report_text",
    "build_incident_report",
]
