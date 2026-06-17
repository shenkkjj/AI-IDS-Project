from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.core.security import get_current_user, require_alert_ingest_token, require_auth_user
from server.core.database import SessionLocal, create_log, get_db
from server.core.state import app_state
from server.core.websocket import manager
from server.models.schemas import AlertIn, AlertTriageUpdateIn
from server.models_db import User
from server.services import alert_service
from server.services.alert_service import DEMO_ATTACK_SCENARIOS

router = APIRouter(prefix="/alerts", tags=["告警"])


class DemoAttackIn(BaseModel):
    scenario: Literal["sql_injection", "xss", "scanner"] = "sql_injection"


@router.post("")
async def receive_alert(
    alert: AlertIn,
    request: Request,
    _: None = Depends(require_alert_ingest_token),
) -> dict[str, Any]:
    try:
        return await alert_service.receive_alert(alert, request)
    except Exception as exc:
        raise HTTPException(status_code=403 if "not allowed" in str(exc) else 503, detail=str(exc))


@router.get("")
async def get_alerts(
    limit: int = 100,
    user: User = Depends(require_auth_user),
) -> dict[str, Any]:
    return await alert_service.get_alerts(user.id, limit)


@router.patch("/{alert_id}/triage")
async def update_alert_triage(
    alert_id: str,
    data: AlertTriageUpdateIn,
    user: User = Depends(require_auth_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """更新指定告警的研判状态。

    - 仅告警所有者可更新;非 owner / 不存在统一返回 404,
      避免通过 403 暴露 alert_id 是否存在。
    - 无效 status / 超长 note 由 Pydantic 在进入 handler 前返回 422。
    - 审计日志 ``Log(action="alert_triage_update")`` 记录脱敏摘要;
      写入失败不得破坏主请求。
    """

    result = await alert_service.update_alert_triage(
        user_id=user.id,
        alert_id=alert_id,
        data=data,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    # 审计:写脱敏摘要。失败保护:仅 warn,不抛。
    audit = result["audit"]
    try:
        create_log(
            db,
            user_id=audit["user_id"],
            level="info",
            action=audit["action"],
            detail=audit["detail"],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("alert_triage_update audit log failed alert_id={} err={}", alert_id, exc)

    return {
        "status": "ok",
        "alert_id": alert_id,
        "triage": result["triage"],
        "alert": result["alert"],
    }


@router.post("/demo")
async def trigger_demo_attack(
    data: DemoAttackIn,
    user: User = Depends(require_auth_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if data.scenario not in DEMO_ATTACK_SCENARIOS:
        raise HTTPException(status_code=422, detail="Unknown demo scenario")

    payload = await alert_service.trigger_demo_attack(user_id=user.id, scenario=data.scenario)
    # SOC 时间线事件：写 Log 让 ``/logs/security-timeline`` 能渲染 demo 攻击。
    # 失败保护：主请求不能因为 Log 写入失败而失败。
    try:
        from server.core.database import create_log
        create_log(
            db,
            user_id=user.id,
            level="info",
            action="demo_attack",
            detail=f"scenario={data.scenario};alert_id={payload['alert_id']}",
        )
    except Exception:  # noqa: BLE001
        # loguru 已经在内部 log 过；这里只保证主请求不被破坏。
        pass
    return {
        "status": "ok",
        "scenario": data.scenario,
        "alert": payload,
        "copilot": alert_service.build_demo_copilot_state(user, db),
    }


@router.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket) -> None:
    # 支持多种认证方式：header、cookie、URL query param
    token = websocket.headers.get("authorization")
    cookie_text = websocket.headers.get("cookie", "")
    access_token_cookie: str | None = None

    query_token = websocket.query_params.get("token")
    if query_token:
        token = f"Bearer {query_token}"

    try:
        from http.cookies import SimpleCookie
        cookie = SimpleCookie()
        cookie.load(cookie_text)
        if "access_token" in cookie:
            access_token_cookie = cookie["access_token"].value or None
    except Exception:
        access_token_cookie = None

    with SessionLocal() as db:
        user: User | None = None
        try:
            user = get_current_user(db, access_token_cookie, token)
        except HTTPException:
            await websocket.close(code=1008)
            return

    if user is None:
        await websocket.close(code=1008)
        return
    await manager.connect(user.id, websocket)
    try:
        backlog = await app_state.alert.get_backlog_snapshot()
        for item in backlog:
            if (item.get("raw_alert") or {}).get("alert_user_id") == user.id:
                await websocket.send_json(item)

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(user.id, websocket)
    except Exception as exc:
        await manager.disconnect(user.id, websocket)
        from loguru import logger
        logger.warning("WebSocket closed with error: {}", exc)
