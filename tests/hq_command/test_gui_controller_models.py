from __future__ import annotations

from pathlib import Path

from hq_command.gui import HQCommandController
from hq_command.main import build_demo_inputs


def test_controller_transforms_demo_inputs() -> None:
    tasks, responders = build_demo_inputs()
    controller = HQCommandController()
    controller.load_from_payload({"tasks": tasks, "responders": responders, "telemetry": {}})

    roster = {row["unit_id"]: row for row in controller.roster_model.items()}
    assert "alpha-1" in roster
    assert "bravo-2" in roster
    assert roster["alpha-1"]["status"] == "available"
    assert "med-evac" in roster["alpha-1"]["current_tasks"]
    assert roster["alpha-1"]["available_capacity"] == 0

    task_rows = {row["task_id"]: row for row in controller.task_queue_model.items()}
    assert task_rows["med-evac"]["status"] == "escalated"
    assert task_rows["med-evac"]["assigned_units"] == ["alpha-1"]
    assert all(score is None or isinstance(score, int) for score in task_rows["med-evac"]["scores"])

    telemetry_rows = {row["metric"]: row["value"] for row in controller.telemetry_model.items()}
    assert "overall_readiness" in telemetry_rows


def test_manual_assignment_is_reflected_in_models(tmp_path: Path) -> None:
    controller = HQCommandController()
    payload = {
        "tasks": [
            {
                "task_id": "logistics",
                "priority": 1,
                "capabilities_required": ["driver"],
            }
        ],
        "responders": [
            {
                "unit_id": "delta-1",
                "capabilities": ["driver"],
                "status": "available",
                "max_concurrent_tasks": 2,
            },
            {
                "unit_id": "echo-3",
                "capabilities": ["driver"],
                "status": "available",
                "max_concurrent_tasks": 1,
            },
        ],
        "telemetry": {},
    }

    controller.load_from_payload(payload)
    controller.apply_manual_assignment("logistics", "echo-3")

    roster = {row["unit_id"]: row for row in controller.roster_model.items()}
    assert "logistics" in roster["echo-3"]["current_tasks"]

    task_rows = {row["task_id"]: row for row in controller.task_queue_model.items()}
    assert task_rows["logistics"]["status"] == "assigned"
    assert "echo-3" in task_rows["logistics"]["assigned_units"]

    # Persist payload to disk and ensure the controller reloads consistently.
    payload_path = tmp_path / "payload.json"
    payload_path.write_text("{}")
    controller.load_from_file(payload_path)
    assert controller.roster_model.items() == []
