"""
HQ Command GUI Main Window.

Implements Phase 1 layout structure with:
- Navigation Rail (left, 72px)
- Global Status Bar (top, 56px)
- Mission Canvas (center, 2-column 55%/45%)
- Context Drawer (right overlay, 360px)
"""

from __future__ import annotations
from typing import Optional
from pathlib import Path

from .controller import HQCommandController
from .panes import RosterPane, TaskQueuePane, TelemetryPane
from .qt_compat import (
    QT_AVAILABLE,
    QtWidgets,
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QLabel,
)

# Phase 1 imports
from .styles import theme, build_palette, component_styles, ThemeVariant, Theme
from .layouts import NavigationRail, GlobalStatusBar, MissionCanvas, ContextDrawer, NavSection
from .components import Heading, Card, ErrorMessage, LoadingSpinner
from .window_manager import WindowManager
from .accessibility import KeyboardNavigationManager, FocusManager, setup_accessibility
from .animations import AnimationBuilder, TransitionManager


class HQMainWindow(QMainWindow):
    """
    Main window for HQ Command GUI.

    Implements Phase 1 core UI framework with navigation rail, status bar,
    mission canvas, and context drawer.
    """

    def __init__(
        self,
        controller: HQCommandController,
        parent: Optional[QWidget] = None,
        theme_variant: ThemeVariant = ThemeVariant.LIGHT,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.current_theme = Theme(theme_variant)

        # Window management
        self.window_manager = WindowManager()
        self.keyboard_nav = KeyboardNavigationManager(self)
        self.focus_manager = FocusManager(self)
        self.transition_manager = TransitionManager()

        # Current section
        self.current_section = "live_ops"

        # Initialize UI
        self._setup_window()
        self._setup_theme()
        self._create_ui()
        self._setup_keyboard_shortcuts()
        self._setup_accessibility()

        # Restore window state
        self.window_manager.restore_window_state(self, default_width=1440, default_height=900)

    def _setup_window(self):
        """Configure main window properties."""
        if QT_AVAILABLE:
            self.setWindowTitle("HQ Command Console")
            self.setMinimumSize(1024, 600)  # Minimum for responsive layout

    def _setup_theme(self):
        """Apply theme to application."""
        if QT_AVAILABLE:
            # Build and set palette
            palette = build_palette(self.current_theme.variant)
            self.setPalette(palette)

            # Apply component styles
            stylesheet = component_styles(self.current_theme.variant)
            self.setStyleSheet(stylesheet)

    def _create_ui(self):
        """Create main UI layout."""
        if not QT_AVAILABLE:
            return

        # Central widget with main layout
        central = QWidget(self)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Navigation Rail (left)
        self.nav_rail = NavigationRail(central)
        self.nav_rail.section_changed.connect(self._on_section_changed)
        main_layout.addWidget(self.nav_rail)

        # 2. Content area (status bar + mission canvas)
        content_widget = QWidget(central)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # 2a. Global Status Bar (top)
        self.status_bar = GlobalStatusBar(content_widget)
        content_layout.addWidget(self.status_bar)

        # 2b. Stacked widget for different sections
        self.section_stack = QStackedWidget(content_widget)
        content_layout.addWidget(self.section_stack)

        # Create section views
        self._create_section_views()

        main_layout.addWidget(content_widget, 1)  # Stretch to fill

        # 3. Context Drawer (right overlay)
        self.context_drawer = ContextDrawer(central)
        self.context_drawer.hide()  # Initially hidden
        # Position drawer (will be positioned properly in resizeEvent)

        self.setCentralWidget(central)

    def _create_section_views(self):
        """Create views for each navigation section."""
        if not QT_AVAILABLE:
            return

        # Live Ops Section (default view with panes)
        live_ops_view = self._create_live_ops_view()
        self.section_stack.addWidget(live_ops_view)
        self.section_views = {"live_ops": 0}

        # Task Board Section
        task_board_view = self._create_task_board_view()
        self.section_stack.addWidget(task_board_view)
        self.section_views["task_board"] = 1

        # Telemetry Section
        telemetry_view = self._create_telemetry_view()
        self.section_stack.addWidget(telemetry_view)
        self.section_views["telemetry"] = 2

        # Audit Section (placeholder)
        audit_view = self._create_placeholder_view("Audit Trails", "Coming in Phase 6")
        self.section_stack.addWidget(audit_view)
        self.section_views["audit"] = 3

        # Admin Section (placeholder)
        admin_view = self._create_placeholder_view("Admin", "Coming in Phase 7")
        self.section_stack.addWidget(admin_view)
        self.section_views["admin"] = 4

    def _create_live_ops_view(self) -> QWidget:
        """Create Live Ops view with 2-column mission canvas."""
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)

        # Mission canvas with 2 columns
        canvas = MissionCanvas(view)

        # Left column: Roster + Task Queue
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(theme.SPACING_MD)

        self.roster_pane = RosterPane(self.controller.roster_model, left_container)
        self.task_pane = TaskQueuePane(self.controller.task_queue_model, left_container)

        left_layout.addWidget(self.roster_pane)
        left_layout.addWidget(self.task_pane)

        canvas.add_to_left(left_container)

        # Right column: Telemetry
        self.telemetry_pane = TelemetryPane(self.controller.telemetry_model, canvas.right_panel)
        canvas.add_to_right(self.telemetry_pane)

        layout.addWidget(canvas)

        return view

    def _create_task_board_view(self) -> QWidget:
        """Create Task Board view (Kanban-style, Phase 2)."""
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(theme.SPACING_MD, theme.SPACING_MD, theme.SPACING_MD, theme.SPACING_MD)

        card = Card()
        card.add_widget(Heading("Task Board", level=2))
        card.add_widget(QLabel("Kanban-style task board coming in Phase 2"))

        layout.addWidget(card)
        layout.addStretch(1)

        return view

    def _create_telemetry_view(self) -> QWidget:
        """Create Telemetry view (detailed analytics, Phase 2)."""
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(theme.SPACING_MD, theme.SPACING_MD, theme.SPACING_MD, theme.SPACING_MD)

        card = Card()
        card.add_widget(Heading("Telemetry Dashboard", level=2))
        card.add_widget(QLabel("Detailed telemetry and analytics coming in Phase 2"))

        layout.addWidget(card)
        layout.addStretch(1)

        return view

    def _create_placeholder_view(self, title: str, message: str) -> QWidget:
        """Create placeholder view for future sections."""
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(theme.SPACING_MD, theme.SPACING_MD, theme.SPACING_MD, theme.SPACING_MD)

        card = Card()
        card.add_widget(Heading(title, level=2))
        card.add_widget(QLabel(message))

        layout.addWidget(card)
        layout.addStretch(1)

        return view

    def _setup_keyboard_shortcuts(self):
        """Set up keyboard navigation shortcuts."""
        if not QT_AVAILABLE:
            return

        callbacks = {
            "nav_live_ops": lambda: self._on_section_changed("live_ops"),
            "nav_task_board": lambda: self._on_section_changed("task_board"),
            "nav_telemetry": lambda: self._on_section_changed("telemetry"),
            "nav_audit": lambda: self._on_section_changed("audit"),
            "nav_admin": lambda: self._on_section_changed("admin"),
            "refresh": self.refresh,
            "toggle_drawer": self.context_drawer.toggle_drawer,
            "fullscreen": lambda: self.window_manager.toggle_fullscreen(self),
        }

        self.keyboard_nav.setup_default_shortcuts(callbacks)

    def _setup_accessibility(self):
        """Set up accessibility features."""
        if not QT_AVAILABLE:
            return

        # Apply accessibility enhancements
        setup_accessibility(self)

        # Set accessible names for major components
        self.nav_rail.setAccessibleName("Navigation")
        self.status_bar.setAccessibleName("Status Bar")
        self.context_drawer.setAccessibleName("Context Drawer")

    def _on_section_changed(self, section_id: str):
        """Handle navigation section change."""
        if section_id not in self.section_views:
            return

        self.current_section = section_id
        index = self.section_views[section_id]

        # Animate transition
        if self.section_stack.currentIndex() != index:
            old_widget = self.section_stack.currentWidget()
            self.section_stack.setCurrentIndex(index)
            new_widget = self.section_stack.currentWidget()

            # Crossfade animation
            if old_widget and new_widget:
                self.transition_manager.crossfade(old_widget, new_widget)

    def refresh(self) -> None:
        """
        Rebind models in case the controller replaced them.

        Refreshes all data views.
        """
        if QT_AVAILABLE and hasattr(self, 'roster_pane'):
            self.roster_pane.set_model(self.controller.roster_model)
            self.task_pane.set_model(self.controller.task_queue_model)
            self.telemetry_pane.set_model(self.controller.telemetry_model)

            # Update status bar
            self._update_status_bar()

    def _update_status_bar(self):
        """Update status bar with current system state."""
        # TODO: Update with real data from controller
        # For now, use placeholder data
        from .components import StatusType

        self.status_bar.set_sync_status("Synced", StatusType.SUCCESS)
        self.status_bar.set_escalation_count(0)
        self.status_bar.set_comms_status("Connected", StatusType.SUCCESS)

    def show_error(self, message: str):
        """
        Display error message in context drawer.

        Args:
            message: Error message to display
        """
        if not QT_AVAILABLE:
            return

        self.context_drawer.clear_content()
        self.context_drawer.set_title("Error")
        error_widget = ErrorMessage(message)
        self.context_drawer.add_content(error_widget)
        self.context_drawer.open_drawer()

    def show_loading(self, message: str = "Loading..."):
        """
        Display loading indicator in context drawer.

        Args:
            message: Loading message
        """
        if not QT_AVAILABLE:
            return

        self.context_drawer.clear_content()
        self.context_drawer.set_title("Loading")

        loading_card = Card()
        loading_card.add_widget(QLabel(message))
        loading_card.add_widget(LoadingSpinner())

        self.context_drawer.add_content(loading_card)
        self.context_drawer.open_drawer()

    def switch_theme(self, variant: ThemeVariant):
        """
        Switch to a different theme variant.

        Args:
            variant: Theme variant to switch to
        """
        if not QT_AVAILABLE:
            return

        self.current_theme = Theme(variant)
        self._setup_theme()

    def resizeEvent(self, event):
        """Handle window resize to position context drawer."""
        super().resizeEvent(event)

        if QT_AVAILABLE and hasattr(self, 'context_drawer'):
            # Position drawer at right edge
            parent_width = self.centralWidget().width()
            if self.context_drawer.is_open:
                self.context_drawer.move(
                    parent_width - theme.CONTEXT_DRAWER_WIDTH,
                    theme.STATUS_BAR_HEIGHT
                )
            else:
                self.context_drawer.move(
                    parent_width,
                    theme.STATUS_BAR_HEIGHT
                )

    def closeEvent(self, event):
        """Handle window close to save state."""
        if QT_AVAILABLE:
            self.window_manager.save_window_state(self)
        super().closeEvent(event)
