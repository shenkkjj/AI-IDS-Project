"""安全事件 / 案件工作台 API (M3-04)。

设计要点（docs/agent/M3_04_INCIDENT_CASE_WORKBENCH_TASK.md §5）:

- 所有端点必须 ``require_auth_user``;非 owner / 不存在统一 404。
- ``Log`` 写脱敏摘要,失败仅 warning,不阻断主请求。
- ``limit`` 参数走 Query 范围校验(1-100)。
- 请求体用 Pydantic schema 校验,失败 422。
- 错误响应不含 stack trace;用户可见 detail 走中文。
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.core.database import create_log, get_db
from server.core.security import require_auth_user
from server.models_db import User
from server.services import incident_service
from server.services.incident_service import (
    CLOSED_STATUSES,
    INCIDENT_SEVERITY_VALUES,
    INCIDENT_STATUS_VALUES,
)


router = APIRouter(prefix="/incidents", tags=["案件"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


IncidentStatus = Literal["open", "investigating", "contained", "resolved", "false_positive"]
IncidentSeverity = Literal["critical", "high", "medium", "low"]


class IncidentCreateIn(BaseModel):
    """``POST /incidents`` 请求体。"""

    title: str = Field(min_length=1, max_length=120)
    summary: str | None = Field(default=None, max_length=1000)
    severity: IncidentSeverity = "medium"
    alert_id: str | None = Field(default=None, max_length=64)


class IncidentUpdateIn(BaseModel):
    """``PATCH /incidents/{id}`` 请求体。所有字段可选;提供且变化时才生效。"""

    status: IncidentStatus | None = None
    severity: IncidentSeverity | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)
    summary: str | None = Field(default=None, max_length=1000)
    note: str | None = Field(default=None, max_length=1000)


class IncidentAlertLinkIn(BaseModel):
    """``POST /incidents/{id}/alerts`` 请求体。"""

    alert_id: str = Field(min_length=1, max_length=64)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_status(value: str) -> str:
    if value not in INCIDENT_STATUS_VALUES:
        raise HTTPException(status_code=422, detail="事件状态非法")
    return value


def _ensure_severity(value: str) -> str:
    if value not in INCIDENT_SEVERITY_VALUES:
        raise HTTPException(status_code=422, detail="事件严重度非法")
    return value


def _write_audit_log(db: Session, audit: dict[str, Any] | None, *, incident_id: str) -> None:
    if not audit:
        return
    try:
        create_log(
            db,
            user_id=audit["user_id"],
            level="info",
            action=audit["action"],
            detail=audit["detail"],
        )
    except Exception as exc:  # noqa: BLE001
        # 审计写入失败不得破坏主请求
        logger.warning("incident audit log failed incident_id={} err={}", incident_id, exc)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_incidents_endpoint(
    limit: int = Query(default=50, ge=1, le=100),
    status: str | None = Query(default=None),
    user: User = Depends(require_auth_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """返回当前用户的 incident 列表;可选按 status 过滤。"""
    if status is not None:
        _ensure_status(status)
    result = incident_service.list_incidents(db, user.id, limit=limit, status=status)
    return {"status": "ok", **result}


@router.post("")
async def create_incident_endpoint(
    body: IncidentCreateIn,
    user: User = Depends(require_auth_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """创建 incident;若 ``alert_id`` 存在且属于当前 user,自动 link。"""
    _ensure_severity(body.severity)
    try:
        result = incident_service.create_incident(
            db,
            user_id=user.id,
            title=body.title,
            summary=body.summary,
            severity=body.severity,
            alert_id=body.alert_id,
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.warning("incident_create persist failed user_id={} err={}", user.id, exc)
        raise HTTPException(status_code=503, detail="案件持久化失败")

    if result is None:
        # alert 不存在 / 非 owner
        raise HTTPException(status_code=404, detail="关联告警不存在")

    _write_audit_log(db, result.get("audit"), incident_id=result["incident"]["incident_id"])
    return {"status": "ok", **result}


@router.get("/{incident_id}")
async def get_incident_detail_endpoint(
    incident_id: str,
    event_limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(require_auth_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """返回 incident 完整 detail(linked_alerts + events);非 owner / 不存在 404。"""
    result = incident_service.get_incident_detail(
        db, user.id, incident_id, event_limit=event_limit
    )
    if result is None:
        raise HTTPException(status_code=404, detail="案件不存在")
    return {"status": "ok", **result}


@router.patch("/{incident_id}")
async def update_incident_endpoint(
    incident_id: str,
    body: IncidentUpdateIn,
    user: User = Depends(require_auth_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """更新 incident 字段;非 owner / 不存在 404。"""
    if body.status is not None:
        _ensure_status(body.status)
    if body.severity is not None:
        _ensure_severity(body.severity)
    # 没有任何字段提供,直接 422
    if (
        body.status is None
        and body.severity is None
        and body.title is None
        and body.summary is None
        and body.note is None
    ):
        raise HTTPException(status_code=422, detail="至少提供一个更新字段")

    try:
        result = incident_service.update_incident(
            db,
            user_id=user.id,
            incident_id=incident_id,
            status=body.status,
            severity=body.severity,
            title=body.title,
            summary=body.summary,
            note=body.note,
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.warning("incident_update persist failed incident_id={} err={}", incident_id, exc)
        raise HTTPException(status_code=503, detail="案件更新失败")

    if result is None:
        raise HTTPException(status_code=404, detail="案件不存在")

    _write_audit_log(db, result.get("audit"), incident_id=incident_id)
    return {"status": "ok", **result}


@router.post("/{incident_id}/alerts")
async def link_alert_endpoint(
    incident_id: str,
    body: IncidentAlertLinkIn,
    user: User = Depends(require_auth_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """把 alert 加入 incident;重复 link 幂等。"""
    try:
        result = incident_service.link_alert(
            db,
            user_id=user.id,
            incident_id=incident_id,
            alert_id=body.alert_id,
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.warning(
            "incident_link persist failed incident_id={} alert_id={} err={}",
            incident_id, body.alert_id, exc,
        )
        raise HTTPException(status_code=503, detail="告警关联失败")

    if result is None:
        # incident 不存在 / alert 不存在 / 非 owner 统一 404
        raise HTTPException(status_code=404, detail="案件或告警不存在")

    # 重复 link 幂等时不写 Log(避免重复审计)
    if not result.get("idempotent"):
        _write_audit_log(db, result.get("audit"), incident_id=incident_id)
    return {
        "status": "ok",
        "incident": result["incident"],
        "alert_count": result["alert_count"],
        "idempotent": result.get("idempotent", False),
    }


@router.delete("/{incident_id}/alerts/{alert_id}")
async def unlink_alert_endpoint(
    incident_id: str,
    alert_id: str,
    user: User = Depends(require_auth_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """软删除 link(``removed_at``);不删 alert_records。"""
    try:
        result = incident_service.unlink_alert(
            db,
            user_id=user.id,
            incident_id=incident_id,
            alert_id=alert_id,
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.warning(
            "incident_unlink persist failed incident_id={} alert_id={} err={}",
            incident_id, alert_id, exc,
        )
        raise HTTPException(status_code=503, detail="告警移出失败")

    if result is None:
        raise HTTPException(status_code=404, detail="案件或告警关联不存在")

    _write_audit_log(db, result.get("audit"), incident_id=incident_id)
    return {
        "status": "ok",
        "incident": result["incident"],
        "alert_count": result["alert_count"],
    }
