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

def _attempt_import(binding: str) -> tuple[ModuleType, ModuleType] | None:
    try:
        core_mod = import_module(f"{binding}.QtCore")
        widgets_mod = import_module(f"{binding}.QtWidgets")
    except Exception:  # pragma: no cover - binding not available
        return None

    return core_mod, widgets_mod


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

    def rowCount(self, parent: Optional[_QModelIndex] = None) -> int:  # noqa: D401 - Qt signature
        return len(self._items)

    def data(self, index: _QModelIndex, role: int = 0) -> Any:  # noqa: D401 - Qt signature
        if not 0 <= index.row() < len(self._items):
            return None
        if role in (_QtNamespace.DisplayRole, _QtNamespace.EditRole, _QtNamespace.UserRole):
            return self._items[index.row()]
        return None

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


class _pyqtSignalShim:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        return None

    def connect(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - shim behavior
        return None

    def emit(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - shim behavior
        return None


class _QFontStub:
    Light = "light"
    Normal = "normal"
    Medium = "medium"
    DemiBold = "demibold"
    Bold = "bold"
    Black = "black"

    def __init__(self, family: str = "", point_size: int = 0) -> None:
        self.family = family
        self.point_size = point_size


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


_SHIM_CORE = _QtCoreModule()
_SHIM_WIDGETS = _QtWidgetsModule()


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
    QtCore = _SHIM_CORE
    QtWidgets = _SHIM_WIDGETS

__all__ = [
    "QtCore",
    "QtWidgets",
    "QT_AVAILABLE",
    "QT_API",
    "SUPPORTED_QT_BINDINGS",
    "qt_exec",
    "QPolygonF",
    "QPointF",
]

# Re-export commonly used classes for convenience
# When Qt is available, these come from the real Qt modules
# When Qt is not available, we provide minimal shims or None
if QT_AVAILABLE:
    for _name, _fallback in {
        "QAbstractListModel": _SHIM_CORE.QAbstractListModel,
        "QModelIndex": _SHIM_CORE.QModelIndex,
        "QObject": _SHIM_CORE.QObject,
        "QTimer": _SHIM_CORE.QTimer,
    }.items():
        if not hasattr(QtCore, _name):
            setattr(QtCore, _name, _fallback)

    if not hasattr(QtCore, "Qt"):
        QtCore.Qt = _QtNamespace  # type: ignore[attr-defined]

    _qt_constants = {
        "DisplayRole": _QtNamespace.DisplayRole,
        "EditRole": _QtNamespace.EditRole,
        "UserRole": _QtNamespace.UserRole,
        "WindowShortcut": 0,
        "ApplicationShortcut": 1,
        "WidgetShortcut": 2,
        "AscendingOrder": 0,
        "DescendingOrder": 1,
    }

    for _const_name, _const_value in _qt_constants.items():
        if not hasattr(QtCore.Qt, _const_name):
            setattr(QtCore.Qt, _const_name, _const_value)

    if not hasattr(QtCore.Qt, "ShortcutContext"):
        QtCore.Qt.ShortcutContext = type(
            "ShortcutContext",
            (),
            {
                "WidgetShortcut": _qt_constants["WidgetShortcut"],
                "WindowShortcut": _qt_constants["WindowShortcut"],
                "ApplicationShortcut": _qt_constants["ApplicationShortcut"],
            },
        )

    if not hasattr(QtCore.Qt, "SortOrder"):
        QtCore.Qt.SortOrder = type(
            "SortOrder",
            (),
            {
                "AscendingOrder": _qt_constants["AscendingOrder"],
                "DescendingOrder": _qt_constants["DescendingOrder"],
            },
        )

    QtGui: ModuleType | None = None
    try:  # pragma: no cover - only when Qt bindings exist
        QtGui = import_module(f"{QT_API}.QtGui")
    except ImportError:  # pragma: no cover - binding missing QtGui
        QtGui = None

    # QtCore classes
    QAbstractItemModel = getattr(
        QtCore,
        "QAbstractItemModel",
        getattr(QtCore, "QAbstractListModel", _SHIM_CORE.QAbstractListModel),
    )
    QModelIndex = getattr(QtCore, "QModelIndex", _SHIM_CORE.QModelIndex)
    QObject = getattr(QtCore, "QObject", _SHIM_CORE.QObject)
    QTimer = getattr(QtCore, "QTimer", _SHIM_CORE.QTimer)
    Qt = getattr(QtCore, "Qt", _QtNamespace)

    _qt_signal = getattr(QtCore, "Signal", None) or getattr(QtCore, "pyqtSignal", None)
    pyqtSignal = _qt_signal if _qt_signal is not None else _pyqtSignalShim

    # QtWidgets classes
    QWidget = getattr(QtWidgets, "QWidget", _QWidget)
    QMainWindow = getattr(QtWidgets, "QMainWindow", _QMainWindow)
    QLabel = getattr(QtWidgets, "QLabel", _QLabel)
    QPushButton = getattr(QtWidgets, "QPushButton", _QWidget)
    QToolButton = getattr(QtWidgets, "QToolButton", _QWidget)
    QFrame = getattr(QtWidgets, "QFrame", _QWidget)
    QVBoxLayout = getattr(QtWidgets, "QVBoxLayout", _QVBoxLayout)
    QHBoxLayout = getattr(QtWidgets, "QHBoxLayout", _QVBoxLayout)
    QStackedWidget = getattr(QtWidgets, "QStackedWidget", _QWidget)
    QSplitter = getattr(QtWidgets, "QSplitter", _QWidget)
    QScrollArea = getattr(QtWidgets, "QScrollArea", _QWidget)
    QSizePolicy = getattr(QtWidgets, "QSizePolicy", None)
    QLineEdit = getattr(QtWidgets, "QLineEdit", _QWidget)
    QComboBox = getattr(QtWidgets, "QComboBox", _QWidget)
    QCheckBox = getattr(QtWidgets, "QCheckBox", _QWidget)
    QProgressBar = getattr(QtWidgets, "QProgressBar", _QWidget)
    QDialog = getattr(QtWidgets, "QDialog", _QWidget)
    QDialogButtonBox = getattr(QtWidgets, "QDialogButtonBox", _QWidget)
    QTableView = getattr(QtWidgets, "QTableView", _QWidget)
    QTableWidget = getattr(QtWidgets, "QTableWidget", _QWidget)
    QTableWidgetItem = getattr(QtWidgets, "QTableWidgetItem", object)
    QHeaderView = getattr(QtWidgets, "QHeaderView", _QWidget)
    QAbstractItemView = getattr(QtWidgets, "QAbstractItemView", _QWidget)
    QStyledItemDelegate = getattr(QtWidgets, "QStyledItemDelegate", _QWidget)
    QMenu = getattr(QtWidgets, "QMenu", _QWidget)
    QAction = getattr(QtWidgets, "QAction", getattr(QtCore, "QAction", object))
    QTextEdit = getattr(QtWidgets, "QTextEdit", _QWidget)
    QSpinBox = getattr(QtWidgets, "QSpinBox", _QWidget)
    QGroupBox = getattr(QtWidgets, "QGroupBox", _QWidget)
    QGridLayout = getattr(QtWidgets, "QGridLayout", _QVBoxLayout)
    QListWidget = getattr(QtWidgets, "QListWidget", _QWidget)
    QListWidgetItem = getattr(QtWidgets, "QListWidgetItem", object)

    # Try to import additional classes that might be in QtWidgets or QtGui
    try:
        QShortcut = QtWidgets.QShortcut
    except AttributeError:
        QShortcut = QtGui.QShortcut if QtGui and hasattr(QtGui, "QShortcut") else None

    try:
        QKeySequence = (
            QtCore.QKeySequence
            if hasattr(QtCore, "QKeySequence")
            else QtWidgets.QKeySequence
        )
    except AttributeError:
        QKeySequence = QtGui.QKeySequence if QtGui and hasattr(QtGui, "QKeySequence") else None

    QPainter = QtGui.QPainter if QtGui and hasattr(QtGui, "QPainter") else None
    QBrush = QtGui.QBrush if QtGui and hasattr(QtGui, "QBrush") else None
    QPen = QtGui.QPen if QtGui and hasattr(QtGui, "QPen") else None
    QColor = QtGui.QColor if QtGui and hasattr(QtGui, "QColor") else None
    QIcon = QtGui.QIcon if QtGui and hasattr(QtGui, "QIcon") else None
    QPixmap = QtGui.QPixmap if QtGui and hasattr(QtGui, "QPixmap") else None
    QScreen = QtGui.QScreen if QtGui and hasattr(QtGui, "QScreen") else None
    QPalette = QtGui.QPalette if QtGui and hasattr(QtGui, "QPalette") else None
    QFont = QtGui.QFont if QtGui and hasattr(QtGui, "QFont") else _QFontStub
    for _weight_name in ("Light", "Normal", "Medium", "DemiBold", "Bold", "Black"):
        if not hasattr(QFont, _weight_name):
            setattr(QFont, _weight_name, getattr(_QFontStub, _weight_name))

    QRect = QtCore.QRect if hasattr(QtCore, "QRect") else None
    QSize = QtCore.QSize if hasattr(QtCore, "QSize") else None
    QPoint = QtCore.QPoint if hasattr(QtCore, "QPoint") else None
    QPropertyAnimation = QtCore.QPropertyAnimation if hasattr(QtCore, "QPropertyAnimation") else None
    QEasingCurve = QtCore.QEasingCurve if hasattr(QtCore, "QEasingCurve") else None
    QParallelAnimationGroup = (
        QtCore.QParallelAnimationGroup if hasattr(QtCore, "QParallelAnimationGroup") else None
    )
    QSequentialAnimationGroup = (
        QtCore.QSequentialAnimationGroup if hasattr(QtCore, "QSequentialAnimationGroup") else None
    )

    QStyleOptionViewItem = (
        QtWidgets.QStyleOptionViewItem if hasattr(QtWidgets, "QStyleOptionViewItem") else None
    )

    QGraphicsOpacityEffect = (
        QtWidgets.QGraphicsOpacityEffect if hasattr(QtWidgets, "QGraphicsOpacityEffect") else None
    )
    QPolygonF = QtGui.QPolygonF if QtGui and hasattr(QtGui, "QPolygonF") else None
    QPointF = QtCore.QPointF if hasattr(QtCore, "QPointF") else None
else:
    # Shim mode - provide minimal implementations
    QAbstractItemModel = _QtCoreModule.QAbstractListModel
    QModelIndex = _QtCoreModule.QModelIndex
    QObject = _QtCoreModule.QObject
    QTimer = _QtCoreModule.QTimer
    Qt = _QtCoreModule.Qt

    pyqtSignal = _pyqtSignalShim

    QFont = _QFontStub

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
    QTableWidget = None
    QTableWidgetItem = None
    QHeaderView = None
    QAbstractItemView = None
    QStyledItemDelegate = None
    QMenu = None
    QAction = None
    QTextEdit = None
    QSpinBox = None
    QGroupBox = None
    QGridLayout = None
    QListWidget = None
    QListWidgetItem = None
    QShortcut = None
    QKeySequence = None
    QPainter = None
    QBrush = None
    QPen = None
    QColor = None
    QRect = None
    QSize = None
    QPoint = None
    QStyleOptionViewItem = None
    QPropertyAnimation = None
    QEasingCurve = None
    QParallelAnimationGroup = None
    QSequentialAnimationGroup = None
    QIcon = None
    QPixmap = None
    QScreen = None
    QPalette = None
    QGraphicsOpacityEffect = None
    QPolygonF = None
    QPointF = None


def qt_exec(target: Any, *args: Any, **kwargs: Any) -> Any:
    """Execute Qt dialogs or menus with PySide/PyQt compatibility."""

    for method_name in ("exec", "exec_"):
        method = getattr(target, method_name, None)
        if callable(method):
            return method(*args, **kwargs)
    return None
