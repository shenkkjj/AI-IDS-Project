import asyncio
import os
import time
from collections import deque
from typing import Any

from loguru import logger

from server.core.config import GATEWAY_RATE_LIMIT_BURST, GATEWAY_RATE_LIMIT_MAX, GATEWAY_RATE_LIMIT_WINDOW

_redis_client: Any = None
_redis_available: bool | None = None


async def _get_redis():
    global _redis_client, _redis_available
    if _redis_available is False:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        import redis.asyncio as aioredis
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0").strip()
        _redis_client = aioredis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        await _redis_client.ping()
        _redis_available = True
        logger.info("Redis connected: {}", url)
        return _redis_client
    except Exception as exc:
        _redis_available = False
        logger.info("Redis unavailable, using in-memory rate limiting: {}", exc)
        return None


_in_memory_buckets: dict[str, deque[float]] = {}
_in_memory_lock = asyncio.Lock()
_cleanup_task: asyncio.Task[Any] | None = None
_CLEANUP_INTERVAL = 300
_BUCKET_MAX_IDLE = 600


def _start_background_cleanup() -> None:
    global _cleanup_task
    if _cleanup_task is not None and not _cleanup_task.done():
        return

    async def _purge_expired() -> None:
        while True:
            await asyncio.sleep(_CLEANUP_INTERVAL)
            now = time.time()
            async with _in_memory_lock:
                stale_ips = [
                    ip for ip, bucket in _in_memory_buckets.items()
                    if not bucket or now - bucket[-1] > _BUCKET_MAX_IDLE
                ]
                for ip in stale_ips:
                    _in_memory_buckets.pop(ip, None)
                if stale_ips:
                    logger.debug("Rate limiter cleaned {} idle buckets, {} remaining",
                                 len(stale_ips), len(_in_memory_buckets))

    _cleanup_task = asyncio.ensure_future(_purge_expired())


async def check_rate_limit(client_ip: str) -> bool:
    _start_background_cleanup()
    redis = await _get_redis()
    if redis is not None:
        return await _redis_rate_limit(redis, client_ip)
    return await _in_memory_rate_limit(client_ip)


async def _redis_rate_limit(redis: Any, client_ip: str) -> bool:
    key = f"waf:ratelimit:{client_ip}"
    now = time.time()
    window = GATEWAY_RATE_LIMIT_WINDOW
    max_requests = GATEWAY_RATE_LIMIT_MAX + GATEWAY_RATE_LIMIT_BURST
    try:
        pipe = redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window)
        results = await pipe.execute()
        count = results[2]
        return count <= max_requests
    except Exception as exc:
        logger.warning("Redis rate limit error, fallback to memory: {}", exc)
        return await _in_memory_rate_limit(client_ip)


async def _in_memory_rate_limit(client_ip: str) -> bool:
    now = time.time()
    max_requests = GATEWAY_RATE_LIMIT_MAX + GATEWAY_RATE_LIMIT_BURST
    async with _in_memory_lock:
        if client_ip not in _in_memory_buckets:
            _in_memory_buckets[client_ip] = deque(maxlen=max_requests + 1)
        bucket = _in_memory_buckets[client_ip]
        while bucket and now - bucket[0] > GATEWAY_RATE_LIMIT_WINDOW:
            bucket.popleft()
        if len(bucket) >= max_requests:
            return False
        bucket.append(now)
        return True


async def get_rate_limit_status(client_ip: str) -> dict[str, Any]:
    redis = await _get_redis()
    now = time.time()
    window = GATEWAY_RATE_LIMIT_WINDOW
    max_requests = GATEWAY_RATE_LIMIT_MAX + GATEWAY_RATE_LIMIT_BURST
    if redis is not None:
        try:
            key = f"waf:ratelimit:{client_ip}"
            await redis.zremrangebyscore(key, 0, now - window)
            count = await redis.zcard(key)
            return {
                "backend": "redis",
                "current": count,
                "limit": max_requests,
                "window": window,
                "remaining": max(0, max_requests - count),
            }
        except Exception:
            pass
    async with _in_memory_lock:
        bucket = _in_memory_buckets.get(client_ip, deque())
        count = len(bucket)
        return {
            "backend": "memory",
            "current": count,
            "limit": max_requests,
            "window": window,
            "remaining": max(0, max_requests - count),
        }
