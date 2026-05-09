import ipaddress
import os
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import Request
from server.core.config import WAF_BLOCK_PATTERNS, HOP_BY_HOP_HEADERS, PROXY_STRIP_HEADERS


def _get_client_ip(request: Request) -> str:
    trusted_proxy_count = int(os.getenv("TRUSTED_PROXY_COUNT", "0").strip())
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded and trusted_proxy_count > 0:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        valid_parts = []
        for p in parts:
            try:
                ipaddress.ip_address(p)
                valid_parts.append(p)
            except ValueError:
                continue
        if len(valid_parts) >= trusted_proxy_count:
            idx = len(valid_parts) - trusted_proxy_count
            ip = valid_parts[idx]
            if ip:
                return ip
    elif forwarded and trusted_proxy_count == 0:
        pass
    client = request.client
    return str(client.host) if client else "unknown"


def _get_direct_client_ip(request: Request) -> str:
    client = request.client
    return str(client.host) if client else ""


def _is_private_or_loopback_ip(ip_text: str) -> bool:
    try:
        parsed = ipaddress.ip_address(ip_text)
    except ValueError:
        return False
    return parsed.is_private or parsed.is_loopback or parsed.is_link_local or parsed.is_reserved


def _is_url_pointing_to_internal(url: str) -> bool:
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return True
        try:
            ipaddress.ip_address(hostname)
            return _is_private_or_loopback_ip(hostname)
        except ValueError:
            pass
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for family, _type, _proto, _canonname, sockaddr in addr_info:
                ip_text = sockaddr[0]
                if _is_private_or_loopback_ip(ip_text):
                    return True
        except socket.gaierror:
            return True
        return False
    except Exception:
        return True


def _resolve_url_host(url: str) -> str | None:
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return None
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for family, _type, _proto, _canonname, sockaddr in addr_info:
                return sockaddr[0]
        except socket.gaierror:
            return None
        return None
    except Exception:
        return None


def _is_allowed_alert_ingest_source(request: Request) -> bool:
    source_ip = _get_direct_client_ip(request)
    if not source_ip:
        return False

    cidr_text = os.getenv("ALERTS_INGEST_ALLOWED_CIDRS", "").strip()
    if not cidr_text:
        return _is_private_or_loopback_ip(source_ip)

    try:
        source = ipaddress.ip_address(source_ip)
    except ValueError:
        return False

    for raw_item in cidr_text.split(","):
        item = raw_item.strip()
        if not item:
            continue
        try:
            network = ipaddress.ip_network(item, strict=False)
        except ValueError:
            continue
        if source in network:
            return True
    return False


def _payload_has_attack_signature(text: str) -> bool:
    if not text:
        return False
    for pattern in WAF_BLOCK_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _build_proxy_headers(request: Request) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in request.headers.items():
        lower = key.lower()
        if lower in HOP_BY_HOP_HEADERS or lower in PROXY_STRIP_HEADERS:
            continue
        out[key] = value
    return out


_LOG_SANITIZE_PATTERNS: list[tuple[str, str]] = [
    (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '[CREDIT_CARD]'),
    (r'\b1[3-9]\d{9}\b', '[PHONE]'),
    (r'(?i)(password|passwd|pwd)\s*[:=]\s*\S+', '[PASSWORD]'),
    (r'sk-[a-zA-Z0-9]{20,}', '[API_KEY]'),
    (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[EMAIL]'),
]

_SANITIZE_PATTERNS_INITIALIZED = False


def _get_sanitize_patterns() -> list[tuple[str, str]]:
    global _SANITIZE_PATTERNS_INITIALIZED
    if not _SANITIZE_PATTERNS_INITIALIZED:
        env_patterns = os.getenv("LOG_SANITIZE_PATTERNS", "").strip()
        if env_patterns:
            try:
                import json
                loaded = json.loads(env_patterns)
                if isinstance(loaded, list):
                    _LOG_SANITIZE_PATTERNS.clear()
                    for item in loaded:
                        if isinstance(item, list) and len(item) == 2:
                            _LOG_SANITIZE_PATTERNS.append((item[0], item[1]))
            except Exception:
                pass
        _SANITIZE_PATTERNS_INITIALIZED = True
    return _LOG_SANITIZE_PATTERNS


def _sanitize_for_log(text: str) -> str:
    if not text:
        return ""
    import re
    sanitized = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
        .replace("\n", " ")
        .replace("\r", "")
    )
    patterns = _get_sanitize_patterns()
    for pattern, replacement in patterns:
        sanitized = re.sub(pattern, replacement, sanitized)
    return sanitized


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
