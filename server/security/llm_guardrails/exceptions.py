"""Guardrail-layer exception types.

`GuardrailViolation` is a `ForbiddenException` so the global handler in
`server/main.py` translates it into a 403 JSON response with the same
envelope as other auth/authz errors.
"""
from __future__ import annotations

from server.core.exceptions import ForbiddenException


class GuardrailViolation(ForbiddenException):
    """Raised by `@guard_input` / `@guard_output` when an LLM call would
    leak sensitive data, get hijacked, or otherwise violate the policy.

    `scope` is the entry-point identifier (e.g. ``"copilot"``).
    `reason` is a human-readable explanation suitable for log/audit.
    `layer` is ``"input"`` or ``"output"`` — used to split metrics.
    `status` is ``"blocked"`` (default) or ``"warning"``.
    """

    default_detail = "护栏层拒绝该请求"

    def __init__(
        self,
        scope: str,
        reason: str,
        *,
        layer: str,
        status: str = "blocked",
    ) -> None:
        super().__init__(
            detail=f"[guardrail:{scope}] {reason}",
            extra={
                "layer": layer,
                "scope": scope,
                "guardrail_status": status,
            },
        )
