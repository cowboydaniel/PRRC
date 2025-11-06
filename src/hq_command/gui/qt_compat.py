"""Centralized imports for PySide6 GUI classes used by HQ Command."""
from __future__ import annotations

from typing import Any

try:
    from PySide6 import QtCore, QtGui, QtWidgets, QtSvg
except ImportError as exc:  # pragma: no cover - import-time guard
    raise ImportError("PySide6 is required to run the HQ Command GUI.") from exc

QT_API = "PySide6"
SUPPORTED_QT_BINDINGS: tuple[str, ...] = (QT_API,)

# Core modules
Qt = QtCore.Qt
pyqtSignal = QtCore.Signal

# QtCore exports
QAbstractItemModel = QtCore.QAbstractItemModel
QAbstractListModel = QtCore.QAbstractListModel
QModelIndex = QtCore.QModelIndex
QObject = QtCore.QObject
QTimer = QtCore.QTimer
QPoint = QtCore.QPoint
QPointF = QtCore.QPointF
QRect = QtCore.QRect
QSize = QtCore.QSize
QPropertyAnimation = QtCore.QPropertyAnimation
QEasingCurve = QtCore.QEasingCurve
QParallelAnimationGroup = QtCore.QParallelAnimationGroup
QSequentialAnimationGroup = QtCore.QSequentialAnimationGroup

# QtGui exports
QAction = QtGui.QAction
QBrush = QtGui.QBrush
QColor = QtGui.QColor
QFont = QtGui.QFont
QIcon = QtGui.QIcon
QKeySequence = QtGui.QKeySequence
QPainter = QtGui.QPainter
QPen = QtGui.QPen
QPixmap = QtGui.QPixmap
QPolygonF = QtGui.QPolygonF
QScreen = QtGui.QScreen
QShortcut = QtGui.QShortcut

# QtSvg exports
QSvgRenderer = QtSvg.QSvgRenderer

# QtWidgets exports
QAbstractItemView = QtWidgets.QAbstractItemView
QApplication = QtWidgets.QApplication
QCheckBox = QtWidgets.QCheckBox
QTabWidget = QtWidgets.QTabWidget
QComboBox = QtWidgets.QComboBox
QDialog = QtWidgets.QDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QFrame = QtWidgets.QFrame
QGraphicsOpacityEffect = QtWidgets.QGraphicsOpacityEffect
QGridLayout = QtWidgets.QGridLayout
QGroupBox = QtWidgets.QGroupBox
QHeaderView = QtWidgets.QHeaderView
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QListWidget = QtWidgets.QListWidget
QListWidgetItem = QtWidgets.QListWidgetItem
QMainWindow = QtWidgets.QMainWindow
QMenu = QtWidgets.QMenu
QProgressBar = QtWidgets.QProgressBar
QPushButton = QtWidgets.QPushButton
QScrollArea = QtWidgets.QScrollArea
QSizePolicy = QtWidgets.QSizePolicy
QSpinBox = QtWidgets.QSpinBox
QSplitter = QtWidgets.QSplitter
QStackedWidget = QtWidgets.QStackedWidget
QStyledItemDelegate = QtWidgets.QStyledItemDelegate
QTableView = QtWidgets.QTableView
QTableWidget = QtWidgets.QTableWidget
QTableWidgetItem = QtWidgets.QTableWidgetItem
QTextEdit = QtWidgets.QTextEdit
QToolButton = QtWidgets.QToolButton
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget

# Additional helpers
QPalette = QtGui.QPalette
QStyleOptionViewItem = QtWidgets.QStyleOptionViewItem


def qt_exec(target: Any, *args: Any, **kwargs: Any) -> Any:
    """Execute dialogs or menus, honoring PySide6 exec variations."""

    for method_name in ("exec", "exec_"):
        method = getattr(target, method_name, None)
        if callable(method):
            return method(*args, **kwargs)
    return None


__all__ = [
    "QT_API",
    "Qt",
    "QtCore",
    "QtGui",
    "QtWidgets",
    "SUPPORTED_QT_BINDINGS",
    "QAbstractItemModel",
    "QAbstractListModel",
    "QAbstractItemView",
    "QAction",
    "QApplication",
    "QBrush",
    "QCheckBox",
    "QColor",
    "QComboBox",
    "QDialog",
    "QDialogButtonBox",
    "QFrame",
    "QGraphicsOpacityEffect",
    "QGridLayout",
    "QGroupBox",
    "QHeaderView",
    "QHBoxLayout",
    "QIcon",
    "QFont",
    "QKeySequence",
    "QLabel",
    "QLineEdit",
    "QListWidget",
    "QListWidgetItem",
    "QMainWindow",
    "QMenu",
    "QModelIndex",
    "QObject",
    "QPalette",
    "QPainter",
    "QPen",
    "QPixmap",
    "QPoint",
    "QPointF",
    "QPolygonF",
    "QProgressBar",
    "QPropertyAnimation",
    "QPushButton",
    "QScreen",
    "QScrollArea",
    "QSequentialAnimationGroup",
    "QShortcut",
    "QSize",
    "QSizePolicy",
    "QSpinBox",
    "QSplitter",
    "QStackedWidget",
    "QStyledItemDelegate",
    "QStyleOptionViewItem",
    "QTableView",
    "QTableWidget",
    "QTableWidgetItem",
    "QTextEdit",
    "QTimer",
    "QToolButton",
    "QVBoxLayout",
    "QWidget",
    "QRect",
    "QEasingCurve",
    "QParallelAnimationGroup",
    "pyqtSignal",
    "qt_exec",
]
