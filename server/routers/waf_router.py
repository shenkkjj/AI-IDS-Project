import time
from typing import Any

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from loguru import logger

from server.core.config import (
    HONEYPOT_ENABLED,
    TARGET_URL,
    THREAT_INTEL_ENABLED,
    THREAT_INTEL_SCORE_THRESHOLD,
    WAF_BLOCK_PATTERNS,
    HOP_BY_HOP_HEADERS,
    PROXY_STRIP_HEADERS,
)
from server.core.rate_limiter import check_rate_limit, get_rate_limit_status
from server.core.utils import _get_client_ip, _payload_has_attack_signature, _build_proxy_headers

router = APIRouter(tags=["WAF Gateway"])

_ip_reputation_cache: dict[str, tuple[float, int]] = {}
_ip_reputation_cache_ttl = 3600

MAX_BODY_BYTES = 10 * 1024 * 1024

HONEYPOT_HTML = """<!DOCTYPE html>
<html><head><title>Admin Panel</title></head>
<body style="font-family:monospace;background:#1a1a2e;color:#e0e0e0;padding:40px">
<h1>System Administration Panel</h1>
<form action="/login" method="POST">
<label>Username:</label><input name="username" type="text"><br><br>
<label>Password:</label><input name="password" type="password"><br><br>
<button type="submit">Login</button>
</form>
<p style="color:#555;font-size:10px">v2.1.0 - Internal Use Only</p>
<!-- DEBUG: db_host=192.168.1.100 db_port=3306 db_user=admin db_pass=P@ssw0rd123 -->
</body></html>"""


def _waf_check_request(request: Request) -> str | None:
    from urllib.parse import unquote
    url_path = unquote(str(request.url.path))
    query = unquote(str(request.url.query)) if request.url.query else ""
    full_url = f"{url_path}?{query}" if query else url_path
    for pattern in WAF_BLOCK_PATTERNS:
        if pattern.search(full_url):
            return f"WAF:blocked:url matched {pattern.pattern}"
    return None


async def _read_body_capped(request: Request, max_bytes: int) -> tuple[bytes, str | None]:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > max_bytes:
            return b"", f"WAF:blocked:body exceeds {max_bytes} bytes"
    return bytes(body), None


def _check_body_text(body_text: str) -> str | None:
    if _payload_has_attack_signature(body_text):
        return "WAF:blocked:body attack signature"
    return None


async def _check_ip_reputation(client_ip: str) -> int:
    if not THREAT_INTEL_ENABLED:
        return 0
    now = time.time()
    if client_ip in _ip_reputation_cache:
        cached_time, cached_score = _ip_reputation_cache[client_ip]
        if now - cached_time < _ip_reputation_cache_ttl:
            return cached_score
    try:
        from server.core.config import ABUSEIPDB_API_KEY
        if not ABUSEIPDB_API_KEY:
            return 0
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://api.abuseipdb.com/api/v2/check",
                params={"ipAddress": client_ip, "maxAgeInDays": 90},
                headers={"Key": ABUSEIPDB_API_KEY, "Accept": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                score = int(data.get("abuseConfidenceScore", 0))
                _ip_reputation_cache[client_ip] = (now, score)
                return score
    except Exception as exc:
        logger.debug("threat intel lookup failed for {}: {}", client_ip, exc)
    return 0


@router.api_route("/proxy/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def waf_gateway(request: Request, path: str) -> Response:
    client_ip = _get_client_ip(request)

    if not await check_rate_limit(client_ip):
        logger.warning("WAF gateway rate limit exceeded: ip={}", client_ip)
        return JSONResponse(status_code=429, content={"detail": "Too Many Requests"})

    reputation = await _check_ip_reputation(client_ip)
    if reputation >= THREAT_INTEL_SCORE_THRESHOLD:
        logger.warning("WAF blocked by threat intel: ip={} score={}", client_ip, reputation)
        if HONEYPOT_ENABLED:
            return HTMLResponse(content=HONEYPOT_HTML, status_code=200)
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_BYTES:
        logger.warning("WAF blocked oversized body: ip={} size={}", client_ip, content_length)
        return JSONResponse(status_code=413, content={"detail": "Payload Too Large"})

    waf_result = _waf_check_request(request)

    body_bytes = b""
    if request.method in ("POST", "PUT", "PATCH"):
        body_bytes, size_err = await _read_body_capped(request, MAX_BODY_BYTES)
        if size_err:
            waf_result = size_err
        elif not waf_result and body_bytes:
            content_type = request.headers.get("content-type", "")
            if "json" in content_type or "form" in content_type or "text" in content_type:
                try:
                    text = body_bytes.decode("utf-8", errors="replace")
                    waf_result = _check_body_text(text)
                except Exception:
                    pass

    if waf_result:
        logger.warning("WAF blocked: ip={} reason={}", client_ip, waf_result)
        if HONEYPOT_ENABLED:
            return HTMLResponse(content=HONEYPOT_HTML, status_code=200)
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    target_url = f"{TARGET_URL}/{path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    try:
        headers = _build_proxy_headers(request)
        headers["X-Forwarded-For"] = client_ip
        headers["X-Real-IP"] = client_ip
        headers["X-WAF-Pass"] = "true"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body_bytes if body_bytes else None,
            )

        response_headers: dict[str, str] = {}
        for key, value in resp.headers.items():
            lower = key.lower()
            if lower in HOP_BY_HOP_HEADERS or lower in PROXY_STRIP_HEADERS:
                continue
            response_headers[key] = value
        response_headers["X-WAF-Status"] = "pass"

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=response_headers,
        )
    except httpx.TimeoutException:
        logger.error("WAF gateway timeout: target={}", target_url)
        return JSONResponse(status_code=504, content={"detail": "Gateway Timeout"})
    except httpx.ConnectError:
        logger.error("WAF gateway connect error: target={}", target_url)
        return JSONResponse(status_code=502, content={"detail": "Bad Gateway"})
    except Exception as exc:
        logger.error("WAF gateway error: {}", exc)
        return JSONResponse(status_code=500, content={"detail": "Internal Gateway Error"})


@router.get("/waf/status")
async def waf_status(request: Request) -> dict[str, Any]:
    client_ip = _get_client_ip(request)
    rate_status = await get_rate_limit_status(client_ip)
    return {
        "status": "active",
        "target_url": TARGET_URL,
        "honeypot_enabled": HONEYPOT_ENABLED,
        "threat_intel_enabled": THREAT_INTEL_ENABLED,
        "rate_limit": rate_status,
    }
