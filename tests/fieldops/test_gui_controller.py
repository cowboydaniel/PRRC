from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fieldops import (
    GPSFix,
    MissionAttachment,
    MissionContact,
    MissionManifest,
    OperationalLogDraft,
    PhotoAttachmentDraft,
)
from fieldops.gui import (
    ConflictPrompt,
    FieldOpsGUIController,
    MeshLink,
    ResourceRequestCard,
    SyncResult,
    TaskAssignmentCard,
)


class DummySyncAdapter:
    def __init__(self, *, available: bool = False) -> None:
        self.available = available
        self.results: list[SyncResult] = []
        self.invocations: int = 0

    def is_available(self) -> bool:
        return self.available

    def push_operations(self, operations):
        self.invocations += 1
        if not self.results:
            return SyncResult((), (), ("No sync results configured",))
        return self.results.pop(0)


@pytest.fixture()
def cache_path(tmp_path: Path) -> Path:
    return tmp_path / "offline_queue.json"


def fixed_clock(start: datetime):
    def _inner() -> datetime:
        fixed_clock.current += timedelta(seconds=1)
        return fixed_clock.current

    fixed_clock.current = start - timedelta(seconds=1)
    return _inner


def test_queue_operation_persists_and_reloads(cache_path: Path) -> None:
    adapter = DummySyncAdapter(available=False)
    controller = FieldOpsGUIController(
        cache_path,
        adapter,
        clock=fixed_clock(datetime(2024, 1, 1, tzinfo=timezone.utc)),
    )

    controller.queue_operation("log-status", {"notes": "Alpha"})
    controller.queue_operation("log-status", {"notes": "Bravo"})

    rehydrated = FieldOpsGUIController(
        cache_path,
        adapter,
        clock=fixed_clock(datetime(2024, 1, 1, tzinfo=timezone.utc)),
    )

    assert len(rehydrated.get_state().offline_queue) == 2
    assert rehydrated.get_state().sync.mode == "offline"
    assert cache_path.exists()


def test_attempt_sync_successfully_flushes_queue(cache_path: Path) -> None:
    adapter = DummySyncAdapter(available=True)
    clock = fixed_clock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    controller = FieldOpsGUIController(cache_path, adapter, clock=clock)
    op = controller.queue_operation("mission-brief", {"mission_id": "A1"})

    adapter.results.append(
        SyncResult(applied_operation_ids=(op.operation_id,), conflicts=(), errors=())
    )

    sync_state = controller.attempt_sync()

    assert sync_state.mode == "idle"
    assert sync_state.pending_operations == 0
    assert not cache_path.exists()
    assert controller.get_state().offline_queue == ()


def test_attempt_sync_surfaces_conflicts(cache_path: Path) -> None:
    adapter = DummySyncAdapter(available=True)
    clock = fixed_clock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    controller = FieldOpsGUIController(cache_path, adapter, clock=clock)
    op = controller.queue_operation("mission-brief", {"mission_id": "A1", "summary": "Local"})

    conflict = ConflictPrompt(
        operation_id=op.operation_id,
        headline="HQ updated mission brief",
        details="Remote edits detected",
        local_snapshot={"summary": "Local"},
        remote_snapshot={"summary": "Remote"},
        severity="warning",
        resolution_hint="Choose local or remote summary",
    )
    adapter.results.append(
        SyncResult(applied_operation_ids=(), conflicts=(conflict,), errors=())
    )

    sync_state = controller.attempt_sync()

    assert sync_state.mode == "conflict"
    assert sync_state.conflict_count == 1
    assert controller.get_state().conflict_prompts == (conflict,)
    assert len(controller.get_state().offline_queue) == 1


def test_submit_operational_log_tracks_gps_and_attachments(cache_path: Path) -> None:
    adapter = DummySyncAdapter(available=False)
    clock = fixed_clock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    controller = FieldOpsGUIController(cache_path, adapter, clock=clock)

    gps_fix = GPSFix(
        latitude=34.05,
        longitude=-117.29,
        altitude_m=512.0,
        horizontal_accuracy_m=4.2,
        captured_at=clock(),
    )
    attachment = PhotoAttachmentDraft(
        path="/tmp/evidence.jpg",
        caption="Perimeter breach",
        captured_at=clock(),
        media_type="image/jpeg",
        size_bytes=2_048,
    )
    draft = OperationalLogDraft(
        category="INCIDENT",
        title="Breach at east gate",
        notes="Unauthorized vehicle forced entry. Patrol dispatched.",
        gps_fix=gps_fix,
        attachments=(attachment,),
        tags=("perimeter", "alert"),
        urgency="priority",
        status="open",
    )

    operation = controller.submit_operational_log(draft)

    assert operation.operation_type == "operational-log"
    payload = operation.payload
    assert payload["gps"]["lat"] == pytest.approx(34.05)
    assert payload["gps"]["alt_m"] == pytest.approx(512.0)
    assert payload["attachments"][0]["path"] == "/tmp/evidence.jpg"
    state = controller.get_state()
    assert state.operational_log_form.last_submission_id == operation.operation_id
    assert state.operational_log_form.backlog_count == len(state.offline_queue)
    assert "awaiting" in state.operational_log_form.banner_message.lower()


def test_sync_clears_logging_form_backlog(cache_path: Path) -> None:
    adapter = DummySyncAdapter(available=True)
    clock = fixed_clock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    controller = FieldOpsGUIController(cache_path, adapter, clock=clock)

    draft = OperationalLogDraft(
        category="SITREP",
        title="Patrol complete",
        notes="Sector sweep complete. No anomalies detected.",
    )

    operation = controller.submit_operational_log(draft)
    adapter.results.append(
        SyncResult(applied_operation_ids=(operation.operation_id,), conflicts=(), errors=())
    )

    controller.attempt_sync()

    form_state = controller.get_state().operational_log_form
    assert form_state.backlog_count == 0
    assert "no pending" in form_state.banner_message.lower()


def test_conflict_resolution_updates_queue(cache_path: Path) -> None:
    adapter = DummySyncAdapter(available=True)
    clock = fixed_clock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    controller = FieldOpsGUIController(cache_path, adapter, clock=clock)
    op = controller.queue_operation("mission-brief", {"mission_id": "A1", "summary": "Local"})

    conflict = ConflictPrompt(
        operation_id=op.operation_id,
        headline="HQ updated mission brief",
        details="Remote edits detected",
        local_snapshot={"summary": "Local"},
        remote_snapshot={"summary": "Remote"},
        severity="warning",
        resolution_hint="Choose local or remote summary",
    )
    adapter.results.append(
        SyncResult(applied_operation_ids=(), conflicts=(conflict,), errors=())
    )
    controller.attempt_sync()

    removed_prompt = controller.apply_conflict_resolution(
        op.operation_id, {"mission_id": "A1", "summary": "Merged"}
    )

    assert removed_prompt == conflict
    assert controller.get_state().conflict_prompts == ()
    assert controller.get_state().sync.conflict_count == 0


def test_mesh_topology_updates_status(cache_path: Path) -> None:
    adapter = DummySyncAdapter(available=False)
    clock = fixed_clock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    controller = FieldOpsGUIController(cache_path, adapter, clock=clock)

    topology = controller.update_mesh_topology(
        [
            MeshLink(
                node_id="alpha",
                link_quality=0.9,
                signal_dbm=-45,
                latency_ms=12.0,
                status="up",
                last_seen=datetime(2024, 1, 1, tzinfo=timezone.utc),
                hop_count=1,
            ),
            MeshLink(
                node_id="bravo",
                link_quality=0.7,
                signal_dbm=-60,
                latency_ms=20.0,
                status="up",
                last_seen=datetime(2024, 1, 1, tzinfo=timezone.utc),
                hop_count=2,
            ),
        ]
    )

    assert topology.mesh_health == "excellent"
    assert "2 peers" in topology.mesh_summary
    assert controller.get_state().mesh.mesh_summary == topology.mesh_summary


def test_ingest_mission_package_updates_workspace(cache_path: Path) -> None:
    adapter = DummySyncAdapter(available=True)
    clock = fixed_clock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    manifest = MissionManifest(
        mission_id="BRAVO-7",
        name="Bravo Recon",
        version="1.2",
        summary="Reconnaissance sweep across sector Bravo.",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        classification="SECRET",
        tags=("recon", "night"),
        contacts=(
            MissionContact(role="S3", name="Capt. Adams", callsign="Steel 3", channel="Encrypted"),
        ),
        attachments=(
            MissionAttachment(name="Bravo SOP", path="docs/bravo_sop.pdf", media_type="application/pdf"),
            MissionAttachment(name="Sector Map", path="maps/sector_bravo.png", media_type="image/png"),
            MissionAttachment(name="Comms Plan", path="comms/plan.txt", media_type="text/plain"),
            MissionAttachment(name="Logistics Notes", path="intel/log_notes.docx", media_type="application/vnd.openxmlformats"),
        ),
        source_path=cache_path,
    )

    package_summary = {
        "package_path": "packages/bravo.pkg",
        "staging_directory": "staging/bravo",
        "cache_directory": "cache/bravo",
        "extracted_file_count": 12,
        "manifest": manifest,
    }

    def mission_loader(path: Path) -> dict[str, object]:
        assert path == Path("/missions/bravo.pkg")
        return package_summary

    controller = FieldOpsGUIController(
        cache_path,
        adapter,
        clock=clock,
        mission_loader=mission_loader,
    )

    workspace = controller.ingest_mission_package(Path("/missions/bravo.pkg"))

    assert workspace.status == "ready"
    assert workspace.mission is not None
    assert workspace.mission.mission_id == "BRAVO-7"
    assert workspace.mission.quick_links.sop and workspace.mission.quick_links.sop[0].color_token == "primary"
    assert workspace.mission.quick_links.maps and workspace.mission.quick_links.maps[0].color_token == "secondary"
    assert workspace.mission.quick_links.comms and workspace.mission.quick_links.comms[0].color_token == "accent"
    assert any(link.category == "attachment" for link in workspace.mission.attachments)
    assert controller.get_state().mission_workspace == workspace


def test_ingest_mission_package_without_manifest(cache_path: Path) -> None:
    adapter = DummySyncAdapter(available=True)
    clock = fixed_clock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    package_summary = {
        "package_path": "packages/empty.pkg",
        "staging_directory": "staging/empty",
        "cache_directory": "cache/empty",
        "extracted_file_count": 0,
        "manifest": None,
    }

    controller = FieldOpsGUIController(
        cache_path,
        adapter,
        clock=clock,
        mission_loader=lambda path: package_summary,
    )

    workspace = controller.ingest_mission_package(Path("/missions/empty.pkg"))

    assert workspace.status == "staged"
    assert workspace.mission is None
    assert "manifest" in workspace.headline.lower()


def test_task_dashboard_offline_actions_merge(cache_path: Path) -> None:
    adapter = DummySyncAdapter(available=True)
    clock = fixed_clock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    controller = FieldOpsGUIController(cache_path, adapter, clock=clock)

    assignments = (
        TaskAssignmentCard(
            task_id="TASK-1",
            title="Establish perimeter",
            status="pending",
            display_status="pending",
            priority="critical",
            summary="Secure the outer perimeter.",
            due_at=clock(),
        ),
        TaskAssignmentCard(
            task_id="TASK-2",
            title="Stage medevac",
            status="pending",
            display_status="pending",
            priority="priority",
            summary="Prep medevac team for launch.",
        ),
    )

    dashboard = controller.update_task_assignments(assignments)

    assert dashboard.columns[0].tasks[0].priority_color_token == "danger"
    operation = controller.apply_task_action("TASK-1", "accept", notes="Bravo team")

    state = controller.get_state().task_dashboard
    assert state.pending_local_actions == 1
    assert state.offline_badge_token == "accent"
    accepted_column = next(column for column in state.columns if column.column_id == "accepted")
    assert accepted_column.tasks[0].offline_action == "accept"

    adapter.results.append(
        SyncResult(applied_operation_ids=(operation.operation_id,), conflicts=(), errors=())
    )
    controller.attempt_sync()

    state = controller.get_state().task_dashboard
    assert state.pending_local_actions == 0
    assert state.offline_badge_token == "success"
    accepted_column = next(column for column in state.columns if column.column_id == "accepted")
    assert accepted_column.tasks[0].display_status == "accepted"
    assert accepted_column.tasks[0].offline_action is None


def test_resource_request_actions_merge(cache_path: Path) -> None:
    adapter = DummySyncAdapter(available=True)
    clock = fixed_clock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    controller = FieldOpsGUIController(cache_path, adapter, clock=clock)

    requests = (
        ResourceRequestCard(
            request_id="REQ-7",
            requester="Alpha Company",
            summary="Resupply fuel drums",
            priority="high",
            status="pending",
            display_status="pending",
            quantity=6,
        ),
    )

    board = controller.update_resource_requests(requests)

    assert board.requests[0].priority_color_token == "accent"
    operation = controller.apply_resource_request_action("REQ-7", "escalate")

    state = controller.get_state().resource_requests
    assert state.pending_local_actions == 1
    assert state.offline_badge_token == "accent"
    assert state.requests[0].offline_action == "escalate"

    adapter.results.append(
        SyncResult(applied_operation_ids=(operation.operation_id,), conflicts=(), errors=())
    )
    controller.attempt_sync()

    state = controller.get_state().resource_requests
    assert state.pending_local_actions == 0
    assert state.offline_badge_token == "success"
    assert state.requests[0].display_status == "escalated"
    assert state.requests[0].offline_action is None

