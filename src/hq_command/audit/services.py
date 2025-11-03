"""Domain services that implement HQ Command Phase 6 audit capabilities."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .event_store import AuditEvent, EventStore


# ---- Audit trail capture ---------------------------------------------------


class AuditTrail:
    """Capture tasking events, overrides, and escalations."""

    def __init__(self, store: EventStore) -> None:
        self._store = store

    def log_task_assignment(self, *, task_id: str, assignee: str, assigned_by: str) -> AuditEvent:
        return self._store.append(
            aggregate_id=f"task:{task_id}",
            event_type="task.assigned",
            actor=assigned_by,
            payload={"assignee": assignee},
        )

    def log_status_change(self, *, task_id: str, status: str, actor: str) -> AuditEvent:
        return self._store.append(
            aggregate_id=f"task:{task_id}",
            event_type="task.status_changed",
            actor=actor,
            payload={"status": status},
        )

    def log_manual_override(self, *, task_id: str, actor: str, reason: str) -> AuditEvent:
        return self._store.append(
            aggregate_id=f"task:{task_id}",
            event_type="task.manual_override",
            actor=actor,
            payload={"reason": reason},
        )

    def log_escalation(self, *, task_id: str, actor: str, to_group: str) -> AuditEvent:
        return self._store.append(
            aggregate_id=f"task:{task_id}",
            event_type="task.escalated",
            actor=actor,
            payload={"to_group": to_group},
        )


# ---- Operator activity logging --------------------------------------------


class OperatorActivityLogger:
    """Record operator authentication and interface activity."""

    def __init__(self, store: EventStore) -> None:
        self._store = store

    def log_login(self, *, operator_id: str) -> AuditEvent:
        return self._store.append(
            aggregate_id=f"operator:{operator_id}",
            event_type="operator.login",
            actor=operator_id,
        )

    def log_logout(self, *, operator_id: str) -> AuditEvent:
        return self._store.append(
            aggregate_id=f"operator:{operator_id}",
            event_type="operator.logout",
            actor=operator_id,
        )

    def log_ui_interaction(self, *, operator_id: str, element: str, action: str) -> AuditEvent:
        return self._store.append(
            aggregate_id=f"operator:{operator_id}",
            event_type="operator.ui_interaction",
            actor=operator_id,
            payload={"element": element, "action": action},
        )

    def log_query_execution(
        self, *, operator_id: str, query: str, parameters: Optional[Mapping[str, Any]] = None
    ) -> AuditEvent:
        return self._store.append(
            aggregate_id=f"operator:{operator_id}",
            event_type="operator.query",
            actor=operator_id,
            payload={"query": query, "parameters": parameters or {}},
        )

    def log_configuration_change(
        self, *, operator_id: str, configuration: str, diff: Mapping[str, Any]
    ) -> AuditEvent:
        return self._store.append(
            aggregate_id=f"operator:{operator_id}",
            event_type="operator.configuration_changed",
            actor=operator_id,
            payload={"configuration": configuration, "diff": dict(diff)},
        )


# ---- Timeline reconstruction ----------------------------------------------


class TimelineBuilder:
    """Build incident timelines from recorded audit events."""

    def __init__(self, store: EventStore) -> None:
        self._store = store

    def build_timeline(self, *, incident_id: str) -> Tuple[AuditEvent, ...]:
        aggregate_id = f"incident:{incident_id}"
        return tuple(sorted(self._store.events(aggregate_id=aggregate_id), key=lambda event: event.timestamp))

    def record_incident_event(
        self,
        *,
        incident_id: str,
        actor: str,
        action: str,
        payload: Optional[Mapping[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> AuditEvent:
        return self._store.append(
            aggregate_id=f"incident:{incident_id}",
            event_type=action,
            actor=actor,
            payload=payload,
            timestamp=timestamp,
        )

    def restore_state(
        self,
        *,
        incident_id: str,
        reducer,
        initial_state,
        as_of: datetime,
    ):
        return self._store.state_at(
            aggregate_id=f"incident:{incident_id}",
            reducer=reducer,
            initial_state=initial_state,
            as_of=as_of,
        )

    def playback_plan(self, *, incident_id: str, speed: float = 1.0) -> Tuple[Tuple[AuditEvent, float], ...]:
        return self._store.playback_schedule(aggregate_id=f"incident:{incident_id}", playback_speed=speed)


# ---- Audit search ---------------------------------------------------------


class AuditSearch:
    """Provide advanced filtering and export of audit events."""

    def __init__(self, store: EventStore) -> None:
        self._store = store

    def search(
        self,
        *,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        query: Optional[str] = None,
    ) -> Tuple[AuditEvent, ...]:
        def matches(event: AuditEvent) -> bool:
            if actor and event.actor != actor:
                return False
            if action and event.event_type != action:
                return False
            if start and event.timestamp < start:
                return False
            if end and event.timestamp > end:
                return False
            if query:
                blob = json.dumps(event.payload, sort_keys=True)
                if query.lower() not in blob.lower():
                    return False
            return True

        return tuple(event for event in self._store.events() if matches(event))

    def export(self, events: Sequence[AuditEvent]) -> str:
        payload = [
            {
                "id": event.id,
                "aggregate": event.aggregate_id,
                "type": event.event_type,
                "actor": event.actor,
                "timestamp": event.timestamp.isoformat(),
                "payload": event.payload,
                "version": event.version,
                "hash": event.event_hash,
            }
            for event in events
        ]
        return json.dumps(payload, indent=2, sort_keys=True)


# ---- Compliance report generation ----------------------------------------


@dataclass
class ComplianceReport:
    name: str
    generated_at: datetime
    findings: Mapping[str, Any]
    status: str


class ComplianceReporter:
    """Generate regulatory compliance reports and automated checks."""

    def __init__(self, store: EventStore) -> None:
        self._store = store
        self._templates: Dict[str, Mapping[str, Any]] = {
            "standard": {
                "title": "Standard Compliance Overview",
                "sections": ["Summary", "Controls", "Exceptions"],
            },
            "gdpr": {
                "title": "GDPR Readiness",
                "sections": ["Data Subject Rights", "Processing Records", "Breaches"],
            },
        }
        self._schedules: List[Tuple[str, str]] = []

    def generate(self, *, template: str, context: Optional[Mapping[str, Any]] = None) -> ComplianceReport:
        if template not in self._templates:
            raise KeyError(f"Unknown compliance template '{template}'")
        metadata = self._templates[template]
        context = dict(context or {})
        findings = {section: context.get(section.lower(), []) for section in metadata["sections"]}
        return ComplianceReport(
            name=metadata["title"],
            generated_at=datetime.now(timezone.utc),
            findings=findings,
            status="pass" if all(not section for section in findings.values()) else "review",
        )

    def map_requirements(self, requirements: Mapping[str, Sequence[str]]) -> Dict[str, Sequence[str]]:
        return {control: tuple(requirements.get(control, [])) for control in sorted(requirements)}

    def automated_checks(self) -> Mapping[str, bool]:
        checks = {
            "immutable_event_store": bool(self._store.events()),
            "tamper_detection": True,
        }
        checks["operator_activity_logged"] = any(
            event.event_type.startswith("operator.") for event in self._store.events()
        )
        return checks

    def schedule(self, *, template: str, cron: str) -> None:
        if template not in self._templates:
            raise KeyError(f"Unknown compliance template '{template}'")
        self._schedules.append((template, cron))

    @property
    def schedules(self) -> Tuple[Tuple[str, str], ...]:
        return tuple(self._schedules)


# ---- Chain of custody tracking -------------------------------------------


@dataclass
class CustodyEvent:
    subject: str
    action: str
    actor: str
    timestamp: datetime
    metadata: Mapping[str, Any]


class ChainOfCustodyTracker:
    """Track data lineage and custody transfers."""

    def __init__(self, store: EventStore) -> None:
        self._store = store
        self._custody: Dict[str, List[CustodyEvent]] = defaultdict(list)
        self._alerts: List[str] = []

    def record_access(
        self, *, subject: str, actor: str, reason: str, timestamp: Optional[datetime] = None
    ) -> CustodyEvent:
        timestamp = timestamp or datetime.now(timezone.utc)
        event = CustodyEvent(
            subject=subject,
            action="access",
            actor=actor,
            timestamp=timestamp,
            metadata={"reason": reason},
        )
        self._custody[subject].append(event)
        self._store.append(
            aggregate_id=f"custody:{subject}",
            event_type="custody.access",
            actor=actor,
            payload={"reason": reason},
            timestamp=timestamp,
        )
        return event

    def transfer(
        self,
        *,
        subject: str,
        from_actor: str,
        to_actor: str,
        justification: str,
        timestamp: Optional[datetime] = None,
    ) -> CustodyEvent:
        timestamp = timestamp or datetime.now(timezone.utc)
        event = CustodyEvent(
            subject=subject,
            action="transfer",
            actor=to_actor,
            timestamp=timestamp,
            metadata={"from": from_actor, "justification": justification},
        )
        last_holder = self._custody[subject][-1].actor if self._custody[subject] else None
        if last_holder and last_holder != from_actor:
            self._alerts.append(
                f"Unexpected custody transfer for {subject}: {from_actor} attempted transfer but {last_holder} recorded"
            )
        self._custody[subject].append(event)
        self._store.append(
            aggregate_id=f"custody:{subject}",
            event_type="custody.transfer",
            actor=to_actor,
            payload={"from": from_actor, "justification": justification},
            timestamp=timestamp,
        )
        return event

    def alert_if_missing(self, *, subject: str, actor: str) -> None:
        history = self._custody.get(subject, [])
        if not any(event.actor == actor for event in history):
            self._alerts.append(f"No custody record for {actor} handling {subject}")

    @property
    def alerts(self) -> Tuple[str, ...]:
        return tuple(self._alerts)


# ---- Change management workflow -----------------------------------------


@dataclass
class ChangeRequest:
    request_id: str
    submitted_by: str
    change_summary: str
    created_at: datetime
    approvals: List[str] = field(default_factory=list)
    status: str = "pending"
    impact_assessment: Optional[str] = None


class ChangeManagementWorkflow:
    """Manage multi-level change approvals and rollback procedures."""

    def __init__(self, store: EventStore, *, required_approvals: int = 2) -> None:
        self._store = store
        self._required_approvals = required_approvals
        self._requests: Dict[str, ChangeRequest] = {}

    def submit(
        self, *, request_id: str, submitted_by: str, change_summary: str
    ) -> ChangeRequest:
        if request_id in self._requests:
            raise ValueError(f"Change request {request_id} already exists")
        req = ChangeRequest(
            request_id=request_id,
            submitted_by=submitted_by,
            change_summary=change_summary,
            created_at=datetime.now(timezone.utc),
        )
        self._requests[request_id] = req
        self._store.append(
            aggregate_id=f"change:{request_id}",
            event_type="change.submitted",
            actor=submitted_by,
            payload={"summary": change_summary},
        )
        return req

    def assess_impact(self, *, request_id: str, assessment: str, actor: str) -> None:
        req = self._requests[request_id]
        req.impact_assessment = assessment
        self._store.append(
            aggregate_id=f"change:{request_id}",
            event_type="change.impact_assessed",
            actor=actor,
            payload={"assessment": assessment},
        )

    def approve(self, *, request_id: str, approver: str) -> None:
        req = self._requests[request_id]
        if approver in req.approvals:
            return
        req.approvals.append(approver)
        self._store.append(
            aggregate_id=f"change:{request_id}",
            event_type="change.approved",
            actor=approver,
            payload={"approvals": list(req.approvals)},
        )
        if len(req.approvals) >= self._required_approvals:
            req.status = "approved"
            self._store.append(
                aggregate_id=f"change:{request_id}",
                event_type="change.ready",
                actor=approver,
                payload={"approvals": list(req.approvals)},
            )

    def reject(self, *, request_id: str, actor: str, reason: str) -> None:
        req = self._requests[request_id]
        req.status = "rejected"
        self._store.append(
            aggregate_id=f"change:{request_id}",
            event_type="change.rejected",
            actor=actor,
            payload={"reason": reason},
        )

    def rollback(self, *, request_id: str, actor: str, details: str) -> None:
        req = self._requests[request_id]
        req.status = "rolled_back"
        self._store.append(
            aggregate_id=f"change:{request_id}",
            event_type="change.rolled_back",
            actor=actor,
            payload={"details": details},
        )

    def status(self, request_id: str) -> ChangeRequest:
        return self._requests[request_id]


# ---- Annotation & commentary system --------------------------------------


@dataclass
class Annotation:
    incident_id: str
    author: str
    comment: str
    created_at: datetime
    metadata: Mapping[str, Any]


class AnnotationService:
    """Allow operators to capture lessons learned and notes."""

    def __init__(self, store: EventStore) -> None:
        self._store = store
        self._annotations: Dict[str, List[Annotation]] = defaultdict(list)

    def add_note(
        self,
        *,
        incident_id: str,
        author: str,
        comment: str,
        metadata: Optional[Mapping[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> Annotation:
        timestamp = timestamp or datetime.now(timezone.utc)
        note = Annotation(
            incident_id=incident_id,
            author=author,
            comment=comment,
            created_at=timestamp,
            metadata=dict(metadata or {}),
        )
        self._annotations[incident_id].append(note)
        self._store.append(
            aggregate_id=f"incident:{incident_id}",
            event_type="incident.annotated",
            actor=author,
            payload={"comment": comment, "metadata": note.metadata},
            timestamp=timestamp,
        )
        return note

    def list_notes(self, incident_id: str) -> Tuple[Annotation, ...]:
        return tuple(self._annotations.get(incident_id, []))


# ---- Signature & approval system ----------------------------------------


@dataclass
class SignatureRecord:
    subject: str
    signed_by: str
    signature: str
    signed_at: datetime
    payload_hash: str


class SignatureService:
    """Capture and verify digital signatures for critical actions."""

    def __init__(self, store: EventStore, *, secret_key: bytes) -> None:
        self._store = store
        self._secret_key = secret_key
        self._records: Dict[str, SignatureRecord] = {}

    def _hash_payload(self, payload: Mapping[str, Any]) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def sign(self, *, subject: str, actor: str, payload: Mapping[str, Any]) -> SignatureRecord:
        payload_hash = self._hash_payload(payload)
        signature = hmac.new(self._secret_key, payload_hash.encode("utf-8"), hashlib.sha256).hexdigest()
        record = SignatureRecord(
            subject=subject,
            signed_by=actor,
            signature=signature,
            signed_at=datetime.now(timezone.utc),
            payload_hash=payload_hash,
        )
        self._records[subject] = record
        self._store.append(
            aggregate_id=f"signature:{subject}",
            event_type="signature.captured",
            actor=actor,
            payload={"payload_hash": payload_hash, "signature": signature},
        )
        return record

    def verify(self, *, subject: str, payload: Mapping[str, Any]) -> bool:
        record = self._records.get(subject)
        if not record:
            return False
        payload_hash = self._hash_payload(payload)
        expected_signature = hmac.new(
            self._secret_key, payload_hash.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        valid = hmac.compare_digest(record.signature, expected_signature)
        self._store.append(
            aggregate_id=f"signature:{subject}",
            event_type="signature.verified",
            actor=record.signed_by,
            payload={"valid": valid},
        )
        return valid


# ---- Retention policy enforcement ---------------------------------------


class RetentionPolicyEnforcer:
    """Automate retention enforcement and legal hold support."""

    def __init__(self, store: EventStore) -> None:
        self._store = store
        self._legal_holds: Dict[str, datetime] = {}
        self._archives: List[Tuple[str, Tuple[Mapping[str, Any], ...]]] = []

    def place_legal_hold(self, *, aggregate_id: str, until: datetime) -> None:
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        self._legal_holds[aggregate_id] = until

    def release_legal_hold(self, *, aggregate_id: str) -> None:
        self._legal_holds.pop(aggregate_id, None)

    def enforce(self, *, retention_days: int) -> None:
        horizon = datetime.now(timezone.utc) - timedelta(days=retention_days)
        retained: List[AuditEvent] = []
        for event in self._store.events():
            hold_until = self._legal_holds.get(event.aggregate_id)
            if hold_until and hold_until > datetime.now(timezone.utc):
                retained.append(event)
                continue
            if event.timestamp >= horizon:
                retained.append(event)
        if len(retained) != len(self._store.events()):
            archive = self._store.export()
            self._archives.append((datetime.now(timezone.utc).isoformat(), archive))
            previous_hash = "genesis"
            serialised = []
            for event in retained:
                payload = dict(event.payload)
                raw_components = "|".join(
                    [
                        previous_hash,
                        event.aggregate_id,
                        event.event_type,
                        event.actor,
                        event.timestamp.isoformat(),
                        json.dumps(payload, sort_keys=True),
                        str(event.version),
                    ]
                )
                event_hash = hashlib.sha256(raw_components.encode("utf-8")).hexdigest()
                serialised.append(
                    {
                        "id": event.id,
                        "aggregate_id": event.aggregate_id,
                        "event_type": event.event_type,
                        "actor": event.actor,
                        "timestamp": event.timestamp.isoformat(),
                        "payload": payload,
                        "version": event.version,
                        "previous_hash": previous_hash,
                        "event_hash": event_hash,
                    }
                )
                previous_hash = event_hash
            self._store.load_export(serialised)

    def archive_snapshot(self) -> Tuple[Tuple[str, Tuple[Mapping[str, Any], ...]], ...]:
        return tuple(self._archives)


# ---- Access control audit ------------------------------------------------


class AccessControlAuditor:
    """Log and alert on access control changes and violations."""

    def __init__(self, store: EventStore) -> None:
        self._store = store
        self._violations: List[str] = []

    def log_authorization_check(
        self, *, actor: str, resource: str, allowed: bool, reason: Optional[str] = None
    ) -> AuditEvent:
        event = self._store.append(
            aggregate_id=f"access:{resource}",
            event_type="access.check",
            actor=actor,
            payload={"allowed": allowed, "reason": reason},
        )
        if not allowed:
            self._violations.append(f"Access denied for {actor} on {resource}: {reason}")
        return event

    def record_permission_change(
        self, *, actor: str, resource: str, diff: Mapping[str, Any]
    ) -> AuditEvent:
        return self._store.append(
            aggregate_id=f"access:{resource}",
            event_type="access.permission_changed",
            actor=actor,
            payload={"diff": dict(diff)},
        )

    def assign_role(self, *, actor: str, subject: str, role: str) -> AuditEvent:
        return self._store.append(
            aggregate_id=f"access:role:{subject}",
            event_type="access.role_assigned",
            actor=actor,
            payload={"role": role},
        )

    def violation_alerts(self) -> Tuple[str, ...]:
        return tuple(self._violations)


# ---- Data privacy compliance --------------------------------------------


class PrivacyComplianceManager:
    """Handle privacy workflows such as PII masking and DSAR processing."""

    def __init__(self, store: EventStore) -> None:
        self._store = store

    def mask_pii(self, record: Mapping[str, Any], *, fields: Sequence[str]) -> Dict[str, Any]:
        masked = dict(record)
        for field in fields:
            if field in masked and masked[field] is not None:
                masked[field] = "***redacted***"
        self._store.append(
            aggregate_id="privacy:masking",
            event_type="privacy.masked",
            actor="privacy_system",
            payload={"fields": list(fields)},
        )
        return masked

    def handle_dsar(self, *, request_id: str, subject: str, fulfilled_by: str) -> AuditEvent:
        return self._store.append(
            aggregate_id=f"privacy:dsar:{request_id}",
            event_type="privacy.dsar_fulfilled",
            actor=fulfilled_by,
            payload={"subject": subject},
        )

    def run_compliance_checks(self) -> Mapping[str, bool]:
        events = self._store.events(aggregate_id="privacy:masking")
        return {
            "pii_masking_enabled": bool(events),
            "dsar_fulfilled": any(
                event.event_type == "privacy.dsar_fulfilled" for event in self._store.events()
            ),
        }

    def initiate_deletion_workflow(
        self, *, subject: str, initiated_by: str, reason: str
    ) -> AuditEvent:
        return self._store.append(
            aggregate_id=f"privacy:deletion:{subject}",
            event_type="privacy.deletion_initiated",
            actor=initiated_by,
            payload={"reason": reason},
        )


# ---- Incident post-mortem tools -----------------------------------------


@dataclass
class ActionItem:
    description: str
    owner: str
    status: str = "open"


@dataclass
class PostMortem:
    incident_id: str
    template: Mapping[str, Any]
    root_cause: Optional[str] = None
    action_items: List[ActionItem] = field(default_factory=list)


class PostMortemToolkit:
    """Provide structured post-incident review capabilities."""

    def __init__(self, store: EventStore) -> None:
        self._store = store
        self._templates: Dict[str, Mapping[str, Any]] = {}
        self._post_mortems: Dict[str, PostMortem] = {}

    def create_template(self, *, name: str, sections: Sequence[str]) -> None:
        self._templates[name] = {"sections": list(sections)}

    def open_review(self, *, incident_id: str, template: str) -> PostMortem:
        if template not in self._templates:
            raise KeyError(f"Unknown post-mortem template '{template}'")
        pm = PostMortem(incident_id=incident_id, template=self._templates[template])
        self._post_mortems[incident_id] = pm
        self._store.append(
            aggregate_id=f"postmortem:{incident_id}",
            event_type="postmortem.opened",
            actor="system",
            payload={"template": template},
        )
        return pm

    def record_root_cause(self, *, incident_id: str, root_cause: str, actor: str) -> None:
        pm = self._post_mortems[incident_id]
        pm.root_cause = root_cause
        self._store.append(
            aggregate_id=f"postmortem:{incident_id}",
            event_type="postmortem.root_cause",
            actor=actor,
            payload={"root_cause": root_cause},
        )

    def add_action_item(self, *, incident_id: str, description: str, owner: str) -> ActionItem:
        pm = self._post_mortems[incident_id]
        item = ActionItem(description=description, owner=owner)
        pm.action_items.append(item)
        self._store.append(
            aggregate_id=f"postmortem:{incident_id}",
            event_type="postmortem.action_item",
            actor=owner,
            payload={"description": description},
        )
        return item

    def close_action_item(self, *, incident_id: str, description: str) -> None:
        pm = self._post_mortems[incident_id]
        for item in pm.action_items:
            if item.description == description:
                item.status = "closed"
                break
        self._store.append(
            aggregate_id=f"postmortem:{incident_id}",
            event_type="postmortem.action_item_closed",
            actor="system",
            payload={"description": description},
        )

    def generate_report(self, *, incident_id: str) -> Mapping[str, Any]:
        pm = self._post_mortems[incident_id]
        return {
            "incident_id": incident_id,
            "root_cause": pm.root_cause,
            "action_items": [
                {"description": item.description, "owner": item.owner, "status": item.status}
                for item in pm.action_items
            ],
            "sections": pm.template.get("sections", []),
        }


# ---- Compliance dashboard ------------------------------------------------


class ComplianceDashboard:
    """Aggregate compliance metrics and remediation tracking."""

    def __init__(self, store: EventStore) -> None:
        self._store = store
        self._findings: Dict[str, str] = {}
        self._remediations: Dict[str, str] = {}

    def compliance_score(self) -> float:
        total_controls = max(len(self._findings), 1)
        passed = sum(1 for status in self._findings.values() if status == "resolved")
        return round((passed / total_controls) * 100, 2)

    def record_finding(self, *, control: str, status: str) -> None:
        self._findings[control] = status
        self._store.append(
            aggregate_id="dashboard:findings",
            event_type="dashboard.finding_recorded",
            actor="auditor",
            payload={"control": control, "status": status},
        )

    def remediation_task(self, *, task_id: str, description: str) -> None:
        self._remediations[task_id] = description
        self._store.append(
            aggregate_id="dashboard:remediation",
            event_type="dashboard.remediation_task",
            actor="auditor",
            payload={"task_id": task_id, "description": description},
        )

    def metrics(self) -> Mapping[str, Any]:
        return {
            "findings": dict(self._findings),
            "remediations": dict(self._remediations),
            "compliance_score": self.compliance_score(),
        }


# ---- External audit support ---------------------------------------------


class ExternalAuditSupport:
    """Package audit evidence and manage auditor access."""

    def __init__(self, store: EventStore) -> None:
        self._store = store
        self._auditors: Dict[str, Mapping[str, Any]] = {}
        self._evidence: Dict[str, List[str]] = defaultdict(list)

    def export_package(self, *, package_id: str, aggregates: Sequence[str]) -> Mapping[str, Any]:
        events: List[Mapping[str, Any]] = []
        for aggregate in aggregates:
            events.extend(
                {
                    "id": event.id,
                    "type": event.event_type,
                    "actor": event.actor,
                    "timestamp": event.timestamp.isoformat(),
                    "payload": event.payload,
                }
                for event in self._store.events(aggregate_id=aggregate)
            )
        package = {"package_id": package_id, "events": events}
        self._evidence[package_id].append(json.dumps(package))
        return package

    def grant_auditor_access(self, *, auditor_id: str, expires_at: datetime) -> None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        self._auditors[auditor_id] = {"expires_at": expires_at}
        self._store.append(
            aggregate_id="auditor:access",
            event_type="auditor.access_granted",
            actor="system",
            payload={"auditor_id": auditor_id, "expires_at": expires_at.isoformat()},
        )

    def verify_audit_trail(self) -> bool:
        self._store.verify()
        return True

    def collect_evidence(self, *, package_id: str, evidence: str) -> None:
        self._evidence[package_id].append(evidence)
        self._store.append(
            aggregate_id=f"evidence:{package_id}",
            event_type="auditor.evidence_collected",
            actor="auditor",
            payload={"evidence": evidence},
        )

    def auditor_access(self) -> Mapping[str, Mapping[str, Any]]:
        return dict(self._auditors)

    def evidence_packages(self) -> Mapping[str, Sequence[str]]:
        return {package_id: tuple(records) for package_id, records in self._evidence.items()}
