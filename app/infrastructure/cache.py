"""Small in-process TTL cache with per-key single-flight loading."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Hashable


class TTLCache[T]:
    def __init__(self, max_entries: int = 512) -> None:
        self.max_entries = max_entries
        self._values: dict[Hashable, tuple[float, T]] = {}
        self._locks: dict[Hashable, threading.Lock] = {}
        self._guard = threading.Lock()

    def get(self, key: Hashable) -> T | None:
        with self._guard:
            entry = self._values.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at < time.monotonic():
                self._values.pop(key, None)
                return None
            return value

    def set(self, key: Hashable, value: T, ttl: float) -> T:
        with self._guard:
            if len(self._values) >= self.max_entries:
                self._prune()
            self._values[key] = (time.monotonic() + ttl, value)
            return value

    def get_or_load(self, key: Hashable, ttl: float, loader: Callable[[], T]) -> T:
        cached = self.get(key)
        if cached is not None:
            return cached
        with self._guard:
            lock = self._locks.setdefault(key, threading.Lock())
        with lock:
            cached = self.get(key)
            if cached is not None:
                return cached
            value = loader()
            self.set(key, value, ttl)
            return value

    def invalidate(self, key: Hashable) -> None:
        with self._guard:
            self._values.pop(key, None)

    def clear(self) -> None:
        with self._guard:
            self._values.clear()

    def _prune(self) -> None:
        now = time.monotonic()
        for key, (expires_at, _value) in list(self._values.items()):
            if expires_at < now:
                self._values.pop(key, None)
        while len(self._values) >= self.max_entries:
            self._values.pop(next(iter(self._values)))
