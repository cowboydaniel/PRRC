"""Tests for FieldOps telemetry snapshot collection."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from fieldops import telemetry


def _is_isoformat_utc(value: str) -> bool:
    parsed = datetime.fromisoformat(value)
    return parsed.tzinfo is not None and parsed.tzinfo.utcoffset(parsed) == timezone.utc.utcoffset(parsed)


def test_collect_telemetry_snapshot_structure():
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


def test_collect_telemetry_normalizes_units(monkeypatch: pytest.MonkeyPatch):
    """Unit conversion and timestamp parsing occurs for injected telemetry."""

    def fake_sensor_data():
        return [
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

    def fake_events():
        return [
            {
                "event": "heartbeat",
                "count": 2,
                "last_seen": "2024-01-01T11:58:00+00:00",
            }
        ]

    def fake_queues():
        return {"uplink": 1, "alerts": 0}

    monkeypatch.setattr(telemetry, "_load_sensor_api_data", fake_sensor_data)
    monkeypatch.setattr(telemetry, "_load_cached_events", fake_events)
    monkeypatch.setattr(telemetry, "_load_queue_depths", fake_queues)

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

