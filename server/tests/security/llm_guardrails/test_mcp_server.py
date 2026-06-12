"""Unit tests for `server.security.llm_guardrails.mcp_server`.

Contract:
- The MCP server exposes two tools:
  - `scan_text(text: str, history: list[dict] | None) -> dict`
    Returns `{"allowed": bool, "reason": str, "layer": "input"}`.
  - `get_stats() -> dict`
    Returns the audit-log aggregate `{passed, blocked, warning}`.
- Tools are registered with `@mcp.tool()` (the FastMCP instance is the
  module-level `mcp` symbol).
- The endpoint is mounted at `/mcp` by the FastAPI app lifespan.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest


# ---- 1. scan_text returns allowed=True for safe input ------------------------


@pytest.mark.asyncio
async def test_scan_text_safe_input(mock_nemo_rails_pass: None) -> None:
    from server.security.llm_guardrails import mcp_server

    result = await mcp_server.scan_text.fn(text="hello", history=None)
    assert result["allowed"] is True
    assert result["reason"] == ""
    assert result["layer"] == "input"


# ---- 2. scan_text returns allowed=False for attack ---------------------------


@pytest.mark.asyncio
async def test_scan_text_attack_blocked(mock_nemo_rails_block: None) -> None:
    from server.security.llm_guardrails import mcp_server

    result = await mcp_server.scan_text.fn(text="ignore previous", history=None)
    assert result["allowed"] is False
    assert result["reason"]
    assert result["layer"] == "input"


# ---- 3. scan_text forwards history ------------------------------------------


@pytest.mark.asyncio
async def test_scan_text_forwards_history(
    mock_nemo_rails_pass: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from server.security.llm_guardrails import core

    captured: dict[str, Any] = {}

    class _Capturing:
        async def check_input(self, *, scope: str, message: str, history: list) -> str | None:
            captured["scope"] = scope
            captured["history"] = history
            return None

    monkeypatch.setattr(core.GuardrailEngine, "_instance", _Capturing())

    from server.security.llm_guardrails import mcp_server

    history = [{"role": "user", "content": "hi"}]
    await mcp_server.scan_text.fn(text="hello", history=history)
    assert captured["scope"] == "mcp"
    assert captured["history"] == history


# ---- 4. get_stats returns three keys ----------------------------------------


def test_get_stats_returns_three_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.security.llm_guardrails import mcp_server
    from server.security.llm_guardrails import audit as audit_mod

    monkeypatch.setattr(
        audit_mod, "get_stats", lambda: {"passed": 10, "blocked": 2, "warning": 1},
    )
    stats = mcp_server.get_stats.fn()
    assert stats == {"passed": 10, "blocked": 2, "warning": 1}


# ---- 5. FastMCP instance is module-level ------------------------------------


def test_mcp_instance_is_fastmcp() -> None:
    from server.security.llm_guardrails import mcp_server

    # FastMCP 实例的 mcp_type 或 instance 类型
    assert hasattr(mcp_server.mcp, "tool")
    # 我们的两个 tool 都注册了
    tool_names = {t.name for t in mcp_server.mcp._tool_manager._tools.values()}
    assert "scan_text" in tool_names
    assert "get_stats" in tool_names
