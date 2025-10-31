"""Analytics helpers that turn FieldOps telemetry into HQ insights."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, Mapping

QUEUE_WARNING_THRESHOLD = 10
QUEUE_CRITICAL_THRESHOLD = 25


def summarize_field_telemetry(telemetry: Mapping[str, Any] | Any) -> Dict[str, Any]:
    """Produce readiness indicators and alerting metadata for HQ dashboards.

    The collector intentionally accepts either a :class:`TelemetrySnapshot`
    instance or a mapping with an equivalent schema.  This flexibility keeps the
    analytics layer decoupled from the FieldOps package while still enabling
    tests to construct lightweight payloads.

    Args:
        telemetry: Telemetry snapshot sourced from FieldOps.

    Returns:
        High-level readiness metrics, alert states, and trend deltas.
    """

    snapshot = _coerce_snapshot(telemetry)

    sensors = snapshot.get("metrics", {}).get("sensors", [])
    events = snapshot.get("metrics", {}).get("events", {})
    queues = snapshot.get("metrics", {}).get("queues", {})

    sensor_states, sensor_trends, sensor_alerts = _analyze_sensors(sensors)
    queue_health, queue_alerts = _analyze_queues(queues)
    event_summary = _summarize_events(events)

    alerts = sensor_alerts + queue_alerts

    readiness_score = _compute_readiness_score(
        snapshot.get("status", "unknown"),
        sensor_states,
        queue_health,
    )
    readiness_level = _readiness_level_from_score(readiness_score, alerts)

    notes = list(snapshot.get("notes", []))
    if alerts:
        notes.append("Alerts active: " + "; ".join(alerts))

    return {
        "source_status": snapshot.get("status", "unknown"),
        "collected_at": snapshot.get("collected_at"),
        "overall_readiness": readiness_level,
        "readiness_score": readiness_score,
        "alerts": alerts,
        "sensor_states": sensor_states,
        "sensor_trends": sensor_trends,
        "queue_health": queue_health,
        "event_overview": event_summary,
        "notes": notes,
    }


def _coerce_snapshot(telemetry: Mapping[str, Any] | Any) -> Dict[str, Any]:
    if is_dataclass(telemetry):
        return asdict(telemetry)
    if isinstance(telemetry, Mapping):
        return dict(telemetry)
    raise TypeError(
        "Telemetry payload must be a dataclass instance or mapping compatible with the FieldOps snapshot schema."
    )


def _analyze_sensors(
    sensors: Iterable[Mapping[str, Any]]
) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], list[str]]:
    states: Dict[str, Dict[str, Any]] = {}
    trends: Dict[str, Dict[str, Any]] = {}
    alerts: list[str] = []

    grouped: Dict[str, list[Mapping[str, Any]]] = {}
    for reading in sensors:
        name = str(reading.get("sensor", "unknown"))
        grouped.setdefault(name, []).append(reading)

    for name, readings in grouped.items():
        ordered = sorted(
            readings,
            key=lambda item: _safe_parse_timestamp(item.get("timestamp")),
        )
        latest = ordered[-1]
        state = _classify_sensor_state(name, latest)
        states[name] = state

        trend = _compute_sensor_trend(name, ordered)
        if trend:
            trends[name] = trend

        severity = state.get("status")
        if severity in {"warning", "critical"}:
            alerts.append(
                f"Sensor {name} reporting {severity} level ({state.get('value')} {state.get('unit')})."
            )

    return states, trends, alerts


def _safe_parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.min
    return datetime.min


def _classify_sensor_state(name: str, reading: Mapping[str, Any]) -> Dict[str, Any]:
    value = reading.get("value")
    unit = reading.get("unit")
    status = "nominal"
    rationale = "within expected range"

    if value is None:
        status = "unknown"
        rationale = "no current reading"
    else:
        status, rationale = _evaluate_sensor_thresholds(name, float(value), str(unit or ""))

    return {
        "status": status,
        "value": value,
        "unit": unit,
        "timestamp": reading.get("timestamp"),
        "rationale": rationale,
    }


def _evaluate_sensor_thresholds(
    name: str, value: float, unit: str
) -> tuple[str, str]:
    normalized_name = name.lower()
    unit_lower = unit.lower()

    def temperature_thresholds(val: float) -> tuple[str, str]:
        if val >= 40 or val <= -10:
            return "critical", "temperature outside safe operating range"
        if val >= 35 or val <= 0:
            return "warning", "temperature approaching limits"
        return "nominal", "temperature stable"

    def battery_thresholds(val: float) -> tuple[str, str]:
        if val <= 10:
            return "critical", "battery nearly depleted"
        if val <= 25:
            return "warning", "battery reserve low"
        return "nominal", "battery level healthy"

    def humidity_thresholds(val: float) -> tuple[str, str]:
        if val <= 10 or val >= 90:
            return "critical", "humidity at damaging levels"
        if val <= 20 or val >= 80:
            return "warning", "humidity approaching extremes"
        return "nominal", "humidity within comfort band"

    def pressure_thresholds(val: float) -> tuple[str, str]:
        if val <= 80 or val >= 120:
            return "critical", "pressure outside tolerance"
        if val <= 90 or val >= 110:
            return "warning", "pressure trending to limit"
        return "nominal", "pressure nominal"

    if "temp" in normalized_name and unit_lower in {"c", "celsius", "kelvin"}:
        return temperature_thresholds(value)
    if any(keyword in normalized_name for keyword in ("battery", "power")):
        return battery_thresholds(value)
    if "humidity" in normalized_name:
        return humidity_thresholds(value)
    if any(keyword in normalized_name for keyword in ("pressure", "psi", "bar")):
        return pressure_thresholds(value)

    return "nominal", "within expected range"


def _compute_sensor_trend(
    name: str, readings: Iterable[Mapping[str, Any]]
) -> Dict[str, Any] | None:
    ordered = [r for r in readings if isinstance(r.get("value"), (int, float))]
    if len(ordered) < 2:
        return None

    start = ordered[0]
    end = ordered[-1]
    delta = float(end["value"]) - float(start["value"])
    direction = "steady"
    if delta > 0.5:
        direction = "rising"
    elif delta < -0.5:
        direction = "falling"

    return {
        "delta": round(delta, 2),
        "start": start.get("value"),
        "end": end.get("value"),
        "unit": end.get("unit"),
        "direction": direction,
    }


def _analyze_queues(queues: Mapping[str, Any]) -> tuple[Dict[str, Any], list[str]]:
    backlog = int(queues.get("total_backlog", 0))
    queue_map = queues.get("queues") if isinstance(queues.get("queues"), Mapping) else {}
    status = "nominal"
    alerts: list[str] = []

    if backlog >= QUEUE_CRITICAL_THRESHOLD:
        status = "critical"
        alerts.append(
            f"Queue backlog {backlog} exceeds critical threshold {QUEUE_CRITICAL_THRESHOLD}."
        )
    elif backlog >= QUEUE_WARNING_THRESHOLD:
        status = "warning"
        alerts.append(
            f"Queue backlog {backlog} exceeds warning threshold {QUEUE_WARNING_THRESHOLD}."
        )

    details = {
        "status": status,
        "total_backlog": backlog,
        "queues": dict(queue_map),
        "thresholds": {
            "warning": QUEUE_WARNING_THRESHOLD,
            "critical": QUEUE_CRITICAL_THRESHOLD,
        },
    }
    return details, alerts


def _summarize_events(events: Mapping[str, Any]) -> Dict[str, Any]:
    records = events.get("records") if isinstance(events.get("records"), Iterable) else []
    recent_events = [
        {
            "event": record.get("event"),
            "count": int(record.get("count", 0)),
            "last_seen": record.get("last_seen"),
        }
        for record in records
    ]

    total_events = int(events.get("total_events", sum(r["count"] for r in recent_events)))

    return {
        "total_events": total_events,
        "recent_events": recent_events,
    }


def _compute_readiness_score(
    source_status: str,
    sensor_states: Mapping[str, Mapping[str, Any]],
    queue_health: Mapping[str, Any],
) -> int:
    score = 100

    if source_status not in {"ok", "ready"}:
        score -= 10

    for state in sensor_states.values():
        status = state.get("status")
        if status == "warning":
            score -= 15
        elif status == "critical":
            score -= 35
        elif status == "unknown":
            score -= 5

    queue_status = queue_health.get("status")
    if queue_status == "warning":
        score -= 10
    elif queue_status == "critical":
        score -= 25

    return max(0, min(100, score))


def _readiness_level_from_score(score: int, alerts: Iterable[str]) -> str:
    if score >= 80 and not list(alerts):
        return "ready"
    if score >= 50:
        return "watch"
    return "critical"

