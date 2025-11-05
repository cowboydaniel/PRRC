"""
HQ Command GUI Main Window.

Implements Phase 1 layout structure with:
- Navigation Rail (left, 72px)
- Global Status Bar (top, 56px)
- Mission Canvas (center, 2-column 55%/45%)
- Context Drawer (right overlay, 360px)
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any, Mapping
from collections import Counter
from pathlib import Path
import logging

from .controller import HQCommandController
from .qt_compat import (
    Qt,
    QtWidgets,
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    qt_exec,
)

# Phase 1 imports
from .styles import theme, build_palette, component_styles, ThemeVariant, Theme
from .layouts import NavigationRail, GlobalStatusBar, MissionCanvas, ContextDrawer, NavSection
from .components import (
    Heading,
    Card,
    ErrorMessage,
    LoadingSpinner,
    Button,
    ButtonVariant,
    StatusType,
    Select,
)
from .window_manager import WindowManager
from .accessibility import KeyboardNavigationManager, FocusManager, setup_accessibility
from .animations import AnimationBuilder, TransitionManager

# Phase 2 imports - Enhanced panes and views
from .enhanced_panes import RosterPane, TaskQueuePane, TelemetryPane
from .kanban import KanbanBoard
from .timeline import TimelineView

# Phase 3 imports - Interactive workflows
from .workflows import (
    ManualAssignmentDialog,
    BulkAssignmentDialog,
    TaskCreationDialog,
    TaskEditDialog,
    TaskEscalationDialog,
    TaskDeferralDialog,
    ResponderStatusDialog,
    ResponderProfileDialog,
    ResponderCreationDialog,
    CallIntakeDialog,
    CallCorrelationDialog,
    UnitRecommendation,
)
from .notifications import (
    NotificationBadge,
    NotificationPanel,
    NotificationManager,
    Notification,
    NotificationType,
)
from .search_filter import (
    GlobalSearchBar,
    SearchResultsPanel,
    FilterManager,
    FilterPresetsPanel,
    ContextDrawerManager,
    FilterPreset,
)

from hq_command.security import build_default_role_context, RoleContext

logger = logging.getLogger(__name__)


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
        *,
        role_context: RoleContext | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.current_theme = Theme(theme_variant)

        operator_roles = controller.operator_roles()
        active_role = controller.operator_active_role()
        self.role_context: RoleContext = role_context or build_default_role_context(
            assigned_roles=operator_roles if operator_roles else None,
            active_role=active_role,
        )
        self.role_registry = self.role_context.registry
        self.operator_profile = dict(controller.operator_profile())

        # Window management
        self.window_manager = WindowManager()
        self.keyboard_nav = KeyboardNavigationManager(self)
        self.focus_manager = FocusManager(self)
        self.transition_manager = TransitionManager()

        # Current section
        self.current_section = "live_ops"

        # Phase 3 - Notification and filter managers
        self.filter_manager = FilterManager()
        self.drawer_content_manager = None  # Initialized after UI creation
        self.filter_presets_panel: Optional[FilterPresetsPanel] = None
        self._active_preset_context: Optional[str] = None
        self.call_log: List[Dict[str, Any]] = []
        self.role_selector: Optional[Select] = None
        self.role_matrix_table: Optional[QTableWidget] = None
        self.role_assignment_label: Optional[QLabel] = None
        self.active_role_summary: Optional[QLabel] = None

        # Initialize UI
        self._setup_window()
        self._setup_theme()
        self._create_ui()
        self._setup_keyboard_shortcuts()
        self._setup_accessibility()
        self._setup_context_menus()  # Phase 3

        # Restore window state
        self.window_manager.restore_window_state(self, default_width=1440, default_height=900)

        self._update_call_actions()
        self._apply_role_to_ui()

    def _setup_window(self):
        """Configure main window properties."""
        self.setWindowTitle("HQ Command Console")
        self.setMinimumSize(1024, 600)  # Minimum for responsive layout

    def _setup_theme(self):
        """Apply theme to application."""
        # Build and set palette
        palette = build_palette(self.current_theme.variant)
        self.setPalette(palette)

        # Apply component styles
        stylesheet = component_styles(self.current_theme.variant)
        self.setStyleSheet(stylesheet)

    def _create_ui(self):
        """Create main UI layout."""
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

        # 2a. Global Status Bar (top) with Phase 3 enhancements
        self.status_bar = GlobalStatusBar(content_widget)

        # Phase 3: Add search bar and notification badge to status bar
        self._enhance_status_bar()

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

        # Phase 3: Context drawer manager
        self.drawer_content_manager = ContextDrawerManager(self.context_drawer)
        self.filter_presets_panel = FilterPresetsPanel(self.filter_manager)
        self.filter_presets_panel.preset_applied.connect(self._on_filter_preset_applied)
        self.filter_presets_panel.preset_saved.connect(self._on_filter_preset_saved)

        self.setCentralWidget(central)

    def _create_section_views(self):
        """Create views for each navigation section."""
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

        # Audit Section (placeholder until Phase 6 integration)
        audit_view = self._create_placeholder_view("Audit Trails", "Compliance suite ready")
        self.section_stack.addWidget(audit_view)
        self.section_views["audit"] = 3

        # Admin Section (Phase 7 role-based workflows)
        admin_view = self._create_admin_view()
        self.section_stack.addWidget(admin_view)
        self.section_views["admin"] = 4

    def _create_live_ops_view(self) -> QWidget:
        """Create Live Ops view with 2-column mission canvas."""
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Mission canvas with 2 columns
        canvas = MissionCanvas(view)

        # Left column: Roster + Task Queue
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(theme.SPACING_LG)  # More comfortable spacing between panes

        self.roster_pane = RosterPane(self.controller.roster_model, left_container)
        self.task_pane = TaskQueuePane(self.controller.task_queue_model, left_container)

        self.roster_pane.filter_presets_requested.connect(
            lambda: self._show_filter_presets_panel("roster")
        )
        self.task_pane.filter_presets_requested.connect(
            lambda: self._show_filter_presets_panel("tasks")
        )
        self.task_pane.bulk_assign_requested.connect(self._show_bulk_assignment_dialog)

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

        # Kanban board with task data
        self.kanban_board = KanbanBoard(view)
        self.kanban_board.task_clicked.connect(self._on_kanban_task_clicked)

        layout.addWidget(self.kanban_board)

        return view

    def _create_telemetry_view(self) -> QWidget:
        """Create Telemetry view (detailed analytics and timeline, Phase 2)."""
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(theme.SPACING_MD, theme.SPACING_MD, theme.SPACING_MD, theme.SPACING_MD)

        # Timeline view for situational awareness
        self.timeline_view = TimelineView(view)
        self.timeline_view.export_requested.connect(self._on_timeline_export_requested)

        layout.addWidget(self.timeline_view)

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

    def _create_admin_view(self) -> QWidget:
        """Create the role management admin view (Phase 7)."""

        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(
            theme.SPACING_LG,
            theme.SPACING_LG,
            theme.SPACING_LG,
            theme.SPACING_LG,
        )
        layout.setSpacing(theme.SPACING_MD)

        layout.addWidget(Heading("Role-Based Access Control", level=2))

        overview_card = Card()
        overview_card.add_widget(
            QLabel(
                "Configure operator roles, review permissions, and launch training "
                "scenarios for each duty profile."
            )
        )
        layout.addWidget(overview_card)

        matrix_card = Card()
        matrix_card.add_widget(Heading("Role Permission Matrix", level=3))
        table = QTableWidget()
        definitions = list(self.role_registry.roles())
        table.setColumnCount(3)
        table.setRowCount(len(definitions))
        table.setHorizontalHeaderLabels(["Role", "Permissions", "Navigation Access"])
        for row, role in enumerate(definitions):
            name_item = QTableWidgetItem(role.display_name)
            name_item.setData(Qt.UserRole, role.identifier)
            table.setItem(row, 0, name_item)

            permissions = sorted(role.permissions)
            permission_text = ", ".join(permissions)
            perm_item = QTableWidgetItem(permission_text)
            perm_item.setToolTip("\n".join(permissions))
            table.setItem(row, 1, perm_item)

            section_labels = ", ".join(self._format_section_label(section) for section in role.navigation_sections)
            section_item = QTableWidgetItem(section_labels)
            section_item.setToolTip(section_labels)
            table.setItem(row, 2, section_item)

        table.resizeColumnsToContents()
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        matrix_card.add_widget(table)
        layout.addWidget(matrix_card)
        self.role_matrix_table = table

        operator_card = Card()
        operator_card.add_widget(Heading("Operator Profile", level=3))
        operator_name = self.operator_profile.get("name") if isinstance(self.operator_profile, Mapping) else None
        operator_label = QLabel(f"Operator: {operator_name or 'Active Operator'}")
        operator_card.add_widget(operator_label)

        self.role_assignment_label = QLabel()
        operator_card.add_widget(self.role_assignment_label)

        self.active_role_summary = QLabel()
        operator_card.add_widget(self.active_role_summary)

        training_button = Button("Launch Training Scenario", ButtonVariant.PRIMARY)
        training_button.clicked.connect(self._launch_training_mode)
        operator_card.add_widget(training_button)

        layout.addWidget(operator_card)

        layout.addStretch(1)
        return view

    def _format_section_label(self, section_id: str) -> str:
        """Return a human-readable label for a navigation section."""

        for section in NavSection:
            if section.value[0] == section_id:
                return section.value[1]
        return section_id.replace("_", " ").title()

    def _setup_keyboard_shortcuts(self):
        """Set up keyboard navigation shortcuts (Phase 1 + Phase 3 enhancements)."""
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

        # Phase 3: Additional shortcuts (3-18)
        self._setup_phase3_shortcuts()

    def _setup_accessibility(self):
        """Set up accessibility features."""
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

        if not self.role_context.is_section_allowed(section_id):
            warning = (
                f"{self.role_context.active_role.display_name} role cannot access "
                f"{self._format_section_label(section_id)}."
            )
            if hasattr(self, "notification_manager") and self.notification_manager:
                self.notification_manager.add_warning_notification(
                    "Access Restricted",
                    warning,
                )
            self.nav_rail.set_active_section(self.current_section, emit=False)
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
        if hasattr(self, 'roster_pane'):
            # Refresh enhanced panes (Phase 2)
            self.roster_pane.refresh()
            self.task_pane.refresh()
            self.telemetry_pane.refresh()

            # Refresh Kanban board if exists
            if hasattr(self, 'kanban_board'):
                task_data = self.controller.task_queue_model.items()
                self.kanban_board.set_tasks(task_data)

            # Update status bar
            self._update_status_bar()
            self._update_admin_view()

    def _update_status_bar(self):
        """Update status bar with current system state."""
        self.status_bar.set_sync_status("Synced", StatusType.SUCCESS)
        self.status_bar.set_escalation_count(0)
        self.status_bar.set_comms_status("Connected", StatusType.SUCCESS)
        self.status_bar.set_active_role(self.role_context.active_role.display_name)
        self.status_bar.set_permission_summary(
            len(self.role_context.permissions_for_active_role())
        )

    def _populate_role_selector(self) -> None:
        """Populate the role selector with assigned roles."""

        if not self.role_selector:
            return

        self.role_selector.blockSignals(True)
        self.role_selector.clear()

        for role_id in self.role_context.assigned_roles:
            definition = self.role_registry.get(role_id)
            self.role_selector.addItem(definition.display_name, role_id)

        active_role_id = self.role_context.active_role_id
        index = self.role_selector.findData(active_role_id)
        if index >= 0:
            self.role_selector.setCurrentIndex(index)
        elif self.role_selector.count() == 0:
            # Ensure the active role is visible even if not explicitly assigned.
            definition = self.role_context.active_role
            self.role_selector.addItem(definition.display_name, definition.identifier)
            self.role_selector.setCurrentIndex(0)

        self.role_selector.setEnabled(self.role_selector.count() > 1)
        self.role_selector.blockSignals(False)

    def _apply_role_to_ui(self) -> None:
        """Apply active role customizations to navigation and status."""

        self._populate_role_selector()

        active_role = self.role_context.active_role
        allowed_sections = list(active_role.navigation_sections)
        if not allowed_sections:
            fallback = active_role.default_section or NavSection.LIVE_OPS.value[0]
            allowed_sections = [fallback]

        requested_section = (
            self.current_section
            if self.current_section in allowed_sections
            else active_role.default_section or allowed_sections[0]
        )
        self.current_section = requested_section
        self.nav_rail.configure_sections(allowed_sections, active=requested_section)
        self.status_bar.set_active_role(active_role.display_name)
        self.status_bar.set_permission_summary(
            len(self.role_context.permissions_for_active_role())
        )
        self._update_admin_view()

    def _update_admin_view(self) -> None:
        """Refresh admin view elements based on the active role."""

        if self.role_matrix_table:
            active_role_id = self.role_context.active_role_id
            self.role_matrix_table.blockSignals(True)
            self.role_matrix_table.clearSelection()
            for row in range(self.role_matrix_table.rowCount()):
                item = self.role_matrix_table.item(row, 0)
                if item is None:
                    continue
                is_active = item.data(Qt.UserRole) == active_role_id
                font = item.font()
                font.setBold(is_active)
                item.setFont(font)
                if is_active:
                    self.role_matrix_table.selectRow(row)
            self.role_matrix_table.blockSignals(False)

        if self.role_assignment_label:
            assigned_names = ", ".join(
                self.role_registry.get(role_id).display_name
                for role_id in self.role_context.assigned_roles
            )
            self.role_assignment_label.setText(
                f"Assigned Roles: {assigned_names or self.role_context.active_role.display_name}"
            )

        if self.active_role_summary:
            active_role = self.role_context.active_role
            self.active_role_summary.setText(
                f"Active Role: {active_role.display_name} – {len(active_role.permissions)} permissions"
            )

    def _on_role_selection_changed(self, index: int) -> None:
        """Handle operator role switching from the status bar."""

        if not self.role_selector:
            return
        role_id = self.role_selector.itemData(index)
        if not role_id or role_id == self.role_context.active_role_id:
            return
        try:
            self.role_context.switch_role(str(role_id))
        except KeyError:
            if hasattr(self, "notification_manager") and self.notification_manager:
                self.notification_manager.add_warning_notification(
                    "Unknown Role",
                    f"Role '{role_id}' is not available in this environment.",
                )
            return

        self._apply_role_to_ui()

        if hasattr(self, "notification_manager") and self.notification_manager:
            self.notification_manager.add_info_notification(
                "Role Switched",
                f"Now operating as {self.role_context.active_role.display_name}.",
            )

    def _launch_training_mode(self) -> None:
        """Simulate launching the training mode for the active role."""

        role = self.role_context.active_role
        permission_preview = ", ".join(sorted(role.permissions)[:5])
        if len(role.permissions) > 5:
            permission_preview += ", …"
        message = (
            f"Training scenario queued for {role.display_name}."
            f" Focus areas: {permission_preview or 'Baseline orientation'}."
        )
        if hasattr(self, "notification_manager") and self.notification_manager:
            self.notification_manager.add_info_notification("Training Mode", message)
        else:
            self.status_bar.set_comms_status("Training queued", StatusType.INFO)

    def _update_call_actions(self) -> None:
        """Enable or disable call correlation actions based on history."""
        has_pairs = len(self.call_log) > 1
        if hasattr(self, "correlation_button"):
            self.correlation_button.setEnabled(has_pairs)

    def show_error(self, message: str):
        """
        Display error message in context drawer.

        Args:
            message: Error message to display
        """
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
        self.current_theme = Theme(variant)
        self._setup_theme()

    def resizeEvent(self, event):
        """Handle window resize to position context drawer."""
        super().resizeEvent(event)

        if hasattr(self, 'context_drawer'):
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

    def _on_kanban_task_clicked(self, status: str, task_id: str):
        """
        Handle Kanban board task click.

        Args:
            status: Column/status where task was clicked
            task_id: ID of clicked task
        """
        # Show task details in context drawer
        self.context_drawer.clear_content()
        self.context_drawer.set_title(f"Task: {task_id}")

        # TODO: Phase 3 - Add detailed task view
        task_info = Card()
        task_info.add_widget(Heading(f"Task {task_id}", level=4))
        task_info.add_widget(QLabel(f"Status: {status}"))
        task_info.add_widget(QLabel("Detailed task view coming in Phase 3"))

        self.context_drawer.add_content(task_info)
        self.context_drawer.open_drawer()

    def _on_timeline_export_requested(self):
        """Handle timeline export request."""
        # TODO: Phase 3 - Implement export dialog
        # For now, just show message
        self.show_loading("Exporting timeline... (Feature coming in Phase 3)")

    def closeEvent(self, event):
        """Handle window close to save state."""
        self.window_manager.save_window_state(self)
        super().closeEvent(event)

    # =========================================================================
    # PHASE 3: INTERACTIVE WORKFLOWS
    # =========================================================================

    def _enhance_status_bar(self):
        """Enhance status bar with search and notifications (Phase 3)."""
        # Role selector (Phase 7)
        self.role_selector = Select()
        self.role_selector.setToolTip("Switch active operator role")
        self.role_selector.setMinimumWidth(200)
        self.role_selector.currentIndexChanged.connect(self._on_role_selection_changed)
        self.status_bar.layout().insertWidget(1, self.role_selector)
        self._populate_role_selector()

        # Add search bar (3-15)
        self.search_bar = GlobalSearchBar()
        self.search_bar.search_requested.connect(self._on_search_requested)
        self.status_bar.layout().insertWidget(2, self.search_bar, 1)

        # Call correlation shortcut button (3-13)
        self.correlation_button = Button("Correlate Calls", ButtonVariant.SECONDARY)
        self.correlation_button.setEnabled(False)
        self.correlation_button.clicked.connect(self._show_call_correlation_dialog)
        self.status_bar.layout().insertWidget(3, self.correlation_button)

        # Add notification badge (3-17)
        self.notification_badge = NotificationBadge()
        self.notification_badge.clicked.connect(self._show_notifications)
        self.status_bar.layout().addWidget(self.notification_badge)

        # Create notification panel (hidden initially)
        self.notification_panel = NotificationPanel()
        self.notification_manager = NotificationManager(self.notification_panel)

        # Connect notification signals
        self.notification_panel.notification_dismissed.connect(self._on_notification_dismissed)
        self.notification_panel.notification_action.connect(self._on_notification_action)

    def _setup_phase3_shortcuts(self):
        """Set up Phase 3 keyboard shortcuts (3-18)."""
        from .qt_compat import QShortcut, QKeySequence

        if not QShortcut or not QKeySequence:
            return

        # Global search (Ctrl+F)
        search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        search_shortcut.activated.connect(self.search_bar.set_focus)

        # Create new task (Ctrl+N)
        new_task_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        new_task_shortcut.activated.connect(self._show_task_creation_dialog)

        # Call intake (Ctrl+I)
        call_intake_shortcut = QShortcut(QKeySequence("Ctrl+I"), self)
        call_intake_shortcut.activated.connect(self._show_call_intake_dialog)

        # Create new responder (Ctrl+Shift+R)
        new_responder_shortcut = QShortcut(QKeySequence("Ctrl+Shift+R"), self)
        new_responder_shortcut.activated.connect(self._show_responder_creation_dialog)

        # Show notifications (Ctrl+Shift+N)
        notifications_shortcut = QShortcut(QKeySequence("Ctrl+Shift+N"), self)
        notifications_shortcut.activated.connect(self._show_notifications)

    def _setup_context_menus(self):
        """Set up context menus for tasks and responders (3-19)."""
        # Task pane context menu
        if hasattr(self, 'task_pane'):
            self.task_pane.setContextMenuPolicy(Qt.CustomContextMenu)
            self.task_pane.customContextMenuRequested.connect(self._show_task_context_menu)

        # Roster pane context menu
        if hasattr(self, 'roster_pane'):
            self.roster_pane.setContextMenuPolicy(Qt.CustomContextMenu)
            self.roster_pane.customContextMenuRequested.connect(self._show_responder_context_menu)

    def _show_task_context_menu(self, position):
        """Show context menu for tasks (3-19)."""
        from .qt_compat import QMenu

        if not QMenu:
            return

        # Get selected task (simplified)
        menu = QMenu(self)

        assign_action = menu.addAction("Assign Units...")
        assign_action.triggered.connect(lambda: self._show_assignment_dialog("TASK-001"))

        edit_action = menu.addAction("Edit Task...")
        edit_action.triggered.connect(lambda: self._show_task_edit_dialog({}))

        escalate_action = menu.addAction("Escalate...")
        escalate_action.triggered.connect(lambda: self._show_escalation_dialog("TASK-001"))

        defer_action = menu.addAction("Defer...")
        defer_action.triggered.connect(lambda: self._show_deferral_dialog("TASK-001"))

        qt_exec(menu, self.task_pane.mapToGlobal(position))

    def _show_responder_context_menu(self, position):
        """Show context menu for responders (3-19)."""
        from .qt_compat import QMenu

        if not QMenu:
            return

        menu = QMenu(self)

        new_responder_action = menu.addAction("New Responder...")
        new_responder_action.triggered.connect(self._show_responder_creation_dialog)

        menu.addSeparator()

        status_action = menu.addAction("Change Status...")
        status_action.triggered.connect(lambda: self._show_status_dialog("UNIT-001"))

        profile_action = menu.addAction("Edit Profile...")
        profile_action.triggered.connect(lambda: self._show_profile_dialog({}))

        qt_exec(menu, self.roster_pane.mapToGlobal(position))

    # -------------------------------------------------------------------------
    # Search and Filter (3-14, 3-15, 3-16)
    # -------------------------------------------------------------------------

    def _on_search_requested(self, query: str, scope: str):
        """Handle search request (3-15)."""
        # Perform search across data
        results = self._perform_search(query, scope)

        # Show results in context drawer
        self.context_drawer.clear_content()
        self.context_drawer.set_title("Search Results")

        results_panel = SearchResultsPanel()
        results_panel.set_results(query, results)
        results_panel.result_selected.connect(self._on_search_result_selected)

        self.context_drawer.add_content(results_panel)
        self.context_drawer.open_drawer()

    def _perform_search(self, query: str, scope: str) -> List[Dict[str, Any]]:
        """Perform search across tasks, responders, and calls (3-15)."""
        results = []
        query_lower = query.lower()

        # Search tasks
        if scope in ('all', 'tasks'):
            tasks = self.controller.task_queue_model.items()
            for task in tasks:
                task_id = task.get('task_id', '').lower()
                location = task.get('location', '').lower()
                if query_lower in task_id or query_lower in location:
                    results.append({
                        'type': 'task',
                        'id': task.get('task_id', ''),
                        'priority': task.get('priority', ''),
                        'location': task.get('location', ''),
                        'data': task,
                    })

        # Search responders
        if scope in ('all', 'responders'):
            responders = self.controller.roster_model.items()
            for responder in responders:
                unit_id = responder.get('unit_id', '').lower()
                caps = ' '.join(responder.get('capabilities', [])).lower()
                if query_lower in unit_id or query_lower in caps:
                    results.append({
                        'type': 'responder',
                        'id': responder.get('unit_id', ''),
                        'status': responder.get('status', ''),
                        'capabilities': responder.get('capabilities', []),
                        'data': responder,
                    })

        return results

    def _on_search_result_selected(self, result_type: str, result_data: Dict[str, Any]):
        """Handle search result selection (3-15)."""
        # Show detailed view based on type
        if result_type == 'task':
            self._show_task_details(result_data.get('data', {}))
        elif result_type == 'responder':
            self._show_responder_details(result_data.get('data', {}))

    # -------------------------------------------------------------------------
    # Workflow Dialogs (3-00 to 3-13)
    # -------------------------------------------------------------------------

    def _show_assignment_dialog(self, task_id: str):
        """Show manual assignment dialog (3-00 to 3-04)."""
        # Get task data
        task_data = self._get_task_data(task_id)
        if not task_data:
            return

        # Get available units
        available_units = [
            r for r in self.controller.roster_model.items()
            if r.get('status') == 'available'
        ]

        # Generate recommendations (simplified)
        recommendations = self._generate_unit_recommendations(task_data, available_units)

        # Show dialog
        dialog = ManualAssignmentDialog(
            task_id,
            task_data,
            available_units,
            recommendations,
            self,
        )

        dialog.assignment_confirmed.connect(self._on_assignment_confirmed)
        qt_exec(dialog)

    def _show_bulk_assignment_dialog(self, task_ids: List[str]) -> None:
        """Show the bulk assignment dialog for multiple tasks (3-02)."""
        tasks: List[Dict[str, Any]] = []
        for task_id in task_ids:
            task_data = self._get_task_data(task_id)
            if task_data:
                tasks.append(task_data)

        if not tasks:
            return

        available_units = [
            r for r in self.controller.roster_model.items()
            if r.get('status') == 'available'
        ]

        recommendations = {
            task.get('task_id', ''): self._generate_unit_recommendations(task, available_units)
            for task in tasks
        }

        dialog = BulkAssignmentDialog(tasks, available_units, recommendations, self)
        dialog.bulk_assignment_confirmed.connect(self._on_bulk_assignment_confirmed)
        qt_exec(dialog)

    def _generate_unit_recommendations(
        self,
        task_data: Dict[str, Any],
        available_units: List[Dict[str, Any]],
    ) -> List[UnitRecommendation]:
        """Generate unit recommendations for assignment (3-01)."""
        recommendations = []
        required_caps = set(task_data.get('capabilities_required', []))

        for unit in available_units[:5]:  # Top 5
            unit_caps = set(unit.get('capabilities', []))
            match_score = len(required_caps & unit_caps) / max(len(required_caps), 1) * 100

            # Simple scoring
            score = match_score
            current_load = len(unit.get('current_tasks', []))
            max_capacity = unit.get('max_concurrent_tasks', 1)

            # Adjust score based on capacity
            if current_load < max_capacity:
                score += 10

            # Adjust for fatigue
            fatigue = unit.get('fatigue', 0.0)
            score -= (fatigue / 100) * 20

            reason = f"Capability match: {match_score:.0f}%, Load: {current_load}/{max_capacity}, Fatigue: {fatigue:.1f}"

            recommendations.append(UnitRecommendation(
                unit_id=unit.get('unit_id', ''),
                suitability_score=min(score, 100),
                capabilities=list(unit_caps),
                current_load=current_load,
                max_capacity=max_capacity,
                location=unit.get('location'),
                fatigue=fatigue,
                match_reason=reason,
            ))

        # Sort by score
        recommendations.sort(key=lambda r: r.suitability_score, reverse=True)

        return recommendations

    def _on_assignment_confirmed(self, task_id: str, unit_ids: List[str]):
        """Handle confirmed assignment (3-04)."""
        # Log assignment (audit trail would be captured here)
        logger.info(f"Assignment confirmed: Task {task_id} -> Units {unit_ids}")

        # Add notification
        self.notification_manager.add_assignment_notification(
            task_id,
            unit_ids,
            action_callback=lambda: self._show_task_details({'task_id': task_id}),
        )

        # Update notification badge
        self.notification_badge.set_unread_count(
            self.notification_panel.get_unread_count()
        )

        # Refresh data
        self.refresh()

    def _on_bulk_assignment_confirmed(self, assignments: Dict[str, List[str]]) -> None:
        """Handle confirmed bulk assignments."""
        for task_id, unit_ids in assignments.items():
            for unit_id in unit_ids:
                self.controller.apply_manual_assignment(task_id, unit_id)

            self.notification_manager.add_assignment_notification(
                task_id,
                unit_ids,
                action_callback=lambda tid=task_id: self._show_task_details({'task_id': tid}),
            )

        self.notification_badge.set_unread_count(
            self.notification_panel.get_unread_count()
        )

        analytics = {
            "Tasks Updated": len(assignments),
            "Units Affected": sum(len(units) for units in assignments.values()),
        }
        if self.drawer_content_manager:
            self.drawer_content_manager.show_analytics_summary(analytics)

        self.refresh()

    def _show_task_creation_dialog(self):
        """Show task creation dialog (3-05)."""
        dialog = TaskCreationDialog(self)
        dialog.task_created.connect(self._on_task_created)
        qt_exec(dialog)

    def _on_task_created(self, task_data: Dict[str, Any]):
        """Handle task creation (3-05)."""
        logger.info(f"Task created: {task_data}")

        # Add notification
        self.notification_manager.add_system_notification(
            "Task Created",
            f"Task {task_data.get('task_id')} has been created",
        )

        self.notification_badge.set_unread_count(
            self.notification_panel.get_unread_count()
        )

        self.refresh()

    def _show_task_edit_dialog(self, task_data: Dict[str, Any]):
        """Show task edit dialog (3-06)."""
        dialog = TaskEditDialog(task_data, self)
        dialog.task_updated.connect(self._on_task_updated)
        qt_exec(dialog)

    def _on_task_updated(self, task_id: str, updated_data: Dict[str, Any]):
        """Handle task update (3-06)."""
        logger.info(f"Task {task_id} updated: {updated_data}")

        self.notification_manager.add_system_notification(
            "Task Updated",
            f"Task {task_id} has been updated",
        )

        self.notification_badge.set_unread_count(
            self.notification_panel.get_unread_count()
        )

        self.refresh()

    def _show_escalation_dialog(self, task_id: str):
        """Show task escalation dialog (3-07)."""
        dialog = TaskEscalationDialog(task_id, self)
        dialog.escalation_confirmed.connect(self._on_escalation_confirmed)
        qt_exec(dialog)

    def _on_escalation_confirmed(self, task_id: str, reason: str):
        """Handle task escalation (3-07)."""
        logger.info(f"Task {task_id} escalated: {reason}")

        self.notification_manager.add_escalation_notification(
            task_id,
            reason,
            action_callback=lambda: self._show_task_details({'task_id': task_id}),
        )

        self.notification_badge.set_unread_count(
            self.notification_panel.get_unread_count()
        )

        # Update status bar escalation count
        escalation_count = self.status_bar.findChild(QLabel, "escalation_count")
        if escalation_count:
            current = int(escalation_count.text() or 0)
            self.status_bar.set_escalation_count(current + 1)

        self.refresh()

    def _show_deferral_dialog(self, task_id: str):
        """Show task deferral dialog (3-08)."""
        dialog = TaskDeferralDialog(task_id, self)
        dialog.deferral_confirmed.connect(self._on_deferral_confirmed)
        qt_exec(dialog)

    def _on_deferral_confirmed(self, task_id: str, reason: str, duration: int):
        """Handle task deferral (3-08)."""
        logger.info(f"Task {task_id} deferred for {duration} minutes: {reason}")

        self.notification_manager.add_system_notification(
            "Task Deferred",
            f"Task {task_id} deferred for {duration} minutes",
        )

        self.notification_badge.set_unread_count(
            self.notification_panel.get_unread_count()
        )

        self.refresh()

    def _show_status_dialog(self, unit_id: str):
        """Show responder status dialog (3-09)."""
        # Get current status
        responder = self._get_responder_data(unit_id)
        if not responder:
            return

        dialog = ResponderStatusDialog(
            unit_id,
            responder.get('status', 'available'),
            responder.get('fatigue', 0.0),
            self,
        )

        dialog.status_changed.connect(self._on_status_changed)
        qt_exec(dialog)

    def _on_status_changed(self, unit_id: str, changes: Dict[str, Any]):
        """Handle responder status change (3-09)."""
        logger.info(f"Status changed for {unit_id}: {changes}")

        self.notification_manager.add_system_notification(
            "Responder Status Changed",
            f"{unit_id} status updated to {changes.get('status')}",
        )

        self.notification_badge.set_unread_count(
            self.notification_panel.get_unread_count()
        )

        self.refresh()

    def _show_profile_dialog(self, unit_data: Dict[str, Any]):
        """Show responder profile dialog (3-10)."""
        dialog = ResponderProfileDialog(unit_data, self)
        dialog.profile_updated.connect(self._on_profile_updated)
        qt_exec(dialog)

    def _on_profile_updated(self, unit_id: str, updates: Dict[str, Any]):
        """Handle responder profile update (3-10)."""
        logger.info(f"Profile updated for {unit_id}: {updates}")

        self.notification_manager.add_system_notification(
            "Responder Profile Updated",
            f"{unit_id} profile has been updated",
        )

        self.notification_badge.set_unread_count(
            self.notification_panel.get_unread_count()
        )

        self.refresh()

    def _show_responder_creation_dialog(self):
        """Show responder creation dialog."""
        dialog = ResponderCreationDialog(self)
        dialog.responder_created.connect(self._on_responder_created)
        qt_exec(dialog)

    def _on_responder_created(self, responder_data: Dict[str, Any]):
        """Handle new responder creation."""
        logger.info(f"New responder created: {responder_data}")

        # TODO: Add responder to controller/data model
        # For now, just notify
        unit_id = responder_data.get('unit_id', 'Unknown')

        self.notification_manager.add_system_notification(
            "New Responder Created",
            f"{unit_id} has been added to the roster",
        )

        self.notification_badge.set_unread_count(
            self.notification_panel.get_unread_count()
        )

        self.refresh()

    def _show_call_intake_dialog(self):
        """Show call intake dialog (3-11 to 3-12)."""
        dialog = CallIntakeDialog(self)
        dialog.call_submitted.connect(self._on_call_submitted)
        dialog.task_generated.connect(self._on_task_created)
        qt_exec(dialog)

    def _on_call_submitted(self, call_data: Dict[str, Any]):
        """Handle call submission (3-11)."""
        logger.info(f"Call submitted: {call_data}")

        self.call_log.append(call_data)
        self._update_call_actions()

        if self.drawer_content_manager:
            self.drawer_content_manager.show_call_transcript(call_data)

        self.notification_manager.add_system_notification(
            "Call Received",
            f"Call {call_data.get('call_id')} logged: {call_data.get('incident_type')}",
        )

        self.notification_badge.set_unread_count(
            self.notification_panel.get_unread_count()
        )

    def _show_call_correlation_dialog(self) -> None:
        """Open the call correlation dialog for recent calls (3-13)."""
        if not self.call_log:
            self.show_error("No calls available for correlation yet.")
            return

        primary_call = self.call_log[-1]
        similar_calls = self._find_similar_calls(primary_call)

        if not similar_calls:
            self.show_error("No related calls found for the most recent entry.")
            return

        dialog = CallCorrelationDialog(primary_call, similar_calls, self)
        dialog.calls_linked.connect(self._on_calls_linked)
        qt_exec(dialog)

    def _find_similar_calls(self, primary_call: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return calls that appear related to the primary call."""
        primary_id = primary_call.get('call_id')
        primary_location = primary_call.get('location')
        primary_type = primary_call.get('incident_type')

        similar: List[Dict[str, Any]] = []
        for call in reversed(self.call_log[:-1]):
            if call.get('call_id') == primary_id:
                continue

            location_match = primary_location and call.get('location') == primary_location
            type_match = primary_type and call.get('incident_type') == primary_type

            if location_match or type_match:
                similar.append(call)

        return similar

    def _on_calls_linked(self, call_ids: List[str]) -> None:
        """Handle confirmation of correlated calls."""
        summary = ", ".join(call_ids)
        self.notification_manager.add_system_notification(
            "Calls Correlated",
            f"Linked calls: {summary}",
        )

        self.notification_badge.set_unread_count(
            self.notification_panel.get_unread_count()
        )

        if self.drawer_content_manager:
            self.drawer_content_manager.show_analytics_summary(
                {"Linked Calls": len(call_ids), "Primary": call_ids[0]}
            )

    # -------------------------------------------------------------------------
    # Notifications (3-17)
    # -------------------------------------------------------------------------

    def _show_notifications(self):
        """Show notifications panel in context drawer (3-17)."""
        self.context_drawer.clear_content()
        self.context_drawer.set_title("Notifications")
        self.context_drawer.add_content(self.notification_panel)
        self.context_drawer.open_drawer()

        # Mark all as read when opened
        # (This is optional behavior)

    def _on_notification_dismissed(self, notification_id: str):
        """Handle notification dismissal (3-17)."""
        self.notification_badge.set_unread_count(
            self.notification_panel.get_unread_count()
        )

    def _on_notification_action(self, notification_id: str):
        """Handle notification action (3-17)."""
        # Action callbacks are already executed
        # This is for additional tracking/logging
        pass

    def _show_filter_presets_panel(self, context: str) -> None:
        """Display the filter presets panel for the given context (3-16)."""
        if not self.filter_presets_panel:
            return

        self._active_preset_context = context

        context_title = "Task Queue" if context == "tasks" else "Responder Roster"
        self.filter_presets_panel.set_context(f"Applying to: {context_title}")
        self.filter_presets_panel.refresh()

        self.context_drawer.clear_content()
        self.context_drawer.set_title(f"{context_title} Presets")
        self.context_drawer.add_content(self.filter_presets_panel)
        self.context_drawer.open_drawer()

    def _on_filter_preset_applied(self, filters: Dict[str, Any]) -> None:
        """Apply filters from the presets panel to the active view."""
        if not self._active_preset_context:
            return

        if self._active_preset_context == "tasks":
            self.task_pane.apply_preset_filters(filters)
            filtered_tasks = self.task_pane.get_filtered_tasks()
            stats = Counter(task.get("priority", 0) for task in filtered_tasks)
            analytics = {
                "Visible Tasks": len(filtered_tasks),
                "P1": stats.get(1, 0),
                "P2": stats.get(2, 0),
            }
            if self.drawer_content_manager:
                self.drawer_content_manager.show_analytics_summary(analytics)
        elif self._active_preset_context == "roster":
            self.roster_pane.apply_preset_filters(filters)
            responders = self.roster_pane.get_filtered_responders()
            if self.drawer_content_manager:
                self.drawer_content_manager.show_responder_roster(responders)

    def _on_filter_preset_saved(self, _placeholder: str) -> None:
        """Persist the currently active filters as a new preset."""
        if not self._active_preset_context:
            return

        current_filters = self._collect_current_filters(self._active_preset_context)
        if not current_filters:
            return

        base = "Task" if self._active_preset_context == "tasks" else "Roster"
        preset_name = self._generate_preset_name(f"{base} Preset")
        description = f"Saved from {base.lower()} view"

        preset = FilterPreset(preset_name, current_filters, description)
        self.filter_manager.save_preset(preset)

        if self.filter_presets_panel:
            self.filter_presets_panel.refresh()

        self.notification_manager.add_system_notification(
            "Preset Saved",
            f"{preset_name} is now available",
        )
        self.notification_badge.set_unread_count(
            self.notification_panel.get_unread_count()
        )

    def _collect_current_filters(self, context: str) -> Dict[str, Any]:
        """Gather the current filter state for the active pane."""
        if context == "tasks":
            return self.task_pane.get_active_filters()
        if context == "roster":
            return self.roster_pane.get_active_filters()
        return {}

    def _generate_preset_name(self, base: str) -> str:
        """Generate a unique preset name based on the provided base."""
        existing = set(self.filter_manager.list_presets())
        index = 1
        candidate = f"{base} {index}"
        while candidate in existing:
            index += 1
            candidate = f"{base} {index}"
        return candidate

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _get_task_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task data by ID."""
        tasks = self.controller.task_queue_model.items()
        for task in tasks:
            if task.get('task_id') == task_id:
                return task
        return None

    def _get_responder_data(self, unit_id: str) -> Optional[Dict[str, Any]]:
        """Get responder data by ID."""
        responders = self.controller.roster_model.items()
        for responder in responders:
            if responder.get('unit_id') == unit_id:
                return responder
        return None

    def _show_task_details(self, task_data: Dict[str, Any]):
        """Show task details in context drawer."""
        self.context_drawer.clear_content()
        self.context_drawer.set_title(f"Task: {task_data.get('task_id', '')}")

        card = Card()
        card.add_widget(Heading("Task Details", level=4))
        card.add_widget(QLabel(f"Priority: {task_data.get('priority', '')}"))
        card.add_widget(QLabel(f"Location: {task_data.get('location', '')}"))
        card.add_widget(QLabel(f"Status: {task_data.get('status', '')}"))

        self.context_drawer.add_content(card)
        self.context_drawer.open_drawer()

    def _show_responder_details(self, responder_data: Dict[str, Any]):
        """Show responder details in context drawer."""
        self.context_drawer.clear_content()
        self.context_drawer.set_title(f"Responder: {responder_data.get('unit_id', '')}")

        card = Card()
        card.add_widget(Heading("Responder Details", level=4))
        card.add_widget(QLabel(f"Status: {responder_data.get('status', '')}"))
        card.add_widget(QLabel(f"Capabilities: {', '.join(responder_data.get('capabilities', []))}"))
        card.add_widget(QLabel(f"Fatigue: {responder_data.get('fatigue', 0.0):.1f}"))

        self.context_drawer.add_content(card)
        self.context_drawer.open_drawer()
