"""LLM provider strategy pattern.

Each provider (OpenAI-compatible, Claude, Gemini) has:
- a request body shape
- an endpoint URL pattern
- a response-token extractor

Adding a new provider means writing one `LLMProvider` subclass — the copilot
service dispatches via `_resolve_provider()` and never branches on the
provider name itself.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

import httpx
from loguru import logger

from server.analyzer import AnalyzerConfig, build_chat_completions_url
from server.core.llm_utils import COPILOT_SYSTEM_PROMPT, _provider_headers
from server.models.schemas import CopilotMessageIn


# ---- shared SSE helpers ----

def sse_pack(text: str) -> str:
    return f"data: {json.dumps({'token': text}, ensure_ascii=False)}\n\n"


def sse_error(text: str) -> str:
    return f"event: error\ndata: {json.dumps({'message': text}, ensure_ascii=False)}\n\n"


def sse_done(provider: str, model_name: str) -> str:
    return f"event: done\ndata: {json.dumps({'provider': provider, 'model': model_name}, ensure_ascii=False)}\n\n"


def _sanitize_user_input(text: str) -> str:
    if not text:
        return text
    import re
    patterns = [
        r"(?i)ignore\s+previous\s+instructions",
        r"(?i)disregard\s+.*system\s+prompt",
        r"(?i)forget\s+.*instructions",
        r"(?i)system\s*:\s*",
        r"(?i)you\s+are\s+now\s+",
        r"<\s*script\b",
        r"javascript\s*:",
    ]
    sanitized = text
    for pat in patterns:
        sanitized = re.sub(pat, "[FILTERED]", sanitized)
    return sanitized


# ---- strategy base ----

class LLMProvider(ABC):
    """One concrete LLM provider strategy."""

    name: str

    @abstractmethod
    def endpoint(self, runtime: AnalyzerConfig) -> str: ...

    @abstractmethod
    def request_body(
        self,
        runtime: AnalyzerConfig,
        user_message: str,
        context_block: str,
        history: list[CopilotMessageIn],
    ) -> dict[str, Any]: ...

    @abstractmethod
    def extract_delta(self, payload: dict[str, Any]) -> str: ...


# ---- OpenAI-compatible ----

class OpenAICompatibleProvider(LLMProvider):
    name = "openai"

    def endpoint(self, runtime: AnalyzerConfig) -> str:
        return build_chat_completions_url(runtime.base_url)

    def request_body(
        self,
        runtime: AnalyzerConfig,
        user_message: str,
        context_block: str,
        history: list[CopilotMessageIn],
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": COPILOT_SYSTEM_PROMPT}
        ]
        for item in history:
            messages.append({"role": item.role, "content": _sanitize_user_input(item.content)})
        user_content = _sanitize_user_input(user_message)
        if context_block:
            user_content = f"{user_content}\n\n{context_block}"
        messages.append({"role": "user", "content": user_content})
        return {
            "model": runtime.model,
            "messages": messages,
            "temperature": 0.2,
            "stream": True,
        }

    def extract_delta(self, payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            return ""
        return str((choices[0] or {}).get("delta", {}).get("content", "") or "")


# ---- Claude ----

class ClaudeProvider(LLMProvider):
    name = "claude"

    def endpoint(self, runtime: AnalyzerConfig) -> str:
        return f"{runtime.base_url.rstrip('/')}/v1/messages"

    def request_body(
        self,
        runtime: AnalyzerConfig,
        user_message: str,
        context_block: str,
        history: list[CopilotMessageIn],
    ) -> dict[str, Any]:
        # Claude expects a top-level `system` and only user/assistant messages
        # in the `messages` array.
        messages: list[dict[str, str]] = []
        for item in history:
            messages.append({"role": item.role, "content": _sanitize_user_input(item.content)})
        user_content = _sanitize_user_input(user_message)
        if context_block:
            user_content = f"{user_content}\n\n{context_block}"
        messages.append({"role": "user", "content": user_content})
        return {
            "model": runtime.model,
            "system": COPILOT_SYSTEM_PROMPT,
            "messages": messages,
            "max_tokens": 2048,
            "temperature": 0.2,
            "stream": True,
        }

    def extract_delta(self, payload: dict[str, Any]) -> str:
        if payload.get("type") != "content_block_delta":
            return ""
        return str(payload.get("delta", {}).get("text", "") or "")


# ---- Gemini ----

class GeminiProvider(LLMProvider):
    name = "gemini"

    def endpoint(self, runtime: AnalyzerConfig) -> str:
        return (
            f"{runtime.base_url.rstrip('/')}/v1beta/models/{runtime.model}"
            f":streamGenerateContent?alt=sse"
        )

    def request_body(
        self,
        runtime: AnalyzerConfig,
        user_message: str,
        context_block: str,
        history: list[CopilotMessageIn],
    ) -> dict[str, Any]:
        contents: list[dict[str, Any]] = []
        for item in history:
            role = "model" if item.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": _sanitize_user_input(item.content)}]})
        user_content = _sanitize_user_input(user_message)
        if context_block:
            user_content = f"{user_content}\n\n{context_block}"
        contents.append({"role": "user", "parts": [{"text": user_content}]})
        return {
            "system_instruction": {"parts": [{"text": COPILOT_SYSTEM_PROMPT}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.2},
        }

    def extract_delta(self, payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates") or []
        if not candidates:
            return ""
        content = (candidates[0] or {}).get("content") or {}
        parts = content.get("parts") or []
        if not parts:
            return ""
        return str((parts[0] or {}).get("text", "") or "").strip()


# ---- registry / factory ----

_PROVIDERS: dict[str, LLMProvider] = {
    "openai": OpenAICompatibleProvider(),
    "custom": OpenAICompatibleProvider(),  # custom endpoints speak OpenAI dialect
    "claude": ClaudeProvider(),
    "gemini": GeminiProvider(),
    "grok": OpenAICompatibleProvider(),  # Grok is OpenAI-compatible
}


def resolve_provider(name: str) -> LLMProvider:
    """Return the strategy for `name`, falling back to OpenAI-compatible."""
    return _PROVIDERS.get(name, _PROVIDERS["openai"])


def register_provider(name: str, provider: LLMProvider) -> None:
    """Plugin a new strategy at runtime."""
    _PROVIDERS[name] = provider


# ---- streaming dispatcher ----

async def stream_completion(
    provider: LLMProvider,
    runtime: AnalyzerConfig,
    *,
    user_message: str,
    context_block: str,
    history: list[CopilotMessageIn],
) -> AsyncIterator[str]:
    """Iterate SSE tokens from the chosen provider, normalizing deltas."""
    endpoint = provider.endpoint(runtime)
    body = provider.request_body(runtime, user_message, context_block, history)
    headers = _provider_headers(provider.name, runtime.api_key)
    timeout = httpx.Timeout(connect=8.0, read=120.0, write=30.0, pool=20.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", endpoint, headers=headers, json=body) as response:
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
                token = provider.extract_delta(payload)
                if token:
                    yield sse_pack(token)
