"""Immutable audit event store with tamper detection and replay support."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import uuid
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, TypeVar


@dataclass(frozen=True)
class AuditEvent:
    """Single immutable event recorded in the audit store."""

    id: str
    aggregate_id: str
    event_type: str
    actor: str
    timestamp: datetime
    payload: Mapping[str, Any]
    version: int
    previous_hash: str
    event_hash: str


class TamperDetectionError(RuntimeError):
    """Raised when the event chain fails tamper detection verification."""


ReducerState = TypeVar("ReducerState")


class EventStore:
    """Append-only event store that chains hashes to detect tampering."""

    def __init__(self) -> None:
        self._events: List[AuditEvent] = []
        self._versions: Dict[str, int] = {}

    def append(
        self,
        *,
        aggregate_id: str,
        event_type: str,
        actor: str,
        payload: Optional[Mapping[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> AuditEvent:
        """Persist an immutable event and return it."""

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        elif timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        normalised_payload = json.loads(json.dumps(payload or {}, default=str))

        version = self._versions.get(aggregate_id, 0) + 1
        previous_hash = self._events[-1].event_hash if self._events else "genesis"
        raw_components = "|".join(
            [
                previous_hash,
                aggregate_id,
                event_type,
                actor,
                timestamp.isoformat(),
                json.dumps(normalised_payload, sort_keys=True, default=str),
                str(version),
            ]
        )
        event_hash = hashlib.sha256(raw_components.encode("utf-8")).hexdigest()

        event = AuditEvent(
            id=str(uuid.uuid4()),
            aggregate_id=aggregate_id,
            event_type=event_type,
            actor=actor,
            timestamp=timestamp,
            payload=normalised_payload,
            version=version,
            previous_hash=previous_hash,
            event_hash=event_hash,
        )

        self._events.append(event)
        self._versions[aggregate_id] = version
        return event

    def events(self, *, aggregate_id: Optional[str] = None) -> Tuple[AuditEvent, ...]:
        """Return all events, optionally filtered by aggregate identifier."""

        if aggregate_id is None:
            return tuple(self._events)
        return tuple(event for event in self._events if event.aggregate_id == aggregate_id)

    def verify(self) -> None:
        """Validate that the entire event chain remains untampered."""

        previous_hash = "genesis"
        for event in self._events:
            raw_components = "|".join(
                [
                    previous_hash,
                    event.aggregate_id,
                    event.event_type,
                    event.actor,
                    event.timestamp.isoformat(),
                    json.dumps(event.payload, sort_keys=True, default=str),
                    str(event.version),
                ]
            )
            expected_hash = hashlib.sha256(raw_components.encode("utf-8")).hexdigest()
            if event.event_hash != expected_hash:
                raise TamperDetectionError(
                    f"Event {event.id} failed hash verification; expected {expected_hash}"
                )
            previous_hash = event.event_hash

    def replay(
        self,
        *,
        aggregate_id: str,
        reducer: Callable[[ReducerState, AuditEvent], ReducerState],
        initial_state: ReducerState,
    ) -> ReducerState:
        """Replay events for an aggregate through a reducer function."""

        state = initial_state
        for event in self.events(aggregate_id=aggregate_id):
            state = reducer(state, event)
        return state

    def state_at(
        self,
        *,
        aggregate_id: str,
        reducer: Callable[[ReducerState, AuditEvent], ReducerState],
        initial_state: ReducerState,
        as_of: datetime,
    ) -> ReducerState:
        """Replay events up to a point in time and return the resulting state."""

        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)

        state = initial_state
        for event in self.events(aggregate_id=aggregate_id):
            if event.timestamp <= as_of:
                state = reducer(state, event)
        return state

    def playback_schedule(
        self,
        *,
        aggregate_id: str,
        playback_speed: float = 1.0,
    ) -> Tuple[Tuple[AuditEvent, float], ...]:
        """Return (event, delay) tuples describing a playback schedule."""

        if playback_speed <= 0:
            raise ValueError("playback_speed must be positive")

        aggregate_events = self.events(aggregate_id=aggregate_id)
        if not aggregate_events:
            return tuple()

        ordered = sorted(aggregate_events, key=lambda event: event.timestamp)
        schedule: List[Tuple[AuditEvent, float]] = []
        previous_ts = ordered[0].timestamp
        schedule.append((ordered[0], 0.0))

        for event in ordered[1:]:
            delta_seconds = (event.timestamp - previous_ts).total_seconds()
            schedule.append((event, delta_seconds / playback_speed))
            previous_ts = event.timestamp
        return tuple(schedule)

    def export(self) -> Tuple[Mapping[str, Any], ...]:
        """Return a serialisable snapshot of the event store."""

        exported: List[Mapping[str, Any]] = []
        for event in self._events:
            exported.append(
                {
                    "id": event.id,
                    "aggregate_id": event.aggregate_id,
                    "event_type": event.event_type,
                    "actor": event.actor,
                    "timestamp": event.timestamp.isoformat(),
                    "payload": dict(event.payload),
                    "version": event.version,
                    "previous_hash": event.previous_hash,
                    "event_hash": event.event_hash,
                }
            )
        return tuple(exported)

    def load_export(self, records: Sequence[Mapping[str, Any]]) -> None:
        """Load events from an export, replacing current state."""

        events: List[AuditEvent] = []
        versions: Dict[str, int] = {}
        previous_hash = "genesis"
        for record in records:
            timestamp = datetime.fromisoformat(record["timestamp"])
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            event = AuditEvent(
                id=record["id"],
                aggregate_id=record["aggregate_id"],
                event_type=record["event_type"],
                actor=record["actor"],
                timestamp=timestamp,
                payload=dict(record["payload"]),
                version=int(record["version"]),
                previous_hash=record["previous_hash"],
                event_hash=record["event_hash"],
            )
            events.append(event)
            versions[event.aggregate_id] = max(versions.get(event.aggregate_id, 0), event.version)
            previous_hash = event.event_hash

        self._events = events
        self._versions = versions
        self.verify()
