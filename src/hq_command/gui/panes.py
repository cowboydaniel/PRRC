"""Widget definitions for HQ Command panes."""
from __future__ import annotations

from typing import Optional

from .controller import RosterListModel, TaskQueueModel, TelemetrySummaryModel
from .qt_compat import QT_AVAILABLE, QtWidgets


class _BasePane(QtWidgets.QWidget):
    """Light-weight widget that binds a list model to a list view."""

    def __init__(self, title: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._title = title
        self._model = None

        if QT_AVAILABLE:
            layout = QtWidgets.QVBoxLayout(self)
            self._title_label = QtWidgets.QLabel(title)
            layout.addWidget(self._title_label)
            self._view = QtWidgets.QListView()
            layout.addWidget(self._view)
        else:
            self._title_label = None
            self._view = None

    def set_model(self, model: RosterListModel | TaskQueueModel | TelemetrySummaryModel) -> None:
        self._model = model
        if QT_AVAILABLE and self._view is not None:
            self._view.setModel(model)

    @property
    def model(self) -> RosterListModel | TaskQueueModel | TelemetrySummaryModel | None:
        return self._model

    @property
    def title(self) -> str:
        return self._title


class RosterPane(_BasePane):
    def __init__(self, model: RosterListModel, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__("Responder Roster", parent)
        self.set_model(model)


class TaskQueuePane(_BasePane):
    def __init__(self, model: TaskQueueModel, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__("Task Queue", parent)
        self.set_model(model)


class TelemetryPane(_BasePane):
    def __init__(self, model: TelemetrySummaryModel, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__("Telemetry Summary", parent)
        self.set_model(model)
