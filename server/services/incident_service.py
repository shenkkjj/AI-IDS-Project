"""安全事件 / 案件服务 (M3-04)。

设计要点（docs/agent/M3_04_INCIDENT_CASE_WORKBENCH_TASK.md §5）:

- ``incidents`` 是案件事实来源;``incident_alert_links`` 是告警关联事实来源;
  ``incident_events`` 是事件时间线事实来源。
- owner 隔离: 所有 incident / link / event 都按 ``user_id`` 严格过滤;
  非 owner / 不存在统一返回 ``None``,路由层映射 404,不暴露存在性。
- 状态流转:
  - ``open / investigating / contained`` 是中间态,可逆。
  - ``resolved / false_positive`` 是关闭态,自动设置 ``closed_at``;
    改回打开态时清空 ``closed_at``。
- 重复 link 幂等: 同一 ``(incident_record_id, alert_record_id)`` 已有
  active link 时,不重复写,不写新 ``IncidentEvent``;也不写新 Log。
- 事件 timeline: 每次 status / severity / summary / title / note 变化
  都要写 ``IncidentEvent``,且与主变更同事务。
- ``Log`` 只写脱敏摘要;``note`` 留在 ``IncidentEvent`` 内部(私有),
  通过 owner API 返回。
- DB 写失败不静默;主路径返回 5xx(由路由层映射)。
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from server.core.database import SessionLocal
from server.models_db import (
    AlertRecord,
    Incident,
    IncidentAlertLink,
    IncidentEvent,
)


# ---------------------------------------------------------------------------
# 枚举常量
# ---------------------------------------------------------------------------

INCIDENT_STATUS_VALUES: tuple[str, ...] = (
    "open",
    "investigating",
    "contained",
    "resolved",
    "false_positive",
)
"""事件状态白名单,与 Pydantic schema 保持一致。"""

OPEN_STATUSES: frozenset[str] = frozenset({"open", "investigating", "contained"})
CLOSED_STATUSES: frozenset[str] = frozenset({"resolved", "false_positive"})

INCIDENT_SEVERITY_VALUES: tuple[str, ...] = ("critical", "high", "medium", "low")
"""事件严重度白名单。"""

INCIDENT_EVENT_TYPES: tuple[str, ...] = (
    "created",
    "status_changed",
    "alert_linked",
    "alert_unlinked",
    "note_added",
    "summary_updated",
    "severity_changed",
    "title_changed",
)


# ---------------------------------------------------------------------------
# 序列化 helpers
# ---------------------------------------------------------------------------


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _epoch_to_dt(value: float | int | None) -> datetime | None:
    if value is None or not value:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError, OSError):
        return None


def _dt_to_epoch(value: datetime | None) -> float:
    if value is None:
        return 0.0
    return float(value.replace(tzinfo=timezone.utc).timestamp())


def _new_incident_id() -> str:
    """生成 ``inc_<12-16 hex>`` 格式的业务 ID。"""
    return "inc_" + uuid.uuid4().hex[:16]


def _incident_to_summary(
    incident: Incident,
    *,
    alert_count: int,
) -> dict[str, Any]:
    """``incidents`` → 列表 / 详情基础信息(不含 linked_alerts / events)。"""
    return {
        "incident_id": incident.incident_id,
        "title": incident.title,
        "summary": incident.summary,
        "severity": incident.severity,
        "status": incident.status,
        "user_id": int(incident.user_id),
        "assignee_user_id": int(incident.assignee_user_id) if incident.assignee_user_id else None,
        "created_from_alert_id": incident.created_from_alert_id,
        "alert_count": int(alert_count),
        "created_at": _dt_to_epoch(incident.created_at),
        "updated_at": _dt_to_epoch(incident.updated_at),
        "closed_at": _dt_to_epoch(incident.closed_at) if incident.closed_at else None,
    }


def _event_to_dict(event: IncidentEvent) -> dict[str, Any]:
    return {
        "id": int(event.id),
        "event_type": event.event_type,
        "from_status": event.from_status,
        "to_status": event.to_status,
        "detail": event.detail or "",
        "note": event.note,
        "actor_user_id": int(event.actor_user_id) if event.actor_user_id else None,
        "created_at": _dt_to_epoch(event.created_at),
    }


def _alert_link_to_alert_item(
    link: IncidentAlertLink,
    alert: AlertRecord | None,
) -> dict[str, Any]:
    """从 IncidentAlertLink + AlertRecord 派生前端 alert 列表所需字段。

    与 ``GET /alerts`` 列表元素结构兼容,便于前端复用 mapBackendAlert。
    """
    if alert is None:
        # 极端 case: link 存在但 alert_record 被删;返回最小信息。
        return {
            "alert_id": link.alert_id,
            "raw_alert": {"alert_user_id": link.user_id},
            "llm_analysis": None,
            "triage": {
                "status": "new",
                "disposition": None,
                "analyst_note": None,
                "updated_at": 0,
                "updated_by": None,
            },
        }
    raw = _json_loads(alert.raw_alert_json)
    analysis = _json_loads(alert.llm_analysis_json)
    return {
        "alert_id": alert.alert_id,
        "raw_alert": raw,
        "llm_analysis": analysis,
        "analysis_error": alert.analysis_error,
        "processed_at": _dt_to_epoch(alert.processed_at),
        "triage": {
            "status": alert.triage_status or "new",
            "disposition": alert.triage_disposition,
            "analyst_note": alert.triage_note,
            "updated_at": _dt_to_epoch(alert.triage_updated_at),
            "updated_by": int(alert.triage_updated_by) if alert.triage_updated_by else None,
        },
    }


def _json_loads(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        result = json.loads(text)
        return result if isinstance(result, dict) else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# 审计 detail 构造
# ---------------------------------------------------------------------------


def _build_create_audit_detail(
    *,
    incident_id: str,
    title: str,
    severity: str,
    status: str,
    source_alert_id: str | None,
) -> str:
    parts = [
        f"incident_id={incident_id}",
        f"title_length={len(title)}",
        f"severity={severity}",
        f"status={status}",
    ]
    if source_alert_id:
        parts.append(f"source_alert_id={source_alert_id}")
    return ";".join(parts)


def _build_update_audit_detail(
    *,
    incident_id: str,
    changed_fields: tuple[str, ...],
    status_from: str | None,
    status_to: str | None,
    severity_from: str | None,
    severity_to: str | None,
    title_changed: bool,
    summary_changed: bool,
    note_length: int,
) -> str:
    parts = [f"incident_id={incident_id}"]
    if changed_fields:
        parts.append(f"changed={','.join(changed_fields)}")
    if status_from and status_to and status_from != status_to:
        parts.append(f"status={status_from}->{status_to}")
    if severity_from and severity_to and severity_from != severity_to:
        parts.append(f"severity={severity_from}->{severity_to}")
    if title_changed:
        parts.append("title_changed=1")
    if summary_changed:
        parts.append("summary_changed=1")
    parts.append(f"note_length={note_length}")
    return ";".join(parts)


def _build_link_audit_detail(
    *,
    incident_id: str,
    alert_id: str,
    action: str,
) -> str:
    return f"incident_id={incident_id};alert_id={alert_id};action={action}"


# ---------------------------------------------------------------------------
# DB 写入 helpers
# ---------------------------------------------------------------------------


def _add_event(
    db: Session,
    *,
    incident: Incident,
    user_id: int,
    event_type: str,
    detail: str = "",
    from_status: str | None = None,
    to_status: str | None = None,
    note: str | None = None,
    actor_user_id: int | None = None,
) -> IncidentEvent:
    event = IncidentEvent(
        incident_record_id=int(incident.id),
        incident_id=str(incident.incident_id),
        user_id=int(user_id),
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        detail=detail or "",
        note=note,
        actor_user_id=int(actor_user_id) if actor_user_id else None,
        created_at=_utcnow_naive(),
    )
    db.add(event)
    return event


def _count_active_links(db: Session, incident_record_id: int) -> int:
    return (
        db.query(IncidentAlertLink)
        .filter(
            IncidentAlertLink.incident_record_id == incident_record_id,
            IncidentAlertLink.removed_at.is_(None),
        )
        .count()
    )


def _get_alert_record_for_user(
    db: Session, user_id: int, alert_id: str
) -> AlertRecord | None:
    return (
        db.query(AlertRecord)
        .filter(AlertRecord.user_id == int(user_id), AlertRecord.alert_id == str(alert_id))
        .first()
    )


# ---------------------------------------------------------------------------
# Public service API
# ---------------------------------------------------------------------------


def create_incident(
    db: Session,
    *,
    user_id: int,
    title: str,
    summary: str | None,
    severity: str,
    alert_id: str | None,
) -> dict[str, Any] | None:
    """创建 incident;若 ``alert_id`` 属于当前 user,自动 link。

    - ``alert_id`` 不存在 / 非 owner → 返回 ``None``(路由层映射 404)。
    - 写 ``IncidentEvent(created)`` + active link + ``IncidentEvent(alert_linked)``。
    - 写 ``Log(action="incident_create")`` 脱敏摘要(由路由层处理)。

    返回值: 包含 ``incident`` / ``linked_alerts`` / ``events`` 的 detail dict。
    """
    alert_record: AlertRecord | None = None
    if alert_id:
        alert_record = _get_alert_record_for_user(db, user_id, alert_id)
        if alert_record is None:
            return None

    incident = Incident(
        user_id=int(user_id),
        incident_id=_new_incident_id(),
        title=title,
        summary=summary,
        severity=severity,
        status="open",
        assignee_user_id=int(user_id),
        created_from_alert_id=str(alert_id) if alert_id else None,
        closed_at=None,
    )
    db.add(incident)
    db.flush()  # 拿 incident.id

    now = _utcnow_naive()
    incident.created_at = now
    incident.updated_at = now

    _add_event(
        db,
        incident=incident,
        user_id=user_id,
        event_type="created",
        detail=f"incident_id={incident.incident_id};severity={severity};status=open",
        to_status="open",
        actor_user_id=user_id,
    )

    linked_alerts: list[dict[str, Any]] = []
    if alert_record is not None:
        link = IncidentAlertLink(
            incident_record_id=int(incident.id),
            user_id=int(user_id),
            incident_id=str(incident.incident_id),
            alert_record_id=int(alert_record.id),
            alert_id=str(alert_record.alert_id),
            linked_by=int(user_id),
            linked_at=now,
            removed_at=None,
        )
        db.add(link)
        db.flush()
        _add_event(
            db,
            incident=incident,
            user_id=user_id,
            event_type="alert_linked",
            detail=f"alert_id={alert_record.alert_id}",
            actor_user_id=user_id,
        )
        linked_alerts.append(_alert_link_to_alert_item(link, alert_record))

    db.commit()
    db.refresh(incident)

    audit = {
        "action": "incident_create",
        "detail": _build_create_audit_detail(
            incident_id=incident.incident_id,
            title=incident.title,
            severity=incident.severity,
            status=incident.status,
            source_alert_id=alert_record.alert_id if alert_record else None,
        ),
        "user_id": int(user_id),
    }

    return {
        "incident": _incident_to_summary(incident, alert_count=len(linked_alerts)),
        "linked_alerts": linked_alerts,
        "events": [_event_to_dict(e) for e in incident.events],
        "audit": audit,
    }


def list_incidents(
    db: Session,
    user_id: int,
    *,
    limit: int = 50,
    status: str | None = None,
) -> dict[str, Any]:
    """按 user 倒序返回 incident 列表;可选按 status 过滤。"""
    bounded = max(1, min(int(limit), 100))
    query = db.query(Incident).filter(Incident.user_id == int(user_id))
    if status:
        query = query.filter(Incident.status == status)
    records = (
        query.order_by(Incident.updated_at.desc(), Incident.id.desc())
        .limit(bounded)
        .all()
    )
    items: list[dict[str, Any]] = []
    for incident in records:
        count = _count_active_links(db, int(incident.id))
        items.append(_incident_to_summary(incident, alert_count=count))
    return {
        "items": items,
        "count": len(items),
        "limit": bounded,
    }


def get_incident_detail(
    db: Session,
    user_id: int,
    incident_id: str,
    *,
    event_limit: int = 20,
) -> dict[str, Any] | None:
    """返回 incident 完整 detail;非 owner / 不存在 → ``None``。"""
    incident = (
        db.query(Incident)
        .filter(Incident.user_id == int(user_id), Incident.incident_id == str(incident_id))
        .first()
    )
    if incident is None:
        return None

    bounded = max(1, min(int(event_limit), 100))

    # active links → linked_alerts
    links = (
        db.query(IncidentAlertLink)
        .filter(
            IncidentAlertLink.incident_record_id == int(incident.id),
            IncidentAlertLink.removed_at.is_(None),
        )
        .order_by(IncidentAlertLink.linked_at.asc(), IncidentAlertLink.id.asc())
        .all()
    )
    alert_ids = [int(link.alert_record_id) for link in links]
    alerts_by_id: dict[int, AlertRecord] = {}
    if alert_ids:
        alerts = (
            db.query(AlertRecord)
            .filter(AlertRecord.id.in_(alert_ids))
            .all()
        )
        alerts_by_id = {int(a.id): a for a in alerts}
    linked_alerts = [
        _alert_link_to_alert_item(link, alerts_by_id.get(int(link.alert_record_id)))
        for link in links
    ]

    # events: newest-first
    events = (
        db.query(IncidentEvent)
        .filter(IncidentEvent.incident_record_id == int(incident.id))
        .order_by(IncidentEvent.created_at.desc(), IncidentEvent.id.desc())
        .limit(bounded)
        .all()
    )

    return {
        "incident": _incident_to_summary(incident, alert_count=len(linked_alerts)),
        "linked_alerts": linked_alerts,
        "events": [_event_to_dict(e) for e in events],
        "event_limit": bounded,
    }


def update_incident(
    db: Session,
    *,
    user_id: int,
    incident_id: str,
    status: str | None,
    severity: str | None,
    title: str | None,
    summary: str | None,
    note: str | None,
) -> dict[str, Any] | None:
    """更新 incident 字段;非 owner / 不存在 → ``None``。

    - status 变化: 写 ``IncidentEvent(status_changed)``;若是进入关闭态,自动设
      ``closed_at``;若是离开关闭态(→ 打开态),清空 ``closed_at``。
    - severity / title / summary / note 变化: 写对应 ``IncidentEvent``。
    - 同事务内全部完成。
    """
    incident = (
        db.query(Incident)
        .filter(Incident.user_id == int(user_id), Incident.incident_id == str(incident_id))
        .first()
    )
    if incident is None:
        return None

    previous_status = incident.status
    previous_severity = incident.severity
    previous_title = incident.title
    previous_summary = incident.summary

    changed_fields: list[str] = []

    if status is not None and status != previous_status:
        incident.status = status
        changed_fields.append("status")
        _add_event(
            db,
            incident=incident,
            user_id=user_id,
            event_type="status_changed",
            from_status=previous_status,
            to_status=status,
            detail=f"status={previous_status}->{status}",
            note=note if note else None,
            actor_user_id=user_id,
        )
        # 关闭态自动设置 closed_at
        if status in CLOSED_STATUSES and previous_status not in CLOSED_STATUSES:
            incident.closed_at = _utcnow_naive()
        elif status in OPEN_STATUSES and previous_status in CLOSED_STATUSES:
            incident.closed_at = None

    if severity is not None and severity != previous_severity:
        incident.severity = severity
        changed_fields.append("severity")
        _add_event(
            db,
            incident=incident,
            user_id=user_id,
            event_type="severity_changed",
            detail=f"severity={previous_severity}->{severity}",
            note=note if note else None,
            actor_user_id=user_id,
        )

    title_changed = title is not None and title != previous_title
    if title_changed:
        incident.title = title
        changed_fields.append("title")
        _add_event(
            db,
            incident=incident,
            user_id=user_id,
            event_type="title_changed",
            detail="title_changed=1",
            note=note if note else None,
            actor_user_id=user_id,
        )

    summary_changed = summary is not None and summary != previous_summary
    if summary_changed:
        incident.summary = summary
        changed_fields.append("summary")
        _add_event(
            db,
            incident=incident,
            user_id=user_id,
            event_type="summary_updated",
            detail="summary_changed=1",
            note=note if note else None,
            actor_user_id=user_id,
        )

    # 单独的 note(没有任何字段变化):写 note_added 事件
    if note is not None and note != "" and not changed_fields:
        _add_event(
            db,
            incident=incident,
            user_id=user_id,
            event_type="note_added",
            note=note,
            detail=f"note_length={len(note)}",
            actor_user_id=user_id,
        )

    if changed_fields:
        incident.updated_at = _utcnow_naive()

    db.commit()
    db.refresh(incident)

    # 收集本次写入的事件(按 id 降序,newest-first),默认 20 条
    events = (
        db.query(IncidentEvent)
        .filter(IncidentEvent.incident_record_id == int(incident.id))
        .order_by(IncidentEvent.id.desc())
        .limit(20)
        .all()
    )

    audit = {
        "action": "incident_update",
        "detail": _build_update_audit_detail(
            incident_id=incident.incident_id,
            changed_fields=tuple(changed_fields),
            status_from=previous_status,
            status_to=incident.status if status is not None and status != previous_status else None,
            severity_from=previous_severity if severity is not None and severity != previous_severity else None,
            severity_to=incident.severity if severity is not None and severity != previous_severity else None,
            title_changed=title_changed,
            summary_changed=summary_changed,
            note_length=len(note or ""),
        ),
        "user_id": int(user_id),
    }

    return {
        "incident": _incident_to_summary(
            incident, alert_count=_count_active_links(db, int(incident.id))
        ),
        "events": [_event_to_dict(e) for e in events],
        "audit": audit,
    }


def link_alert(
    db: Session,
    *,
    user_id: int,
    incident_id: str,
    alert_id: str,
) -> dict[str, Any] | None:
    """把 alert 加入 incident;重复 link 幂等(不重复写 active link / event / Log)。

    - incident 不属于当前 user → ``None``。
    - alert 不属于当前 user → ``None``。
    - active link 已存在 → 返回当前 incident 状态,不写新 active link,
      不写新 ``IncidentEvent(alert_linked)``,**不**写 Log(避免重复审计)。
      这是任务文档 §4 推荐行为,由测试锁定。
    """
    incident = (
        db.query(Incident)
        .filter(Incident.user_id == int(user_id), Incident.incident_id == str(incident_id))
        .first()
    )
    if incident is None:
        return None

    alert_record = _get_alert_record_for_user(db, user_id, alert_id)
    if alert_record is None:
        return None

    existing = (
        db.query(IncidentAlertLink)
        .filter(
            IncidentAlertLink.incident_record_id == int(incident.id),
            IncidentAlertLink.alert_record_id == int(alert_record.id),
            IncidentAlertLink.removed_at.is_(None),
        )
        .first()
    )
    if existing is not None:
        # 幂等:不写新 link / event / Log
        return {
            "incident": _incident_to_summary(
                incident, alert_count=_count_active_links(db, int(incident.id))
            ),
            "alert_count": _count_active_links(db, int(incident.id)),
            "audit": None,
            "idempotent": True,
        }

    link = IncidentAlertLink(
        incident_record_id=int(incident.id),
        user_id=int(user_id),
        incident_id=str(incident.incident_id),
        alert_record_id=int(alert_record.id),
        alert_id=str(alert_record.alert_id),
        linked_by=int(user_id),
        linked_at=_utcnow_naive(),
        removed_at=None,
    )
    db.add(link)
    _add_event(
        db,
        incident=incident,
        user_id=user_id,
        event_type="alert_linked",
        detail=f"alert_id={alert_record.alert_id}",
        actor_user_id=user_id,
    )
    incident.updated_at = _utcnow_naive()
    db.commit()
    db.refresh(incident)

    audit = {
        "action": "incident_alert_link",
        "detail": _build_link_audit_detail(
            incident_id=incident.incident_id,
            alert_id=alert_record.alert_id,
            action="link",
        ),
        "user_id": int(user_id),
    }
    return {
        "incident": _incident_to_summary(
            incident, alert_count=_count_active_links(db, int(incident.id))
        ),
        "alert_count": _count_active_links(db, int(incident.id)),
        "audit": audit,
        "idempotent": False,
    }


def unlink_alert(
    db: Session,
    *,
    user_id: int,
    incident_id: str,
    alert_id: str,
) -> dict[str, Any] | None:
    """软删除 link(``removed_at = now``);非 owner / 不存在 / link 不存在统一 ``None``。"""
    incident = (
        db.query(Incident)
        .filter(Incident.user_id == int(user_id), Incident.incident_id == str(incident_id))
        .first()
    )
    if incident is None:
        return None

    alert_record = _get_alert_record_for_user(db, user_id, alert_id)
    if alert_record is None:
        return None

    link = (
        db.query(IncidentAlertLink)
        .filter(
            IncidentAlertLink.incident_record_id == int(incident.id),
            IncidentAlertLink.alert_record_id == int(alert_record.id),
            IncidentAlertLink.removed_at.is_(None),
        )
        .first()
    )
    if link is None:
        return None

    link.removed_at = _utcnow_naive()
    _add_event(
        db,
        incident=incident,
        user_id=user_id,
        event_type="alert_unlinked",
        detail=f"alert_id={alert_record.alert_id}",
        actor_user_id=user_id,
    )
    incident.updated_at = _utcnow_naive()
    db.commit()
    db.refresh(incident)

    audit = {
        "action": "incident_alert_unlink",
        "detail": _build_link_audit_detail(
            incident_id=incident.incident_id,
            alert_id=alert_record.alert_id,
            action="unlink",
        ),
        "user_id": int(user_id),
    }
    return {
        "incident": _incident_to_summary(
            incident, alert_count=_count_active_links(db, int(incident.id))
        ),
        "alert_count": _count_active_links(db, int(incident.id)),
        "audit": audit,
    }


def build_incident_audit_detail(
    *,
    incident_id: str,
    changed_fields: tuple[str, ...],
    status_from: str | None,
    status_to: str | None,
    note_length: int,
) -> str:
    """公开 helper,允许 router 层在 service 出错时构造 fallback detail。"""
    return _build_update_audit_detail(
        incident_id=incident_id,
        changed_fields=changed_fields,
        status_from=status_from,
        status_to=status_to,
        severity_from=None,
        severity_to=None,
        title_changed=False,
        summary_changed=False,
        note_length=note_length,
    )


__all__ = [
    "INCIDENT_STATUS_VALUES",
    "INCIDENT_SEVERITY_VALUES",
    "INCIDENT_EVENT_TYPES",
    "OPEN_STATUSES",
    "CLOSED_STATUSES",
    "create_incident",
    "list_incidents",
    "get_incident_detail",
    "update_incident",
    "link_alert",
    "unlink_alert",
    "build_incident_audit_detail",
]
