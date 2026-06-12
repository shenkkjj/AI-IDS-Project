"""WAF ASGI-style middleware.

Runs before any route handler. Inspects the URL path and query string
against `WAF_BLOCK_PATTERNS` and short-circuits with 403 on a match.

This is the first half of the WAF split from the `waf_router` (M8). The
router continues to own the proxy / honeypot / threat-intel endpoints
because those are explicit business routes, not transparent filters.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from urllib.parse import unquote

from server.core.config import WAF_BLOCK_PATTERNS


class WAFMiddleware(BaseHTTPMiddleware):
    """Block requests whose URL matches a known attack signature."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        url_path = unquote(str(request.url.path))
        query = unquote(str(request.url.query)) if request.url.query else ""
        full_url = f"{url_path}?{query}" if query else url_path
        for pattern in WAF_BLOCK_PATTERNS:
            if pattern.search(full_url):
                client_ip = (
                    request.client.host if request.client else "unknown"
                )
                logger.warning(
                    "WAF blocked client_ip={} method={} url={} pattern={}",
                    client_ip, request.method, full_url, pattern.pattern,
                )
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Forbidden by WAF"},
                    headers={"X-WAF-Block-Reason": "url-pattern"},
                )
        return await call_next(request)
