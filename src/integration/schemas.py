"""
Integration Message Schema Validation

This module provides schema validation for all message types exchanged between
HQ Command and FieldOps through the integration layer.

The schemas ensure data integrity and provide clear validation errors when
message payloads don't conform to expected formats.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

# Import shared schemas - handle both package and module imports
try:
    from shared.schemas import validate_priority, priority_to_int, priority_to_string
except ImportError:
    from ..shared.schemas import validate_priority, priority_to_int, priority_to_string


class ValidationError(Exception):
    """Raised when message payload validation fails."""
    pass


@dataclass
class TaskAssignmentSchema:
    """
    Schema for task assignment messages from HQ to FieldOps.

    Validates that task assignments contain all required fields and
    proper data types.
    """
    task_id: str
    priority: Union[int, str]  # Can be int (HQ) or str (FieldOps)
    capabilities_required: List[str] = field(default_factory=list)
    location: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    created_at: Optional[str] = None
    expires_at: Optional[str] = None

    def __post_init__(self):
        """Validate fields after initialization."""
        # Validate task_id
        if not self.task_id or not isinstance(self.task_id, str):
            raise ValidationError("task_id must be a non-empty string")

        # Validate priority
        if not validate_priority(self.priority):
            raise ValidationError(
                f"Invalid priority: {self.priority}. Must be 1-5 (int) or "
                "'Routine'/'High'/'Critical' (str)"
            )

        # Validate capabilities_required
        if not isinstance(self.capabilities_required, list):
            raise ValidationError("capabilities_required must be a list")

        for cap in self.capabilities_required:
            if not isinstance(cap, str):
                raise ValidationError(
                    f"All capabilities must be strings, got: {type(cap)}"
                )

        # Validate timestamps if provided
        for field_name in ['created_at', 'expires_at']:
            timestamp = getattr(self, field_name)
            if timestamp is not None:
                try:
                    if isinstance(timestamp, str):
                        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except (ValueError, AttributeError) as e:
                    raise ValidationError(
                        f"{field_name} must be a valid ISO format timestamp: {e}"
                    )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskAssignmentSchema":
        """Create schema instance from dictionary, validating all fields."""
        return cls(
            task_id=data.get("task_id", ""),
            priority=data.get("priority", 3),
            capabilities_required=data.get("capabilities_required", []),
            location=data.get("location"),
            title=data.get("title"),
            description=data.get("description"),
            assigned_to=data.get("assigned_to"),
            created_at=data.get("created_at"),
            expires_at=data.get("expires_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for transmission."""
        result = {
            "task_id": self.task_id,
            "priority": self.priority,
            "capabilities_required": self.capabilities_required,
        }

        # Add optional fields if present
        if self.location:
            result["location"] = self.location
        if self.title:
            result["title"] = self.title
        if self.description:
            result["description"] = self.description
        if self.assigned_to:
            result["assigned_to"] = self.assigned_to
        if self.created_at:
            result["created_at"] = self.created_at
        if self.expires_at:
            result["expires_at"] = self.expires_at

        return result


@dataclass
class StatusUpdateSchema:
    """
    Schema for status update messages from FieldOps to HQ.

    Validates responder status updates including task progress,
    availability, and capabilities.
    """
    device_id: str
    status: str  # "available", "busy", "offline", "emergency"
    timestamp: str
    current_tasks: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    max_concurrent_tasks: Optional[int] = None
    fatigue_level: Optional[float] = None
    location: Optional[tuple] = None

    def __post_init__(self):
        """Validate fields after initialization."""
        # Validate device_id
        if not self.device_id or not isinstance(self.device_id, str):
            raise ValidationError("device_id must be a non-empty string")

        # Validate status
        valid_statuses = {"available", "busy", "offline", "emergency"}
        if self.status not in valid_statuses:
            raise ValidationError(
                f"Invalid status: {self.status}. Must be one of {valid_statuses}"
            )

        # Validate timestamp
        try:
            datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        except (ValueError, AttributeError) as e:
            raise ValidationError(f"Invalid timestamp format: {e}")

        # Validate current_tasks
        if not isinstance(self.current_tasks, list):
            raise ValidationError("current_tasks must be a list")

        # Validate capabilities
        if not isinstance(self.capabilities, list):
            raise ValidationError("capabilities must be a list")

        # Validate max_concurrent_tasks
        if self.max_concurrent_tasks is not None:
            if not isinstance(self.max_concurrent_tasks, int) or self.max_concurrent_tasks < 0:
                raise ValidationError(
                    "max_concurrent_tasks must be a non-negative integer"
                )

        # Validate fatigue_level
        if self.fatigue_level is not None:
            if not isinstance(self.fatigue_level, (int, float)):
                raise ValidationError("fatigue_level must be a number")
            if not 0.0 <= self.fatigue_level <= 1.0:
                raise ValidationError("fatigue_level must be between 0.0 and 1.0")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StatusUpdateSchema":
        """Create schema instance from dictionary, validating all fields."""
        return cls(
            device_id=data.get("device_id", ""),
            status=data.get("status", "unknown"),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            current_tasks=data.get("current_tasks", []),
            capabilities=data.get("capabilities", []),
            max_concurrent_tasks=data.get("max_concurrent_tasks"),
            fatigue_level=data.get("fatigue_level"),
            location=data.get("location"),
        )


@dataclass
class TelemetrySchema:
    """
    Schema for telemetry report messages from FieldOps to HQ.

    Validates telemetry data including sensor readings, events,
    and queue status.
    """
    device_id: str
    collected_at: str
    status: str
    metrics: Dict[str, Any]
    location: Optional[tuple] = None

    def __post_init__(self):
        """Validate fields after initialization."""
        # Validate device_id
        if not self.device_id or not isinstance(self.device_id, str):
            raise ValidationError("device_id must be a non-empty string")

        # Validate collected_at timestamp
        try:
            datetime.fromisoformat(self.collected_at.replace('Z', '+00:00'))
        except (ValueError, AttributeError) as e:
            raise ValidationError(f"Invalid collected_at timestamp: {e}")

        # Validate status
        if not isinstance(self.status, str):
            raise ValidationError("status must be a string")

        # Validate metrics structure
        if not isinstance(self.metrics, dict):
            raise ValidationError("metrics must be a dictionary")

        # Validate sensors if present
        if "sensors" in self.metrics:
            if not isinstance(self.metrics["sensors"], list):
                raise ValidationError("metrics.sensors must be a list")

            for sensor in self.metrics["sensors"]:
                if not isinstance(sensor, dict):
                    raise ValidationError("Each sensor must be a dictionary")

                # Check required sensor fields
                required_fields = ["id", "type", "value"]
                for field_name in required_fields:
                    if field_name not in sensor:
                        raise ValidationError(
                            f"Sensor missing required field: {field_name}"
                        )

        # Validate location if present
        if self.location is not None:
            if not isinstance(self.location, (tuple, list)) or len(self.location) != 2:
                raise ValidationError(
                    "location must be a tuple/list of (latitude, longitude)"
                )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelemetrySchema":
        """Create schema instance from dictionary, validating all fields."""
        return cls(
            device_id=data.get("device_id", ""),
            collected_at=data.get("collected_at", datetime.utcnow().isoformat()),
            status=data.get("status", "unknown"),
            metrics=data.get("metrics", {}),
            location=data.get("location"),
        )


@dataclass
class ResourceAllocationSchema:
    """
    Schema for resource allocation messages.

    Validates resource requests and allocations between HQ and FieldOps.
    """
    resource_id: str
    resource_type: str  # "personnel", "equipment", "supplies", etc.
    quantity: int
    requesting_unit: str
    timestamp: str
    priority: Union[int, str]
    status: str = "pending"  # "pending", "approved", "denied", "fulfilled"
    notes: Optional[str] = None

    def __post_init__(self):
        """Validate fields after initialization."""
        # Validate resource_id
        if not self.resource_id or not isinstance(self.resource_id, str):
            raise ValidationError("resource_id must be a non-empty string")

        # Validate resource_type
        if not self.resource_type or not isinstance(self.resource_type, str):
            raise ValidationError("resource_type must be a non-empty string")

        # Validate quantity
        if not isinstance(self.quantity, int) or self.quantity <= 0:
            raise ValidationError("quantity must be a positive integer")

        # Validate requesting_unit
        if not self.requesting_unit or not isinstance(self.requesting_unit, str):
            raise ValidationError("requesting_unit must be a non-empty string")

        # Validate timestamp
        try:
            datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        except (ValueError, AttributeError) as e:
            raise ValidationError(f"Invalid timestamp format: {e}")

        # Validate priority
        if not validate_priority(self.priority):
            raise ValidationError(
                f"Invalid priority: {self.priority}. Must be 1-5 (int) or "
                "'Routine'/'High'/'Critical' (str)"
            )

        # Validate status
        valid_statuses = {"pending", "approved", "denied", "fulfilled"}
        if self.status not in valid_statuses:
            raise ValidationError(
                f"Invalid status: {self.status}. Must be one of {valid_statuses}"
            )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResourceAllocationSchema":
        """Create schema instance from dictionary, validating all fields."""
        return cls(
            resource_id=data.get("resource_id", ""),
            resource_type=data.get("resource_type", ""),
            quantity=data.get("quantity", 0),
            requesting_unit=data.get("requesting_unit", ""),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            priority=data.get("priority", 3),
            status=data.get("status", "pending"),
            notes=data.get("notes"),
        )


def validate_task_assignment(data: Dict[str, Any]) -> TaskAssignmentSchema:
    """
    Validate a task assignment message payload.

    Args:
        data: Dictionary containing task assignment data

    Returns:
        Validated TaskAssignmentSchema instance

    Raises:
        ValidationError: If validation fails
    """
    return TaskAssignmentSchema.from_dict(data)


def validate_status_update(data: Dict[str, Any]) -> StatusUpdateSchema:
    """
    Validate a status update message payload.

    Args:
        data: Dictionary containing status update data

    Returns:
        Validated StatusUpdateSchema instance

    Raises:
        ValidationError: If validation fails
    """
    return StatusUpdateSchema.from_dict(data)


def validate_telemetry(data: Dict[str, Any]) -> TelemetrySchema:
    """
    Validate a telemetry report message payload.

    Args:
        data: Dictionary containing telemetry data

    Returns:
        Validated TelemetrySchema instance

    Raises:
        ValidationError: If validation fails
    """
    return TelemetrySchema.from_dict(data)


def validate_resource_allocation(data: Dict[str, Any]) -> ResourceAllocationSchema:
    """
    Validate a resource allocation message payload.

    Args:
        data: Dictionary containing resource allocation data

    Returns:
        Validated ResourceAllocationSchema instance

    Raises:
        ValidationError: If validation fails
    """
    return ResourceAllocationSchema.from_dict(data)
