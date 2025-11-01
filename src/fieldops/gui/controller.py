"""Offline-first FieldOps GUI controller logic."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping, Protocol, Sequence

_SUPPORTED_ACTIONS = {"accept", "defer", "escalate"}

from .offline_cache import OfflineQueueStorage
from .state import (
    ConflictPrompt,
    FieldOpsGUIState,
    MissionAttachmentLink,
    MissionBriefing,
    MissionQuickLinks,
    MissionWorkspaceState,
    MeshHealth,
    MeshLink,
    MeshTopology,
    OperationalLogDraft,
    OperationalLogFormState,
    OfflineOperation,
    ResourceRequestBoardState,
    ResourceRequestCard,
    SyncResult,
    SyncState,
    TaskAssignmentCard,
    TaskDashboardState,
    default_operational_log_form,
    empty_mission_workspace,
    empty_resource_board,
    empty_task_dashboard,
)
from ..mission_loader import MissionAttachment, MissionManifest, load_mission_package


class SyncAdapter(Protocol):
    """Protocol describing sync adapters used by the controller."""

    def is_available(self) -> bool:  # pragma: no cover - structural typing hook
        """Return ``True`` if a backhaul or HQ connection is available."""

    def push_operations(self, operations: Sequence[OfflineOperation]) -> SyncResult:
        """Attempt to upload operations to HQ, returning a :class:`SyncResult`."""


class FieldOpsGUIController:
    """Coordinates offline queue management and mesh awareness for the GUI."""

    def __init__(
        self,
        cache_path: Path,
        sync_adapter: SyncAdapter,
        *,
        clock: Callable[[], datetime] | None = None,
        mission_loader: Callable[[Path], Mapping[str, object]] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._adapter = sync_adapter
        self._storage = OfflineQueueStorage(cache_path)
        self._queue: list[OfflineOperation] = self._storage.load()
        self._mission_loader = mission_loader or load_mission_package
        initial_mode = "idle" if self._adapter.is_available() else "offline"
        self._state = FieldOpsGUIState(
            sync=SyncState(
                mode=initial_mode,
                message="Ready for mission intake" if initial_mode == "idle" else "Awaiting mesh uplink",
                last_synced_at=None,
                pending_operations=len(self._queue),
                conflict_count=0,
            ),
            offline_queue=tuple(self._queue),
            conflict_prompts=(),
            mesh=MeshTopology(links=(), mesh_health="unknown", last_updated=None, mesh_summary="Mesh scan pending"),
            mission_workspace=empty_mission_workspace(),
            operational_log_form=self._initial_log_form_state(),
            task_dashboard=empty_task_dashboard(),
            resource_requests=empty_resource_board(),
        )
        self._task_baseline: dict[str, TaskAssignmentCard] = {}
        self._pending_task_actions: dict[str, str] = {}
        self._resource_baseline: dict[str, ResourceRequestCard] = {}
        self._pending_resource_actions: dict[str, str] = {}

    def get_state(self) -> FieldOpsGUIState:
        """Return the current GUI state."""

        return self._state

    def prepare_log_form(self) -> OperationalLogFormState:
        """Return the current operational log form state for rendering."""

        return self._state.operational_log_form

    def submit_operational_log(self, draft: OperationalLogDraft) -> OfflineOperation:
        """Queue a completed operational log form for synchronization."""

        operation = self.queue_operation("operational-log", draft.to_operation_payload())
        self._state = self._state.with_updates(
            operational_log_form=self._state.operational_log_form.with_submission(
                operation.operation_id,
                len(self._queue),
            )
        )
        return operation

    def queue_operation(self, operation_type: str, payload: dict) -> OfflineOperation:
        """Queue an operation for later synchronization."""

        operation = OfflineOperation(
            operation_id=f"op-{self._clock().timestamp():.0f}-{len(self._queue) + 1}",
            operation_type=operation_type,
            payload=payload,
            created_at=self._clock(),
        )
        self._queue.append(operation)
        self._persist_queue()
        self._update_state_after_queue()
        return operation

    def update_task_assignments(
        self, assignments: Iterable[TaskAssignmentCard]
    ) -> TaskDashboardState:
        """Refresh the task dashboard with the latest assignments."""

        self._task_baseline = {
            assignment.task_id: assignment.with_offline_action(None)
            for assignment in assignments
        }
        return self._compose_task_dashboard(timestamp=self._clock())

    def update_resource_requests(
        self, requests: Iterable[ResourceRequestCard]
    ) -> ResourceRequestBoardState:
        """Refresh the resource request board with the latest snapshot."""

        self._resource_baseline = {
            request.request_id: request.with_offline_action(None)
            for request in requests
        }
        return self._compose_resource_board(timestamp=self._clock())

    def apply_task_action(
        self, task_id: str, action: str, *, notes: str | None = None
    ) -> OfflineOperation:
        """Apply a local action to a task assignment."""

        payload: dict[str, object] = {"task_id": task_id, "action": action}
        if notes:
            payload["notes"] = notes
        if action not in _SUPPORTED_ACTIONS:
            raise ValueError(f"Unsupported task action: {action}")
        if task_id not in self._task_baseline:
            placeholder = TaskAssignmentCard.offline_placeholder(task_id, action, self._clock())
            self._task_baseline[task_id] = placeholder.with_offline_action(None)
        operation = self.queue_operation("task-action", payload)
        self._pending_task_actions[task_id] = action
        self._compose_task_dashboard()
        return operation

    def apply_resource_request_action(
        self, request_id: str, action: str, *, notes: str | None = None
    ) -> OfflineOperation:
        """Apply a local action to a resource request."""

        payload: dict[str, object] = {"request_id": request_id, "action": action}
        if notes:
            payload["notes"] = notes
        if action not in _SUPPORTED_ACTIONS:
            raise ValueError(f"Unsupported resource request action: {action}")
        if request_id not in self._resource_baseline:
            placeholder = ResourceRequestCard.offline_placeholder(request_id, action, self._clock())
            self._resource_baseline[request_id] = placeholder.with_offline_action(None)
        operation = self.queue_operation("resource-request-action", payload)
        self._pending_resource_actions[request_id] = action
        self._compose_resource_board()
        return operation

    def attempt_sync(self) -> SyncState:
        """Attempt to synchronize the offline queue with HQ."""

        if not self._adapter.is_available():
            return self._set_sync_state(
                mode="offline",
                message="No mesh backhaul detected – queued actions ready for resend",
                conflicts=self._state.conflict_prompts,
            )
        if not self._queue:
            return self._set_sync_state(
                mode="idle",
                message="All field updates delivered",
                conflicts=(),
            )

        self._set_sync_state(
            mode="syncing",
            message="Syncing queued field updates",
            conflicts=self._state.conflict_prompts,
        )
        operations_by_id = {operation.operation_id: operation for operation in self._queue}
        result = self._adapter.push_operations(tuple(self._queue))
        applied_ids = set(result.applied_operation_ids)
        if applied_ids:
            applied_operations = [operations_by_id[op_id] for op_id in applied_ids if op_id in operations_by_id]
            self._queue = [operation for operation in self._queue if operation.operation_id not in applied_ids]
            if self._queue:
                self._persist_queue()
            else:
                self._storage.clear()
            self._clear_offline_action_flags(applied_operations)
        conflicts = result.conflicts
        self._state = self._state.with_updates(
            conflict_prompts=conflicts,
            offline_queue=tuple(self._queue),
        )
        if result.errors:
            return self._set_sync_state(
                mode="error",
                message="; ".join(result.errors),
                conflicts=conflicts,
            )
        if conflicts:
            return self._set_sync_state(
                mode="conflict",
                message="Review {count} conflicted updates".format(count=len(conflicts)),
                conflicts=conflicts,
            )
        return self._set_sync_state(
            mode="idle",
            message="Field updates delivered",
            conflicts=(),
            last_synced_at=self._clock(),
        )

    def apply_conflict_resolution(self, operation_id: str, payload: dict) -> ConflictPrompt | None:
        """Update an operation with a resolved payload and drop the prompt."""

        updated_operation: OfflineOperation | None = None
        removed_prompt = next(
            (prompt for prompt in self._state.conflict_prompts if prompt.operation_id == operation_id),
            None,
        )
        for index, operation in enumerate(self._queue):
            if operation.operation_id == operation_id:
                updated_operation = operation.with_payload(payload)
                self._queue[index] = updated_operation
                break
        if updated_operation is None:
            raise KeyError(f"Operation not found in queue: {operation_id}")

        remaining_prompts = tuple(
            prompt for prompt in self._state.conflict_prompts if prompt.operation_id != operation_id
        )
        self._state = self._state.with_updates(
            conflict_prompts=remaining_prompts,
            offline_queue=tuple(self._queue),
        )
        self._persist_queue()
        self._refresh_sync_metadata()
        return removed_prompt

    def update_mesh_topology(self, links: Iterable[MeshLink]) -> MeshTopology:
        """Update mesh awareness information for the GUI."""

        link_tuple = tuple(links)
        health = self._classify_mesh_health(link_tuple)
        summary = self._summarize_mesh(link_tuple, health)
        topology = MeshTopology(
            links=link_tuple,
            mesh_health=health,
            last_updated=self._clock(),
            mesh_summary=summary,
        )
        self._state = self._state.with_updates(mesh=topology)
        if health in {"offline", "degraded"}:
            self._set_sync_state(
                mode="offline" if health == "offline" else self._state.sync.mode,
                message=summary,
                conflicts=self._state.conflict_prompts,
            )
        return topology

    def ingest_mission_package(self, package_path: Path) -> MissionWorkspaceState:
        """Ingest a mission package and update the workspace state."""

        summary = self._mission_loader(package_path)
        manifest = summary.get("manifest")
        workspace = self._state.mission_workspace
        if isinstance(manifest, MissionManifest):
            attachments = self._build_attachment_links(manifest)
            quick_links = MissionQuickLinks(
                sop=tuple(link for link in attachments if link.category == "sop"),
                maps=tuple(link for link in attachments if link.category == "map"),
                comms=tuple(link for link in attachments if link.category == "comms"),
            )
            mission = MissionBriefing.from_manifest(
                manifest,
                quick_links=quick_links,
                attachments=attachments,
            )
            headline = f"{mission.name} ready for briefing"
            workspace = workspace.with_updates(
                status="ready",
                headline=headline,
                mission=mission,
                package_path=str(summary.get("package_path")) if summary.get("package_path") else None,
                staging_directory=str(summary.get("staging_directory")) if summary.get("staging_directory") else None,
                cache_directory=str(summary.get("cache_directory")) if summary.get("cache_directory") else None,
                extracted_file_count=summary.get("extracted_file_count"),
            )
        else:
            workspace = workspace.with_updates(
                status="staged",
                headline="Package staged – manifest not found",
                mission=None,
                package_path=str(summary.get("package_path")) if summary.get("package_path") else None,
                staging_directory=str(summary.get("staging_directory")) if summary.get("staging_directory") else None,
                cache_directory=str(summary.get("cache_directory")) if summary.get("cache_directory") else None,
                extracted_file_count=summary.get("extracted_file_count"),
            )

        self._state = self._state.with_updates(mission_workspace=workspace)
        return workspace

    def _set_sync_state(
        self,
        *,
        mode: str,
        message: str,
        conflicts: Sequence[ConflictPrompt],
        last_synced_at: datetime | None = None,
    ) -> SyncState:
        """Update sync metadata while preserving queue counts."""

        sync_state = self._state.sync.with_updates(
            mode=mode,
            message=message,
            last_synced_at=last_synced_at or self._state.sync.last_synced_at,
            pending_operations=len(self._queue),
            conflict_count=len(conflicts),
        )
        self._state = self._state.with_updates(sync=sync_state)
        self._update_logging_form_backlog()
        return sync_state

    def _persist_queue(self) -> None:
        self._storage.write(self._queue)

    def _update_state_after_queue(self) -> None:
        self._refresh_sync_metadata()
        self._state = self._state.with_updates(offline_queue=tuple(self._queue))
        self._update_logging_form_backlog()

    def _refresh_sync_metadata(self) -> None:
        sync = self._state.sync
        pending = len(self._queue)
        message = sync.message
        if sync.mode in {"idle", "offline"}:
            message = self._format_backlog_message(pending, sync.mode)
        self._state = self._state.with_updates(
            sync=sync.with_updates(
                pending_operations=pending,
                conflict_count=len(self._state.conflict_prompts),
                message=message,
            )
        )

    def _classify_mesh_health(self, links: Sequence[MeshLink]) -> MeshHealth:
        if not links:
            return "offline"
        average = sum(link.normalized_quality() for link in links) / len(links)
        if average >= 0.8:
            return "excellent"
        if average >= 0.6:
            return "good"
        if average >= 0.4:
            return "fair"
        if average >= 0.2:
            return "poor"
        return "degraded"

    def _summarize_mesh(self, links: Sequence[MeshLink], health: MeshHealth) -> str:
        if not links:
            return "No mesh peers detected"
        best_peer = max(links, key=lambda link: link.normalized_quality())
        template = "Mesh {health} – {count} peers, best {peer} at {signal:.0f} dBm"
        return template.format(
            health=health,
            count=len(links),
            peer=best_peer.node_id,
            signal=best_peer.signal_dbm,
        )

    def _build_attachment_links(self, manifest: MissionManifest) -> tuple[MissionAttachmentLink, ...]:
        links: list[MissionAttachmentLink] = []
        for attachment in manifest.attachments:
            category = self._categorize_attachment(attachment)
            color_token = self._color_for_category(category)
            label = attachment.name or Path(attachment.path).name
            badge = self._badge_for_attachment(attachment)
            links.append(
                MissionAttachmentLink.from_manifest(
                    attachment,
                    label=label,
                    category=category,
                    color_token=color_token,
                    badge=badge,
                )
            )
        return tuple(links)

    @staticmethod
    def _categorize_attachment(attachment: MissionAttachment) -> str:
        name = (attachment.name or Path(attachment.path).name).lower()
        media_type = (attachment.media_type or "").lower()
        if "sop" in name or "standard operating" in name:
            return "sop"
        if "map" in name or "geo" in name or "grid" in name or media_type.startswith("image/"):
            return "map"
        if any(token in name for token in ("comm", "radio", "freq", "call")) or "text/plain" in media_type:
            return "comms"
        return "attachment"

    @staticmethod
    def _color_for_category(category: str) -> str:
        if category == "sop":
            return "primary"
        if category == "map":
            return "secondary"
        if category == "comms":
            return "accent"
        return "neutral_700"

    @staticmethod
    def _badge_for_attachment(attachment: MissionAttachment) -> str | None:
        if attachment.media_type:
            subtype = attachment.media_type.split("/")[-1]
            if subtype:
                return subtype.upper()
        suffix = Path(attachment.path).suffix
        if suffix:
            return suffix.lstrip(".").upper()
        return None

    def _initial_log_form_state(self) -> OperationalLogFormState:
        form = default_operational_log_form()
        return form.with_backlog(len(self._queue))

    def _update_logging_form_backlog(self) -> None:
        form = self._state.operational_log_form.with_backlog(len(self._queue))
        self._state = self._state.with_updates(operational_log_form=form)

    def _format_backlog_message(self, pending: int, mode: str) -> str:
        if pending:
            return f"{pending} field update{'s' if pending != 1 else ''} queued for sync"
        if mode == "offline":
            return "Awaiting mesh uplink"
        return "Ready for mission intake"

    def _compose_task_dashboard(self, *, timestamp: datetime | None = None) -> TaskDashboardState:
        assignments: list[TaskAssignmentCard] = []
        for task_id, card in self._task_baseline.items():
            action = self._pending_task_actions.get(task_id)
            assignments.append(card.with_offline_action(action))
        for task_id, action in self._pending_task_actions.items():
            if task_id not in self._task_baseline:
                assignments.append(TaskAssignmentCard.offline_placeholder(task_id, action, self._clock()))
        dashboard = TaskDashboardState.compose(
            assignments,
            pending_actions=len(self._pending_task_actions),
            timestamp=timestamp or self._clock(),
        )
        self._state = self._state.with_updates(task_dashboard=dashboard)
        return dashboard

    def _compose_resource_board(self, *, timestamp: datetime | None = None) -> ResourceRequestBoardState:
        requests: list[ResourceRequestCard] = []
        for request_id, card in self._resource_baseline.items():
            action = self._pending_resource_actions.get(request_id)
            requests.append(card.with_offline_action(action))
        for request_id, action in self._pending_resource_actions.items():
            if request_id not in self._resource_baseline:
                requests.append(ResourceRequestCard.offline_placeholder(request_id, action, self._clock()))
        board = ResourceRequestBoardState.compose(
            requests,
            pending_actions=len(self._pending_resource_actions),
            timestamp=timestamp or self._clock(),
        )
        self._state = self._state.with_updates(resource_requests=board)
        return board

    def _clear_offline_action_flags(self, applied_operations: Sequence[OfflineOperation]) -> None:
        task_updated = False
        request_updated = False
        for operation in applied_operations:
            if operation.operation_type == "task-action":
                task_id = str(operation.payload.get("task_id"))
                action = str(operation.payload.get("action"))
                if task_id in self._pending_task_actions:
                    self._pending_task_actions.pop(task_id, None)
                    task_updated = True
                if task_id not in self._task_baseline:
                    placeholder = TaskAssignmentCard.offline_placeholder(task_id, action, self._clock())
                    self._task_baseline[task_id] = placeholder.with_offline_action(None)
                self._task_baseline[task_id] = self._task_baseline[task_id].with_merged_action(action)
                task_updated = True
            elif operation.operation_type == "resource-request-action":
                request_id = str(operation.payload.get("request_id"))
                action = str(operation.payload.get("action"))
                if request_id in self._pending_resource_actions:
                    self._pending_resource_actions.pop(request_id, None)
                    request_updated = True
                if request_id not in self._resource_baseline:
                    placeholder = ResourceRequestCard.offline_placeholder(request_id, action, self._clock())
                    self._resource_baseline[request_id] = placeholder.with_offline_action(None)
                self._resource_baseline[request_id] = self._resource_baseline[request_id].with_merged_action(action)
                request_updated = True
        if task_updated:
            self._compose_task_dashboard(timestamp=self._clock())
        if request_updated:
            self._compose_resource_board(timestamp=self._clock())

