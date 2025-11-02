"""
Kanban Board for HQ Command GUI (Phase 2).

Provides visual task management with drag-drop preparation.
Implements tasks 2-14 to 2-16.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .qt_compat import (
    QT_AVAILABLE,
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
from .components import Card, Heading, Caption, Badge, BadgeType
from .styles import theme


class TaskCard(Card):
    """
    Rich task card for Kanban board display.

    Shows task ID, priority, capabilities, assigned units, and metadata.
    """

    # Signals
    clicked = pyqtSignal(str)  # task_id

    def __init__(self, task_data: Dict[str, Any], parent: Optional[QWidget] = None):
        """
        Initialize task card.

        Args:
            task_data: Task data dictionary with keys:
                       task_id, priority, required_capabilities, assigned_units, status
            parent: Parent widget
        """
        super().__init__(parent)

        self._task_data = task_data
        self._task_id = task_data.get("task_id", "")

        self._setup_ui()

        # Make clickable
        self.setCursor(Qt.PointingHandCursor)

    def _setup_ui(self) -> None:
        """Set up task card UI."""
        # Task ID header
        task_id_label = Heading(self._task_id, level=5)
        self.layout.addWidget(task_id_label)

        # Priority badge
        priority = self._task_data.get("priority", 0)
        priority_badge = Badge(f"P{priority}", self._get_priority_badge_type(priority))
        self.layout.addWidget(priority_badge)

        # Status if escalated
        if self._task_data.get("escalated", False):
            escalation_badge = Badge("⚠️ ESCALATED", BadgeType.DANGER)
            self.layout.addWidget(escalation_badge)

        # Capabilities
        capabilities = self._task_data.get("required_capabilities", [])
        if capabilities:
            caps_layout = QHBoxLayout()
            caps_label = Caption("Required:")
            caps_layout.addWidget(caps_label)

            for cap in capabilities[:3]:  # Show max 3
                cap_badge = Badge(cap, BadgeType.INFO)
                caps_layout.addWidget(cap_badge)

            if len(capabilities) > 3:
                more_label = Caption(f"+{len(capabilities) - 3} more")
                caps_layout.addWidget(more_label)

            caps_layout.addStretch()
            self.layout.addLayout(caps_layout)

        # Assigned units
        assigned_units = self._task_data.get("assigned_units", [])
        if assigned_units:
            units_layout = QHBoxLayout()
            units_label = Caption(f"Assigned to {len(assigned_units)} unit(s)")
            units_layout.addWidget(units_label)
            units_layout.addStretch()
            self.layout.addLayout(units_layout)
        else:
            unassigned_label = Caption("No units assigned")
            unassigned_label.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-style: italic;")
            self.layout.addWidget(unassigned_label)

    def _get_priority_badge_type(self, priority: int) -> BadgeType:
        """Get badge type based on priority."""
        if priority == 1:
            return BadgeType.DANGER
        elif priority == 2:
            return BadgeType.WARNING
        elif priority == 3:
            return BadgeType.INFO
        else:
            return BadgeType.DEFAULT

    def mousePressEvent(self, event) -> None:
        """Handle mouse click."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._task_id)
        super().mousePressEvent(event)

    @property
    def task_id(self) -> str:
        """Get task ID."""
        return self._task_id


class KanbanColumn(QWidget):
    """
    Single column in the Kanban board.

    Displays tasks in a specific status with header showing count.
    """

    # Signals
    task_clicked = pyqtSignal(str, str)  # column_name, task_id

    def __init__(self, title: str, status_key: str, parent: Optional[QWidget] = None):
        """
        Initialize Kanban column.

        Args:
            title: Column display title
            status_key: Task status key for this column
            parent: Parent widget
        """
        super().__init__(parent)

        self._title = title
        self._status_key = status_key
        self._task_cards: List[TaskCard] = []

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up column UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACING_SM, theme.SPACING_SM, theme.SPACING_SM, theme.SPACING_SM)
        layout.setSpacing(theme.SPACING_SM)

        # Column header with count
        self._header_label = Heading(f"{self._title} (0)", level=4)
        layout.addWidget(self._header_label)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(f"background-color: {theme.BORDER_COLOR};")
        layout.addWidget(separator)

        # Scrollable task container
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._tasks_container = QWidget()
        self._tasks_layout = QVBoxLayout(self._tasks_container)
        self._tasks_layout.setSpacing(theme.SPACING_SM)
        self._tasks_layout.addStretch()

        scroll_area.setWidget(self._tasks_container)
        layout.addWidget(scroll_area)

        # Set background color
        self.setStyleSheet(f"""
            KanbanColumn {{
                background-color: {theme.BACKGROUND_SECONDARY};
                border-radius: {theme.BORDER_RADIUS_SM}px;
            }}
        """)

        self.setMinimumWidth(300)

    def add_task(self, task_data: Dict[str, Any]) -> None:
        """Add a task card to this column."""
        task_card = TaskCard(task_data)
        task_card.clicked.connect(lambda tid: self.task_clicked.emit(self._status_key, tid))

        self._task_cards.append(task_card)
        self._tasks_layout.insertWidget(self._tasks_layout.count() - 1, task_card)

        self._update_header()

    def clear_tasks(self) -> None:
        """Remove all task cards."""
        for card in self._task_cards:
            self._tasks_layout.removeWidget(card)
            card.deleteLater()

        self._task_cards.clear()
        self._update_header()

    def _update_header(self) -> None:
        """Update column header with task count."""
        count = len(self._task_cards)
        self._header_label.setText(f"{self._title} ({count})")

    @property
    def status_key(self) -> str:
        """Get status key for this column."""
        return self._status_key


class KanbanBoard(QWidget):
    """
    Kanban board for visual task management.

    Features (Tasks 2-14 to 2-16):
    - 4-column board (Queued, Active, Monitoring, After Action)
    - Card-based task display with metadata
    - Column headers with task counts
    - Horizontal scrolling for narrow screens
    - Rich task cards with priority, capabilities, assignments
    - Drag-drop preparation (interaction model designed, Phase 3 implementation)
    """

    # Signals
    task_clicked = pyqtSignal(str, str)  # status, task_id

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._columns: Dict[str, KanbanColumn] = {}

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up Kanban board UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.SPACING_SM)

        # Header
        title = Heading("Task Board (Kanban)", level=3)
        layout.addWidget(title)

        # Horizontal scrollable board
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        board_container = QWidget()
        board_layout = QHBoxLayout(board_container)
        board_layout.setSpacing(theme.SPACING_MD)

        # Create 4 columns
        column_configs = [
            ("Queued", "queued"),
            ("Active", "assigned"),
            ("Monitoring", "monitoring"),
            ("After Action", "completed"),
        ]

        for title, status_key in column_configs:
            column = KanbanColumn(title, status_key)
            column.task_clicked.connect(self.task_clicked.emit)
            self._columns[status_key] = column
            board_layout.addWidget(column)

        board_layout.addStretch()

        scroll_area.setWidget(board_container)
        layout.addWidget(scroll_area)

    def set_tasks(self, tasks: List[Dict[str, Any]]) -> None:
        """
        Set all tasks on the Kanban board.

        Args:
            tasks: List of task dictionaries with keys: task_id, priority,
                   required_capabilities, assigned_units, status, escalated
        """
        # Clear all columns
        for column in self._columns.values():
            column.clear_tasks()

        # Add tasks to appropriate columns
        for task in tasks:
            status = task.get("status", "pending").lower()

            # Map status to column
            if status == "pending" or status == "deferred":
                column_key = "queued"
            elif status == "assigned":
                column_key = "assigned"
            elif status == "escalated":
                column_key = "assigned"  # Escalated tasks stay in active
            elif status == "completed":
                column_key = "completed"
            else:
                column_key = "queued"  # Default

            if column_key in self._columns:
                self._columns[column_key].add_task(task)

    def get_column_tasks(self, status_key: str) -> List[str]:
        """Get task IDs in a specific column."""
        if status_key in self._columns:
            column = self._columns[status_key]
            return [card.task_id for card in column._task_cards]
        return []


# Drag-drop interaction design (for Phase 3 implementation)
"""
DRAG-DROP INTERACTION MODEL (Task 2-16)

Valid column transitions:
- Queued → Active (assign units)
- Active → Monitoring (task in progress)
- Monitoring → After Action (complete task)
- Any → Queued (defer/reassign)

Visual feedback:
- Drag state: Card becomes semi-transparent, shows grab cursor
- Valid drop zone: Column highlights with accent color border
- Invalid drop zone: Column shows red border
- Drop animation: Card smoothly slides into position

State change triggers:
- Queued → Active: Opens assignment dialog if no units assigned
- Active → Monitoring: Confirms task is in progress
- Monitoring → After Action: Marks task as completed
- Any → Queued: Defers task with reason capture

Implementation notes for Phase 3:
1. Enable drag-drop on TaskCard widgets
2. Implement dragEnterEvent/dropEvent on KanbanColumn
3. Add transition validation logic
4. Connect drop events to controller actions
5. Add smooth animation on successful drop
"""
