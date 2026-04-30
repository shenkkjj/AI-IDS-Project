from typing import Any

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from server.core.database import get_db
from server.core.security import get_current_user
from server.core.utils import _get_client_ip
from server.models.schemas import CopilotStreamIn, ThreatConfirmIn
from server.models_db import User
from server.services import copilot_service
from server.services.alert_service import find_alert_by_id, append_new_threat_csv
from server.core.database import create_log
from server.core.utils import _sanitize_for_log

router = APIRouter(tags=["Copilot"])


@router.post("/copilot/stream")
async def copilot_stream_route(
    data: CopilotStreamIn,
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    user = get_current_user(db, access_token_cookie, authorization)
    client_ip = _get_client_ip(request)

    async def event_generator():
        async for chunk in copilot_service.copilot_stream(user, data, client_ip, db):
            yield chunk

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/threats/confirm")
async def post_threat_confirm(
    data: ThreatConfirmIn,
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)

    alert = find_alert_by_id(data.alert_id, user_id=user.id)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert_id not found")

    await append_new_threat_csv(alert, data.label)
    create_log(db, user_id=user.id, level="info", action="threat_confirm", detail=f"{data.alert_id}:{_sanitize_for_log(data.label)}")
    return {
        "status": "ok",
        "saved_to": "new_threats.csv",
        "alert_id": data.alert_id,
        "label": data.label,
    }
