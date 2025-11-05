"""PySide6 application scaffolding for the FieldOps offline-first GUI."""
from __future__ import annotations

import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .controller import FieldOpsGUIController, SyncAdapter
from .state import (
    GPSFix,
    MissionAttachmentLink,
    MissionQuickLinks,
    MissionWorkspaceState,
    OperationalLogDraft,
    ResourceRequestBoardState,
    ResourceRequestCard,
    SyncResult,
    SyncState,
    TaskAssignmentCard,
    TaskColumnState,
    TaskDashboardState,
)
from .styles import (
    COLOR_TOKENS,
    TYPOGRAPHY,
    build_palette,
    component_styles,
    focus_ring_stylesheet,
    HORIZONTAL_PADDING_PX,
    MIN_CONTROL_HEIGHT_PX,
    SPACING_GRID_PX,
)
from ..hardware import enumerate_serial_interfaces, plan_touchscreen_calibration
from ..telemetry import TelemetrySnapshot, collect_telemetry_snapshot


@dataclass
class NavigationEntry:
    """Navigation metadata for the FieldOps GUI sections."""

    label: str
    widget: QWidget


class LocalEchoSyncAdapter(SyncAdapter):
    """In-memory sync adapter that echoes operations as applied."""

    def __init__(self) -> None:
        self._available = True

    def is_available(self) -> bool:  # pragma: no cover - thin wrapper
        return self._available

    def set_available(self, value: bool) -> None:
        self._available = value

    def push_operations(self, operations):  # type: ignore[override]
        applied = tuple(operation.operation_id for operation in operations)
        return SyncResult(
            applied_operation_ids=applied,
            conflicts=tuple(),
            errors=tuple(),
        )


class FieldOpsMainWindow(QMainWindow):
    """Primary PySide6 window coordinating FieldOps GUI views."""

    def __init__(
        self,
        controller: FieldOpsGUIController,
        *,
        telemetry_provider: Callable[[], TelemetrySnapshot] = collect_telemetry_snapshot,
        sync_adapter: LocalEchoSyncAdapter | None = None,
        demo_package: Path | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("FieldOps Command Tablet")
        self._controller = controller
        self._telemetry_provider = telemetry_provider
        self._sync_adapter = sync_adapter
        self._demo_package = demo_package
        self._state = controller.get_state()
        self._snapshot: TelemetrySnapshot | None = None
        self._styles = component_styles()

        self._stack = QStackedWidget()
        self._navigation_buttons: dict[str, QToolButton] = {}

        self._mission_view = MissionWorkspaceView(self._load_mission_package)
        self._log_view = OperationalLogView(self._submit_log)
        self._task_view = TaskDashboardView(self._apply_task_action)
        self._resource_view = ResourceBoardView(self._apply_resource_action)
        self._telemetry_view = TelemetryView()
        self._settings_view = SettingsView(self._toggle_offline_mode)

        self._navigation: Sequence[NavigationEntry] = (
            NavigationEntry("Mission", self._mission_view),
            NavigationEntry("Logs", self._log_view),
            NavigationEntry("Tasks", self._task_view),
            NavigationEntry("Resources", self._resource_view),
            NavigationEntry("Telemetry", self._telemetry_view),
            NavigationEntry("Settings", self._settings_view),
        )

        self._build_ui()
        self._apply_styles()
        self._install_actions()
        self._mission_view.set_load_demo_enabled(self._demo_package)
        self.resize(1280, 800)

        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(15_000)
        self._sync_timer.timeout.connect(self._perform_sync)  # type: ignore[arg-type]
        self._sync_timer.start()

        self._telemetry_timer = QTimer(self)
        self._telemetry_timer.setInterval(20_000)
        self._telemetry_timer.timeout.connect(self._refresh_telemetry)  # type: ignore[arg-type]
        self._telemetry_timer.start()

        if self._demo_package is not None:
            self._load_demo_data()
        self._refresh_state()
        self._refresh_telemetry()

    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)

        navigation_frame = QFrame()
        navigation_frame.setObjectName("NavigationRail")
        navigation_layout = QVBoxLayout(navigation_frame)
        navigation_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        navigation_layout.setSpacing(SPACING_GRID_PX)
        navigation_layout.setContentsMargins(
            SPACING_GRID_PX, SPACING_GRID_PX * 2, SPACING_GRID_PX, SPACING_GRID_PX * 2
        )

        button_widths: list[int] = []
        for index, entry in enumerate(self._navigation):
            button = QToolButton()
            button.setText(entry.label)
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setObjectName("NavigationRailButton")
            _apply_typography(button, "navigation_label")
            button.clicked.connect(lambda checked, i=index: self._set_active_page(i))  # type: ignore[arg-type]
            metrics = button.fontMetrics()
            label_width = metrics.horizontalAdvance(button.text())
            button_widths.append(
                label_width + (HORIZONTAL_PADDING_PX * 2) + (SPACING_GRID_PX * 2)
            )
            navigation_layout.addWidget(button)
            self._navigation_buttons[entry.label] = button
            self._stack.addWidget(entry.widget)
        navigation_layout.addStretch(1)

        if button_widths:
            navigation_width = max(button_widths)
            navigation_frame.setMinimumWidth(navigation_width)
            navigation_frame.setMaximumWidth(navigation_width)

        content_frame = QWidget()
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._top_bar = TopBar()
        content_layout.addWidget(self._top_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self._stack)
        content_layout.addWidget(scroll)

        root_layout.addWidget(navigation_frame)
        root_layout.addWidget(content_frame, 1)
        self.setCentralWidget(central)
        self._set_active_page(0)

    def _apply_styles(self) -> None:
        try:
            QApplication.instance().setPalette(build_palette())  # type: ignore[union-attr]
        except Exception:  # pragma: no cover - environment guard
            pass
        stylesheet = "\n".join(
            (
                focus_ring_stylesheet(),
                self._styles.navigation_rail,
                self._styles.top_bar,
                self._styles.mission_tab_bar,
                self._styles.offline_queue_row,
                self._styles.telemetry_card,
                self._styles.conflict_dialog,
            )
        )
        self.setStyleSheet(stylesheet)

    def _install_actions(self) -> None:
        if self._demo_package is None:
            return
        load_demo_action = QAction("Load Demo Mission", self)
        load_demo_action.triggered.connect(lambda: self._load_mission_package(str(self._demo_package)))  # type: ignore[arg-type]
        self.menuBar().addAction(load_demo_action)

    def _set_active_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        for i, entry in enumerate(self._navigation):
            self._navigation_buttons[entry.label].setChecked(i == index)

    def _load_mission_package(self, path: str | None = None) -> None:
        if not path:
            filename, _ = QFileDialog.getOpenFileName(
                self,
                "Select Mission Package",
                str(Path.home()),
                "Archives (*.zip *.tar *.tar.gz *.tgz *.tar.bz2 *.tbz2)",
            )
            path = filename or None
        if not path:
            return
        try:
            workspace = self._controller.ingest_mission_package(Path(path))
        except Exception as exc:  # pragma: no cover - GUI feedback
            QMessageBox.critical(self, "Mission Intake Failed", str(exc))
            return
        self._mission_view.update_workspace(workspace)
        self._refresh_state()

    def _submit_log(self, title: str, notes: str, category: str) -> None:
        draft = OperationalLogDraft(
            category=category,
            title=title,
            notes=notes,
            gps_fix=GPSFix(latitude=39.7392, longitude=-104.9903),
        )
        operation = self._controller.submit_operational_log(draft)
        self._log_view.show_submission(operation.operation_id)
        self._refresh_state()

    def _apply_task_action(
        self, task_id: str, action: str, metadata: dict[str, object] | None = None
    ) -> None:
        """Apply task action with validation and error feedback."""
        # Validate task_id
        if not task_id or not isinstance(task_id, str):
            QMessageBox.warning(
                self,
                "Invalid Task",
                "Invalid task ID. Please select a valid task."
            )
            return

        # Validate action
        valid_actions = {"accept", "decline", "complete", "cancel"}
        if action not in valid_actions:
            QMessageBox.warning(
                self,
                "Invalid Action",
                f"Invalid action '{action}'. Valid actions: {', '.join(valid_actions)}"
            )
            return

        # Validate metadata for completion action
        if action == "complete" and metadata:
            if "notes" in metadata and not isinstance(metadata["notes"], str):
                QMessageBox.warning(
                    self,
                    "Invalid Metadata",
                    "Completion notes must be a string."
                )
                return

        try:
            self._controller.apply_task_action(task_id, action, metadata=metadata)
            self._refresh_state()

            # Show success feedback
            action_past = {
                "accept": "accepted",
                "decline": "declined",
                "complete": "completed",
                "cancel": "cancelled"
            }.get(action, action)

            self._top_bar.set_mesh_message(f"Task {action_past} successfully")
        except Exception as e:
            QMessageBox.critical(
                self,
                "Task Action Failed",
                f"Failed to {action} task: {str(e)}\n\nPlease try again or contact support."
            )
            # Log the error for debugging
            import logging
            logging.error(f"Task action failed: {e}", exc_info=True)

    def _apply_resource_action(self, request_id: str, action: str) -> None:
        """Apply resource request action with validation and error feedback."""
        # Validate request_id
        if not request_id or not isinstance(request_id, str):
            QMessageBox.warning(
                self,
                "Invalid Request",
                "Invalid request ID. Please select a valid resource request."
            )
            return

        # Validate action
        valid_actions = {"fulfill", "cancel"}
        if action not in valid_actions:
            QMessageBox.warning(
                self,
                "Invalid Action",
                f"Invalid action '{action}'. Valid actions: {', '.join(valid_actions)}"
            )
            return

        try:
            self._controller.apply_resource_request_action(request_id, action)
            self._refresh_state()

            # Show success feedback
            action_past = {
                "fulfill": "fulfilled",
                "cancel": "cancelled"
            }.get(action, action)

            self._top_bar.set_mesh_message(f"Resource request {action_past} successfully")
        except Exception as e:
            QMessageBox.critical(
                self,
                "Resource Action Failed",
                f"Failed to {action} resource request: {str(e)}\n\nPlease try again or contact support."
            )
            # Log the error for debugging
            import logging
            logging.error(f"Resource action failed: {e}", exc_info=True)

    def _toggle_offline_mode(self, enabled: bool) -> None:
        if self._sync_adapter is not None:
            self._sync_adapter.set_available(not enabled)
        self._refresh_state()
        if enabled:
            self._top_bar.set_mesh_message("Offline mode enabled")
        else:
            self._top_bar.set_mesh_message("Mesh link active")

    def _load_demo_data(self) -> None:
        if self._demo_package is None:
            return
        demo_tasks = (
            TaskAssignmentCard(
                task_id="med-resupply",
                title="Stage Medical Resupply",
                status="pending",
                display_status="pending",
                priority="High",
                summary="Inventory and stage trauma resupply cache",
                assignee="N. Ellis",
            ),
            TaskAssignmentCard(
                task_id="mesh-survey",
                title="Run Mesh Health Survey",
                status="pending",
                display_status="pending",
                priority="Routine",
                summary="Sweep RuggedNet nodes for interference",
                assignee="I. Tran",
            ),
        )
        demo_requests = (
            ResourceRequestCard(
                request_id="generator-fuel",
                requester="FOB Charlie",
                summary="Refuel generator reserve",
                priority="Critical",
                status="pending",
                display_status="pending",
                quantity=4,
            ),
        )
        self._controller.update_task_assignments(demo_tasks)
        self._controller.update_resource_requests(demo_requests)
        try:
            self._controller.ingest_mission_package(self._demo_package)
        except Exception:
            pass

    def _perform_sync(self) -> None:
        self._controller.attempt_sync()
        self._refresh_state()

    def _refresh_state(self) -> None:
        self._state = self._controller.get_state()
        self._top_bar.update_sync(self._state.sync)
        mesh_message = self._state.mesh.mesh_summary or "Mesh scan pending"
        self._top_bar.set_mesh_message(mesh_message)
        self._mission_view.update_workspace(self._state.mission_workspace)
        self._log_view.update_form(self._state.operational_log_form)
        self._task_view.update_dashboard(self._state.task_dashboard)
        self._resource_view.update_board(self._state.resource_requests)
        self._settings_view.update_cache_metadata(len(self._state.offline_queue))

    def _refresh_telemetry(self) -> None:
        try:
            snapshot = self._telemetry_provider()
        except Exception as exc:  # pragma: no cover - GUI feedback
            self._telemetry_view.show_error(str(exc))
            return
        self._snapshot = snapshot
        self._telemetry_view.update_snapshot(snapshot)
        self._top_bar.set_telemetry_status(snapshot.status, snapshot.notes)

    def closeEvent(self, event: QCloseEvent) -> None:  # pragma: no cover - GUI lifecycle
        self._sync_timer.stop()
        self._telemetry_timer.stop()
        super().closeEvent(event)


class TopBar(QFrame):
    """Top bar summarizing sync and telemetry status."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("TopBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX,
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX,
        )
        layout.setSpacing(SPACING_GRID_PX * 2)

        self._sync_label = QLabel("Ready for mission intake")
        self._sync_detail = QLabel("Queue: 0")
        self._mesh_label = QLabel("Mesh scan pending")
        self._telemetry_badge = QLabel("Telemetry OK")
        self._telemetry_badge.setObjectName("SyncBadge")

        layout.addWidget(self._sync_label, 2)
        layout.addWidget(self._sync_detail, 0)
        layout.addWidget(self._mesh_label, 1)
        layout.addWidget(self._telemetry_badge, 0)

    def update_sync(self, sync: SyncState) -> None:
        message = sync.message
        if sync.last_synced_at:
            message = f"{message} – last synced {sync.last_synced_at.astimezone().strftime('%H:%M:%S')}"
        self._sync_label.setText(message)
        queue_text = f"Queue: {sync.pending_operations}"
        if sync.conflict_count:
            queue_text += f" – {sync.conflict_count} conflicts"
        self._sync_detail.setText(queue_text)

    def set_mesh_message(self, message: str) -> None:
        self._mesh_label.setText(message)

    def set_telemetry_status(self, status: str, notes: Iterable[str]) -> None:
        badge_text = "Telemetry OK" if status == "ok" else f"Telemetry {status.upper()}"
        self._telemetry_badge.setText(badge_text)
        if status != "ok" and notes:
            self._telemetry_badge.setToolTip("\n".join(notes))
        else:
            self._telemetry_badge.setToolTip("")


class MissionWorkspaceView(QWidget):
    """Mission intake workspace aligned with style tokens."""

    def __init__(self, load_callback: Callable[[str | None], None]) -> None:
        super().__init__()
        self._load_callback = load_callback
        self._demo_button: QPushButton | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
        )
        layout.setSpacing(SPACING_GRID_PX * 2)

        self._headline = QLabel("Awaiting mission package")
        _apply_typography(self._headline, "section_header")
        layout.addWidget(self._headline)

        self._summary = QLabel("Drop a mission archive to begin intake")
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)

        self._load_button = QPushButton("Load Mission Package")
        self._load_button.setMinimumHeight(MIN_CONTROL_HEIGHT_PX)
        self._load_button.clicked.connect(lambda: self._load_callback(None))  # type: ignore[arg-type]
        layout.addWidget(self._load_button)

        self._quick_links = QTabWidget()
        self._quick_links.tabBar().setObjectName("MissionWorkspace")
        self._quick_links.setTabPosition(QTabWidget.TabPosition.North)
        self._quick_links.addTab(self._build_link_list(), "Briefing")
        self._quick_links.addTab(self._build_link_list(), "Files")
        self._quick_links.addTab(self._build_link_list(), "Comms")
        layout.addWidget(self._quick_links)

        self._contacts = QListWidget()
        layout.addWidget(self._contacts)

    def _build_link_list(self) -> QListWidget:
        widget = QListWidget()
        widget.setObjectName("QuickLinkList")
        widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        return widget

    def update_workspace(self, workspace: MissionWorkspaceState) -> None:
        self._headline.setText(workspace.headline)
        if workspace.mission:
            mission = workspace.mission
            summary_lines = [mission.summary or "No summary provided"]
            summary_lines.append(
                f"Classification: {mission.classification or 'N/A'}"
            )
            summary_lines.append(
                "Tags: " + ", ".join(mission.tags) if mission.tags else "Tags: None"
            )
            self._summary.setText("\n".join(summary_lines))
            self._populate_links(mission.quick_links, mission.attachments)
            self._populate_contacts(mission.contacts)
        else:
            self._summary.setText("Package staged – awaiting manifest")
            self._clear_lists()

    def _populate_links(
        self,
        quick_links: MissionQuickLinks,
        attachments: Sequence[MissionAttachmentLink],
    ) -> None:
        categories = {
            "Briefing": self._quick_links.widget(0),
            "Files": self._quick_links.widget(1),
            "Comms": self._quick_links.widget(2),
        }
        for widget in categories.values():
            widget: QListWidget
            widget.clear()

        def _add_item(target: QListWidget, link: MissionAttachmentLink) -> None:
            label = f"{link.label} ({link.badge or link.media_type or 'file'})"
            target.addItem(label)

        seen: set[tuple[str, str]] = set()
        for link in quick_links.sop:
            _add_item(categories["Briefing"], link)
            seen.add((link.path, link.category))
        for link in quick_links.maps:
            _add_item(categories["Files"], link)
            seen.add((link.path, link.category))
        for link in quick_links.comms:
            _add_item(categories["Comms"], link)
            seen.add((link.path, link.category))

        for link in attachments:
            key = (link.path, link.category)
            if key in seen:
                continue
            if link.category == "sop":
                target = categories["Briefing"]
            elif link.category == "map":
                target = categories["Files"]
            elif link.category == "comms":
                target = categories["Comms"]
            else:
                target = categories["Files"]
            _add_item(target, link)

    def _populate_contacts(self, contacts) -> None:
        self._contacts.clear()
        for contact in contacts:
            summary = f"{contact.role}: {contact.name}"
            if contact.callsign:
                summary += f" – {contact.callsign}"
            if contact.channel:
                summary += f" / {contact.channel}"
            self._contacts.addItem(summary)

    def _clear_lists(self) -> None:
        for index in range(self._quick_links.count()):
            widget = self._quick_links.widget(index)
            if isinstance(widget, QListWidget):
                widget.clear()
        self._contacts.clear()

    def set_load_demo_enabled(self, demo_path: Path | None) -> None:
        if self._demo_button is None:
            self._demo_button = QPushButton("Load Demo Package")
            self._demo_button.setMinimumHeight(MIN_CONTROL_HEIGHT_PX)
            self.layout().addWidget(self._demo_button)  # type: ignore[arg-type]
        if demo_path is None:
            self._demo_button.hide()
            return
        self._demo_button.show()
        try:
            self._demo_button.clicked.disconnect()  # type: ignore[call-arg]
        except Exception:  # pragma: no cover - Qt signals guard
            pass
        self._demo_button.clicked.connect(lambda: self._load_callback(str(demo_path)))  # type: ignore[arg-type]


class OperationalLogView(QWidget):
    """Operational logging form with offline queue awareness."""

    def __init__(self, submit_callback: Callable[[str, str, str], None]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
        )
        layout.setSpacing(SPACING_GRID_PX * 2)

        self._banner = QLabel("No pending field logs")
        layout.addWidget(self._banner)

        self._category = QComboBox()
        layout.addWidget(self._category)

        self._title = QLineEdit()
        self._title.setPlaceholderText("Entry title")
        self._title.setMinimumHeight(MIN_CONTROL_HEIGHT_PX)
        layout.addWidget(self._title)

        self._notes = QTextEdit()
        self._notes.setPlaceholderText("Mission notes, GPS tags, and attachments summary")
        layout.addWidget(self._notes)

        self._submit = QPushButton("Queue Field Log")
        self._submit.setMinimumHeight(MIN_CONTROL_HEIGHT_PX)
        layout.addWidget(self._submit)

        def _submit_form() -> None:
            title = self._title.text().strip() or "Untitled Log"
            notes = self._notes.toPlainText().strip() or "No additional notes"
            category = self._category.currentText() or "SITREP"
            submit_callback(title, notes, category)
            self._notes.clear()
            self._title.clear()

        self._submit.clicked.connect(_submit_form)  # type: ignore[arg-type]

    def update_form(self, form_state) -> None:
        self._banner.setText(form_state.banner_message)
        if form_state.banner_token == "accent":
            self._banner.setStyleSheet(f"color: {COLOR_TOKENS['accent'].hex};")
        else:
            self._banner.setStyleSheet(f"color: {COLOR_TOKENS['success'].hex};")
        if not self._category.count():
            self._category.addItems(form_state.categories)
        index = max(0, self._category.findText(form_state.selected_category))
        self._category.setCurrentIndex(index)

    def show_submission(self, submission_id: str) -> None:
        self._banner.setText(f"Queued field log {submission_id}")


class TaskDashboardView(QWidget):
    """Task dashboard with offline badges."""

    def __init__(
        self, action_callback: Callable[[str, str, dict[str, object] | None], None]
    ) -> None:
        super().__init__()
        self._action_callback = action_callback
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
        )
        layout.setSpacing(SPACING_GRID_PX * 2)

        self._badge = QLabel("Task board synced")
        layout.addWidget(self._badge)

        self._columns_container = QHBoxLayout()
        self._columns_container.setSpacing(SPACING_GRID_PX * 2)
        layout.addLayout(self._columns_container)

    def update_dashboard(self, dashboard: TaskDashboardState) -> None:
        self._badge.setText(dashboard.offline_badge_message)
        self._clear_columns()
        for column in dashboard.columns:
            group = self._build_column(column)
            self._columns_container.addWidget(group)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._columns_container.addWidget(spacer)

    def _clear_columns(self) -> None:
        while self._columns_container.count():
            item = self._columns_container.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _build_column(self, column: TaskColumnState) -> QGroupBox:
        group = QGroupBox(column.title)
        layout = QVBoxLayout(group)
        layout.setSpacing(SPACING_GRID_PX)
        for task in column.tasks:
            card = self._build_task_card(task)
            layout.addWidget(card)
        layout.addStretch(1)
        return group

    def _build_task_card(self, task: TaskAssignmentCard) -> QWidget:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(SPACING_GRID_PX // 2)

        title = QLabel(task.title)
        title.setWordWrap(True)
        _apply_typography(title, "card_title")
        card_layout.addWidget(title)

        status = QLabel(f"Status: {task.display_status.title()}")
        card_layout.addWidget(status)

        if task.summary:
            summary = QLabel(task.summary)
            summary.setWordWrap(True)
            card_layout.addWidget(summary)

        action_row = QHBoxLayout()
        action_row.setSpacing(SPACING_GRID_PX)

        accept_button = QPushButton("Accept")
        accept_button.setMinimumHeight(MIN_CONTROL_HEIGHT_PX)
        accept_enabled = task.display_status.lower() not in {"accepted", "completed"}
        accept_button.setEnabled(accept_enabled)
        accept_button.clicked.connect(
            lambda _=None, task_id=task.task_id: self._action_callback(task_id, "accept", None)
        )  # type: ignore[arg-type]
        action_row.addWidget(accept_button)

        complete_button = QPushButton("Complete")
        complete_button.setMinimumHeight(MIN_CONTROL_HEIGHT_PX)
        complete_button.setEnabled(task.display_status.lower() in {"accepted", "completed"})
        complete_button.clicked.connect(lambda _=None, t=task: self._open_completion_dialog(t))
        action_row.addWidget(complete_button)

        defer_button = QPushButton("Defer")
        defer_button.setMinimumHeight(MIN_CONTROL_HEIGHT_PX)
        defer_button.clicked.connect(
            lambda _=None, task_id=task.task_id: self._action_callback(task_id, "defer", None)
        )  # type: ignore[arg-type]
        action_row.addWidget(defer_button)

        escalate_button = QPushButton("Escalate")
        escalate_button.setMinimumHeight(MIN_CONTROL_HEIGHT_PX)
        escalate_button.clicked.connect(
            lambda _=None, task_id=task.task_id: self._action_callback(task_id, "escalate", None)
        )  # type: ignore[arg-type]
        action_row.addWidget(escalate_button)

        card_layout.addLayout(action_row)
        return card

    def _open_completion_dialog(self, task: TaskAssignmentCard) -> None:
        dialog = TaskCompletionDialog(task, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            metadata = dialog.completion_metadata()
            self._action_callback(task.task_id, "complete", metadata)


class TaskCompletionDialog(QDialog):
    """Details dialog surfaced when completing a task."""

    def __init__(self, task: TaskAssignmentCard, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Complete Task – {task.title}")
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
        )
        layout.setSpacing(SPACING_GRID_PX * 2)

        notes_box = QGroupBox("Completion Notes")
        notes_layout = QVBoxLayout(notes_box)
        self._notes = QTextEdit()
        self._notes.setPlaceholderText("Summarize the outcome and follow-on actions.")
        self._notes.setMinimumHeight(120)
        notes_layout.addWidget(self._notes)
        layout.addWidget(notes_box)

        photo_box = QGroupBox("Photos")
        photo_layout = QVBoxLayout(photo_box)
        self._photo_list = QListWidget()
        photo_layout.addWidget(self._photo_list)
        photo_buttons = QHBoxLayout()
        add_photo = QPushButton("Add Photo")
        remove_photo = QPushButton("Remove Selected")
        add_photo.clicked.connect(self._add_photo)
        remove_photo.clicked.connect(self._remove_selected_photo)
        photo_buttons.addWidget(add_photo)
        photo_buttons.addWidget(remove_photo)
        photo_buttons.addStretch(1)
        photo_layout.addLayout(photo_buttons)
        layout.addWidget(photo_box)

        incidents_box = QGroupBox("Incidents")
        incidents_layout = QVBoxLayout(incidents_box)
        self._incident_list = QListWidget()
        incidents_layout.addWidget(self._incident_list)
        incident_controls = QHBoxLayout()
        self._incident_input = QLineEdit()
        self._incident_input.setPlaceholderText("Brief incident summary")
        add_incident = QPushButton("Add Incident")
        remove_incident = QPushButton("Remove Selected")
        add_incident.clicked.connect(self._add_incident)
        remove_incident.clicked.connect(self._remove_selected_incident)
        incident_controls.addWidget(self._incident_input)
        incident_controls.addWidget(add_incident)
        incident_controls.addWidget(remove_incident)
        incidents_layout.addLayout(incident_controls)
        layout.addWidget(incidents_box)

        debrief_box = QGroupBox("Debrief")
        debrief_layout = QVBoxLayout(debrief_box)
        self._debrief_checkbox = QCheckBox("Debrief completed with team")
        self._debrief_notes = QTextEdit()
        self._debrief_notes.setPlaceholderText("Capture key takeaways and follow-up tasks.")
        self._debrief_notes.setMinimumHeight(80)
        debrief_layout.addWidget(self._debrief_checkbox)
        debrief_layout.addWidget(self._debrief_notes)
        layout.addWidget(debrief_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_photo(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Photo",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)",
        )
        if not filename:
            return
        item = QListWidgetItem(Path(filename).name)
        item.setData(Qt.ItemDataRole.UserRole, filename)
        self._photo_list.addItem(item)

    def _remove_selected_photo(self) -> None:
        for item in self._photo_list.selectedItems():
            row = self._photo_list.row(item)
            self._photo_list.takeItem(row)

    def _add_incident(self) -> None:
        text = self._incident_input.text().strip()
        if not text:
            return
        self._incident_list.addItem(text)
        self._incident_input.clear()

    def _remove_selected_incident(self) -> None:
        for item in self._incident_list.selectedItems():
            row = self._incident_list.row(item)
            self._incident_list.takeItem(row)

    def completion_metadata(self) -> dict[str, object]:
        notes = self._notes.toPlainText().strip()
        photos: list[str] = []
        for index in range(self._photo_list.count()):
            item = self._photo_list.item(index)
            stored = item.data(Qt.ItemDataRole.UserRole)
            photos.append(stored if stored is not None else item.text())
        incidents = [self._incident_list.item(i).text() for i in range(self._incident_list.count())]
        debrief_notes = self._debrief_notes.toPlainText().strip()

        metadata: dict[str, object] = {}
        if notes:
            metadata["notes"] = notes
        if photos:
            metadata["photos"] = photos
        if incidents:
            metadata["incidents"] = incidents
        metadata["debrief"] = {
            "completed": self._debrief_checkbox.isChecked(),
            "notes": debrief_notes,
        }
        return metadata

class ResourceBoardView(QWidget):
    """Resource request board with offline badge."""

    def __init__(self, action_callback: Callable[[str, str], None]) -> None:
        super().__init__()
        self._action_callback = action_callback
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
        )
        layout.setSpacing(SPACING_GRID_PX * 2)

        self._badge = QLabel("Resource board synced")
        layout.addWidget(self._badge)

        self._list = QVBoxLayout()
        layout.addLayout(self._list)

    def update_board(self, board: ResourceRequestBoardState) -> None:
        self._badge.setText(board.offline_badge_message)
        while self._list.count():
            item = self._list.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for request in board.requests:
            card = self._build_request_card(request)
            self._list.addWidget(card)
        self._list.addStretch(1)

    def _build_request_card(self, request: ResourceRequestCard) -> QWidget:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(card)
        layout.setSpacing(SPACING_GRID_PX)

        summary = QLabel(f"{request.summary} ({request.priority})")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        meta = QLabel(f"Requester: {request.requester}")
        layout.addWidget(meta)

        buttons = QHBoxLayout()
        buttons.setSpacing(SPACING_GRID_PX)
        for action in ("accept", "defer", "escalate"):
            button = QPushButton(action.title())
            button.setMinimumHeight(MIN_CONTROL_HEIGHT_PX)
            button.clicked.connect(
                lambda _=None, a=action, request_id=request.request_id: self._action_callback(request_id, a)
            )  # type: ignore[arg-type]
            buttons.addWidget(button)
        layout.addLayout(buttons)
        return card


class TelemetryView(QWidget):
    """Telemetry cards that degrade gracefully when data is missing."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
        )
        layout.setSpacing(SPACING_GRID_PX * 2)

        self._status_label = QLabel("Telemetry awaiting snapshot")
        layout.addWidget(self._status_label)

        self._sensor_card = TelemetryCard("Sensor Readings")
        self._event_card = TelemetryCard("Cached Events")
        self._queue_card = TelemetryCard("Queue Backlog")

        layout.addWidget(self._sensor_card)
        layout.addWidget(self._event_card)
        layout.addWidget(self._queue_card)

    def update_snapshot(self, snapshot: TelemetrySnapshot) -> None:
        self._status_label.setText(
            f"Status: {snapshot.status.upper()} at {snapshot.collected_at}"
        )
        degraded = snapshot.status != "ok"
        self._sensor_card.set_degraded(degraded and not snapshot.metrics.sensors)
        if snapshot.metrics.sensors:
            lines = [f"{reading.sensor}: {reading.value} {reading.unit}" for reading in snapshot.metrics.sensors]
        else:
            lines = ["No sensor readings"]
        self._sensor_card.set_lines(lines)

        event_lines = []
        if snapshot.metrics.events.records:
            for record in snapshot.metrics.events.records:
                event_lines.append(f"{record.event}: {record.count} (last {record.last_seen})")
        else:
            event_lines.append("No cached events")
        self._event_card.set_degraded(degraded and not snapshot.metrics.events.records)
        self._event_card.set_lines(event_lines)

        queue_lines = [f"Total backlog: {snapshot.metrics.queues.total_backlog}"]
        for queue, depth in snapshot.metrics.queues.queues.items():
            queue_lines.append(f"{queue}: {depth}")
        self._queue_card.set_degraded(snapshot.metrics.queues.total_backlog > 10)
        self._queue_card.set_lines(queue_lines)

    def show_error(self, message: str) -> None:
        self._status_label.setText(f"Telemetry error: {message}")
        for card in (self._sensor_card, self._event_card, self._queue_card):
            card.set_degraded(True)
            card.set_lines(["No telemetry available"])


class TelemetryCard(QFrame):
    """Reusable telemetry card widget."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("TelemetryCard")
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_GRID_PX)

        self._title = QLabel(title)
        _apply_typography(self._title, "card_title")
        layout.addWidget(self._title)

        self._content = QLabel("–")
        self._content.setWordWrap(True)
        layout.addWidget(self._content)

    def set_lines(self, lines: Iterable[str]) -> None:
        self._content.setText("\n".join(lines))

    def set_degraded(self, degraded: bool) -> None:
        self.setProperty("data-state", "degraded" if degraded else "active")
        self.style().unpolish(self)
        self.style().polish(self)


class SettingsView(QWidget):
    """Settings panel exposing calibration and diagnostics scaffolding."""

    def __init__(self, toggle_offline: Callable[[bool], None]) -> None:
        super().__init__()
        self._toggle_offline = toggle_offline
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
        )
        layout.setSpacing(SPACING_GRID_PX * 2)

        self._offline_button = QPushButton("Enable Offline Mode")
        self._offline_button.setCheckable(True)
        self._offline_button.setMinimumHeight(MIN_CONTROL_HEIGHT_PX)
        self._offline_button.toggled.connect(self._toggle_offline)  # type: ignore[arg-type]
        layout.addWidget(self._offline_button)

        calibration = plan_touchscreen_calibration()
        calibration_box = TelemetryCard("Touchscreen Calibration")
        calibration_box.set_lines(
            [
                f"Status: {calibration['status']}",
                f"Profile: {calibration['profile_path'] or 'Not Provided'}",
                "Integration Points:",
            ]
            + [f"- {point}" for point in calibration["integration_points"]]
        )
        layout.addWidget(calibration_box)

        serial_box = TelemetryCard("Serial Interfaces")
        serial_lines = []
        for interface in enumerate_serial_interfaces():
            serial_lines.append(
                f"{interface['port']}: {interface['role']} ({interface['status']})"
            )
        serial_box.set_lines(serial_lines or ["No interfaces detected"])
        layout.addWidget(serial_box)

        self._cache_label = QLabel("Offline queue entries: 0")
        layout.addWidget(self._cache_label)

    def update_cache_metadata(self, queue_size: int) -> None:
        self._cache_label.setText(f"Offline queue entries: {queue_size}")


def _apply_typography(widget: QLabel, token: str) -> None:
    spec = TYPOGRAPHY[token]
    font = QFont(spec.family, spec.size_pt)
    weight_map = {
        "Regular": QFont.Weight.Normal,
        "Medium": QFont.Weight.Medium,
        "DemiBold": QFont.Weight.DemiBold,
        "Bold": QFont.Weight.Bold,
    }
    font.setWeight(weight_map.get(spec.weight, QFont.Weight.Normal))
    if spec.letter_case == "uppercase":
        widget.setText(widget.text().upper())
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spec.letter_spacing_em * spec.size_pt)
    widget.setFont(font)


def _prepare_demo_package() -> Path | None:
    """Bundle the text-based phase 3 demo mission into a temporary archive."""

    source_dir = Path(__file__).resolve().parents[3] / "samples" / "missions" / "phase3_demo"
    if not source_dir.is_dir():
        return None

    try:
        destination_root = Path.home() / ".prrc" / "demo_packages"
        destination_root.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None

    package_path = destination_root / "phase3_demo.pkg"
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pkg") as tmp_file:
            tmp_path = Path(tmp_file.name)

        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for candidate in sorted(source_dir.rglob("*")):
                if candidate.is_file():
                    archive.write(
                        candidate,
                        candidate.relative_to(source_dir).as_posix(),
                    )

        tmp_path.replace(package_path)
    except OSError:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        return None
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

    return package_path


def launch_app(*, demo_mode: bool = False) -> int:
    """Launch the FieldOps GUI application."""

    app = QApplication.instance() or QApplication(sys.argv)
    cache_path = Path.home() / ".prrc" / "fieldops_offline_queue.json"
    adapter = LocalEchoSyncAdapter()
    controller = FieldOpsGUIController(cache_path, adapter)
    demo_package = _prepare_demo_package() if demo_mode else None
    window = FieldOpsMainWindow(
        controller,
        telemetry_provider=collect_telemetry_snapshot,
        sync_adapter=adapter,
        demo_package=demo_package,
    )
    try:
        window.showMaximized()
    except AttributeError:  # pragma: no cover - compatibility guard
        window.show()
    return app.exec()


__all__ = ["FieldOpsMainWindow", "TaskCompletionDialog", "launch_app", "LocalEchoSyncAdapter"]
