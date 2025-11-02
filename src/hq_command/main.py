"""Executable entrypoint for demonstrating the HQ Command tasking engine."""
from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint

if __package__ in {None, ""}:  # pragma: no cover - runtime convenience for scripts
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from hq_command.tasking_engine import (  # type: ignore  # noqa: E402
    ResponderStatus,
    TaskingOrder,
    schedule_tasks_for_field_units,
)


def build_demo_inputs() -> tuple[list[TaskingOrder], list[ResponderStatus]]:
    """Construct a representative set of tasking inputs for the demo runner."""

    tasks = [
        TaskingOrder(
            task_id="med-evac",  # urgent evacuation requiring multiple units
            priority=5,
            capabilities_required=frozenset({"medic", "driver"}),
            min_units=2,
            max_units=2,
            location="ao-west",
            metadata={"category": "medical", "details": "Evacuate injured unit"},
        ),
        TaskingOrder(
            task_id="sensor-repair",
            priority=3,
            capabilities_required=frozenset({"engineer"}),
            location="ao-west",
            metadata={"category": "maintenance"},
        ),
        TaskingOrder(
            task_id="supply-run",
            priority=2,
            capabilities_required=frozenset({"driver"}),
            location="ao-east",
            metadata={"category": "logistics"},
        ),
    ]

    responders = [
        ResponderStatus(
            unit_id="alpha-1",
            capabilities=frozenset({"medic", "driver"}),
            location="ao-west",
            max_concurrent_tasks=1,
        ),
        ResponderStatus(
            unit_id="bravo-2",
            capabilities=frozenset({"medic"}),
            location="ao-west",
            max_concurrent_tasks=1,
        ),
        ResponderStatus(
            unit_id="charlie-5",
            capabilities=frozenset({"engineer"}),
            location="ao-west",
            max_concurrent_tasks=1,
        ),
        ResponderStatus(
            unit_id="delta-7",
            capabilities=frozenset({"driver"}),
            location="ao-east",
            status="busy",
            max_concurrent_tasks=1,
            current_tasks=["long-haul"],
        ),
    ]

    return tasks, responders


def main() -> None:
    """Execute the demo runner when invoked as a script."""

    tasks, responders = build_demo_inputs()
    result = schedule_tasks_for_field_units(tasks, responders)

    print("HQ Command Tasking Engine Demo")
    print("===============================")
    print("Assignments:")
    for assignment in result["assignments"]:
        print(
            f"  - Task {assignment['task_id']} -> Unit {assignment['unit_id']} "
            f"(score {assignment['score']})"
        )

    if result["deferred"]:
        print("Deferred tasks:")
        for task_id in result["deferred"]:
            print(f"  - {task_id}")

    if result["escalated"]:
        print("Escalated tasks:")
        for task_id in result["escalated"]:
            print(f"  - {task_id}")

    print("\nAudit metadata:")
    pprint(result["audit"])


if __name__ == "__main__":
    main()
