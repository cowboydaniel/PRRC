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
    task_dashboard: "TaskDashboardState"
    resource_requests: "ResourceRequestBoardState"

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


ACTION_TO_STATUS = {
    "accept": "accepted",
    "defer": "deferred",
    "escalate": "escalated",
    "complete": "completed",
}


def _priority_token(priority: str) -> str:
    normalized = priority.lower()
    if normalized in {"critical", "emergency", "immediate"}:
        return "danger"
    if normalized in {"high", "priority"}:
        return "accent"
    if normalized in {"routine", "low"}:
        return "success"
    return "neutral_700"


def _priority_sort_index(token: str) -> int:
    order = {"danger": 0, "accent": 1, "success": 2}
    return order.get(token, 3)


@dataclass(frozen=True)
class TaskAssignmentCard:
    """Card metadata surfaced in the task dashboard."""

    task_id: str
    title: str
    status: str
    priority: str
    display_status: str
    summary: str | None = None
    assignee: str | None = None
    due_at: datetime | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    location: str | None = None
    offline_action: str | None = None

    def with_offline_action(self, action: str | None) -> "TaskAssignmentCard":
        """Return a card highlighting an offline intent."""

        if not action:
            return replace(self, offline_action=None, display_status=self.status)
        status = ACTION_TO_STATUS.get(action, self.display_status)
        if action == "escalate":
            return replace(
                self,
                offline_action=action,
                display_status=status,
                priority="Emergency",
            )
        return replace(self, offline_action=action, display_status=status)

    def with_merged_action(self, action: str) -> "TaskAssignmentCard":
        """Return a card that reflects a merged action."""

        status = ACTION_TO_STATUS.get(action, self.status)
        if action == "escalate":
            return replace(
                self,
                status=status,
                display_status=status,
                offline_action=None,
                priority="Emergency",
            )
        return replace(self, status=status, display_status=status, offline_action=None)

    @property
    def priority_color_token(self) -> str:
        """Return the color token representing the task priority."""

        return _priority_token(self.priority)

    @classmethod
    def offline_placeholder(cls, task_id: str, action: str, timestamp: datetime) -> "TaskAssignmentCard":
        """Build a placeholder card when a task snapshot is unavailable."""

        status = ACTION_TO_STATUS.get(action, "pending")
        headline = f"Offline {action} pending"
        summary = "Awaiting HQ merge for task update"
        priority = "Emergency" if action == "escalate" else "priority"
        return cls(
            task_id=task_id,
            title=headline,
            status=status,
            display_status=status,
            priority=priority,
            summary=summary,
            due_at=timestamp,
            offline_action=action,
        )


@dataclass(frozen=True)
class TaskColumnState:
    """Column metadata for the task dashboard."""

    column_id: str
    title: str
    header_token: str
    tasks: tuple[TaskAssignmentCard, ...]


@dataclass(frozen=True)
class TaskDashboardState:
    """Structured dashboard data for task management."""

    columns: tuple[TaskColumnState, ...]
    pending_local_actions: int
    last_refreshed_at: datetime | None
    offline_badge_token: str
    offline_badge_message: str

    @classmethod
    def compose(
        cls,
        assignments: Sequence[TaskAssignmentCard],
        *,
        pending_actions: int,
        timestamp: datetime | None,
    ) -> "TaskDashboardState":
        """Build a dashboard view from assignments."""

        columns: dict[str, list[TaskAssignmentCard]] = {
            "pending": [],
            "accepted": [],
            "deferred": [],
            "escalated": [],
            "completed": [],
        }
        for assignment in assignments:
            bucket = assignment.display_status.lower()
            column_id = bucket if bucket in columns else "pending"
            columns[column_id].append(assignment)

        def _sorted(cards: list[TaskAssignmentCard]) -> tuple[TaskAssignmentCard, ...]:
            return tuple(
                sorted(
                    cards,
                    key=lambda card: (
                        card.offline_action is None,
                        _priority_sort_index(card.priority_color_token),
                        card.due_at or datetime.max,
                        card.title,
                    ),
                )
            )

        ordered_columns = (
            TaskColumnState(
                column_id="pending",
                title="Pending",
                header_token="secondary",
                tasks=_sorted(columns["pending"]),
            ),
            TaskColumnState(
                column_id="accepted",
                title="Accepted",
                header_token="secondary",
                tasks=_sorted(columns["accepted"]),
            ),
            TaskColumnState(
                column_id="deferred",
                title="Deferred",
                header_token="secondary",
                tasks=_sorted(columns["deferred"]),
            ),
            TaskColumnState(
                column_id="escalated",
                title="Escalated",
                header_token="secondary",
                tasks=_sorted(columns["escalated"]),
            ),
            TaskColumnState(
                column_id="completed",
                title="Completed",
                header_token="secondary",
                tasks=_sorted(columns["completed"]),
            ),
        )

        if pending_actions:
            badge_token = "accent"
            badge_message = f"{pending_actions} task update{'s' if pending_actions != 1 else ''} awaiting HQ merge"
        else:
            badge_token = "success"
            badge_message = "Task board synced"
        return cls(
            columns=ordered_columns,
            pending_local_actions=pending_actions,
            last_refreshed_at=timestamp,
            offline_badge_token=badge_token,
            offline_badge_message=badge_message,
        )


@dataclass(frozen=True)
class ResourceRequestCard:
    """Resource request metadata for the FieldOps board."""

    request_id: str
    requester: str
    summary: str
    priority: str
    status: str
    display_status: str
    quantity: int | None = None
    needed_at: datetime | None = None
    location: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    offline_action: str | None = None

    def with_offline_action(self, action: str | None) -> "ResourceRequestCard":
        """Return a card that reflects an offline action."""

        if not action:
            return replace(self, offline_action=None, display_status=self.status)
        status = ACTION_TO_STATUS.get(action, self.display_status)
        return replace(self, offline_action=action, display_status=status)

    def with_merged_action(self, action: str) -> "ResourceRequestCard":
        """Return a card after a merged action is applied."""

        status = ACTION_TO_STATUS.get(action, self.status)
        return replace(self, status=status, display_status=status, offline_action=None)

    @property
    def priority_color_token(self) -> str:
        """Return the color token describing request priority."""

        return _priority_token(self.priority)

    @classmethod
    def offline_placeholder(
        cls, request_id: str, action: str, timestamp: datetime
    ) -> "ResourceRequestCard":
        """Create a placeholder card when a request snapshot is missing."""

        status = ACTION_TO_STATUS.get(action, "pending")
        return cls(
            request_id=request_id,
            requester="Offline",
            summary=f"Offline {action} pending",
            priority="priority",
            status=status,
            display_status=status,
            needed_at=timestamp,
            offline_action=action,
        )


@dataclass(frozen=True)
class ResourceRequestBoardState:
    """Board summary for resource requests."""

    requests: tuple[ResourceRequestCard, ...]
    pending_local_actions: int
    headline: str
    last_refreshed_at: datetime | None
    offline_badge_token: str
    offline_badge_message: str

    @classmethod
    def compose(
        cls,
        requests: Sequence[ResourceRequestCard],
        *,
        pending_actions: int,
        timestamp: datetime | None,
    ) -> "ResourceRequestBoardState":
        """Build a board view from resource requests."""

        ordered = tuple(
            sorted(
                requests,
                key=lambda card: (
                    card.offline_action is None,
                    _priority_sort_index(card.priority_color_token),
                    card.needed_at or datetime.max,
                    card.summary,
                ),
            )
        )
        if pending_actions:
            badge_token = "accent"
            badge_message = (
                f"{pending_actions} resource update{'s' if pending_actions != 1 else ''} awaiting HQ merge"
            )
        else:
            badge_token = "success"
            badge_message = "Resource board synced"
        headline = "Resource Requests"
        return cls(
            requests=ordered,
            pending_local_actions=pending_actions,
            headline=headline,
            last_refreshed_at=timestamp,
            offline_badge_token=badge_token,
            offline_badge_message=badge_message,
        )


def empty_task_dashboard() -> TaskDashboardState:
    """Return an empty task dashboard."""

    return TaskDashboardState.compose((), pending_actions=0, timestamp=None)


def empty_resource_board() -> ResourceRequestBoardState:
    """Return an empty resource request board."""

    return ResourceRequestBoardState.compose((), pending_actions=0, timestamp=None)


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

