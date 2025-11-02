"""
HQ Command GUI Accessibility Infrastructure.

Provides keyboard navigation, focus management, and ARIA-style labeling.
"""

from typing import Optional, List

from .qt_compat import QWidget, QShortcut, QKeySequence, Qt
from .styles import theme


class KeyboardNavigationManager:
    """
    Manages keyboard navigation and shortcuts for the application.

    Provides consistent keyboard shortcuts across the application.
    """

    def __init__(self, parent: QWidget):
        """
        Initialize keyboard navigation manager.

        Args:
            parent: Parent widget for shortcuts
        """
        self.parent = parent
        self.shortcuts: List[QShortcut] = []

    def register_shortcut(
        self,
        key_sequence: str,
        callback: callable,
        context: Qt.ShortcutContext = Qt.WindowShortcut,
    ):
        """
        Register a keyboard shortcut.

        Args:
            key_sequence: Key sequence (e.g., "Ctrl+S", "F1")
            callback: Function to call when shortcut is triggered
            context: Shortcut context (window, application, etc.)
        """
        shortcut = QShortcut(QKeySequence(key_sequence), self.parent)
        shortcut.setContext(context)
        shortcut.activated.connect(callback)
        self.shortcuts.append(shortcut)

    def setup_default_shortcuts(self, callbacks: dict):
        """
        Set up default application shortcuts.

        Args:
            callbacks: Dictionary mapping action names to callbacks
        """
        # Navigation shortcuts (Alt+1 through Alt+5)
        if "nav_live_ops" in callbacks:
            self.register_shortcut("Alt+1", callbacks["nav_live_ops"])
        if "nav_task_board" in callbacks:
            self.register_shortcut("Alt+2", callbacks["nav_task_board"])
        if "nav_telemetry" in callbacks:
            self.register_shortcut("Alt+3", callbacks["nav_telemetry"])
        if "nav_audit" in callbacks:
            self.register_shortcut("Alt+4", callbacks["nav_audit"])
        if "nav_admin" in callbacks:
            self.register_shortcut("Alt+5", callbacks["nav_admin"])

        # Common actions
        if "save" in callbacks:
            self.register_shortcut("Ctrl+S", callbacks["save"])
        if "refresh" in callbacks:
            self.register_shortcut("F5", callbacks["refresh"])
        if "search" in callbacks:
            self.register_shortcut("Ctrl+F", callbacks["search"])
        if "new_task" in callbacks:
            self.register_shortcut("Ctrl+N", callbacks["new_task"])
        if "toggle_drawer" in callbacks:
            self.register_shortcut("Ctrl+D", callbacks["toggle_drawer"])
        if "help" in callbacks:
            self.register_shortcut("F1", callbacks["help"])
        if "fullscreen" in callbacks:
            self.register_shortcut("F11", callbacks["fullscreen"])

    def clear_shortcuts(self):
        """Clear all registered shortcuts."""
        for shortcut in self.shortcuts:
            shortcut.setEnabled(False)
            shortcut.deleteLater()
        self.shortcuts.clear()


class FocusManager:
    """
    Manages focus order and focus indicators for accessibility.

    Ensures logical tab order and visible focus indicators.
    """

    def __init__(self, parent: QWidget):
        """
        Initialize focus manager.

        Args:
            parent: Parent widget
        """
        self.parent = parent
        self.focus_chain: List[QWidget] = []

    def set_focus_chain(self, widgets: List[QWidget]):
        """
        Set explicit tab order for widgets.

        Args:
            widgets: Ordered list of widgets for tab navigation
        """
        self.focus_chain = widgets

        # Set Qt tab order
        for i in range(len(widgets) - 1):
            QWidget.setTabOrder(widgets[i], widgets[i + 1])

    def ensure_visible_focus(self, widget: QWidget):
        """
        Ensure widget has visible focus indicator.

        Args:
            widget: Widget to ensure focus visibility for
        """
        # Apply focus ring stylesheet
        widget.setStyleSheet(
            widget.styleSheet() + f"""
            *:focus {{
                outline: 3px solid {theme.FOCUS_RING};
                outline-offset: 2px;
            }}
            """
        )

    def focus_first(self):
        """Move focus to first widget in chain."""
        if self.focus_chain:
            self.focus_chain[0].setFocus()

    def focus_last(self):
        """Move focus to last widget in chain."""
        if self.focus_chain:
            self.focus_chain[-1].setFocus()


class AccessibilityHelper:
    """
    Provides accessibility utilities for widgets.

    Handles ARIA-style labeling and descriptions.
    """

    @staticmethod
    def set_accessible_name(widget: QWidget, name: str):
        """
        Set accessible name for screen readers.

        Args:
            widget: Widget to label
            name: Accessible name
        """
        widget.setAccessibleName(name)

    @staticmethod
    def set_accessible_description(widget: QWidget, description: str):
        """
        Set accessible description for screen readers.

        Args:
            widget: Widget to describe
            description: Accessible description
        """
        widget.setAccessibleDescription(description)

    @staticmethod
    def mark_as_button(widget: QWidget, label: str):
        """
        Mark widget as button role with label.

        Args:
            widget: Widget to mark
            label: Button label
        """
        widget.setAccessibleName(label)
        widget.setAccessibleDescription(f"Button: {label}")

    @staticmethod
    def mark_as_input(widget: QWidget, label: str, required: bool = False):
        """
        Mark widget as input field with label.

        Args:
            widget: Widget to mark
            label: Input label
            required: Whether input is required
        """
        desc = f"Input field: {label}"
        if required:
            desc += " (required)"
        widget.setAccessibleName(label)
        widget.setAccessibleDescription(desc)

    @staticmethod
    def ensure_touch_target_size(widget: QWidget):
        """
        Ensure widget meets minimum touch target size (44px).

        Args:
            widget: Widget to check/adjust
        """
        if widget.minimumHeight() < theme.MIN_TOUCH_TARGET:
            widget.setMinimumHeight(theme.MIN_TOUCH_TARGET)
        if widget.minimumWidth() < theme.MIN_TOUCH_TARGET:
            widget.setMinimumWidth(theme.MIN_TOUCH_TARGET)


def setup_accessibility(widget: QWidget):
    """
    Apply accessibility enhancements to a widget and its children.

    Args:
        widget: Root widget to enhance
    """
    # Ensure focus policy allows keyboard navigation
    if widget.focusPolicy() == Qt.NoFocus:
        widget.setFocusPolicy(Qt.TabFocus)

    # Apply focus ring stylesheet
    widget.setStyleSheet(
        widget.styleSheet() + f"""
        *:focus {{
            outline: 3px solid {theme.FOCUS_RING};
            outline-offset: 2px;
        }}
        """
    )

    # Recursively apply to children
    for child in widget.findChildren(QWidget):
        if child.focusPolicy() == Qt.NoFocus and child.isEnabled():
            child.setFocusPolicy(Qt.TabFocus)
