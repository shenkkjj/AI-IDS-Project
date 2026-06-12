import json
from typing import Any, AsyncIterator

from fastapi import HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from server.analyzer import AnalyzerConfig
from server.core.config import COPILOT_RATE_LIMIT_WINDOW, COPILOT_RATE_LIMIT_MAX
from server.core.database import create_log
from server.core.llm_utils import user_config_to_llm_runtime
from server.core.state import app_state
from server.models.schemas import CopilotMessageIn, CopilotStreamIn
from server.models_db import User
from server.services.llm_providers import (
    resolve_provider,
    sse_done,
    sse_error,
    stream_completion,
)


def _build_context_from_alert(alert: dict[str, Any] | None) -> str:
    if not alert:
        return ""

    raw_alert = alert.get("raw_alert") or {}
    llm_analysis = alert.get("llm_analysis") or {}
    lines = [
        "[当前选中告警上下文]",
        f"alert_id: {alert.get('alert_id', '')}",
        f"source_ip: {raw_alert.get('source_ip', '')}",
        f"destination_ip: {raw_alert.get('destination_ip', '')}",
        f"timestamp: {raw_alert.get('timestamp', '')}",
        f"model_probability: {raw_alert.get('model_probability', '')}",
        f"blocked: {raw_alert.get('blocked', False)}",
        f"payload: {raw_alert.get('payload', '')}",
        f"existing_risk_level: {llm_analysis.get('risk_level', '')}",
        f"existing_summary: {llm_analysis.get('summary', '')}",
        "请基于这条告警给出专业安全分析和可执行防御建议，优先给出立即动作。",
    ]
    return "\n".join(lines)


async def stream_user_chat_completion(
    *,
    runtime: AnalyzerConfig,
    provider: str,
    user_message: str,
    context_block: str,
    history: list[CopilotMessageIn],
) -> AsyncIterator[str]:
    """Stream a chat completion from the chosen LLM provider.

    Dispatches to the provider strategy in `server.services.llm_providers`.
    New providers can be added without touching this function.
    """
    if not runtime.api_key or not runtime.base_url:
        yield sse_error("请先在配置页设置可用的 API Key 与 Base URL")
        return

    strategy = resolve_provider(provider)
    try:
        async for token in stream_completion(
            strategy,
            runtime,
            user_message=user_message,
            context_block=context_block,
            history=history,
        ):
            yield token
        yield sse_done(provider, runtime.model)
    except Exception as exc:
        logger.exception(
            "copilot stream failed provider={} model={} err_type={}",
            provider, runtime.model, type(exc).__name__,
        )
        yield sse_error("AI 服务暂时不可用，请稍后重试")


async def copilot_stream(user: User, data: CopilotStreamIn, client_ip: str, db: Session) -> AsyncIterator[str]:
    async with app_state.rate_limit.copilot_lock:
        if not app_state.rate_limit._check_rate_limit(app_state.rate_limit.copilot_attempts, client_ip, COPILOT_RATE_LIMIT_WINDOW, COPILOT_RATE_LIMIT_MAX):  # noqa: E501
            raise HTTPException(status_code=429, detail="Copilot请求过于频繁，请1分钟后再试")

    from server.services.user_service import get_or_create_user_config
    config = get_or_create_user_config(db, user.id)
    runtime, provider = user_config_to_llm_runtime(config, user)

    alert: dict[str, Any] | None = None
    if data.alert_id:
        from server.services.alert_service import find_alert_by_id
        alert = await find_alert_by_id(str(data.alert_id).strip(), user_id=user.id)

    context_block = _build_context_from_alert(alert)

    create_log(
        db,
        user_id=user.id,
        level="info",
        action="copilot_stream",
        detail=f"provider={provider};model={runtime.model};alert_id={data.alert_id or ''}",
    )

    async for chunk in stream_user_chat_completion(
        runtime=runtime,
        provider=provider,
        user_message=str(data.message).strip(),
        context_block=context_block,
        history=data.history,
    ):
        yield chunk
