"""Data virtualization helpers for the HQ Command GUI."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from typing import Callable, Dict, Generic, Iterable, Iterator, List, Optional, Sequence, Tuple, TypeVar


T = TypeVar("T")


@dataclass(slots=True)
class VirtualWindow(Generic[T]):
    """Represents a contiguous range of rows."""

    start: int
    items: Sequence[T]

    @property
    def stop(self) -> int:
        return self.start + len(self.items)

    def __iter__(self) -> Iterator[T]:
        return iter(self.items)


class VirtualizedSequence(Generic[T]):
    """Provide indexed access to large datasets without loading everything."""

    def __init__(
        self,
        fetch_page: Callable[[int, int], Sequence[T]],
        *,
        total_count: int,
        page_size: int = 200,
        cache_pages: int = 6,
    ) -> None:
        if total_count < 0:
            raise ValueError("total_count cannot be negative")
        if page_size <= 0:
            raise ValueError("page_size must be positive")
        if cache_pages <= 0:
            raise ValueError("cache_pages must be positive")

        self._fetch_page = fetch_page
        self._total = total_count
        self._page_size = page_size
        self._cache_pages = cache_pages
        self._cache: OrderedDict[int, List[T]] = OrderedDict()
        self._lock = Lock()
        self.page_hits = 0
        self.page_misses = 0

    def __len__(self) -> int:  # pragma: no cover - trivial
        return self._total

    @property
    def total(self) -> int:
        return self._total

    def _load_page(self, page: int) -> List[T]:
        if page < 0:
            raise IndexError("page cannot be negative")
        with self._lock:
            if page in self._cache:
                self._cache.move_to_end(page)
                self.page_hits += 1
                return self._cache[page]

        items = list(self._fetch_page(page, self._page_size))
        with self._lock:
            self._cache[page] = items
            self._cache.move_to_end(page)
            self.page_misses += 1
            while len(self._cache) > self._cache_pages:
                self._cache.popitem(last=False)
        return items

    def _page_for_index(self, index: int) -> Tuple[int, int]:
        if not 0 <= index < self._total:
            raise IndexError("index out of range")
        page = index // self._page_size
        offset = index % self._page_size
        return page, offset

    def __getitem__(self, index: int) -> T:
        page, offset = self._page_for_index(index)
        items = self._load_page(page)
        if offset >= len(items):
            raise IndexError("offset outside of loaded page")
        return items[offset]

    def window(self, start: int, stop: Optional[int] = None) -> VirtualWindow[T]:
        if stop is None:
            stop = min(start + self._page_size, self._total)
        if start < 0 or stop < start:
            raise ValueError("Invalid window range")
        if stop > self._total:
            stop = self._total

        collected: List[T] = []
        for index in range(start, stop):
            page, offset = self._page_for_index(index)
            items = self._load_page(page)
            if offset < len(items):
                collected.append(items[offset])
        return VirtualWindow(start=start, items=tuple(collected))

    def prefetch(self, start: int, stop: Optional[int] = None) -> None:
        if stop is None:
            stop = start + self._page_size
        if start < 0:
            start = 0
        if stop > self._total:
            stop = self._total
        for index in range(start, stop, self._page_size):
            page = index // self._page_size
            self._load_page(page)

    def metrics(self) -> Dict[str, int]:
        return {"page_hits": self.page_hits, "page_misses": self.page_misses, "cache_size": len(self._cache)}

