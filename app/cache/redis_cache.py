"""
app/cache/redis_cache.py — Async Redis client with in-memory fallback.

Tries to connect to Redis. If Redis is unavailable (no Docker, no brew),
automatically falls back to the in-memory store so the app still works.
"""
from __future__ import annotations

from loguru import logger
from app.config import get_settings
from app.cache.memory_store import MemoryClient

_client = None
_using_memory = False


async def get_redis_client():
    global _client, _using_memory

    if _client is not None:
        return _client

    settings = get_settings()

    # Try real Redis first
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        await r.ping()
        _client = r
        _using_memory = False
        logger.info(f"✅ Connected to Redis: {settings.redis_url}")
        return _client
    except Exception as e:
        logger.warning(f"⚠️  Redis unavailable ({e}). Using in-memory store (dev mode).")
        _client = MemoryClient()
        _using_memory = True
        return _client


async def close_redis():
    global _client
    if _client:
        await _client.aclose()
        _client = None
    logger.info("Cache connection closed.")


async def cache_set(key: str, value: str, ttl: int) -> None:
    r = await get_redis_client()
    await r.setex(key, ttl, value)


async def cache_get(key: str) -> str | None:
    r = await get_redis_client()
    return await r.get(key)


async def cache_delete(key: str) -> None:
    r = await get_redis_client()
    await r.delete(key)


def is_using_memory_fallback() -> bool:
    return _using_memory
