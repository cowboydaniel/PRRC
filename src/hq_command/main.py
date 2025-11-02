"""Executable entrypoint for the HQ Command tasking engine."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from pprint import pprint
from typing import IO, Any, Sequence

if __package__ in {None, ""}:  # pragma: no cover - runtime convenience for scripts
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from hq_command.tasking_engine import (  # type: ignore  # noqa: E402
    ResponderStatus,
    TaskingOrder,
    schedule_tasks_for_field_units,
)


def _default_config_path() -> Path:
    """Return the default JSON config containing production task inputs."""

    return (
        Path(__file__).resolve().parents[2]
        / "samples"
        / "hq_command"
        / "production_inputs.json"
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


def _build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for the HQ Command tasking engine."""

    parser = argparse.ArgumentParser(
        description="Run the HQ Command tasking engine in production or demo mode"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run with canned demo data and human-readable output",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the HQ Command GUI console instead of writing CLI output",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=_default_config_path(),
        help=(
            "Path to a JSON file containing 'tasks' and 'responders' payloads. "
            "Used when running in production mode."
        ),
    )
    parser.add_argument(
        "--refresh-interval",
        type=float,
        default=5.0,
        help="Seconds between GUI refreshes when running in --gui mode",
    )
    return parser


def run_production_mode(
    config_path: Path,
    *,
    stdout: IO[str] | None = None,
    stderr: IO[str] | None = None,
) -> int:
    """Execute the scheduler using structured JSON inputs for automation."""

    out_stream = stdout or sys.stdout
    err_stream = stderr or sys.stderr

    try:
        payload = json.loads(config_path.read_text())
    except FileNotFoundError:
        err_stream.write(f"Config file not found: {config_path}\n")
        return 1
    except json.JSONDecodeError as exc:
        err_stream.write(f"Invalid JSON in config file {config_path}: {exc}\n")
        return 1

    tasks: Sequence[Any] = payload.get("tasks", [])
    responders: Sequence[Any] = payload.get("responders", [])

    result = schedule_tasks_for_field_units(tasks, responders)
    json.dump(result, out_stream, indent=2, sort_keys=True)
    out_stream.write("\n")
    return 0


def run_demo_mode(*, stdout: IO[str] | None = None) -> None:
    """Execute the interactive demo showcasing scheduling output."""

    out_stream = stdout or sys.stdout
    tasks, responders = build_demo_inputs()
    result = schedule_tasks_for_field_units(tasks, responders)

    print("HQ Command Tasking Engine Demo", file=out_stream)
    print("===============================", file=out_stream)
    print("Assignments:", file=out_stream)
    for assignment in result["assignments"]:
        print(
            f"  - Task {assignment['task_id']} -> Unit {assignment['unit_id']} "
            f"(score {assignment['score']})",
            file=out_stream,
        )

    if result["deferred"]:
        print("Deferred tasks:", file=out_stream)
        for task_id in result["deferred"]:
            print(f"  - {task_id}", file=out_stream)

    if result["escalated"]:
        print("Escalated tasks:", file=out_stream)
        for task_id in result["escalated"]:
            print(f"  - {task_id}", file=out_stream)

    print("\nAudit metadata:", file=out_stream)
    pprint(result["audit"], stream=out_stream)


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and dispatch to the selected execution mode."""

    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.demo:
        run_demo_mode()
        return 0

    if args.gui:
        from hq_command import gui

        gui_argv = ["--config", str(args.config), "--refresh-interval", str(args.refresh_interval)]
        return gui.main(gui_argv)

    return run_production_mode(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
