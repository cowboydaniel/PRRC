"""Command-line entrypoint for the PRRC OS Suite prototypes.

This CLI wires together placeholder operations from FieldOps, HQ Command, and
Bridge to outline the eventual operator experience.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from fieldops import (
    load_mission_package,
    collect_telemetry_snapshot,
    plan_touchscreen_calibration,
)
from hq_command import summarize_field_telemetry
from bridge import route_message_to_partner


def load_mission_command(package: str) -> None:
    """Handle the `load-mission` command."""
    mission_data = load_mission_package(Path(package))
    # Inline logging provides a template for future structured output handlers.
    print("Mission package summary:")
    for key, value in mission_data.items():
        print(f"  {key}: {value}")


def status_command() -> None:
    """Handle the `status` command."""
    telemetry = collect_telemetry_snapshot()
    summary = summarize_field_telemetry(telemetry)
    print("HQ Command status report:")
    for key, value in summary.items():
        print(f"  {key}: {value}")


def send_bridge_message_command(payload: str) -> None:
    """Handle the `bridge-send` command."""
    # The payload is deliberately simple to emphasize wiring, not transport.
    result = route_message_to_partner({"payload": payload})
    print("Bridge routing result:")
    for key, value in result.items():
        print(f"  {key}: {value}")


def calibrate_touchscreen_command(profile: str | None) -> None:
    """Handle the `calibrate-touchscreen` command."""
    profile_path = Path(profile) if profile else None
    plan = plan_touchscreen_calibration(profile_path)
    print("Touchscreen calibration plan:")
    for key, value in plan.items():
        print(f"  {key}: {value}")


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level CLI parser."""
    parser = argparse.ArgumentParser(description="PRRC OS Suite CLI prototype")
    subparsers = parser.add_subparsers(dest="command", required=True)

    load_parser = subparsers.add_parser(
        "load-mission",
        help="Load a mission package for FieldOps devices",
    )
    load_parser.add_argument(
        "package",
        help="Path to the mission package archive or manifest",
    )

    subparsers.add_parser(
        "status",
        help="View summarized system status",
    )

    bridge_parser = subparsers.add_parser(
        "bridge-send",
        help="Send a message through the Bridge integration layer",
    )
    bridge_parser.add_argument(
        "payload",
        help="Message contents to simulate forwarding",
    )

    calibrate_parser = subparsers.add_parser(
        "calibrate-touchscreen",
        help="Plan a Dell Rugged Extreme touchscreen calibration routine",
    )
    calibrate_parser.add_argument(
        "--profile",
        help="Optional calibration profile to reuse",
    )

    return parser


def dispatch(args: argparse.Namespace) -> None:
    """Dispatch the parsed arguments to the correct handler."""
    command_map = {
        "load-mission": lambda: load_mission_command(args.package),
        "status": status_command,
        "bridge-send": lambda: send_bridge_message_command(args.payload),
        "calibrate-touchscreen": lambda: calibrate_touchscreen_command(args.profile),
    }
    handler = command_map[args.command]
    handler()


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint used by the project packaging configuration."""
    parser = build_parser()
    args = parser.parse_args(argv)
    dispatch(args)


if __name__ == "__main__":
    main()
