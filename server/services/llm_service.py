import time
from typing import Any

import httpx
from fastapi import HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from server.analyzer import AnalyzerConfig
from server.core.config import LLM_RATE_LIMIT_WINDOW, LLM_RATE_LIMIT_MAX
from server.core.database import create_log
from server.core.llm_utils import (
    choose_provider,
    _provider_headers,
    _provider_test_endpoint,
    _test_request_body,
    _extract_test_reply,
)
from server.core.security import _safe_decrypt
from server.core.state import app_state
from server.models.schemas import LLMConfigIn
from server.models_db import User


_llm_config_lock = app_state.rate_limit.llm_lock


async def get_runtime_llm_config() -> AnalyzerConfig:
    from server.main import _llm_config
    async with _llm_config_lock:
        return _llm_config


async def update_runtime_llm_config(data: LLMConfigIn) -> AnalyzerConfig:
    from server.main import _llm_config
    global _llm_config

    update = data.model_dump(exclude_none=True)
    if not update:
        raise HTTPException(status_code=400, detail="No config fields provided")

    async with _llm_config_lock:
        current = _llm_config

        api_key = current.api_key
        if "api_key" in update:
            api_key = str(update["api_key"]).strip()

        base_url = current.base_url
        if "base_url" in update:
            base_url = str(update["base_url"]).strip().rstrip("/")
            from server.core.utils import _is_url_pointing_to_internal
            if base_url and _is_url_pointing_to_internal(base_url):
                raise HTTPException(status_code=422, detail="base_url 不允许指向内网地址")

        model = current.model
        if "model" in update:
            model = str(update["model"]).strip() or current.model

        timeout_seconds = current.timeout_seconds
        if "timeout_seconds" in update:
            try:
                timeout_seconds = int(update["timeout_seconds"])
            except (ValueError, TypeError):
                raise HTTPException(status_code=422, detail="timeout_seconds must be an integer")

        provider = choose_provider(str(update.get("ai_provider", "custom")), model, base_url)
        if not base_url:
            from server.core.config import PROVIDER_BASE_URL_DEFAULTS
            base_url = PROVIDER_BASE_URL_DEFAULTS[provider]
        if not model:
            from server.core.config import PROVIDER_MODEL_DEFAULTS
            model = PROVIDER_MODEL_DEFAULTS[provider]

        if timeout_seconds < 1 or timeout_seconds > 300:
            raise HTTPException(status_code=422, detail="timeout_seconds must be in 1..300")

        new_config = AnalyzerConfig(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
        )

        _llm_config = new_config
        return new_config


async def test_llm_connection_by_provider(config: AnalyzerConfig, provider: str) -> dict[str, Any]:
    if not config.api_key or not config.base_url:
        raise ValueError("缺少 API Key 或 Base URL")

    if config.timeout_seconds < 1 or config.timeout_seconds > 300:
        raise ValueError("timeout_seconds 必须在 1-300 之间")

    endpoint = _provider_test_endpoint(provider, config)
    request_body = _test_request_body(provider, config.model)
    headers = _provider_headers(provider, config.api_key)

    started_at = time.time()
    try:
        async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
            response = await client.post(endpoint, headers=headers, json=request_body)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise ValueError(f"连接超时 ({config.timeout_seconds}s): {exc}")
    except httpx.HTTPStatusError as exc:
        raise ValueError(f"API 返回错误: HTTP {exc.response.status_code}")
    except httpx.RequestError as exc:
        raise ValueError(f"请求失败: {exc}")

    response_json = response.json()
    content = _extract_test_reply(provider, response_json)
    latency_ms = int((time.time() - started_at) * 1000)

    return {
        "ok": True,
        "latency_ms": latency_ms,
        "reply": content,
        "model": config.model,
        "base_url": config.base_url,
    }


async def test_llm_config(data: LLMConfigIn, user: User, request, db: Session) -> dict[str, Any]:
    from server.core.utils import _get_client_ip
    client_ip = _get_client_ip(request)
    async with app_state.rate_limit.llm_lock:
        if not app_state.rate_limit._check_rate_limit(app_state.rate_limit.llm_attempts, client_ip, LLM_RATE_LIMIT_WINDOW, LLM_RATE_LIMIT_MAX):  # noqa: E501
            raise HTTPException(status_code=429, detail="LLM测试请求过于频繁，请1分钟后再试")

    update = data.model_dump(exclude_none=True)
    from server.services.user_service import get_or_create_user_config
    config = get_or_create_user_config(db, user.id)
    decrypted_key = _safe_decrypt(user.encrypted_api_key) or ""

    provider = choose_provider(
        str(update.get("ai_provider", config.ai_provider)),
        str(update.get("model", config.model)),
        str(update.get("base_url", config.base_url)),
    )

    model = str(update.get("model", config.model)).strip() or config.model
    base_url = str(update.get("base_url", config.base_url)).strip() or config.base_url
    timeout_seconds = int(update.get("timeout_seconds", config.timeout_seconds))

    api_key = decrypted_key
    if "api_key" in update:
        api_key = str(update["api_key"] or "").strip() or decrypted_key

    test_config = AnalyzerConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
    )

    logger.info(
        "[LLM_TEST] user_id={} provider={} model={} base_url={} has_api_key={}",
        user.id, provider, test_config.model,
        test_config.base_url[:30] + "..." if len(test_config.base_url) > 30 else test_config.base_url,
        bool(test_config.api_key),
    )

    if not test_config.api_key or not test_config.base_url:
        raise HTTPException(status_code=400, detail="API Key 和 Base URL 不能为空")

    if test_config.timeout_seconds < 1 or test_config.timeout_seconds > 300:
        raise HTTPException(status_code=422, detail="timeout_seconds 必须在 1-300 之间")

    from urllib.parse import urlparse
    parsed_base = urlparse(test_config.base_url)
    if parsed_base.scheme not in {"http", "https"} or not parsed_base.netloc:
        raise HTTPException(status_code=422, detail="Base URL 格式无效")

    from server.core.utils import _is_url_pointing_to_internal
    if _is_url_pointing_to_internal(test_config.base_url):
        raise HTTPException(status_code=422, detail="base_url 不允许指向内网地址")

    try:
        result = await test_llm_connection_by_provider(test_config, provider)
        logger.info("[LLM_TEST] success user_id={} result={}", user.id, result)
        create_log(
            db,
            user_id=user.id,
            level="info",
            action="llm_test",
            detail=f"provider={provider};model={test_config.model}",
        )
        return {"status": "ok", "provider": provider, "result": result}
    except httpx.TimeoutException as exc:
        logger.warning("[LLM_TEST] timeout user_id={} base_url={} exc={}", user.id, test_config.base_url, exc)
        raise HTTPException(status_code=400, detail="连接超时，请检查网络或 Base URL 是否可达，或增加超时时间") from exc
    except httpx.ConnectError as exc:
        logger.warning("[LLM_TEST] connect_error user_id={} base_url={} exc={}", user.id, test_config.base_url, exc)
        raise HTTPException(status_code=400, detail="无法连接到服务器，请检查 Base URL") from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("[LLM_TEST] http_error user_id={} status={} body={}", user.id, exc.response.status_code, exc.response.text[:200])  # noqa: E501
        raise HTTPException(status_code=400, detail=f"服务器返回错误 ({exc.response.status_code})，请检查 API Key 和模型名称") from exc
    except Exception as exc:
        logger.warning("[LLM_TEST] failure user_id={} exc_type={} exc={}", user.id, type(exc).__name__, exc)
        raise HTTPException(status_code=400, detail="LLM 连接测试失败，请检查配置") from exc
