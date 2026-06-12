"""Public API of the LLM guardrails layer.

Re-exports the most commonly used symbols so callers can do::

    from server.security.llm_guardrails import guard_input, GuardrailViolation

instead of reaching into submodules.
"""
from server.security.llm_guardrails.audit import get_stats, log_guardrail_event
from server.security.llm_guardrails.core import GuardrailEngine
from server.security.llm_guardrails.decorators import guard_input, guard_output
from server.security.llm_guardrails.exceptions import GuardrailViolation

__all__ = [
    "GuardrailEngine",
    "GuardrailViolation",
    "get_stats",
    "guard_input",
    "guard_output",
    "log_guardrail_event",
]
