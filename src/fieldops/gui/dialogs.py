"""Dialog components for FieldOps first-run setup and job acceptance."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .styles import (
    HORIZONTAL_PADDING_PX,
    MIN_CONTROL_HEIGHT_PX,
    SPACING_GRID_PX,
)


class FieldOpsConfig:
    """Configuration manager for FieldOps settings."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or (Path.home() / ".prrc" / "fieldops_config.json")
        self.config: dict[str, Any] = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        """Load configuration from file if it exists."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_config(self, config: dict[str, Any]) -> None:
        """Save configuration to file."""
        self.config = config
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.get(key, default)

    def is_first_run(self) -> bool:
        """Check if this is the first run (no config exists)."""
        return not self.config or "device_id" not in self.config


class FirstRunDialog(QDialog):
    """Dialog for first-run setup of device ID, user ID, and user capabilities."""

    # Available capability options
    AVAILABLE_CAPABILITIES = [
        "Medical Response",
        "Fire Suppression",
        "Search and Rescue",
        "Hazmat Response",
        "Technical Rescue",
        "Swift Water Rescue",
        "Vehicle Extrication",
        "Communication Support",
        "Transport/Logistics",
        "Command and Control",
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("FieldOps First Run Setup")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        # Configuration data
        self._device_id = ""
        self._user_id = ""
        self._capabilities: list[str] = []

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
        )
        layout.setSpacing(SPACING_GRID_PX * 2)

        # Welcome message
        welcome_label = QLabel(
            "<h2>Welcome to FieldOps</h2>"
            "<p>Before you begin, please configure your device and user information.</p>"
        )
        welcome_label.setWordWrap(True)
        layout.addWidget(welcome_label)

        # Device ID section
        device_group = QGroupBox("Device Configuration")
        device_layout = QFormLayout(device_group)
        device_layout.setSpacing(SPACING_GRID_PX)

        self._device_id_input = QLineEdit()
        self._device_id_input.setPlaceholderText("e.g., UNIT-001, TABLET-A1")
        self._device_id_input.setMinimumHeight(MIN_CONTROL_HEIGHT_PX)
        device_layout.addRow("Device ID:", self._device_id_input)

        device_help = QLabel("A unique identifier for this FieldOps device/tablet")
        device_help.setStyleSheet("color: gray; font-size: 11px;")
        device_layout.addRow("", device_help)

        layout.addWidget(device_group)

        # User ID section
        user_group = QGroupBox("User Configuration")
        user_layout = QFormLayout(user_group)
        user_layout.setSpacing(SPACING_GRID_PX)

        self._user_id_input = QLineEdit()
        self._user_id_input.setPlaceholderText("e.g., J.Smith, Responder-42")
        self._user_id_input.setMinimumHeight(MIN_CONTROL_HEIGHT_PX)
        user_layout.addRow("User ID:", self._user_id_input)

        user_help = QLabel("Your unique identifier or callsign")
        user_help.setStyleSheet("color: gray; font-size: 11px;")
        user_layout.addRow("", user_help)

        layout.addWidget(user_group)

        # Capabilities section
        capabilities_group = QGroupBox("User Capabilities")
        capabilities_layout = QVBoxLayout(capabilities_group)
        capabilities_layout.setSpacing(SPACING_GRID_PX)

        cap_help = QLabel("Select all capabilities you are qualified to perform:")
        capabilities_layout.addWidget(cap_help)

        # Create checkboxes for each capability
        self._capability_checkboxes: dict[str, QCheckBox] = {}
        for capability in self.AVAILABLE_CAPABILITIES:
            checkbox = QCheckBox(capability)
            self._capability_checkboxes[capability] = checkbox
            capabilities_layout.addWidget(checkbox)

        layout.addWidget(capabilities_group)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _validate_and_accept(self) -> None:
        """Validate inputs before accepting."""
        device_id = self._device_id_input.text().strip()
        user_id = self._user_id_input.text().strip()

        if not device_id:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Missing Device ID",
                "Please enter a Device ID to continue."
            )
            self._device_id_input.setFocus()
            return

        if not user_id:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Missing User ID",
                "Please enter a User ID to continue."
            )
            self._user_id_input.setFocus()
            return

        # Collect selected capabilities
        capabilities = [
            cap for cap, checkbox in self._capability_checkboxes.items()
            if checkbox.isChecked()
        ]

        if not capabilities:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "No Capabilities Selected",
                "Please select at least one capability to continue."
            )
            return

        self._device_id = device_id
        self._user_id = user_id
        self._capabilities = capabilities

        self.accept()

    def get_configuration(self) -> dict[str, Any]:
        """Return the configuration data."""
        return {
            "device_id": self._device_id,
            "user_id": self._user_id,
            "capabilities": self._capabilities,
        }


class JobAcceptanceDialog(QDialog):
    """Dialog for accepting a job with team capabilities, member IDs, and vehicle ID."""

    # Available team capability options
    AVAILABLE_TEAM_CAPABILITIES = [
        "Medical Response",
        "Fire Suppression",
        "Search and Rescue",
        "Hazmat Response",
        "Technical Rescue",
        "Swift Water Rescue",
        "Vehicle Extrication",
        "Communication Support",
        "Transport/Logistics",
        "Command and Control",
        "Heavy Equipment Operation",
        "K9 Unit",
        "Aviation Support",
    ]

    def __init__(self, task_id: str, task_title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Accept Job - {task_title}")
        self.setModal(True)
        self.setMinimumWidth(650)
        self.setMinimumHeight(600)

        self._task_id = task_id
        self._task_title = task_title

        # Job acceptance data
        self._team_capabilities: list[str] = []
        self._team_member_ids: list[str] = []
        self._vehicle_id = ""

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
        )
        layout.setSpacing(SPACING_GRID_PX * 2)

        # Task info
        task_info = QLabel(f"<h3>{self._task_title}</h3><p>Task ID: {self._task_id}</p>")
        task_info.setWordWrap(True)
        layout.addWidget(task_info)

        # Team capabilities section
        capabilities_group = QGroupBox("Required Team Capabilities")
        capabilities_layout = QVBoxLayout(capabilities_group)
        capabilities_layout.setSpacing(SPACING_GRID_PX)

        cap_help = QLabel("Select all capabilities needed for this job:")
        capabilities_layout.addWidget(cap_help)

        # Create checkboxes for each team capability
        self._capability_checkboxes: dict[str, QCheckBox] = {}
        for capability in self.AVAILABLE_TEAM_CAPABILITIES:
            checkbox = QCheckBox(capability)
            self._capability_checkboxes[capability] = checkbox
            capabilities_layout.addWidget(checkbox)

        layout.addWidget(capabilities_group)

        # Team members section
        team_group = QGroupBox("Team Members")
        team_layout = QVBoxLayout(team_group)
        team_layout.setSpacing(SPACING_GRID_PX)

        team_help = QLabel("Enter all team member IDs participating in this job:")
        team_layout.addWidget(team_help)

        self._team_list = QListWidget()
        self._team_list.setMinimumHeight(100)
        team_layout.addWidget(self._team_list)

        team_controls = QHBoxLayout()
        team_controls.setSpacing(SPACING_GRID_PX)

        self._team_member_input = QLineEdit()
        self._team_member_input.setPlaceholderText("Enter team member ID")
        self._team_member_input.setMinimumHeight(MIN_CONTROL_HEIGHT_PX)
        self._team_member_input.returnPressed.connect(self._add_team_member)
        team_controls.addWidget(self._team_member_input)

        add_member_button = QPushButton("Add Member")
        add_member_button.setMinimumHeight(MIN_CONTROL_HEIGHT_PX)
        add_member_button.clicked.connect(self._add_team_member)
        team_controls.addWidget(add_member_button)

        remove_member_button = QPushButton("Remove Selected")
        remove_member_button.setMinimumHeight(MIN_CONTROL_HEIGHT_PX)
        remove_member_button.clicked.connect(self._remove_team_member)
        team_controls.addWidget(remove_member_button)

        team_layout.addLayout(team_controls)
        layout.addWidget(team_group)

        # Vehicle section
        vehicle_group = QGroupBox("Vehicle Information")
        vehicle_layout = QFormLayout(vehicle_group)
        vehicle_layout.setSpacing(SPACING_GRID_PX)

        self._vehicle_id_input = QLineEdit()
        self._vehicle_id_input.setPlaceholderText("e.g., ENGINE-1, TRUCK-5, AMBULANCE-12")
        self._vehicle_id_input.setMinimumHeight(MIN_CONTROL_HEIGHT_PX)
        vehicle_layout.addRow("Vehicle ID:", self._vehicle_id_input)

        vehicle_help = QLabel("The primary vehicle being used for this job")
        vehicle_help.setStyleSheet("color: gray; font-size: 11px;")
        vehicle_layout.addRow("", vehicle_help)

        layout.addWidget(vehicle_group)

        # Notes section
        notes_group = QGroupBox("Additional Notes (Optional)")
        notes_layout = QVBoxLayout(notes_group)
        notes_layout.setSpacing(SPACING_GRID_PX)

        self._notes_input = QTextEdit()
        self._notes_input.setPlaceholderText("Enter any additional notes about this job acceptance...")
        self._notes_input.setMinimumHeight(80)
        notes_layout.addWidget(self._notes_input)

        layout.addWidget(notes_group)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText("Accept Job")
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _add_team_member(self) -> None:
        """Add a team member to the list."""
        member_id = self._team_member_input.text().strip()
        if not member_id:
            return

        # Check for duplicates
        for i in range(self._team_list.count()):
            if self._team_list.item(i).text() == member_id:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self,
                    "Duplicate Member",
                    f"Team member '{member_id}' is already in the list."
                )
                return

        self._team_list.addItem(member_id)
        self._team_member_input.clear()
        self._team_member_input.setFocus()

    def _remove_team_member(self) -> None:
        """Remove selected team member from the list."""
        for item in self._team_list.selectedItems():
            row = self._team_list.row(item)
            self._team_list.takeItem(row)

    def _validate_and_accept(self) -> None:
        """Validate inputs before accepting."""
        # Collect team capabilities
        team_capabilities = [
            cap for cap, checkbox in self._capability_checkboxes.items()
            if checkbox.isChecked()
        ]

        if not team_capabilities:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "No Capabilities Selected",
                "Please select at least one team capability required for this job."
            )
            return

        # Collect team member IDs
        team_members = [
            self._team_list.item(i).text()
            for i in range(self._team_list.count())
        ]

        if not team_members:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "No Team Members",
                "Please add at least one team member ID."
            )
            return

        # Validate vehicle ID
        vehicle_id = self._vehicle_id_input.text().strip()
        if not vehicle_id:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Missing Vehicle ID",
                "Please enter a Vehicle ID."
            )
            self._vehicle_id_input.setFocus()
            return

        self._team_capabilities = team_capabilities
        self._team_member_ids = team_members
        self._vehicle_id = vehicle_id

        self.accept()

    def get_job_metadata(self) -> dict[str, Any]:
        """Return the job acceptance metadata."""
        return {
            "task_id": self._task_id,
            "team_capabilities": self._team_capabilities,
            "team_member_ids": self._team_member_ids,
            "vehicle_id": self._vehicle_id,
            "notes": self._notes_input.toPlainText().strip(),
        }


class SensorDetailsDialog(QDialog):
    """Dialog showing detailed sensor readings, events, and queue information."""

    def __init__(self, snapshot: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Telemetry Details")
        self.setModal(True)
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)

        self._snapshot = snapshot
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
            HORIZONTAL_PADDING_PX,
            SPACING_GRID_PX * 2,
        )
        layout.setSpacing(SPACING_GRID_PX * 2)

        # Header with status
        header = QLabel(
            f"<h2>Telemetry Snapshot</h2>"
            f"<p><b>Status:</b> {self._snapshot.status.upper()} | "
            f"<b>Collected:</b> {self._snapshot.collected_at}</p>"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        # Notes section if any
        if self._snapshot.notes:
            notes_text = "<br>".join(f"• {note}" for note in self._snapshot.notes)
            notes_label = QLabel(f"<p><b>Notes:</b><br>{notes_text}</p>")
            notes_label.setWordWrap(True)
            notes_label.setStyleSheet("background-color: #fff3cd; padding: 8px; border-radius: 4px;")
            layout.addWidget(notes_label)

        # Sensor Readings Section
        sensor_group = QGroupBox("Sensor Readings")
        sensor_layout = QVBoxLayout(sensor_group)
        sensor_layout.setSpacing(SPACING_GRID_PX)

        if self._snapshot.metrics.sensors:
            sensor_text = QTextEdit()
            sensor_text.setReadOnly(True)
            sensor_text.setMinimumHeight(200)

            # Build formatted sensor table
            sensor_content = "<table style='width: 100%; border-collapse: collapse;'>"
            sensor_content += "<tr style='background-color: #e9ecef; font-weight: bold;'>"
            sensor_content += "<th style='padding: 8px; text-align: left; border: 1px solid #dee2e6;'>Sensor</th>"
            sensor_content += "<th style='padding: 8px; text-align: right; border: 1px solid #dee2e6;'>Value</th>"
            sensor_content += "<th style='padding: 8px; text-align: left; border: 1px solid #dee2e6;'>Unit</th>"
            sensor_content += "<th style='padding: 8px; text-align: left; border: 1px solid #dee2e6;'>Timestamp</th>"
            sensor_content += "</tr>"

            for i, reading in enumerate(self._snapshot.metrics.sensors):
                bg_color = "#f8f9fa" if i % 2 == 0 else "#ffffff"
                sensor_content += f"<tr style='background-color: {bg_color};'>"
                sensor_content += f"<td style='padding: 8px; border: 1px solid #dee2e6;'><b>{reading.sensor}</b></td>"
                sensor_content += f"<td style='padding: 8px; text-align: right; border: 1px solid #dee2e6;'>{reading.value}</td>"
                sensor_content += f"<td style='padding: 8px; border: 1px solid #dee2e6;'>{reading.unit}</td>"
                sensor_content += f"<td style='padding: 8px; border: 1px solid #dee2e6; font-family: monospace; font-size: 11px;'>{reading.timestamp}</td>"
                sensor_content += "</tr>"

            sensor_content += "</table>"
            sensor_text.setHtml(sensor_content)
            sensor_layout.addWidget(sensor_text)
        else:
            no_sensors = QLabel("No sensor readings available")
            no_sensors.setStyleSheet("color: gray; font-style: italic; padding: 16px;")
            sensor_layout.addWidget(no_sensors)

        layout.addWidget(sensor_group)

        # Events Section
        events_group = QGroupBox("Cached Events")
        events_layout = QVBoxLayout(events_group)
        events_layout.setSpacing(SPACING_GRID_PX)

        if self._snapshot.metrics.events.records:
            events_text = QTextEdit()
            events_text.setReadOnly(True)
            events_text.setMinimumHeight(150)

            events_content = f"<p><b>Total Events:</b> {self._snapshot.metrics.events.total_events}</p>"
            events_content += "<table style='width: 100%; border-collapse: collapse; margin-top: 8px;'>"
            events_content += "<tr style='background-color: #e9ecef; font-weight: bold;'>"
            events_content += "<th style='padding: 8px; text-align: left; border: 1px solid #dee2e6;'>Event Type</th>"
            events_content += "<th style='padding: 8px; text-align: right; border: 1px solid #dee2e6;'>Count</th>"
            events_content += "<th style='padding: 8px; text-align: left; border: 1px solid #dee2e6;'>Last Seen</th>"
            events_content += "</tr>"

            for i, record in enumerate(self._snapshot.metrics.events.records):
                bg_color = "#f8f9fa" if i % 2 == 0 else "#ffffff"
                events_content += f"<tr style='background-color: {bg_color};'>"
                events_content += f"<td style='padding: 8px; border: 1px solid #dee2e6;'><b>{record.event}</b></td>"
                events_content += f"<td style='padding: 8px; text-align: right; border: 1px solid #dee2e6;'>{record.count}</td>"
                events_content += f"<td style='padding: 8px; border: 1px solid #dee2e6; font-family: monospace; font-size: 11px;'>{record.last_seen}</td>"
                events_content += "</tr>"

            events_content += "</table>"
            events_text.setHtml(events_content)
            events_layout.addWidget(events_text)
        else:
            no_events = QLabel("No cached events")
            no_events.setStyleSheet("color: gray; font-style: italic; padding: 16px;")
            events_layout.addWidget(no_events)

        layout.addWidget(events_group)

        # Queue Metrics Section
        queue_group = QGroupBox("Queue Backlog")
        queue_layout = QVBoxLayout(queue_group)
        queue_layout.setSpacing(SPACING_GRID_PX)

        queue_text = QTextEdit()
        queue_text.setReadOnly(True)
        queue_text.setMaximumHeight(150)

        queue_content = f"<p><b>Total Backlog:</b> {self._snapshot.metrics.queues.total_backlog}</p>"
        queue_content += "<table style='width: 100%; border-collapse: collapse; margin-top: 8px;'>"
        queue_content += "<tr style='background-color: #e9ecef; font-weight: bold;'>"
        queue_content += "<th style='padding: 8px; text-align: left; border: 1px solid #dee2e6;'>Queue Name</th>"
        queue_content += "<th style='padding: 8px; text-align: right; border: 1px solid #dee2e6;'>Depth</th>"
        queue_content += "</tr>"

        for i, (queue_name, depth) in enumerate(self._snapshot.metrics.queues.queues.items()):
            bg_color = "#f8f9fa" if i % 2 == 0 else "#ffffff"
            # Color code based on depth
            if depth > 10:
                status_color = "#dc3545"  # Red for high backlog
            elif depth > 5:
                status_color = "#ffc107"  # Yellow for medium
            else:
                status_color = "#28a745"  # Green for low/zero

            queue_content += f"<tr style='background-color: {bg_color};'>"
            queue_content += f"<td style='padding: 8px; border: 1px solid #dee2e6;'><b>{queue_name}</b></td>"
            queue_content += f"<td style='padding: 8px; text-align: right; border: 1px solid #dee2e6; color: {status_color}; font-weight: bold;'>{depth}</td>"
            queue_content += "</tr>"

        queue_content += "</table>"
        queue_text.setHtml(queue_content)
        queue_layout.addWidget(queue_text)

        layout.addWidget(queue_group)

        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)


__all__ = [
    "FirstRunDialog",
    "JobAcceptanceDialog",
    "FieldOpsConfig",
    "SensorDetailsDialog",
]
