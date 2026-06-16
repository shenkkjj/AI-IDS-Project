from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.core.security import get_current_user, require_alert_ingest_token, require_auth_user
from server.core.database import SessionLocal, get_db
from server.core.state import app_state
from server.core.websocket import manager
from server.models.schemas import AlertIn
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
