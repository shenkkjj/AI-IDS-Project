import json
from typing import Any, AsyncIterator

import httpx
from fastapi import HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from server.analyzer import AnalyzerConfig
from server.core.config import COPILOT_RATE_LIMIT_WINDOW, COPILOT_RATE_LIMIT_MAX
from server.core.database import create_log
from server.core.llm_utils import (
    choose_provider,
    COPILOT_SYSTEM_PROMPT,
    _provider_headers,
    user_config_to_llm_runtime,
)
from server.core.state import app_state
from server.models.schemas import CopilotMessageIn, CopilotStreamIn
from server.models_db import User


def _build_openai_messages(user_message: str, context_block: str, history: list[CopilotMessageIn]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": COPILOT_SYSTEM_PROMPT}]
    for item in history:
        messages.append({"role": item.role, "content": item.content})

    user_content = user_message
    if context_block:
        user_content = f"{user_message}\n\n{context_block}"
    messages.append({"role": "user", "content": user_content})
    return messages


def _build_gemini_contents(user_message: str, context_block: str, history: list[CopilotMessageIn]) -> list[dict[str, Any]]:
    contents: list[dict[str, Any]] = []
    for item in history:
        role = "model" if item.role == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": item.content}]})

    user_content = user_message
    if context_block:
        user_content = f"{user_message}\n\n{context_block}"
    contents.append({"role": "user", "parts": [{"text": user_content}]})
    return contents


def _extract_openai_delta(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not choices:
        return ""
    return str((choices[0] or {}).get("delta", {}).get("content", "") or "")


def _extract_claude_delta(payload: dict[str, Any]) -> str:
    if payload.get("type") != "content_block_delta":
        return ""
    return str(payload.get("delta", {}).get("text", "") or "")


def _extract_gemini_delta(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    content = (candidates[0] or {}).get("content") or {}
    parts = content.get("parts") or []
    if not parts:
        return ""
    return str((parts[0] or {}).get("text", "") or "").strip()


def _sse_pack(text: str) -> str:
    return f"data: {json.dumps({'token': text}, ensure_ascii=False)}\n\n"


def _sse_error(text: str) -> str:
    return f"event: error\ndata: {json.dumps({'message': text}, ensure_ascii=False)}\n\n"


def _sse_done(provider: str, model_name: str) -> str:
    payload = {"provider": provider, "model": model_name}
    return f"event: done\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


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
    if not runtime.api_key or not runtime.base_url:
        yield _sse_error("请先在配置页设置可用的 API Key 与 Base URL")
        return

    timeout = httpx.Timeout(connect=8.0, read=120.0, write=30.0, pool=20.0)

    try:
        if provider == "claude":
            endpoint = f"{runtime.base_url.rstrip('/')}/v1/messages"
            request_body = {
                "model": runtime.model,
                "system": COPILOT_SYSTEM_PROMPT,
                "messages": _build_openai_messages(user_message, context_block, history)[1:],
                "max_tokens": 2048,
                "temperature": 0.2,
                "stream": True,
            }
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", endpoint, headers=_provider_headers(provider, runtime.api_key), json=request_body) as response:
                    response.raise_for_status()
                    async for raw_line in response.aiter_lines():
                        line = str(raw_line or "").strip()
                        if not line.startswith("data:"):
                            continue
                        payload_text = line[5:].strip()
                        if payload_text == "[DONE]":
                            break
                        try:
                            payload = json.loads(payload_text)
                        except Exception:
                            continue
                        token = _extract_claude_delta(payload)
                        if token:
                            yield _sse_pack(token)

        elif provider == "gemini":
            endpoint = (
                f"{runtime.base_url.rstrip('/')}/v1beta/models/{runtime.model}:streamGenerateContent"
                f"?alt=sse"
            )
            request_body = {
                "system_instruction": {"parts": [{"text": COPILOT_SYSTEM_PROMPT}]},
                "contents": _build_gemini_contents(user_message, context_block, history),
                "generationConfig": {"temperature": 0.2},
            }
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", endpoint, headers=_provider_headers(provider, runtime.api_key), json=request_body) as response:
                    response.raise_for_status()
                    async for raw_line in response.aiter_lines():
                        line = str(raw_line or "").strip()
                        if not line.startswith("data:"):
                            continue
                        payload_text = line[5:].strip()
                        if payload_text == "[DONE]":
                            break
                        try:
                            payload = json.loads(payload_text)
                        except Exception:
                            continue
                        token = _extract_gemini_delta(payload)
                        if token:
                            yield _sse_pack(token)

        else:
            from server.analyzer import build_chat_completions_url
            endpoint = build_chat_completions_url(runtime.base_url)
            request_body = {
                "model": runtime.model,
                "messages": _build_openai_messages(user_message, context_block, history),
                "temperature": 0.2,
                "stream": True,
            }
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", endpoint, headers=_provider_headers(provider, runtime.api_key), json=request_body) as response:
                    response.raise_for_status()
                    async for raw_line in response.aiter_lines():
                        line = str(raw_line or "").strip()
                        if not line or not line.startswith("data:"):
                            continue
                        payload_text = line[5:].strip()
                        if payload_text == "[DONE]":
                            break
                        try:
                            payload = json.loads(payload_text)
                        except Exception:
                            continue
                        token = _extract_openai_delta(payload)
                        if token:
                            yield _sse_pack(token)

        yield _sse_done(provider, runtime.model)
    except Exception as exc:
        logger.exception("copilot stream failed provider={} model={} err_type={}", provider, runtime.model, type(exc).__name__)
        yield _sse_error("AI 服务暂时不可用，请稍后重试")


async def copilot_stream(user: User, data: CopilotStreamIn, client_ip: str, db: Session) -> AsyncIterator[str]:
    async with app_state.rate_limit.copilot_lock:
        if not app_state.rate_limit._check_rate_limit(app_state.rate_limit.copilot_attempts, client_ip, COPILOT_RATE_LIMIT_WINDOW, COPILOT_RATE_LIMIT_MAX):
            raise HTTPException(status_code=429, detail="Copilot请求过于频繁，请1分钟后再试")

    from server.services.user_service import get_or_create_user_config
    config = get_or_create_user_config(db, user.id)
    runtime, provider = user_config_to_llm_runtime(config, user)

    alert: dict[str, Any] | None = None
    if data.alert_id:
        from server.services.alert_service import find_alert_by_id
        alert = find_alert_by_id(str(data.alert_id).strip(), user_id=user.id)

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
