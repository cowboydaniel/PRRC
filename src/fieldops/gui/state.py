"""State containers for the FieldOps GUI foundation.

The FieldOps desktop client targets Dell Rugged deployments that operate in
intermittent or denied network environments.  Rather than binding directly to a
Qt widget hierarchy, these dataclasses capture the view-model state the GUI
must expose: sync banners, conflict prompts, and mesh networking telemetry.

Phase 3 of the roadmap builds upon the validated mission and telemetry
workflows from earlier phases.  These structures keep the GUI logic portable so
that PySide6 screens, CLI fallbacks, and tests can all reason about a common
state representation without requiring a Qt event loop.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Mapping, Sequence

SyncMode = str
MeshHealth = str


@dataclass(frozen=True)
class OfflineOperation:
    """Queued GUI intent that must be synchronized with HQ when online."""

    operation_id: str
    operation_type: str
    payload: Mapping[str, Any]
    created_at: datetime
    requires_ack: bool = True

    def to_json(self) -> dict[str, Any]:
        """Serialize the operation for disk persistence."""

        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "payload": self._convert_payload(self.payload),
            "created_at": self.created_at.isoformat(),
            "requires_ack": self.requires_ack,
        }

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> "OfflineOperation":
        """Rehydrate an :class:`OfflineOperation` from JSON data."""

        return cls(
            operation_id=str(payload["operation_id"]),
            operation_type=str(payload["operation_type"]),
            payload=payload.get("payload", {}),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            requires_ack=bool(payload.get("requires_ack", True)),
        )

    def with_payload(self, payload: Mapping[str, Any]) -> "OfflineOperation":
        """Return a copy of the operation with a new payload."""

        return replace(self, payload=payload)

    @staticmethod
    def _convert_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Normalize nested payload values for JSON serialization."""

        def _convert(value: Any) -> Any:
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, Mapping):
                return {k: _convert(v) for k, v in value.items()}
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
                return [
                    _convert(v)
                    for v in value
                ]
            return value

        return {k: _convert(v) for k, v in payload.items()}


@dataclass(frozen=True)
class ConflictPrompt:
    """Conflict details surfaced to the GUI for operator review."""

    operation_id: str
    headline: str
    details: str
    local_snapshot: Mapping[str, Any] | None
    remote_snapshot: Mapping[str, Any] | None
    severity: str = "warning"
    resolution_hint: str | None = None


@dataclass(frozen=True)
class MeshLink:
    """Represents a link discovered in the local mesh topology."""

    node_id: str
    link_quality: float
    signal_dbm: float
    latency_ms: float | None
    status: str
    last_seen: datetime
    hop_count: int

    def normalized_quality(self) -> float:
        """Clamp the quality metric between 0.0 and 1.0."""

        return max(0.0, min(1.0, self.link_quality))


@dataclass(frozen=True)
class MeshTopology:
    """Aggregated mesh awareness used to drive status banners."""

    links: tuple[MeshLink, ...]
    mesh_health: MeshHealth
    last_updated: datetime | None
    mesh_summary: str = ""


@dataclass(frozen=True)
class SyncState:
    """High-level sync banner information for the GUI."""

    mode: SyncMode
    message: str
    last_synced_at: datetime | None
    pending_operations: int
    conflict_count: int

    def with_updates(self, **updates: Any) -> "SyncState":
        """Return a modified copy with ``updates`` applied."""

        return replace(self, **updates)


@dataclass(frozen=True)
class FieldOpsGUIState:
    """Composite state consumed by GUI views and status widgets."""

    sync: SyncState
    offline_queue: tuple[OfflineOperation, ...]
    conflict_prompts: tuple[ConflictPrompt, ...]
    mesh: MeshTopology

    def with_updates(self, **updates: Any) -> "FieldOpsGUIState":
        """Return a modified copy with ``updates`` applied."""

        return replace(self, **updates)


@dataclass(frozen=True)
class SyncResult:
    """Result returned by sync adapters after attempting an upload."""

    applied_operation_ids: tuple[str, ...]
    conflicts: tuple[ConflictPrompt, ...]
    errors: tuple[str, ...]

