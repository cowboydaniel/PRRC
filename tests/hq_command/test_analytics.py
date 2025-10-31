"""Tests for HQ Command analytics summaries."""
from __future__ import annotations

from datetime import datetime, timezone

from hq_command.analytics import summarize_field_telemetry
from fieldops.telemetry import (
    TelemetrySnapshot,
    TelemetryMetrics,
    SensorReading,
    EventSummary,
    EventRecord,
    QueueMetrics,
)


def _dt(hour: int, minute: int) -> str:
    return datetime(2024, 1, 1, hour, minute, tzinfo=timezone.utc).isoformat()


def build_sample_snapshot() -> TelemetrySnapshot:
    sensors = [
        SensorReading(
            sensor="temperature_probe",
            value=24.5,
            unit="celsius",
            timestamp=_dt(12, 0),
        ),
        SensorReading(
            sensor="temperature_probe",
            value=27.2,
            unit="celsius",
            timestamp=_dt(12, 15),
        ),
        SensorReading(
            sensor="battery_main",
            value=18.0,
            unit="percent",
            timestamp=_dt(12, 10),
        ),
    ]

    events = EventSummary(
        total_events=5,
        records=[
            EventRecord(
                event="uplink_success",
                count=4,
                last_seen=_dt(12, 5),
            ),
            EventRecord(
                event="motion_alert",
                count=1,
                last_seen=_dt(11, 58),
            ),
        ],
    )

    queues = QueueMetrics(
        queues={
            "uplink": 9,
            "alerts": 6,
        },
        total_backlog=15,
    )

    metrics = TelemetryMetrics(sensors=sensors, events=events, queues=queues)

    return TelemetrySnapshot(
        status="ok",
        collected_at=_dt(12, 16),
        metrics=metrics,
        notes=["snapshot synthesized for analytics test"],
    )


def test_summarize_field_telemetry_outputs_readiness_and_trends():
    snapshot = build_sample_snapshot()
    summary = summarize_field_telemetry(snapshot)

    assert summary["source_status"] == "ok"
    assert summary["overall_readiness"] == "watch"
    assert 40 <= summary["readiness_score"] < 100

    sensor_states = summary["sensor_states"]
    assert "battery_main" in sensor_states
    assert sensor_states["battery_main"]["status"] == "warning"

    sensor_trends = summary["sensor_trends"]
    assert sensor_trends["temperature_probe"]["delta"] == 2.7
    assert sensor_trends["temperature_probe"]["direction"] == "rising"

    queue_health = summary["queue_health"]
    assert queue_health["status"] == "warning"
    assert queue_health["total_backlog"] == 15

    assert summary["alerts"], "expected alerts when queue backlog elevated"


def test_summarize_field_telemetry_accepts_raw_mapping_payloads():
    snapshot = build_sample_snapshot()
    mapping_payload = {
        "status": "degraded",
        "collected_at": snapshot.collected_at,
        "metrics": {
            "sensors": [
                {
                    "sensor": "humidity_probe",
                    "value": 95.0,
                    "unit": "percent",
                    "timestamp": snapshot.collected_at,
                }
            ],
            "events": {
                "records": [],
                "total_events": 0,
            },
            "queues": {
                "queues": {"uplink": 3},
                "total_backlog": 3,
            },
        },
        "notes": [],
    }

    summary = summarize_field_telemetry(mapping_payload)

    assert summary["source_status"] == "degraded"
    assert summary["overall_readiness"] == "watch"
    assert summary["queue_health"]["status"] == "nominal"
    assert summary["sensor_states"]["humidity_probe"]["status"] == "critical"
    assert any("humidity" in alert for alert in summary["alerts"])

