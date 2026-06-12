"""L4 OpenAI Moderation provider — the strategy-pattern twin of `client.py`.

`OpenAIModerationClient` is the standalone httpx-based implementation.
`OpenAIModerationProvider` is the same logic, but registered in
`server.services.llm_providers._PROVIDERS` so any caller that already
uses the project's LLMProvider registry can fetch a moderation strategy
the same way it fetches a chat-completion strategy.

Either path is acceptable; the L4 integration in `core.GuardrailEngine`
defaults to `OpenAIModerationClient` for direct, low-latency access.
"""
from __future__ import annotations

from typing import Any

from server.security.llm_guardrails.moderation.client import (
    DEFAULT_MODEL,
    OpenAIModerationClient,
)


class OpenAIModerationProvider:
    """Provider wrapper that conforms to the LLMProvider-style interface.

    Exposes ``name`` (registry key) and ``check(text)`` (the operation).
    Internally delegates to `OpenAIModerationClient` so the wire format
    is identical across both code paths.
    """

    name = "openai-moderation"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._client = OpenAIModerationClient(api_key=api_key, model=model)

    async def check(self, text: str) -> dict[str, Any]:
        """Run a single moderation call. See `OpenAIModerationClient.check`."""
        return await self._client.check(text)
