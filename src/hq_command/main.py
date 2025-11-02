"""Executable entrypoint for the HQ Command tasking engine."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import IO, Any, Sequence

if __package__ in {None, ""}:  # pragma: no cover - runtime convenience for scripts
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from hq_command.tasking_engine import (  # type: ignore  # noqa: E402
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




def _build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for the HQ Command tasking engine."""

    parser = argparse.ArgumentParser(
        description="Launch the HQ Command GUI console with optional configuration",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=_default_config_path(),
        help=(
            "Path to a JSON file containing 'tasks' and 'responders' payloads. "
            "Used to seed the GUI roster, queue, and telemetry panes."
        ),
    )
    parser.add_argument(
        "--refresh-interval",
        type=float,
        default=5.0,
        help="Seconds between GUI refreshes while reloading configuration data",
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




def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and dispatch to the selected execution mode."""

    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    from hq_command import gui

    gui_argv = ["--config", str(args.config), "--refresh-interval", str(args.refresh_interval)]
    return gui.main(gui_argv)


if __name__ == "__main__":
    raise SystemExit(main())
