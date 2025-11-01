"""PySide6 styling helpers aligned with :mod:`docs/fieldops_gui_style.md`."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import importlib.util
from typing import Mapping


@dataclass(frozen=True)
class ColorToken:
    """Semantic color tokens pulled from the FieldOps palette."""

    name: str
    hex: str
    usage: str


COLOR_TOKENS: Mapping[str, ColorToken] = {
    "primary": ColorToken("primary", "#0C3D5B", "Navigation rail, primary buttons, headers"),
    "primary_light": ColorToken("primary_light", "#145A80", "Hover/focus states"),
    "primary_contrast": ColorToken("primary_contrast", "#E8F4FF", "Text/icons over primary surfaces"),
    "secondary": ColorToken("secondary", "#1F6F43", "Mission status pills, confirmation cues"),
    "accent": ColorToken("accent", "#F6A000", "Sync prompts, warning banners"),
    "success": ColorToken("success", "#3FA776", "Sync-complete indicators"),
    "danger": ColorToken("danger", "#C4373B", "Failed sync, tamper alerts"),
    "neutral_900": ColorToken("neutral_900", "#121417", "Primary text on light surfaces"),
    "neutral_700": ColorToken("neutral_700", "#2D3035", "Secondary text and iconography"),
    "neutral_200": ColorToken("neutral_200", "#C9CFD6", "Borders, dividers, disabled controls"),
    "surface_light": ColorToken("surface_light", "#F5F7FA", "Mission brief panels, forms"),
    "surface_dark": ColorToken("surface_dark", "#1B1E22", "High-contrast telemetry cards"),
}


@dataclass(frozen=True)
class TypographyToken:
    """Font sizing and weight guidelines from the style spec."""

    role: str
    family: str
    size_pt: int
    weight: str
    letter_case: str | None = None
    letter_spacing_em: float = 0.0


TYPOGRAPHY: Mapping[str, TypographyToken] = {
    "section_header": TypographyToken("section_header", "Noto Sans", 20, "Bold"),
    "card_title": TypographyToken("card_title", "Noto Sans", 16, "DemiBold"),
    "body": TypographyToken("body", "Noto Sans", 14, "Regular"),
    "metadata": TypographyToken("metadata", "Noto Sans", 12, "Medium"),
    "navigation_label": TypographyToken(
        "navigation_label", "Noto Sans", 14, "Medium", letter_case="uppercase", letter_spacing_em=0.08
    ),
}

SPACING_GRID_PX = 8
MIN_CONTROL_HEIGHT_PX = 44
HORIZONTAL_PADDING_PX = 16


@dataclass(frozen=True)
class ComponentStyles:
    """Representative Qt style sheet snippets for major UI regions."""

    navigation_rail: str
    top_bar: str
    mission_tab_bar: str
    offline_queue_row: str
    telemetry_card: str
    conflict_dialog: str


@lru_cache(maxsize=1)
def component_styles() -> ComponentStyles:
    """Return Qt Style Sheet fragments that encode the FieldOps look."""

    primary = COLOR_TOKENS["primary"].hex
    primary_light = COLOR_TOKENS["primary_light"].hex
    primary_contrast = COLOR_TOKENS["primary_contrast"].hex
    accent = COLOR_TOKENS["accent"].hex
    neutral_200 = COLOR_TOKENS["neutral_200"].hex
    neutral_700 = COLOR_TOKENS["neutral_700"].hex
    neutral_900 = COLOR_TOKENS["neutral_900"].hex
    surface_light = COLOR_TOKENS["surface_light"].hex
    surface_dark = COLOR_TOKENS["surface_dark"].hex

    navigation_rail = f"""
    QWidget#NavigationRail {{
        background: {primary};
        min-width: 72px;
        max-width: 72px;
    }}
    QToolButton#NavigationRailButton {{
        color: {primary_contrast};
        text-transform: uppercase;
        letter-spacing: {TYPOGRAPHY['navigation_label'].letter_spacing_em}em;
        min-height: {MIN_CONTROL_HEIGHT_PX}px;
        padding: {SPACING_GRID_PX}px {HORIZONTAL_PADDING_PX}px;
        opacity: 0.6;
    }}
    QToolButton#NavigationRailButton:checked,
    QToolButton#NavigationRailButton:hover {{
        background: {primary_light};
        opacity: 1.0;
    }}
    """

    top_bar = f"""
    QWidget#TopBar {{
        background: {surface_light};
        color: {neutral_900};
        padding: {SPACING_GRID_PX * 2}px {HORIZONTAL_PADDING_PX}px;
    }}
    QLabel#SyncBadge {{
        background: {accent};
        color: {neutral_900};
        border-radius: {SPACING_GRID_PX}px;
        padding: {SPACING_GRID_PX // 2}px {SPACING_GRID_PX * 2}px;
    }}
    """

    mission_tab_bar = f"""
    QTabBar#MissionWorkspace::tab {{
        padding: {SPACING_GRID_PX * 2}px {HORIZONTAL_PADDING_PX}px;
        background: {surface_light};
        color: {neutral_700};
    }}
    QTabBar#MissionWorkspace::tab:selected {{
        color: {neutral_900};
        border-bottom: 3px solid {primary};
    }}
    """

    offline_queue_row = f"""
    QListView#OfflineQueue::item {{
        background: {surface_dark};
        color: {primary_contrast};
        min-height: {MIN_CONTROL_HEIGHT_PX}px;
        padding: {SPACING_GRID_PX}px {HORIZONTAL_PADDING_PX}px;
    }}
    QListView#OfflineQueue::item:selected {{
        border-left: 4px solid {primary};
    }}
    """

    telemetry_card = f"""
    QWidget#TelemetryCard {{
        background: {surface_dark};
        color: {primary_contrast};
        border-radius: {SPACING_GRID_PX}px;
        padding: {SPACING_GRID_PX * 2}px;
        border: 1px solid rgba(255, 255, 255, 0.08);
    }}
    QWidget#TelemetryCard[data-state="degraded"] {{
        background: {neutral_700};
    }}
    """

    conflict_dialog = f"""
    QDialog#ConflictResolution {{
        background: {surface_light};
        color: {neutral_900};
        padding: {SPACING_GRID_PX * 2}px {HORIZONTAL_PADDING_PX * 2}px;
    }}
    QPushButton#ConflictPrimary {{
        background: {primary};
        color: {primary_contrast};
        min-height: {MIN_CONTROL_HEIGHT_PX}px;
        padding: {SPACING_GRID_PX}px {HORIZONTAL_PADDING_PX * 2}px;
        border-radius: {SPACING_GRID_PX}px;
    }}
    QPushButton#ConflictSecondary {{
        background: transparent;
        color: {neutral_700};
        border: 1px solid {neutral_200};
        min-height: {MIN_CONTROL_HEIGHT_PX}px;
        padding: {SPACING_GRID_PX}px {HORIZONTAL_PADDING_PX * 2}px;
        border-radius: {SPACING_GRID_PX}px;
    }}
    """

    return ComponentStyles(
        navigation_rail=navigation_rail.strip(),
        top_bar=top_bar.strip(),
        mission_tab_bar=mission_tab_bar.strip(),
        offline_queue_row=offline_queue_row.strip(),
        telemetry_card=telemetry_card.strip(),
        conflict_dialog=conflict_dialog.strip(),
    )


def build_palette():
    """Construct a :class:`PySide6.QtGui.QPalette` when PySide6 is available."""

    if importlib.util.find_spec("PySide6") is None:
        raise RuntimeError("PySide6 is required to build the FieldOps palette")

    from PySide6.QtGui import QColor, QPalette  # type: ignore[import]

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLOR_TOKENS["surface_light"].hex))
    palette.setColor(QPalette.WindowText, QColor(COLOR_TOKENS["neutral_900"].hex))
    palette.setColor(QPalette.Base, QColor(COLOR_TOKENS["surface_light"].hex))
    palette.setColor(QPalette.AlternateBase, QColor(COLOR_TOKENS["surface_dark"].hex))
    palette.setColor(QPalette.ToolTipBase, QColor(COLOR_TOKENS["neutral_900"].hex))
    palette.setColor(QPalette.ToolTipText, QColor(COLOR_TOKENS["primary_contrast"].hex))
    palette.setColor(QPalette.Text, QColor(COLOR_TOKENS["neutral_900"].hex))
    palette.setColor(QPalette.Button, QColor(COLOR_TOKENS["primary"].hex))
    palette.setColor(QPalette.ButtonText, QColor(COLOR_TOKENS["primary_contrast"].hex))
    palette.setColor(QPalette.Highlight, QColor(COLOR_TOKENS["primary_light"].hex))
    palette.setColor(QPalette.HighlightedText, QColor(COLOR_TOKENS["primary_contrast"].hex))
    palette.setColor(QPalette.Link, QColor(COLOR_TOKENS["accent"].hex))
    palette.setColor(QPalette.BrightText, QColor(COLOR_TOKENS["primary_contrast"].hex))
    return palette


def focus_ring_stylesheet() -> str:
    """Expose the 3 px accessible focus outline defined in the style guide."""

    return (
        "* :focus {"
        " outline: 3px solid #7AC1FF;"
        " outline-offset: 2px;"
        " }"
    )
