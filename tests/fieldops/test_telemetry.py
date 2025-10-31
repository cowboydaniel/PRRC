"""Tests for FieldOps telemetry snapshot collection."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from fieldops import telemetry
from fieldops.connectors import FieldOpsTelemetryConfig


@pytest.fixture
def telemetry_connector_stubs(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Patch telemetry module to use deterministic connector stubs."""

    config = FieldOpsTelemetryConfig(
        api_base_url="https://fieldops.test",
        api_token="test-token",
        sensor_device_id="device-001",
        event_cache_id="cache-001",
        queue_group="uplink-queue",
        timeout_seconds=1.0,
    )

    monkeypatch.setattr(telemetry, "_get_telemetry_config", lambda: config)

    class SensorClientStub:
        def __init__(self) -> None:
            self.payload = [
                {
                    "sensor": "temperature_probe",
                    "value": 72.4,
                    "unit": "fahrenheit",
                    "timestamp": "2024-01-01T12:00:00+00:00",
                }
            ]

        def fetch_latest_readings(self, device_id: str):  # pragma: no cover - type narrow
            assert device_id == config.sensor_device_id
            return list(self.payload)

    class EventClientStub:
        def __init__(self) -> None:
            self.payload = [
                {
                    "event": "motion_detected",
                    "count": 3,
                    "last_seen": "2024-01-01T11:58:00+00:00",
                }
            ]

        def fetch_cached_events(self, cache_id: str):  # pragma: no cover - type narrow
            assert cache_id == config.event_cache_id
            return list(self.payload)

    class QueueClientStub:
        def __init__(self) -> None:
            self.payload = {
                "uplink": 4,
                "alerts": 1,
            }

        def fetch_queue_depths(self, queue_group: str):  # pragma: no cover - type narrow
            assert queue_group == config.queue_group
            return dict(self.payload)

    sensor_stub = SensorClientStub()
    event_stub = EventClientStub()
    queue_stub = QueueClientStub()

    monkeypatch.setattr(
        telemetry,
        "FieldOpsSensorClient",
        lambda *args, **kwargs: sensor_stub,
    )
    monkeypatch.setattr(
        telemetry,
        "FieldOpsEventClient",
        lambda *args, **kwargs: event_stub,
    )
    monkeypatch.setattr(
        telemetry,
        "FieldOpsQueueClient",
        lambda *args, **kwargs: queue_stub,
    )

    return {
        "config": config,
        "sensor_stub": sensor_stub,
        "event_stub": event_stub,
        "queue_stub": queue_stub,
    }


def _is_isoformat_utc(value: str) -> bool:
    parsed = datetime.fromisoformat(value)
    return parsed.tzinfo is not None and parsed.tzinfo.utcoffset(parsed) == timezone.utc.utcoffset(parsed)


def test_collect_telemetry_snapshot_structure(telemetry_connector_stubs):
    """Default collector returns normalized structures and metadata."""

    snapshot = telemetry.collect_telemetry_snapshot()

    assert snapshot["status"] in {"ok", "degraded"}
    assert _is_isoformat_utc(snapshot["collected_at"])

    sensors = snapshot["metrics"]["sensors"]
    assert isinstance(sensors, list)
    assert sensors, "expected default sensor payload"
    for reading in sensors:
        assert {"sensor", "value", "unit", "timestamp"} <= set(reading)
        assert isinstance(reading["value"], (int, float))
        assert _is_isoformat_utc(reading["timestamp"])

    events = snapshot["metrics"]["events"]
    assert events["total_events"] >= 0
    for event in events["records"]:
        assert {"event", "count", "last_seen"} <= set(event)
        assert event["count"] >= 0
        assert _is_isoformat_utc(event["last_seen"])

    queues = snapshot["metrics"]["queues"]
    assert queues["total_backlog"] == sum(queues["queues"].values())
    for value in queues["queues"].values():
        assert value >= 0


def test_collect_telemetry_normalizes_units(telemetry_connector_stubs):
    """Unit conversion and timestamp parsing occurs for injected telemetry."""

    stubs = telemetry_connector_stubs

    stubs["sensor_stub"].payload = [
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

    stubs["event_stub"].payload = [
        {
            "event": "heartbeat",
            "count": 2,
            "last_seen": "2024-01-01T11:58:00+00:00",
        }
    ]

    stubs["queue_stub"].payload = {"uplink": 1, "alerts": 0}

    snapshot = telemetry.collect_telemetry_snapshot()

    sensors = snapshot["metrics"]["sensors"]
    assert sensors[0]["unit"] == "celsius"
    assert abs(sensors[0]["value"] - 30) < 0.01
    assert sensors[1]["unit"] == "percent"
    assert sensors[1]["value"] == pytest.approx(30.0)

    events = snapshot["metrics"]["events"]
    assert events["total_events"] == 2
    assert events["records"][0]["last_seen"].endswith("+00:00")

    queues = snapshot["metrics"]["queues"]
    assert queues["queues"]["uplink"] == 1
    assert queues["total_backlog"] == 1

