"""Production queue metrics storage for FieldOps.

This module provides persistent storage for tracking queue depths across
telemetry upload, task synchronization, and log submission operations.
Queue metrics are stored in JSON format and updated atomically.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict
from threading import Lock


class QueueMetricsStorage:
    """Thread-safe JSON-backed storage for queue metrics."""

    def __init__(self, storage_path: Path | None = None) -> None:
        """Initialize queue metrics storage.

        Args:
            storage_path: Path to JSON storage file. Defaults to
                ~/.fieldops/queue_metrics.json
        """
        if storage_path is None:
            storage_path = Path.home() / ".fieldops" / "queue_metrics.json"

        self._storage_path = storage_path
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

        # Initialize with zeros if file doesn't exist
        if not self._storage_path.exists():
            self._write_metrics({
                "telemetry_upload": 0,
                "task_sync": 0,
                "log_submission": 0,
            })

    def _read_metrics(self) -> Dict[str, int]:
        """Read metrics from disk."""
        try:
            data = json.loads(self._storage_path.read_text("utf-8"))
            return {
                "telemetry_upload": int(data.get("telemetry_upload", 0)),
                "task_sync": int(data.get("task_sync", 0)),
                "log_submission": int(data.get("log_submission", 0)),
            }
        except (json.JSONDecodeError, OSError):
            # Return zeros on any error
            return {
                "telemetry_upload": 0,
                "task_sync": 0,
                "log_submission": 0,
            }

    def _write_metrics(self, metrics: Dict[str, int]) -> None:
        """Write metrics to disk."""
        self._storage_path.write_text(
            json.dumps(metrics, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def get_metrics(self) -> Dict[str, int]:
        """Get current queue depths.

        Returns:
            Dictionary mapping queue names to depths
        """
        with self._lock:
            return self._read_metrics()

    def increment(self, queue_name: str, amount: int = 1) -> None:
        """Increment a queue depth.

        Args:
            queue_name: Name of queue (telemetry_upload, task_sync, log_submission)
            amount: Amount to increment by (default 1)
        """
        with self._lock:
            metrics = self._read_metrics()
            if queue_name in metrics:
                metrics[queue_name] = max(0, metrics[queue_name] + amount)
                self._write_metrics(metrics)

    def decrement(self, queue_name: str, amount: int = 1) -> None:
        """Decrement a queue depth.

        Args:
            queue_name: Name of queue (telemetry_upload, task_sync, log_submission)
            amount: Amount to decrement by (default 1)
        """
        with self._lock:
            metrics = self._read_metrics()
            if queue_name in metrics:
                metrics[queue_name] = max(0, metrics[queue_name] - amount)
                self._write_metrics(metrics)

    def set(self, queue_name: str, value: int) -> None:
        """Set a queue depth to a specific value.

        Args:
            queue_name: Name of queue (telemetry_upload, task_sync, log_submission)
            value: New depth value
        """
        with self._lock:
            metrics = self._read_metrics()
            if queue_name in metrics:
                metrics[queue_name] = max(0, value)
                self._write_metrics(metrics)

    def reset(self) -> None:
        """Reset all queue depths to zero."""
        with self._lock:
            self._write_metrics({
                "telemetry_upload": 0,
                "task_sync": 0,
                "log_submission": 0,
            })


# Global instance for production use
_global_storage: QueueMetricsStorage | None = None


def get_queue_storage() -> QueueMetricsStorage:
    """Get the global queue metrics storage instance.

    Returns:
        Global QueueMetricsStorage instance
    """
    global _global_storage
    if _global_storage is None:
        _global_storage = QueueMetricsStorage()
    return _global_storage
