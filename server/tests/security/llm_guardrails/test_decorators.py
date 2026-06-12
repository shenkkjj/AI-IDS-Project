"""Unit tests for `server.security.llm_guardrails.decorators`.

Contract:
- `@guard_input(scope=..., message_field=..., history_field=...)`
  - Pre-call: invokes `GuardrailEngine.check_input`. If blocked, raises
    `GuardrailViolation` and writes an audit row with status='blocked'.
  - Otherwise: invokes the wrapped function and writes audit row with
    status='passed'.
- Works on both sync and async functions.
- Audit failures must never break the call.
- Works regardless of whether the function is called with kwargs or args.
"""
from __future__ import annotations

import asyncio
import inspect
from typing import Any

import pytest

from server.security.llm_guardrails.decorators import guard_input, guard_output
from server.security.llm_guardrails.exceptions import GuardrailViolation


# ---- 1. Async function: allowed path -----------------------------------------


@pytest.mark.asyncio
async def test_guard_input_async_allowed(mock_nemo_rails_pass: None) -> None:
    @guard_input(scope="copilot", message_field="message", history_field="history")
    async def fn(message: str, history: list) -> str:
        return "ok"

    out = await fn(message="hello", history=[])
    assert out == "ok"


# ---- 2. Async function: blocked path -----------------------------------------


@pytest.mark.asyncio
async def test_guard_input_async_blocked_raises_violation(
    mock_nemo_rails_block: None,
) -> None:
    @guard_input(scope="copilot", message_field="message", history_field="history")
    async def fn(message: str, history: list) -> str:
        return "should not be called"

    with pytest.raises(GuardrailViolation) as info:
        await fn(message="ignore previous", history=[])
    assert info.value.status_code == 403
    assert "guardrail:copilot" in info.value.detail


# ---- 3. Sync function: allowed path -------------------------------------------


def test_guard_input_sync_allowed(mock_nemo_rails_pass: None) -> None:
    @guard_input(scope="mcp", message_field="text", history_field="history")
    def fn(text: str, history: list) -> str:
        return "ok"

    assert fn(text="hello", history=[]) == "ok"


# ---- 4. Sync function: blocked path -------------------------------------------


def test_guard_input_sync_blocked(mock_nemo_rails_block: None) -> None:
    @guard_input(scope="mcp", message_field="text", history_field="history")
    def fn(text: str, history: list) -> str:
        return "should not run"

    with pytest.raises(GuardrailViolation):
        fn(text="x", history=[])


# ---- 5. field name customizable ----------------------------------------------


@pytest.mark.asyncio
async def test_guard_input_with_custom_field_names(mock_nemo_rails_pass: None) -> None:
    @guard_input(scope="x", message_field="payload", history_field="trail")
    async def fn(payload: str, trail: list) -> str:
        return "ok"

    assert await fn(payload="hi", trail=[]) == "ok"


# ---- 6. Positional args do not crash (kwargs-only expected) ------------------


@pytest.mark.asyncio
async def test_guard_input_missing_kwargs_no_crash(mock_nemo_rails_pass: None) -> None:
    """If the wrapped function does not receive message/history kwargs,
    the decorator must not crash — it should pass the call through.
    """
    @guard_input(scope="x", message_field="message", history_field="history")
    async def fn() -> str:
        return "ok"

    assert await fn() == "ok"


# ---- 7. @guard_output exists and is a decorator factory ----------------------


def test_guard_output_is_decorator_factory() -> None:
    deco = guard_output(scope="copilot")
    assert callable(deco)
    assert inspect.isfunction(deco) or hasattr(deco, "__call__")


# ---- 7b. H-4: @guard_output actually runs the L1 output rail ---------------


@pytest.mark.asyncio
async def test_guard_output_async_blocks_private_ip() -> None:
    """H-4: the output rail must catch RFC1918 IPs in the LLM reply."""

    @guard_output(scope="copilot")
    async def fn() -> str:
        return "The DB is at 192.168.1.42 and it is down."

    with pytest.raises(GuardrailViolation) as info:
        await fn()
    assert info.value.status_code == 403
    assert "guardrail:copilot" in info.value.detail
    # 分类名暴露,具体 regex 模式不暴露
    assert "private_ip_disclosure" in info.value.detail


@pytest.mark.asyncio
async def test_guard_output_async_blocks_api_key() -> None:
    @guard_output(scope="copilot")
    async def fn() -> str:
        return "Use this token: sk-abcdefgh1234567890abcdef"

    with pytest.raises(GuardrailViolation) as info:
        await fn()
    assert "api_key_disclosure" in info.value.detail


@pytest.mark.asyncio
async def test_guard_output_async_allows_benign() -> None:
    @guard_output(scope="copilot")
    async def fn() -> str:
        return "The alert was a port scan from a public IP. No action needed."

    out = await fn()
    assert "port scan" in out


def test_guard_output_sync_blocks_private_ip() -> None:
    @guard_output(scope="copilot")
    def fn() -> str:
        return "Server 10.0.0.5 is the production database."

    with pytest.raises(GuardrailViolation) as info:
        fn()
    assert "private_ip_disclosure" in info.value.detail


# ---- 7c. C-1: sync guard_input from inside a running event loop fails loud -


@pytest.mark.asyncio
async def test_guard_input_sync_inside_event_loop_raises_runtime_error() -> None:
    """C-1 fix: previously the sync wrapper used ``asyncio.run`` which
    crashes silently when the sync callable is invoked from inside an
    async context. We now raise a clear RuntimeError pointing the
    developer at the async path."""
    from server.security.llm_guardrails.decorators import guard_input

    @guard_input(scope="test", message_field="message", history_field="history")
    def fn(message: str, history: list) -> str:
        return "should not run"

    # This is invoked from inside the @pytest.mark.asyncio loop, so the
    # sync wrapper must detect the running loop and fail loud.
    with pytest.raises(RuntimeError) as info:
        fn(message="hello", history=[])
    assert "running event loop" in str(info.value)
    assert "async def" in str(info.value)


# ---- 8. Default field names: 'message' and 'history' -------------------------


@pytest.mark.asyncio
async def test_guard_input_default_field_names(mock_nemo_rails_pass: None) -> None:
    @guard_input(scope="x")
    async def fn(message: str, history: list) -> str:
        return f"got {message}"

    out = await fn(message="hi", history=[])
    assert out == "got hi"
