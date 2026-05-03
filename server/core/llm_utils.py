import json
import os
from typing import Any

from server.analyzer import AnalyzerConfig, build_chat_completions_url
from server.core.config import ALLOWED_AI_PROVIDERS, PROVIDER_MODEL_DEFAULTS, PROVIDER_BASE_URL_DEFAULTS, load_timeout_seconds
from server.security_utils import DecryptionError, decrypt_api_key


COPILOT_SYSTEM_PROMPT = (
    "你是企业级 Security Copilot。回答要专业、可执行、简洁，先给结论，再给证据与处置步骤。"
)


def normalize_ai_provider(value: str | None) -> str:
    provider = str(value or "").strip().lower()
    if provider not in ALLOWED_AI_PROVIDERS:
        return "custom"
    return provider


def infer_provider_from_base_url(base_url: str) -> str:
    normalized = str(base_url or "").strip().lower()
    if "anthropic.com" in normalized:
        return "claude"
    if "generativelanguage.googleapis.com" in normalized:
        return "gemini"
    if "x.ai" in normalized:
        return "grok"
    if "openai.com" in normalized:
        return "openai"
    return "custom"


def infer_provider_from_model(model_name: str) -> str:
    model = str(model_name or "").strip().lower()
    if model.startswith("claude"):
        return "claude"
    if model.startswith("gemini"):
        return "gemini"
    if model.startswith("grok"):
        return "grok"
    if model.startswith("gpt") or model.startswith("o"):
        return "openai"
    return "custom"


def choose_provider(preferred: str | None, model_name: str, base_url: str) -> str:
    normalized = normalize_ai_provider(preferred)
    # If user explicitly set a provider (not empty and not "custom"), respect it
    if preferred and str(preferred).strip().lower() not in {"", "custom"}:
        return normalized
    
    # If preferred is "custom", respect that choice too
    if normalized == "custom":
        return "custom"

    by_url = infer_provider_from_base_url(base_url)
    if by_url != "custom":
        return by_url

    by_model = infer_provider_from_model(model_name)
    if by_model != "custom":
        return by_model

    return "openai"


def user_config_to_llm_runtime(config, user) -> tuple[AnalyzerConfig, str]:
    try:
        api_key = decrypt_api_key(user.encrypted_api_key) or ""
    except DecryptionError:
        api_key = ""
    provider = choose_provider(getattr(config, "ai_provider", None), config.model, config.base_url)
    model = (config.model or PROVIDER_MODEL_DEFAULTS.get(provider, "")).strip()
    base_url = (config.base_url or PROVIDER_BASE_URL_DEFAULTS.get(provider, "")).strip().rstrip("/")

    runtime = AnalyzerConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=config.timeout_seconds,
    )
    return runtime, provider


def config_to_payload(config: AnalyzerConfig, ai_provider: str = "custom") -> dict[str, Any]:
    provider = choose_provider(ai_provider, config.model, config.base_url)
    return {
        "ai_provider": provider,
        "base_url": config.base_url,
        "model": config.model,
        "timeout_seconds": config.timeout_seconds,
        "has_api_key": bool(config.api_key),
    }


def _provider_headers(provider: str, api_key: str) -> dict[str, str]:
    if provider == "claude":
        return {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
    if provider == "gemini":
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }


def _test_request_body(provider: str, model: str) -> dict[str, Any]:
    if provider == "claude":
        return {
            "model": model,
            "system": "You are a network security assistant.",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "reply with pong"}]}],
            "max_tokens": 8,
            "temperature": 0,
        }
    if provider == "gemini":
        return {
            "contents": [{"role": "user", "parts": [{"text": "reply with pong"}]}],
            "generationConfig": {"temperature": 0},
        }
    return {
        "model": model,
        "messages": [{"role": "user", "content": "reply with pong"}],
        "temperature": 0,
        "max_tokens": 8,
    }


def _provider_test_endpoint(provider: str, runtime: AnalyzerConfig) -> str:
    normalized_base = runtime.base_url.rstrip("/")
    if provider == "claude":
        return f"{normalized_base}/v1/messages"
    if provider == "gemini":
        return f"{normalized_base}/v1beta/models/{runtime.model}:generateContent"
    return build_chat_completions_url(runtime.base_url)


def _extract_test_reply(provider: str, payload: dict[str, Any]) -> str:
    if provider == "claude":
        content_items = payload.get("content") or []
        if not content_items:
            return ""
        return str((content_items[0] or {}).get("text", "") or "").strip()
    if provider == "gemini":
        candidates = payload.get("candidates") or []
        if not candidates:
            return ""
        parts = ((candidates[0] or {}).get("content") or {}).get("parts") or []
        if not parts:
            return ""
        return str((parts[0] or {}).get("text", "") or "").strip()
    return str((payload.get("choices", [{}])[0] or {}).get("message", {}).get("content", "") or "").strip()


def _resolve_test_api_key(update: dict[str, Any], runtime: AnalyzerConfig) -> str:
    candidate = str(update.get("api_key", "")).strip()
    if candidate:
        return candidate

    if "api_key" in update:
        raise ValueError("api_key cannot be empty")

    return str(runtime.api_key).strip()
