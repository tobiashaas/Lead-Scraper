"""Redis-backed caching utilities for API responses and computations."""
from __future__ import annotations

import asyncio
import functools
import hashlib
import json
from typing import Any, Awaitable, Callable, Optional, TypeVar

import redis.asyncio as redis

from app.core.config import settings
from app.utils.metrics import record_cache_hit, record_cache_miss, record_cache_write

T = TypeVar("T")


class CacheManager:
    """Utility wrapper around Redis for JSON-serialised caching."""

    def __init__(self, redis_url: str, redis_db: int = 0) -> None:
        self.redis_url = redis_url
        self.redis_db = redis_db
        self._client: Optional[redis.Redis] = None
        self._lock = asyncio.Lock()

    async def _get_client(self) -> redis.Redis | None:
        if self._client is not None:
            return self._client

        async with self._lock:
            if self._client is not None:
                return self._client
            try:
                self._client = redis.from_url(
                    self.redis_url,
                    db=self.redis_db,
                    decode_responses=True,
                    encoding="utf-8",
                )
                await self._client.ping()
            except Exception:  # pragma: no cover - best effort cache
                self._client = None
        return self._client

    async def get(self, key: str) -> Any | None:
        client = await self._get_client()
        if not client:
            return None
        value = await client.get(key)
        if value is None:
            record_cache_miss(_extract_prefix(key))
            return None
        record_cache_hit(_extract_prefix(key), size_bytes=len(value.encode("utf-8")))
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        client = await self._get_client()
        if not client:
            return
        payload = json.dumps(value)
        record_cache_write(_extract_prefix(key))
        await client.setex(key, ttl, payload)

    async def delete(self, key: str) -> None:
        client = await self._get_client()
        if not client:
            return
        await client.delete(key)

    async def delete_pattern(self, pattern: str) -> None:
        client = await self._get_client()
        if not client:
            return
        cursor = 0
        while True:
            cursor, keys = await client.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                await client.delete(*keys)
            if cursor == 0:
                break


_cache_manager: CacheManager | None = None
_cache_lock = asyncio.Lock()


async def get_cache_manager() -> CacheManager | None:
    global _cache_manager
    if _cache_manager is not None:
        return _cache_manager

    async with _cache_lock:
        if _cache_manager is not None:
            return _cache_manager
        if not settings.redis_url:
            return None
        _cache_manager = CacheManager(settings.redis_url, settings.redis_db)
        return _cache_manager


def _normalize_for_cache(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple, set)):
        return [_normalize_for_cache(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_for_cache(val) for key, val in value.items()}
    return value.__class__.__name__


def _build_cache_key(prefix: str, func_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    normalized_args = _normalize_for_cache(args)
    normalized_kwargs = _normalize_for_cache(kwargs)
    hasher = hashlib.sha256()
    hasher.update(json.dumps([normalized_args, normalized_kwargs], sort_keys=True).encode("utf-8"))
    return f"{prefix}:{func_name}:{hasher.hexdigest()}"


F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def cache_result(ttl: int = 300, key_prefix: str = "cache") -> Callable[[F], F]:
    """Decorate async callables to cache results in Redis."""

    def decorator(func: F) -> F:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError("cache_result decorator can only be applied to async functions")

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            manager = await get_cache_manager()
            if manager is None:
                return await func(*args, **kwargs)
            cache_key = _build_cache_key(key_prefix, func.__name__, args, kwargs)
            cached = await manager.get(cache_key)
            if cached is not None:
                return cached
            result = await func(*args, **kwargs)
            await manager.set(cache_key, result, ttl=ttl)
            return result

        return wrapper  # type: ignore[return-value]

    return decorator


async def invalidate_pattern(pattern: str) -> None:
    manager = await get_cache_manager()
    if manager is None:
        return
    await manager.delete_pattern(pattern)


def _extract_prefix(key: str) -> str:
    return key.split(":", 1)[0] if ":" in key else key


__all__ = ["CacheManager", "cache_result", "get_cache_manager", "invalidate_pattern"]
