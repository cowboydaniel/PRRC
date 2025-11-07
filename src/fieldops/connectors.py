"""FieldOps telemetry connectors (OPTIONAL - NOT CURRENTLY USED).

NOTE: This module is preserved for potential future use but is NOT currently
used by the telemetry system. The application is designed as offline-first
and collects telemetry from LOCAL hardware sensors on Dell Rugged Extreme
tablets (see hardware.py).

This module defines minimal HTTP clients that could communicate with external
FieldOps telemetry services if such integration were needed in the future.
The clients are intentionally lightweight so they can run on constrained
rugged devices while still surfacing actionable errors when configuration
or network steps fail.

For actual telemetry collection, see:
- fieldops/telemetry.py - Main telemetry collection module (uses local hardware)
- fieldops/hardware.py - Hardware sensor reading functions
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence
from urllib import error, request

__all__ = [
    "FieldOpsTelemetryConfig",
    "FieldOpsSensorClient",
    "FieldOpsEventClient",
    "FieldOpsQueueClient",
]


@dataclass(frozen=True)
class FieldOpsTelemetryConfig:
    """Configuration required to talk to the FieldOps telemetry APIs."""

    api_base_url: str
    api_token: str
    sensor_device_id: str
    event_cache_id: str
    queue_group: str
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "FieldOpsTelemetryConfig":
        """Load configuration from environment variables.

        Expected variables:
            FIELDOPS_API_BASE_URL – Base URL for the FieldOps telemetry API.
            FIELDOPS_API_TOKEN – Bearer token for authenticating requests.
            FIELDOPS_SENSOR_DEVICE_ID – Device identifier for sensor readings.
            FIELDOPS_EVENT_CACHE_ID – Cache identifier for buffered events.
            FIELDOPS_QUEUE_GROUP – Queue group to query for backlog metrics.
            FIELDOPS_API_TIMEOUT – Optional timeout (seconds) for HTTP calls.
        """

        env_map = {
            "FIELDOPS_API_BASE_URL": None,
            "FIELDOPS_API_TOKEN": None,
            "FIELDOPS_SENSOR_DEVICE_ID": None,
            "FIELDOPS_EVENT_CACHE_ID": None,
            "FIELDOPS_QUEUE_GROUP": None,
        }

        missing = []
        for key in env_map:
            value = os.environ.get(key)
            if not value:
                missing.append(key)
            else:
                env_map[key] = value

        if missing:
            raise RuntimeError(
                "Missing FieldOps telemetry configuration: "
                + ", ".join(sorted(missing))
            )

        timeout_value = os.environ.get("FIELDOPS_API_TIMEOUT")
        timeout_seconds = 10.0
        if timeout_value:
            try:
                timeout_seconds = float(timeout_value)
            except ValueError as exc:  # pragma: no cover - defensive branch
                raise RuntimeError(
                    "FIELDOPS_API_TIMEOUT must be numeric (seconds)."
                ) from exc

        return cls(
            api_base_url=env_map["FIELDOPS_API_BASE_URL"],
            api_token=env_map["FIELDOPS_API_TOKEN"],
            sensor_device_id=env_map["FIELDOPS_SENSOR_DEVICE_ID"],
            event_cache_id=env_map["FIELDOPS_EVENT_CACHE_ID"],
            queue_group=env_map["FIELDOPS_QUEUE_GROUP"],
            timeout_seconds=timeout_seconds,
        )


class _BaseFieldOpsClient:
    """Common functionality for FieldOps HTTP clients."""

    def __init__(self, base_url: str, token: str, timeout_seconds: float) -> None:
        if not base_url:
            raise RuntimeError("FieldOps client requires an API base URL.")
        if not token:
            raise RuntimeError("FieldOps client requires an API token.")

        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout_seconds

    def _get_json(self, path: str) -> Any:
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }
        req = request.Request(url, headers=headers)

        try:
            with request.urlopen(req, timeout=self._timeout) as resp:
                status = getattr(resp, "status", None)
                if status and status >= 400:
                    raise RuntimeError(
                        f"FieldOps API request to {url} failed with status {status}."
                    )
                raw = resp.read()
        except error.URLError as exc:
            raise RuntimeError(f"Failed to reach FieldOps API at {url}: {exc}.") from exc

        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"FieldOps API at {url} returned invalid JSON payload."
            ) from exc


class FieldOpsSensorClient(_BaseFieldOpsClient):
    """Client for interacting with the FieldOps sensor API."""

    def fetch_latest_readings(self, device_id: str) -> Sequence[Mapping[str, Any]]:
        if not device_id:
            raise RuntimeError("Sensor client requires a device identifier.")

        data = self._get_json(f"api/devices/{device_id}/sensors")

        if isinstance(data, Mapping):
            readings = data.get("readings")
        else:
            readings = data

        if not isinstance(readings, Iterable) or isinstance(readings, (str, bytes)):
            raise RuntimeError(
                "Sensor API returned an unexpected payload; expected a sequence of readings."
            )

        return list(readings)


class FieldOpsEventClient(_BaseFieldOpsClient):
    """Client for interacting with the FieldOps cached event API."""

    def fetch_cached_events(self, cache_id: str) -> Sequence[Mapping[str, Any]]:
        if not cache_id:
            raise RuntimeError("Event client requires an event cache identifier.")

        data = self._get_json(f"api/caches/{cache_id}/events")

        if isinstance(data, Mapping):
            events = data.get("events")
        else:
            events = data

        if not isinstance(events, Iterable) or isinstance(events, (str, bytes)):
            raise RuntimeError(
                "Event API returned an unexpected payload; expected a sequence of events."
            )

        return list(events)


class FieldOpsQueueClient(_BaseFieldOpsClient):
    """Client for interacting with FieldOps queue depth metrics."""

    def fetch_queue_depths(self, queue_group: str) -> Mapping[str, Any]:
        if not queue_group:
            raise RuntimeError("Queue client requires a queue group identifier.")

        data = self._get_json(f"api/queues/{queue_group}/depths")

        if not isinstance(data, Mapping):
            raise RuntimeError(
                "Queue API returned an unexpected payload; expected a mapping of queue depths."
            )

        return dict(data)
