"""`@guard_input` / `@guard_output` decorators for LLM entry points.

These are the *only* sanctioned way to talk to an LLM in this codebase.
Adding a new LLM call? Wrap it with `@guard_input(scope="your_scope")`.

Audit events are always written (best-effort). DB failures do not break
the user's call — see `audit.log_guardrail_event`.
"""
from __future__ import annotations

import asyncio
import functools
import inspect
from typing import Any, Awaitable, Callable, ParamSpec, TypeVar

from loguru import logger

from server.security.llm_guardrails.audit import log_guardrail_event
from server.security.llm_guardrails.core import GuardrailEngine
from server.security.llm_guardrails.exceptions import GuardrailViolation


P = ParamSpec("P")
R = TypeVar("R")


def _safe_log(scope: str, layer: str, status: str, reason: str) -> None:
    try:
        log_guardrail_event(scope=scope, layer=layer, status=status, reason=reason)
    except Exception as exc:  # noqa: BLE001
        logger.warning("guardrail audit log failed scope={} err={}", scope, exc)


def _extract_kwargs(
    kwargs: dict[str, Any],
    *,
    message_field: str,
    history_field: str,
) -> tuple[str, list[dict[str, Any]]]:
    message = kwargs.get(message_field, "") or ""
    history = kwargs.get(history_field, []) or []
    if not isinstance(history, list):
        history = []
    return str(message), history


def _check_input_sync(
    scope: str,
    *,
    message_field: str,
    history_field: str,
    kwargs: dict[str, Any],
) -> str | None:
    """Run the async `check_input` from a sync callable.

    C-1 fix: previously used ``asyncio.run`` unconditionally, which
    raises ``RuntimeError: asyncio.run() cannot be called from a running
    event loop`` whenever the sync wrapper is invoked inside an async
    context (e.g. an ``async def`` test or a sync helper called from
    a worker task). We now detect the case and raise a clear, actionable
    error pointing the developer at the async path.
    """
    message, history = _extract_kwargs(
        kwargs, message_field=message_field, history_field=history_field,
    )
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No event loop — safe to spin up a fresh one for this call.
        return asyncio.run(
            GuardrailEngine.instance().check_input(
                scope=scope, message=message, history=history,
            )
        )
    # We are inside a running event loop. `asyncio.run` would crash, and
    # silently swallowing the check would weaken security. Fail loud
    # so the caller fixes the call site.
    raise RuntimeError(
        f"@guard_input scope={scope!r} decorated a sync callable that was "
        "invoked from within a running event loop. Decorate the wrapped "
        "function with `async def` instead, or call "
        "`GuardrailEngine.instance().check_input(...)` directly via `await`."
    )


async def _check_input_async(
    scope: str,
    *,
    message_field: str,
    history_field: str,
    kwargs: dict[str, Any],
) -> str | None:
    message, history = _extract_kwargs(
        kwargs, message_field=message_field, history_field=history_field,
    )
    return await GuardrailEngine.instance().check_input(
        scope=scope, message=message, history=history,
    )


async def _check_output_async(
    scope: str,
    *,
    response: Any,
    history: list[dict[str, Any]] | None,
) -> str | None:
    """Run the output rail against the model's reply. Returns a category
    string if the response should be blocked, else None.

    H-4 fix: the previous version of ``guard_output`` was a no-op that
    just wrote a "passed" audit row. We now run a real L1 check that
    catches private-IP / API-key / env-var disclosure in the reply.
    """
    return await GuardrailEngine.instance().check_output(
        scope=scope, response=response, history=history or [],
    )


def _check_output_sync(
    scope: str,
    *,
    response: Any,
    history: list[dict[str, Any]] | None,
) -> str | None:
    """Sync version of `_check_output_async`. Same event-loop
    detection as `_check_input_sync` — fails loud with a clear message
    if invoked from within a running loop (C-1 fix)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_check_output_async(
            scope=scope, response=response, history=history,
        ))
    raise RuntimeError(
        f"@guard_output scope={scope!r} decorated a sync callable that was "
        "invoked from within a running event loop. Decorate the wrapped "
        "function with `async def` instead."
    )


def guard_input(
    scope: str,
    *,
    message_field: str = "message",
    history_field: str = "history",
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that runs the input guardrail before the wrapped LLM call.

    - `scope` is an opaque identifier propagated to the audit log.
    - `message_field` / `history_field` tell the decorator which kwarg
      holds the user message and the multi-turn history respectively.
      Defaults match the Copilot service's parameter names.
    - Works on both sync and async callables.
    - If the wrapped function does not receive the expected kwargs, the
      decorator passes the call through (no false blocks).
    """

    def deco(fn: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def aw(*args: P.args, **kwargs: P.kwargs) -> R:
                if message_field not in kwargs and history_field not in kwargs:
                    # No relevant kwargs — pass through.
                    return await fn(*args, **kwargs)
                reason = await _check_input_async(
                    scope,
                    message_field=message_field,
                    history_field=history_field,
                    kwargs=kwargs,
                )
                if reason:
                    _safe_log(scope, "input", "blocked", reason)
                    raise GuardrailViolation(scope, reason, layer="input")
                _safe_log(scope, "input", "passed", "")
                return await fn(*args, **kwargs)

            return aw  # type: ignore[return-value]

        @functools.wraps(fn)
        def sw(*args: P.args, **kwargs: P.kwargs) -> R:
            if message_field not in kwargs and history_field not in kwargs:
                return fn(*args, **kwargs)
            reason = _check_input_sync(
                scope,
                message_field=message_field,
                history_field=history_field,
                kwargs=kwargs,
            )
            if reason:
                _safe_log(scope, "input", "blocked", reason)
                raise GuardrailViolation(scope, reason, layer="input")
            _safe_log(scope, "input", "passed", "")
            return fn(*args, **kwargs)

        return sw  # type: ignore[return-value]

    return deco


def guard_output(
    scope: str,
    *,
    response_field: str = "response",
    history_field: str = "history",
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that runs the output guardrail after the wrapped LLM call.

    Output rails check whether the LLM response leaks secrets (private
    IPs, API key prefixes, internal hostnames, env-var names) — H-4 fix:
    this is now a real check, not a no-op.

    The wrapped function's return value is passed to the engine's
    ``check_output`` which extracts text from plain str / dict / list
    shapes defensively — see ``GuardrailEngine._extract_text``.
    """

    def deco(fn: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def aw(*args: P.args, **kwargs: P.kwargs) -> R:
                result = await fn(*args, **kwargs)
                history = kwargs.get(history_field) or []
                reason = await _check_output_async(
                    scope, response=result, history=history,
                )
                if reason:
                    _safe_log(scope, "output", "blocked", reason)
                    raise GuardrailViolation(scope, reason, layer="output")
                _safe_log(scope, "output", "passed", "")
                return result

            return aw  # type: ignore[return-value]

        @functools.wraps(fn)
        def sw(*args: P.args, **kwargs: P.kwargs) -> R:
            result = fn(*args, **kwargs)
            history = kwargs.get(history_field) or []
            reason = _check_output_sync(
                scope, response=result, history=history,
            )
            if reason:
                _safe_log(scope, "output", "blocked", reason)
                raise GuardrailViolation(scope, reason, layer="output")
            _safe_log(scope, "output", "passed", "")
            return result

        return sw  # type: ignore[return-value]

    return deco
