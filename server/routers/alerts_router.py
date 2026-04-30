from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from server.core.database import get_db, SessionLocal
from server.core.security import get_current_user, require_alert_ingest_token, require_auth_user
from server.core.state import app_state
from server.core.websocket import manager
from server.models.schemas import AlertIn
from server.models_db import User
from server.services import alert_service

router = APIRouter(prefix="/alerts", tags=["告警"])


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


@router.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket) -> None:
    token = websocket.headers.get("authorization")
    cookie_text = websocket.headers.get("cookie", "")
    access_token_cookie: str | None = None

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
