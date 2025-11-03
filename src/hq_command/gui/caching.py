"""Caching and data loading helpers for the HQ Command GUI.

The roadmap for Phase 8 calls for a data caching layer with a stale while
revalidate strategy, request batching, and pagination primitives.  The
utilities in this module are intentionally framework agnostic so they can be
re-used by the Qt models as well as non-UI data sources.
"""

from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Callable, Deque, Dict, Generic, Iterable, Iterator, List, MutableMapping, Optional, Tuple, TypeVar


T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


@dataclass(slots=True)
class CacheEntry(Generic[V]):
    """Small container used by :class:`StaleWhileRevalidateCache`."""

    value: V
    created_at: float
    refreshed_at: float

    @property
    def age(self) -> float:
        return monotonic() - self.created_at

    @property
    def time_since_refresh(self) -> float:
        return monotonic() - self.refreshed_at


class StaleWhileRevalidateCache(Generic[K, V]):
    """In-memory cache that keeps stale values while refreshing in the background.

    The cache is thread-safe and tracks hit/miss statistics so the GUI can feed
    those metrics into the dashboard telemetry.
    """

    def __init__(
        self,
        ttl_seconds: float,
        *,
        max_age_seconds: float | None = None,
        refresh_executor: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_age_seconds is not None and max_age_seconds < ttl_seconds:
            raise ValueError("max_age_seconds must be greater than ttl_seconds")

        self._ttl = ttl_seconds
        self._max_age = max_age_seconds
        self._refresh_executor = refresh_executor
        self._entries: Dict[K, CacheEntry[V]] = {}
        self._lock = Lock()
        self.hits = 0
        self.misses = 0
        self.refreshes = 0

    def get(self, key: K, loader: Callable[[], V]) -> V:
        """Return a cached value, loading and refreshing as required."""

        now = monotonic()
        entry = None
        with self._lock:
            entry = self._entries.get(key)

        if entry is None:
            value = loader()
            with self._lock:
                self._entries[key] = CacheEntry(value=value, created_at=now, refreshed_at=now)
                self.misses += 1
            return value

        age = now - entry.created_at
        time_since_refresh = now - entry.refreshed_at

        if age >= (self._max_age or float("inf")):
            # Drop expired entries entirely.
            value = loader()
            with self._lock:
                self._entries[key] = CacheEntry(value=value, created_at=now, refreshed_at=now)
                self.misses += 1
            return value

        if time_since_refresh <= self._ttl:
            self.hits += 1
            return entry.value

        # Entry is stale but still within the allowed max age.  Return the stale
        # value immediately and schedule a refresh.  If no executor is supplied
        # we fall back to performing the refresh synchronously to keep the
        # behaviour deterministic for unit tests.
        def _refresh() -> None:
            new_value = loader()
            refreshed = CacheEntry(value=new_value, created_at=entry.created_at, refreshed_at=monotonic())
            with self._lock:
                self._entries[key] = refreshed
                self.refreshes += 1

        if self._refresh_executor is not None:
            self._refresh_executor(_refresh)
        else:
            _refresh()

        self.hits += 1
        return entry.value

    def invalidate(self, key: K | None = None) -> None:
        """Invalidate cached entries."""

        with self._lock:
            if key is None:
                self._entries.clear()
            else:
                self._entries.pop(key, None)

    def snapshot(self) -> Dict[str, float | int]:
        """Return metrics describing cache performance."""

        with self._lock:
            size = len(self._entries)
        return {
            "size": size,
            "ttl_seconds": self._ttl,
            "max_age_seconds": self._max_age if self._max_age is not None else float("inf"),
            "hits": self.hits,
            "misses": self.misses,
            "refreshes": self.refreshes,
        }


class RequestBatcher(Generic[K, V]):
    """Aggregate small fetch requests into larger batched operations."""

    def __init__(self, loader: Callable[[Iterable[K]], MutableMapping[K, V]], batch_size: int = 20) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self._loader = loader
        self._batch_size = batch_size
        self._queue: Deque[K] = deque()

    def queue(self, key: K) -> None:
        if key not in self._queue:
            self._queue.append(key)

    def flush(self) -> Dict[K, V]:
        batched: Dict[K, V] = {}
        while self._queue:
            chunk: List[K] = [self._queue.popleft() for _ in range(min(self._batch_size, len(self._queue) + 1))]
            fetched = self._loader(chunk)
            batched.update(fetched)
        return batched


class PaginatedResult(Generic[T]):
    """Lightweight container describing a page of results."""

    def __init__(self, items: Iterable[T], total: int, page: int, page_size: int) -> None:
        self.items = list(items)
        self.total = total
        self.page = page
        self.page_size = page_size

    def __iter__(self) -> Iterator[T]:
        return iter(self.items)

    @property
    def pages(self) -> int:
        if self.page_size == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size


class PaginationController(Generic[T]):
    """Stateful helper that keeps track of pagination for large datasets."""

    def __init__(self, fetch_page: Callable[[int, int], PaginatedResult[T]], page_size: int = 100) -> None:
        if page_size <= 0:
            raise ValueError("page_size must be positive")
        self._fetch_page = fetch_page
        self._page_size = page_size
        self._current_page = 0
        self._total = 0
        self._cache: OrderedDict[int, List[T]] = OrderedDict()
        self._cache_size = 3

    @property
    def page_size(self) -> int:
        return self._page_size

    @property
    def total_items(self) -> int:
        return self._total

    @property
    def current_page(self) -> int:
        return self._current_page

    def set_cache_size(self, pages: int) -> None:
        if pages <= 0:
            raise ValueError("Cache size must be positive")
        self._cache_size = pages

    def _store_page(self, page: int, items: List[T]) -> None:
        self._cache[page] = items
        self._cache.move_to_end(page)
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

    def _load_page(self, page: int) -> List[T]:
        if page in self._cache:
            self._cache.move_to_end(page)
            return self._cache[page]

        result = self._fetch_page(page, self._page_size)
        self._total = result.total
        items = list(result.items)
        self._store_page(page, items)
        return items

    def page(self, index: int) -> List[T]:
        if index < 0:
            raise ValueError("Page index cannot be negative")
        items = self._load_page(index)
        self._current_page = index
        return list(items)

    def next_page(self) -> List[T]:
        if (self._current_page + 1) * self._page_size >= self._total and self._total:
            return []
        return self.page(self._current_page + 1)

    def previous_page(self) -> List[T]:
        if self._current_page == 0:
            return []
        return self.page(self._current_page - 1)

    def prefetch(self, page: int) -> None:
        if page < 0:
            return
        if page in self._cache:
            return
        self._load_page(page)

