"""Performance and profiling utilities for HQ Command."""

from __future__ import annotations

import gc
import statistics
import tracemalloc
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from time import monotonic
from typing import Dict, Iterator, List


@dataclass
class MetricSample:
    """Represents a captured timing sample."""

    name: str
    duration: float


class PerformanceMetrics:
    """Collect timing samples for named execution blocks."""

    def __init__(self) -> None:
        self._samples: Dict[str, List[float]] = defaultdict(list)

    @contextmanager
    def time_block(self, name: str) -> Iterator[None]:
        start = monotonic()
        try:
            yield
        finally:
            duration = monotonic() - start
            self._samples[name].append(duration)

    def snapshot(self) -> Dict[str, Dict[str, float]]:
        snapshot: Dict[str, Dict[str, float]] = {}
        for name, samples in self._samples.items():
            if not samples:
                continue
            snapshot[name] = {
                "count": float(len(samples)),
                "avg": statistics.fmean(samples),
                "min": min(samples),
                "max": max(samples),
            }
        return snapshot


class RenderThrottler:
    """Throttle expensive UI operations to a target interval."""

    def __init__(self, interval_seconds: float = 0.1) -> None:
        if interval_seconds < 0:
            raise ValueError("interval_seconds cannot be negative")
        self._interval = interval_seconds
        self._last_run = 0.0

    def should_run(self) -> bool:
        now = monotonic()
        if now - self._last_run >= self._interval:
            self._last_run = now
            return True
        return False

    def reset(self) -> None:
        self._last_run = 0.0


class MemoryTracker:
    """Provide basic instrumentation for memory usage."""

    def __init__(self) -> None:
        tracemalloc.start()
        self._snapshots: List[tracemalloc.Snapshot] = []

    def capture_snapshot(self) -> None:
        self._snapshots.append(tracemalloc.take_snapshot())

    def growth(self) -> int:
        if len(self._snapshots) < 2:
            return 0
        first = self._snapshots[0]
        last = self._snapshots[-1]
        stats = last.compare_to(first, "lineno")
        return sum(stat.size_diff for stat in stats)

    def current_usage(self) -> int:
        current, _ = tracemalloc.get_traced_memory()
        return current

    def stop(self) -> None:
        tracemalloc.stop()


def proactive_gc(threshold: int = 1000000) -> int:
    """Trigger garbage collection if tracked allocations exceed ``threshold``."""

    current, peak = tracemalloc.get_traced_memory()
    if peak > threshold:
        return gc.collect()
    return 0

