"""L4 OpenAI Moderation client (independent of `server.services.llm_providers`).

This client is the stand-alone `httpx`-based implementation. It is also
re-exported as `OpenAIModerationProvider` in `provider.py` for callers that
prefer the strategy pattern. Both paths use the same wire format.

Why a separate client (vs. reusing the OpenAI SDK)?
  - We want the audit/fail-closed path to be independent of the project's
    primary OpenAI key rotation. A separate `_transport` injection point
    also makes mocking trivial in tests.
  - It also keeps the dependency surface smaller: only `httpx` is required.

H-2 fix: a single long-lived ``httpx.AsyncClient`` is reused across calls
instead of a fresh one per request, so we get TCP/TLS keep-alive and HTTP
pooling. ``aclose()`` releases it deterministically (call on shutdown).
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx


DEFAULT_MODEL = "omni-moderation-latest"
DEFAULT_ENDPOINT = "https://api.openai.com/v1/moderations"
MAX_INPUT_CHARS = 8000
DEFAULT_TIMEOUT_S = 5.0


class OpenAIModerationClient:
    """Thin async wrapper around the OpenAI Moderation API.

    Constructor accepts an explicit ``_transport`` so tests can swap a
    fake transport without monkey-patching. Production code should pass
    nothing and let the default shared httpx client handle the request.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        *,
        endpoint: str = DEFAULT_ENDPOINT,
        _transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._endpoint = endpoint
        self._transport = _transport
        # Long-lived shared client for the default (production) code path.
        # Lazily created on first use; aclose() releases it.
        self._shared_client: httpx.AsyncClient | None = None
        # Guard against two coroutines racing the first-check lazy init.
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        """Return the shared ``AsyncClient``, creating it on first use.

        If the caller injected a ``_transport`` (test scenario) we still
        build a short-lived client per call so the transport's mock state
        is isolated — production code paths always take the shared branch.
        """
        if self._transport is not None:
            # Test path: short-lived client with a fake transport. Each
            # call gets a fresh client so concurrent tests don't share
            # connection state.
            return httpx.AsyncClient(transport=self._transport, timeout=DEFAULT_TIMEOUT_S)
        if self._shared_client is None:
            async with self._client_lock:
                if self._shared_client is None:
                    self._shared_client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_S)
        return self._shared_client

    async def aclose(self) -> None:
        """Release the shared connection pool. Safe to call multiple times."""
        if self._shared_client is not None:
            await self._shared_client.aclose()
            self._shared_client = None

    async def check(self, text: str) -> dict[str, Any]:
        """Return ``{flagged: bool, categories: dict}`` for the input.

        Raises ``httpx.HTTPStatusError`` on non-2xx so the caller can
        fail-closed (return blocked) — see `core.GuardrailEngine`.
        """
        body = {
            "model": self._model,
            "input": (text or "")[:MAX_INPUT_CHARS],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        client = await self._get_client()
        owns_client = self._transport is not None  # test path closes its own
        try:
            resp = await client.post(
                self._endpoint, headers=headers, content=json.dumps(body),
            )
            resp.raise_for_status()
            payload = resp.json()
        finally:
            if owns_client:
                await client.aclose()

        results = payload.get("results") or []
        if not results:
            # OpenAI always returns a result for valid input; treat as
            # failure so the caller can fail-closed.
            raise ValueError("OpenAI moderation response missing results[]")
        first = results[0]
        return {
            "flagged": bool(first.get("flagged", False)),
            "categories": dict(first.get("categories") or {}),
        }
