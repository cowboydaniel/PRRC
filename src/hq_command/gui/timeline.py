"""
Timeline View for HQ Command GUI (Phase 2).

Provides chronological event stream for tracking task lifecycle events.
Implements tasks 2-11 to 2-13.
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
    QScrollArea,
    Qt,
    pyqtSignal,
)
from .components import Card, Heading, Caption, Badge, BadgeType, Input, Select
from .styles import theme


class EventCard(Card):
    """
    Card component for displaying a single timeline event.

    Shows event type, timestamp, details, and related entities.
    """

    def __init__(
        self,
        event_type: str,
        timestamp: str,
        details: str,
        parent: Optional[QWidget] = None,
    ):
        """
        Initialize event card.

        Args:
            event_type: Type of event (task_created, assignment, escalation, etc.)
            timestamp: ISO timestamp string
            details: Event description
            parent: Parent widget
        """
        super().__init__(parent)

        self._event_type = event_type
        self._timestamp = timestamp
        self._details = details

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up event card UI."""
        # Event type badge
        badge_type = self._get_badge_type(self._event_type)
        type_badge = Badge(self._format_event_type(self._event_type), badge_type)
        self.layout.addWidget(type_badge)

        # Timestamp
        time_label = Caption(self._format_timestamp(self._timestamp))
        self.layout.addWidget(time_label)

        # Details
        details_label = QLabel(self._details)
        details_label.setWordWrap(True)
        self.layout.addWidget(details_label)

    def _get_badge_type(self, event_type: str) -> BadgeType:
        """Determine badge type based on event type."""
        if "escalat" in event_type.lower():
            return BadgeType.DANGER
        elif "complet" in event_type.lower():
            return BadgeType.SUCCESS
        elif "assign" in event_type.lower():
            return BadgeType.INFO
        elif "creat" in event_type.lower():
            return BadgeType.DEFAULT
        else:
            return BadgeType.WARNING

    def _format_event_type(self, event_type: str) -> str:
        """Format event type for display."""
        return event_type.replace("_", " ").title()

    def _format_timestamp(self, timestamp: str) -> str:
        """Format timestamp for display."""
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, AttributeError):
            return timestamp


class TimelineView(QWidget):
    """
    Chronological event stream view for HQ Command operations.

    Features (Tasks 2-11 to 2-13):
    - Chronological event stream
    - Event cards for different types (task creation, assignment, completion, escalation)
    - Time grouping (last hour, today, this week)
    - Auto-scroll for new events
    - Event type filtering
    - Time range selector
    - Search functionality
    - Export timeline capability
    """

    # Signals
    export_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._events: List[Dict[str, Any]] = []
        self._filtered_events: List[Dict[str, Any]] = []

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up timeline view UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.SPACING_SM)

        # Header with filters
        header_layout = QHBoxLayout()

        title = Heading("Situational Timeline", level=3)
        header_layout.addWidget(title)

        # Time range filter
        self._time_filter = Select(["Last Hour", "Today", "This Week", "All Time"])
        self._time_filter.setMaximumWidth(150)
        header_layout.addWidget(QLabel("Time:"))
        header_layout.addWidget(self._time_filter)

        # Event type filter
        self._type_filter = Select([
            "All Events",
            "Task Created",
            "Task Assigned",
            "Task Escalated",
            "Task Completed",
            "Status Change",
        ])
        self._type_filter.setMaximumWidth(150)
        header_layout.addWidget(QLabel("Type:"))
        header_layout.addWidget(self._type_filter)

        # Search box
        self._search_input = Input(placeholder="Search events...")
        self._search_input.setMaximumWidth(200)
        header_layout.addWidget(self._search_input)

        # Export button
        self._export_button = QPushButton("Export")
        self._export_button.setMaximumWidth(100)
        header_layout.addWidget(self._export_button)

        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Scrollable event container
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        self._events_container = QWidget()
        self._events_layout = QVBoxLayout(self._events_container)
        self._events_layout.setSpacing(theme.SPACING_SM)
        self._events_layout.addStretch()

        scroll_area.setWidget(self._events_container)

        layout.addWidget(scroll_area)

    def _connect_signals(self) -> None:
        """Connect UI signals."""
        self._time_filter.currentTextChanged.connect(self._on_filter_changed)
        self._type_filter.currentTextChanged.connect(self._on_filter_changed)
        self._search_input.textChanged.connect(self._on_search_changed)
        self._export_button.clicked.connect(self.export_requested.emit)

    def add_event(
        self,
        event_type: str,
        timestamp: str,
        details: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a new event to the timeline.

        Args:
            event_type: Type of event
            timestamp: ISO timestamp string
            details: Event description
            metadata: Additional event metadata
        """
        event_data = {
            "event_type": event_type,
            "timestamp": timestamp,
            "details": details,
            "metadata": metadata or {},
        }

        self._events.append(event_data)
        self._apply_filters()

    def set_events(self, events: List[Dict[str, Any]]) -> None:
        """
        Set all timeline events (replacing existing).

        Args:
            events: List of event dictionaries with keys: event_type, timestamp, details, metadata
        """
        self._events = events
        self._apply_filters()

    def _apply_filters(self) -> None:
        """Apply current filters to events and update display."""
        # Start with all events
        filtered = self._events.copy()

        # Apply time filter
        time_range = self._time_filter.currentText()
        if time_range != "All Time":
            filtered = self._filter_by_time(filtered, time_range)

        # Apply type filter
        event_type = self._type_filter.currentText()
        if event_type != "All Events":
            filtered = self._filter_by_type(filtered, event_type)

        # Apply search filter
        search_text = self._search_input.text().lower().strip()
        if search_text:
            filtered = [
                e for e in filtered
                if search_text in e.get("details", "").lower()
                or search_text in e.get("event_type", "").lower()
            ]

        self._filtered_events = filtered
        self._update_display()

    def _filter_by_time(self, events: List[Dict[str, Any]], time_range: str) -> List[Dict[str, Any]]:
        """Filter events by time range."""
        now = datetime.now()

        filtered = []
        for event in events:
            try:
                timestamp = event.get("timestamp", "")
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

                if time_range == "Last Hour":
                    if (now - dt).total_seconds() <= 3600:
                        filtered.append(event)
                elif time_range == "Today":
                    if dt.date() == now.date():
                        filtered.append(event)
                elif time_range == "This Week":
                    if (now - dt).days <= 7:
                        filtered.append(event)
            except (ValueError, AttributeError):
                # Include events with invalid timestamps
                filtered.append(event)

        return filtered

    def _filter_by_type(self, events: List[Dict[str, Any]], event_type: str) -> List[Dict[str, Any]]:
        """Filter events by type."""
        type_map = {
            "Task Created": "task_created",
            "Task Assigned": "task_assigned",
            "Task Escalated": "task_escalated",
            "Task Completed": "task_completed",
            "Status Change": "status_change",
        }

        target_type = type_map.get(event_type, event_type.lower().replace(" ", "_"))

        return [e for e in events if e.get("event_type", "").lower() == target_type]

    def _update_display(self) -> None:
        """Update the event display with filtered events."""
        # Clear existing event cards
        while self._events_layout.count() > 1:  # Keep the stretch
            item = self._events_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Sort events by timestamp (newest first)
        sorted_events = sorted(
            self._filtered_events,
            key=lambda e: e.get("timestamp", ""),
            reverse=True,
        )

        # Group events by day
        current_group = None
        for event in sorted_events:
            # Add date separator if needed
            timestamp = event.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                date_str = dt.strftime("%Y-%m-%d")

                if date_str != current_group:
                    current_group = date_str
                    separator = Heading(dt.strftime("%B %d, %Y"), level=5)
                    separator.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; margin-top: {theme.SPACING_MD}px;")
                    self._events_layout.insertWidget(self._events_layout.count() - 1, separator)
            except (ValueError, AttributeError):
                pass

            # Add event card
            event_card = EventCard(
                event_type=event.get("event_type", ""),
                timestamp=timestamp,
                details=event.get("details", ""),
            )
            self._events_layout.insertWidget(self._events_layout.count() - 1, event_card)

    def _on_filter_changed(self, _text: str = "") -> None:
        """Handle filter changes."""
        self._apply_filters()

    def _on_search_changed(self, _text: str) -> None:
        """Handle search text changes."""
        self._apply_filters()

    def get_events(self) -> List[Dict[str, Any]]:
        """Get all events (for export)."""
        return self._events.copy()

    def get_filtered_events(self) -> List[Dict[str, Any]]:
        """Get currently filtered events."""
        return self._filtered_events.copy()
