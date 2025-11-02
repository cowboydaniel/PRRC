"""
HQ Command GUI Main Window.

Implements Phase 1 layout structure with:
- Navigation Rail (left, 72px)
- Global Status Bar (top, 56px)
- Mission Canvas (center, 2-column 55%/45%)
- Context Drawer (right overlay, 360px)
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from pathlib import Path

from .controller import HQCommandController
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

# Phase 2 imports - Enhanced panes and views
from .enhanced_panes import RosterPane, TaskQueuePane, TelemetryPane
from .kanban import KanbanBoard
from .timeline import TimelineView

# Phase 3 imports - Interactive workflows
from .workflows import (
    ManualAssignmentDialog,
    TaskCreationDialog,
    TaskEditDialog,
    TaskEscalationDialog,
    TaskDeferralDialog,
    ResponderStatusDialog,
    ResponderProfileDialog,
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
)


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

        # Phase 3 - Notification and filter managers
        self.filter_manager = FilterManager()
        self.drawer_content_manager = None  # Initialized after UI creation

        # Initialize UI
        self._setup_window()
        self._setup_theme()
        self._create_ui()
        self._setup_keyboard_shortcuts()
        self._setup_accessibility()
        self._setup_context_menus()  # Phase 3

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

    def _setup_keyboard_shortcuts(self):
        """Set up keyboard navigation shortcuts (Phase 1 + Phase 3 enhancements)."""
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

        # Phase 3: Additional shortcuts (3-18)
        self._setup_phase3_shortcuts()

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
        if QT_AVAILABLE:
            self.window_manager.save_window_state(self)
        super().closeEvent(event)

    # =========================================================================
    # PHASE 3: INTERACTIVE WORKFLOWS
    # =========================================================================

    def _enhance_status_bar(self):
        """Enhance status bar with search and notifications (Phase 3)."""
        if not QT_AVAILABLE:
            return

        # Add search bar (3-15)
        self.search_bar = GlobalSearchBar()
        self.search_bar.search_requested.connect(self._on_search_requested)
        self.status_bar.layout().insertWidget(1, self.search_bar, 1)

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

        # Show notifications (Ctrl+Shift+N)
        notifications_shortcut = QShortcut(QKeySequence("Ctrl+Shift+N"), self)
        notifications_shortcut.activated.connect(self._show_notifications)

    def _setup_context_menus(self):
        """Set up context menus for tasks and responders (3-19)."""
        if not QT_AVAILABLE:
            return

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

        menu.exec_(self.task_pane.mapToGlobal(position))

    def _show_responder_context_menu(self, position):
        """Show context menu for responders (3-19)."""
        from .qt_compat import QMenu

        if not QMenu:
            return

        menu = QMenu(self)

        status_action = menu.addAction("Change Status...")
        status_action.triggered.connect(lambda: self._show_status_dialog("UNIT-001"))

        profile_action = menu.addAction("Edit Profile...")
        profile_action.triggered.connect(lambda: self._show_profile_dialog({}))

        menu.exec_(self.roster_pane.mapToGlobal(position))

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
        dialog.exec_()

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
        print(f"Assignment confirmed: Task {task_id} -> Units {unit_ids}")

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

    def _show_task_creation_dialog(self):
        """Show task creation dialog (3-05)."""
        dialog = TaskCreationDialog(self)
        dialog.task_created.connect(self._on_task_created)
        dialog.exec_()

    def _on_task_created(self, task_data: Dict[str, Any]):
        """Handle task creation (3-05)."""
        print(f"Task created: {task_data}")

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
        dialog.exec_()

    def _on_task_updated(self, task_id: str, updated_data: Dict[str, Any]):
        """Handle task update (3-06)."""
        print(f"Task {task_id} updated: {updated_data}")

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
        dialog.exec_()

    def _on_escalation_confirmed(self, task_id: str, reason: str):
        """Handle task escalation (3-07)."""
        print(f"Task {task_id} escalated: {reason}")

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
        dialog.exec_()

    def _on_deferral_confirmed(self, task_id: str, reason: str, duration: int):
        """Handle task deferral (3-08)."""
        print(f"Task {task_id} deferred for {duration} minutes: {reason}")

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
        dialog.exec_()

    def _on_status_changed(self, unit_id: str, changes: Dict[str, Any]):
        """Handle responder status change (3-09)."""
        print(f"Status changed for {unit_id}: {changes}")

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
        dialog.exec_()

    def _on_profile_updated(self, unit_id: str, updates: Dict[str, Any]):
        """Handle responder profile update (3-10)."""
        print(f"Profile updated for {unit_id}: {updates}")

        self.notification_manager.add_system_notification(
            "Responder Profile Updated",
            f"{unit_id} profile has been updated",
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
        dialog.exec_()

    def _on_call_submitted(self, call_data: Dict[str, Any]):
        """Handle call submission (3-11)."""
        print(f"Call submitted: {call_data}")

        self.notification_manager.add_system_notification(
            "Call Received",
            f"Call {call_data.get('call_id')} logged: {call_data.get('incident_type')}",
        )

        self.notification_badge.set_unread_count(
            self.notification_panel.get_unread_count()
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
