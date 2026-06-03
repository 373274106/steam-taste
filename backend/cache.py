"""Tiny LRU + TTL cache. No external deps."""

import time
from collections import OrderedDict
from typing import Any, Optional


class TTLCache:
    """Bounded LRU cache where entries expire after `ttl` seconds.

    Thread-safe enough for our single-process FastAPI use case (GIL).
    """

    def __init__(self, maxsize: int = 500, ttl: float = 3600.0):
        self.maxsize = maxsize
        self.ttl = ttl
        self._store: OrderedDict[Any, tuple[float, Any]] = OrderedDict()

    def get(self, key) -> Optional[Any]:
        item = self._store.get(key)
        if item is None:
            return None
        ts, value = item
        if time.time() - ts > self.ttl:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return value

    def set(self, key, value) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (time.time(), value)
        while len(self._store) > self.maxsize:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()
