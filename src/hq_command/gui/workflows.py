"""
HQ Command GUI Interactive Workflows (Phase 3).

Provides interactive components for:
- Manual unit-to-task assignment (3-00 to 3-04)
- Task creation and editing (3-05 to 3-06)
- Task escalation and deferral (3-07 to 3-08)
- Responder management (3-09 to 3-10)
- Call intake and processing (3-11 to 3-13)
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, timezone
from dataclasses import dataclass

from .qt_compat import (
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QPushButton,
    QLineEdit,
    QComboBox,
    QTextEdit,
    QSpinBox,
    QCheckBox,
    QGroupBox,
    QScrollArea,
    QListWidget,
    QListWidgetItem,
    QTabWidget,
    QDialogButtonBox,
    Qt,
    pyqtSignal,
)
from .styles import theme
from .components import (
    Modal,
    Button,
    ButtonVariant,
    Input,
    Select,
    Heading,
    Caption,
    Card,
    Badge,
    BadgeType,
    ErrorMessage,
)


# =============================================================================
# MANUAL ASSIGNMENT MODAL (3-00 to 3-04)
# =============================================================================

@dataclass
class UnitRecommendation:
    """Recommendation for unit assignment with scoring."""
    unit_id: str
    suitability_score: float  # 0-100
    capabilities: List[str]
    current_load: int
    max_capacity: int
    location: Optional[str]
    fatigue: float
    match_reason: str  # Human-readable explanation


class ManualAssignmentDialog(Modal):
    """
    Manual assignment modal for assigning units to tasks.

    Features (3-00 to 3-04):
    - Unit selector with capability matching
    - Scheduler-computed recommendations with scores
    - Validation (capacity, capabilities, conflicts)
    - Audit trail capture
    """

    assignment_confirmed = pyqtSignal(str, list)  # task_id, [unit_ids]

    def __init__(
        self,
        task_id: str,
        task_data: Dict[str, Any],
        available_units: List[Dict[str, Any]],
        recommendations: List[UnitRecommendation],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(f"Assign Units to Task {task_id}", parent)

        self.task_id = task_id
        self.task_data = task_data
        self.available_units = available_units
        self.recommendations = recommendations
        self.selected_units: List[str] = []

        self.setMinimumWidth(800)
        self.setMinimumHeight(600)

        self._build_ui()

    def _build_ui(self):
        """Build the assignment dialog UI."""
        # Task information section
        task_card = Card()
        task_card.add_widget(Heading("Task Details", level=4))

        task_info_layout = QGridLayout()
        task_info_layout.addWidget(QLabel("Task ID:"), 0, 0)
        task_info_layout.addWidget(QLabel(self.task_id), 0, 1)
        task_info_layout.addWidget(QLabel("Priority:"), 0, 2)
        priority = self.task_data.get('priority', 'Unknown')
        task_info_layout.addWidget(Badge(f"P{priority}", BadgeType.WARNING), 0, 3)

        capabilities_required = self.task_data.get('capabilities_required', [])
        task_info_layout.addWidget(QLabel("Required Capabilities:"), 1, 0)
        caps_label = QLabel(", ".join(capabilities_required) if capabilities_required else "None")
        task_info_layout.addWidget(caps_label, 1, 1, 1, 3)

        task_card.add_layout(task_info_layout)
        self.content_layout.addWidget(task_card)

        # Recommendations section (3-01)
        rec_card = Card()
        rec_card.add_widget(Heading("Recommended Units (Scheduler Suggestions)", level=4))

        self.recommendations_table = QTableWidget()
        self.recommendations_table.setColumnCount(6)
        self.recommendations_table.setHorizontalHeaderLabels([
            "Unit ID", "Score", "Capabilities", "Load", "Location", "Reason"
        ])
        self.recommendations_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.recommendations_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.recommendations_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self._populate_recommendations()
        rec_card.add_widget(self.recommendations_table)
        self.content_layout.addWidget(rec_card)

        # All units section with filtering
        all_units_card = Card()
        all_units_card.add_widget(Heading("All Available Units", level=4))

        # Filter controls
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self.unit_filter = Input(placeholder="Search by unit ID or capability")
        self.unit_filter.textChanged.connect(self._filter_units)
        filter_layout.addWidget(self.unit_filter)
        all_units_card.add_layout(filter_layout)

        self.units_table = QTableWidget()
        self.units_table.setColumnCount(6)
        self.units_table.setHorizontalHeaderLabels([
            "Select", "Unit ID", "Capabilities", "Status", "Load", "Fatigue"
        ])
        self.units_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.units_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self._populate_units_table()
        all_units_card.add_widget(self.units_table)
        self.content_layout.addWidget(all_units_card)

        # Assignment preview and validation (3-03)
        self.validation_label = QLabel("")
        self.validation_label.setWordWrap(True)
        self.content_layout.addWidget(self.validation_label)

        # Override reason capture (3-04)
        reason_group = QGroupBox("Assignment Notes (for audit trail)")
        reason_layout = QVBoxLayout()
        self.reason_input = QTextEdit()
        self.reason_input.setPlaceholderText(
            "Optional: Explain any manual overrides or special circumstances..."
        )
        self.reason_input.setMaximumHeight(80)
        reason_layout.addWidget(self.reason_input)
        reason_group.setLayout(reason_layout)
        self.content_layout.addWidget(reason_group)

        # Connect signals
        self.button_box.accepted.disconnect()  # Remove default
        self.button_box.accepted.connect(self._confirm_assignment)
        self.recommendations_table.cellDoubleClicked.connect(self._add_recommended_unit)
        self.units_table.cellChanged.connect(self._on_unit_selection_changed)

    def _populate_recommendations(self):
        """Populate recommendations table with scoring (3-01)."""
        self.recommendations_table.setRowCount(len(self.recommendations))

        for row, rec in enumerate(self.recommendations):
            # Unit ID
            self.recommendations_table.setItem(row, 0, QTableWidgetItem(rec.unit_id))

            # Score with color coding
            score_item = QTableWidgetItem(f"{rec.suitability_score:.0f}")
            if rec.suitability_score >= 80:
                score_item.setForeground(Qt.green)
            elif rec.suitability_score >= 60:
                score_item.setForeground(Qt.yellow)
            else:
                score_item.setForeground(Qt.red)
            self.recommendations_table.setItem(row, 1, score_item)

            # Capabilities
            caps_str = ", ".join(rec.capabilities) if rec.capabilities else "None"
            self.recommendations_table.setItem(row, 2, QTableWidgetItem(caps_str))

            # Load
            load_str = f"{rec.current_load}/{rec.max_capacity}"
            self.recommendations_table.setItem(row, 3, QTableWidgetItem(load_str))

            # Location
            location = rec.location or "Unknown"
            self.recommendations_table.setItem(row, 4, QTableWidgetItem(location))

            # Reason (tooltip shows full explanation)
            reason_item = QTableWidgetItem(rec.match_reason[:50] + "..." if len(rec.match_reason) > 50 else rec.match_reason)
            reason_item.setToolTip(rec.match_reason)
            self.recommendations_table.setItem(row, 5, reason_item)

    def _populate_units_table(self):
        """Populate all units table."""
        self.units_table.setRowCount(len(self.available_units))

        for row, unit in enumerate(self.available_units):
            # Checkbox for selection
            checkbox = QCheckBox()
            checkbox.setProperty("unit_id", unit.get('unit_id', ''))
            checkbox.stateChanged.connect(lambda state, r=row: self._on_checkbox_changed(r, state))
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.units_table.setCellWidget(row, 0, checkbox_widget)

            # Unit ID
            self.units_table.setItem(row, 1, QTableWidgetItem(unit.get('unit_id', '')))

            # Capabilities
            caps = unit.get('capabilities', [])
            caps_str = ", ".join(caps) if caps else "None"
            self.units_table.setItem(row, 2, QTableWidgetItem(caps_str))

            # Status
            status = unit.get('status', 'unknown')
            self.units_table.setItem(row, 3, QTableWidgetItem(status))

            # Load
            current_tasks = len(unit.get('current_tasks', []))
            max_concurrent = unit.get('max_concurrent_tasks', 1)
            load_str = f"{current_tasks}/{max_concurrent}"
            self.units_table.setItem(row, 4, QTableWidgetItem(load_str))

            # Fatigue
            fatigue = unit.get('fatigue', 0.0)
            self.units_table.setItem(row, 5, QTableWidgetItem(f"{fatigue:.1f}"))

    def _on_checkbox_changed(self, row: int, state: int):
        """Handle unit selection checkbox change."""
        checkbox_widget = self.units_table.cellWidget(row, 0)
        checkbox = checkbox_widget.findChild(QCheckBox)
        unit_id = checkbox.property("unit_id")

        if state == Qt.Checked:
            if unit_id not in self.selected_units:
                self.selected_units.append(unit_id)
        else:
            if unit_id in self.selected_units:
                self.selected_units.remove(unit_id)

        self._validate_selection()

    def _add_recommended_unit(self, row: int, column: int):
        """Add recommended unit to selection on double-click."""
        unit_id = self.recommendations_table.item(row, 0).text()

        # Find and check the unit in the main table
        for r in range(self.units_table.rowCount()):
            if self.units_table.item(r, 1).text() == unit_id:
                checkbox_widget = self.units_table.cellWidget(r, 0)
                checkbox = checkbox_widget.findChild(QCheckBox)
                checkbox.setChecked(True)
                break

    def _filter_units(self, text: str):
        """Filter units table based on search text."""
        text_lower = text.lower()

        for row in range(self.units_table.rowCount()):
            unit_id = self.units_table.item(row, 1).text().lower()
            capabilities = self.units_table.item(row, 2).text().lower()

            matches = text_lower in unit_id or text_lower in capabilities
            self.units_table.setRowHidden(row, not matches)

    def _validate_selection(self):
        """Validate selected units (3-03: capacity, capabilities, conflicts)."""
        if not self.selected_units:
            self.validation_label.setText("No units selected.")
            self.validation_label.setStyleSheet("")
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return

        # Get task requirements
        required_caps = set(self.task_data.get('capabilities_required', []))
        min_units = self.task_data.get('min_units', 1)
        max_units = self.task_data.get('max_units', 1)

        # Check unit count
        if len(self.selected_units) < min_units:
            self.validation_label.setText(
                f"⚠ Need at least {min_units} units. Currently selected: {len(self.selected_units)}"
            )
            self.validation_label.setStyleSheet(f"color: {theme.WARNING};")
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return

        if len(self.selected_units) > max_units:
            self.validation_label.setText(
                f"⚠ Maximum {max_units} units allowed. Currently selected: {len(self.selected_units)}"
            )
            self.validation_label.setStyleSheet(f"color: {theme.DANGER};")
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return

        # Check capability coverage
        selected_unit_data = [u for u in self.available_units if u.get('unit_id') in self.selected_units]
        combined_caps = set()
        over_capacity_units = []

        for unit in selected_unit_data:
            combined_caps.update(unit.get('capabilities', []))

            # Check capacity
            current_tasks = len(unit.get('current_tasks', []))
            max_concurrent = unit.get('max_concurrent_tasks', 1)
            if current_tasks >= max_concurrent:
                over_capacity_units.append(unit.get('unit_id', ''))

        if over_capacity_units:
            self.validation_label.setText(
                f"⚠ Units at capacity: {', '.join(over_capacity_units)}"
            )
            self.validation_label.setStyleSheet(f"color: {theme.DANGER};")
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return

        missing_caps = required_caps - combined_caps
        if missing_caps:
            self.validation_label.setText(
                f"⚠ Missing required capabilities: {', '.join(missing_caps)}"
            )
            self.validation_label.setStyleSheet(f"color: {theme.DANGER};")
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return

        # All validations passed
        self.validation_label.setText(
            f"✓ Valid assignment: {len(self.selected_units)} unit(s) selected with all required capabilities."
        )
        self.validation_label.setStyleSheet(f"color: {theme.SUCCESS};")
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _confirm_assignment(self):
        """Confirm and emit assignment with audit trail (3-04)."""
        if not self.selected_units:
            return

        # Assignment will be logged with:
        # - timestamp
        # - operator ID (to be added by caller)
        # - selected units
        # - override reason (if provided)
        # - original scheduler recommendations

        self.assignment_confirmed.emit(self.task_id, self.selected_units)
        self.accept()

    def get_assignment_audit_data(self) -> Dict[str, Any]:
        """Get audit trail data for this assignment (3-04)."""
        return {
            'task_id': self.task_id,
            'assigned_units': self.selected_units,
            'override_reason': self.reason_input.toPlainText(),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'scheduler_recommendations': [
                {
                    'unit_id': rec.unit_id,
                    'score': rec.suitability_score,
                    'reason': rec.match_reason,
                }
                for rec in self.recommendations
            ],
        }


# =============================================================================
# TASK CREATION & EDITING (3-05 to 3-06)
# =============================================================================

class TaskCreationDialog(Modal):
    """
    Task creation modal (3-05).

    Allows operators to select a task from calls or create new tasks with validation.
    """

    task_created = pyqtSignal(dict)  # task_data

    def __init__(self, existing_tasks: Optional[List[Dict[str, Any]]] = None, parent: Optional[QWidget] = None):
        super().__init__("Create Task", parent)

        self.existing_tasks = existing_tasks or []
        self.setMinimumWidth(600)
        self._build_ui()

    def _build_ui(self):
        """Build task creation form with tabs."""
        # Tab widget for selection vs creation
        self.tabs = QTabWidget()

        # Tab 1: Select from calls
        select_widget = QWidget()
        select_layout = QVBoxLayout(select_widget)
        select_layout.addWidget(Caption("Select a task created from a call:"))

        self.task_list = QListWidget()
        for task in self.existing_tasks:
            task_id = task.get("task_id", "Unknown")
            priority = task.get("priority", 0)
            capabilities = task.get("capabilities_required", [])
            if isinstance(capabilities, (list, tuple)):
                capabilities = ", ".join(capabilities)
            item_text = f"{task_id} (P{priority}) - [{capabilities}]"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, task)
            self.task_list.addItem(item)

        if not self.existing_tasks:
            self.task_list.addItem("No tasks from calls available")
            self.task_list.setEnabled(False)

        select_layout.addWidget(self.task_list)

        # Tab 2: Create from scratch
        create_widget = QWidget()
        create_layout = QVBoxLayout(create_widget)
        create_layout.addWidget(Caption("Create a new task from scratch:"))

        # Task ID
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("Task ID:"))
        self.task_id_input = Input(placeholder="Enter unique task ID")
        id_layout.addWidget(self.task_id_input)
        create_layout.addLayout(id_layout)

        # Priority
        priority_layout = QHBoxLayout()
        priority_layout.addWidget(QLabel("Priority:"))
        self.priority_select = Select(items=["1 (Highest)", "2 (High)", "3 (Medium)", "4 (Low)", "5 (Lowest)"])
        self.priority_select.setCurrentIndex(2)  # Default to medium (3)
        priority_layout.addWidget(self.priority_select)
        create_layout.addLayout(priority_layout)

        # Capabilities
        caps_layout = QVBoxLayout()
        caps_layout.addWidget(QLabel("Required Capabilities (comma-separated):"))
        self.capabilities_input = Input(placeholder="e.g., medical, transport, technical")
        caps_layout.addWidget(self.capabilities_input)
        create_layout.addLayout(caps_layout)

        # Location
        loc_layout = QHBoxLayout()
        loc_layout.addWidget(QLabel("Location:"))
        self.location_input = Input(placeholder="Task location (optional)")
        loc_layout.addWidget(self.location_input)
        create_layout.addLayout(loc_layout)

        # Unit requirements
        units_layout = QHBoxLayout()
        units_layout.addWidget(QLabel("Min Units:"))
        self.min_units_spin = QSpinBox()
        self.min_units_spin.setMinimum(1)
        self.min_units_spin.setMaximum(10)
        self.min_units_spin.setValue(1)
        units_layout.addWidget(self.min_units_spin)

        units_layout.addWidget(QLabel("Max Units:"))
        self.max_units_spin = QSpinBox()
        self.max_units_spin.setMinimum(1)
        self.max_units_spin.setMaximum(10)
        self.max_units_spin.setValue(1)
        units_layout.addWidget(self.max_units_spin)
        create_layout.addLayout(units_layout)

        # Metadata
        metadata_layout = QVBoxLayout()
        metadata_layout.addWidget(QLabel("Additional Notes:"))
        self.metadata_input = QTextEdit()
        self.metadata_input.setPlaceholderText("Any additional task information...")
        self.metadata_input.setMaximumHeight(100)
        metadata_layout.addWidget(self.metadata_input)
        create_layout.addLayout(metadata_layout)

        # Validation message
        self.validation_label = QLabel("")
        self.validation_label.setWordWrap(True)
        create_layout.addWidget(self.validation_label)

        create_layout.addStretch()

        # Add tabs
        self.tabs.addTab(select_widget, "From Call")
        self.tabs.addTab(create_widget, "From Scratch")

        self.content_layout.addWidget(self.tabs)

        # Connect validation
        self.task_id_input.textChanged.connect(self._validate_form)
        self.tabs.currentChanged.connect(self._validate_form)
        self.button_box.accepted.disconnect()
        self.button_box.accepted.connect(self._on_accept)

        self._validate_form()

    def _on_accept(self):
        """Handle accept based on active tab."""
        if self.tabs.currentIndex() == 0:
            # Selecting task from calls
            selected_items = self.task_list.selectedItems()
            if not selected_items:
                from .qt_compat import QMessageBox
                QMessageBox.warning(self, "Selection Required", "Please select a task.")
                return

            task_data = selected_items[0].data(Qt.UserRole)
            if task_data:
                self.task_created.emit(task_data)
                self.accept()
        else:
            # Creating new task
            self._create_task()

    def _validate_form(self):
        """Validate form inputs (3-05)."""
        # Only validate if on the "From Scratch" tab (index 1)
        if self.tabs.currentIndex() == 0:
            # "From Call" tab - always enable OK button
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
            return

        # Validate "From Scratch" tab
        task_id = self.task_id_input.text().strip()

        if not task_id:
            self.validation_label.setText("⚠ Task ID is required")
            self.validation_label.setStyleSheet(f"color: {theme.DANGER};")
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return

        if self.min_units_spin.value() > self.max_units_spin.value():
            self.validation_label.setText("⚠ Min units cannot exceed max units")
            self.validation_label.setStyleSheet(f"color: {theme.DANGER};")
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return

        self.validation_label.setText("✓ Form valid")
        self.validation_label.setStyleSheet(f"color: {theme.SUCCESS};")
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _create_task(self):
        """Create task and emit signal."""
        priority_text = self.priority_select.currentText()
        priority = int(priority_text.split()[0])

        capabilities_text = self.capabilities_input.text().strip()
        capabilities = [cap.strip() for cap in capabilities_text.split(',') if cap.strip()]

        task_data = {
            'task_id': self.task_id_input.text().strip(),
            'priority': priority,
            'capabilities_required': capabilities,
            'min_units': self.min_units_spin.value(),
            'max_units': self.max_units_spin.value(),
            'location': self.location_input.text().strip() or None,
            'metadata': {
                'notes': self.metadata_input.toPlainText(),
                'created_at': datetime.now(timezone.utc).isoformat(),
            },
        }

        self.task_created.emit(task_data)
        self.accept()


class TaskEditDialog(TaskCreationDialog):
    """
    Task editing modal (3-06).

    Allows editing of non-assigned tasks.
    """

    task_updated = pyqtSignal(str, dict)  # task_id, updated_data

    def __init__(self, task_data: Dict[str, Any], parent: Optional[QWidget] = None):
        self.original_task_data = task_data
        super().__init__(parent)

        self.setWindowTitle(f"Edit Task {task_data.get('task_id', '')}")
        self._populate_from_task()

        # Change signal
        self.task_created.disconnect()
        self.task_created.connect(lambda data: self.task_updated.emit(
            self.original_task_data.get('task_id', ''), data
        ))

    def _populate_from_task(self):
        """Populate form with existing task data."""
        self.task_id_input.setText(self.original_task_data.get('task_id', ''))
        self.task_id_input.setReadOnly(True)  # Can't change task ID

        priority = self.original_task_data.get('priority', 1)
        self.priority_select.setCurrentIndex(priority - 1)

        capabilities = self.original_task_data.get('capabilities_required', [])
        self.capabilities_input.setText(', '.join(capabilities))

        location = self.original_task_data.get('location', '')
        if location:
            self.location_input.setText(location)

        self.min_units_spin.setValue(self.original_task_data.get('min_units', 1))
        self.max_units_spin.setValue(self.original_task_data.get('max_units', 1))

        metadata = self.original_task_data.get('metadata', {})
        notes = metadata.get('notes', '')
        if notes:
            self.metadata_input.setPlainText(notes)


# =============================================================================
# TASK ESCALATION & DEFERRAL (3-07 to 3-08)
# =============================================================================

class TaskEscalationDialog(Modal):
    """
    Task escalation dialog (3-07).

    Allows operators to escalate tasks with reason capture.
    """

    escalation_confirmed = pyqtSignal(str, str)  # task_id, reason

    def __init__(self, task_id: str, parent: Optional[QWidget] = None):
        super().__init__(f"Escalate Task {task_id}", parent)

        self.task_id = task_id
        self.setMinimumWidth(500)

        self._build_ui()

    def _build_ui(self):
        """Build escalation dialog."""
        self.content_layout.addWidget(QLabel(
            f"You are about to escalate task {self.task_id}. "
            "Please provide a reason for escalation:"
        ))

        self.reason_input = QTextEdit()
        self.reason_input.setPlaceholderText(
            "Explain why this task requires escalation (e.g., critical priority, "
            "understaffed, resource shortage)..."
        )
        self.reason_input.setMinimumHeight(150)
        self.content_layout.addWidget(self.reason_input)

        self.button_box.accepted.disconnect()
        self.button_box.accepted.connect(self._confirm_escalation)

    def _confirm_escalation(self):
        """Confirm escalation."""
        reason = self.reason_input.toPlainText().strip()

        if not reason:
            # Require a reason
            from .components import ErrorMessage
            error = ErrorMessage("Escalation reason is required")
            self.content_layout.insertWidget(0, error)
            return

        self.escalation_confirmed.emit(self.task_id, reason)
        self.accept()


class TaskDeferralDialog(Modal):
    """
    Task deferral dialog (3-08).

    Allows operators to defer tasks with reason and duration.
    """

    deferral_confirmed = pyqtSignal(str, str, int)  # task_id, reason, duration_minutes

    def __init__(self, task_id: str, parent: Optional[QWidget] = None):
        super().__init__(f"Defer Task {task_id}", parent)

        self.task_id = task_id
        self.setMinimumWidth(500)

        self._build_ui()

    def _build_ui(self):
        """Build deferral dialog."""
        self.content_layout.addWidget(QLabel(
            f"Defer task {self.task_id} to be reconsidered later."
        ))

        # Duration selection
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("Defer for:"))
        self.duration_spin = QSpinBox()
        self.duration_spin.setMinimum(5)
        self.duration_spin.setMaximum(1440)  # Up to 24 hours
        self.duration_spin.setValue(30)
        self.duration_spin.setSuffix(" minutes")
        duration_layout.addWidget(self.duration_spin)
        duration_layout.addStretch()
        self.content_layout.addLayout(duration_layout)

        # Reason
        self.content_layout.addWidget(QLabel("Reason for deferral:"))
        self.reason_input = QTextEdit()
        self.reason_input.setPlaceholderText(
            "Explain why this task is being deferred (e.g., awaiting resources, "
            "lower priority, waiting for more information)..."
        )
        self.reason_input.setMinimumHeight(100)
        self.content_layout.addWidget(self.reason_input)

        self.button_box.accepted.disconnect()
        self.button_box.accepted.connect(self._confirm_deferral)

    def _confirm_deferral(self):
        """Confirm deferral."""
        reason = self.reason_input.toPlainText().strip()

        if not reason:
            from .components import ErrorMessage
            error = ErrorMessage("Deferral reason is required")
            self.content_layout.insertWidget(0, error)
            return

        duration = self.duration_spin.value()
        self.deferral_confirmed.emit(self.task_id, reason, duration)
        self.accept()


# =============================================================================
# RESPONDER MANAGEMENT (3-09 to 3-10)
# =============================================================================

class ResponderStatusDialog(Modal):
    """
    Responder status management dialog (3-09).

    Allows changing responder status and fatigue level.
    """

    status_changed = pyqtSignal(str, dict)  # unit_id, changes

    def __init__(
        self,
        unit_id: str,
        current_status: str,
        current_fatigue: float,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(f"Manage Status: {unit_id}", parent)

        self.unit_id = unit_id
        self.current_status = current_status
        self.current_fatigue = current_fatigue

        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self):
        """Build status management dialog."""
        # Current status display
        current_group = QGroupBox("Current Status")
        current_layout = QVBoxLayout()
        current_layout.addWidget(QLabel(f"Status: {self.current_status}"))
        current_layout.addWidget(QLabel(f"Fatigue: {self.current_fatigue:.1f}"))
        current_group.setLayout(current_layout)
        self.content_layout.addWidget(current_group)

        # New status selection
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("New Status:"))
        self.status_select = Select(items=["available", "busy", "offline"])
        self.status_select.setCurrentText(self.current_status)
        status_layout.addWidget(self.status_select)
        self.content_layout.addLayout(status_layout)

        # Fatigue adjustment
        fatigue_layout = QHBoxLayout()
        fatigue_layout.addWidget(QLabel("Fatigue Level:"))
        self.fatigue_spin = QSpinBox()
        self.fatigue_spin.setMinimum(0)
        self.fatigue_spin.setMaximum(100)
        self.fatigue_spin.setValue(int(self.current_fatigue))
        fatigue_layout.addWidget(self.fatigue_spin)
        fatigue_layout.addStretch()
        self.content_layout.addLayout(fatigue_layout)

        # Reason
        self.content_layout.addWidget(QLabel("Reason for change:"))
        self.reason_input = QTextEdit()
        self.reason_input.setPlaceholderText("Optional: Explain status change...")
        self.reason_input.setMaximumHeight(80)
        self.content_layout.addWidget(self.reason_input)

        self.button_box.accepted.disconnect()
        self.button_box.accepted.connect(self._confirm_change)

    def _confirm_change(self):
        """Confirm status change."""
        changes = {
            'status': self.status_select.currentText(),
            'fatigue': float(self.fatigue_spin.value()),
            'change_reason': self.reason_input.toPlainText(),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

        self.status_changed.emit(self.unit_id, changes)
        self.accept()


class ResponderProfileDialog(Modal):
    """
    Responder profile editor (3-10).

    Allows editing responder capabilities, location, and settings.
    """

    profile_updated = pyqtSignal(str, dict)  # unit_id, updates

    def __init__(self, unit_data: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(f"Edit Profile: {unit_data.get('unit_id', '')}", parent)

        self.unit_data = unit_data
        self.unit_id = unit_data.get('unit_id', '')

        self.setMinimumWidth(500)
        self._build_ui()

    def _build_ui(self):
        """Build profile editor."""
        # Unit ID (read-only)
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("Unit ID:"))
        id_label = QLabel(self.unit_id)
        id_label.setStyleSheet("font-weight: bold;")
        id_layout.addWidget(id_label)
        id_layout.addStretch()
        self.content_layout.addLayout(id_layout)

        # Capabilities editor
        self.content_layout.addWidget(Heading("Capabilities", level=4))
        caps_label = QLabel("Comma-separated capability tags:")
        self.content_layout.addWidget(caps_label)

        current_caps = self.unit_data.get('capabilities', [])
        self.capabilities_input = Input(placeholder="e.g., medical, transport, technical")
        self.capabilities_input.setText(', '.join(current_caps))
        self.content_layout.addWidget(self.capabilities_input)

        # Location editor
        self.content_layout.addWidget(Heading("Location", level=4))
        current_location = self.unit_data.get('location', '')
        self.location_input = Input(placeholder="Current location")
        self.location_input.setText(current_location or '')
        self.content_layout.addWidget(self.location_input)

        # Max concurrent tasks
        self.content_layout.addWidget(Heading("Capacity", level=4))
        capacity_layout = QHBoxLayout()
        capacity_layout.addWidget(QLabel("Max Concurrent Tasks:"))
        self.capacity_spin = QSpinBox()
        self.capacity_spin.setMinimum(1)
        self.capacity_spin.setMaximum(10)
        self.capacity_spin.setValue(self.unit_data.get('max_concurrent_tasks', 1))
        capacity_layout.addWidget(self.capacity_spin)
        capacity_layout.addStretch()
        self.content_layout.addLayout(capacity_layout)

        self.button_box.accepted.disconnect()
        self.button_box.accepted.connect(self._save_profile)

    def _save_profile(self):
        """Save profile updates."""
        capabilities_text = self.capabilities_input.text().strip()
        capabilities = [cap.strip() for cap in capabilities_text.split(',') if cap.strip()]

        updates = {
            'capabilities': capabilities,
            'location': self.location_input.text().strip() or None,
            'max_concurrent_tasks': self.capacity_spin.value(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }

        self.profile_updated.emit(self.unit_id, updates)
        self.accept()


class ResponderCreationDialog(Modal):
    """
    Create new responder dialog or select existing responder.

    Allows selecting an existing responder or creating a new responder
    with ID, capabilities, location, and settings.
    """

    responder_created = pyqtSignal(dict)  # new_responder_data

    def __init__(self, existing_responders: Optional[List[Dict[str, Any]]] = None, parent: Optional[QWidget] = None):
        super().__init__("Create Roster Entry", parent)

        self.existing_responders = existing_responders or []
        self.setMinimumWidth(500)
        self._build_ui()

    def _build_ui(self):
        """Build creation form with tabs for selecting or creating."""
        # Tab widget for selection vs creation
        self.tabs = QTabWidget()

        # Tab 1: Select existing responder
        select_widget = QWidget()
        select_layout = QVBoxLayout(select_widget)
        select_layout.addWidget(Caption("Select an existing responder to add to the roster:"))

        self.responder_list = QListWidget()
        for responder in self.existing_responders:
            unit_id = responder.get("unit_id", "Unknown")
            capabilities = responder.get("capabilities", [])
            if isinstance(capabilities, (list, tuple)):
                capabilities = ", ".join(capabilities)
            item_text = f"{unit_id} - [{capabilities}]"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, responder)
            self.responder_list.addItem(item)

        if not self.existing_responders:
            self.responder_list.addItem("No existing responders available")
            self.responder_list.setEnabled(False)

        select_layout.addWidget(self.responder_list)

        # Tab 2: Create new responder
        create_widget = QWidget()
        create_layout = QVBoxLayout(create_widget)
        create_layout.addWidget(Caption("Create a new responder:"))

        # Unit ID input
        create_layout.addWidget(Heading("Unit Information", level=4))
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("Unit ID:"))
        self.unit_id_input = Input(placeholder="e.g., UNIT-101")
        id_layout.addWidget(self.unit_id_input)
        create_layout.addLayout(id_layout)

        help_label = QLabel("Enter a unique identifier for this responder")
        help_label.setStyleSheet("font-size: 11px; color: #666; margin-bottom: 16px;")
        create_layout.addWidget(help_label)

        # Capabilities editor
        create_layout.addWidget(Heading("Capabilities", level=4))
        caps_label = QLabel("Comma-separated capability tags:")
        create_layout.addWidget(caps_label)

        self.capabilities_input = Input(placeholder="e.g., medical, transport, technical")
        create_layout.addWidget(self.capabilities_input)

        # Location editor
        create_layout.addWidget(Heading("Location", level=4))
        self.location_input = Input(placeholder="Current location (optional)")
        create_layout.addWidget(self.location_input)

        # Max concurrent tasks
        create_layout.addWidget(Heading("Capacity", level=4))
        capacity_layout = QHBoxLayout()
        capacity_layout.addWidget(QLabel("Max Concurrent Tasks:"))
        self.capacity_spin = QSpinBox()
        self.capacity_spin.setMinimum(1)
        self.capacity_spin.setMaximum(10)
        self.capacity_spin.setValue(3)  # Default to 3
        capacity_layout.addWidget(self.capacity_spin)
        capacity_layout.addStretch()
        create_layout.addLayout(capacity_layout)

        # Initial status
        create_layout.addWidget(Heading("Initial Status", level=4))
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Status:"))
        self.status_select = Select()
        self.status_select.addItems(["available", "busy", "offline"])
        status_layout.addWidget(self.status_select)
        status_layout.addStretch()
        create_layout.addLayout(status_layout)

        create_layout.addStretch()

        # Add tabs
        self.tabs.addTab(select_widget, "Select Existing")
        self.tabs.addTab(create_widget, "Create New")

        self.content_layout.addWidget(self.tabs)

        self.button_box.accepted.disconnect()
        self.button_box.accepted.connect(self._on_accept)

    def _on_accept(self):
        """Handle accept based on active tab."""
        if self.tabs.currentIndex() == 0:
            # Selecting existing responder
            selected_items = self.responder_list.selectedItems()
            if not selected_items:
                from .qt_compat import QMessageBox
                QMessageBox.warning(self, "Selection Required", "Please select a responder.")
                return

            responder_data = selected_items[0].data(Qt.UserRole)
            if responder_data:
                self.responder_created.emit(responder_data)
                self.accept()
        else:
            # Creating new responder
            self._create_responder()

    def _create_responder(self):
        """Validate and create new responder."""
        unit_id = self.unit_id_input.text().strip()

        # Validation
        if not unit_id:
            from .qt_compat import QMessageBox
            QMessageBox.warning(self, "Validation Error", "Unit ID is required.")
            return

        capabilities_text = self.capabilities_input.text().strip()
        capabilities = [cap.strip() for cap in capabilities_text.split(',') if cap.strip()]

        if not capabilities:
            from .qt_compat import QMessageBox
            QMessageBox.warning(self, "Validation Error", "At least one capability is required.")
            return

        location = self.location_input.text().strip() or None

        new_responder = {
            'unit_id': unit_id,
            'capabilities': capabilities,
            'location': location,
            'max_concurrent_tasks': self.capacity_spin.value(),
            'status': self.status_select.currentText(),
            'fatigue': 0.0,  # Start fresh
            'current_tasks': [],
            'metadata': {},
            'created_at': datetime.now(timezone.utc).isoformat(),
        }

        self.responder_created.emit(new_responder)
        self.accept()


# =============================================================================
# CALL INTAKE (3-11 to 3-13)
# =============================================================================

class CallIntakeDialog(Modal):
    """
    Incident call intake form (3-11 to 3-12).

    911-style call intake with call-to-task conversion capability.
    """

    call_submitted = pyqtSignal(dict)  # call_data
    task_generated = pyqtSignal(dict)  # task_data

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Incident Call Intake", parent)

        self.setMinimumWidth(700)
        self.setMinimumHeight(600)

        self._build_ui()

    def _build_ui(self):
        """Build call intake form."""
        # Caller information
        caller_group = QGroupBox("Caller Information")
        caller_layout = QGridLayout()

        caller_layout.addWidget(QLabel("Caller Name:"), 0, 0)
        self.caller_name_input = Input(placeholder="Name of caller")
        caller_layout.addWidget(self.caller_name_input, 0, 1)

        caller_layout.addWidget(QLabel("Callback Number:"), 1, 0)
        self.callback_input = Input(placeholder="Phone number")
        caller_layout.addWidget(self.callback_input, 1, 1)

        caller_group.setLayout(caller_layout)
        self.content_layout.addWidget(caller_group)

        # Location information
        location_group = QGroupBox("Location")
        location_layout = QVBoxLayout()

        self.location_input = Input(placeholder="Address or location description")
        location_layout.addWidget(self.location_input)

        location_group.setLayout(location_layout)
        self.content_layout.addWidget(location_group)

        # Incident details
        incident_group = QGroupBox("Incident Details")
        incident_layout = QVBoxLayout()

        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Incident Type:"))
        self.incident_type_select = Select(items=[
            "Medical Emergency",
            "Fire",
            "Accident",
            "Security Incident",
            "Infrastructure Failure",
            "Other",
        ])
        type_layout.addWidget(self.incident_type_select)
        incident_layout.addLayout(type_layout)

        severity_layout = QHBoxLayout()
        severity_layout.addWidget(QLabel("Severity:"))
        self.severity_select = Select(items=[
            "Critical (Life-threatening)",
            "Urgent (Serious)",
            "Moderate",
            "Low",
        ])
        severity_layout.addWidget(self.severity_select)
        incident_layout.addLayout(severity_layout)

        incident_layout.addWidget(QLabel("Description:"))
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(
            "Detailed description of the incident..."
        )
        self.description_input.setMinimumHeight(150)
        incident_layout.addWidget(self.description_input)

        incident_group.setLayout(incident_layout)
        self.content_layout.addWidget(incident_group)

        # Action buttons
        action_layout = QHBoxLayout()
        self.generate_task_btn = Button("Generate Task from Call", ButtonVariant.PRIMARY)
        self.generate_task_btn.clicked.connect(self._generate_task)
        action_layout.addWidget(self.generate_task_btn)
        action_layout.addStretch()
        self.content_layout.addLayout(action_layout)

        # Change default button behavior
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Save Call Only")
        self.button_box.accepted.disconnect()
        self.button_box.accepted.connect(self._save_call)

    def _save_call(self):
        """Save call data without generating task."""
        call_data = self._get_call_data()
        self.call_submitted.emit(call_data)
        self.accept()

    def _generate_task(self):
        """Generate task from call data (3-12)."""
        call_data = self._get_call_data()

        # Auto-populate task fields from call
        task_data = {
            'task_id': f"CALL-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            'priority': self._infer_priority(call_data['severity']),
            'capabilities_required': self._infer_capabilities(call_data['incident_type']),
            'location': call_data['location'],
            'min_units': 1,
            'max_units': self._infer_max_units(call_data['severity']),
            'metadata': {
                'call_data': call_data,
                'created_from_call': True,
                'created_at': datetime.now(timezone.utc).isoformat(),
            },
        }

        # Emit both call and task
        self.call_submitted.emit(call_data)
        self.task_generated.emit(task_data)
        self.accept()

    def _get_call_data(self) -> Dict[str, Any]:
        """Extract call data from form."""
        return {
            'call_id': f"CALL-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            'caller_name': self.caller_name_input.text().strip(),
            'callback_number': self.callback_input.text().strip(),
            'location': self.location_input.text().strip(),
            'incident_type': self.incident_type_select.currentText(),
            'severity': self.severity_select.currentText(),
            'description': self.description_input.toPlainText(),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    def _infer_priority(self, severity: str) -> int:
        """Infer task priority from call severity (3-12)."""
        if "Critical" in severity:
            return 1
        elif "Urgent" in severity:
            return 2
        elif "Moderate" in severity:
            return 3
        else:
            return 4

    def _infer_capabilities(self, incident_type: str) -> List[str]:
        """Infer required capabilities from incident type (3-12)."""
        capability_map = {
            "Medical Emergency": ["medical", "emergency"],
            "Fire": ["fire", "emergency"],
            "Accident": ["medical", "emergency"],
            "Security Incident": ["security"],
            "Infrastructure Failure": ["technical", "maintenance"],
            "Other": [],
        }
        return capability_map.get(incident_type, [])

    def _infer_max_units(self, severity: str) -> int:
        """Infer max units from severity (3-12)."""
        if "Critical" in severity:
            return 3
        elif "Urgent" in severity:
            return 2
        else:
            return 1


class CallCorrelationDialog(Modal):
    """
    Multi-call correlation interface (3-13).

    Allows linking related calls and detecting duplicates.
    """

    calls_linked = pyqtSignal(list)  # [call_ids]

    def __init__(
        self,
        primary_call: Dict[str, Any],
        similar_calls: List[Dict[str, Any]],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(f"Correlate Call {primary_call.get('call_id', '')}", parent)

        self.primary_call = primary_call
        self.similar_calls = similar_calls
        self.selected_calls: List[str] = []

        self.setMinimumWidth(700)
        self.setMinimumHeight(500)

        self._build_ui()

    def _build_ui(self):
        """Build correlation dialog."""
        # Primary call display
        primary_card = Card()
        primary_card.add_widget(Heading("Primary Call", level=4))
        primary_card.add_widget(QLabel(f"Call ID: {self.primary_call.get('call_id', '')}"))
        primary_card.add_widget(QLabel(f"Location: {self.primary_call.get('location', '')}"))
        primary_card.add_widget(QLabel(f"Type: {self.primary_call.get('incident_type', '')}"))
        primary_card.add_widget(QLabel(f"Time: {self.primary_call.get('timestamp', '')}"))
        self.content_layout.addWidget(primary_card)

        # Similar/Related calls
        self.content_layout.addWidget(Heading("Related/Similar Calls", level=4))
        self.content_layout.addWidget(QLabel(
            "Select calls that appear to be related or duplicate reports of the same incident:"
        ))

        # Calls table
        self.calls_table = QTableWidget()
        self.calls_table.setColumnCount(5)
        self.calls_table.setHorizontalHeaderLabels([
            "Select", "Call ID", "Location", "Type", "Time"
        ])
        self.calls_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.calls_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self._populate_calls_table()
        self.content_layout.addWidget(self.calls_table)

        # Correlation reason
        self.content_layout.addWidget(QLabel("Reason for correlation:"))
        self.reason_input = QTextEdit()
        self.reason_input.setPlaceholderText(
            "Explain why these calls are related (e.g., same incident, same location, "
            "duplicate reports)..."
        )
        self.reason_input.setMaximumHeight(80)
        self.content_layout.addWidget(self.reason_input)

        self.button_box.accepted.disconnect()
        self.button_box.accepted.connect(self._confirm_correlation)

    def _populate_calls_table(self):
        """Populate similar calls table."""
        self.calls_table.setRowCount(len(self.similar_calls))

        for row, call in enumerate(self.similar_calls):
            # Checkbox
            checkbox = QCheckBox()
            checkbox.setProperty("call_id", call.get('call_id', ''))
            checkbox.stateChanged.connect(lambda state, r=row: self._on_call_selected(r, state))
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.calls_table.setCellWidget(row, 0, checkbox_widget)

            # Call data
            self.calls_table.setItem(row, 1, QTableWidgetItem(call.get('call_id', '')))
            self.calls_table.setItem(row, 2, QTableWidgetItem(call.get('location', '')))
            self.calls_table.setItem(row, 3, QTableWidgetItem(call.get('incident_type', '')))
            self.calls_table.setItem(row, 4, QTableWidgetItem(call.get('timestamp', '')))

    def _on_call_selected(self, row: int, state: int):
        """Handle call selection."""
        checkbox_widget = self.calls_table.cellWidget(row, 0)
        checkbox = checkbox_widget.findChild(QCheckBox)
        call_id = checkbox.property("call_id")

        if state == Qt.Checked:
            if call_id not in self.selected_calls:
                self.selected_calls.append(call_id)
        else:
            if call_id in self.selected_calls:
                self.selected_calls.remove(call_id)

    def _confirm_correlation(self):
        """Confirm call correlation."""
        if not self.selected_calls:
            from .components import ErrorMessage
            error = ErrorMessage("Please select at least one call to correlate")
            self.content_layout.insertWidget(0, error)
            return

        # Include primary call in the correlation
        all_calls = [self.primary_call.get('call_id', '')] + self.selected_calls

        self.calls_linked.emit(all_calls)
        self.accept()


class BulkAssignmentDialog(Modal):
    """Batch assignment dialog for assigning units to multiple tasks (3-02)."""

    bulk_assignment_confirmed = pyqtSignal(dict)  # {task_id: [unit_id]}

    def __init__(
        self,
        tasks: List[Dict[str, Any]],
        available_units: List[Dict[str, Any]],
        recommendations: Dict[str, List[UnitRecommendation]],
        parent: Optional[QWidget] = None,
    ):
        super().__init__("Bulk Assign Units", parent)

        self.tasks = tasks
        self.available_units = available_units
        self.recommendations = recommendations
        self._assignment_map: Dict[str, List[str]] = {
            task.get("task_id", ""): [] for task in tasks
        }
        self._task_lists: Dict[str, QListWidget] = {}
        self._building = False

        self.setMinimumWidth(900)
        self.setMinimumHeight(600)

        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the bulk assignment interface."""
        self.content_layout.addWidget(
            Heading(
                f"Selected Tasks ({len(self.tasks)})",
                level=4,
            )
        )
        self.content_layout.addWidget(
            QLabel(
                "Review each task, accept recommended units, or pick alternates before"
                " confirming all assignments."
            )
        )

        apply_all_btn = Button("Apply Recommended to All", ButtonVariant.SECONDARY)
        apply_all_btn.clicked.connect(self._apply_recommended_to_all)
        self.content_layout.addWidget(apply_all_btn)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(theme.SPACING_MD)

        for task in self.tasks:
            card = self._create_task_card(task)
            container_layout.addWidget(card)

        container_layout.addStretch()
        scroll.setWidget(container)
        self.content_layout.addWidget(scroll, 1)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        self.content_layout.addWidget(self.summary_label)
        self._update_summary()

        self.button_box.accepted.disconnect()
        self.button_box.accepted.connect(self._confirm_bulk_assignment)

    def _create_task_card(self, task: Dict[str, Any]) -> Card:
        """Create a card containing unit selections for a task."""
        task_id = task.get("task_id", "Unknown")
        card = Card()
        card.add_widget(Heading(f"Task {task_id}", level=5))

        info = QLabel(
            f"Priority P{task.get('priority', 'N/A')} — Required: "
            f"{', '.join(task.get('required_capabilities', [])) or 'None'}"
        )
        info.setWordWrap(True)
        card.add_widget(info)

        recommended_units = [
            rec.unit_id for rec in self.recommendations.get(task_id, [])[:2]
        ]
        if recommended_units:
            rec_label = QLabel(
                "Recommended: " + ", ".join(recommended_units)
            )
            rec_label.setStyleSheet(f"color: {theme.SUCCESS}; font-weight: 600;")
            card.add_widget(rec_label)

        list_widget = QListWidget()
        list_widget.setSelectionMode(QListWidget.NoSelection)
        self._populate_unit_list(list_widget, task_id, recommended_units)
        list_widget.itemChanged.connect(
            lambda _item, tid=task_id: self._on_unit_toggled(tid)
        )
        self._task_lists[task_id] = list_widget
        card.add_widget(list_widget)

        return card

    def _populate_unit_list(
        self,
        list_widget: QListWidget,
        task_id: str,
        recommended_units: List[str],
    ) -> None:
        """Populate the selectable unit list for a task."""
        self._building = True
        list_widget.clear()
        for unit in self.available_units:
            unit_id = unit.get("unit_id", "")
            item_text = f"{unit_id} — {', '.join(unit.get('capabilities', []))}"
            item = QListWidgetItem(item_text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            if unit_id in recommended_units:
                item.setCheckState(Qt.Checked)
                self._assignment_map.setdefault(task_id, [])
                if unit_id not in self._assignment_map[task_id]:
                    self._assignment_map[task_id].append(unit_id)
            else:
                item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, unit_id)
            list_widget.addItem(item)
        self._building = False

    def _apply_recommended_to_all(self) -> None:
        """Select recommended units for all tasks."""
        for task in self.tasks:
            task_id = task.get("task_id", "")
            list_widget = self._task_lists.get(task_id)
            if not list_widget:
                continue
            recommended_units = [
                rec.unit_id for rec in self.recommendations.get(task_id, [])[:2]
            ]
            for index in range(list_widget.count()):
                item = list_widget.item(index)
                unit_id = item.data(Qt.UserRole)
                if unit_id in recommended_units:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
        self._update_summary()

    def _on_unit_toggled(self, task_id: str) -> None:
        """Track unit selections for a task."""
        if self._building:
            return

        list_widget = self._task_lists.get(task_id)
        if not list_widget:
            return

        selected: List[str] = []
        for index in range(list_widget.count()):
            item = list_widget.item(index)
            if item.checkState() == Qt.Checked:
                unit_id = item.data(Qt.UserRole)
                if unit_id:
                    selected.append(unit_id)

        self._assignment_map[task_id] = selected
        self._update_summary()

    def _update_summary(self) -> None:
        """Update the summary label to reflect pending assignments."""
        assigned_tasks = sum(1 for units in self._assignment_map.values() if units)
        total_units = sum(len(units) for units in self._assignment_map.values())
        self.summary_label.setText(
            f"Assignments prepared for {assigned_tasks} task(s); "
            f"{total_units} unit selections ready to confirm."
        )

    def _confirm_bulk_assignment(self) -> None:
        """Emit the bulk assignment payload when confirmed."""
        assignments = {
            task_id: units
            for task_id, units in self._assignment_map.items()
            if task_id and units
        }

        if not assignments:
            error = ErrorMessage("Select at least one unit before confirming assignments.")
            self.content_layout.insertWidget(0, error)
            return

        self.bulk_assignment_confirmed.emit(assignments)
        self.accept()
