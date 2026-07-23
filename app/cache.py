"""
app/cache.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PURPOSE: Manages all caching for the application.
         Stores session state and analysis results so they can be
         retrieved quickly without re-running the expensive AI pipeline.

HOW IT WORKS:
  - Primary store: Redis (a fast in-memory database running in Docker)
  - Automatic fallback: If Redis is down, switches to a simple Python
    dict-based store so the app keeps working in development.

SECTIONS:
  1. In-Memory Fallback  — Thread-safe dict store with TTL expiry
  2. Redis Client        — Async Redis wrapper with auto-fallback logic
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import time
import threading
from typing import Optional

import logfire
from loguru import logger

from app.config import get_settings

# Instruments all Redis calls with Logfire observability traces
logfire.instrument_redis()


# ─── SECTION 1: IN-MEMORY FALLBACK ────────────────────────────────────────────
# Used automatically when Redis is not running (e.g. local dev without Docker).
# Thread-safe for single-process usage.

# Internal store: maps key → (value_string, expiry_timestamp)
_store: dict[str, tuple[str, float]] = {}
_lock = threading.Lock()  # Prevents race conditions in multi-threaded environments


def _clean_expired():
    """Remove all keys that have passed their TTL expiry time."""
    now = time.time()
    with _lock:
        expired = [k for k, (_, exp) in _store.items() if exp < now]
        for k in expired:
            del _store[k]


def mem_set(key: str, value: str, ttl: int) -> None:
    """Store a value in memory with a Time-To-Live (TTL) in seconds."""
    with _lock:
        _store[key] = (value, time.time() + ttl)


def mem_get(key: str) -> Optional[str]:
    """Retrieve a value from memory. Returns None if missing or expired."""
    _clean_expired()
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        value, exp = entry
        if time.time() > exp:
            del _store[key]
            return None
        return value


def mem_delete(key: str) -> None:
    """Delete a key from the in-memory store."""
    with _lock:
        _store.pop(key, None)


class MemoryClient:
    """
    A drop-in async-compatible replacement for the Redis client.
    Implements the same interface (get, setex, delete, ping) so that
    all callers work identically whether Redis is running or not.
    """

    async def get(self, key: str) -> Optional[str]:
        return mem_get(key)

    async def setex(self, key: str, ttl: int, value: str) -> bool:
        """Set a value with an expiry time (mimics Redis SETEX command)."""
        mem_set(key, value, ttl)
        return True

    async def delete(self, key: str) -> None:
        mem_delete(key)

    async def ping(self) -> bool:
        """Always returns True — the in-memory store is always available."""
        return True

    async def aclose(self):
        """No-op: nothing to close for an in-memory store."""
        pass


# ─── SECTION 2: REDIS CLIENT ──────────────────────────────────────────────────
# Singleton async Redis client. Created once and reused for all requests.

_client = None          # The active client (either real Redis or MemoryClient)
_using_memory = False   # Tracks which mode we're in for the health check endpoint


async def get_redis_client():
    """
    Returns the active cache client (Redis or in-memory fallback).
    Creates the client on first call and reuses it for all subsequent calls.

    On startup, tries to connect to Redis. If it fails for any reason
    (Docker not running, connection refused, etc.), automatically
    switches to the MemoryClient fallback with a warning log.
    """
    global _client, _using_memory

    # Return cached client if we already connected
    if _client is not None:
        return _client

    settings = get_settings()

    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=1,  # Fail fast — don't hang on connection
            socket_timeout=1,
        )
        await r.ping()  # Test the connection before trusting it
        _client = r
        _using_memory = False
        logger.info(f"✅ Connected to Redis: {settings.redis_url}")
        return _client
    except Exception as e:
        # Redis is unavailable — switch to in-memory mode automatically
        logger.warning(f"⚠️  Redis unavailable ({e}). Using in-memory store (dev mode).")
        _client = MemoryClient()
        _using_memory = True
        return _client


async def close_redis():
    """
    Gracefully close the Redis connection on app shutdown.
    Called by the FastAPI lifespan handler in app/main.py.
    """
    global _client
    if _client:
        await _client.aclose()
        _client = None
    logger.info("Cache connection closed.")


async def cache_set(key: str, value: str, ttl: int) -> None:
    """Store a string value in the cache with a TTL (in seconds)."""
    r = await get_redis_client()
    await r.setex(key, ttl, value)


async def cache_get(key: str) -> str | None:
    """Retrieve a cached string value. Returns None if the key doesn't exist or has expired."""
    r = await get_redis_client()
    return await r.get(key)


async def cache_delete(key: str) -> None:
    """Explicitly remove a key from the cache before it expires."""
    r = await get_redis_client()
    await r.delete(key)


def is_using_memory_fallback() -> bool:
    """
    Returns True if we are running on the in-memory fallback (Redis is down).
    Used by the /health/ready endpoint to warn operators.
    """
    return _using_memory
