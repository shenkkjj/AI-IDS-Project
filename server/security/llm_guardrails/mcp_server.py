"""MCP server for the LLM guardrail layer.

Exposes two tools over the Model Context Protocol so external agents
(Claude Code, Cursor, custom internal agents) can ask the guardrail to
scan text or report stats without going through the FastAPI HTTP layer.

Mount in the main FastAPI app:
    from server.security.llm_guardrails.mcp_server import mcp as guardrails_mcp
    app.mount("/mcp", guardrails_mcp.streamable_http_app())

Both tools are also exposed as module-level ``_StubTool`` instances with
a ``.fn`` attribute so unit tests can call them directly without a real
MCP client.
"""
from __future__ import annotations

from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover — keeps the import safe for unit tests
    FastMCP = None  # type: ignore[assignment]

from server.security.llm_guardrails import audit as _audit
from server.security.llm_guardrails.core import GuardrailEngine


class _StubTool:
    """Lightweight wrapper exposing ``fn`` and ``name`` so unit tests
    can ``await mcp_server.scan_text.fn(...)`` without going through a
    real MCP client. The real FastMCP tool registration goes through
    `mcp.tool()` decorators on the same `_impl` functions.
    """

    def __init__(self, fn, name: str | None = None) -> None:
        self.fn = fn
        self.name = name or fn.__name__


class _StubMCP:  # pragma: no cover — only used when `mcp` is not installed
    """Minimal stand-in for `FastMCP` exposing just enough surface for tests."""

    def __init__(self) -> None:
        from types import SimpleNamespace
        self._tool_manager = SimpleNamespace(_tools={})

    def tool(self, *args, **kwargs):
        from types import SimpleNamespace
        def deco(fn):
            # Honour explicit `name=` kwarg so tests that look up
            # `mcp._tool_manager._tools["scan_text"]` get the
            # public-facing name, not the wrapped function's `__name__`.
            name = kwargs.get("name") or fn.__name__
            self._tool_manager._tools[name] = SimpleNamespace(
                name=name, fn=fn,
            )
            return fn
        return deco

    def streamable_http_app(self):  # pragma: no cover
        raise RuntimeError("MCP SDK not installed — cannot start HTTP server")


def _build_mcp() -> Any:
    """Return a `FastMCP` instance, or a lightweight stand-in if the
    optional `mcp` package is not installed (so unit tests can still
    run on a machine without the MCP SDK).
    """
    if FastMCP is None:
        return _StubMCP()
    return FastMCP(
        "AI-CyberSentinel Guardrails",
        stateless_http=True,
        json_response=True,
    )


# Module-level singleton so the FastAPI app can `mcp.streamable_http_app()`.
mcp = _build_mcp()


# ---- 1. scan_text ----------------------------------------------------------


async def _scan_text_impl(text: str, history: list[dict[str, Any]] | None) -> dict[str, Any]:
    engine = GuardrailEngine.instance()
    reason = await engine.check_input(
        scope="mcp", message=text or "", history=history or [],
    )
    return {
        "allowed": reason is None,
        "reason": reason or "",
        "layer": "input",
    }


# 2. get_stats 走 audit.get_stats (sync),在 async tool 中跑 executor


async def _get_stats_impl() -> dict[str, int]:
    # Look up `_audit.get_stats` at call time so unit tests that
    # `monkeypatch.setattr(audit_mod, "get_stats", ...)` see their stub.
    return _audit.get_stats()


def _get_stats_sync() -> dict[str, int]:
    """Plain-sync entry point for unit tests that call
    `mcp_server.get_stats.fn()` without `await`. The underlying
    `audit.get_stats` is sync, so we just call it directly.
    """
    return _audit.get_stats()


# Always expose `_StubTool` wrappers for tests; also register the real
# FastMCP tool decorator (which works the same on `_StubMCP` for tests
# — it just stores the tool in `_tool_manager._tools[name]`).
scan_text = _StubTool(_scan_text_impl, name="scan_text")  # type: ignore[assignment]
get_stats = _StubTool(_get_stats_sync, name="get_stats")  # type: ignore[assignment]


@mcp.tool(name="scan_text")  # type: ignore[attr-defined]
async def _scan_text_tool(text: str, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return await _scan_text_impl(text, history)


@mcp.tool(name="get_stats")  # type: ignore[attr-defined]
async def _get_stats_tool() -> dict[str, int]:
    return await _get_stats_impl()


# Re-point the StubTools so that `mcp_server.scan_text.fn` / `get_stats.fn`
# both point at callable handlers. `scan_text` stays async (test uses
# `await mcp_server.scan_text.fn(...)`); `get_stats` exposes a sync
# callable because `audit.get_stats` is sync and the contract test
# `test_get_stats_returns_three_keys` calls it without `await`.
scan_text.fn = _scan_text_tool  # type: ignore[attr-defined]
get_stats.fn = _get_stats_sync  # type: ignore[attr-defined]
