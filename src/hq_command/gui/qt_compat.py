"""Compatibility helpers for optional Qt bindings.

The repository does not ship with Qt bindings, so this module provides a very
small compatibility layer that mimics the interfaces used by the GUI package.
When a supported Qt binding (such as PySide6 or PyQt5) is installed it will be
imported and the real classes exposed.  When bindings are unavailable a
light-weight shim is
provided so the controller logic can still be exercised in unit tests without a
GUI event loop.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from types import ModuleType
from typing import Any, Iterable, List, Optional, Sequence

SUPPORTED_QT_BINDINGS: Sequence[str] = (
    "PySide6",
    "PyQt6",
    "PySide2",
    "PyQt5",
)

_REQUIRED_CORE_ATTRS = ("QAbstractListModel", "QModelIndex", "QObject", "QTimer")
_REQUIRED_WIDGET_ATTRS = (
    "QApplication",
    "QLabel",
    "QListView",
    "QMainWindow",
    "QVBoxLayout",
    "QWidget",
)


def _attempt_import(binding: str) -> tuple[ModuleType, ModuleType] | None:
    try:
        core_mod = import_module(f"{binding}.QtCore")
        widgets_mod = import_module(f"{binding}.QtWidgets")
    except Exception:  # pragma: no cover - binding not available
        return None

    for attr in _REQUIRED_CORE_ATTRS:
        if not hasattr(core_mod, attr):
            return None
    for attr in _REQUIRED_WIDGET_ATTRS:
        if not hasattr(widgets_mod, attr):
            return None

    return core_mod, widgets_mod


QT_API: str | None = None

for _binding in SUPPORTED_QT_BINDINGS:  # pragma: no cover - executed when bindings exist
    _modules = _attempt_import(_binding)
    if _modules is not None:
        QtCore, QtWidgets = _modules
        QT_API = _binding
        QT_AVAILABLE = True
        break
else:  # pragma: no cover - fall back to shim used in tests
    QT_AVAILABLE = False

    class _QtNamespace:
        DisplayRole = 0
        EditRole = 2
        UserRole = 32

    class _QModelIndex:
        def __init__(self, row: int = -1) -> None:
            self._row = row

        def row(self) -> int:
            return self._row

    class _QObject:
        pass

    class _QAbstractListModel:
        """A very small subset of the Qt list model API."""

        def __init__(self, parent: Optional[_QObject] = None) -> None:
            self._parent = parent
            self._items: List[Any] = []

        # Qt normally passes QModelIndex instances to rowCount/data; the shim
        # keeps the same signature for easier substitution.
        def rowCount(self, parent: Optional[_QModelIndex] = None) -> int:  # noqa: D401 - Qt signature
            return len(self._items)

        def data(self, index: _QModelIndex, role: int = 0) -> Any:  # noqa: D401 - Qt signature
            if not 0 <= index.row() < len(self._items):
                return None
            if role in (_QtNamespace.DisplayRole, _QtNamespace.EditRole, _QtNamespace.UserRole):
                return self._items[index.row()]
            return None

        # Helpers that mimic the methods our models expect to call.
        def _set_items(self, items: Iterable[Any]) -> None:
            self._items = list(items)

        def _get_items(self) -> List[Any]:
            return list(self._items)

    class _QWidget:
        def __init__(self, parent: Optional["_QWidget"] = None) -> None:
            self._parent = parent

    class _QMainWindow(_QWidget):
        def __init__(self, parent: Optional[_QWidget] = None) -> None:
            super().__init__(parent)
            self._central_widget: Optional[_QWidget] = None

        def setCentralWidget(self, widget: _QWidget) -> None:
            self._central_widget = widget

    class _QApplication:
        def __init__(self, argv: List[str]) -> None:
            self.argv = argv

        def exec_(self) -> int:
            return 0

    class _QVBoxLayout:
        def __init__(self, parent: Optional[_QWidget] = None) -> None:
            self._parent = parent
            self._widgets: List[_QWidget] = []

        def addWidget(self, widget: _QWidget) -> None:
            self._widgets.append(widget)

    class _QListView(_QWidget):
        def __init__(self, parent: Optional[_QWidget] = None) -> None:
            super().__init__(parent)
            self._model: Optional[_QAbstractListModel] = None

        def setModel(self, model: _QAbstractListModel) -> None:
            self._model = model

    class _QLabel(_QWidget):
        def __init__(self, text: str = "", parent: Optional[_QWidget] = None) -> None:
            super().__init__(parent)
            self.text = text

        def setText(self, text: str) -> None:
            self.text = text

    class _QTimer:
        def __init__(self) -> None:
            self._interval = 0
            self._callback: Optional[callable] = None

        def setInterval(self, msec: int) -> None:
            self._interval = msec

        def timeout(self, callback: callable) -> None:
            self._callback = callback

        # The real Qt API exposes `timeout` as a signal.  The shim simply
        # provides a callable attribute that tests can trigger manually.
        def trigger(self) -> None:
            if self._callback:
                self._callback()

        def start(self) -> None:
            return None

    @dataclass
    class _SignalHandle:
        connect: callable

    class _SignalTimer(_QTimer):
        def __init__(self) -> None:
            super().__init__()
            self._connect_target: Optional[callable] = None

        def timeout(self) -> "_SignalHandle":  # type: ignore[override]
            def _connect(callback: callable) -> None:
                self._callback = callback

            return _SignalHandle(connect=_connect)

    class _QtCoreModule:
        Qt = _QtNamespace
        QModelIndex = _QModelIndex
        QObject = _QObject
        QAbstractListModel = _QAbstractListModel
        QTimer = _SignalTimer

    class _QtWidgetsModule:
        QApplication = _QApplication
        QListView = _QListView
        QLabel = _QLabel
        QMainWindow = _QMainWindow
        QWidget = _QWidget
        QVBoxLayout = _QVBoxLayout

    QtCore = _QtCoreModule()
    QtWidgets = _QtWidgetsModule()

__all__ = ["QtCore", "QtWidgets", "QT_AVAILABLE", "QT_API", "SUPPORTED_QT_BINDINGS"]

# Re-export commonly used classes for convenience
# When Qt is available, these come from the real Qt modules
# When Qt is not available, we provide minimal shims or None
if QT_AVAILABLE:
    # QtCore classes
    QAbstractItemModel = QtCore.QAbstractItemModel
    QModelIndex = QtCore.QModelIndex
    QObject = QtCore.QObject
    QTimer = QtCore.QTimer
    Qt = QtCore.Qt
    pyqtSignal = QtCore.Signal if hasattr(QtCore, 'Signal') else QtCore.pyqtSignal

    # QtWidgets classes
    QWidget = QtWidgets.QWidget
    QMainWindow = QtWidgets.QMainWindow
    QLabel = QtWidgets.QLabel
    QPushButton = QtWidgets.QPushButton
    QToolButton = QtWidgets.QToolButton
    QFrame = QtWidgets.QFrame
    QVBoxLayout = QtWidgets.QVBoxLayout
    QHBoxLayout = QtWidgets.QHBoxLayout
    QStackedWidget = QtWidgets.QStackedWidget
    QSplitter = QtWidgets.QSplitter
    QScrollArea = QtWidgets.QScrollArea
    QSizePolicy = QtWidgets.QSizePolicy
    QLineEdit = QtWidgets.QLineEdit
    QComboBox = QtWidgets.QComboBox
    QCheckBox = QtWidgets.QCheckBox
    QProgressBar = QtWidgets.QProgressBar
    QDialog = QtWidgets.QDialog
    QDialogButtonBox = QtWidgets.QDialogButtonBox
    QTableView = QtWidgets.QTableView
    QHeaderView = QtWidgets.QHeaderView
    QStyledItemDelegate = QtWidgets.QStyledItemDelegate
    QMenu = QtWidgets.QMenu
    QAction = QtWidgets.QAction if hasattr(QtWidgets, 'QAction') else QtCore.QAction

    # Try to import additional classes that might be in QtWidgets or QtGui
    try:
        QShortcut = QtWidgets.QShortcut
    except AttributeError:
        from importlib import import_module
        QtGui = import_module(f"{QT_API}.QtGui")
        QShortcut = QtGui.QShortcut

    try:
        QKeySequence = QtCore.QKeySequence if hasattr(QtCore, 'QKeySequence') else QtWidgets.QKeySequence
    except AttributeError:
        from importlib import import_module
        QtGui = import_module(f"{QT_API}.QtGui")
        QKeySequence = QtGui.QKeySequence

    try:
        QPainter = None
        QBrush = None
        QPen = None
        QColor = None
        QRect = None
        QSize = None
        QStyleOptionViewItem = None
        QPropertyAnimation = None
        QEasingCurve = None
        QIcon = None
        QPixmap = None
        QScreen = None

        from importlib import import_module
        QtGui = import_module(f"{QT_API}.QtGui")
        QPainter = QtGui.QPainter
        QBrush = QtGui.QBrush
        QPen = QtGui.QPen
        QColor = QtGui.QColor
        QIcon = QtGui.QIcon
        QPixmap = QtGui.QPixmap
        QScreen = QtGui.QScreen if hasattr(QtGui, 'QScreen') else None

        # Some classes might be in QtCore
        QRect = QtCore.QRect
        QSize = QtCore.QSize
        QPropertyAnimation = QtCore.QPropertyAnimation
        QEasingCurve = QtCore.QEasingCurve

        # QStyleOptionViewItem is in QtWidgets
        QStyleOptionViewItem = QtWidgets.QStyleOptionViewItem
    except (ImportError, AttributeError):
        pass
else:
    # Shim mode - provide minimal implementations
    QAbstractItemModel = _QtCoreModule.QAbstractListModel
    QModelIndex = _QtCoreModule.QModelIndex
    QObject = _QtCoreModule.QObject
    QTimer = _QtCoreModule.QTimer
    Qt = _QtCoreModule.Qt

    class _pyqtSignalShim:
        def __init__(self, *args):
            pass
        def connect(self, func):
            pass
        def emit(self, *args):
            pass

    pyqtSignal = _pyqtSignalShim

    QWidget = _QtWidgetsModule.QWidget
    QMainWindow = _QtWidgetsModule.QMainWindow
    QLabel = _QtWidgetsModule.QLabel
    QPushButton = None
    QToolButton = None
    QFrame = None
    QVBoxLayout = _QtWidgetsModule.QVBoxLayout
    QHBoxLayout = None
    QStackedWidget = None
    QSplitter = None
    QScrollArea = None
    QSizePolicy = None
    QLineEdit = None
    QComboBox = None
    QCheckBox = None
    QProgressBar = None
    QDialog = None
    QDialogButtonBox = None
    QTableView = None
    QHeaderView = None
    QStyledItemDelegate = None
    QMenu = None
    QAction = None
    QShortcut = None
    QKeySequence = None
    QPainter = None
    QBrush = None
    QPen = None
    QColor = None
    QRect = None
    QSize = None
    QStyleOptionViewItem = None
    QPropertyAnimation = None
    QEasingCurve = None
    QIcon = None
    QPixmap = None
    QScreen = None
