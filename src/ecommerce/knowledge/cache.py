"""Small in-memory TTL cache with observable hit/miss counters."""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class CacheStats:
    hits: int
    misses: int
    evictions: int


class TTLCache(Generic[T]):
    def __init__(self, *, ttl_seconds: float = 300.0, max_entries: int = 128):
        if ttl_seconds <= 0 or max_entries <= 0:
            raise ValueError("ttl_seconds and max_entries must be positive")
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._items: OrderedDict[str, tuple[float, T]] = OrderedDict()
        self._hits = self._misses = self._evictions = 0

    def get(self, key: str) -> T | None:
        item = self._items.get(key)
        if item is None:
            self._misses += 1
            return None
        created, value = item
        if time.monotonic() - created >= self.ttl_seconds:
            del self._items[key]
            self._misses += 1
            return None
        self._items.move_to_end(key)
        self._hits += 1
        return value

    def set(self, key: str, value: T) -> None:
        self._items[key] = (time.monotonic(), value)
        self._items.move_to_end(key)
        while len(self._items) > self.max_entries:
            self._items.popitem(last=False)
            self._evictions += 1

    def stats(self) -> CacheStats:
        return CacheStats(self._hits, self._misses, self._evictions)
