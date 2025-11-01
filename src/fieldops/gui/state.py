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

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Mapping, Sequence

from ..mission_loader import MissionAttachment, MissionContact, MissionManifest

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
    mission_workspace: "MissionWorkspaceState"
    operational_log_form: "OperationalLogFormState"

    def with_updates(self, **updates: Any) -> "FieldOpsGUIState":
        """Return a modified copy with ``updates`` applied."""

        return replace(self, **updates)


@dataclass(frozen=True)
class SyncResult:
    """Result returned by sync adapters after attempting an upload."""

    applied_operation_ids: tuple[str, ...]
    conflicts: tuple[ConflictPrompt, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class MissionContactCard:
    """Presentation-ready mission contact information."""

    role: str
    name: str
    callsign: str | None = None
    channel: str | None = None

    @classmethod
    def from_manifest(cls, contact: MissionContact) -> "MissionContactCard":
        """Build a card from a manifest contact."""

        return cls(
            role=contact.role,
            name=contact.name,
            callsign=contact.callsign,
            channel=contact.channel,
        )


@dataclass(frozen=True)
class MissionAttachmentLink:
    """Attachment metadata tuned for quick-link presentation."""

    label: str
    path: str
    category: str
    color_token: str
    media_type: str | None = None
    badge: str | None = None

    @classmethod
    def from_manifest(
        cls,
        attachment: MissionAttachment,
        *,
        label: str,
        category: str,
        color_token: str,
        badge: str | None,
    ) -> "MissionAttachmentLink":
        """Create a presentation link from manifest metadata."""

        return cls(
            label=label,
            path=attachment.path,
            category=category,
            color_token=color_token,
            media_type=attachment.media_type,
            badge=badge,
        )


@dataclass(frozen=True)
class MissionQuickLinks:
    """Attachment groupings surfaced as quick links."""

    sop: tuple[MissionAttachmentLink, ...] = field(default_factory=tuple)
    maps: tuple[MissionAttachmentLink, ...] = field(default_factory=tuple)
    comms: tuple[MissionAttachmentLink, ...] = field(default_factory=tuple)

    def all_links(self) -> tuple[MissionAttachmentLink, ...]:
        """Return all quick-link attachments for convenience."""

        return self.sop + self.maps + self.comms


@dataclass(frozen=True)
class MissionBriefing:
    """Normalized mission metadata for the GUI workspace."""

    mission_id: str
    name: str
    version: str
    summary: str | None
    classification: str | None
    created_at: datetime
    updated_at: datetime | None
    tags: tuple[str, ...]
    contacts: tuple[MissionContactCard, ...]
    quick_links: MissionQuickLinks
    attachments: tuple[MissionAttachmentLink, ...]

    @classmethod
    def from_manifest(
        cls,
        manifest: MissionManifest,
        *,
        quick_links: MissionQuickLinks,
        attachments: tuple[MissionAttachmentLink, ...],
    ) -> "MissionBriefing":
        """Construct a briefing summary from a manifest."""

        return cls(
            mission_id=manifest.mission_id,
            name=manifest.name,
            version=manifest.version,
            summary=manifest.summary,
            classification=manifest.classification,
            created_at=manifest.created_at,
            updated_at=manifest.updated_at,
            tags=manifest.tags,
            contacts=tuple(MissionContactCard.from_manifest(contact) for contact in manifest.contacts),
            quick_links=quick_links,
            attachments=attachments,
        )


@dataclass(frozen=True)
class MissionWorkspaceState:
    """Mission intake workspace state for the GUI."""

    status: str
    headline: str
    mission: MissionBriefing | None
    package_path: str | None
    staging_directory: str | None
    cache_directory: str | None
    extracted_file_count: int | None

    def with_updates(self, **updates: Any) -> "MissionWorkspaceState":
        """Return a modified copy with ``updates`` applied."""

        return replace(self, **updates)


def empty_mission_workspace() -> MissionWorkspaceState:
    """Return an empty mission workspace state for initialization."""

    return MissionWorkspaceState(
        status="idle",
        headline="Awaiting mission package",
        mission=None,
        package_path=None,
        staging_directory=None,
        cache_directory=None,
        extracted_file_count=None,
    )


@dataclass(frozen=True)
class GPSFix:
    """Structured GPS metadata captured alongside operational logs."""

    latitude: float
    longitude: float
    altitude_m: float | None = None
    horizontal_accuracy_m: float | None = None
    vertical_accuracy_m: float | None = None
    captured_at: datetime | None = None

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly payload describing the GPS fix."""

        payload: dict[str, Any] = {
            "lat": self.latitude,
            "lon": self.longitude,
        }
        if self.altitude_m is not None:
            payload["alt_m"] = self.altitude_m
        if self.horizontal_accuracy_m is not None:
            payload["h_acc_m"] = self.horizontal_accuracy_m
        if self.vertical_accuracy_m is not None:
            payload["v_acc_m"] = self.vertical_accuracy_m
        if self.captured_at is not None:
            payload["captured_at"] = self.captured_at.isoformat()
        return payload


@dataclass(frozen=True)
class PhotoAttachmentDraft:
    """Photo attachment metadata for operational log submissions."""

    path: str
    caption: str | None = None
    captured_at: datetime | None = None
    media_type: str | None = None
    size_bytes: int | None = None
    checksum: str | None = None
    thumbnail_path: str | None = None

    def to_payload(self) -> dict[str, Any]:
        """Serialize the attachment draft for queuing."""

        payload: dict[str, Any] = {"path": self.path}
        if self.caption:
            payload["caption"] = self.caption
        if self.captured_at is not None:
            payload["captured_at"] = self.captured_at.isoformat()
        if self.media_type:
            payload["media_type"] = self.media_type
        if self.size_bytes is not None:
            payload["size_bytes"] = self.size_bytes
        if self.checksum:
            payload["checksum"] = self.checksum
        if self.thumbnail_path:
            payload["thumbnail_path"] = self.thumbnail_path
        return payload


@dataclass(frozen=True)
class OperationalLogDraft:
    """Form submission payload for operational logging."""

    category: str
    title: str
    notes: str
    gps_fix: GPSFix | None = None
    attachments: tuple[PhotoAttachmentDraft, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    urgency: str = "routine"
    status: str = "open"

    def to_operation_payload(self) -> dict[str, Any]:
        """Convert the draft into an operation payload."""

        payload: dict[str, Any] = {
            "category": self.category,
            "title": self.title,
            "notes": self.notes,
            "urgency": self.urgency,
            "status": self.status,
            "tags": list(self.tags),
        }
        if self.gps_fix is not None:
            payload["gps"] = self.gps_fix.to_payload()
        if self.attachments:
            payload["attachments"] = [attachment.to_payload() for attachment in self.attachments]
        else:
            payload["attachments"] = []
        return payload


@dataclass(frozen=True)
class OperationalLogFormState:
    """UI state for the operational logging form."""

    categories: tuple[str, ...]
    selected_category: str
    backlog_count: int
    banner_message: str
    banner_token: str
    last_submission_id: str | None = None

    def with_backlog(self, backlog_count: int) -> "OperationalLogFormState":
        """Update the form with the latest backlog count and banner."""

        if backlog_count:
            message = f"{backlog_count} field log{'s' if backlog_count != 1 else ''} awaiting sync"
            token = "accent"
        else:
            message = "No pending field logs"
            token = "success"
        return replace(self, backlog_count=backlog_count, banner_message=message, banner_token=token)

    def with_submission(self, operation_id: str, backlog_count: int) -> "OperationalLogFormState":
        """Return a form state reflecting a newly queued submission."""

        updated = self.with_backlog(backlog_count)
        return replace(updated, last_submission_id=operation_id, selected_category=self.selected_category)


def default_operational_log_form() -> OperationalLogFormState:
    """Provide the default operational logging form configuration."""

    categories = ("SITREP", "CONTACT", "INCIDENT", "INTEL")
    return OperationalLogFormState(
        categories=categories,
        selected_category=categories[0],
        backlog_count=0,
        banner_message="No pending field logs",
        banner_token="success",
        last_submission_id=None,
    )

