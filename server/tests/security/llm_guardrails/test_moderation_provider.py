"""Unit tests for `server.security.llm_guardrails.moderation.provider`.

The `OpenAIModerationProvider` is the strategy-pattern twin of the
standalone `OpenAIModerationClient`. It is registered into
`server.services.llm_providers._PROVIDERS` so callers using the
project's LLMProvider registry can fetch a moderation strategy the
same way they fetch a chat-completion strategy.
"""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from server.security.llm_guardrails.moderation.provider import OpenAIModerationProvider


class _MockTransport(httpx.AsyncBaseTransport):
    def __init__(self, *, status_code: int, payload: dict[str, Any]) -> None:
        self._status_code = status_code
        self._payload = payload

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=self._status_code,
            content=json.dumps(self._payload).encode(),
            headers={"content-type": "application/json"},
        )


@pytest.mark.asyncio
async def test_provider_name_is_openai_moderation() -> None:
    provider = OpenAIModerationProvider(api_key="sk-test")
    assert provider.name == "openai-moderation"


@pytest.mark.asyncio
async def test_provider_check_delegates_to_client() -> None:
    """`OpenAIModerationProvider.check` must return the same shape as
    the underlying client (`{flagged, categories}`).
    """
    transport = _MockTransport(
        status_code=200,
        payload={"results": [{"flagged": True, "categories": {"hate": True}}]},
    )
    provider = OpenAIModerationProvider(
        api_key="sk-test", model="omni-moderation-latest",
    )
    # Patch the inner client to use our mock transport.
    provider._client.__init__(  # type: ignore[attr-defined]
        api_key="sk-test", model="omni-moderation-latest", _transport=transport,
    )
    result = await provider.check("hateful text")
    assert result["flagged"] is True
    assert result["categories"]["hate"] is True


@pytest.mark.asyncio
async def test_provider_check_passes_through_clean_text() -> None:
    transport = _MockTransport(
        status_code=200,
        payload={"results": [{"flagged": False, "categories": {}}]},
    )
    provider = OpenAIModerationProvider(
        api_key="sk-test", model="omni-moderation-latest",
    )
    provider._client.__init__(  # type: ignore[attr-defined]
        api_key="sk-test", model="omni-moderation-latest", _transport=transport,
    )
    result = await provider.check("hello world")
    assert result["flagged"] is False


@pytest.mark.asyncio
async def test_provider_default_model() -> None:
    """Constructor should default to omni-moderation-latest."""
    provider = OpenAIModerationProvider(api_key="sk-test")
    assert provider._client._model == "omni-moderation-latest"
