"""
app/cache/redis_cache.py — Async Redis client singleton.

Uses redis.asyncio for FastAPI compatibility.
"""
from __future__ import annotations

import redis.asyncio as aioredis
from functools import lru_cache
from loguru import logger

from app.config import get_settings

_redis_client: aioredis.Redis | None = None


async def get_redis_client() -> aioredis.Redis:
    """Return the shared async Redis client, creating it if needed."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
        logger.info(f"Redis client initialised: {settings.redis_url}")
    return _redis_client


async def close_redis():
    """Close the Redis connection pool gracefully."""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis connection closed.")


# ─────────────────────────────────────────────────────────────────────────────
# Cache helpers
# ─────────────────────────────────────────────────────────────────────────────
async def cache_set(key: str, value: str, ttl: int) -> None:
    redis = await get_redis_client()
    await redis.setex(key, ttl, value)


async def cache_get(key: str) -> str | None:
    redis = await get_redis_client()
    return await redis.get(key)


async def cache_delete(key: str) -> None:
    redis = await get_redis_client()
    await redis.delete(key)
