"""Real-time synchronization utilities for HQ Command.

The :mod:`hq_command.sync` module provides a lightweight, fully testable
abstraction for the Phase 4 roadmap goals covering WebSocket connectivity,
bidirectional change propagation, offline queueing, conflict management, and
telemetry required for HQ tasking operations.  The implementation is transport
agnostic so production deployments can wrap an actual WebSocket client while
tests exercise deterministic in-memory transports.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Deque, Dict, Iterable, List, MutableMapping, Optional
from collections import deque


EventHandler = Callable[["SyncEvent"], None]


@dataclass(slots=True)
class SyncEvent:
    """Structured real-time event delivered to subscribers."""

    event_type: str
    payload: MutableMapping[str, Any]
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class OutboundChange:
    """Describe a change initiated locally that must be synchronized."""

    change_id: str
    resource_id: str
    action: str
    version: int
    payload: MutableMapping[str, Any] = field(default_factory=dict)
    requires_ack: bool = True


@dataclass(slots=True)
class ConflictRecord:
    """Metadata describing a detected synchronization conflict."""

    change_id: str
    resource_id: str
    local_version: int
    remote_version: int
    payload: MutableMapping[str, Any]
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved: bool = False
    resolution_note: str | None = None


@dataclass(slots=True)
class PresenceRecord:
    """Represent the online status of an HQ operator."""

    operator_id: str
    status: str
    last_seen: datetime
    display_name: str | None = None


@dataclass(slots=True)
class ReliabilityMetrics:
    """Capture operational metrics for synchronization health."""

    connect_attempts: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    acknowledgements: int = 0
    reconnect_backoff_schedule: List[float] = field(default_factory=list)
    latency_measurements_ms: List[float] = field(default_factory=list)

    def record_backoff(self, delay_seconds: float) -> None:
        self.reconnect_backoff_schedule.append(delay_seconds)

    def record_latency(self, latency_ms: float) -> None:
        self.latency_measurements_ms.append(latency_ms)


@dataclass(slots=True)
class BackoffPolicy:
    """Simple exponential backoff policy without time.sleep dependencies."""

    initial_delay: float = 0.5
    multiplier: float = 2.0
    maximum_delay: float = 8.0

    def schedule(self, max_attempts: int) -> List[float]:
        delay = self.initial_delay
        schedule: List[float] = []
        for _ in range(max_attempts):
            schedule.append(delay)
            delay = min(delay * self.multiplier, self.maximum_delay)
        return schedule


class WebSocketTransport:
    """Minimal interface a transport implementation must provide."""

    def connect(self) -> None:  # pragma: no cover - interface only
        raise NotImplementedError

    def send(self, message: MutableMapping[str, Any]) -> None:  # pragma: no cover
        raise NotImplementedError

    def receive(self) -> Optional[MutableMapping[str, Any]]:  # pragma: no cover
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - interface only
        raise NotImplementedError


class MemoryTransport(WebSocketTransport):
    """In-memory WebSocket transport used for deterministic tests."""

    def __init__(self, *, fail_on_first_connect: bool = False) -> None:
        self._connected = False
        self._incoming: Deque[MutableMapping[str, Any]] = deque()
        self.sent_messages: List[MutableMapping[str, Any]] = []
        self._fail_on_first_connect = fail_on_first_connect
        self._attempts = 0

    def connect(self) -> None:
        self._attempts += 1
        if self._fail_on_first_connect and self._attempts == 1:
            raise ConnectionError("Simulated transient connection failure")
        self._connected = True

    def send(self, message: MutableMapping[str, Any]) -> None:
        if not self._connected:
            raise ConnectionError("Transport is not connected")
        self.sent_messages.append(message)

    def receive(self) -> Optional[MutableMapping[str, Any]]:
        if self._incoming:
            return self._incoming.popleft()
        return None

    def queue_incoming(self, message: MutableMapping[str, Any]) -> None:
        self._incoming.append(message)

    def close(self) -> None:
        self._connected = False


class HQSyncClient:
    """Client coordinating HQ Command real-time synchronization."""

    def __init__(
        self,
        transport: WebSocketTransport,
        *,
        auth_token: str,
        backoff: BackoffPolicy | None = None,
    ) -> None:
        self._transport = transport
        self._auth_token = auth_token
        self._backoff = backoff or BackoffPolicy()
        self._connected = False
        self._subscriptions: Dict[str, List[EventHandler]] = {}
        self._offline_queue: Deque[OutboundChange] = deque()
        self._pending_changes: Dict[str, OutboundChange] = {}
        self._resource_versions: Dict[str, int] = {}
        self._conflicts: Dict[str, ConflictRecord] = {}
        self._presence: Dict[str, PresenceRecord] = {}
        self._device_status: Dict[str, MutableMapping[str, Any]] = {}
        self._geo_state: Dict[str, MutableMapping[str, Any]] = {}
        self._time_delta_ms: float = 0.0
        self._last_sync: datetime | None = None
        self._metrics = ReliabilityMetrics()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def ensure_connection(self, *, max_attempts: int = 5) -> None:
        """Connect to the transport with exponential backoff retries."""

        schedule = self._backoff.schedule(max_attempts)
        for attempt, delay in enumerate(schedule, start=1):
            self._metrics.connect_attempts += 1
            try:
                self._transport.connect()
            except ConnectionError:
                self._metrics.failed_connections += 1
                self._metrics.record_backoff(delay)
                if attempt == len(schedule):
                    raise
            else:
                self._connected = True
                self._metrics.successful_connections += 1
                self._last_sync = datetime.now(timezone.utc)
                self._send_handshake()
                self._flush_offline_queue()
                return

    def _send_handshake(self) -> None:
        handshake = {
            "type": "auth",
            "token": self._auth_token,
            "requested_subscriptions": list(self._subscriptions.keys()),
            "client_time": datetime.now(timezone.utc).isoformat(),
        }
        self._transport.send(handshake)
        self._metrics.messages_sent += 1

    def close(self) -> None:
        self._transport.close()
        self._connected = False

    # ------------------------------------------------------------------
    # Subscription & event management
    # ------------------------------------------------------------------
    def register_handler(self, event_type: str, handler: EventHandler) -> None:
        handlers = self._subscriptions.setdefault(event_type, [])
        handlers.append(handler)
        if self._connected:
            self._send_subscription_update()

    def _send_subscription_update(self) -> None:
        message = {
            "type": "subscription_update",
            "subscriptions": list(self._subscriptions.keys()),
        }
        self._transport.send(message)
        self._metrics.messages_sent += 1

    def process_incoming(self, *, limit: Optional[int] = None) -> None:
        processed = 0
        while True:
            if limit is not None and processed >= limit:
                break
            message = self._transport.receive()
            if message is None:
                break
            processed += 1
            self._metrics.messages_received += 1
            message_type = message.get("type")
            if message_type == "event":
                self._handle_event(message)
            elif message_type == "ack":
                self._handle_ack(message)
            elif message_type == "time_sync":
                self._handle_time_sync(message)
            elif message_type == "presence":
                self._handle_presence(message)
            elif message_type == "device":
                self._handle_device_event(message)
            elif message_type == "geo":
                self._handle_geo_event(message)
            elif message_type == "latency":
                self._handle_latency(message)

    def _handle_event(self, message: MutableMapping[str, Any]) -> None:
        event_type = message.get("event_type", "")
        payload = message.get("payload", {})
        resource_id = message.get("resource_id")
        version = int(message.get("version", 0))
        timestamp = message.get("timestamp")
        if timestamp:
            try:
                sent_at = datetime.fromisoformat(timestamp)
            except ValueError:
                sent_at = None
            else:
                if sent_at.tzinfo is None:
                    sent_at = sent_at.replace(tzinfo=timezone.utc)
                latency = (datetime.now(timezone.utc) - sent_at).total_seconds() * 1000
                self._metrics.record_latency(latency)

        if resource_id is not None:
            current_version = self._resource_versions.get(resource_id, -1)
            if version < current_version:
                conflict = ConflictRecord(
                    change_id=message.get("change_id", f"conflict-{resource_id}"),
                    resource_id=resource_id,
                    local_version=current_version,
                    remote_version=version,
                    payload=payload,
                )
                self._conflicts[conflict.change_id] = conflict
            else:
                self._resource_versions[resource_id] = version

        event = SyncEvent(event_type=event_type, payload=payload)
        for handler in self._subscriptions.get(event_type, []):
            handler(event)

        self._last_sync = datetime.now(timezone.utc)

    def _handle_ack(self, message: MutableMapping[str, Any]) -> None:
        change_id = message.get("change_id")
        if change_id and change_id in self._pending_changes:
            del self._pending_changes[change_id]
        self._metrics.acknowledgements += 1
        self._last_sync = datetime.now(timezone.utc)

    def _handle_time_sync(self, message: MutableMapping[str, Any]) -> None:
        server_time_raw = message.get("server_time")
        if not server_time_raw:
            return
        server_time = datetime.fromisoformat(server_time_raw)
        if server_time.tzinfo is None:
            server_time = server_time.replace(tzinfo=timezone.utc)
        delta = server_time - datetime.now(timezone.utc)
        self._time_delta_ms = delta.total_seconds() * 1000
        self._last_sync = datetime.now(timezone.utc)

    def _handle_presence(self, message: MutableMapping[str, Any]) -> None:
        records: Iterable[MutableMapping[str, Any]] = message.get("records", [])
        for record in records:
            operator_id = record["operator_id"]
            status = record.get("status", "unknown")
            last_seen_raw = record.get("last_seen")
            last_seen = (
                datetime.fromisoformat(last_seen_raw)
                if last_seen_raw
                else datetime.now(timezone.utc)
            )
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            presence = PresenceRecord(
                operator_id=operator_id,
                status=status,
                last_seen=last_seen,
                display_name=record.get("display_name"),
            )
            self._presence[operator_id] = presence

    def _handle_device_event(self, message: MutableMapping[str, Any]) -> None:
        device_id = message.get("device_id")
        payload = message.get("payload", {})
        if device_id:
            self._device_status[device_id] = payload

    def _handle_geo_event(self, message: MutableMapping[str, Any]) -> None:
        resource_id = message.get("resource_id")
        payload = message.get("payload", {})
        if resource_id:
            self._geo_state[resource_id] = payload

    def _handle_latency(self, message: MutableMapping[str, Any]) -> None:
        latency_ms = float(message.get("latency_ms", 0.0))
        self._metrics.record_latency(latency_ms)

    # ------------------------------------------------------------------
    # Outbound change management
    # ------------------------------------------------------------------
    def publish_change(self, change: OutboundChange) -> None:
        """Publish a locally initiated change, queueing when offline."""

        if self._connected:
            self._send_change(change)
        else:
            self._offline_queue.append(change)
        if change.requires_ack:
            self._pending_changes[change.change_id] = change
        self._resource_versions[change.resource_id] = change.version

    def _send_change(self, change: OutboundChange) -> None:
        message = {
            "type": "change",
            "change_id": change.change_id,
            "resource_id": change.resource_id,
            "action": change.action,
            "version": change.version,
            "payload": change.payload,
            "requires_ack": change.requires_ack,
        }
        self._transport.send(message)
        self._metrics.messages_sent += 1

    def _flush_offline_queue(self) -> None:
        while self._offline_queue:
            change = self._offline_queue.popleft()
            self._send_change(change)

    # ------------------------------------------------------------------
    # Conflict management
    # ------------------------------------------------------------------
    def resolve_conflict(self, change_id: str, *, note: str | None = None) -> None:
        conflict = self._conflicts.get(change_id)
        if not conflict:
            return
        conflict.resolved = True
        conflict.resolution_note = note

    def conflicts(self) -> List[ConflictRecord]:
        return list(self._conflicts.values())

    # ------------------------------------------------------------------
    # State inspection helpers
    # ------------------------------------------------------------------
    def status_snapshot(self) -> Dict[str, Any]:
        """Return dashboard-friendly status indicators."""

        return {
            "connection": "connected" if self._connected else "offline",
            "pending_changes": len(self._pending_changes),
            "offline_queue": len(self._offline_queue),
            "conflicts": len([c for c in self._conflicts.values() if not c.resolved]),
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "time_delta_ms": self._time_delta_ms,
        }

    @property
    def metrics(self) -> ReliabilityMetrics:
        return self._metrics

    @property
    def presence(self) -> Dict[str, PresenceRecord]:
        return self._presence

    @property
    def device_status(self) -> Dict[str, MutableMapping[str, Any]]:
        return self._device_status

    @property
    def geo_state(self) -> Dict[str, MutableMapping[str, Any]]:
        return self._geo_state

    def record_local_state(self, resource_id: str, version: int) -> None:
        self._resource_versions[resource_id] = version

