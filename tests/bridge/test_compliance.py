from __future__ import annotations

from bridge.compliance import TamperEvidentAuditLog, audit_event, configure_audit_log


def setup_function(function) -> None:  # pragma: no cover - pytest hook
    configure_audit_log(TamperEvidentAuditLog())


def test_audit_event_records_hash_chain() -> None:
    configure_audit_log(TamperEvidentAuditLog())
    first = audit_event({"jurisdiction": "US", "event_type": "route", "details": "first"})
    second = audit_event({"jurisdiction": "US", "event_type": "route", "details": "second"})

    assert first["status"] == "recorded"
    assert second["status"] == "recorded"
    assert second["previous_hash"] == first["record_hash"]


def test_retention_policy_prunes_outdated_events() -> None:
    log = TamperEvidentAuditLog(default_retention_days=30)
    configure_audit_log(log)

    first = audit_event(
        {
            "jurisdiction": "EU",
            "event_type": "route",
            "details": "first",
            "retention_days": 10,
        }
    )
    second = audit_event(
        {
            "jurisdiction": "EU",
            "event_type": "route",
            "details": "second",
            "retention_days": 0,
        }
    )

    assert first["status"] == "recorded"
    assert second["status"] == "recorded"
    records = list(log.history(jurisdiction="EU"))
    assert len(records) == 1
    assert records[0].payload["details"] == "second"
