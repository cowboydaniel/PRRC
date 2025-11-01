"""Test configuration helpers."""

from __future__ import annotations

import importlib.machinery
import sys
import types
from pathlib import Path


class _Signal:
    def connect(self, *args, **kwargs):
        return None

    def disconnect(self, *args, **kwargs):  # pragma: no cover - convenience shim
        return None


def _ensure_pyside_stubs() -> None:
    if "PySide6" in sys.modules:
        return

    pyside6 = types.ModuleType("PySide6")
    pyside6.__spec__ = importlib.machinery.ModuleSpec("PySide6", loader=None)

    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.__spec__ = importlib.machinery.ModuleSpec("PySide6.QtCore", loader=None)

    class _Qt:
        class AlignmentFlag:
            AlignTop = object()

        class ScrollBarPolicy:
            ScrollBarAlwaysOff = object()

    class _QTimer:
        def __init__(self, *args, **kwargs):
            self.timeout = _Signal()

        def setInterval(self, *args, **kwargs):
            return None

        def start(self):
            return None

        def stop(self):
            return None

    qtcore.Qt = _Qt
    qtcore.QTimer = _QTimer

    qtgui = types.ModuleType("PySide6.QtGui")
    qtgui.__spec__ = importlib.machinery.ModuleSpec("PySide6.QtGui", loader=None)

    class _QAction:
        def __init__(self, *args, **kwargs):
            self.triggered = _Signal()

    class _QCloseEvent:  # pragma: no cover - container shim
        pass

    class _QFont:
        def __init__(self, *args, **kwargs):
            return None

        def setWeight(self, *args, **kwargs):
            return None

        def setLetterSpacing(self, *args, **kwargs):
            return None

    qtgui.QAction = _QAction
    qtgui.QCloseEvent = _QCloseEvent
    qtgui.QFont = _QFont

    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    qtwidgets.__spec__ = importlib.machinery.ModuleSpec("PySide6.QtWidgets", loader=None)

    class _Widget:
        def __init__(self, *args, **kwargs):
            return None

        def setObjectName(self, *args, **kwargs):
            return None

        def setContentsMargins(self, *args, **kwargs):
            return None

        def setSpacing(self, *args, **kwargs):
            return None

        def addWidget(self, *args, **kwargs):
            return None

        def addLayout(self, *args, **kwargs):
            return None

        def addStretch(self, *args, **kwargs):
            return None

        def setWordWrap(self, *args, **kwargs):
            return None

        def setMinimumHeight(self, *args, **kwargs):
            return None

        def setAlignment(self, *args, **kwargs):
            return None

        def setTabPosition(self, *args, **kwargs):
            return None

        def addTab(self, *args, **kwargs):
            return None

        def setWidgetResizable(self, *args, **kwargs):
            return None

        def setHorizontalScrollBarPolicy(self, *args, **kwargs):
            return None

        def setWidget(self, *args, **kwargs):
            return None

        def setSizePolicy(self, *args, **kwargs):
            return None

        def setText(self, *args, **kwargs):
            return None

        def setToolTip(self, *args, **kwargs):
            return None

        def hide(self, *args, **kwargs):
            return None

        def show(self, *args, **kwargs):
            return None

    class _Layout(_Widget):
        def addItem(self, *args, **kwargs):
            return None

    class _Button(_Widget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.clicked = _Signal()
            self.toggled = _Signal()

        def setCheckable(self, *args, **kwargs):
            return None

        def setAutoExclusive(self, *args, **kwargs):
            return None

    class _Dialog(_Widget):
        class DialogCode:
            Accepted = 1
            Rejected = 0

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._result = self.DialogCode.Rejected

        def exec(self):
            return self._result

        def accept(self):
            self._result = self.DialogCode.Accepted

        def reject(self):
            self._result = self.DialogCode.Rejected

        def setModal(self, *args, **kwargs):
            return None

        def setMinimumWidth(self, *args, **kwargs):
            return None

    class _DialogButtonBox(_Widget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.accepted = _Signal()
            self.rejected = _Signal()

    class _ListWidgetItem:
        def __init__(self, text=""):
            self._text = text
            self._data = {}

        def setData(self, role, value):
            self._data[role] = value

        def data(self, role):
            return self._data.get(role)

        def text(self):
            return self._text

    class _ListWidget(_Widget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._items: list[_ListWidgetItem] = []

        def addItem(self, item):
            self._items.append(item)

        def count(self):
            return len(self._items)

        def item(self, index):
            return self._items[index]

        def selectedItems(self):  # pragma: no cover - selection not modeled
            return []

        def takeItem(self, row):
            if 0 <= row < len(self._items):
                return self._items.pop(row)
            return None

    class _Application(_Widget):
        _instance = None

        def __init__(self, *args, **kwargs):
            type(self)._instance = self

        @classmethod
        def instance(cls):
            return cls._instance

        def exec(self):
            return 0

        def setPalette(self, *args, **kwargs):
            return None

    class _MenuBar(_Widget):
        def addAction(self, *args, **kwargs):
            return None

    class _MainWindow(_Widget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._menu = _MenuBar()

        def menuBar(self):
            return self._menu

        def setCentralWidget(self, *args, **kwargs):
            return None

        def resize(self, *args, **kwargs):
            return None

        def setStyleSheet(self, *args, **kwargs):
            return None

        def setWindowTitle(self, *args, **kwargs):
            return None

    class _QFileDialog:
        @staticmethod
        def getOpenFileName(*args, **kwargs):
            return ("", "")

    class _QMessageBox:
        @staticmethod
        def critical(*args, **kwargs):
            return None

    class _QSizePolicy:
        Expanding = object()
        Minimum = object()

        def __init__(self, *args, **kwargs):
            return None

        def setHorizontalStretch(self, *args, **kwargs):
            return None

    qtwidgets.QApplication = _Application
    qtwidgets.QCheckBox = _Button
    qtwidgets.QComboBox = _Widget
    qtwidgets.QFileDialog = _QFileDialog
    qtwidgets.QFrame = _Widget
    qtwidgets.QGroupBox = _Widget
    qtwidgets.QHBoxLayout = _Layout
    qtwidgets.QLabel = _Widget
    qtwidgets.QLineEdit = _Widget
    qtwidgets.QListWidget = _ListWidget
    qtwidgets.QListWidgetItem = _ListWidgetItem
    qtwidgets.QMainWindow = _MainWindow
    qtwidgets.QMessageBox = _QMessageBox
    qtwidgets.QPushButton = _Button
    qtwidgets.QScrollArea = _Widget
    qtwidgets.QSizePolicy = _QSizePolicy
    qtwidgets.QDialog = _Dialog
    qtwidgets.QDialogButtonBox = _DialogButtonBox
    qtwidgets.QStackedWidget = _Widget
    qtwidgets.QTabWidget = _Widget
    qtwidgets.QTextEdit = _Widget
    qtwidgets.QToolButton = _Button
    qtwidgets.QVBoxLayout = _Layout
    qtwidgets.QWidget = _Widget

    sys.modules["PySide6"] = pyside6
    sys.modules["PySide6.QtCore"] = qtcore
    sys.modules["PySide6.QtGui"] = qtgui
    sys.modules["PySide6.QtWidgets"] = qtwidgets

    pyside6.QtCore = qtcore
    pyside6.QtGui = qtgui
    pyside6.QtWidgets = qtwidgets


_ensure_pyside_stubs()


def pytest_configure() -> None:
    """Ensure the ``src`` directory is importable during tests."""

    src_dir = Path(__file__).resolve().parents[1] / "src"
    sys.path.insert(0, str(src_dir))
