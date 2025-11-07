"""Telemetry collection for FieldOps Dell Rugged Extreme devices.

This module collects telemetry from local hardware sensors on Dell Latitude
Rugged Extreme tablets, including:
- System sensors (CPU temperature, battery status, etc.)
- Cached system events (GPS fix, network status, mission activities)
- Local queue metrics (offline operation queue depths)

All data is collected locally from the device - no external API calls.
Gracefully degrades to simulated data when running on non-hardware platforms
for development and testing purposes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Sequence

# Local hardware sensor imports - no external APIs
try:
    from .hardware import (
        read_system_sensors,
        get_cached_system_events,
        get_queue_metrics,
    )
except ImportError:
    # Fallback for testing when hardware module not available
    def read_system_sensors():
        return []
    def get_cached_system_events():
        return []
    def get_queue_metrics():
        return {}

__all__ = [
    "SensorReading",
    "EventRecord",
    "EventSummary",
    "QueueMetrics",
    "TelemetryMetrics",
    "TelemetrySnapshot",
    "collect_telemetry_snapshot",
]


@dataclass(frozen=True)
class SensorReading:
    """Normalized representation of a FieldOps sensor reading."""

    sensor: str
    value: float | None
    unit: str
    timestamp: str


@dataclass(frozen=True)
class EventRecord:
    """Record of a cached FieldOps event."""

    event: str
    count: int
    last_seen: str


@dataclass(frozen=True)
class EventSummary:
    """Aggregate information about cached FieldOps events."""

    total_events: int
    records: list[EventRecord]


@dataclass(frozen=True)
class QueueMetrics:
    """Queue backlog statistics sourced from FieldOps services."""

    queues: Dict[str, int]
    total_backlog: int


@dataclass(frozen=True)
class TelemetryMetrics:
    """Container for normalized telemetry metrics."""

    sensors: list[SensorReading]
    events: EventSummary
    queues: QueueMetrics


@dataclass(frozen=True)
class TelemetrySnapshot:
    """Snapshot of FieldOps telemetry data used by HQ analytics."""

    status: str
    collected_at: str
    metrics: TelemetryMetrics
    notes: list[str]


def collect_telemetry_snapshot() -> TelemetrySnapshot:
    """Collect a snapshot of local telemetry data.

    The function pulls from three conceptual sources:

    * Sensor APIs – provide raw readings in a variety of timestamp formats and
      units that are normalized here.
    * Cached events – represent recent system activity held in a local store.
    * Queue depths – express pipeline backlogs for uplink and alert handlers.

    Returns:
        TelemetrySnapshot: Typed snapshot representing key FieldOps metrics used
        by HQ Command dashboards.
    """

    collected_at = datetime.now(timezone.utc)

    sensor_payload = [
        _normalize_sensor_reading(reading, collected_at)
        for reading in _load_sensor_api_data()
    ]

    event_payload = _summarize_events(_load_cached_events(), collected_at)
    queue_payload = _normalize_queue_depths(_load_queue_depths())

    notes = []
    status = "ok"

    if not sensor_payload:
        status = "degraded"
        notes.append("Sensor API returned no readings.")

    if queue_payload.total_backlog > 10:
        status = "degraded"
        notes.append("Queue backlog exceeds nominal threshold.")

    if not event_payload.records:
        notes.append("No cached events reported during collection window.")

    metrics = TelemetryMetrics(
        sensors=sensor_payload,
        events=event_payload,
        queues=queue_payload,
    )

    return TelemetrySnapshot(
        status=status,
        collected_at=collected_at.isoformat(),
        metrics=metrics,
        notes=notes,
    )


def _load_sensor_api_data() -> Sequence[Mapping[str, Any]]:
    """Load sensor readings from local Dell Rugged hardware.

    Reads from actual system sensors (CPU temp, battery, etc.) when available,
    falls back to simulated data for development/testing.
    """
    return read_system_sensors()


def _load_cached_events() -> Iterable[Mapping[str, Any]]:
    """Load cached events from local system event log.

    Returns recent system events from the local event cache.
    """
    return get_cached_system_events()


def _load_queue_depths() -> Mapping[str, Any]:
    """Load queue depth metrics from local offline operation queue.

    Returns the depth of local queues (telemetry, task sync, logs, etc.).
    """
    return get_queue_metrics()


def _normalize_sensor_reading(
    reading: Mapping[str, Any],
    fallback_timestamp: datetime,
) -> SensorReading:
    """Normalize sensor readings to consistent units and timestamp format."""

    sensor = reading.get("sensor") or reading.get("id", "unknown")
    raw_value = reading.get("value")
    unit = (reading.get("unit") or "").lower()
    timestamp = _normalize_timestamp(reading.get("timestamp"), fallback=fallback_timestamp)

    normalized_value: float | None
    normalized_unit = unit

    if raw_value is None:
        normalized_value = None
        normalized_unit = "unknown"
    else:
        if unit in {"fahrenheit", "f"}:
            normalized_value = _round_float((float(raw_value) - 32.0) * 5.0 / 9.0)
            normalized_unit = "celsius"
        elif unit in {"ratio", "fraction"}:
            normalized_value = _round_float(float(raw_value) * 100.0)
            normalized_unit = "percent"
        elif unit in {"psi"}:
            normalized_value = _round_float(float(raw_value) * 6.89476)
            normalized_unit = "kilopascal"
        else:
            normalized_value = _round_float(float(raw_value))
            normalized_unit = unit or "unknown"

    return SensorReading(
        sensor=sensor,
        value=normalized_value,
        unit=normalized_unit,
        timestamp=timestamp,
    )


def _summarize_events(
    events: Iterable[Mapping[str, Any]],
    fallback_timestamp: datetime,
) -> EventSummary:
    """Normalize cached events and compute aggregate counts."""

    records: list[EventRecord] = []
    total_events = 0

    for event in events:
        count = int(event.get("count", 0))
        total_events += max(count, 0)
        records.append(
            EventRecord(
                event=event.get("event", "unknown"),
                count=max(count, 0),
                last_seen=_normalize_timestamp(
                    event.get("last_seen"), fallback=fallback_timestamp
                ),
            )
        )

    return EventSummary(total_events=total_events, records=records)


def _normalize_queue_depths(depths: Mapping[str, Any]) -> QueueMetrics:
    """Ensure queue depth metrics are non-negative integers."""

    queues: MutableMapping[str, int] = {}
    for queue_name, raw_value in depths.items():
        try:
            queues[queue_name] = max(int(raw_value), 0)
        except (TypeError, ValueError):
            queues[queue_name] = 0

    sorted_queues = dict(sorted(queues.items()))
    return QueueMetrics(queues=sorted_queues, total_backlog=sum(sorted_queues.values()))


def _normalize_timestamp(
    value: Any,
    *,
    fallback: datetime,
) -> str:
    """Convert timestamps to an ISO 8601 string with UTC timezone."""

    if value is None:
        candidate = fallback
    elif isinstance(value, datetime):
        candidate = value
    elif isinstance(value, (int, float)):
        candidate = datetime.fromtimestamp(float(value), tz=timezone.utc)
    elif isinstance(value, str):
        candidate = _parse_datetime_string(value, fallback)
    else:
        candidate = fallback

    if candidate.tzinfo is None:
        candidate = candidate.replace(tzinfo=timezone.utc)

    return candidate.astimezone(timezone.utc).isoformat()


def _parse_datetime_string(value: str, fallback: datetime) -> datetime:
    """Parse various timestamp string formats with sensible defaults."""

    try:
        candidate = datetime.fromisoformat(value)
    except ValueError:
        return fallback

    if candidate.tzinfo is None:
        candidate = candidate.replace(tzinfo=timezone.utc)

    return candidate


def _round_float(value: float, *, digits: int = 2) -> float:
    """Round floating point values to a consistent precision."""

    return round(float(value), digits)

