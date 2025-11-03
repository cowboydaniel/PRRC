from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hq_command.sync import (
    HQSyncClient,
    MemoryTransport,
    OutboundChange,
    SyncEvent,
)


def test_client_connects_with_backoff_and_flushes_offline_queue() -> None:
    transport = MemoryTransport(fail_on_first_connect=True)
    client = HQSyncClient(transport, auth_token="test-token")

    # Queue a change before connectivity exists to ensure offline queueing works.
    change = OutboundChange(
        change_id="chg-1",
        resource_id="task-22",
        action="update",
        version=1,
        payload={"status": "in-progress"},
    )
    client.publish_change(change)

    client.ensure_connection(max_attempts=3)

    # Two connection attempts should be recorded with a backoff schedule.
    assert client.metrics.connect_attempts == 2
    assert client.metrics.failed_connections == 1
    assert client.metrics.successful_connections == 1
    assert client.metrics.reconnect_backoff_schedule == [0.5]

    # Offline change should be flushed once the connection succeeds.
    change_messages = [m for m in transport.sent_messages if m["type"] == "change"]
    assert change_messages and change_messages[0]["change_id"] == "chg-1"


def test_event_subscription_routes_payloads() -> None:
    transport = MemoryTransport()
    client = HQSyncClient(transport, auth_token="token")
    client.ensure_connection()

    received: list[SyncEvent] = []
    client.register_handler("task_update", lambda event: received.append(event))

    transport.queue_incoming(
        {
            "type": "event",
            "event_type": "task_update",
            "resource_id": "task-1",
            "version": 2,
            "payload": {"task_id": "task-1", "status": "assigned"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    client.process_incoming()

    assert len(received) == 1
    assert received[0].payload["status"] == "assigned"
    assert client.status_snapshot()["connection"] == "connected"


def test_conflict_detection_and_resolution() -> None:
    transport = MemoryTransport()
    client = HQSyncClient(transport, auth_token="token")
    client.record_local_state("task-9", version=3)
    client.ensure_connection()

    transport.queue_incoming(
        {
            "type": "event",
            "event_type": "task_update",
            "resource_id": "task-9",
            "version": 2,
            "payload": {"task_id": "task-9", "status": "stale"},
            "change_id": "remote-1",
        }
    )

    client.process_incoming()

    conflicts = client.conflicts()
    assert conflicts and conflicts[0].change_id == "remote-1"
    assert not conflicts[0].resolved

    client.resolve_conflict("remote-1", note="Applied remote update")
    conflicts = client.conflicts()
    assert conflicts[0].resolved is True
    assert conflicts[0].resolution_note == "Applied remote update"


def test_acknowledgements_clear_pending_changes() -> None:
    transport = MemoryTransport()
    client = HQSyncClient(transport, auth_token="token")
    client.ensure_connection()

    change = OutboundChange(
        change_id="chg-2",
        resource_id="task-31",
        action="update",
        version=5,
    )
    client.publish_change(change)

    transport.queue_incoming({"type": "ack", "change_id": "chg-2"})
    client.process_incoming()

    assert client.status_snapshot()["pending_changes"] == 0
    assert client.metrics.acknowledgements == 1


def test_presence_and_device_updates_record_state() -> None:
    transport = MemoryTransport()
    client = HQSyncClient(transport, auth_token="token")
    client.ensure_connection()

    now = datetime.now(timezone.utc)
    transport.queue_incoming(
        {
            "type": "presence",
            "records": [
                {
                    "operator_id": "op-7",
                    "status": "online",
                    "last_seen": now.isoformat(),
                    "display_name": "Operator Seven",
                }
            ],
        }
    )
    transport.queue_incoming(
        {
            "type": "device",
            "device_id": "field-3",
            "payload": {"signal": "good", "battery": 0.87},
        }
    )
    transport.queue_incoming(
        {
            "type": "geo",
            "resource_id": "task-31",
            "payload": {"lat": 39.1, "lon": -77.2},
        }
    )

    client.process_incoming()

    assert client.presence["op-7"].status == "online"
    assert client.device_status["field-3"]["battery"] == 0.87
    assert client.geo_state["task-31"]["lat"] == 39.1


def test_time_synchronization_tracks_delta_and_latency_metrics() -> None:
    transport = MemoryTransport()
    client = HQSyncClient(transport, auth_token="token")
    client.ensure_connection()

    server_time = datetime.now(timezone.utc) + timedelta(milliseconds=120)
    transport.queue_incoming(
        {"type": "time_sync", "server_time": server_time.isoformat()}
    )
    transport.queue_incoming(
        {
            "type": "event",
            "event_type": "telemetry_update",
            "resource_id": "telemetry-1",
            "version": 1,
            "payload": {"temperature": 21.5},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    client.process_incoming()

    # Delta should be within a reasonable bound of the injected value.
    assert abs(client.status_snapshot()["time_delta_ms"] - 120.0) < 50
    assert client.metrics.latency_measurements_ms

