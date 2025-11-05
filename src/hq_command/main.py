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

# Integration imports
try:
    from integration import (
        create_hq_coordinator,
        HQIntegration,
        integrate_with_tasking_engine,
        setup_bridge_components,
    )
    INTEGRATION_AVAILABLE = True
except ImportError:
    INTEGRATION_AVAILABLE = False


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


def setup_integration(hq_id: str = "hq_command") -> HQIntegration | None:
    """
    Set up HQ Command integration with Bridge and FieldOps

    Args:
        hq_id: ID of this HQ Command instance

    Returns:
        HQIntegration instance if available, None otherwise
    """
    if not INTEGRATION_AVAILABLE:
        return None

    try:
        # Configure Bridge components
        router, audit_log = setup_bridge_components()

        # Create HQ coordinator
        coordinator = create_hq_coordinator(router, audit_log, hq_id=hq_id)

        # Create HQ integration
        hq = HQIntegration(coordinator)

        # Wire integration to tasking engine
        import hq_command.tasking_engine as tasking_module
        integrate_with_tasking_engine(hq, tasking_module)

        return hq

    except Exception as e:
        print(f"Warning: Failed to set up integration: {e}", file=sys.stderr)
        return None


def run_production_mode(
    config_path: Path,
    *,
    stdout: IO[str] | None = None,
    stderr: IO[str] | None = None,
    send_to_field: bool = False,
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

    # If requested, send tasks to field units via Bridge
    if send_to_field and INTEGRATION_AVAILABLE:
        hq = setup_integration()
        if hq:
            import hq_command.tasking_engine as tasking_module
            if hasattr(tasking_module, 'send_assignments_to_field'):
                out_stream.write("\nSending task assignments to field units...\n")
                send_results = tasking_module.send_assignments_to_field(result)
                out_stream.write(f"Sent to {sum(send_results.values())} units successfully\n")

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
