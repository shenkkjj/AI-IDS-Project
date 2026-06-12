"""Colang 1.0 actions referenced from the rail flows.

`openai_moderation_check` is called by `define flow openai moderation check`
in `rails/input.co` whenever the LLM-as-judge pipeline needs a moderation
verdict. The action is declared with ``is_system_action=True`` so NeMo
auto-injects the current ``context`` and ``events`` keyword arguments.
"""
from typing import List, Optional

from nemoguardrails.actions import action
from openai import AsyncOpenAI


_client: Optional[AsyncOpenAI] = None


def _client_lazy() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI()
    return _client


@action(is_system_action=True)
async def openai_moderation_check(
    context: Optional[dict] = None,
    events: Optional[List[dict]] = None,
) -> bool:
    """OpenAI omni-moderation check used as the L4 input rail.

    Returns ``True`` to allow the request, ``False`` to block it. Fails
    *closed* (returns ``False``) on any infrastructure error so a
    moderation outage cannot accidentally let a jailbreak through.
    """
    text = (context or {}).get("last_user_message", "")
    if not text:
        return True
    if events:
        history = [
            e.get("final_transcript", "")
            for e in events
            if e.get("type") == "UtteranceUserActionFinished"
        ]
        if history:
            text = "\n".join(history) + "\n" + text
    try:
        resp = await _client_lazy().moderations.create(
            model="omni-moderation-latest",
            input=text[:8000],
        )
        return not resp.results[0].flagged
    except Exception:
        return False
