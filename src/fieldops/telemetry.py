"""Telemetry collection scaffolding for FieldOps.

This module coordinates simulated device sensors, cached events, and uplink
queue monitoring in lieu of the eventual hardware integrations. While the
current implementation still relies on local stub data, it mirrors the
normalization steps that the production collectors will perform so that
downstream analytics code can be exercised today.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Sequence

from .connectors import (
    FieldOpsEventClient,
    FieldOpsQueueClient,
    FieldOpsSensorClient,
    FieldOpsTelemetryConfig,
)

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


def _get_telemetry_config() -> FieldOpsTelemetryConfig | None:
    """Return the telemetry configuration sourced from the environment.

    Returns:
        FieldOpsTelemetryConfig if environment variables are set, None otherwise.
    """
    try:
        return FieldOpsTelemetryConfig.from_env()
    except RuntimeError:
        # Configuration not available - return None to enable mock/stub mode
        return None


def _load_sensor_api_data() -> Sequence[Mapping[str, Any]]:
    """Load sensor readings from the FieldOps sensor API."""

    config = _get_telemetry_config()
    if config is None:
        # Return stub data when configuration is unavailable
        return []

    client = FieldOpsSensorClient(
        config.api_base_url, config.api_token, config.timeout_seconds
    )
    return client.fetch_latest_readings(config.sensor_device_id)


def _load_cached_events() -> Iterable[Mapping[str, Any]]:
    """Load cached events from the FieldOps event API."""

    config = _get_telemetry_config()
    if config is None:
        # Return stub data when configuration is unavailable
        return []

    client = FieldOpsEventClient(
        config.api_base_url, config.api_token, config.timeout_seconds
    )
    return client.fetch_cached_events(config.event_cache_id)


def _load_queue_depths() -> Mapping[str, Any]:
    """Load queue depth metrics from the FieldOps queue API."""

    config = _get_telemetry_config()
    if config is None:
        # Return stub data when configuration is unavailable
        return {}

    client = FieldOpsQueueClient(
        config.api_base_url, config.api_token, config.timeout_seconds
    )
    return client.fetch_queue_depths(config.queue_group)


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

