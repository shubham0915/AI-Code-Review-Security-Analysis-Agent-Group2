"""
app/cache/memory_store.py — In-memory fallback store when Redis is unavailable.
Uses a simple dict with TTL. Thread-safe for single-process dev use.
"""
from __future__ import annotations

import time
import threading
from typing import Optional

_store: dict[str, tuple[str, float]] = {}  # key -> (value, expire_at)
_lock = threading.Lock()


def _clean_expired():
    now = time.time()
    with _lock:
        expired = [k for k, (_, exp) in _store.items() if exp < now]
        for k in expired:
            del _store[k]


def mem_set(key: str, value: str, ttl: int) -> None:
    with _lock:
        _store[key] = (value, time.time() + ttl)


def mem_get(key: str) -> Optional[str]:
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
    with _lock:
        _store.pop(key, None)


def mem_ping() -> bool:
    return True


class MemoryClient:
    """Async-compatible in-memory client matching the redis.asyncio interface."""

    async def get(self, key: str) -> Optional[str]:
        return mem_get(key)

    async def setex(self, key: str, ttl: int, value: str) -> bool:
        mem_set(key, value, ttl)
        return True

    async def delete(self, key: str) -> None:
        mem_delete(key)

    async def ping(self) -> bool:
        return True

    async def aclose(self):
        pass
