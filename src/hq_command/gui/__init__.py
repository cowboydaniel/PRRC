"""HQ Command GUI package."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .controller import HQCommandController
from .main_window import HQMainWindow
from .qt_compat import QT_AVAILABLE, QtCore, QtWidgets

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


def _cli_dump(controller: HQCommandController) -> None:
    snapshot = {
        "roster": controller.roster_model.items(),
        "task_queue": controller.task_queue_model.items(),
        "telemetry": controller.telemetry_model.items(),
    }
    json.dump(snapshot, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config_path = args.config
    controller = HQCommandController()
    controller.load_from_file(config_path)

    if not QT_AVAILABLE:
        sys.stderr.write("Qt bindings are not installed; running in headless snapshot mode.\n")
        _cli_dump(controller)
        return 0

    qt_argv = list(sys.argv if argv is None else [sys.argv[0], *argv])
    app = QtWidgets.QApplication(qt_argv)
    window = HQMainWindow(controller)
    if hasattr(window, "show"):
        window.show()

    timer = QtCore.QTimer()
    timer.setInterval(int(args.refresh_interval * 1000))

    def _refresh() -> None:
        controller.load_from_file(config_path)
        window.refresh()

    _connect_timer(timer, _refresh)
    _start_timer(timer)

    return app.exec_()


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())
