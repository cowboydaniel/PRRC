"""Controller logic for the HQ Command GUI package."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Sequence

from hq_command.analytics import summarize_field_telemetry
from hq_command.tasking_engine import (
    ResponderPayload,
    ResponderStatus,
    TaskPayload,
    TaskingOrder,
    schedule_tasks_for_field_units,
)

from .qt_compat import QtCore


class BaseListModel(QtCore.QAbstractListModel):
    """Simple list model that works with or without real Qt bindings."""

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._items: list[Any] = []

    # Qt signature uses camelCase and optional QModelIndex argument.
    def rowCount(self, parent: QtCore.QModelIndex | None = None) -> int:  # type: ignore[override]
        if hasattr(self, "_get_items"):
            return len(getattr(self, "_get_items")())  # type: ignore[misc]
        return len(self._items)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole) -> Any:  # type: ignore[override]
        row = index.row()
        if hasattr(self, "_get_items"):
            source = list(getattr(self, "_get_items")())  # type: ignore[misc]
        else:
            source = self._items
        if not 0 <= row < len(source):
            return None
        if role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole, QtCore.Qt.UserRole):
            return source[row]
        return None

    # Convenience helpers used by the controller to provide deterministic data to
    # unit tests without relying on Qt-specific signals.
    def set_items(self, items: Iterable[Any]) -> None:
        items_list = list(items)

        begin_reset = getattr(self, "beginResetModel", None)
        if callable(begin_reset):  # pragma: no branch - simple guard
            begin_reset()

        if hasattr(self, "_set_items"):
            getattr(self, "_set_items")(items_list)  # type: ignore[misc]
        else:
            self._items = list(items_list)

        end_reset = getattr(self, "endResetModel", None)
        if callable(end_reset):  # pragma: no branch - simple guard
            end_reset()

        if not hasattr(self, "_set_items"):
            # Mirror the shim storage when real Qt bindings are available.
            self._items = items_list

    def items(self) -> list[Any]:
        if hasattr(self, "_get_items"):
            return list(getattr(self, "_get_items")())  # type: ignore[misc]
        return list(self._items)


class RosterListModel(BaseListModel):
    """Represents responder roster details for the GUI."""


class TaskQueueModel(BaseListModel):
    """Represents the active task queue and scheduling outcomes."""


class TelemetrySummaryModel(BaseListModel):
    """Flattens telemetry summaries into key/value rows for display."""


@dataclass
class ControllerState:
    tasks: Sequence[TaskPayload]
    responders: Sequence[ResponderPayload]
    telemetry: Mapping[str, Any]
    operator: Mapping[str, Any] = field(default_factory=dict)


class HQCommandController:
    """Coordinate data loading, scheduling, and GUI model updates."""

    def __init__(self) -> None:
        self._state = ControllerState(tasks=[], responders=[], telemetry={}, operator={})
        self.roster_model = RosterListModel()
        self.task_queue_model = TaskQueueModel()
        self.telemetry_model = TelemetrySummaryModel()
        self._last_schedule: dict[str, Any] | None = None

    # ------------------------------------------------------------------ loading
    def load_from_payload(self, payload: Mapping[str, Any]) -> None:
        """Seed controller state from an in-memory payload."""

        tasks = payload.get("tasks", [])
        responders = payload.get("responders", [])
        telemetry = payload.get("telemetry", {})
        operator = payload.get("operator", {})
        self._state = ControllerState(
            tasks=list(tasks),
            responders=list(responders),
            telemetry=dict(telemetry),
            operator=dict(operator) if isinstance(operator, Mapping) else {},
        )
        self.refresh_models()

    def load_from_file(self, path: Path) -> None:
        """Load controller state from a JSON document."""

        data = json.loads(path.read_text())
        self.load_from_payload(data)

    # ---------------------------------------------------------------- scheduling
    def refresh_models(self) -> None:
        """Recompute scheduling output and update Qt models."""

        task_objects = [self._coerce_task(task) for task in self._state.tasks]
        responder_objects = [self._coerce_responder(resp) for resp in self._state.responders]

        schedule_result = schedule_tasks_for_field_units(task_objects, responder_objects)
        self._last_schedule = schedule_result

        manual_assignments: list[dict[str, Any]] = []
        scheduled_pairs = {
            (assignment["task_id"], assignment["unit_id"])
            for assignment in schedule_result["assignments"]
        }
        for responder in responder_objects:
            for task_id in responder.current_tasks:
                pair = (task_id, responder.unit_id)
                if pair in scheduled_pairs:
                    continue
                manual_assignments.append(
                    {
                        "task_id": task_id,
                        "unit_id": responder.unit_id,
                        "score": None,
                        "manual": True,
                    }
                )

        combined_assignments = list(schedule_result["assignments"]) + manual_assignments
        assignments_by_unit = self._group_assignments(combined_assignments, key="unit_id")
        assignments_by_task = self._group_assignments(combined_assignments, key="task_id")
        manual_task_ids = {entry["task_id"] for entry in manual_assignments}

        roster_rows = [
            {
                "unit_id": responder.unit_id,
                "status": responder.status,
                "capabilities": sorted(responder.capabilities),
                "current_tasks": list(responder.current_tasks),
                "available_capacity": responder.available_capacity(),
                "fatigue": responder.fatigue,
                "assigned": assignments_by_unit.get(responder.unit_id, []),
            }
            for responder in responder_objects
        ]
        self.roster_model.set_items(roster_rows)

        task_rows = [
            {
                "task_id": task.task_id,
                "priority": task.priority,
                "required_capabilities": sorted(task.capabilities_required),
                "assigned_units": [
                    assignment["unit_id"] for assignment in assignments_by_task.get(task.task_id, [])
                ],
                "scores": [assignment["score"] for assignment in assignments_by_task.get(task.task_id, [])],
                "status": self._task_status(task.task_id, schedule_result, manual_task_ids),
                "escalated": task.task_id in schedule_result["escalated"],
            }
            for task in task_objects
        ]
        self.task_queue_model.set_items(task_rows)

        telemetry_summary = summarize_field_telemetry(self._state.telemetry)
        telemetry_rows = [
            {"metric": key, "value": value}
            for key, value in sorted(telemetry_summary.items())
        ]
        self.telemetry_model.set_items(telemetry_rows)

    # ----------------------------------------------------------------- operator
    def operator_profile(self) -> Mapping[str, Any]:
        """Return the active operator profile payload."""

        return self._state.operator

    def operator_roles(self) -> tuple[str, ...]:
        """Return roles assigned to the operator."""

        roles = self._state.operator.get("roles")
        if isinstance(roles, str):
            return (roles,)
        if isinstance(roles, Sequence):
            return tuple(str(role) for role in roles if isinstance(role, str))
        return ()

    def operator_active_role(self) -> str | None:
        """Return the operator's preferred active role if provided."""

        active = self._state.operator.get("active_role")
        return str(active) if isinstance(active, str) else None

    def apply_manual_assignment(self, task_id: str, unit_id: str) -> None:
        """Record a manual assignment and refresh models.

        Manual overrides simply append the task identifier to the targeted
        responder's ``current_tasks`` collection.  The scheduler is then invoked
        again so deterministic scoring can reconcile the override with other
        priorities.
        """

        updated = False
        new_responders: List[Mapping[str, Any]] = []
        for responder in self._state.responders:
            if isinstance(responder, ResponderStatus):
                payload = {
                    "unit_id": responder.unit_id,
                    "capabilities": list(responder.capabilities),
                    "status": responder.status,
                    "max_concurrent_tasks": responder.max_concurrent_tasks,
                    "current_tasks": list(responder.current_tasks),
                    "fatigue": responder.fatigue,
                    "location": responder.location,
                    "metadata": dict(responder.metadata),
                }
            else:
                payload = dict(responder)

            if payload.get("unit_id") == unit_id:
                tasks = list(payload.get("current_tasks", []))
                if task_id not in tasks:
                    tasks.append(task_id)
                payload["current_tasks"] = tasks
                payload["status"] = payload.get("status", "available")
                updated = True
            new_responders.append(payload)

        if not updated:
            raise ValueError(f"No responder with unit_id '{unit_id}' present in roster")

        self._state = ControllerState(tasks=self._state.tasks, responders=new_responders, telemetry=self._state.telemetry)
        self.refresh_models()

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _group_assignments(assignments: Sequence[Mapping[str, Any]], *, key: str) -> dict[str, list[Mapping[str, Any]]]:
        grouped: dict[str, list[Mapping[str, Any]]] = {}
        for entry in assignments:
            grouped.setdefault(str(entry[key]), []).append(dict(entry))
        return grouped

    @staticmethod
    def _task_status(
        task_id: str,
        schedule_result: Mapping[str, Any],
        manual_assignments: set[str] | None = None,
    ) -> str:
        if task_id in schedule_result.get("escalated", []):
            return "escalated"
        if task_id in schedule_result.get("deferred", []) and not (
            manual_assignments and task_id in manual_assignments
        ):
            return "deferred"
        if manual_assignments and task_id in manual_assignments:
            return "assigned"
        assignment_units = [assignment for assignment in schedule_result.get("assignments", []) if assignment.get("task_id") == task_id]
        if assignment_units:
            return "assigned"
        return "pending"

    @staticmethod
    def _coerce_task(task: TaskPayload) -> TaskingOrder:
        if isinstance(task, TaskingOrder):
            return task
        return TaskingOrder(
            task_id=str(task["task_id"]),
            priority=int(task.get("priority", 0)),
            capabilities_required=frozenset(task.get("capabilities_required", [])),
            min_units=int(task.get("min_units", task.get("minimum_units", 1))),
            max_units=int(task.get("max_units", task.get("maximum_units", 1))),
            location=task.get("location"),
            metadata=task.get("metadata", {}),
        )

    @staticmethod
    def _coerce_responder(responder: ResponderPayload) -> ResponderStatus:
        if isinstance(responder, ResponderStatus):
            return responder
        return ResponderStatus(
            unit_id=str(responder["unit_id"]),
            capabilities=frozenset(responder.get("capabilities", [])),
            status=responder.get("status", "available"),
            max_concurrent_tasks=int(responder.get("max_concurrent_tasks", responder.get("capacity", 1))),
            current_tasks=list(responder.get("current_tasks", [])),
            fatigue=float(responder.get("fatigue", 0.0)),
            location=responder.get("location"),
            metadata=responder.get("metadata", {}),
        )

    # Exposed for tests and the CLI to inspect scheduling details.
    @property
    def last_schedule(self) -> Mapping[str, Any] | None:
        return self._last_schedule
