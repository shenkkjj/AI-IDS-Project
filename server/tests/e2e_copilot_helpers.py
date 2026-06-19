"""Copilot E2E diagnostic helpers for Playwright tests.

These helpers are test-only. They never print cookies, tokens, passwords,
API keys, raw payloads, or full response bodies. They only capture DOM text,
assistant message text, sanitized console errors, and selected HTTP status
metadata needed to debug flaky browser E2E failures.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

ARTIFACT_DIR = Path("docs/runs/artifacts/m3-12-demo-flow-stability")

_SENSITIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9]{8,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_-]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+", re.IGNORECASE),
)


def _sanitize_text(text: str, *, limit: int = 1200) -> str:
    value = str(text or "")
    for pattern in _SENSITIVE_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value[:limit]


def _artifact_name(prefix: str, suffix: str) -> str:
    safe_prefix = re.sub(r"[^a-zA-Z0-9_.-]+", "-", prefix).strip("-") or "artifact"
    safe_suffix = re.sub(r"[^a-zA-Z0-9_.-]+", "-", suffix).strip("-") or "txt"
    return f"{safe_prefix}.{safe_suffix}"


def write_json_artifact(prefix: str, payload: dict) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / _artifact_name(prefix, "json")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


async def collect_visible_text(page, *, limit: int = 1200) -> str:
    text = await page.evaluate(
        """
        () => {
            const body = document.body;
            if (!body) return '';
            const clone = body.cloneNode(true);
            clone.querySelectorAll('script, style, noscript').forEach((n) => n.remove());
            return (clone.innerText || clone.textContent || '').trim();
        }
        """
    )
    return _sanitize_text(str(text or ""), limit=limit)


async def collect_assistant_messages(page) -> list[str]:
    return await page.evaluate(
        """
        () => Array.from(
            document.querySelectorAll('[data-testid="copilot-message"][data-role="assistant"]')
        ).map((node) => (node.innerText || node.textContent || '').trim()).filter(Boolean)
        """
    )


async def wait_for_copilot_fallback_message(page, *, timeout_ms: int = 45000) -> str:
    """Wait until a visible assistant message contains the no-key fallback.

    This keeps the original product assertion strict: the user-visible Copilot
    message must mention API Key or Base URL. The only change from the old test
    is condition-based waiting with a longer budget and better diagnostics.
    """
    handle = await page.wait_for_function(
        """
        () => {
            const nodes = Array.from(
                document.querySelectorAll('[data-testid="copilot-message"][data-role="assistant"]')
            );
            const texts = nodes
                .map((node) => (node.innerText || node.textContent || '').trim())
                .filter(Boolean);
            for (let i = texts.length - 1; i >= 0; i -= 1) {
                const text = texts[i];
                if (text.includes('API Key') || text.includes('Base URL')) {
                    return text;
                }
            }
            return false;
        }
        """,
        timeout=timeout_ms,
    )
    value = await handle.json_value()
    return str(value or "")


def install_network_diagnostics(page, diag: dict) -> None:
    diag.setdefault("console", [])
    diag.setdefault("page_errors", [])
    diag.setdefault("responses", [])

    def on_console(message) -> None:
        if message.type not in {"error", "warning"}:
            return
        diag["console"].append(
            {
                "type": message.type,
                "text": _sanitize_text(message.text, limit=500),
            }
        )

    def on_page_error(error) -> None:
        diag["page_errors"].append(_sanitize_text(str(error), limit=500))

    def on_response(response) -> None:
        parsed = urlparse(response.url)
        path = parsed.path
        if not (
            path.endswith("/api/backend/copilot/stream")
            or path.endswith("/api/backend/alerts/demo")
            or path.endswith("/api/backend/health")
            or path.endswith("/api/auth/session")
        ):
            return
        diag["responses"].append(
            {
                "method": response.request.method,
                "path": path,
                "status": response.status,
            }
        )

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    page.on("response", on_response)


async def save_copilot_failure_artifacts(page, diag: dict, *, prefix: str) -> dict:
    """Save screenshot + sanitized JSON diagnostics and return artifact paths."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_path = ARTIFACT_DIR / _artifact_name(prefix, "png")
    await page.screenshot(path=str(screenshot_path), full_page=True)
    diag["assistant_messages"] = [
        _sanitize_text(item, limit=800) for item in await collect_assistant_messages(page)
    ]
    diag["body_text"] = await collect_visible_text(page, limit=1200)
    json_path = write_json_artifact(prefix, diag)
    return {
        "screenshot": str(screenshot_path),
        "diagnostics": str(json_path),
    }
