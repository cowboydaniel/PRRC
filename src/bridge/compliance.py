"""Bridge compliance module with tamper-evident audit logging."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import uuid
from typing import Any, Dict, Iterable, Mapping


@dataclass(frozen=True)
class AuditRecord:
    """Single immutable audit entry stored within the log."""

    id: str
    jurisdiction: str
    event_type: str
    payload: Dict[str, Any]
    recorded_at: datetime
    previous_hash: str
    record_hash: str


def _normalise_event(event: Mapping[str, Any]) -> Dict[str, Any]:
    return {str(key): value for key, value in event.items()}


class TamperEvidentAuditLog:
    """Audit log that chains records using SHA-256 hashes."""

    def __init__(self, *, default_retention_days: int = 90) -> None:
        self.default_retention_days = default_retention_days
        self._records: list[AuditRecord] = []

    def record(self, event: Mapping[str, Any]) -> AuditRecord:
        """Persist an event and return the immutable audit record."""

        payload = _normalise_event(event)
        jurisdiction = str(payload.get("jurisdiction", "unknown")).lower()
        event_type = str(payload.get("event_type", "unspecified"))
        retention_days = int(payload.get("retention_days", self.default_retention_days))

        timestamp = datetime.now(timezone.utc)
        previous_hash = self._records[-1].record_hash if self._records else "genesis"

        serialised_payload = json.dumps(payload, sort_keys=True, default=str)
        record_hash = hashlib.sha256(
            "|".join([previous_hash, timestamp.isoformat(), serialised_payload]).encode("utf-8")
        ).hexdigest()

        record = AuditRecord(
            id=str(uuid.uuid4()),
            jurisdiction=jurisdiction,
            event_type=event_type,
            payload=payload,
            recorded_at=timestamp,
            previous_hash=previous_hash,
            record_hash=record_hash,
        )

        self._records.append(record)
        self._enforce_retention(jurisdiction, retention_days)
        return record

    def history(self, *, jurisdiction: str | None = None) -> Iterable[AuditRecord]:
        if jurisdiction is None:
            return tuple(self._records)
        jurisdiction_lower = jurisdiction.lower()
        return tuple(record for record in self._records if record.jurisdiction == jurisdiction_lower)

    def _enforce_retention(self, jurisdiction: str, retention_days: int) -> None:
        horizon = datetime.now(timezone.utc) - timedelta(days=retention_days)
        kept: list[AuditRecord] = []
        latest_for_jurisdiction: AuditRecord | None = None

        for record in self._records:
            if record.jurisdiction != jurisdiction:
                kept.append(record)
                continue

            latest_for_jurisdiction = record
            if record.recorded_at >= horizon:
                kept.append(record)

        if latest_for_jurisdiction and not any(
            record.jurisdiction == jurisdiction for record in kept
        ):
            kept.append(latest_for_jurisdiction)

        self._records = kept


_DEFAULT_AUDIT_LOG = TamperEvidentAuditLog()


def configure_audit_log(log: TamperEvidentAuditLog) -> None:
    """Configure the module-level audit log instance."""

    global _DEFAULT_AUDIT_LOG
    _DEFAULT_AUDIT_LOG = log


def audit_event(event: Mapping[str, Any]) -> Dict[str, Any]:
    """Record an audit event and return acknowledgement metadata."""

    record = _DEFAULT_AUDIT_LOG.record(event)
    return {
        "status": "recorded",
        "record_id": record.id,
        "record_hash": record.record_hash,
        "previous_hash": record.previous_hash,
        "recorded_at": record.recorded_at,
        "jurisdiction": record.jurisdiction,
        "event_type": record.event_type,
    }
