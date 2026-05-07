from typing import Any

import httpx
from loguru import logger


async def send_webhook(url: str, payload: dict[str, Any], timeout: float = 10.0) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
            if resp.status_code < 400:
                logger.info("webhook sent ok status={} url={}", resp.status_code, url[:60])
                return True
            logger.warning("webhook failed status={} url={}", resp.status_code, url[:60])
            return False
    except Exception as exc:
        logger.warning("webhook error url={} err={}", url[:60], exc)
        return False


def build_alert_webhook_payload(alert: dict[str, Any], webhook_type: str = "generic") -> dict[str, Any]:
    raw = alert.get("raw_alert") or {}
    llm = alert.get("llm_analysis") or {}
    risk = llm.get("risk_level", "unknown")
    summary = llm.get("summary", "无摘要")

    base = {
        "title": f"[{risk.upper()}] CyberSentinel 高危告警",
        "text": f"**来源**: {raw.get('source_ip', 'unknown')} → {raw.get('destination_ip', 'unknown')}\n"
                f"**载荷**: {raw.get('payload', '')}\n"
                f"**摘要**: {summary}\n"
                f"**已拦截**: {'是' if raw.get('blocked') else '否'}",
        "risk_level": risk,
        "alert_id": alert.get("alert_id", ""),
    }

    if webhook_type == "dingtalk":
        return {
            "msgtype": "markdown",
            "markdown": {"title": base["title"], "text": base["text"]},
        }
    if webhook_type == "feishu":
        return {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": base["title"]}},
                "elements": [{"tag": "markdown", "content": base["text"]}],
            },
        }
    return base


async def notify_critical_alert(
    alert: dict[str, Any],
    webhook_url: str,
    webhook_type: str = "generic",
) -> bool:
    payload = build_alert_webhook_payload(alert, webhook_type)
    return await send_webhook(webhook_url, payload)
