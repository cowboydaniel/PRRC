"""Main window definition for the HQ Command GUI."""
from __future__ import annotations

from typing import Optional

from .controller import HQCommandController
from .panes import RosterPane, TaskQueuePane, TelemetryPane
from .qt_compat import QT_AVAILABLE, QtWidgets


class HQMainWindow(QtWidgets.QMainWindow):
    """Container window that hosts the roster, task queue, and telemetry panes."""

    def __init__(self, controller: HQCommandController, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.controller = controller

        if QT_AVAILABLE:
            self.setWindowTitle("HQ Command Console")

        central = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(central)

        self.roster_pane = RosterPane(controller.roster_model, central)
        self.task_pane = TaskQueuePane(controller.task_queue_model, central)
        self.telemetry_pane = TelemetryPane(controller.telemetry_model, central)

        layout.addWidget(self.roster_pane)
        layout.addWidget(self.task_pane)
        layout.addWidget(self.telemetry_pane)

        if QT_AVAILABLE:
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(8)

        self.setCentralWidget(central)

    def refresh(self) -> None:
        """Rebind models in case the controller replaced them."""

        self.roster_pane.set_model(self.controller.roster_model)
        self.task_pane.set_model(self.controller.task_queue_model)
        self.telemetry_pane.set_model(self.controller.telemetry_model)
