from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hq_command.audit import (
    AnnotationService,
    AuditSearch,
    AuditTrail,
    ChainOfCustodyTracker,
    ChangeManagementWorkflow,
    ComplianceDashboard,
    ComplianceReporter,
    EventStore,
    ExternalAuditSupport,
    OperatorActivityLogger,
    PostMortemToolkit,
    PrivacyComplianceManager,
    RetentionPolicyEnforcer,
    SignatureService,
    TamperDetectionError,
    TimelineBuilder,
)


@pytest.fixture()
def event_store() -> EventStore:
    return EventStore()


def test_event_store_append_and_verify(event_store: EventStore) -> None:
    event_store.append(
        aggregate_id="task:1",
        event_type="task.assigned",
        actor="controller",
        payload={"assignee": "alpha"},
    )
    event_store.append(
        aggregate_id="task:1",
        event_type="task.status_changed",
        actor="alpha",
        payload={"status": "in_progress"},
    )

    assert len(event_store.events()) == 2
    assert event_store.events()[1].version == 2
    event_store.verify()

    tampered = list(event_store.export())
    tampered[-1]["payload"]["status"] = "done"
    with pytest.raises(TamperDetectionError):
        event_store.load_export(tampered)


def test_timeline_reconstruction_and_playback(event_store: EventStore) -> None:
    builder = TimelineBuilder(event_store)
    incident_id = "inc-7"
    now = datetime.now(timezone.utc)
    builder.record_incident_event(
        incident_id=incident_id,
        actor="analyst",
        action="incident.opened",
        payload={},
        timestamp=now,
    )
    builder.record_incident_event(
        incident_id=incident_id,
        actor="lead",
        action="incident.escalated",
        payload={"level": 2},
        timestamp=now + timedelta(minutes=5),
    )

    def reducer(state: dict[str, int], event):
        if event.event_type == "incident.escalated":
            state["level"] = event.payload["level"]
        return state

    state = builder.restore_state(
        incident_id=incident_id,
        reducer=reducer,
        initial_state={"level": 0},
        as_of=now + timedelta(minutes=6),
    )
    assert state["level"] == 2

    schedule = builder.playback_plan(incident_id=incident_id, speed=2.0)
    assert pytest.approx(schedule[1][1], rel=1e-3) == 150.0


def test_audit_search_and_export(event_store: EventStore) -> None:
    trail = AuditTrail(event_store)
    trail.log_task_assignment(task_id="99", assignee="b", assigned_by="controller")
    trail.log_status_change(task_id="99", status="closed", actor="b")

    search = AuditSearch(event_store)
    results = search.search(actor="b")
    assert len(results) == 1
    assert "closed" in search.export(results)


def test_compliance_reporter_checks_and_schedule(event_store: EventStore) -> None:
    reporter = ComplianceReporter(event_store)
    reporter.schedule(template="standard", cron="0 0 * * 1")
    report = reporter.generate(template="standard")
    assert report.status == "pass"
    assert reporter.schedules == (("standard", "0 0 * * 1"),)
    checks = reporter.automated_checks()
    assert not checks["immutable_event_store"]


def test_chain_of_custody_flags_missing_transfers(event_store: EventStore) -> None:
    tracker = ChainOfCustodyTracker(event_store)
    tracker.record_access(subject="dataset", actor="analyst", reason="triage")
    tracker.transfer(subject="dataset", from_actor="analyst", to_actor="qa", justification="review")
    tracker.alert_if_missing(subject="dataset", actor="forensics")
    assert "forensics" in " ".join(tracker.alerts)


def test_change_management_requires_multiple_approvals(event_store: EventStore) -> None:
    workflow = ChangeManagementWorkflow(event_store, required_approvals=2)
    workflow.submit(request_id="chg-1", submitted_by="ops", change_summary="Upgrade service")
    workflow.assess_impact(request_id="chg-1", assessment="Low risk", actor="risk")
    workflow.approve(request_id="chg-1", approver="sec")
    workflow.approve(request_id="chg-1", approver="ops-lead")
    assert workflow.status("chg-1").status == "approved"


def test_signature_service_sign_and_verify(event_store: EventStore) -> None:
    service = SignatureService(event_store, secret_key=b"secret")
    payload = {"action": "release"}
    record = service.sign(subject="rel-1", actor="director", payload=payload)
    assert service.verify(subject="rel-1", payload=payload)
    assert record.signature


def test_retention_policy_respects_legal_hold(event_store: EventStore) -> None:
    logger = OperatorActivityLogger(event_store)
    logger.log_login(operator_id="alice")
    logger.log_logout(operator_id="alice")

    enforcer = RetentionPolicyEnforcer(event_store)
    enforcer.place_legal_hold(aggregate_id="operator:alice", until=datetime.now(timezone.utc) + timedelta(days=1))
    enforcer.enforce(retention_days=0)
    assert len(event_store.events()) == 2


def test_privacy_manager_masking_and_checks(event_store: EventStore) -> None:
    manager = PrivacyComplianceManager(event_store)
    masked = manager.mask_pii({"name": "Alice", "id": "123"}, fields=["name"])
    assert masked["name"] == "***redacted***"
    manager.handle_dsar(request_id="req-1", subject="Alice", fulfilled_by="privacy")
    checks = manager.run_compliance_checks()
    assert checks["pii_masking_enabled"]
    assert checks["dsar_fulfilled"]


def test_post_mortem_generates_report(event_store: EventStore) -> None:
    toolkit = PostMortemToolkit(event_store)
    toolkit.create_template(name="standard", sections=["Summary", "Timeline"])
    toolkit.open_review(incident_id="inc-1", template="standard")
    toolkit.record_root_cause(incident_id="inc-1", root_cause="Misconfig", actor="lead")
    toolkit.add_action_item(incident_id="inc-1", description="Fix", owner="eng")
    report = toolkit.generate_report(incident_id="inc-1")
    assert report["root_cause"] == "Misconfig"
    assert report["action_items"][0]["owner"] == "eng"


def test_external_audit_support_exports_and_verifies(event_store: EventStore) -> None:
    search = AuditTrail(event_store)
    search.log_task_assignment(task_id="1", assignee="alpha", assigned_by="ops")
    support = ExternalAuditSupport(event_store)
    package = support.export_package(package_id="pkg-1", aggregates=["task:1"])
    assert package["events"]
    support.grant_auditor_access(auditor_id="aud-1", expires_at=datetime.now(timezone.utc))
    assert support.verify_audit_trail()


def test_annotations_and_dashboard_metrics(event_store: EventStore) -> None:
    annotations = AnnotationService(event_store)
    annotations.add_note(
        incident_id="inc-77",
        author="analyst",
        comment="Initial triage",
        metadata={"severity": "high"},
    )
    notes = annotations.list_notes("inc-77")
    assert notes[0].metadata["severity"] == "high"

    dashboard = ComplianceDashboard(event_store)
    dashboard.record_finding(control="audit-log", status="resolved")
    dashboard.remediation_task(task_id="rem-1", description="Rotate keys")
    metrics = dashboard.metrics()
    assert metrics["compliance_score"] == 100.0
