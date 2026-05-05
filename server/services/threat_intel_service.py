import json
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from loguru import logger

# 公开免费威胁情报源
FEEDS: list[dict[str, Any]] = [
    {
        "name": "Tor Exit Nodes",
        "url": "https://check.torproject.org/torbulkexitlist",
        "parser": "lines",
        "enabled": True,
    },
    {
        "name": "Emerging Threats Compromised IPs",
        "url": "https://rules.emergingthreats.net/blockrules/compromised-ips.txt",
        "parser": "lines",
        "enabled": True,
    },
    {
        "name": "SSLBL Botnet C2 IPs",
        "url": "https://sslbl.abuse.ch/blacklist/sslipblacklist.csv",
        "parser": "csv",
        "csv_col": 0,
        "enabled": True,
    },
]

CACHE_TTL = 3600  # 1小时

_cached_blacklist: set[str] = set()
_cache_ts: float = 0.0

IP_PATTERN = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")


def _extract_ip(line: str) -> str | None:
    line = line.strip()
    if line.startswith("#") or not line:
        return None
    m = IP_PATTERN.search(line)
    if m:
        ip = m.group(0)
        parts = ip.split(".")
        if all(0 <= int(p) <= 255 for p in parts):
            return ip
    return None


async def fetch_feed(url: str, parser: str, csv_col: int = 0) -> set[str]:
    ips: set[str] = set()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            text = resp.text

            if parser == "lines":
                for line in text.splitlines():
                    ip = _extract_ip(line)
                    if ip:
                        ips.add(ip)
            elif parser == "csv":
                for line in text.splitlines():
                    if line.startswith("#") or not line.strip():
                        continue
                    parts = line.split(",")
                    if len(parts) > csv_col:
                        ip = _extract_ip(parts[csv_col])
                        if ip:
                            ips.add(ip)
    except Exception as exc:
        logger.warning("threat intel fetch failed feed={} err={}", url, exc)
    return ips


async def refresh_blacklist() -> tuple[int, dict[str, int]]:
    global _cached_blacklist, _cache_ts
    now = datetime.now(timezone.utc).timestamp()
    if _cache_ts > 0 and (now - _cache_ts) < CACHE_TTL:
        return len(_cached_blacklist), {"cached": len(_cached_blacklist)}

    merged: set[str] = set()
    stats: dict[str, int] = {}

    for feed in FEEDS:
        if not feed.get("enabled"):
            continue
        logger.info("fetching threat feed: {}", feed["name"])
        result = await fetch_feed(feed["url"], feed["parser"], feed.get("csv_col", 0))
        merged |= result
        stats[feed["name"]] = len(result)

    _cached_blacklist = merged
    _cache_ts = now
    logger.info("threat intel refreshed total={} feeds={}", len(merged), len(stats))
    return len(merged), stats


def is_blacklisted(ip: str) -> bool:
    return ip in _cached_blacklist


def get_blacklist_size() -> int:
    return len(_cached_blacklist)
