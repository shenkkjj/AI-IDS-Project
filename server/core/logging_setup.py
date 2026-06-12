"""Centralised loguru configuration.

Default sink: pretty-printed text to stderr (good for local dev).
`LOG_FORMAT=json` switches to a one-line JSON record per event so log
aggregators (Loki, Datadog, ELK) can ingest without a sidecar parser.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

from loguru import logger


_CONFIGURED = False


def _json_formatter(record: dict[str, Any]) -> str:
    """Render a loguru record as a single-line JSON string."""
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["name"],
        "function": record["function"],
        "line": record["line"],
    }
    extras = record.get("extra") or {}
    if extras:
        payload.update(extras)
    if record["exception"] is not None:
        payload["exception"] = record["exception"].get_text()
    return json.dumps(payload, ensure_ascii=False, default=str) + "\n"


def configure_logging() -> None:
    """Idempotently install the loguru sinks.

    Called from `main.py` at import time. Subsequent calls are no-ops.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    logger.remove()
    if os.getenv("LOG_FORMAT", "").strip().lower() == "json":
        logger.add(sys.stderr, format=_json_formatter, level=os.getenv("LOG_LEVEL", "INFO"))
    else:
        logger.add(
            sys.stderr,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            ),
            level=os.getenv("LOG_LEVEL", "INFO"),
        )
    _CONFIGURED = True
