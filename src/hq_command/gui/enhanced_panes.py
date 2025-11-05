"""
Enhanced Panes for HQ Command GUI (Phase 2).

Provides rich data visualization for roster, tasks, and telemetry.
Implements custom table views with sorting, filtering, and visual indicators.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

from .qt_compat import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QPushButton,
    QTableView,
    QAbstractItemModel,
    QModelIndex,
    QStyledItemDelegate,
    QPainter,
    QStyleOptionViewItem,
    QSize,
    QMenu,
    QAction,
    Qt,
    QtCore,
    pyqtSignal,
    qt_exec,
)
from .controller import RosterListModel, TaskQueueModel, TelemetrySummaryModel
from .components import Badge, BadgeType, Button, ButtonVariant, Heading, Input, Select
from .data_table import DataTable, DataTableModel
from .charts import GaugeChart, GaugeStyle, Sparkline, MetricCard, AlertSummaryCard
from .styles import theme


# =============================================================================
# ROSTER PANE (Tasks 2-00 to 2-03)
# =============================================================================

class RosterTableModel(DataTableModel):
    """
    Enhanced table model for roster display with proper column mapping.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        columns = ["Unit ID", "Status", "Capabilities", "Tasks", "Capacity", "Fatigue"]
        super().__init__(columns, parent)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """Return formatted data for display."""
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        if not (0 <= row < len(self._filtered_data)):
            return None

        row_data = self._filtered_data[row]

        if role == Qt.UserRole:
            # Return full row data for delegates
            return row_data

        if role == Qt.DisplayRole or role == Qt.EditRole:
            # Map columns to data fields
            if col == 0:  # Unit ID
                return row_data.get("unit_id", "")
            elif col == 1:  # Status
                return row_data.get("status", "available")
            elif col == 2:  # Capabilities
                caps = row_data.get("capabilities", [])
                return ", ".join(caps) if caps else ""
            elif col == 3:  # Tasks
                tasks = row_data.get("current_tasks", [])
                return len(tasks)
            elif col == 4:  # Capacity
                return row_data.get("available_capacity", 0)
            elif col == 5:  # Fatigue
                return f"{row_data.get('fatigue', 0):.0f}%"

        return None


class RosterPane(QWidget):
    """
    Enhanced Roster Pane with table view, filtering, and visual indicators.

    Features (Tasks 2-00 to 2-03):
    - Custom table widget with columns
    - Column sorting capability
    - Color-coded status badges
    - Fatigue level indicators
    - Capacity utilization bars
    - Status and capability filtering
    - Search box for unit ID lookup
    """

    filter_presets_requested = pyqtSignal()
    create_requested = pyqtSignal()

    def __init__(self, model: RosterListModel, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._model = model
        self._table_model = RosterTableModel()
        self._active_preset_filters: Dict[str, Any] = {}

        self._setup_ui()
        self._connect_signals()

        # Initial data load
        self.refresh()

    def _setup_ui(self) -> None:
        """Set up the roster pane UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.SPACING_SM)

        # Header with title and filters
        header_layout = QHBoxLayout()

        title = Heading("Responder Roster", level=3)
        header_layout.addWidget(title)

        # Status filter
        self._status_filter = Select(["All", "Available", "Busy", "Offline"])
        self._status_filter.setMaximumWidth(150)
        header_layout.addWidget(QLabel("Status:"))
        header_layout.addWidget(self._status_filter)

        # Search box
        self._search_input = Input(placeholder="Search unit ID...")
        self._search_input.setMaximumWidth(200)
        header_layout.addWidget(self._search_input)

        presets_button = Button("Presets", ButtonVariant.OUTLINE)
        presets_button.clicked.connect(self.filter_presets_requested.emit)
        header_layout.addWidget(presets_button)

        create_button = Button("Create", ButtonVariant.PRIMARY)
        create_button.clicked.connect(self.create_requested.emit)
        header_layout.addWidget(create_button)

        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Data table
        self._table = DataTable(
            columns=["Unit ID", "Status", "Capabilities", "Tasks", "Capacity", "Fatigue"],
            show_search=False,  # We have our own search
            show_pagination=False,
        )

        # Replace the table's model with our custom one
        self._table._model = self._table_model
        self._table._table_view.setModel(self._table_model)

        # Set column widths
        self._table.set_column_width(0, 100)  # Unit ID
        self._table.set_column_width(1, 100)  # Status
        self._table.set_column_width(2, 250)  # Capabilities
        self._table.set_column_width(3, 80)   # Tasks
        self._table.set_column_width(4, 80)   # Capacity
        self._table.set_column_width(5, 80)   # Fatigue

        layout.addWidget(self._table)

    def _connect_signals(self) -> None:
        """Connect UI signals."""
        self._status_filter.currentTextChanged.connect(self._on_filter_changed)
        self._search_input.textChanged.connect(self._on_search_changed)

    def refresh(self) -> None:
        """Refresh roster data from model."""
        if not self._model:
            return

        # Get data from controller model
        roster_data = self._model.items()

        # Set data in table model
        self._table_model.set_data(roster_data)

    def _on_filter_changed(self, status: str) -> None:
        """Handle status filter changes."""
        self._apply_filters()

    def _on_search_changed(self, text: str) -> None:
        """Handle search text changes."""
        self._apply_filters()

    def _apply_filters(self) -> None:
        """Apply the combined status, search, and preset filters."""
        status_text = self._status_filter.currentText()
        search_text = self._search_input.text().lower().strip()
        preset_filters = self._active_preset_filters

        if (
            status_text == "All"
            and not search_text
            and not preset_filters
        ):
            self._table_model.set_filter(None)
            return

        def combined_filter(row: Dict[str, Any]) -> bool:
            if status_text != "All":
                if row.get("status", "").lower() != status_text.lower():
                    return False

            if search_text:
                unit_id = str(row.get("unit_id", "")).lower()
                if search_text not in unit_id:
                    return False

            preset_status = preset_filters.get("status")
            if preset_status and row.get("status", "").lower() != str(preset_status).lower():
                return False

            capacity_min = preset_filters.get("capacity_min")
            if capacity_min is not None:
                if row.get("available_capacity", 0) < capacity_min:
                    return False

            capacity_exact = preset_filters.get("capacity")
            if capacity_exact is not None:
                if row.get("available_capacity", 0) != capacity_exact:
                    return False

            return True

        self._table_model.set_filter(combined_filter)

    def apply_preset_filters(self, filters: Dict[str, Any]) -> None:
        """Apply preset filters originating from the filter manager."""
        self._active_preset_filters = filters.copy()

        status_value = filters.get("status")
        if status_value:
            status_title = str(status_value).capitalize()
            if status_title in ["All", "Available", "Busy", "Offline"]:
                self._status_filter.setCurrentText(status_title)
        elif self._status_filter.currentText() != "All":
            self._status_filter.setCurrentText("All")

        self._apply_filters()

    def get_filtered_responders(self) -> List[Dict[str, Any]]:
        """Return the responders currently visible in the table."""
        return self._table_model.filtered_data()

    def get_active_filters(self) -> Dict[str, Any]:
        """Return the active filters so they can be persisted as presets."""
        filters: Dict[str, Any] = {}

        status_text = self._status_filter.currentText()
        if status_text != "All":
            filters["status"] = status_text.lower()

        search_text = self._search_input.text().strip()
        if search_text:
            filters["unit_id_contains"] = search_text

        filters.update(self._active_preset_filters)
        return filters


# =============================================================================
# TASK QUEUE PANE (Tasks 2-04 to 2-07)
# =============================================================================

class TaskQueueTableModel(DataTableModel):
    """Enhanced table model for task queue display."""

    def __init__(self, parent: Optional[QWidget] = None):
        columns = ["Task ID", "Priority", "Capabilities", "Assigned Units", "Status", "Score"]
        super().__init__(columns, parent)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """Return formatted data for display."""
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        if not (0 <= row < len(self._filtered_data)):
            return None

        row_data = self._filtered_data[row]

        if role == Qt.UserRole:
            return row_data

        if role == Qt.DisplayRole or role == Qt.EditRole:
            if col == 0:  # Task ID
                return row_data.get("task_id", "")
            elif col == 1:  # Priority
                return f"P{row_data.get('priority', 0)}"
            elif col == 2:  # Capabilities
                caps = row_data.get("required_capabilities", [])
                return ", ".join(caps) if caps else ""
            elif col == 3:  # Assigned Units
                units = row_data.get("assigned_units", [])
                return len(units)
            elif col == 4:  # Status
                status = row_data.get("status", "pending")
                return status.capitalize()
            elif col == 5:  # Score
                scores = row_data.get("scores", [])
                if scores and scores[0] is not None:
                    return f"{scores[0]:.1f}"
                return "-"

        # Color coding based on priority and status
        if role == Qt.BackgroundRole:
            priority = row_data.get("priority", 0)
            status = row_data.get("status", "pending")

            if status == "escalated":
                from .qt_compat import QColor, QBrush
                return QBrush(QColor(theme.DANGER + "20"))
            elif priority == 1:
                from .qt_compat import QColor, QBrush
                return QBrush(QColor(theme.WARNING + "20"))

        return None


class TaskQueuePane(QWidget):
    """
    Enhanced Task Queue Pane with table view and actions.

    Features (Tasks 2-04 to 2-07):
    - Custom table widget with columns
    - Column sorting and filtering
    - Priority badges with color coding
    - Escalation flag icons
    - Status chips
    - Right-click context menu
    - Assign/Escalate/Defer actions
    """

    # Signals for actions
    assign_requested = pyqtSignal(str)  # task_id
    escalate_requested = pyqtSignal(str)  # task_id
    defer_requested = pyqtSignal(str)  # task_id
    bulk_assign_requested = pyqtSignal(list)  # [task_id]
    filter_presets_requested = pyqtSignal()
    create_requested = pyqtSignal()

    def __init__(self, model: TaskQueueModel, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._model = model
        self._table_model = TaskQueueTableModel()
        self._active_preset_filters: Dict[str, Any] = {}

        self._setup_ui()
        self._connect_signals()

        self.refresh()

    def _setup_ui(self) -> None:
        """Set up the task queue pane UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.SPACING_SM)

        # Header with title and filters
        header_layout = QHBoxLayout()

        title = Heading("Task Queue", level=3)
        header_layout.addWidget(title)

        # Priority filter
        self._priority_filter = Select(["All", "P1", "P2", "P3", "P4"])
        self._priority_filter.setMaximumWidth(100)
        header_layout.addWidget(QLabel("Priority:"))
        header_layout.addWidget(self._priority_filter)

        # Status filter
        self._status_filter = Select(["All", "Pending", "Assigned", "Escalated", "Deferred"])
        self._status_filter.setMaximumWidth(150)
        header_layout.addWidget(QLabel("Status:"))
        header_layout.addWidget(self._status_filter)

        header_layout.addStretch()

        self._bulk_assign_button = Button("Assign Selected", ButtonVariant.PRIMARY)
        self._bulk_assign_button.setEnabled(False)
        self._bulk_assign_button.clicked.connect(self._on_bulk_assign_clicked)
        header_layout.addWidget(self._bulk_assign_button)

        presets_button = Button("Presets", ButtonVariant.OUTLINE)
        presets_button.clicked.connect(self.filter_presets_requested.emit)
        header_layout.addWidget(presets_button)

        create_button = Button("Create", ButtonVariant.PRIMARY)
        create_button.clicked.connect(self.create_requested.emit)
        header_layout.addWidget(create_button)

        layout.addLayout(header_layout)

        # Data table
        self._table = DataTable(
            columns=["Task ID", "Priority", "Capabilities", "Assigned Units", "Status", "Score"],
            show_search=False,
            show_pagination=False,
        )

        # Replace with custom model
        self._table._model = self._table_model
        self._table._table_view.setModel(self._table_model)

        # Enable context menu
        self._table._table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table._table_view.customContextMenuRequested.connect(self._show_context_menu)

        # Set column widths
        self._table.set_column_width(0, 120)  # Task ID
        self._table.set_column_width(1, 70)   # Priority
        self._table.set_column_width(2, 200)  # Capabilities
        self._table.set_column_width(3, 120)  # Assigned Units
        self._table.set_column_width(4, 100)  # Status
        self._table.set_column_width(5, 80)   # Score

        layout.addWidget(self._table)

    def _connect_signals(self) -> None:
        """Connect UI signals."""
        self._priority_filter.currentTextChanged.connect(self._on_filter_changed)
        self._status_filter.currentTextChanged.connect(self._on_filter_changed)
        self._table.selection_changed.connect(self._on_selection_changed)

    def refresh(self) -> None:
        """Refresh task queue data from model."""
        if not self._model:
            return

        task_data = self._model.items()
        self._table_model.set_data(task_data)

    def _on_filter_changed(self, _text: str = "") -> None:
        """Handle filter changes."""
        priority = self._priority_filter.currentText()
        status = self._status_filter.currentText()

        if priority == "All" and status == "All":
            self._table_model.set_filter(None)
            return

        self._apply_filters(priority, status)

    def _apply_filters(self, priority: str, status: str) -> None:
        """Apply dropdown and preset filters together."""
        preset_filters = self._active_preset_filters

        if (
            priority == "All"
            and status == "All"
            and not preset_filters
        ):
            self._table_model.set_filter(None)
            return

        def combined_filter(row: Dict[str, Any]) -> bool:
            if priority != "All":
                task_priority = row.get("priority", 0)
                if f"P{task_priority}" != priority:
                    return False

            if status != "All":
                task_status = row.get("status", "pending").lower()
                if task_status != status.lower():
                    return False

            preset_status = preset_filters.get("status")
            if preset_status and row.get("status", "").lower() != str(preset_status).lower():
                return False

            priority_max = preset_filters.get("priority_max")
            if priority_max is not None and row.get("priority", 0) > priority_max:
                return False

            priority_exact = preset_filters.get("priority")
            if priority_exact is not None and row.get("priority", 0) != priority_exact:
                return False

            return True

        self._table_model.set_filter(combined_filter)

    def _on_selection_changed(self, rows: List[int]) -> None:
        """Enable bulk assignment when multiple tasks are selected."""
        self._bulk_assign_button.setEnabled(bool(rows))

    def _on_bulk_assign_clicked(self) -> None:
        """Emit a request for bulk assignment for selected tasks."""
        selected_ids = self.get_selected_task_ids()
        if selected_ids:
            self.bulk_assign_requested.emit(selected_ids)

    def get_selected_task_ids(self) -> List[str]:
        """Return the task IDs that are currently selected in the table."""
        rows = self._table.get_selected_rows()
        task_ids: List[str] = []
        for row in rows:
            row_data = self._table_model.get_row_data(row)
            if not row_data:
                continue
            task_id = row_data.get("task_id")
            if task_id:
                task_ids.append(str(task_id))
        return task_ids

    def apply_preset_filters(self, filters: Dict[str, Any]) -> None:
        """Apply filters from a saved preset."""
        self._active_preset_filters = filters.copy()

        preset_status = filters.get("status")
        if preset_status:
            status_title = str(preset_status).capitalize()
            if status_title in ["Pending", "Assigned", "Escalated", "Deferred"]:
                self._status_filter.setCurrentText(status_title)
        elif self._status_filter.currentText() != "All":
            self._status_filter.setCurrentText("All")

        preset_priority = filters.get("priority")
        if preset_priority is not None:
            priority_label = f"P{preset_priority}"
            if priority_label in ["P1", "P2", "P3", "P4"]:
                self._priority_filter.setCurrentText(priority_label)
        elif self._priority_filter.currentText() != "All":
            self._priority_filter.setCurrentText("All")

        self._apply_filters(
            self._priority_filter.currentText(),
            self._status_filter.currentText(),
        )

    def get_filtered_tasks(self) -> List[Dict[str, Any]]:
        """Return the filtered task rows currently displayed."""
        return self._table_model.filtered_data()

    def get_active_filters(self) -> Dict[str, Any]:
        """Return the active filters in the task pane."""
        filters: Dict[str, Any] = {}

        priority_text = self._priority_filter.currentText()
        if priority_text != "All":
            filters["priority"] = int(priority_text.replace("P", ""))

        status_text = self._status_filter.currentText()
        if status_text != "All":
            filters["status"] = status_text.lower()

        filters.update(self._active_preset_filters)
        return filters

    def _show_context_menu(self, position) -> None:
        """Show context menu for task actions."""
        # Get selected row
        selected_rows = self._table.get_selected_rows()
        if not selected_rows:
            return

        row = selected_rows[0]
        row_data = self._table_model.get_row_data(row)
        if not row_data:
            return

        task_id = row_data.get("task_id", "")

        # Create context menu
        menu = QMenu(self)

        assign_action = QAction("Assign Units", self)
        assign_action.triggered.connect(lambda: self.assign_requested.emit(task_id))
        menu.addAction(assign_action)

        escalate_action = QAction("Escalate Task", self)
        escalate_action.triggered.connect(lambda: self.escalate_requested.emit(task_id))
        menu.addAction(escalate_action)

        defer_action = QAction("Defer Task", self)
        defer_action.triggered.connect(lambda: self.defer_requested.emit(task_id))
        menu.addAction(defer_action)

        qt_exec(menu, self._table._table_view.viewport().mapToGlobal(position))


# =============================================================================
# TELEMETRY PANE (Tasks 2-08 to 2-10)
# =============================================================================

class TelemetryPane(QWidget):
    """
    Enhanced Telemetry Pane with card-based layout and visualizations.

    Features (Tasks 2-08 to 2-10):
    - Card-based grid layout
    - Active Devices display showing connected FieldOps units
    - Sensor state cards (nominal/warning/critical)
    - Alert summary card
    - Trend sparklines
    - Real-time update animations
    """

    def __init__(self, model: TelemetrySummaryModel, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._model = model
        self._cards: Dict[str, MetricCard] = {}
        self._alert_card: Optional[AlertSummaryCard] = None
        self._active_devices: Dict[str, Dict[str, Any]] = {}
        self._devices_list: Optional[QWidget] = None

        self._setup_ui()

        self.refresh()

    def _setup_ui(self) -> None:
        """Set up the telemetry pane UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.SPACING_MD)

        # Header
        title = Heading("Telemetry Summary", level=3)
        layout.addWidget(title)

        # Active Devices card (replaces Readiness Score)
        from .components import Card
        devices_card = Card()
        devices_header = QHBoxLayout()
        devices_header.addWidget(Heading("Active Devices", level=4))
        devices_header.addStretch()
        self._device_count_label = QLabel("0 connected")
        self._device_count_label.setStyleSheet(f"color: {theme.TEXT_SECONDARY};")
        devices_header.addWidget(self._device_count_label)

        devices_card_widget = QWidget()
        devices_card_layout = QVBoxLayout(devices_card_widget)
        devices_card_layout.setContentsMargins(0, 0, 0, 0)
        devices_card_layout.addLayout(devices_header)

        # Scrollable list of devices
        self._devices_list = QWidget()
        self._devices_list_layout = QVBoxLayout(self._devices_list)
        self._devices_list_layout.setContentsMargins(0, theme.SPACING_SM, 0, 0)
        self._devices_list_layout.setSpacing(theme.SPACING_SM)

        # Initial empty state
        empty_label = QLabel("No devices connected")
        empty_label.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; padding: {theme.SPACING_MD}px;")
        self._devices_list_layout.addWidget(empty_label)

        devices_card_layout.addWidget(self._devices_list)
        devices_card.add_widget(devices_card_widget)
        layout.addWidget(devices_card)

        # Alert summary card
        self._alert_card = AlertSummaryCard("System Alerts")
        layout.addWidget(self._alert_card)

        # Additional metrics cards (will be populated dynamically)
        self._metrics_container = QWidget()
        self._metrics_layout = QVBoxLayout(self._metrics_container)
        self._metrics_layout.setSpacing(theme.SPACING_SM)
        layout.addWidget(self._metrics_container)

        layout.addStretch()

    def update_active_devices(self, devices: Dict[str, Dict[str, Any]]) -> None:
        """Update the active devices display with current device information"""
        self._active_devices = devices

        # Clear existing device widgets
        while self._devices_list_layout.count():
            child = self._devices_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Update count
        device_count = len(devices)
        self._device_count_label.setText(f"{device_count} connected")

        if not devices:
            # Show empty state
            empty_label = QLabel("No devices connected")
            empty_label.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; padding: {theme.SPACING_SM}px;")
            self._devices_list_layout.addWidget(empty_label)
        else:
            # Show device list
            for device_id, device_info in sorted(devices.items()):
                device_widget = self._create_device_widget(device_id, device_info)
                self._devices_list_layout.addWidget(device_widget)

    def _create_device_widget(self, device_id: str, device_info: Dict[str, Any]) -> QWidget:
        """Create a widget displaying a single device"""
        widget = QFrame()
        widget.setFrameShape(QFrame.StyledPanel)
        widget.setStyleSheet(f"""
            QFrame {{
                background-color: {theme.BACKGROUND_SECONDARY};
                border: 1px solid {theme.BORDER_COLOR};
                border-radius: 4px;
                padding: {theme.SPACING_SM}px;
            }}
        """)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(theme.SPACING_SM, theme.SPACING_SM, theme.SPACING_SM, theme.SPACING_SM)
        layout.setSpacing(4)

        # Device ID and status badge
        header = QHBoxLayout()
        device_label = QLabel(f"<b>{device_id}</b>")
        header.addWidget(device_label)
        header.addStretch()

        status = device_info.get("status", "unknown")
        status_badge = Badge(status.capitalize(), BadgeType.SUCCESS if status == "available" else BadgeType.WARNING)
        header.addWidget(status_badge)
        layout.addLayout(header)

        # Capabilities
        capabilities = device_info.get("capabilities", [])
        if capabilities:
            caps_text = f"Capabilities: {', '.join(capabilities[:3])}"
            if len(capabilities) > 3:
                caps_text += f" +{len(capabilities) - 3} more"
            caps_label = QLabel(caps_text)
            caps_label.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 11px;")
            layout.addWidget(caps_label)

        # Task info
        current_tasks = device_info.get("current_task_count", 0)
        max_tasks = device_info.get("max_concurrent_tasks", 1)
        task_label = QLabel(f"Tasks: {current_tasks}/{max_tasks}")
        task_label.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(task_label)

        return widget

    def refresh(self) -> None:
        """Refresh telemetry data from model."""
        if not self._model:
            return

        telemetry_data = self._model.items()

        # Update cards based on telemetry data
        for item in telemetry_data:
            metric = item.get("metric", "")
            value = item.get("value", "")

            if metric == "critical_alerts":
                # Update alert card
                try:
                    critical = int(value)
                    if self._alert_card:
                        self._alert_card.set_counts(critical=critical)
                except (ValueError, TypeError):
                    pass
            elif metric == "warning_alerts":
                try:
                    warning = int(value)
                    if self._alert_card:
                        # Get current counts and update
                        self._alert_card.set_counts(warning=warning)
                except (ValueError, TypeError):
                    pass
            else:
                # Create or update metric card
                if metric not in self._cards:
                    card = MetricCard(metric.replace("_", " ").title(), str(value))
                    self._cards[metric] = card
                    self._metrics_layout.addWidget(card)
                else:
                    self._cards[metric].set_value(str(value))
