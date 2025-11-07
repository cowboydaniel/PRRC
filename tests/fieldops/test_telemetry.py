"""Tests for FieldOps telemetry snapshot collection."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from fieldops import telemetry


@pytest.fixture
def telemetry_connector_stubs(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Patch telemetry module to use deterministic hardware stubs."""

    # Stub data for hardware sensors
    sensor_data = [
        {
            "sensor": "temperature_probe",
            "value": 72.4,
            "unit": "fahrenheit",
            "timestamp": "2024-01-01T12:00:00+00:00",
        }
    ]

    # Stub data for system events
    event_data = [
        {
            "event": "motion_detected",
            "count": 3,
            "last_seen": "2024-01-01T11:58:00+00:00",
        }
    ]

    # Stub data for queue metrics
    queue_data = {
        "uplink": 4,
        "alerts": 1,
    }

    # Patch hardware functions with deterministic data
    monkeypatch.setattr(telemetry, "read_system_sensors", lambda: sensor_data)
    monkeypatch.setattr(telemetry, "get_cached_system_events", lambda: event_data)
    monkeypatch.setattr(telemetry, "get_queue_metrics", lambda: queue_data)

    return {
        "sensor_data": sensor_data,
        "event_data": event_data,
        "queue_data": queue_data,
    }


def _is_isoformat_utc(value: str) -> bool:
    parsed = datetime.fromisoformat(value)
    return parsed.tzinfo is not None and parsed.tzinfo.utcoffset(parsed) == timezone.utc.utcoffset(parsed)


def test_collect_telemetry_snapshot_structure(telemetry_connector_stubs):
    """Default collector returns normalized structures and metadata."""

    snapshot = telemetry.collect_telemetry_snapshot()

    assert isinstance(snapshot, telemetry.TelemetrySnapshot)
    assert snapshot.status in {"ok", "degraded"}
    assert _is_isoformat_utc(snapshot.collected_at)

    sensors = snapshot.metrics.sensors
    assert isinstance(sensors, list)
    assert sensors, "expected default sensor payload"
    for reading in sensors:
        assert isinstance(reading, telemetry.SensorReading)
        assert isinstance(reading.value, (int, float)) or reading.value is None
        assert _is_isoformat_utc(reading.timestamp)

    events = snapshot.metrics.events
    assert events.total_events >= 0
    for event in events.records:
        assert isinstance(event, telemetry.EventRecord)
        assert event.count >= 0
        assert _is_isoformat_utc(event.last_seen)

    queues = snapshot.metrics.queues
    assert queues.total_backlog == sum(queues.queues.values())
    for value in queues.queues.values():
        assert value >= 0


def test_collect_telemetry_normalizes_units(telemetry_connector_stubs, monkeypatch):
    """Unit conversion and timestamp parsing occurs for injected telemetry."""

    # Override hardware stubs with specific test data
    sensor_data = [
        {
            "sensor": "temp",  # Fahrenheit to Celsius conversion
            "value": 86,
            "unit": "fahrenheit",
            "timestamp": "2024-01-01T12:00:00",
        },
        {
            "sensor": "humidity",
            "value": 0.30,
            "unit": "ratio",
            "timestamp": datetime(2024, 1, 1, 11, 59, tzinfo=timezone.utc),
        },
    ]

    event_data = [
        {
            "event": "heartbeat",
            "count": 2,
            "last_seen": "2024-01-01T11:58:00+00:00",
        }
    ]

    queue_data = {"uplink": 1, "alerts": 0}

    monkeypatch.setattr(telemetry, "read_system_sensors", lambda: sensor_data)
    monkeypatch.setattr(telemetry, "get_cached_system_events", lambda: event_data)
    monkeypatch.setattr(telemetry, "get_queue_metrics", lambda: queue_data)

    snapshot = telemetry.collect_telemetry_snapshot()

    sensors = snapshot.metrics.sensors
    assert sensors[0].unit == "celsius"
    assert abs(sensors[0].value - 30) < 0.01
    assert sensors[1].unit == "percent"
    assert sensors[1].value == pytest.approx(30.0)

    events = snapshot.metrics.events
    assert events.total_events == 2
    assert events.records[0].last_seen.endswith("+00:00")

    queues = snapshot.metrics.queues
    assert queues.queues["uplink"] == 1
    assert queues.total_backlog == 1


def test_collect_telemetry_handles_degraded_paths(telemetry_connector_stubs, monkeypatch):
    """Edge-case telemetry inputs degrade status and emit operator notes."""

    # Override hardware stubs with edge-case data
    # Sensor hardware outage - no data
    sensor_data = []

    # Cached events missing - no data
    event_data = []

    # Queue depths with invalid types and negative values
    queue_data = {"alerts": "invalid", "uplink": "15", "ingest": -4}

    monkeypatch.setattr(telemetry, "read_system_sensors", lambda: sensor_data)
    monkeypatch.setattr(telemetry, "get_cached_system_events", lambda: event_data)
    monkeypatch.setattr(telemetry, "get_queue_metrics", lambda: queue_data)

    snapshot = telemetry.collect_telemetry_snapshot()

    assert snapshot.status == "degraded"
    assert "Sensor API returned no readings." in snapshot.notes
    assert "Queue backlog exceeds nominal threshold." in snapshot.notes
    assert "No cached events reported during collection window." in snapshot.notes

    queues = snapshot.metrics.queues
    # Invalid values are coerced to zero and totals remain non-negative
    assert queues.queues["alerts"] == 0
    assert queues.queues["ingest"] == 0
    assert queues.queues["uplink"] == 15
    assert queues.total_backlog == 15

    events = snapshot.metrics.events
    assert events.total_events == 0
    assert events.records == []

