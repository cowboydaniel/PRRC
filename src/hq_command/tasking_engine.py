"""Tasking engine utilities for HQ Command.

The module provides typed models representing tasking requirements and
responder availability alongside deterministic scheduling logic.  Results from
``schedule_tasks_for_field_units`` are structured so FieldOps devices or other
consumers can synchronize assignments without additional transformation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, MutableSequence, Sequence, Tuple, Union

TaskPayload = Union["TaskingOrder", Mapping[str, Any]]
ResponderPayload = Union["ResponderStatus", Mapping[str, Any]]

ESCALATION_PRIORITY = 4


@dataclass(frozen=True, slots=True)
class TaskingOrder:
    """Describe a task HQ Command needs to allocate to responders.

    Attributes:
        task_id: Unique identifier for audit and follow-up.
        priority: Integer priority where higher values demand earlier servicing.
        capabilities_required: Capabilities a responder must provide.
        min_units: Minimum number of responders required for the task to start.
        max_units: Hard cap of responders that may be assigned.
        location: Optional geographic/operational location descriptor.
        metadata: Additional structured context kept for audit logs.
    """

    task_id: str
    priority: int
    capabilities_required: frozenset[str] = field(default_factory=frozenset)
    min_units: int = 1
    max_units: int = 1
    location: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task_id:
            raise ValueError("task_id is required for TaskingOrder")
        if self.priority < 0:
            raise ValueError("priority must be non-negative")
        if self.min_units < 0:
            raise ValueError("min_units cannot be negative")
        if self.max_units < 1:
            raise ValueError("max_units must be at least 1")
        if self.max_units < self.min_units:
            raise ValueError("max_units must be greater than or equal to min_units")

    @property
    def capability_requirements(self) -> frozenset[str]:
        """Return the normalized set of capability requirements."""

        return self.capabilities_required


@dataclass(slots=True)
class ResponderStatus:
    """Track responder availability and capabilities for scheduling."""

    unit_id: str
    capabilities: frozenset[str]
    status: str = "available"
    max_concurrent_tasks: int = 1
    current_tasks: MutableSequence[str] = field(default_factory=list)
    fatigue: float = 0.0
    location: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.unit_id:
            raise ValueError("unit_id is required for ResponderStatus")
        if self.max_concurrent_tasks < 1:
            raise ValueError("max_concurrent_tasks must be at least 1")
        if self.fatigue < 0:
            raise ValueError("fatigue cannot be negative")
        if self.status not in {"available", "busy", "offline"}:
            raise ValueError(f"Unsupported status '{self.status}'")

    def available_capacity(self) -> int:
        """Return the number of additional tasks the responder can accept."""

        if self.status != "available":
            return 0
        return max(self.max_concurrent_tasks - len(self.current_tasks), 0)

    def assign(self, task_id: str) -> None:
        """Record that the responder has accepted an assignment."""

        if self.available_capacity() <= 0:
            raise RuntimeError("Responder has no available capacity")
        self.current_tasks.append(task_id)


def _coerce_task(payload: TaskPayload) -> TaskingOrder:
    if isinstance(payload, TaskingOrder):
        return payload
    if not isinstance(payload, Mapping):
        raise TypeError("Task payloads must be TaskingOrder or mapping instances")

    try:
        task_id = payload["task_id"]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise ValueError("task payload missing 'task_id'") from exc

    priority = int(payload.get("priority", 0))
    capabilities = frozenset(payload.get("capabilities_required", ()))
    min_units = int(payload.get("min_units", payload.get("minimum_units", 1)))
    max_units = int(payload.get("max_units", payload.get("maximum_units", 1)))
    location = payload.get("location")
    metadata = payload.get("metadata", {})

    return TaskingOrder(
        task_id=task_id,
        priority=priority,
        capabilities_required=capabilities,
        min_units=min_units,
        max_units=max_units,
        location=location,
        metadata=metadata,
    )


def _coerce_responder(payload: ResponderPayload) -> ResponderStatus:
    if isinstance(payload, ResponderStatus):
        return payload
    if not isinstance(payload, Mapping):
        raise TypeError("Responder payloads must be ResponderStatus or mapping instances")

    try:
        unit_id = payload["unit_id"]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise ValueError("responder payload missing 'unit_id'") from exc

    capabilities = frozenset(payload.get("capabilities", ()))
    status = payload.get("status", "available")
    max_concurrent = int(payload.get("max_concurrent_tasks", payload.get("capacity", 1)))
    current_tasks: Sequence[str] = tuple(payload.get("current_tasks", ()))
    fatigue = float(payload.get("fatigue", 0.0))
    location = payload.get("location")
    metadata = payload.get("metadata", {})

    responder = ResponderStatus(
        unit_id=unit_id,
        capabilities=capabilities,
        status=status,
        max_concurrent_tasks=max_concurrent,
        fatigue=fatigue,
        location=location,
        metadata=metadata,
    )
    responder.current_tasks.extend(current_tasks)
    return responder


def _score_assignment(task: TaskingOrder, responder: ResponderStatus) -> int | None:
    """Compute a deterministic score for a task/responder pairing."""

    if responder.available_capacity() <= 0:
        return None
    if not task.capability_requirements.issubset(responder.capabilities):
        return None

    base = task.priority * 100
    capability_bonus = len(task.capability_requirements) * 10
    location_bonus = 0
    if task.location and responder.location:
        location_bonus = 5 if task.location == responder.location else -5
    load_penalty = (responder.max_concurrent_tasks - responder.available_capacity()) * 15
    fatigue_penalty = int(responder.fatigue * 10)

    return base + capability_bonus + location_bonus - load_penalty - fatigue_penalty


def schedule_tasks_for_field_units(
    tasks: Iterable[TaskPayload],
    responders: Iterable[ResponderPayload] | None = None,
) -> Dict[str, Any]:
    """Schedule tasks for FieldOps units.

    Args:
        tasks: Planned activities requiring assignment.
        responders: Units available for assignment.  When omitted an empty roster
            is assumed which will cause all tasks to defer.

    Returns:
        Structured metadata about the scheduling outcome for logging/telemetry.
    """

    task_objects: List[TaskingOrder] = [_coerce_task(task) for task in tasks]
    responder_objects: List[ResponderStatus] = [
        _coerce_responder(responder) for responder in (responders or [])
    ]

    tasks_in_priority = sorted(
        task_objects,
        key=lambda order: (-order.priority, order.task_id),
    )

    assignments: List[Dict[str, Any]] = []
    deferred: List[str] = []
    escalated: List[str] = []

    for task in tasks_in_priority:
        scored_candidates: List[Tuple[int, str, ResponderStatus]] = []
        for responder in responder_objects:
            score = _score_assignment(task, responder)
            if score is not None:
                scored_candidates.append((score, responder.unit_id, responder))

        scored_candidates.sort(key=lambda item: (-item[0], item[1]))

        assigned_count = 0
        for score, _, responder in scored_candidates:
            if assigned_count >= task.max_units:
                break
            if responder.available_capacity() <= 0:
                continue

            responder.assign(task.task_id)
            assignments.append(
                {
                    "task_id": task.task_id,
                    "unit_id": responder.unit_id,
                    "score": score,
                    "priority": task.priority,
                }
            )
            assigned_count += 1

        if assigned_count == 0:
            deferred.append(task.task_id)
            if task.priority >= ESCALATION_PRIORITY or task.min_units > 1:
                escalated.append(task.task_id)
        elif assigned_count < task.min_units:
            escalated.append(task.task_id)

    audit = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tasks_processed": len(task_objects),
        "units_considered": len(responder_objects),
        "assignments_made": len(assignments),
        "deferred_tasks": len(deferred),
        "escalated_tasks": len(escalated),
    }

    status = "complete" if not escalated else "escalated"

    return {
        "status": status,
        "assignments": assignments,
        "deferred": deferred,
        "escalated": escalated,
        "audit": audit,
    }
