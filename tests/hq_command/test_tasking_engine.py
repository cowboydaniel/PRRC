from __future__ import annotations

import pytest

from hq_command.tasking_engine import (
    ESCALATION_PRIORITY,
    ResponderStatus,
    TaskingOrder,
    schedule_tasks_for_field_units,
)


def test_scheduling_assigns_high_priority_and_defers_lower_priority() -> None:
    urgent = TaskingOrder(
        task_id="urgent-med",
        priority=ESCALATION_PRIORITY + 1,
        capabilities_required=frozenset({"medic"}),
    )
    routine = TaskingOrder(
        task_id="routine-check",
        priority=1,
        capabilities_required=frozenset({"medic"}),
    )

    responder = ResponderStatus(
        unit_id="med-1",
        capabilities=frozenset({"medic"}),
        max_concurrent_tasks=1,
    )

    result = schedule_tasks_for_field_units([routine, urgent], [responder])

    assert [assignment["task_id"] for assignment in result["assignments"]] == [
        "urgent-med"
    ]
    assert result["deferred"] == ["routine-check"]
    # urgent task should escalate if it cannot be serviced; ensure routine low
    assert result["escalated"] == []
    assert result["status"] == "complete"


def test_partial_fulfillment_triggers_escalation() -> None:
    mass_casualty = TaskingOrder(
        task_id="mass-casualty",
        priority=ESCALATION_PRIORITY,
        capabilities_required=frozenset({"medic"}),
        min_units=2,
        max_units=3,
    )

    responders = [
        ResponderStatus(unit_id="med-1", capabilities=frozenset({"medic"})),
    ]

    result = schedule_tasks_for_field_units([mass_casualty], responders)

    assert result["assignments"][0]["task_id"] == "mass-casualty"
    assert result["escalated"] == ["mass-casualty"]
    assert result["status"] == "escalated"


def test_invalid_task_payload_raises_value_error() -> None:
    responder = ResponderStatus(unit_id="alpha", capabilities=frozenset({"medic"}))

    with pytest.raises(ValueError):
        schedule_tasks_for_field_units([
            {"priority": 3, "capabilities_required": ["medic"]}
        ], [responder])


def test_audit_metadata_tracks_results() -> None:
    tasks = [
        TaskingOrder(task_id="one", priority=1),
        TaskingOrder(task_id="two", priority=2),
    ]
    responders: list[ResponderStatus] = []

    result = schedule_tasks_for_field_units(tasks, responders)

    assert result["audit"]["tasks_processed"] == 2
    assert result["audit"]["units_considered"] == 0
    assert result["deferred"] == ["two", "one"]
    assert result["escalated"] == []
    assert result["status"] == "complete"
