"""
Chart Integration Framework for HQ Command GUI.

Provides visualization components including gauges, sparklines,
and basic charts without requiring external chart libraries.

Uses Qt's QPainter for custom rendering.
"""

from __future__ import annotations

from typing import List, Optional, Tuple
from enum import Enum

from .qt_compat import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QPainter,
    QPen,
    QBrush,
    QColor,
    QRect,
    QSize,
    Qt,
    QPolygonF,
    QPointF,
)
from .components import Card, Heading, Caption
from .styles import theme


class GaugeStyle(Enum):
    """Visual style for gauge charts."""
    CIRCULAR = "circular"
    HORIZONTAL_BAR = "horizontal_bar"
    VERTICAL_BAR = "vertical_bar"


class GaugeChart(QWidget):
    """
    Gauge chart for displaying a value within a range (e.g., 0-100).

    Supports multiple visual styles and color thresholds.
    """

    def __init__(
        self,
        title: str = "",
        min_value: float = 0.0,
        max_value: float = 100.0,
        current_value: float = 0.0,
        style: GaugeStyle = GaugeStyle.CIRCULAR,
        parent: Optional[QWidget] = None,
    ):
        """
        Initialize gauge chart.

        Args:
            title: Chart title
            min_value: Minimum value on the scale
            max_value: Maximum value on the scale
            current_value: Current value to display
            style: Visual style (circular, horizontal bar, vertical bar)
            parent: Parent widget
        """
        super().__init__(parent)

        self._title = title
        self._min_value = min_value
        self._max_value = max_value
        self._current_value = current_value
        self._style = style

        # Color thresholds (value -> color)
        self._thresholds: List[Tuple[float, str]] = []

        self.setMinimumSize(120, 120)

    def set_value(self, value: float) -> None:
        """Update the gauge value and repaint."""
        self._current_value = max(self._min_value, min(self._max_value, value))
        self.update()

    def set_thresholds(self, thresholds: List[Tuple[float, str]]) -> None:
        """
        Set color thresholds for the gauge.

        Args:
            thresholds: List of (threshold_value, color) tuples.
                       Example: [(50, "#F6A000"), (75, "#C4373B")]
        """
        self._thresholds = sorted(thresholds, key=lambda x: x[0])
        self.update()

    def _get_color_for_value(self, value: float) -> str:
        """Determine color based on value and thresholds."""
        if not self._thresholds:
            return theme.PRIMARY

        for threshold, color in reversed(self._thresholds):
            if value >= threshold:
                return color

        # Below all thresholds - use first color or default
        if self._thresholds:
            return self._thresholds[0][1]
        return theme.PRIMARY

    def paintEvent(self, event) -> None:
        """Paint the gauge based on style."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._style == GaugeStyle.CIRCULAR:
            self._paint_circular_gauge(painter)
        elif self._style == GaugeStyle.HORIZONTAL_BAR:
            self._paint_horizontal_bar(painter)
        elif self._style == GaugeStyle.VERTICAL_BAR:
            self._paint_vertical_bar(painter)

    def _paint_circular_gauge(self, painter: QPainter) -> None:
        """Paint circular gauge (arc)."""
        rect = self.rect()
        size = min(rect.width(), rect.height())
        margin = 10

        # Center the gauge
        gauge_rect = QRect(
            rect.x() + (rect.width() - size) // 2 + margin,
            rect.y() + (rect.height() - size) // 2 + margin,
            size - 2 * margin,
            size - 2 * margin,
        )

        # Background arc
        painter.setPen(QPen(QColor(theme.NEUTRAL_200), 10, Qt.SolidLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(gauge_rect, 0, 360 * 16)  # Full circle

        # Value arc
        ratio = (self._current_value - self._min_value) / (self._max_value - self._min_value)
        angle = int(360 * ratio * 16)  # Qt uses 1/16th degree units
        color = self._get_color_for_value(self._current_value)
        painter.setPen(QPen(QColor(color), 10, Qt.SolidLine))
        painter.drawArc(gauge_rect, 90 * 16, -angle)  # Start from top, go clockwise

        # Draw value text in center
        painter.setPen(QColor(theme.TEXT_PRIMARY))
        painter.setFont(painter.font())
        value_text = f"{self._current_value:.0f}"
        painter.drawText(gauge_rect, Qt.AlignCenter, value_text)

    def _paint_horizontal_bar(self, painter: QPainter) -> None:
        """Paint horizontal progress bar gauge."""
        rect = self.rect()
        bar_height = 20
        margin = 5

        bar_rect = QRect(
            rect.x() + margin,
            rect.y() + (rect.height() - bar_height) // 2,
            rect.width() - 2 * margin,
            bar_height,
        )

        # Background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(theme.NEUTRAL_200)))
        painter.drawRoundedRect(bar_rect, 4, 4)

        # Value bar
        ratio = (self._current_value - self._min_value) / (self._max_value - self._min_value)
        value_width = int(bar_rect.width() * ratio)
        value_rect = QRect(bar_rect.x(), bar_rect.y(), value_width, bar_height)

        color = self._get_color_for_value(self._current_value)
        painter.setBrush(QBrush(QColor(color)))
        painter.drawRoundedRect(value_rect, 4, 4)

        # Value text
        painter.setPen(QColor(theme.TEXT_PRIMARY))
        value_text = f"{self._current_value:.0f}"
        text_rect = QRect(rect.x(), bar_rect.y() + bar_height + 5, rect.width(), 20)
        painter.drawText(text_rect, Qt.AlignCenter, value_text)

    def _paint_vertical_bar(self, painter: QPainter) -> None:
        """Paint vertical progress bar gauge."""
        rect = self.rect()
        bar_width = 20
        margin = 5

        bar_rect = QRect(
            rect.x() + (rect.width() - bar_width) // 2,
            rect.y() + margin,
            bar_width,
            rect.height() - 2 * margin,
        )

        # Background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(theme.NEUTRAL_200)))
        painter.drawRoundedRect(bar_rect, 4, 4)

        # Value bar (from bottom)
        ratio = (self._current_value - self._min_value) / (self._max_value - self._min_value)
        value_height = int(bar_rect.height() * ratio)
        value_rect = QRect(
            bar_rect.x(),
            bar_rect.y() + bar_rect.height() - value_height,
            bar_width,
            value_height,
        )

        color = self._get_color_for_value(self._current_value)
        painter.setBrush(QBrush(QColor(color)))
        painter.drawRoundedRect(value_rect, 4, 4)

    def sizeHint(self) -> QSize:
        """Provide size hint for layout."""
        if self._style == GaugeStyle.CIRCULAR:
            return QSize(120, 120)
        elif self._style == GaugeStyle.HORIZONTAL_BAR:
            return QSize(200, 60)
        else:  # VERTICAL_BAR
            return QSize(60, 120)


class Sparkline(QWidget):
    """
    Mini line chart for showing trends over time.

    Displays a simple line chart without axes or labels,
    useful for showing trends in compact spaces.
    """

    def __init__(
        self,
        data: Optional[List[float]] = None,
        width: int = 100,
        height: int = 30,
        parent: Optional[QWidget] = None,
    ):
        """
        Initialize sparkline chart.

        Args:
            data: List of data points to plot
            width: Widget width
            height: Widget height
            parent: Parent widget
        """
        super().__init__(parent)

        self._data = data or []
        self._line_color = theme.PRIMARY
        self._fill_color = theme.PRIMARY_LIGHT

        self.setFixedSize(width, height)

    def set_data(self, data: List[float]) -> None:
        """Update sparkline data."""
        self._data = data
        self.update()

    def set_colors(self, line_color: str, fill_color: Optional[str] = None) -> None:
        """Set line and fill colors."""
        self._line_color = line_color
        self._fill_color = fill_color or line_color
        self.update()

    def paintEvent(self, event) -> None:
        """Paint the sparkline."""
        if not self._data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        margin = 2

        # Calculate bounds
        min_val = min(self._data)
        max_val = max(self._data)
        value_range = max_val - min_val if max_val != min_val else 1

        # Calculate point positions
        points = []
        x_step = (rect.width() - 2 * margin) / max(len(self._data) - 1, 1)

        for i, value in enumerate(self._data):
            x = margin + i * x_step
            # Invert y because Qt coordinates are top-down
            y_ratio = (value - min_val) / value_range
            y = rect.height() - margin - y_ratio * (rect.height() - 2 * margin)
            points.append((x, y))

        if len(points) < 2:
            return

        # Draw filled area under line
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(self._fill_color + "40")))  # Add transparency

        # Create polygon for fill
        fill_points = [(margin, rect.height() - margin)] + points + [(rect.width() - margin, rect.height() - margin)]

        if QPolygonF and QPointF:
            polygon = QPolygonF([QPointF(x, y) for x, y in fill_points])
            painter.drawPolygon(polygon)

            # Draw line
            painter.setPen(QPen(QColor(self._line_color), 2, Qt.SolidLine))
            painter.setBrush(Qt.NoBrush)

            line_polygon = QPolygonF([QPointF(x, y) for x, y in points])
            painter.drawPolyline(line_polygon)
        else:
            # Fallback: draw simple line segments
            painter.setPen(QPen(QColor(self._line_color), 2, Qt.SolidLine))
            for i in range(len(points) - 1):
                painter.drawLine(int(points[i][0]), int(points[i][1]),
                                int(points[i+1][0]), int(points[i+1][1]))


class MetricCard(Card):
    """
    Card component for displaying a single metric with optional visualization.

    Combines a metric name, value, and optional chart (gauge or sparkline).
    """

    def __init__(
        self,
        title: str,
        value: str = "",
        subtitle: str = "",
        parent: Optional[QWidget] = None,
    ):
        """
        Initialize metric card.

        Args:
            title: Metric name/title
            value: Current value (can be formatted string)
            subtitle: Additional context text
            parent: Parent widget
        """
        super().__init__(parent)

        self._title_label = Heading(title, level=4)
        self._value_label = Heading(value, level=2)
        self._subtitle_label = Caption(subtitle)

        self.layout.addWidget(self._title_label)
        self.layout.addWidget(self._value_label)
        if subtitle:
            self.layout.addWidget(self._subtitle_label)

        self.layout.addStretch()

    def set_value(self, value: str) -> None:
        """Update the metric value."""
        self._value_label.setText(value)

    def set_subtitle(self, subtitle: str) -> None:
        """Update the subtitle."""
        self._subtitle_label.setText(subtitle)
        self._subtitle_label.setVisible(bool(subtitle))

    def add_chart(self, chart_widget: QWidget) -> None:
        """Add a chart widget (gauge, sparkline) to the card."""
        # Insert chart before the stretch
        self.layout.insertWidget(self.layout.count() - 1, chart_widget)


class AlertSummaryCard(Card):
    """
    Card for displaying alert summary with count badges.
    """

    def __init__(
        self,
        title: str = "Alerts",
        parent: Optional[QWidget] = None,
    ):
        """
        Initialize alert summary card.

        Args:
            title: Card title
            parent: Parent widget
        """
        super().__init__(parent)

        # Title
        title_label = Heading(title, level=4)
        self.layout.addWidget(title_label)

        # Alert counters
        self._counters_layout = QVBoxLayout()
        self._counters_layout.setSpacing(theme.SPACING_SM)

        self._critical_label = QLabel("Critical: 0")
        self._warning_label = QLabel("Warning: 0")
        self._info_label = QLabel("Info: 0")

        self._counters_layout.addWidget(self._critical_label)
        self._counters_layout.addWidget(self._warning_label)
        self._counters_layout.addWidget(self._info_label)

        self.layout.addLayout(self._counters_layout)
        self.layout.addStretch()

    def set_counts(self, critical: int = 0, warning: int = 0, info: int = 0) -> None:
        """Update alert counts."""
        self._critical_label.setText(f"Critical: {critical}")
        self._warning_label.setText(f"Warning: {warning}")
        self._info_label.setText(f"Info: {info}")

        # Apply colors
        self._critical_label.setStyleSheet(f"color: {theme.DANGER}; font-weight: bold;")
        self._warning_label.setStyleSheet(f"color: {theme.WARNING}; font-weight: bold;")
        self._info_label.setStyleSheet(f"color: {theme.INFO}; font-weight: normal;")
