"""
HQ Command GUI Layout Components.

Provides major layout components including:
- Navigation Rail (left sidebar)
- Global Status Bar (top bar)
- Mission Canvas (center 2-column layout)
- Context Drawer (right overlay)
"""

from typing import Optional, List, Callable, Sequence
from enum import Enum

from .qt_compat import (
    QWidget,
    QFrame,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QScrollArea,
    QSizePolicy,
    QPropertyAnimation,
    QEasingCurve,
    Qt,
    pyqtSignal,
)
from .styles import theme
from .components import StatusBadge, StatusType


# =============================================================================
# NAVIGATION RAIL
# =============================================================================

class NavSection(Enum):
    """Navigation sections for HQ Command."""
    LIVE_OPS = ("live_ops", "Live Ops", "📡")
    TASK_BOARD = ("task_board", "Task Board", "📋")
    TELEMETRY = ("telemetry", "Telemetry", "📊")
    AUDIT = ("audit", "Audit Trails", "🔍")
    ADMIN = ("admin", "Admin", "⚙️")


class NavigationRail(QFrame):
    """
    Left-side navigation rail (72px wide).

    Provides tab-style navigation with icons and labels.
    Emits signals when navigation changes.
    """

    section_changed = pyqtSignal(str)  # Emits section ID when clicked

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("NavigationRail")
        self.setFixedWidth(theme.NAV_RAIL_WIDTH)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, theme.SPACING_SM, 0, theme.SPACING_SM)
        layout.setSpacing(theme.SPACING_XS)

        # Create navigation buttons
        self.buttons: dict[str, QToolButton] = {}
        for section in NavSection:
            button = QToolButton(self)
            button.setObjectName("NavButton")
            button.setText(f"{section.value[2]}\n{section.value[1]}")
            button.setCheckable(True)
            button.setToolTip(section.value[1])
            button.setMinimumHeight(theme.MIN_TOUCH_TARGET + theme.SPACING_LG)
            button.setMinimumWidth(theme.NAV_RAIL_WIDTH - theme.SPACING_SM * 2)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.clicked.connect(
                lambda checked, s=section.value[0]: self._on_nav_clicked(s)
            )
            layout.addWidget(button)
            self.buttons[section.value[0]] = button

        # Set first button as active
        if self.buttons:
            first_section = list(self.buttons.keys())[0]
            self.buttons[first_section].setChecked(True)

        # Add spacer to push buttons to top
        layout.addStretch(1)

        self._visible_sections: set[str] = set(self.buttons.keys())

    def _on_nav_clicked(self, section_id: str):
        """Handle navigation button click."""
        if section_id not in self._visible_sections:
            return
        # Uncheck all other buttons
        for btn_id, button in self.buttons.items():
            button.setChecked(btn_id == section_id)

        # Emit signal
        self.section_changed.emit(section_id)

    def configure_sections(self, section_ids: Sequence[str], *, active: Optional[str] = None) -> None:
        """Limit navigation to the provided sections and select an active one."""

        visible = [section_id for section_id in section_ids if section_id in self.buttons]
        if not visible:
            visible = list(self.buttons.keys())

        self._visible_sections = set(visible)
        for section_id, button in self.buttons.items():
            button.setVisible(section_id in self._visible_sections)

        target = active if active in self._visible_sections else (visible[0] if visible else None)
        if target:
            self.set_active_section(target)

    def set_active_section(self, section_id: str, *, emit: bool = True):
        """Programmatically set the active section."""

        if section_id not in self.buttons:
            return

        previous_state = self.blockSignals(True) if not emit else False
        for btn_id, button in self.buttons.items():
            button.setChecked(btn_id == section_id)
        if not emit:
            self.blockSignals(previous_state)
        else:
            self.section_changed.emit(section_id)


# =============================================================================
# GLOBAL STATUS BAR
# =============================================================================

class GlobalStatusBar(QFrame):
    """
    Top status bar (56px height).

    Displays sync status, escalation counts, and communication status.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("StatusBar")
        self.setFixedHeight(theme.STATUS_BAR_HEIGHT)

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            theme.SPACING_MD,
            theme.SPACING_MD,
            theme.SPACING_MD,
            theme.SPACING_MD,
        )
        layout.setSpacing(theme.SPACING_MD)

        # Application title
        self.title_label = QLabel("HQ Command")
        self.title_label.setObjectName("H4")
        layout.addWidget(self.title_label)

        self.role_badge = StatusBadge("Role: --", StatusType.INFO)
        layout.addWidget(self.role_badge)

        # Spacer
        layout.addStretch(1)

        self.permission_badge = StatusBadge("0 Permissions", StatusType.INFO)
        layout.addWidget(self.permission_badge)

        # Sync status badge
        self.sync_badge = StatusBadge("Synced", StatusType.SUCCESS)
        layout.addWidget(self.sync_badge)

        # Escalation count badge
        self.escalation_badge = StatusBadge("0 Escalations", StatusType.INFO)
        layout.addWidget(self.escalation_badge)

        # Communications status badge
        self.comms_badge = StatusBadge("Connected", StatusType.SUCCESS)
        layout.addWidget(self.comms_badge)

    def set_sync_status(self, status: str, status_type: StatusType):
        """Update sync status display."""
        self.sync_badge.setText(status)
        self.sync_badge.set_status(status_type)

    def set_escalation_count(self, count: int):
        """Update escalation count display."""
        self.escalation_badge.setText(f"{count} Escalation{'s' if count != 1 else ''}")
        if count > 0:
            self.escalation_badge.set_status(StatusType.WARNING)
        else:
            self.escalation_badge.set_status(StatusType.INFO)

    def set_comms_status(self, status: str, status_type: StatusType):
        """Update communications status display."""
        self.comms_badge.setText(status)
        self.comms_badge.set_status(status_type)

    def set_active_role(self, role_name: str, status_type: StatusType = StatusType.INFO):
        """Display the active operator role."""

        self.role_badge.setText(f"Role: {role_name}")
        self.role_badge.set_status(status_type)

    def set_permission_summary(self, permission_count: int):
        """Display a summary of granted permissions."""

        label = "Permission" if permission_count == 1 else "Permissions"
        self.permission_badge.setText(f"{permission_count} {label}")
        self.permission_badge.set_status(StatusType.INFO)


# =============================================================================
# MISSION CANVAS (2-COLUMN LAYOUT)
# =============================================================================

class MissionCanvas(QWidget):
    """
    Center mission canvas with 2-column layout (55%/45% split).

    Uses QSplitter to allow resizing between columns.
    Provides responsive reflow logic for narrow screens.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Splitter for 2-column layout
        self.splitter = QSplitter(Qt.Horizontal, self)
        layout.addWidget(self.splitter)

        # Left panel (55%)
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(
            theme.SPACING_LG,
            theme.SPACING_LG,
            theme.SPACING_MD,
            theme.SPACING_LG,
        )
        self.left_layout.setSpacing(theme.SPACING_LG)
        self.splitter.addWidget(self.left_panel)

        # Right panel (45%)
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(
            theme.SPACING_MD,
            theme.SPACING_LG,
            theme.SPACING_LG,
            theme.SPACING_LG,
        )
        self.right_layout.setSpacing(theme.SPACING_LG)
        self.splitter.addWidget(self.right_panel)

        # Set initial splitter sizes (55%/45%)
        self.splitter.setSizes([550, 450])

    def add_to_left(self, widget: QWidget):
        """Add widget to left panel."""
        self.left_layout.addWidget(widget)

    def add_to_right(self, widget: QWidget):
        """Add widget to right panel."""
        self.right_layout.addWidget(widget)

    def resizeEvent(self, event):
        """Handle resize for responsive layout."""
        super().resizeEvent(event)

        # Responsive reflow for narrow screens (≤1023px)
        width = event.size().width()

        if width <= 1023:
            # Switch to vertical stacking for narrow screens
            if self.splitter.orientation() == Qt.Horizontal:
                self.splitter.setOrientation(Qt.Vertical)
                # Equal distribution in vertical mode
                self.splitter.setSizes([500, 500])
        else:
            # Return to horizontal layout for wider screens
            if self.splitter.orientation() == Qt.Vertical:
                self.splitter.setOrientation(Qt.Horizontal)
                # Restore 55%/45% split
                self.splitter.setSizes([550, 450])


# =============================================================================
# CONTEXT DRAWER (RIGHT OVERLAY)
# =============================================================================

class ContextDrawer(QFrame):
    """
    Right-side overlay drawer (360px width).

    Slides in/out with animation. Used for detailed views and context info.
    """

    drawer_opened = pyqtSignal()
    drawer_closed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ContextDrawer")
        self.setFixedWidth(theme.CONTEXT_DRAWER_WIDTH)

        # Initially hidden (positioned off-screen to the right)
        self.is_open = False

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            theme.SPACING_MD,
            theme.SPACING_MD,
            theme.SPACING_MD,
            theme.SPACING_MD,
        )
        layout.setSpacing(theme.SPACING_MD)

        # Header with close button
        header_layout = QHBoxLayout()
        self.title_label = QLabel("Context")
        self.title_label.setObjectName("H3")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch(1)

        self.close_button = QToolButton()
        self.close_button.setText("✕")
        self.close_button.setFixedSize(theme.MIN_TOUCH_TARGET, theme.MIN_TOUCH_TARGET)
        self.close_button.clicked.connect(self.close_drawer)
        header_layout.addWidget(self.close_button)

        layout.addLayout(header_layout)

        # Scrollable content area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(theme.SPACING_SM)
        self.content_layout.addStretch(1)

        self.scroll_area.setWidget(self.content_widget)
        layout.addWidget(self.scroll_area)

        # Animation for slide in/out
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setDuration(theme.TRANSITION_SLOW)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    def set_title(self, title: str):
        """Set drawer title."""
        self.title_label.setText(title)

    def add_content(self, widget: QWidget):
        """Add widget to drawer content."""
        # Remove stretch if present
        if self.content_layout.count() > 0:
            item = self.content_layout.takeAt(self.content_layout.count() - 1)
            if item.spacerItem():
                del item

        self.content_layout.addWidget(widget)
        self.content_layout.addStretch(1)

    def clear_content(self):
        """Clear all content from drawer."""
        while self.content_layout.count() > 0:
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.content_layout.addStretch(1)

    def open_drawer(self):
        """Animate drawer opening (slide in from right)."""
        if not self.is_open:
            self.show()
            parent_width = self.parent().width() if self.parent() else 0
            start_pos = (parent_width, 0)
            end_pos = (parent_width - theme.CONTEXT_DRAWER_WIDTH, 0)

            self.animation.setStartValue(start_pos)
            self.animation.setEndValue(end_pos)
            self.animation.start()

            self.is_open = True
            self.drawer_opened.emit()

    def close_drawer(self):
        """Animate drawer closing (slide out to right)."""
        if self.is_open:
            parent_width = self.parent().width() if self.parent() else 0
            start_pos = (parent_width - theme.CONTEXT_DRAWER_WIDTH, 0)
            end_pos = (parent_width, 0)

            self.animation.setStartValue(start_pos)
            self.animation.setEndValue(end_pos)
            self.animation.finished.connect(self._on_close_finished)
            self.animation.start()

            self.is_open = False

    def _on_close_finished(self):
        """Handle animation finished (hide drawer)."""
        self.hide()
        self.drawer_closed.emit()
        self.animation.finished.disconnect(self._on_close_finished)

    def toggle_drawer(self):
        """Toggle drawer open/closed."""
        if self.is_open:
            self.close_drawer()
        else:
            self.open_drawer()


# =============================================================================
# RESPONSIVE CONTAINER
# =============================================================================

class ResponsiveContainer(QWidget):
    """
    Container that adjusts layout based on available width.

    Implements responsive breakpoints:
    - ≥1440px: 4-column grid
    - 1024-1439px: 2-column grid
    - ≤1023px: 1-column stack
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_columns = 4

        # Main layout (will be recreated on resize)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(theme.SPACING_MD)

        # Track widgets for rearrangement
        self.widgets: List[QWidget] = []

    def add_widget(self, widget: QWidget):
        """Add widget to responsive container."""
        self.widgets.append(widget)
        self._rearrange_layout()

    def _rearrange_layout(self):
        """Rearrange widgets based on current column count."""
        # Clear layout
        while self.layout.count() > 0:
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Create grid based on column count
        if self.current_columns == 1:
            # Stack vertically
            for widget in self.widgets:
                self.layout.addWidget(widget)
        else:
            # Create grid
            rows_needed = (len(self.widgets) + self.current_columns - 1) // self.current_columns
            for row in range(rows_needed):
                row_layout = QHBoxLayout()
                row_layout.setSpacing(theme.SPACING_MD)

                for col in range(self.current_columns):
                    idx = row * self.current_columns + col
                    if idx < len(self.widgets):
                        row_layout.addWidget(self.widgets[idx])
                    else:
                        row_layout.addStretch(1)

                self.layout.addLayout(row_layout)

    def resizeEvent(self, event):
        """Handle resize to update column count."""
        super().resizeEvent(event)
        width = self.width()

        # Determine column count based on width
        if width >= 1440:
            new_columns = 4
        elif width >= 1024:
            new_columns = 2
        else:
            new_columns = 1

        # Rearrange if column count changed
        if new_columns != self.current_columns:
            self.current_columns = new_columns
            self._rearrange_layout()
