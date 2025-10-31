"""Telemetry collection scaffolding for FieldOps.

This module coordinates simulated device sensors, cached events, and uplink
queue monitoring in lieu of the eventual hardware integrations. While the
current implementation still relies on local stub data, it mirrors the
normalization steps that the production collectors will perform so that
downstream analytics code can be exercised today.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Sequence

from .connectors import (
    FieldOpsEventClient,
    FieldOpsQueueClient,
    FieldOpsSensorClient,
    FieldOpsTelemetryConfig,
)


def collect_telemetry_snapshot() -> Dict[str, Any]:
    """Collect a snapshot of local telemetry data.

    The function pulls from three conceptual sources:

    * Sensor APIs – provide raw readings in a variety of timestamp formats and
      units that are normalized here.
    * Cached events – represent recent system activity held in a local store.
    * Queue depths – express pipeline backlogs for uplink and alert handlers.

    Returns:
        A dictionary representing key metrics used by HQ Command dashboards.
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

    if queue_payload["total_backlog"] > 10:
        status = "degraded"
        notes.append("Queue backlog exceeds nominal threshold.")

    if not event_payload["records"]:
        notes.append("No cached events reported during collection window.")

    return {
        "status": status,
        "collected_at": collected_at.isoformat(),
        "metrics": {
            "sensors": sensor_payload,
            "events": event_payload,
            "queues": queue_payload,
        },
        "notes": notes,
    }


def _get_telemetry_config() -> FieldOpsTelemetryConfig:
    """Return the telemetry configuration sourced from the environment."""

    return FieldOpsTelemetryConfig.from_env()


def _load_sensor_api_data() -> Sequence[Mapping[str, Any]]:
    """Load sensor readings from the FieldOps sensor API."""

    config = _get_telemetry_config()
    client = FieldOpsSensorClient(
        config.api_base_url, config.api_token, config.timeout_seconds
    )
    return client.fetch_latest_readings(config.sensor_device_id)


def _load_cached_events() -> Iterable[Mapping[str, Any]]:
    """Load cached events from the FieldOps event API."""

    config = _get_telemetry_config()
    client = FieldOpsEventClient(
        config.api_base_url, config.api_token, config.timeout_seconds
    )
    return client.fetch_cached_events(config.event_cache_id)


def _load_queue_depths() -> Mapping[str, Any]:
    """Load queue depth metrics from the FieldOps queue API."""

    config = _get_telemetry_config()
    client = FieldOpsQueueClient(
        config.api_base_url, config.api_token, config.timeout_seconds
    )
    return client.fetch_queue_depths(config.queue_group)


def _normalize_sensor_reading(
    reading: Mapping[str, Any],
    fallback_timestamp: datetime,
) -> MutableMapping[str, Any]:
    """Normalize sensor readings to consistent units and timestamp format."""

    normalized: MutableMapping[str, Any] = {
        "sensor": reading.get("sensor") or reading.get("id", "unknown"),
        "value": reading.get("value"),
        "unit": (reading.get("unit") or "").lower(),
    }

    normalized["timestamp"] = _normalize_timestamp(
        reading.get("timestamp"), fallback=fallback_timestamp
    )

    value = normalized.get("value")
    unit = normalized.get("unit")

    if value is None:
        normalized["unit"] = "unknown"
        return normalized

    if unit in {"fahrenheit", "f"}:
        normalized["value"] = _round_float((float(value) - 32.0) * 5.0 / 9.0)
        normalized["unit"] = "celsius"
    elif unit in {"ratio", "fraction"}:
        normalized["value"] = _round_float(float(value) * 100.0)
        normalized["unit"] = "percent"
    elif unit in {"psi"}:
        normalized["value"] = _round_float(float(value) * 6.89476)
        normalized["unit"] = "kilopascal"
    else:
        normalized["value"] = _round_float(float(value))

    return normalized


def _summarize_events(
    events: Iterable[Mapping[str, Any]],
    fallback_timestamp: datetime,
) -> MutableMapping[str, Any]:
    """Normalize cached events and compute aggregate counts."""

    records = []
    total_events = 0

    for event in events:
        count = int(event.get("count", 0))
        total_events += max(count, 0)
        records.append(
            {
                "event": event.get("event", "unknown"),
                "count": max(count, 0),
                "last_seen": _normalize_timestamp(
                    event.get("last_seen"), fallback=fallback_timestamp
                ),
            }
        )

    return {
        "total_events": total_events,
        "records": records,
    }


def _normalize_queue_depths(depths: Mapping[str, Any]) -> MutableMapping[str, Any]:
    """Ensure queue depth metrics are non-negative integers."""

    queues: MutableMapping[str, int] = {}
    for queue_name, raw_value in depths.items():
        try:
            queues[queue_name] = max(int(raw_value), 0)
        except (TypeError, ValueError):
            queues[queue_name] = 0

    return {
        "queues": dict(sorted(queues.items())),
        "total_backlog": sum(queues.values()),
    }


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

