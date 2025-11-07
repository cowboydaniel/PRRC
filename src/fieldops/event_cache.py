"""Production system event cache for FieldOps.

This module provides persistent storage for tracking recent system events.
Events are stored in JSON format with automatic pruning of old entries.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List
from threading import Lock


class SystemEventCache:
    """Thread-safe JSON-backed cache for system events."""

    def __init__(
        self,
        storage_path: Path | None = None,
        *,
        max_age_minutes: int = 60,
        max_events_per_type: int = 100,
    ) -> None:
        """Initialize system event cache.

        Args:
            storage_path: Path to JSON storage file. Defaults to
                ~/.fieldops/event_cache.json
            max_age_minutes: Maximum age of events to keep (default 60)
            max_events_per_type: Maximum events per type to keep (default 100)
        """
        if storage_path is None:
            storage_path = Path.home() / ".fieldops" / "event_cache.json"

        self._storage_path = storage_path
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._max_age_minutes = max_age_minutes
        self._max_events_per_type = max_events_per_type

        # Initialize with empty cache if file doesn't exist
        if not self._storage_path.exists():
            self._write_cache([])

    def _read_cache(self) -> List[Dict[str, Any]]:
        """Read events from disk."""
        try:
            data = json.loads(self._storage_path.read_text("utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _write_cache(self, events: List[Dict[str, Any]]) -> None:
        """Write events to disk."""
        self._storage_path.write_text(
            json.dumps(events, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _prune_old_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove events older than max_age_minutes."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=self._max_age_minutes)
        pruned = []
        for event in events:
            try:
                timestamp = datetime.fromisoformat(event["timestamp"])
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                if timestamp >= cutoff:
                    pruned.append(event)
            except (KeyError, ValueError):
                # Skip malformed events
                continue
        return pruned

    def log_event(self, event_type: str, **metadata: Any) -> None:
        """Log a system event.

        Args:
            event_type: Type of event (e.g., "gps_fix_acquired", "network_connected")
            **metadata: Additional metadata to store with the event
        """
        with self._lock:
            events = self._read_cache()

            # Add new event
            event = {
                "event_type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **metadata,
            }
            events.append(event)

            # Prune old events
            events = self._prune_old_events(events)

            # Limit events per type
            type_counts: Dict[str, int] = defaultdict(int)
            filtered_events = []
            # Reverse to keep most recent
            for event in reversed(events):
                event_type_key = event.get("event_type", "unknown")
                if type_counts[event_type_key] < self._max_events_per_type:
                    filtered_events.append(event)
                    type_counts[event_type_key] += 1
            # Restore chronological order
            events = list(reversed(filtered_events))

            self._write_cache(events)

    def get_events(self) -> List[Dict[str, Any]]:
        """Get all cached events.

        Returns:
            List of event dictionaries with timestamp and metadata
        """
        with self._lock:
            events = self._read_cache()
            return self._prune_old_events(events)

    def get_event_summary(self) -> List[Dict[str, Any]]:
        """Get summarized event counts by type.

        Returns:
            List of dictionaries with event type, count, and last_seen timestamp
        """
        with self._lock:
            events = self._prune_old_events(self._read_cache())

            # Group by event type
            type_data: Dict[str, Dict[str, Any]] = {}
            for event in events:
                event_type = event.get("event_type", "unknown")
                timestamp = event.get("timestamp")

                if event_type not in type_data:
                    type_data[event_type] = {
                        "event": event_type,
                        "count": 0,
                        "last_seen": timestamp,
                    }

                type_data[event_type]["count"] += 1

                # Update last_seen to most recent timestamp
                if timestamp:
                    try:
                        current = datetime.fromisoformat(type_data[event_type]["last_seen"])
                        new = datetime.fromisoformat(timestamp)
                        if new > current:
                            type_data[event_type]["last_seen"] = timestamp
                    except (ValueError, KeyError):
                        pass

            return list(type_data.values())

    def clear(self) -> None:
        """Clear all cached events."""
        with self._lock:
            self._write_cache([])


# Global instance for production use
_global_cache: SystemEventCache | None = None


def get_event_cache() -> SystemEventCache:
    """Get the global system event cache instance.

    Returns:
        Global SystemEventCache instance
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = SystemEventCache()
    return _global_cache
