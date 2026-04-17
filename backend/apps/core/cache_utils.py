from __future__ import annotations

from typing import Any, Callable

from django.core.cache import cache


class CacheService:
    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        return cache.get(key, default)

    @staticmethod
    def set(key: str, value: Any, timeout: int) -> None:
        cache.set(key, value, timeout)

    @staticmethod
    def get_or_set(key: str, builder: Callable[[], Any], timeout: int) -> Any:
        value = cache.get(key)
        if value is not None:
            return value
        value = builder()
        cache.set(key, value, timeout)
        return value

    @staticmethod
    def delete(key: str) -> None:
        cache.delete(key)