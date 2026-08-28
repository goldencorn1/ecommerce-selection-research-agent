"""Small opt-in, bounded TTL cache for normalized search responses."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from time import monotonic
import threading

from .models import SearchResponse


@dataclass(frozen=True, slots=True)
class SearchCacheHit:
    response: SearchResponse
    age_seconds: float


class SearchCache:
    """Thread-safe in-memory cache; only successful responses are stored."""

    def __init__(self, *, ttl_seconds: float, max_entries: int = 128):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self.ttl_seconds = float(ttl_seconds)
        self.max_entries = int(max_entries)
        self._entries: OrderedDict[str, tuple[float, SearchResponse]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> SearchCacheHit | None:
        now = monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            created_at, response = entry
            age_seconds = now - created_at
            if age_seconds >= self.ttl_seconds:
                self._entries.pop(key, None)
                return None
            self._entries.move_to_end(key)
            return SearchCacheHit(response=response, age_seconds=age_seconds)

    def set(self, key: str, response: SearchResponse) -> None:
        with self._lock:
            self._entries[key] = (monotonic(), response)
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
