"""HQ Command GUI package."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Sequence

try:  # pragma: no cover - import guard for headless environments
    from .controller import HQCommandController
    from .main_window import HQMainWindow
    from .qt_compat import QtCore, QtWidgets
except ImportError:  # pragma: no cover - PySide6 missing
    HQCommandController = None  # type: ignore[assignment]
    HQMainWindow = None  # type: ignore[assignment]
    QtCore = None  # type: ignore[assignment]
    QtWidgets = None  # type: ignore[assignment]

# Integration imports
try:
    from integration import (
        create_hq_coordinator,
        HQIntegration,
        setup_bridge_components,
    )
    INTEGRATION_AVAILABLE = True
except ImportError:
    INTEGRATION_AVAILABLE = False

logger = logging.getLogger(__name__)

__all__ = ["HQCommandController", "HQMainWindow", "main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the HQ Command GUI console")
    parser.add_argument("--config", type=Path, default=Path("samples/hq_command/production_inputs.json"))
    parser.add_argument(
        "--refresh-interval",
        type=float,
        default=5.0,
        help="Seconds between background refreshes from the configuration file",
    )
    return parser


def _connect_timer(timer: Any, callback: callable) -> None:
    timeout_attr = getattr(timer, "timeout", None)
    if timeout_attr is None:
        return
    connect = getattr(timeout_attr, "connect", None)
    if callable(connect):
        connect(callback)
    elif callable(timeout_attr):
        timeout_attr(callback)


def _start_timer(timer: Any) -> None:
    starter = getattr(timer, "start", None)
    if callable(starter):
        starter()


def main(argv: Sequence[str] | None = None) -> int:
    if HQCommandController is None or HQMainWindow is None or QtWidgets is None or QtCore is None:
        raise RuntimeError("PySide6 is required to launch the HQ Command GUI.")

    parser = build_parser()
    args = parser.parse_args(argv)

    config_path = args.config
    controller = HQCommandController()
    controller.load_from_file(config_path)

    # Initialize integration layer for live device tracking
    hq_integration = None
    if INTEGRATION_AVAILABLE:
        try:
            router, audit_log = setup_bridge_components()
            coordinator = create_hq_coordinator(router, audit_log, hq_id="hq_command")
            hq_integration = HQIntegration(coordinator)

            # Track active devices separately from responders
            active_devices = {}

            logger.info("HQ Integration initialized - live device tracking enabled")

        except Exception as e:
            logger.warning(f"Failed to initialize integration: {e}")
            hq_integration = None
    else:
        logger.warning("Integration layer not available - device tracking disabled")

    qt_argv = list(sys.argv if argv is None else [sys.argv[0], *argv])
    app = QtWidgets.QApplication(qt_argv)
    window = HQMainWindow(controller)

    # Store active_devices reference on window for access during callbacks
    if hq_integration:
        window._active_devices = active_devices
        # Update callback to refresh the window immediately
        def handle_status_update_with_refresh(payload: dict) -> None:
            """Update active devices and refresh window"""
            try:
                unit_id = payload.get("unit_id")
                if not unit_id:
                    return

                # Update active devices dictionary
                active_devices[unit_id] = {
                    "status": payload.get("status", "available"),
                    "capabilities": payload.get("capabilities", []),
                    "max_concurrent_tasks": payload.get("capacity", 1),
                    "current_task_count": payload.get("current_task_count", 0),
                    "fatigue_level": payload.get("fatigue_level", 0.0),
                }

                logger.info(f"Device status updated: {unit_id} - {payload.get('status', 'available')}")

                # Update telemetry pane with active devices
                if hasattr(window, 'telemetry_pane'):
                    window.telemetry_pane.update_active_devices(active_devices)

            except Exception as e:
                logger.error(f"Error handling device status update: {e}", exc_info=True)

        hq_integration.on_status_update_received(handle_status_update_with_refresh)
    else:
        window._active_devices = {}

    if hasattr(window, "showMaximized"):
        window.showMaximized()
    elif hasattr(window, "show"):
        window.show()

    timer = QtCore.QTimer()
    timer.setInterval(int(args.refresh_interval * 1000))

    def _refresh() -> None:
        controller.load_from_file(config_path)
        window.refresh()
        # Also update active devices display
        if hasattr(window, 'telemetry_pane') and hasattr(window, '_active_devices'):
            window.telemetry_pane.update_active_devices(window._active_devices)

    _connect_timer(timer, _refresh)
    _start_timer(timer)

    exec_method = getattr(app, "exec", None)
    if callable(exec_method):
        return exec_method()
    return app.exec_()


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())
