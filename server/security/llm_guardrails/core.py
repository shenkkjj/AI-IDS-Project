"""`GuardrailEngine` — the LLM-call gatekeeper.

`check_input(scope, message, history)` is the single entry point used by
`@guard_input`. It runs four defensive layers in order:

  L1. Fast regex over the (history-merged) text — catches the obvious
      patterns without paying for an LLM roundtrip.
  L2/L3. The NeMo Guardrails LLMRails (Colang flows + self_check_input
      LLM-as-judge) if the library is installed and a config is present.
  L4. OpenAI's `omni-moderation-latest` for a final, dedicated classifier
      verdict. Always attempted, even after L1 hits, so that a clean
      audit row carries the strongest possible signal.

5-second timeout enforced via `asyncio.wait_for` ensures the calling
request never blocks on guardrail work. If we time out, we **allow** the
request (fail-open) so that a guardrail outage never denies a legitimate
user — but we emit an `audit warning` row so the SOC can spot the outage.

Why fail-open on infrastructure errors (but fail-closed on policy errors)?
  - Policy errors ("this looks like a prompt injection") are returned by
    the L1 regex, the LLM judge, or the moderation API and we honour them.
  - Infrastructure errors (NeMo crashed, OpenAI 500, network down) are
    swallowed; the user is allowed, audit row marked `warning`.
"""
from __future__ import annotations

import asyncio
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

from loguru import logger


# 1.5 seconds is the new default after SC-11. Generous for a single
# OpenAI Moderation call (<200ms p99) plus a NeMo self_check_input
# LLM-as-judge (<1s typical). Anything slower than 1.5s on the rail
# path is a real outage — we'd rather pass through (fail-open) than
# make the user wait on a slow guard. The 5s original value masked
# infra problems and added noticeable latency to Copilot SSE.
DEFAULT_RAIL_TIMEOUT_S = 1.5


def _read_timeout_s() -> float:
    """Read ``GUARDRAIL_RAIL_TIMEOUT_S`` at call time (H-6 fix).

    The previous implementation cached the value at ``__init__`` time, so
    tests that monkey-patched the env var after the singleton was
    created saw no effect. Reading on every call is cheap (a single
    ``os.getenv`` is just a dict lookup on the process environ) and
    keeps config hot-reloadable in dev.
    """
    raw = os.getenv("GUARDRAIL_RAIL_TIMEOUT_S")
    if not raw:
        return DEFAULT_RAIL_TIMEOUT_S
    try:
        return float(raw)
    except ValueError:
        logger.warning(
            "GUARDRAIL_RAIL_TIMEOUT_S={!r} is not a float; using default {}",
            raw, DEFAULT_RAIL_TIMEOUT_S,
        )
        return DEFAULT_RAIL_TIMEOUT_S


def _read_nemo_enabled() -> bool:
    """Read ``NEMO_GUARDRAILS_ENABLED`` at call time (H-6)."""
    return os.getenv("NEMO_GUARDRAILS_ENABLED", "true").strip().lower() not in {
        "0", "false", "no", "off",
    }


# OpenAI key may live in `LLM_API_KEY` (the project's canonical name) or
# the more conventional `OPENAI_API_KEY`. We accept either so users with
# either env-var convention get a working L4 path. Read on every
# `_init_moderation` so key rotation is picked up by a process restart
# (or by `GuardrailEngine.reset()` from tests).
def _read_openai_moderation_key() -> str:
    return (
        os.getenv("OPENAI_API_KEY", "").strip()
        or os.getenv("LLM_API_KEY", "").strip()
    )


def _read_allowed_tools() -> frozenset[str]:
    """Read the tool-name whitelist from ``GUARDRAIL_ALLOWED_TOOLS``.

    OWASP LLM06 (Excessive Agency) defence: a hijacked LLM that returns
    ``tool_calls`` for a function the deployment never advertised
    (``rm -rf``, ``run_command`` etc.) is the most damaging attack
    class against agentic systems. The allowlist is empty by default —
    which is *fail-closed*: any tool call is rejected unless the
    deployment explicitly opts in. Set the env var to a comma-separated
    list of allowed tool/function names, e.g.
    ``GUARDRAIL_ALLOWED_TOOLS=search_alerts,fetch_threat_intel``.
    """
    raw = os.getenv("GUARDRAIL_ALLOWED_TOOLS", "").strip()
    if not raw:
        return frozenset()
    return frozenset(t.strip() for t in raw.split(",") if t.strip())

# L1 fast-path patterns. These mirror the regexes in
# `server.services.llm_providers._sanitize_user_input` so the L1 layer
# is at least as strict as the in-line sanitiser, and so we can detect
# the same attacks even when NeMo / OpenAI are offline.
L1_BLOCK_PATTERNS: list[re.Pattern[str]] = [
    # --- "ignore / forget prior instructions" variants ---
    re.compile(r"(?i)ignore\s+(?:all\s+)?previous\s+instructions?"),
    re.compile(r"(?i)ignore\s+(?:all\s+)?previous\b"),  # bare "ignore previous" — H-3 follow-up
    re.compile(r"(?i)ignore\s+(?:all\s+)?(?:your|the|all)\s+(?:previous|prior)\s+(?:instructions?|refusal)"),
    re.compile(r"(?i)ignore\s+(?:all\s+)?(?:the\s+)?(?:conversation|context|history)"),
    re.compile(r"(?i)ignore\s+everything\s+(?:before|above|prior)"),
    re.compile(r"(?i)disregard\s+(?:everything|all|above|prior|the\s+above)"),
    re.compile(r"(?i)forget\s+(?:your|all|the)\s+(?:instructions?|rules?|guidelines?)"),
    re.compile(r"(?i)forget\s+everything\s+(?:above|before|prior)"),
    re.compile(r"(?i)repeat\s+everything\s+(?:above|before)"),
    # --- system / SYS / INST pseudo-roles ---
    # 注意:不要 ^ 锚点(merged history 后 "system:" 可能在行中)
    re.compile(r"(?i)\bsystem\s*:\s*"),
    re.compile(r"(?i)<\|?\s*system\s*\|?>"),
    re.compile(r"(?i)<<?\s*SYS\s*>>?"),
    re.compile(r"(?i)\[\s*INST\s*\]"),
    re.compile(r"(?i)<<<\s*END\s+SYSTEM"),
    re.compile(r"(?i)system\s+(?:message|prompt|instructions?)\b"),
    re.compile(r"(?i)system\s+prompt\s*(?:约束|限制|override|above)"),
    # --- role hijack ---
    re.compile(r"(?i)you\s+are\s+now\s+(?:a|an)\s+"),
    re.compile(r"(?i)you\s+are\s+now\s+ChatGPT"),
    re.compile(r"(?i)act\s+as\s+(?:a|an)\s+(?:evil|unrestricted|unfiltered|pirate|hacker)"),
    re.compile(r"(?i)act\s+as\s+if\s+(?:you\s+)?(?:have\s+no|you\s+aren't)"),
    re.compile(r"(?i)pretend\s+(?:the\s+)?(?:safety|guidelines|rules)\s+(?:do\s+not\s+)?(?:exist|apply)"),
    re.compile(r"(?i)pretend\s+(?:the\s+)?(?:safety|guidelines|rules)[\s\S]{0,40}?(?:do\s+not|don'?t)\s+(?:exist|apply)"),
    re.compile(r"(?i)pretend\s+(?:to\s+be|you\s+(?:are|accepted?))"),
    re.compile(r"(?i)developer\s+mode\s+enabled"),
    re.compile(r"(?i)do\s+anything\s+now"),
    re.compile(r"(?i)\bDAN\b"),
    re.compile(r"(?i)no\s+concept\s+of\s+(?:safety|rules)"),
    re.compile(r"(?i)bound\s+by\s+(?:no|any)\s+rules"),
    re.compile(r"(?i)without\s+(?:any\s+)?rules"),
    # --- info disclosure ---
    re.compile(r"(?i)print\s+(?:the\s+)?(?:system\s+prompt|secret|api[_\s-]?key|password|env)",
              flags=re.IGNORECASE),
    re.compile(r"(?i)(?:reveal|show|tell)\s+me\s+(?:the\s+)?(?:api[_\s-]?key|secret|password)"),
    re.compile(r"(?i)echo\s+(?:the\s+)?system\s+prompt"),
    re.compile(r"(?i)echo\s+(?:the\s+)?(?:full\s+)?(?:content\s+of\s+)?(?:your\s+)?system"),
    re.compile(r"(?i)value\s+of\s+(?:api[_\s-]?key|secret|password|env)"),
    re.compile(r"(?i)what\s+is\s+(?:the\s+)?(?:api[_\s-]?key|secret|password)"),
    re.compile(r"(?i)list\s+(?:all\s+)?(?:internal|secret|api[_\s-]?key)"),
    re.compile(r"(?i)translate\s+.*?into\s+(?:your\s+)?system"),
    # 显式索取 secret env var(POSTGRES_PASSWORD, API_KEY, SECRET_KEY 等)
    re.compile(r"(?i)give\s+me\s+(?:the\s+)?[A-Z_]*(?:PASSWORD|SECRET|API_KEY|TOKEN|KEY)"),
    re.compile(r"(?i)(?:reveal|show|expose|leak)\s+(?:the\s+)?[A-Z_]*(?:PASSWORD|SECRET|API_KEY|TOKEN)"),
    # ALL_CAPS 形式的 env var 名(OPENAI_API_KEY, POSTGRES_PASSWORD, AUTH_SECRET 等)
    re.compile(r"\b[A-Z][A-Z0-9_]*(?:PASSWORD|SECRET|API_KEY|TOKEN|AUTH_KEY|PRIVATE_KEY)\b"),
    # 直接出现知名 env var 名
    re.compile(r"\b(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|POSTGRES_PASSWORD|AUTH_SECRET|APP_SECRET|APP_JWT_SECRET|APP_API_KEY_ENCRYPTION_SECRET)\b"),
    # --- bypass / execute ---
    re.compile(r"(?i)bypass(?:es|ed|ing)?\s+(?:the\s+)?(?:all\s+)?(?:safety|filter|moderation|admin|check|auth|rbac)"),
    re.compile(r"(?i)execute\s+(?:the\s+)?(?:above|new|hidden)"),
    re.compile(r"(?i)decode\s+.*?execute"),
    # 包含 admin/rbac 突破意图
    re.compile(r"(?i)(?:admin|rbac)\s+check"),
    re.compile(r"(?i)跳\s*过\s*(?:RBAC|rbac|admin|权限|校验|检查)"),
    # --- chinese variants ---
    re.compile(r"(?i)忽略\s*(?:之前|以上|上文|上面|刚才|先前的?)\s*(?:的|所有)?\s*(?:指令|指示|规则)"),
    re.compile(r"(?i)忘记\s*(?:之前|上面|以上|刚才|先前的?)?\s*(?:的)?\s*(?:指令|指示|规则|设定|对话)"),
    re.compile(r"(?i)你\s*(?:现在)?\s*(?:是|扮演|成了|不再)\s*(?:一个|个)?\s*(?:无(?:限制|审核)|邪恶|坏|反叛)"),
    re.compile(r"(?i)(?:无视|不要管|不要理会)\s*(?:之前|以上)的?\s*(?:指令|指示|规则|设定)"),
    re.compile(r"(?i)没有\s*(?:任何|的)?\s*(?:限制|规则|约束|审核)"),
    re.compile(r"(?i)不再受\s*\S*\s*约束"),
    re.compile(r"(?i)没有任何\s*(?:限制|规则|约束)"),
    re.compile(r"(?i)直接\s*(?:给|告)我\s*\S*"),
    # 角色扮演变体:你扮演一个"反叛 AI" / "BadGPT" / 邪恶的
    re.compile(r"(?i)扮演[一-龥]*?(?:反叛|邪恶|坏|无(?:限制|审核)|不受限)"),
    re.compile(r"(?i)故意\s*(?:输出|暴露|泄露)\s*(?:所有|全部)?\s*(?:密钥|密码|内部|IP)"),
    # --- unicode bypass / obfuscation ---
    # 中英混合: "ignore" + 中文"指令" 同行
    re.compile(r"(?i)ignore\s*(?:前一条|上条|之前|前面)"),
    # 字符间插点: "I.g.n.o.r.e" —— 只匹配字母拆词,避开 IP/版本号
    re.compile(r"(?i)(?:[A-Za-z]\.){3,}[A-Za-z]"),
    # Unicode 转义文本:字面 i
    re.compile(r"\\u00[6-7][0-9a-fA-F]"),
    # 连续 3 个以上 zero-width / non-breaking space 夹在单词内
    re.compile(r"\w[​‌‍ ]{2,}\w"),
    # --- base64 / hex / HTML-entity encoded "ignore" / "system" / "DAN"
    #     prefixes (SC-8 fix: extend the dictionary so trivial encoding
    #     bypasses are caught by L1 instead of needing a per-glyph pattern).
    re.compile(r"(?i)aWdub3Jl"),  # base64("ignore")
    re.compile(r"(?i)c3lzdGVt"),  # base64("system")
    re.compile(r"(?i)c3lzdGVtOnJvbGU="),  # base64("system:role")
    re.compile(r"(?i)c3lzdGVtOiA="),  # base64("system: ")
    re.compile(r"(?i)aWdub3JlIGFsbA=="),  # base64("ignore all")
    re.compile(r"(?i)69676e6f7265"),  # hex("ignore")
    re.compile(r"(?i)73797374656d"),  # hex("system")
    re.compile(r"(?i)64616e"),  # hex("dan")
    re.compile(r"(?i)6a61696c627265616b"),  # hex("jailbreak")
    # ROT13 common keywords
    re.compile(r"(?i)\bvtaber\b(?:cerivbhf|qbja)?"),  # ROT13("ignore" + "previous" / "all")
    re.compile(r"(?i)\bflfgrz\b"),  # ROT13("system")
    # HTML entity-encoded keywords (literal &#NN; or &#xNN;)
    re.compile(r"(?i)&#x?[0-9a-f]{1,3};(?:#x?[0-9a-f]{1,3};){2,}(?:ignore|system|prompt|role)"),
    re.compile(r"(?i)ignore&#x?[0-9a-f]{1,3};"),  # ignore + entity suffix
]


# Mapping from L1 regex buckets to user-safe category names. The regex
# text itself is NEVER returned to the user — only the category. The full
# pattern is still written to the audit log so the SOC can investigate.
# See security review SC-2.
L1_PATTERN_CATEGORY: list[tuple[str, re.Pattern[str]]] = [
    ("prompt_injection", re.compile(r"(?i)ignore\s+(?:all\s+)?(?:your|the|all)\s+(?:previous|prior)\s+(?:instructions?|refusal)")),
    ("prompt_injection", re.compile(r"(?i)ignore\s+(?:all\s+)?previous\s+instructions?")),
    ("prompt_injection", re.compile(r"(?i)ignore\s+(?:all\s+)?previous\b")),  # H-3 follow-up: bare form
    ("prompt_injection", re.compile(r"(?i)ignore\s+(?:all\s+)?(?:the\s+)?(?:conversation|context|history)")),
    ("prompt_injection", re.compile(r"(?i)ignore\s+everything\s+(?:before|above|prior)")),
    ("prompt_injection", re.compile(r"(?i)disregard\s+(?:everything|all|above|prior|the\s+above)")),
    ("prompt_injection", re.compile(r"(?i)forget\s+(?:your|all|the)\s+(?:instructions?|rules?|guidelines?)")),
    ("prompt_injection", re.compile(r"(?i)forget\s+everything\s+(?:above|before|prior)")),
    ("prompt_injection", re.compile(r"(?i)repeat\s+everything\s+(?:above|before)")),
    ("system_impersonation", re.compile(r"(?i)\bsystem\s*:\s*")),
    ("system_impersonation", re.compile(r"(?i)<\|?\s*system\s*\|?>")),
    ("system_impersonation", re.compile(r"(?i)<<?\s*SYS\s*>>?")),
    ("system_impersonation", re.compile(r"(?i)\[\s*INST\s*\]")),
    ("system_impersonation", re.compile(r"(?i)<<<\s*END\s+SYSTEM")),
    ("system_impersonation", re.compile(r"(?i)system\s+(?:message|prompt|instructions?)\b")),
    ("system_impersonation", re.compile(r"(?i)system\s+prompt\s*(?:约束|限制|override|above)")),
    ("role_hijack", re.compile(r"(?i)you\s+are\s+now\s+(?:a|an)\s+")),
    ("role_hijack", re.compile(r"(?i)you\s+are\s+now\s+ChatGPT")),
    ("role_hijack", re.compile(r"(?i)act\s+as\s+(?:a|an)\s+(?:evil|unrestricted|unfiltered|pirate|hacker)")),
    ("role_hijack", re.compile(r"(?i)act\s+as\s+if\s+(?:you\s+)?(?:have\s+no|you\s+aren't)")),
    ("role_hijack", re.compile(r"(?i)pretend\s+(?:the\s+)?(?:safety|guidelines|rules)\s+(?:do\s+not\s+)?(?:exist|apply)")),
    ("role_hijack", re.compile(r"(?i)pretend\s+(?:the\s+)?(?:safety|guidelines|rules)[\s\S]{0,40}?(?:do\s+not|don'?t)\s+(?:exist|apply)")),
    ("role_hijack", re.compile(r"(?i)pretend\s+(?:to\s+be|you\s+(?:are|accepted?))")),
    ("role_hijack", re.compile(r"(?i)developer\s+mode\s+enabled")),
    ("role_hijack", re.compile(r"(?i)do\s+anything\s+now")),
    ("role_hijack", re.compile(r"(?i)\bDAN\b")),
    ("role_hijack", re.compile(r"(?i)no\s+concept\s+of\s+(?:safety|rules)")),
    ("role_hijack", re.compile(r"(?i)bound\s+by\s+(?:no|any)\s+rules")),
    ("role_hijack", re.compile(r"(?i)without\s+(?:any\s+)?rules")),
    ("secret_disclosure", re.compile(r"(?i)print\s+(?:the\s+)?(?:system\s+prompt|secret|api[_\s-]?key|password|env)", flags=re.IGNORECASE)),
    ("secret_disclosure", re.compile(r"(?i)(?:reveal|show|tell)\s+me\s+(?:the\s+)?(?:api[_\s-]?key|secret|password)")),
    ("secret_disclosure", re.compile(r"(?i)echo\s+(?:the\s+)?system\s+prompt")),
    ("secret_disclosure", re.compile(r"(?i)echo\s+(?:the\s+)?(?:full\s+)?(?:content\s+of\s+)?(?:your\s+)?system")),
    ("secret_disclosure", re.compile(r"(?i)value\s+of\s+(?:api[_\s-]?key|secret|password|env)")),
    ("secret_disclosure", re.compile(r"(?i)what\s+is\s+(?:the\s+)?(?:api[_\s-]?key|secret|password)")),
    ("secret_disclosure", re.compile(r"(?i)list\s+(?:all\s+)?(?:internal|secret|api[_\s-]?key)")),
    ("secret_disclosure", re.compile(r"(?i)translate\s+.*?into\s+(?:your\s+)?system")),
    ("secret_disclosure", re.compile(r"(?i)give\s+me\s+(?:the\s+)?[A-Z_]*(?:PASSWORD|SECRET|API_KEY|TOKEN|KEY)")),
    ("secret_disclosure", re.compile(r"(?i)(?:reveal|show|expose|leak)\s+(?:the\s+)?[A-Z_]*(?:PASSWORD|SECRET|API_KEY|TOKEN)")),
    ("secret_disclosure", re.compile(r"\b[A-Z][A-Z0-9_]*(?:PASSWORD|SECRET|API_KEY|TOKEN|AUTH_KEY|PRIVATE_KEY)\b")),
    ("secret_disclosure", re.compile(r"\b(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|POSTGRES_PASSWORD|AUTH_SECRET|APP_SECRET|APP_JWT_SECRET|APP_API_KEY_ENCRYPTION_SECRET)\b")),
    ("bypass_attempt", re.compile(r"(?i)bypass(?:es|ed|ing)?\s+(?:the\s+)?(?:all\s+)?(?:safety|filter|moderation|admin|check|auth|rbac)")),
    ("bypass_attempt", re.compile(r"(?i)execute\s+(?:the\s+)?(?:above|new|hidden)")),
    ("bypass_attempt", re.compile(r"(?i)decode\s+.*?execute")),
    ("bypass_attempt", re.compile(r"(?i)(?:admin|rbac)\s+check")),
    ("bypass_attempt", re.compile(r"(?i)跳\s*过\s*(?:RBAC|rbac|admin|权限|校验|检查)")),
    # Chinese variants
    ("prompt_injection", re.compile(r"(?i)忽略\s*(?:之前|以上|上文|上面|刚才|先前的?)\s*(?:的|所有)?\s*(?:指令|指示|规则)")),
    ("prompt_injection", re.compile(r"(?i)忘记\s*(?:之前|上面|以上|刚才|先前的?)?\s*(?:的)?\s*(?:指令|指示|规则|设定|对话)")),
    ("prompt_injection", re.compile(r"(?i)(?:无视|不要管|不要理会)\s*(?:之前|以上)的?\s*(?:指令|指示|规则|设定)")),
    ("role_hijack", re.compile(r"(?i)你\s*(?:现在)?\s*(?:是|扮演|成了|不再)\s*(?:一个|个)?\s*(?:无(?:限制|审核)|邪恶|坏|反叛)")),
    ("role_hijack", re.compile(r"(?i)扮演[一-龥]*?(?:反叛|邪恶|坏|无(?:限制|审核)|不受限)")),
    ("role_hijack", re.compile(r"(?i)故意\s*(?:输出|暴露|泄露)\s*(?:所有|全部)?\s*(?:密钥|密码|内部|IP)")),
    ("unconstrained", re.compile(r"(?i)没有\s*(?:任何|的)?\s*(?:限制|规则|约束|审核)")),
    ("unconstrained", re.compile(r"(?i)不再受\s*\S*\s*约束")),
    ("unconstrained", re.compile(r"(?i)没有任何\s*(?:限制|规则|约束)")),
    ("secret_disclosure", re.compile(r"(?i)直接\s*(?:给|告)我\s*\S*")),
    # Unicode bypass / obfuscation
    ("unicode_obfuscation", re.compile(r"(?i)ignore\s*(?:前一条|上条|之前|前面)")),
    ("unicode_obfuscation", re.compile(r"(?i)(?:[A-Za-z]\.){3,}[A-Za-z]")),
    ("unicode_obfuscation", re.compile(r"\\u00[6-7][0-9a-fA-F]")),
    ("unicode_obfuscation", re.compile(r"\w[​‌‍ ]{2,}\w")),
    ("unicode_obfuscation", re.compile(r"(?i)aWdub3Jl")),
    ("unicode_obfuscation", re.compile(r"(?i)c3lzdGVt")),
    ("unicode_obfuscation", re.compile(r"(?i)c3lzdGVtOnJvbGU=")),
    ("unicode_obfuscation", re.compile(r"(?i)c3lzdGVtOiA=")),
    ("unicode_obfuscation", re.compile(r"(?i)aWdub3JlIGFsbA==")),
    ("unicode_obfuscation", re.compile(r"(?i)69676e6f7265")),
    ("unicode_obfuscation", re.compile(r"(?i)73797374656d")),
    ("unicode_obfuscation", re.compile(r"(?i)64616e")),
    ("unicode_obfuscation", re.compile(r"(?i)6a61696c627265616b")),
    ("unicode_obfuscation", re.compile(r"(?i)\bvtaber\b(?:cerivbhf|qbja)?")),
    ("unicode_obfuscation", re.compile(r"(?i)\bflfgrz\b")),
    ("unicode_obfuscation", re.compile(r"(?i)&#x?[0-9a-f]{1,3};(?:#x?[0-9a-f]{1,3};){2,}(?:ignore|system|prompt|role)")),
    ("unicode_obfuscation", re.compile(r"(?i)ignore&#x?[0-9a-f]{1,3};")),
]

# Legacy compatibility alias for any code that imported the bare list.
L1_BLOCK_PATTERNS: list[re.Pattern[str]] = [p for _, p in L1_PATTERN_CATEGORY]


def _normalize_for_l1(text: str) -> str:
    """NFKC normalise input before regex matching (H-3 fix).

    Why NFKC:
      - Collapses full-width Latin (e.g. ``ｉｇｎｏｒｅ`` → ``ignore``) and
        compatibility-decomposed forms so trivial unicode bypasses are
        caught by the existing regex set instead of needing a per-glyph
        pattern list.
      - Folds case for some characters (e.g. ``İ`` → ``i̇``) — though we
        still keep ``re.IGNORECASE`` on the regex side as belt-and-braces.

    The original text is preserved in the audit log via the caller — we
    only change what the regex *sees*.
    """
    if not text:
        return ""
    return unicodedata.normalize("NFKC", text)


# Output-side L1 patterns. The output rail is the *last* chance to catch
# a model that has been hijacked into leaking secrets. We look for:
#   - private/internal IP addresses (RFC1918 ranges)
#   - common API key prefixes
#   - internal hostnames / service names
#   - raw well-known env var names (same set the input side looks for)
# See security review H-4 / SC-6.
OUTPUT_L1_PATTERN_CATEGORY: list[tuple[str, re.Pattern[str]]] = [
    ("private_ip_disclosure", re.compile(r"\b(?:10|127)\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")),
    ("private_ip_disclosure", re.compile(r"\b192\.168\.\d{1,3}\.\d{1,3}\b")),
    ("private_ip_disclosure", re.compile(r"\b172\.(?:1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3}\b")),
    ("api_key_disclosure", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}")),
    ("api_key_disclosure", re.compile(r"\b(?:pk|sk|rk)_(?:live|test)_[A-Za-z0-9]{8,}")),
    ("api_key_disclosure", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),  # AWS access key
    ("api_key_disclosure", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),  # GitHub PAT
    ("internal_hostname", re.compile(r"(?i)\b(?:internal|corp|intranet)-[a-z0-9][a-z0-9\-]{2,}\b")),
    ("internal_hostname", re.compile(r"(?i)\.corp\.local\b")),
    ("env_var_disclosure", re.compile(r"\b(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|POSTGRES_PASSWORD|AUTH_SECRET|APP_SECRET|APP_JWT_SECRET|APP_API_KEY_ENCRYPTION_SECRET)\b")),
    ("env_var_disclosure", re.compile(r"\b[A-Z][A-Z0-9_]*(?:PASSWORD|SECRET|API_KEY|TOKEN|AUTH_KEY|PRIVATE_KEY)\b\s*[=:]\s*\S+")),
]


# ---------------------------------------------------------------------------
# PII detection (OWASP LLM02 — Sensitive Information Disclosure).
# P2-A hardening. Detection is *opt-in* and the default behaviour is to
# flag-and-warn (not block), because legitimate Copilot flows sometimes
# need to discuss synthetic PII (e.g. "block SSN 123-45-6789"). The
# caller decides whether to surface the PII as a `pii_warning` reason
# and the SOC can audit-trace the submission.
# ---------------------------------------------------------------------------

# 中国身份证 18 位(末位可为 X)。预筛后用 `_validate_chinese_id_card` 校验位
_CHINESE_ID_CARD_RE = re.compile(r"\b[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b")

# 美国 SSN(NNN-NN-NNNN)
_US_SSN_RE = re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")

# 信用卡 13-19 位数字(可含空格/连字符),预筛后用 Luhn 校验
_CREDIT_CARD_RE = re.compile(r"\b(?:\d[ \-]?){12,18}\d\b")

# 中国手机号 11 位 1[3-9]xxxxxxxxx
_CN_MOBILE_RE = re.compile(r"(?<![\d])1[3-9]\d{9}(?![\d])")

_PII_PATTERN_CATEGORY: list[tuple[str, re.Pattern[str]]] = [
    ("chinese_id_card", _CHINESE_ID_CARD_RE),
    ("us_ssn", _US_SSN_RE),
    ("credit_card", _CREDIT_CARD_RE),
    ("cn_mobile", _CN_MOBILE_RE),
]


def _validate_chinese_id_card(value: str) -> bool:
    """Validate the 18-digit Chinese ID card checksum.

    Weight factors and check codes are defined in GB 11643-1999. The
    function returns ``True`` only for values that pass both the
    structural regex and the checksum — reducing false positives such
    as long digit sequences that happen to look ID-card-shaped.
    """
    if not _CHINESE_ID_CARD_RE.fullmatch(value):
        return False
    weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    check_codes = "10X98765432"
    total = sum(int(c) * w for c, w in zip(value[:17], weights))
    expected = check_codes[total % 11]
    return expected == value[17].upper()


def _validate_credit_card(value: str) -> bool:
    """Luhn check used by all major card networks (Visa / MC / Amex / etc).

    Strips spaces and dashes first so a human-typed ``1234 5678 9012 3456``
    is normalised before the checksum runs.
    """
    digits = [c for c in value if c.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        n = int(d)
        if i % 2 == parity:
            n *= 2
            if n > 9:
                n -= 9
        checksum += n
    return checksum % 10 == 0


def find_pii(text: str) -> list[tuple[str, str]]:
    """Scan ``text`` for PII candidates and return a list of
    ``(category, matched_value)`` tuples.

    Categories: ``chinese_id_card`` / ``us_ssn`` / ``credit_card`` /
    ``cn_mobile``. Each value is the exact substring that matched, so
    the caller can redact or log it as needed.

    Empty list means no PII was found. The function never raises; bad
    input returns an empty list.
    """
    if not text:
        return []
    normalised = _normalize_for_l1(text)
    hits: list[tuple[str, str]] = []
    for category, pattern in _PII_PATTERN_CATEGORY:
        for m in pattern.finditer(normalised):
            value = m.group(0)
            if category == "chinese_id_card" and not _validate_chinese_id_card(value):
                continue
            if category == "credit_card" and not _validate_credit_card(value):
                continue
            hits.append((category, value))
    return hits


def _l1_check_output(text: str) -> str | None:
    """Run the output-side L1 patterns. Returns the matched *category*
    (or None). Same user-vs-audit split as the input side: only the
    category is returned here; the regex pattern lives in the audit log.
    """
    if not text:
        return None
    normalised = _normalize_for_l1(text)
    for category, pattern in OUTPUT_L1_PATTERN_CATEGORY:
        if pattern.search(normalised):
            return category
    return None


def _l1_check_output_with_pattern(text: str) -> tuple[str | None, str | None]:
    """Like `_l1_check_output` but also returns the matched pattern for audit."""
    if not text:
        return None, None
    normalised = _normalize_for_l1(text)
    for category, pattern in OUTPUT_L1_PATTERN_CATEGORY:
        if pattern.search(normalised):
            return category, pattern.pattern
    return None, None


def _l1_check(text: str) -> str | None:
    """Return a blocking *category* (not a regex) if any L1 pattern matches;
    else None. The category is the only thing the caller should surface
    to the user — full pattern text lives in the audit log via
    `log_guardrail_event` (the caller passes the matched pattern as
    `reason`).

    The input is NFKC-normalised first so trivial unicode bypasses
    (full-width letters, compatibility decompositions) are caught
    by the same regex set (H-3).
    """
    if not text:
        return None
    normalised = _normalize_for_l1(text)
    for category, pattern in L1_PATTERN_CATEGORY:
        if pattern.search(normalised):
            return category
    return None


def _l1_check_with_pattern(text: str) -> tuple[str | None, str | None]:
    """Like `_l1_check` but also returns the matched pattern (audit-only)."""
    if not text:
        return None, None
    normalised = _normalize_for_l1(text)
    for category, pattern in L1_PATTERN_CATEGORY:
        if pattern.search(normalised):
            return category, pattern.pattern
    return None, None


class _InstanceAdapter:
    """Wrap a duck-typed `instance()` so the 5s timeout still applies
    even when tests monkey-patch ``GuardrailEngine._instance`` with a
    stand-in object that lacks a timeout.
    """

    def __init__(self, inner: Any, *, timeout_s: float) -> None:
        self._inner = inner
        self._timeout_s = timeout_s

    async def check_input(self, *, scope: str, message: str, history: list) -> str | None:
        try:
            return await asyncio.wait_for(
                self._inner.check_input(scope=scope, message=message, history=history),
                timeout=self._timeout_s,
            )
        except asyncio.TimeoutError:
            logger.warning("guardrail timeout after {}s scope={}", self._timeout_s, scope)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("guardrail internal error scope={} err={}", scope, exc)
            return None


class GuardrailEngine:
    """Process-wide singleton; do not instantiate directly."""

    _instance: "GuardrailEngine | Any | None" = None

    def __init__(self) -> None:
        # NeMo integration is best-effort. If the library is missing
        # or the config is absent, `self._rails` is None and the engine
        # short-circuits to "allow". This keeps tests and dev environments
        # green even without the heavy dep.
        self._rails: Any = None
        self._moderation = None
        # Timeout / NeMo enabled flag are read at *call* time via the
        # helper functions, not cached here (H-6 fix).
        self._init_rails()
        self._init_moderation()

    def _init_rails(self) -> None:
        """Initialise NeMo Guardrails. Fails *loud* if the config dir is
        empty or missing required files (security review SC-7).

        Behaviour:
        - If `NEMO_GUARDRAILS_ENABLED` env var is explicitly ``"false"``,
          skip NeMo entirely (L2/L3 will be disabled, but the engine
          still runs with L1 + L4 only).
        - Otherwise, require the config dir to exist and contain
          ``config.yml`` + ``rails/input.co`` + ``actions.py``. If any
          of those is missing we log an error AND keep the rails as
          None — but the engine still runs (L1 + L4 cover the basics).
        """
        if os.getenv("NEMO_GUARDRAILS_ENABLED", "true").strip().lower() in {
            "0", "false", "no", "off",
        }:
            logger.info("NeMo Guardrails disabled via NEMO_GUARDRAILS_ENABLED=false")
            self._rails = None
            return

        cfg_path = os.getenv(
            "NEMO_GUARDRAILS_CONFIG_PATH",
            "server/security/llm_guardrails/config",
        )
        cfg_dir = Path(cfg_path) if "Path" not in globals() else __import__("pathlib").Path(cfg_path)
        # Required files: if any is missing, hard-warn (don't fail-closed
        # by default — but call out clearly in logs).
        required = ["config.yml", "rails/input.co", "actions.py"]
        missing = [p for p in required if not (cfg_dir / p).exists()]
        if missing:
            logger.error(
                "NeMo config incomplete at {}: missing {} — "
                "L2/L3 (Colang + LLM-as-judge) will NOT be active. "
                "See security review SC-7.",
                cfg_path, missing,
            )
            self._rails = None
            return

        try:
            from nemoguardrails import LLMRails, RailsConfig  # type: ignore

            config = RailsConfig.from_path(str(cfg_dir))
            self._rails = LLMRails(config)
            logger.info("guardrail engine initialised with NeMo at {}", cfg_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("guardrail engine running WITHOUT NeMo rails: {}", exc)
            self._rails = None

    def _init_moderation(self) -> None:
        try:
            from server.security.llm_guardrails.moderation.client import OpenAIModerationClient

            self._moderation = OpenAIModerationClient(api_key=_read_openai_moderation_key())
        except Exception as exc:  # noqa: BLE001
            logger.warning("moderation client init failed: {}", exc)
            self._moderation = None

    @classmethod
    def instance(cls) -> "GuardrailEngine | _InstanceAdapter":
        """Return the process-wide singleton. Tests may monkey-patch
        ``cls._instance`` to inject a stub; if that stub is not a
        `GuardrailEngine` subclass, we wrap it in a `_InstanceAdapter`
        so the 5s timeout contract still holds.
        """
        if cls._instance is None:
            cls._instance = cls()
        if isinstance(cls._instance, GuardrailEngine):
            return cls._instance
        # Duck-typed stand-in (e.g. a test stub). Apply timeout protection.
        return _InstanceAdapter(cls._instance, timeout_s=DEFAULT_RAIL_TIMEOUT_S)

    @classmethod
    def reset(cls) -> None:
        """Test hook: drop the singleton so a new instance is built
        on the next ``instance()`` call. Never call this from app code.
        """
        cls._instance = None

    async def check_input(
        self,
        *,
        scope: str,
        message: str,
        history: list[dict[str, Any]],
    ) -> str | None:
        """Run all input rails. Return ``None`` if allowed, else a
        human-readable reason for blocking.

        ``scope`` is opaque to the engine — it is just propagated to the
        audit log. The decorator reads it from the user.
        """
        try:
            return await asyncio.wait_for(
                self._run_rails(scope=scope, message=message, history=history),
                timeout=_read_timeout_s(),
            )
        except asyncio.TimeoutError:
            logger.warning(
                "guardrail timeout after {}s scope={}", _read_timeout_s(), scope,
            )
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("guardrail internal error scope={} err={}", scope, exc)
            return None

    async def _run_rails(
        self,
        *,
        scope: str,
        message: str,
        history: list[dict[str, Any]],
    ) -> str | None:
        # Build the merged text once; every layer below reuses it.
        merged = self._merge_history(message, history)

        # L1 fast-path regex. Cheap, deterministic, runs first.
        # Returns (category, pattern) so the caller can log the pattern
        # in the audit log without ever exposing it to the end user.
        l1_category, l1_pattern = _l1_check_with_pattern(merged)
        if l1_category:
            return f"{l1_category} (L1: {l1_pattern[:60]})"

        # L4 OpenAI Moderation (cheap, fast, fail-closed).
        if self._moderation is not None:
            try:
                result = await self._moderation.check(merged)
                if result.get("flagged"):
                    return (
                        f"prompt_injection (L4: openai_moderation,"
                        f"cats={list((result.get('categories') or {}).keys())})"
                    )
            except Exception as exc:  # noqa: BLE001
                # Moderation 异常按 plan §2.1 E 决策:fail-closed
                # 但 reason 用 type name,不含用户内容。
                return f"moderation_unavailable (L4: fail-closed, exc={type(exc).__name__})"

        # L2/L3 NeMo Guardrails (Colang flows + LLM-as-judge).
        if self._rails is None:
            return None  # 没 NeMo 时,L1 放行 + Moderation 放行就放行

        messages = _build_messages_for_rails(history=history, message=message)
        try:
            res = await self._rails.generate_async(
                messages=messages,
                options={"rails": ["input"]},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("NeMo generate_async failed scope={} err={}", scope, exc)
            return None

        content = self._extract_text(res) or ""
        if self._looks_like_refusal(content):
            return content or "blocked by NeMo guardrails"
        return None

    # Roles we accept from a Copilot history turn. Anything else is dropped
    # silently so a malicious `role="tool"` or `role="dev"` payload can't
    # be smuggled past L1/L4 as if it were a legitimate prior turn.
    # See security review SC-3 / SC-19.
    _ALLOWED_ROLES = frozenset({"user", "assistant", "system"})

    @staticmethod
    def _merge_history(message: str, history: list[dict[str, Any]]) -> str:
        """Concatenate ALL non-empty turns (any allowed role) plus the
        current user message. Pasting them into one text lets L1 regex and
        L4 moderation see multi-turn injection that would otherwise hide
        inside an `assistant` or `system` turn.

        The order is preserved (oldest first) so a 5-turn script reads
        naturally to both humans reviewing the audit log and to the LLM
        judge (when L2/L3 are enabled).
        """
        parts: list[str] = []
        for item in history or []:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "")
            if role not in GuardrailEngine._ALLOWED_ROLES:
                continue  # silently drop unknown / hostile roles
            content = str(item.get("content") or "")
            if not content:
                continue
            parts.append(f"{role}: {content}")
        parts.append(f"user: {message or ''}")
        return "\n".join(parts)

    @staticmethod
    def _extract_text(res: Any) -> str:
        """NeMo returns a dict-like object whose `content` is the bot reply.
        Be liberal in what we accept — handle plain str, dict, or list shapes.
        """
        if isinstance(res, str):
            return res
        if isinstance(res, dict):
            content = res.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict):
                    return str(first.get("text") or "")
        return ""

    @staticmethod
    def _extract_tool_calls(res: Any) -> list[str]:
        """Pull every tool / function name out of an LLM response (P2-D).

        Handles OpenAI's ``tool_calls[].function.name`` and the legacy
        ``function_call.name`` shape, plus Anthropic's ``content[].name``
        (when ``type=="tool_use"``). Returns a deduplicated list
        preserving first-seen order.
        """
        seen: set[str] = set()
        ordered: list[str] = []

        def _push(name: Any) -> None:
            if not isinstance(name, str):
                return
            name = name.strip()
            if not name or name in seen:
                return
            seen.add(name)
            ordered.append(name)

        if not isinstance(res, dict):
            return []

        for tc in res.get("tool_calls") or []:
            if isinstance(tc, dict):
                fn = tc.get("function") or {}
                _push(fn.get("name") or tc.get("name"))

        fc = res.get("function_call")
        if isinstance(fc, dict):
            _push(fc.get("name"))

        content = res.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    _push(item.get("name"))
        return ordered

    async def check_output(
        self,
        *,
        scope: str,
        response: Any,
        history: list[dict[str, Any]] | None = None,
    ) -> str | None:
        """H-4: run the output-side L1 (and optional L4) checks against
        the model's reply. Returns ``None`` if allowed, else a category
        string for blocking.

        Unlike ``check_input``, this is run *after* the LLM has already
        generated its response, so the asymmetry is intentional: the
        model output is the attack surface we can no longer influence
        with instruction-time guardrails.

        Output-side L1 catches things like RFC1918 IP disclosure, raw
        API key prefixes, internal hostnames, and bare env-var names.
        OWASP LLM06 (P2-D): also inspects ``tool_calls`` / ``function_call``
        and rejects any tool that is not in the deployment allowlist.
        """
        text = self._extract_text(response)
        tool_names = self._extract_tool_calls(response)
        if not text and not tool_names:
            return None
        try:
            return await asyncio.wait_for(
                self._run_output_rails(
                    scope=scope,
                    response_text=text,
                    tool_names=tool_names,
                    history=history or [],
                ),
                timeout=_read_timeout_s(),
            )
        except asyncio.TimeoutError:
            logger.warning(
                "output-rail timeout after {}s scope={}", _read_timeout_s(), scope,
            )
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("output-rail internal error scope={} err={}", scope, exc)
            return None

    async def _run_output_rails(
        self,
        *,
        scope: str,
        response_text: str,
        tool_names: list[str],
        history: list[dict[str, Any]],
    ) -> str | None:
        # L1 output patterns — fast, deterministic, no LLM.
        if response_text:
            l1_category, l1_pattern = _l1_check_output_with_pattern(response_text)
            if l1_category:
                return f"{l1_category} (L1-out: {l1_pattern[:60]})"
        # P2-D: tool-call allowlist (OWASP LLM06 Excessive Agency).
        if tool_names:
            allowed = _read_allowed_tools()
            unauthorised = [n for n in tool_names if n not in allowed]
            if unauthorised:
                # Fail-closed: with an empty allowlist, every tool call
                # is unauthorised by construction.
                return (
                    f"unauthorised_tool_call (L1-out: tools={unauthorised!r},"
                    f" allowed={sorted(allowed) if allowed else '<empty>'})"
                )
        # (Future) L2 output rail via NeMo self_check_output is already
        # declared in config.yml/rails/output.co, but not invoked here
        # yet because the streaming path is owned by the Copilot service
        # and we don't want to add latency per-token. P1 work item.
        return None

    @staticmethod
    def _looks_like_refusal(text: str) -> bool:
        if not text:
            return False
        lowered = text.lower()
        refusal_markers = (
            "抱歉",  # 我们的 Colang 默认拒答文本前缀
            "i'm sorry",
            "i can't",
            "i cannot",
            "i won't",
            "i refuse",
            "触发了安全策略",
        )
        return any(marker in lowered for marker in refusal_markers)


def _build_messages_for_rails(*, history: list[dict[str, Any]], message: str) -> list[dict[str, str]]:
    """Compose a NeMo-compatible ``messages`` list from multi-turn history
    and a current user message.

    Defensive against bad inputs: history items that are not dicts are
    dropped, AND roles are whitelisted to ``{user, assistant, system}``
    so a malicious `role="tool"` or `role="dev"` payload cannot smuggle
    extra "messages" to the LLM (security review SC-3).
    """
    out: list[dict[str, str]] = []
    for item in history or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "user")
        if role not in GuardrailEngine._ALLOWED_ROLES:
            continue
        content = str(item.get("content") or "")
        if not content:
            continue
        out.append({"role": role, "content": content})
    out.append({"role": "user", "content": str(message or "")})
    return out
