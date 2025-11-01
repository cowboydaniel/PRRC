"""Persistence helpers for the FieldOps GUI offline queue."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .state import OfflineOperation


class OfflineQueueStorage:
    """JSON-backed storage for queued GUI operations."""

    def __init__(self, cache_file: Path) -> None:
        self._cache_file = cache_file
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[OfflineOperation]:
        """Load operations from disk if present."""

        if not self._cache_file.exists():
            return []
        payload = json.loads(self._cache_file.read_text("utf-8"))
        return [OfflineOperation.from_json(entry) for entry in payload]

    def write(self, operations: Iterable[OfflineOperation]) -> None:
        """Persist ``operations`` to disk."""

        serialized = [operation.to_json() for operation in operations]
        self._cache_file.write_text(
            json.dumps(serialized, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def clear(self) -> None:
        """Remove the cache file entirely."""

        if self._cache_file.exists():
            self._cache_file.unlink()

