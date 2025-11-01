"""Offline-first FieldOps GUI controller logic."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping, Protocol, Sequence

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
    OfflineOperation,
    SyncResult,
    SyncState,
    empty_mission_workspace,
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
        )

    def get_state(self) -> FieldOpsGUIState:
        """Return the current GUI state."""

        return self._state

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
        result = self._adapter.push_operations(tuple(self._queue))
        applied_ids = set(result.applied_operation_ids)
        if applied_ids:
            self._queue = [operation for operation in self._queue if operation.operation_id not in applied_ids]
            if self._queue:
                self._persist_queue()
            else:
                self._storage.clear()
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
        return sync_state

    def _persist_queue(self) -> None:
        self._storage.write(self._queue)

    def _update_state_after_queue(self) -> None:
        self._refresh_sync_metadata()
        self._state = self._state.with_updates(offline_queue=tuple(self._queue))

    def _refresh_sync_metadata(self) -> None:
        self._state = self._state.with_updates(
            sync=self._state.sync.with_updates(
                pending_operations=len(self._queue),
                conflict_count=len(self._state.conflict_prompts),
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

