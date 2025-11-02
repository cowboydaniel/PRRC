"""
HQ Command GUI Component Library.

Provides reusable UI components (buttons, badges, cards, inputs, dialogs)
with consistent styling and accessibility features.
"""

from typing import Optional, List
from enum import Enum

from .qt_compat import (
    QWidget,
    QPushButton,
    QLabel,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QProgressBar,
    QDialog,
    QDialogButtonBox,
    Qt,
    pyqtSignal,
)
from .styles import theme


# =============================================================================
# ENUMS
# =============================================================================

class ButtonVariant(Enum):
    """Button style variants."""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    DANGER = "danger"
    OUTLINE = "outline"


class BadgeType(Enum):
    """Badge/chip style types."""
    DEFAULT = "default"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"
    INFO = "info"


class StatusType(Enum):
    """Status indicator types."""
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"
    INFO = "info"


# =============================================================================
# BUTTONS
# =============================================================================

class Button(QPushButton):
    """
    Styled button component with variants.

    Supports primary, secondary, danger, and outline styles.
    Ensures minimum touch target size for accessibility.
    """

    def __init__(
        self,
        text: str = "",
        variant: ButtonVariant = ButtonVariant.PRIMARY,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(text, parent)
        self.variant = variant
        self.setMinimumHeight(theme.MIN_TOUCH_TARGET)
        self._apply_variant()

    def _apply_variant(self):
        """Apply object name based on variant for stylesheet matching."""
        if self.variant == ButtonVariant.SECONDARY:
            self.setObjectName("SecondaryButton")
        elif self.variant == ButtonVariant.DANGER:
            self.setObjectName("DangerButton")
        elif self.variant == ButtonVariant.OUTLINE:
            self.setObjectName("OutlineButton")
        else:
            self.setObjectName("")  # Use default primary styling

    def set_variant(self, variant: ButtonVariant):
        """Change button variant dynamically."""
        self.variant = variant
        self._apply_variant()
        self.style().unpolish(self)
        self.style().polish(self)


# =============================================================================
# BADGES / CHIPS
# =============================================================================

class Badge(QLabel):
    """
    Badge/chip component for status indicators and labels.

    Supports different types (success, warning, danger, info) with
    appropriate color coding.
    """

    def __init__(
        self,
        text: str = "",
        badge_type: BadgeType = BadgeType.DEFAULT,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(text, parent)
        self.badge_type = badge_type
        self.setObjectName("Badge")
        self._apply_type()

    def _apply_type(self):
        """Apply type attribute for stylesheet matching."""
        if self.badge_type != BadgeType.DEFAULT:
            self.setProperty("type", self.badge_type.value)

    def set_type(self, badge_type: BadgeType):
        """Change badge type dynamically."""
        self.badge_type = badge_type
        self._apply_type()
        self.style().unpolish(self)
        self.style().polish(self)


# =============================================================================
# STATUS INDICATOR
# =============================================================================

class StatusBadge(QLabel):
    """
    Status badge for displaying sync status, escalation counts, etc.

    Used in status bar and other locations requiring status display.
    """

    def __init__(
        self,
        text: str = "",
        status: StatusType = StatusType.SUCCESS,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(text, parent)
        self.status = status
        self.setObjectName("StatusBadge")
        self._apply_status()

    def _apply_status(self):
        """Apply status attribute for stylesheet matching."""
        self.setProperty("status", self.status.value)

    def set_status(self, status: StatusType):
        """Update status type dynamically."""
        self.status = status
        self._apply_status()
        self.style().unpolish(self)
        self.style().polish(self)


# =============================================================================
# CARDS / PANELS
# =============================================================================

class Card(QFrame):
    """
    Card component for containing related content.

    Provides consistent styling with rounded corners, borders, and padding.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFrameShape(QFrame.StyledPanel)

        # Set up layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(
            theme.SPACING_MD,
            theme.SPACING_MD,
            theme.SPACING_MD,
            theme.SPACING_MD,
        )
        self.layout.setSpacing(theme.SPACING_SM)

    def add_widget(self, widget: QWidget):
        """Add a widget to the card."""
        self.layout.addWidget(widget)

    def add_layout(self, layout):
        """Add a layout to the card."""
        self.layout.addLayout(layout)


class Panel(QFrame):
    """
    Panel component for grouping related controls.

    Similar to Card but with lighter styling.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setFrameShape(QFrame.StyledPanel)

        # Set up layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(
            theme.SPACING_MD,
            theme.SPACING_MD,
            theme.SPACING_MD,
            theme.SPACING_MD,
        )
        self.layout.setSpacing(theme.SPACING_SM)

    def add_widget(self, widget: QWidget):
        """Add a widget to the panel."""
        self.layout.addWidget(widget)


# =============================================================================
# TYPOGRAPHY COMPONENTS
# =============================================================================

class Heading(QLabel):
    """
    Heading label with predefined sizes (H1-H6).
    """

    def __init__(
        self,
        text: str = "",
        level: int = 1,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(text, parent)
        self.level = max(1, min(6, level))  # Clamp between 1-6
        self.setObjectName(f"H{self.level}")


class Caption(QLabel):
    """
    Caption label for small, secondary text.
    """

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setObjectName("Caption")


# =============================================================================
# FORM INPUTS
# =============================================================================

class Input(QLineEdit):
    """
    Styled text input with consistent sizing and appearance.
    """

    def __init__(
        self,
        placeholder: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setMinimumHeight(theme.MIN_TOUCH_TARGET)


class Select(QComboBox):
    """
    Styled dropdown select with consistent sizing and appearance.
    """

    def __init__(
        self,
        items: Optional[List[str]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setMinimumHeight(theme.MIN_TOUCH_TARGET)
        if items:
            self.addItems(items)


class Checkbox(QCheckBox):
    """
    Styled checkbox with consistent sizing.
    """

    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(text, parent)
        self.setMinimumHeight(theme.MIN_TOUCH_TARGET)


# =============================================================================
# LOADING INDICATORS
# =============================================================================

class LoadingSpinner(QProgressBar):
    """
    Indeterminate progress bar for loading states.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimum(0)
        self.setMaximum(0)  # Indeterminate mode
        self.setTextVisible(False)


class ProgressIndicator(QProgressBar):
    """
    Determinate progress bar for showing completion progress.
    """

    def __init__(
        self,
        minimum: int = 0,
        maximum: int = 100,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setMinimum(minimum)
        self.setMaximum(maximum)
        self.setTextVisible(True)


# =============================================================================
# SKELETON SCREEN
# =============================================================================

class SkeletonLoader(QWidget):
    """
    Skeleton screen component for data loading states.

    Displays placeholder rectangles that animate to indicate loading.
    """

    def __init__(
        self,
        num_lines: int = 3,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(theme.SPACING_SM)

        for i in range(num_lines):
            line = QFrame(self)
            line.setFrameShape(QFrame.StyledPanel)
            line.setMinimumHeight(theme.SPACING_LG)
            line.setStyleSheet(f"""
                QFrame {{
                    background-color: {theme.NEUTRAL_200};
                    border-radius: {theme.BORDER_RADIUS_SM}px;
                }}
            """)
            layout.addWidget(line)


# =============================================================================
# MODAL DIALOG
# =============================================================================

class Modal(QDialog):
    """
    Base modal dialog with consistent styling and button layout.
    """

    def __init__(
        self,
        title: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)

        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(
            theme.SPACING_LG,
            theme.SPACING_LG,
            theme.SPACING_LG,
            theme.SPACING_LG,
        )
        self.main_layout.setSpacing(theme.SPACING_MD)

        # Title
        if title:
            self.title_label = Heading(title, level=3)
            self.main_layout.addWidget(self.title_label)

        # Content area
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(theme.SPACING_SM)
        self.main_layout.addLayout(self.content_layout)

        # Button box
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.main_layout.addWidget(self.button_box)

    def add_content(self, widget: QWidget):
        """Add content widget to the modal."""
        self.content_layout.addWidget(widget)


# =============================================================================
# ERROR DISPLAY
# =============================================================================

class ErrorMessage(QFrame):
    """
    Error message component for displaying errors inline.

    Styled with danger color for visibility.
    """

    def __init__(
        self,
        message: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setStyleSheet(f"""
            QFrame#Card {{
                background-color: {theme.DANGER};
                border: 1px solid {theme.DANGER};
                border-radius: {theme.BORDER_RADIUS_SM}px;
                padding: {theme.SPACING_MD}px;
            }}
            QLabel {{
                color: white;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            theme.SPACING_MD,
            theme.SPACING_SM,
            theme.SPACING_MD,
            theme.SPACING_SM,
        )

        # Error icon (text-based for now)
        icon_label = QLabel("⚠️")
        icon_label.setStyleSheet("font-size: 18pt;")
        layout.addWidget(icon_label)

        # Error message
        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label, 1)

    def set_message(self, message: str):
        """Update error message."""
        self.message_label.setText(message)


class WarningMessage(QFrame):
    """
    Warning message component for displaying warnings inline.

    Styled with warning color for visibility.
    """

    def __init__(
        self,
        message: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setStyleSheet(f"""
            QFrame#Card {{
                background-color: {theme.WARNING};
                border: 1px solid {theme.WARNING};
                border-radius: {theme.BORDER_RADIUS_SM}px;
                padding: {theme.SPACING_MD}px;
            }}
            QLabel {{
                color: {theme.ACCENT_CONTRAST};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            theme.SPACING_MD,
            theme.SPACING_SM,
            theme.SPACING_MD,
            theme.SPACING_SM,
        )

        # Warning icon
        icon_label = QLabel("⚠")
        icon_label.setStyleSheet("font-size: 18pt;")
        layout.addWidget(icon_label)

        # Warning message
        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label, 1)

    def set_message(self, message: str):
        """Update warning message."""
        self.message_label.setText(message)


class SuccessMessage(QFrame):
    """
    Success message component for displaying success notifications inline.

    Styled with success color for visibility.
    """

    def __init__(
        self,
        message: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setStyleSheet(f"""
            QFrame#Card {{
                background-color: {theme.SUCCESS};
                border: 1px solid {theme.SUCCESS};
                border-radius: {theme.BORDER_RADIUS_SM}px;
                padding: {theme.SPACING_MD}px;
            }}
            QLabel {{
                color: white;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            theme.SPACING_MD,
            theme.SPACING_SM,
            theme.SPACING_MD,
            theme.SPACING_SM,
        )

        # Success icon
        icon_label = QLabel("✓")
        icon_label.setStyleSheet("font-size: 18pt; font-weight: bold;")
        layout.addWidget(icon_label)

        # Success message
        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label, 1)

    def set_message(self, message: str):
        """Update success message."""
        self.message_label.setText(message)
