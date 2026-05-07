from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request

from server.core.utils import _is_url_pointing_to_internal
from server.core.security import require_auth_user
from server.models_db import User
from server.services import notification_service

router = APIRouter(prefix="/notify", tags=["通知"])


@router.post("/webhook/test")
async def test_webhook(
    request: Request,
    webhook_url: str = "",
    webhook_type: str = "generic",
    user: User = Depends(require_auth_user),
) -> dict[str, Any]:
    if not webhook_url.strip():
        return {"status": "skipped", "detail": "no webhook url provided"}

    parsed = urlparse(webhook_url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=422, detail="webhook URL 必须以 http 或 https 开头")
    if _is_url_pointing_to_internal(webhook_url.strip()):
        raise HTTPException(status_code=422, detail="webhook URL 不允许指向内网地址")

    test_payload = {
        "title": "CyberSentinel 通知测试",
        "text": "如果你收到这条消息，说明 webhook 配置正确。",
        "risk_level": "info",
    }
    if webhook_type == "dingtalk":
        test_payload = {
            "msgtype": "markdown",
            "markdown": {"title": "CyberSentinel 测试", "text": "通知测试成功"},
        }

    ok = await notification_service.send_webhook(webhook_url.strip(), test_payload)
    return {"status": "sent" if ok else "failed", "webhook_url": webhook_url[:80]}
