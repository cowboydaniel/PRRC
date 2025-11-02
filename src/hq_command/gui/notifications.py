"""
HQ Command GUI Notification System (Phase 3).

Provides notification components for:
- Notification badges and panels (3-17)
- Different notification types (escalation, assignment, system)
- Notification dismissal and management
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, timezone
from enum import Enum

from .qt_compat import (
    QWidget,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    Qt,
    pyqtSignal,
)
from .styles import theme
from .components import Badge, BadgeType, Card, Button, ButtonVariant


# =============================================================================
# NOTIFICATION TYPES
# =============================================================================

class NotificationType(Enum):
    """Types of notifications."""
    ESCALATION = "escalation"
    ASSIGNMENT = "assignment"
    SYSTEM = "system"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Notification:
    """Notification data structure."""
    notification_id: str
    notification_type: NotificationType
    title: str
    message: str
    timestamp: datetime
    read: bool = False
    actionable: bool = False
    action_label: Optional[str] = None
    action_callback: Optional[Callable] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


# Import dataclass
from dataclasses import dataclass


# =============================================================================
# NOTIFICATION BADGE
# =============================================================================

class NotificationBadge(QWidget):
    """
    Notification badge component showing unread count (3-17).

    Displays a badge with the number of unread notifications.
    """

    clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.unread_count = 0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Icon (using text emoji for now)
        self.icon_label = QLabel("🔔")
        self.icon_label.setStyleSheet("font-size: 20pt;")
        layout.addWidget(self.icon_label)

        # Badge with count
        self.count_badge = Badge("0", BadgeType.DANGER)
        self.count_badge.setVisible(False)
        layout.addWidget(self.count_badge)

        # Make clickable
        self.mousePressEvent = lambda e: self.clicked.emit()
        self.setCursor(Qt.PointingHandCursor)

    def set_unread_count(self, count: int):
        """Update unread notification count."""
        self.unread_count = count

        if count > 0:
            self.count_badge.setText(str(count))
            self.count_badge.setVisible(True)
        else:
            self.count_badge.setVisible(False)


# =============================================================================
# NOTIFICATION ITEM
# =============================================================================

class NotificationItem(QFrame):
    """
    Individual notification item in the notification panel (3-17).
    """

    dismissed = pyqtSignal(str)  # notification_id
    action_triggered = pyqtSignal(str)  # notification_id

    def __init__(
        self,
        notification: Notification,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self.notification = notification
        self.setObjectName("Card")

        # Style based on read status
        if not notification.read:
            self.setProperty("unread", True)

        self._build_ui()

    def _build_ui(self):
        """Build notification item UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            theme.SPACING_SM,
            theme.SPACING_SM,
            theme.SPACING_SM,
            theme.SPACING_SM,
        )
        layout.setSpacing(theme.SPACING_XS)

        # Header row (type badge + timestamp + dismiss button)
        header_layout = QHBoxLayout()

        # Type badge
        type_badge = self._get_type_badge()
        header_layout.addWidget(type_badge)

        # Timestamp
        timestamp_str = self._format_timestamp(self.notification.timestamp)
        timestamp_label = QLabel(timestamp_str)
        timestamp_label.setStyleSheet(f"color: {theme.NEUTRAL_500}; font-size: 11pt;")
        header_layout.addWidget(timestamp_label)

        header_layout.addStretch()

        # Dismiss button
        dismiss_btn = QPushButton("✕")
        dismiss_btn.setFixedSize(24, 24)
        dismiss_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {theme.NEUTRAL_500};
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {theme.DANGER};
            }}
        """)
        dismiss_btn.clicked.connect(lambda: self.dismissed.emit(self.notification.notification_id))
        header_layout.addWidget(dismiss_btn)

        layout.addLayout(header_layout)

        # Title
        title_label = QLabel(self.notification.title)
        title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        # Message
        message_label = QLabel(self.notification.message)
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        # Action button (if actionable)
        if self.notification.actionable and self.notification.action_label:
            action_btn = Button(
                self.notification.action_label,
                ButtonVariant.PRIMARY,
            )
            action_btn.clicked.connect(
                lambda: self.action_triggered.emit(self.notification.notification_id)
            )
            layout.addWidget(action_btn)

    def _get_type_badge(self) -> Badge:
        """Get badge for notification type."""
        type_map = {
            NotificationType.ESCALATION: ("⚠ Escalation", BadgeType.DANGER),
            NotificationType.ASSIGNMENT: ("📋 Assignment", BadgeType.INFO),
            NotificationType.SYSTEM: ("⚙ System", BadgeType.DEFAULT),
            NotificationType.WARNING: ("⚠ Warning", BadgeType.WARNING),
            NotificationType.INFO: ("ℹ Info", BadgeType.INFO),
        }

        text, badge_type = type_map.get(
            self.notification.notification_type,
            ("Notification", BadgeType.DEFAULT)
        )

        return Badge(text, badge_type)

    def _format_timestamp(self, timestamp: datetime) -> str:
        """Format timestamp for display."""
        now = datetime.now(timezone.utc)
        delta = now - timestamp

        if delta.total_seconds() < 60:
            return "Just now"
        elif delta.total_seconds() < 3600:
            minutes = int(delta.total_seconds() / 60)
            return f"{minutes}m ago"
        elif delta.total_seconds() < 86400:
            hours = int(delta.total_seconds() / 3600)
            return f"{hours}h ago"
        else:
            days = int(delta.total_seconds() / 86400)
            return f"{days}d ago"

    def mark_read(self):
        """Mark notification as read."""
        self.notification.read = True
        self.setProperty("unread", False)
        # Force style update
        self.style().unpolish(self)
        self.style().polish(self)


# =============================================================================
# NOTIFICATION PANEL
# =============================================================================

class NotificationPanel(QFrame):
    """
    Notification panel component (3-17).

    Displays a list of notifications with filtering and actions.
    """

    notification_dismissed = pyqtSignal(str)  # notification_id
    notification_action = pyqtSignal(str)  # notification_id

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.notifications: List[Notification] = []
        self.notification_items: Dict[str, NotificationItem] = {}

        self.setObjectName("Panel")
        self.setMinimumWidth(400)

        self._build_ui()

    def _build_ui(self):
        """Build notification panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setObjectName("PanelHeader")
        header_layout = QHBoxLayout(header)

        header_label = QLabel("Notifications")
        header_label.setStyleSheet("font-weight: bold; font-size: 14pt;")
        header_layout.addWidget(header_label)

        header_layout.addStretch()

        # Mark all read button
        self.mark_all_read_btn = Button("Mark All Read", ButtonVariant.OUTLINE)
        self.mark_all_read_btn.clicked.connect(self._mark_all_read)
        header_layout.addWidget(self.mark_all_read_btn)

        # Clear all button
        self.clear_all_btn = Button("Clear All", ButtonVariant.OUTLINE)
        self.clear_all_btn.clicked.connect(self._clear_all)
        header_layout.addWidget(self.clear_all_btn)

        layout.addWidget(header)

        # Scroll area for notifications
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        self.notifications_container = QWidget()
        self.notifications_layout = QVBoxLayout(self.notifications_container)
        self.notifications_layout.setContentsMargins(
            theme.SPACING_SM,
            theme.SPACING_SM,
            theme.SPACING_SM,
            theme.SPACING_SM,
        )
        self.notifications_layout.setSpacing(theme.SPACING_SM)
        self.notifications_layout.addStretch()

        scroll.setWidget(self.notifications_container)
        layout.addWidget(scroll)

        # Empty state
        self.empty_label = QLabel("No notifications")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(f"color: {theme.NEUTRAL_500}; padding: 40px;")
        self.notifications_layout.insertWidget(0, self.empty_label)

    def add_notification(self, notification: Notification):
        """Add a new notification to the panel."""
        # Hide empty state if visible
        if self.empty_label.isVisible():
            self.empty_label.setVisible(False)

        # Create notification item
        item = NotificationItem(notification)
        item.dismissed.connect(self._on_notification_dismissed)
        item.action_triggered.connect(self._on_notification_action)

        # Add to top of list
        self.notifications_layout.insertWidget(0, item)
        self.notifications.insert(0, notification)
        self.notification_items[notification.notification_id] = item

    def remove_notification(self, notification_id: str):
        """Remove a notification from the panel."""
        if notification_id in self.notification_items:
            item = self.notification_items[notification_id]
            self.notifications_layout.removeWidget(item)
            item.deleteLater()
            del self.notification_items[notification_id]

            # Remove from list
            self.notifications = [
                n for n in self.notifications
                if n.notification_id != notification_id
            ]

            # Show empty state if no notifications
            if not self.notifications:
                self.empty_label.setVisible(True)

    def get_unread_count(self) -> int:
        """Get count of unread notifications."""
        return sum(1 for n in self.notifications if not n.read)

    def _mark_all_read(self):
        """Mark all notifications as read."""
        for item in self.notification_items.values():
            item.mark_read()

    def _clear_all(self):
        """Clear all notifications."""
        for notification_id in list(self.notification_items.keys()):
            self.remove_notification(notification_id)

    def _on_notification_dismissed(self, notification_id: str):
        """Handle notification dismissal."""
        self.remove_notification(notification_id)
        self.notification_dismissed.emit(notification_id)

    def _on_notification_action(self, notification_id: str):
        """Handle notification action."""
        # Find notification and execute callback if present
        notification = next(
            (n for n in self.notifications if n.notification_id == notification_id),
            None
        )

        if notification and notification.action_callback:
            notification.action_callback()

        self.notification_action.emit(notification_id)


# =============================================================================
# NOTIFICATION MANAGER
# =============================================================================

class NotificationManager:
    """
    Notification manager for creating and managing notifications (3-17).

    Centralized notification management with type-specific helpers.
    """

    def __init__(self, notification_panel: NotificationPanel):
        self.panel = notification_panel
        self._notification_counter = 0

    def _generate_id(self) -> str:
        """Generate unique notification ID."""
        self._notification_counter += 1
        return f"notification-{self._notification_counter}"

    def add_escalation_notification(
        self,
        task_id: str,
        reason: str,
        action_callback: Optional[Callable] = None,
    ):
        """Add an escalation notification."""
        notification = Notification(
            notification_id=self._generate_id(),
            notification_type=NotificationType.ESCALATION,
            title=f"Task {task_id} Escalated",
            message=f"Reason: {reason}",
            timestamp=datetime.now(timezone.utc),
            actionable=action_callback is not None,
            action_label="View Task" if action_callback else None,
            action_callback=action_callback,
        )

        self.panel.add_notification(notification)

    def add_assignment_notification(
        self,
        task_id: str,
        unit_ids: List[str],
        action_callback: Optional[Callable] = None,
    ):
        """Add an assignment notification."""
        units_str = ", ".join(unit_ids)
        notification = Notification(
            notification_id=self._generate_id(),
            notification_type=NotificationType.ASSIGNMENT,
            title="New Assignment",
            message=f"Task {task_id} assigned to: {units_str}",
            timestamp=datetime.now(timezone.utc),
            actionable=action_callback is not None,
            action_label="View Assignment" if action_callback else None,
            action_callback=action_callback,
        )

        self.panel.add_notification(notification)

    def add_system_notification(
        self,
        title: str,
        message: str,
        action_callback: Optional[Callable] = None,
        action_label: Optional[str] = None,
    ):
        """Add a system notification."""
        notification = Notification(
            notification_id=self._generate_id(),
            notification_type=NotificationType.SYSTEM,
            title=title,
            message=message,
            timestamp=datetime.now(timezone.utc),
            actionable=action_callback is not None,
            action_label=action_label,
            action_callback=action_callback,
        )

        self.panel.add_notification(notification)

    def add_warning_notification(self, title: str, message: str):
        """Add a warning notification."""
        notification = Notification(
            notification_id=self._generate_id(),
            notification_type=NotificationType.WARNING,
            title=title,
            message=message,
            timestamp=datetime.now(timezone.utc),
        )

        self.panel.add_notification(notification)

    def add_info_notification(self, title: str, message: str):
        """Add an info notification."""
        notification = Notification(
            notification_id=self._generate_id(),
            notification_type=NotificationType.INFO,
            title=title,
            message=message,
            timestamp=datetime.now(timezone.utc),
        )

        self.panel.add_notification(notification)
