"""
Shared Protocol for HQ Command <-> FieldOps Communication

This module defines the message format and data contracts for communication
between HQ Command and FieldOps, routed through the Bridge module.

All messages flow through the Bridge for compliance auditing and protocol translation.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Literal, Any
from enum import Enum


class MessageType(str, Enum):
    """Types of messages exchanged between HQ and FieldOps"""
    # HQ → FieldOps
    TASK_ASSIGNMENT = "task_assignment"
    TASK_UPDATE = "task_update"
    TASK_CANCELLATION = "task_cancellation"

    # FieldOps → HQ
    TELEMETRY_REPORT = "telemetry_report"
    OPERATIONS_SYNC = "operations_sync"
    STATUS_UPDATE = "status_update"

    # Bidirectional
    ACKNOWLEDGEMENT = "acknowledgement"
    ERROR = "error"


@dataclass
class MessageEnvelope:
    """
    Standard envelope for all HQ-FieldOps messages

    Wraps payload with routing and audit metadata
    """
    message_id: str
    message_type: MessageType
    sender_id: str
    recipient_id: str
    timestamp: datetime
    payload: dict[str, Any]
    correlation_id: str | None = None  # For request-response tracking

    def to_dict(self) -> dict[str, Any]:
        """Serialize for transmission"""
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MessageEnvelope":
        """Deserialize from transmission"""
        return cls(
            message_id=data["message_id"],
            message_type=MessageType(data["message_type"]),
            sender_id=data["sender_id"],
            recipient_id=data["recipient_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            payload=data["payload"],
            correlation_id=data.get("correlation_id"),
        )


# ============================================================================
# HQ → FieldOps Message Payloads
# ============================================================================

@dataclass
class TaskAssignmentPayload:
    """
    Payload for TASK_ASSIGNMENT messages

    Sent from HQ Command to FieldOps to assign new tasks to field units
    """
    tasks: list[dict[str, Any]]  # List of serialized TaskingOrder objects
    operator_id: str
    issued_at: datetime
    expires_at: datetime | None = None
    priority_override: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tasks": self.tasks,
            "operator_id": self.operator_id,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "priority_override": self.priority_override,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskAssignmentPayload":
        return cls(
            tasks=data["tasks"],
            operator_id=data["operator_id"],
            issued_at=datetime.fromisoformat(data["issued_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            priority_override=data.get("priority_override"),
        )


@dataclass
class TaskUpdatePayload:
    """Payload for TASK_UPDATE messages (task modifications)"""
    task_id: str
    updates: dict[str, Any]  # Fields to update
    updated_by: str
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "updates": self.updates,
            "updated_by": self.updated_by,
            "reason": self.reason,
        }


@dataclass
class TaskCancellationPayload:
    """Payload for TASK_CANCELLATION messages"""
    task_ids: list[str]
    cancelled_by: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_ids": self.task_ids,
            "cancelled_by": self.cancelled_by,
            "reason": self.reason,
        }


# ============================================================================
# FieldOps → HQ Message Payloads
# ============================================================================

@dataclass
class TelemetryReportPayload:
    """
    Payload for TELEMETRY_REPORT messages

    Sent from FieldOps to HQ with telemetry snapshots
    """
    device_id: str
    telemetry: dict[str, Any]  # Serialized TelemetrySnapshot
    collected_at: datetime
    location: tuple[float, float] | None = None  # (lat, lon)

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "telemetry": self.telemetry,
            "collected_at": self.collected_at.isoformat(),
            "location": list(self.location) if self.location else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TelemetryReportPayload":
        location = data.get("location")
        return cls(
            device_id=data["device_id"],
            telemetry=data["telemetry"],
            collected_at=datetime.fromisoformat(data["collected_at"]),
            location=tuple(location) if location else None,
        )


@dataclass
class OperationsSyncPayload:
    """
    Payload for OPERATIONS_SYNC messages

    Sent from FieldOps to HQ with offline operations queue
    """
    device_id: str
    operations: list[dict[str, Any]]  # Serialized OfflineOperation objects
    synced_at: datetime
    sequence_number: int  # Increments with each sync for ordering

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "operations": self.operations,
            "synced_at": self.synced_at.isoformat(),
            "sequence_number": self.sequence_number,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OperationsSyncPayload":
        return cls(
            device_id=data["device_id"],
            operations=data["operations"],
            synced_at=datetime.fromisoformat(data["synced_at"]),
            sequence_number=data["sequence_number"],
        )


@dataclass
class StatusUpdatePayload:
    """Payload for STATUS_UPDATE messages (unit status changes)"""
    unit_id: str
    status: Literal["available", "busy", "offline", "maintenance"]
    capabilities: list[str]
    max_concurrent_tasks: int
    current_task_count: int
    fatigue_level: float  # 0.0 to 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================================
# Bidirectional Message Payloads
# ============================================================================

@dataclass
class AcknowledgementPayload:
    """Payload for ACKNOWLEDGEMENT messages"""
    ack_message_id: str  # ID of message being acknowledged
    status: Literal["received", "processing", "completed", "failed"]
    details: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ErrorPayload:
    """Payload for ERROR messages"""
    error_code: str
    error_message: str
    related_message_id: str | None = None
    retry_after: int | None = None  # Seconds to wait before retry

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================================
# Protocol Utilities
# ============================================================================

def create_task_assignment_message(
    tasks: list[dict[str, Any]],
    operator_id: str,
    sender_id: str,
    recipient_id: str,
    message_id: str | None = None,
    expires_at: datetime | None = None,
) -> MessageEnvelope:
    """
    Convenience function to create a task assignment message

    Args:
        tasks: List of serialized TaskingOrder objects
        operator_id: ID of operator issuing the tasks
        sender_id: HQ Command instance ID
        recipient_id: FieldOps device/unit ID
        message_id: Optional custom message ID
        expires_at: Optional expiration timestamp

    Returns:
        MessageEnvelope ready for transmission
    """
    import uuid

    payload = TaskAssignmentPayload(
        tasks=tasks,
        operator_id=operator_id,
        issued_at=datetime.utcnow(),
        expires_at=expires_at,
    )

    return MessageEnvelope(
        message_id=message_id or str(uuid.uuid4()),
        message_type=MessageType.TASK_ASSIGNMENT,
        sender_id=sender_id,
        recipient_id=recipient_id,
        timestamp=datetime.utcnow(),
        payload=payload.to_dict(),
    )


def create_telemetry_report_message(
    device_id: str,
    telemetry: dict[str, Any],
    sender_id: str,
    recipient_id: str,
    message_id: str | None = None,
    location: tuple[float, float] | None = None,
) -> MessageEnvelope:
    """
    Convenience function to create a telemetry report message

    Args:
        device_id: FieldOps device/unit ID
        telemetry: Serialized TelemetrySnapshot
        sender_id: FieldOps device/unit ID
        recipient_id: HQ Command instance ID
        message_id: Optional custom message ID
        location: Optional GPS coordinates

    Returns:
        MessageEnvelope ready for transmission
    """
    import uuid

    payload = TelemetryReportPayload(
        device_id=device_id,
        telemetry=telemetry,
        collected_at=datetime.utcnow(),
        location=location,
    )

    return MessageEnvelope(
        message_id=message_id or str(uuid.uuid4()),
        message_type=MessageType.TELEMETRY_REPORT,
        sender_id=sender_id,
        recipient_id=recipient_id,
        timestamp=datetime.utcnow(),
        payload=payload.to_dict(),
    )


def create_operations_sync_message(
    device_id: str,
    operations: list[dict[str, Any]],
    sequence_number: int,
    sender_id: str,
    recipient_id: str,
    message_id: str | None = None,
) -> MessageEnvelope:
    """
    Convenience function to create an operations sync message

    Args:
        device_id: FieldOps device/unit ID
        operations: List of serialized OfflineOperation objects
        sequence_number: Sequence number for ordering
        sender_id: FieldOps device/unit ID
        recipient_id: HQ Command instance ID
        message_id: Optional custom message ID

    Returns:
        MessageEnvelope ready for transmission
    """
    import uuid

    payload = OperationsSyncPayload(
        device_id=device_id,
        operations=operations,
        synced_at=datetime.utcnow(),
        sequence_number=sequence_number,
    )

    return MessageEnvelope(
        message_id=message_id or str(uuid.uuid4()),
        message_type=MessageType.OPERATIONS_SYNC,
        sender_id=sender_id,
        recipient_id=recipient_id,
        timestamp=datetime.utcnow(),
        payload=payload.to_dict(),
    )


def create_acknowledgement_message(
    ack_message_id: str,
    status: Literal["received", "processing", "completed", "failed"],
    sender_id: str,
    recipient_id: str,
    details: str | None = None,
    message_id: str | None = None,
) -> MessageEnvelope:
    """
    Convenience function to create an acknowledgement message

    Args:
        ack_message_id: ID of message being acknowledged
        status: Acknowledgement status
        sender_id: ID of acknowledging party
        recipient_id: ID of original sender
        details: Optional details
        message_id: Optional custom message ID

    Returns:
        MessageEnvelope ready for transmission
    """
    import uuid

    payload = AcknowledgementPayload(
        ack_message_id=ack_message_id,
        status=status,
        details=details,
    )

    return MessageEnvelope(
        message_id=message_id or str(uuid.uuid4()),
        message_type=MessageType.ACKNOWLEDGEMENT,
        sender_id=sender_id,
        recipient_id=recipient_id,
        timestamp=datetime.utcnow(),
        payload=payload.to_dict(),
        correlation_id=ack_message_id,
    )
