"""Entry point for launching the FieldOps GUI demo."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

if __package__ in {None, ""}:
    # Allow running "python src/fieldops/main.py" by ensuring the project
    # source directory is importable for absolute package imports.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from fieldops.gui.app import launch_app
else:  # pragma: no cover - exercised when imported as a package module.
    from .gui.app import launch_app

# Integration imports
try:
    from integration import (
        create_fieldops_coordinator,
        FieldOpsIntegration,
        create_bridge_sync_adapter,
        setup_bridge_components,
    )
    INTEGRATION_AVAILABLE = True
except ImportError:
    INTEGRATION_AVAILABLE = False


def setup_integration(device_id: str = "fieldops_001") -> FieldOpsIntegration | None:
    """
    Set up FieldOps integration with Bridge and HQ Command

    Args:
        device_id: ID of this FieldOps device

    Returns:
        FieldOpsIntegration instance if available, None otherwise
    """
    if not INTEGRATION_AVAILABLE:
        return None

    try:
        # Configure Bridge components
        router, audit_log = setup_bridge_components()

        # Create FieldOps coordinator
        coordinator = create_fieldops_coordinator(router, audit_log, device_id=device_id)

        # Create FieldOps integration
        fieldops = FieldOpsIntegration(coordinator)

        return fieldops

    except Exception as e:
        print(f"Warning: Failed to set up integration: {e}", file=sys.stderr)
        return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the FieldOps GUI")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Start the application with demo data and sample mission package",
    )
    parser.add_argument(
        "--device-id",
        type=str,
        default="fieldops_001",
        help="Device ID for this FieldOps instance",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Launch the FieldOps Field GUI."""
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    # Set up integration if available
    if INTEGRATION_AVAILABLE:
        integration = setup_integration(device_id=args.device_id)
        if integration:
            print(f"FieldOps integration enabled (device: {args.device_id})")

            # Send initial status update to register with HQ Command
            integration.send_status_update_to_hq(
                status="available",
                capabilities=["basic_response", "transport", "communication"],
                max_concurrent_tasks=3,
                current_task_count=0,
                fatigue_level=0.0,
            )
            print(f"Sent initial status update to HQ Command")

    return launch_app(demo_mode=args.demo)


if __name__ == "__main__":
    raise SystemExit(main())
