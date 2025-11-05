"""Command-line entrypoint for the PRRC OS Suite prototypes.

This CLI wires together placeholder operations from FieldOps, HQ Command, and
Bridge to outline the eventual operator experience.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from fieldops import (
    load_mission_package,
    collect_telemetry_snapshot,
    plan_touchscreen_calibration,
)
from hq_command import summarize_field_telemetry
from bridge import route_message_to_partner

# Integration imports
try:
    from integration import (
        create_hq_coordinator,
        create_fieldops_coordinator,
        HQIntegration,
        FieldOpsIntegration,
        setup_bridge_components,
    )
    INTEGRATION_AVAILABLE = True
except ImportError:
    INTEGRATION_AVAILABLE = False


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


def integrated_task_send_command(config: str, unit_id: str | None) -> None:
    """Handle the `send-tasks` command (integrated workflow)."""
    if not INTEGRATION_AVAILABLE:
        print("Error: Integration module not available")
        return

    # Load task configuration
    try:
        with open(config, "r") as f:
            payload = json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return

    # Schedule tasks using HQ Command
    from hq_command.tasking_engine import schedule_tasks_for_field_units

    tasks = payload.get("tasks", [])
    responders = payload.get("responders", [])
    result = schedule_tasks_for_field_units(tasks, responders)

    print("Task scheduling result:")
    print(f"  Assignments: {len(result.get('assignments', []))}")
    print(f"  Unassigned: {len(result.get('unassigned', []))}")

    # Set up integration and send to field
    router, audit_log = setup_bridge_components()
    coordinator = create_hq_coordinator(router, audit_log, hq_id="hq_cli")
    hq = HQIntegration(coordinator)

    # Prepare unit assignments
    unit_tasks = {}
    for assignment in result.get("assignments", []):
        for assigned_unit in assignment.get("assigned_units", []):
            # Filter by unit_id if specified
            if unit_id and assigned_unit != unit_id:
                continue

            if assigned_unit not in unit_tasks:
                unit_tasks[assigned_unit] = []

            task_dict = {
                "task_id": assignment["task_id"],
                "priority": assignment["priority"],
                "capabilities_required": assignment["capabilities_required"],
                "location": assignment.get("location"),
            }
            unit_tasks[assigned_unit].append(task_dict)

    # Send to units
    print(f"\nSending tasks to {len(unit_tasks)} field unit(s)...")
    send_results = hq.send_tasks_to_multiple_units(
        assignments=unit_tasks,
        operator_id=payload.get("operator_id", "cli_operator"),
    )

    for unit, success in send_results.items():
        status = "✓" if success else "✗"
        print(f"  {status} {unit}: {len(unit_tasks[unit])} tasks")

    # Show statistics
    stats = coordinator.get_statistics()
    print(f"\nCoordinator statistics:")
    print(f"  Sent: {stats['sent']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Pending retry: {stats['pending_retry']}")


def integrated_telemetry_send_command(device_id: str) -> None:
    """Handle the `send-telemetry` command (integrated workflow)."""
    if not INTEGRATION_AVAILABLE:
        print("Error: Integration module not available")
        return

    # Collect telemetry
    telemetry = collect_telemetry_snapshot()

    # Serialize telemetry
    telemetry_dict = {
        "status": telemetry.status,
        "collected_at": telemetry.collected_at.isoformat(),
        "metrics": {
            "sensors": [
                {
                    "id": s.id,
                    "type": s.type,
                    "value": s.value,
                    "unit": s.unit,
                    "timestamp": s.timestamp.isoformat(),
                }
                for s in telemetry.metrics.sensors
            ],
            "events": telemetry.metrics.events,
            "queues": telemetry.metrics.queues,
        },
    }

    # Set up integration
    router, audit_log = setup_bridge_components()
    coordinator = create_fieldops_coordinator(router, audit_log, device_id=device_id)
    fieldops = FieldOpsIntegration(coordinator)

    # Send telemetry to HQ
    print(f"Sending telemetry from {device_id} to HQ...")
    success = fieldops.send_telemetry_to_hq(telemetry_dict)

    if success:
        print("✓ Telemetry sent successfully")
    else:
        print("✗ Failed to send telemetry")

    # Show statistics
    stats = coordinator.get_statistics()
    print(f"\nCoordinator statistics:")
    print(f"  Sent: {stats['sent']}")
    print(f"  Failed: {stats['failed']}")


def integration_demo_command() -> None:
    """Handle the `integration-demo` command (end-to-end demonstration)."""
    if not INTEGRATION_AVAILABLE:
        print("Error: Integration module not available")
        return

    print("=== PRRC Integration Demo ===\n")

    # Set up components
    router, audit_log = setup_bridge_components()

    hq_coord = create_hq_coordinator(router, audit_log, hq_id="hq_demo")
    hq = HQIntegration(hq_coord)

    fo_coord = create_fieldops_coordinator(router, audit_log, device_id="fieldops_demo")
    fieldops = FieldOpsIntegration(fo_coord)

    # Simulate bidirectional communication
    print("1. HQ Command sends task assignment to FieldOps...")
    tasks = [
        {
            "task_id": "demo-task-1",
            "priority": 1,
            "capabilities_required": ["hazmat", "medical"],
            "location": "sector-alpha",
        }
    ]

    hq.send_tasks_to_field_unit(
        unit_id="fieldops_demo",
        tasks=tasks,
        operator_id="demo_operator",
    )
    print("   ✓ Task assignment sent\n")

    print("2. FieldOps sends telemetry to HQ...")
    telemetry = {
        "status": "operational",
        "collected_at": "2025-01-01T12:00:00",
        "metrics": {"sensors": [], "events": [], "queues": []},
    }
    fieldops.send_telemetry_to_hq(telemetry)
    print("   ✓ Telemetry sent\n")

    print("3. FieldOps syncs operations to HQ...")
    operations = [
        {
            "id": "op-1",
            "type": "task_complete",
            "payload": {"task_id": "demo-task-1"},
            "created_at": "2025-01-01T13:00:00",
        }
    ]
    fieldops.sync_operations_to_hq(operations)
    print("   ✓ Operations synced\n")

    # Show statistics
    print("HQ Coordinator Statistics:")
    hq_stats = hq_coord.get_statistics()
    for key, value in hq_stats.items():
        print(f"  {key}: {value}")

    print("\nFieldOps Coordinator Statistics:")
    fo_stats = fo_coord.get_statistics()
    for key, value in fo_stats.items():
        print(f"  {key}: {value}")

    print("\n=== Demo Complete ===")
    print("\nThe integration layer successfully:")
    print("  ✓ Routed messages through the Bridge")
    print("  ✓ Logged all communications for compliance")
    print("  ✓ Connected HQ Command and FieldOps")


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

    # Integrated workflow commands
    if INTEGRATION_AVAILABLE:
        send_tasks_parser = subparsers.add_parser(
            "send-tasks",
            help="Send task assignments from HQ to FieldOps units (integrated)",
        )
        send_tasks_parser.add_argument(
            "config",
            help="Path to JSON config with tasks and responders",
        )
        send_tasks_parser.add_argument(
            "--unit-id",
            help="Optional: send only to specific unit ID",
        )

        send_telemetry_parser = subparsers.add_parser(
            "send-telemetry",
            help="Send telemetry from FieldOps to HQ (integrated)",
        )
        send_telemetry_parser.add_argument(
            "--device-id",
            default="fieldops_cli",
            help="Device ID for this FieldOps instance",
        )

        subparsers.add_parser(
            "integration-demo",
            help="Run end-to-end integration demonstration",
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

    # Add integrated commands if available
    if INTEGRATION_AVAILABLE:
        command_map.update({
            "send-tasks": lambda: integrated_task_send_command(args.config, args.unit_id),
            "send-telemetry": lambda: integrated_telemetry_send_command(args.device_id),
            "integration-demo": integration_demo_command,
        })

    handler = command_map.get(args.command)
    if handler:
        handler()
    else:
        print(f"Error: Unknown command '{args.command}'")


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint used by the project packaging configuration."""
    parser = build_parser()
    args = parser.parse_args(argv)
    dispatch(args)


if __name__ == "__main__":
    main()
