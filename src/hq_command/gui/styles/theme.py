"""
HQ Command GUI Theme System.

Centralizes design tokens (colors, typography, spacing, animations)
and provides theme building utilities for the HQ Command GUI.

Based on FieldOps GUI Style Guide (docs/fieldops_gui_style.md) and
HQ Command GUI Design Blueprint (docs/hq_command_gui_design.md).
"""

from enum import Enum
from typing import Dict, Any
from ..qt_compat import QPalette, QColor, QFont


# =============================================================================
# COLOR TOKENS
# =============================================================================

# Primary Colors - Navigation, Headers, Primary Actions
PRIMARY = "#0C3D5B"  # Navy blue - navigation rail, primary buttons, headers
PRIMARY_LIGHT = "#145A80"  # Lighter navy - hover/focus states
PRIMARY_DARK = "#082A3F"  # Darker navy - pressed states
PRIMARY_CONTRAST = "#E8F4FF"  # Light blue - text/icons on primary surfaces

# Secondary Colors - Logistics, Confirmations
SECONDARY = "#1F6F43"  # Forest green - mission status, logistics indicators
SECONDARY_LIGHT = "#2A8F59"  # Lighter green - hover states
SECONDARY_CONTRAST = "#E8F7EF"  # Light green - text on secondary surfaces

# Accent Color - Warnings, Attention
ACCENT = "#F6A000"  # Amber - warnings, sync prompts, attention cues
ACCENT_LIGHT = "#FFB733"  # Lighter amber - hover states
ACCENT_CONTRAST = "#1F1600"  # Dark text on accent surfaces

# Status Colors
SUCCESS = "#3FA776"  # Green - success indicators, sync complete
DANGER = "#C4373B"  # Red - errors, escalations, failed sync
WARNING = "#F6A000"  # Same as accent - warnings
INFO = "#1976D2"  # Blue - informational messages

# Neutral Palette
NEUTRAL_900 = "#121417"  # Almost black - primary text on light surfaces
NEUTRAL_800 = "#1B1E22"  # Very dark gray - rich dark surfaces
NEUTRAL_700 = "#2D3035"  # Dark gray - secondary text, icons
NEUTRAL_600 = "#4A4D52"  # Medium-dark gray - tertiary text
NEUTRAL_500 = "#71757D"  # Medium gray - placeholder text, disabled text
NEUTRAL_400 = "#9197A0"  # Medium-light gray - borders on dark
NEUTRAL_300 = "#B4B9C2"  # Light gray - borders, dividers
NEUTRAL_200 = "#C9CFD6"  # Very light gray - disabled controls, subtle borders
NEUTRAL_100 = "#E4E7EB"  # Nearly white - hover states on light
NEUTRAL_50 = "#F5F7FA"  # Off-white - subtle backgrounds

# Surface Colors
SURFACE_LIGHT = "#F5F7FA"  # Light mode primary surface (same as NEUTRAL_50)
SURFACE_DARK = "#1B1E22"  # Dark mode primary surface (same as NEUTRAL_800)
SURFACE_ELEVATED_LIGHT = "#FFFFFF"  # Elevated surfaces in light mode
SURFACE_ELEVATED_DARK = "#2D3035"  # Elevated surfaces in dark mode

# Background Colors
BACKGROUND_LIGHT = "#FFFFFF"  # Light mode background
BACKGROUND_DARK = "#121417"  # Dark mode background

# Focus Ring
FOCUS_RING = "#7AC1FF"  # Accessible blue for keyboard focus outlines


# =============================================================================
# TYPOGRAPHY TOKENS
# =============================================================================

FONT_FAMILY = "Noto Sans"  # Primary font family (Qt will fallback if unavailable)
FONT_FAMILY_FALLBACK = "Arial, sans-serif"
FONT_FAMILY_MONO = "Noto Mono, Courier New, monospace"

# Font Sizes (in pt)
FONT_SIZE_H1 = 28  # Page titles
FONT_SIZE_H2 = 24  # Section headers
FONT_SIZE_H3 = 20  # Subsection headers
FONT_SIZE_H4 = 18  # Card titles
FONT_SIZE_H5 = 16  # Small headings
FONT_SIZE_H6 = 14  # Tiny headings
FONT_SIZE_BODY = 14  # Body text, buttons
FONT_SIZE_SMALL = 12  # Metadata, captions
FONT_SIZE_TINY = 10  # Very small labels

# Font Weights
FONT_WEIGHT_LIGHT = QFont.Light
FONT_WEIGHT_NORMAL = QFont.Normal
FONT_WEIGHT_MEDIUM = QFont.Medium
FONT_WEIGHT_DEMIBOLD = QFont.DemiBold
FONT_WEIGHT_BOLD = QFont.Bold
FONT_WEIGHT_BLACK = QFont.Black


# =============================================================================
# SPACING TOKENS (8px base grid)
# =============================================================================

SPACING_BASE = 8  # Base grid unit
SPACING_XS = 4  # 0.5 × base (very tight)
SPACING_SM = 8  # 1 × base (tight)
SPACING_MD = 16  # 2 × base (normal)
SPACING_LG = 24  # 3 × base (comfortable)
SPACING_XL = 32  # 4 × base (spacious)
SPACING_XXL = 48  # 6 × base (very spacious)

# Touch targets
MIN_TOUCH_TARGET = 44  # Minimum touch target size (glove-friendly)


# =============================================================================
# COMPONENT DIMENSIONS
# =============================================================================

NAV_RAIL_WIDTH = 72  # Navigation rail width
STATUS_BAR_HEIGHT = 56  # Global status bar height
CONTEXT_DRAWER_WIDTH = 360  # Right-side context drawer width
PANEL_RESIZE_HANDLE_WIDTH = 4  # Resize handle for split panes
SCROLLBAR_WIDTH = 12  # Custom scrollbar width

# Border Radius
BORDER_RADIUS_SM = 4  # Small corners (buttons, inputs)
BORDER_RADIUS_MD = 8  # Medium corners (cards)
BORDER_RADIUS_LG = 12  # Large corners (modals)
BORDER_RADIUS_ROUND = 9999  # Fully rounded (badges, pills)

# Shadows
SHADOW_SM = "0 1px 2px rgba(0, 0, 0, 0.05)"
SHADOW_MD = "0 2px 4px rgba(12, 61, 91, 0.12)"
SHADOW_LG = "0 4px 8px rgba(12, 61, 91, 0.16)"
SHADOW_XL = "0 8px 16px rgba(12, 61, 91, 0.20)"


# =============================================================================
# ANIMATION TOKENS
# =============================================================================

# Transition Durations (in ms)
TRANSITION_FAST = 150  # Quick interactions (hover, focus)
TRANSITION_NORMAL = 250  # Standard transitions (dropdowns, tooltips)
TRANSITION_SLOW = 400  # Larger animations (drawer, modal)
TRANSITION_VERY_SLOW = 600  # Complex animations

# Easing Functions (CSS cubic-bezier format)
EASING_STANDARD = "cubic-bezier(0.4, 0.0, 0.2, 1)"  # Standard material design
EASING_DECELERATE = "cubic-bezier(0.0, 0.0, 0.2, 1)"  # Enter screen
EASING_ACCELERATE = "cubic-bezier(0.4, 0.0, 1, 1)"  # Exit screen
EASING_SHARP = "cubic-bezier(0.4, 0.0, 0.6, 1)"  # Quick, sharp transitions


# =============================================================================
# THEME VARIANTS
# =============================================================================

class ThemeVariant(Enum):
    """Available theme variants."""
    LIGHT = "light"
    DARK = "dark"
    HIGH_CONTRAST = "high_contrast"


class Theme:
    """
    Theme configuration container.

    Holds all color, typography, and spacing tokens for a specific theme variant.
    """

    def __init__(self, variant: ThemeVariant = ThemeVariant.LIGHT):
        self.variant = variant
        self._colors = self._build_color_scheme(variant)

    def _build_color_scheme(self, variant: ThemeVariant) -> Dict[str, str]:
        """Build color scheme based on theme variant."""
        if variant == ThemeVariant.LIGHT:
            return {
                "background": BACKGROUND_LIGHT,
                "surface": SURFACE_LIGHT,
                "surface_elevated": SURFACE_ELEVATED_LIGHT,
                "text_primary": NEUTRAL_900,
                "text_secondary": NEUTRAL_700,
                "text_tertiary": NEUTRAL_500,
                "border": NEUTRAL_200,
                "border_strong": NEUTRAL_300,
                "divider": NEUTRAL_200,
            }
        elif variant == ThemeVariant.DARK:
            return {
                "background": BACKGROUND_DARK,
                "surface": SURFACE_DARK,
                "surface_elevated": SURFACE_ELEVATED_DARK,
                "text_primary": NEUTRAL_100,
                "text_secondary": NEUTRAL_300,
                "text_tertiary": NEUTRAL_400,
                "border": NEUTRAL_700,
                "border_strong": NEUTRAL_600,
                "divider": NEUTRAL_700,
            }
        else:  # HIGH_CONTRAST
            return {
                "background": "#000000",
                "surface": "#000000",
                "surface_elevated": "#1A1A1A",
                "text_primary": "#FFFFFF",
                "text_secondary": "#FFFFFF",
                "text_tertiary": "#CCCCCC",
                "border": "#FFFFFF",
                "border_strong": "#FFFFFF",
                "divider": "#FFFFFF",
            }

    def get_color(self, name: str) -> str:
        """Get a theme-specific color by name."""
        return self._colors.get(name, "#FF00FF")  # Magenta fallback for missing colors

    def to_dict(self) -> Dict[str, Any]:
        """Export theme as dictionary."""
        return {
            "variant": self.variant.value,
            "colors": self._colors,
            "typography": {
                "font_family": FONT_FAMILY,
                "font_sizes": {
                    "h1": FONT_SIZE_H1,
                    "h2": FONT_SIZE_H2,
                    "h3": FONT_SIZE_H3,
                    "h4": FONT_SIZE_H4,
                    "h5": FONT_SIZE_H5,
                    "h6": FONT_SIZE_H6,
                    "body": FONT_SIZE_BODY,
                    "small": FONT_SIZE_SMALL,
                    "tiny": FONT_SIZE_TINY,
                },
            },
            "spacing": {
                "base": SPACING_BASE,
                "xs": SPACING_XS,
                "sm": SPACING_SM,
                "md": SPACING_MD,
                "lg": SPACING_LG,
                "xl": SPACING_XL,
            },
        }


# =============================================================================
# THEME BUILDER FUNCTIONS
# =============================================================================

def build_palette(variant: ThemeVariant = ThemeVariant.LIGHT) -> QPalette:
    """
    Build a QPalette for the specified theme variant.

    Args:
        variant: Theme variant to use

    Returns:
        QPalette configured with theme colors
    """
    palette = QPalette()
    theme = Theme(variant)

    if variant == ThemeVariant.LIGHT:
        # Light mode palette
        palette.setColor(QPalette.Window, QColor(SURFACE_LIGHT))
        palette.setColor(QPalette.WindowText, QColor(NEUTRAL_900))
        palette.setColor(QPalette.Base, QColor(BACKGROUND_LIGHT))
        palette.setColor(QPalette.AlternateBase, QColor(SURFACE_LIGHT))
        palette.setColor(QPalette.Text, QColor(NEUTRAL_900))
        palette.setColor(QPalette.Button, QColor(SURFACE_ELEVATED_LIGHT))
        palette.setColor(QPalette.ButtonText, QColor(NEUTRAL_900))
        palette.setColor(QPalette.BrightText, QColor(PRIMARY_CONTRAST))
        palette.setColor(QPalette.Link, QColor(PRIMARY))
        palette.setColor(QPalette.Highlight, QColor(PRIMARY))
        palette.setColor(QPalette.HighlightedText, QColor(PRIMARY_CONTRAST))

        # Disabled state
        palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(NEUTRAL_500))
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor(NEUTRAL_500))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(NEUTRAL_500))

    elif variant == ThemeVariant.DARK:
        # Dark mode palette
        palette.setColor(QPalette.Window, QColor(SURFACE_DARK))
        palette.setColor(QPalette.WindowText, QColor(NEUTRAL_100))
        palette.setColor(QPalette.Base, QColor(BACKGROUND_DARK))
        palette.setColor(QPalette.AlternateBase, QColor(SURFACE_DARK))
        palette.setColor(QPalette.Text, QColor(NEUTRAL_100))
        palette.setColor(QPalette.Button, QColor(SURFACE_ELEVATED_DARK))
        palette.setColor(QPalette.ButtonText, QColor(NEUTRAL_100))
        palette.setColor(QPalette.BrightText, QColor(PRIMARY_CONTRAST))
        palette.setColor(QPalette.Link, QColor(PRIMARY_LIGHT))
        palette.setColor(QPalette.Highlight, QColor(PRIMARY_LIGHT))
        palette.setColor(QPalette.HighlightedText, QColor(PRIMARY_CONTRAST))

        # Disabled state
        palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(NEUTRAL_400))
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor(NEUTRAL_400))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(NEUTRAL_400))

    else:  # HIGH_CONTRAST
        # High contrast palette
        palette.setColor(QPalette.Window, QColor("#000000"))
        palette.setColor(QPalette.WindowText, QColor("#FFFFFF"))
        palette.setColor(QPalette.Base, QColor("#000000"))
        palette.setColor(QPalette.AlternateBase, QColor("#1A1A1A"))
        palette.setColor(QPalette.Text, QColor("#FFFFFF"))
        palette.setColor(QPalette.Button, QColor("#1A1A1A"))
        palette.setColor(QPalette.ButtonText, QColor("#FFFFFF"))
        palette.setColor(QPalette.BrightText, QColor("#FFFFFF"))
        palette.setColor(QPalette.Link, QColor("#00BFFF"))
        palette.setColor(QPalette.Highlight, QColor("#FFFF00"))
        palette.setColor(QPalette.HighlightedText, QColor("#000000"))

    return palette


def focus_ring_stylesheet() -> str:
    """
    Generate stylesheet for accessible focus rings.

    Returns:
        QSS stylesheet string
    """
    return f"""
    *:focus {{
        outline: 3px solid {FOCUS_RING};
        outline-offset: 2px;
    }}
    """


def component_styles(variant: ThemeVariant = ThemeVariant.LIGHT) -> str:
    """
    Generate comprehensive component stylesheets.

    Args:
        variant: Theme variant to use

    Returns:
        Complete QSS stylesheet string for all components
    """
    theme = Theme(variant)
    bg = theme.get_color("background")
    surface = theme.get_color("surface")
    surface_elevated = theme.get_color("surface_elevated")
    text_primary = theme.get_color("text_primary")
    text_secondary = theme.get_color("text_secondary")
    border = theme.get_color("border")

    return f"""
    /* =================================================================
       GLOBAL STYLES
       ================================================================= */

    QWidget {{
        font-family: "{FONT_FAMILY}", Arial, sans-serif;
        font-size: {FONT_SIZE_BODY}pt;
        color: {text_primary};
        background-color: {bg};
    }}

    /* =================================================================
       NAVIGATION RAIL
       ================================================================= */

    QWidget#NavigationRail {{
        background-color: {PRIMARY};
        min-width: {NAV_RAIL_WIDTH}px;
        max-width: {NAV_RAIL_WIDTH}px;
    }}

    QToolButton#NavButton {{
        background-color: transparent;
        color: {PRIMARY_CONTRAST};
        border: none;
        border-radius: {BORDER_RADIUS_MD}px;
        padding: {SPACING_MD}px;
        min-width: {MIN_TOUCH_TARGET}px;
        min-height: {MIN_TOUCH_TARGET}px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-size: {FONT_SIZE_SMALL}pt;
        font-weight: 500;
    }}

    QToolButton#NavButton:hover {{
        background-color: {PRIMARY_LIGHT};
    }}

    QToolButton#NavButton:pressed {{
        background-color: {PRIMARY_DARK};
    }}

    QToolButton#NavButton:checked {{
        background-color: {PRIMARY_LIGHT};
        border-left: 4px solid {ACCENT};
    }}

    /* =================================================================
       STATUS BAR
       ================================================================= */

    QWidget#StatusBar {{
        background-color: {surface};
        min-height: {STATUS_BAR_HEIGHT}px;
        max-height: {STATUS_BAR_HEIGHT}px;
        border-bottom: 1px solid {border};
    }}

    QLabel#StatusLabel {{
        color: {text_primary};
        font-size: {FONT_SIZE_BODY}pt;
        padding: 0 {SPACING_MD}px;
    }}

    QLabel#StatusBadge {{
        background-color: {SUCCESS};
        color: white;
        border-radius: {BORDER_RADIUS_ROUND}px;
        padding: {SPACING_XS}px {SPACING_SM}px;
        font-size: {FONT_SIZE_SMALL}pt;
        font-weight: 600;
    }}

    QLabel#StatusBadge[status="warning"] {{
        background-color: {WARNING};
        color: {ACCENT_CONTRAST};
    }}

    QLabel#StatusBadge[status="danger"] {{
        background-color: {DANGER};
        color: white;
    }}

    /* =================================================================
       BUTTONS
       ================================================================= */

    QPushButton {{
        background-color: {PRIMARY};
        color: {PRIMARY_CONTRAST};
        border: none;
        border-radius: {BORDER_RADIUS_SM}px;
        padding: {SPACING_SM}px {SPACING_MD}px;
        min-height: {MIN_TOUCH_TARGET}px;
        font-size: {FONT_SIZE_BODY}pt;
        font-weight: 500;
    }}

    QPushButton:hover {{
        background-color: {PRIMARY_LIGHT};
    }}

    QPushButton:pressed {{
        background-color: {PRIMARY_DARK};
    }}

    QPushButton:disabled {{
        background-color: {border};
        color: {text_secondary};
    }}

    QPushButton#SecondaryButton {{
        background-color: {SECONDARY};
        color: {SECONDARY_CONTRAST};
    }}

    QPushButton#SecondaryButton:hover {{
        background-color: {SECONDARY_LIGHT};
    }}

    QPushButton#DangerButton {{
        background-color: {DANGER};
        color: white;
    }}

    QPushButton#DangerButton:hover {{
        background-color: #A62E32;
    }}

    QPushButton#OutlineButton {{
        background-color: transparent;
        color: {PRIMARY};
        border: 2px solid {PRIMARY};
    }}

    QPushButton#OutlineButton:hover {{
        background-color: {PRIMARY};
        color: {PRIMARY_CONTRAST};
    }}

    /* =================================================================
       INPUT FIELDS
       ================================================================= */

    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {surface_elevated};
        color: {text_primary};
        border: 1px solid {border};
        border-radius: {BORDER_RADIUS_SM}px;
        padding: {SPACING_SM}px {SPACING_MD}px;
        min-height: {MIN_TOUCH_TARGET}px;
        font-size: {FONT_SIZE_BODY}pt;
    }}

    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {PRIMARY};
        border-width: 2px;
    }}

    QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
        background-color: {surface};
        color: {text_secondary};
        border-color: {border};
    }}

    /* =================================================================
       DROPDOWNS / COMBOBOX
       ================================================================= */

    QComboBox {{
        background-color: {surface_elevated};
        color: {text_primary};
        border: 1px solid {border};
        border-radius: {BORDER_RADIUS_SM}px;
        padding: {SPACING_SM}px {SPACING_MD}px;
        min-height: {MIN_TOUCH_TARGET}px;
        font-size: {FONT_SIZE_BODY}pt;
    }}

    QComboBox:hover {{
        border-color: {PRIMARY};
    }}

    QComboBox:focus {{
        border-color: {PRIMARY};
        border-width: 2px;
    }}

    QComboBox::drop-down {{
        border: none;
        width: {SPACING_LG}px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {surface_elevated};
        color: {text_primary};
        border: 1px solid {border};
        selection-background-color: {PRIMARY};
        selection-color: {PRIMARY_CONTRAST};
    }}

    /* =================================================================
       CHECKBOXES AND RADIO BUTTONS
       ================================================================= */

    QCheckBox, QRadioButton {{
        color: {text_primary};
        spacing: {SPACING_SM}px;
        font-size: {FONT_SIZE_BODY}pt;
    }}

    QCheckBox::indicator, QRadioButton::indicator {{
        width: {SPACING_LG}px;
        height: {SPACING_LG}px;
        border: 2px solid {border};
        background-color: {surface_elevated};
    }}

    QCheckBox::indicator {{
        border-radius: {BORDER_RADIUS_SM}px;
    }}

    QRadioButton::indicator {{
        border-radius: {SPACING_MD}px;
    }}

    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background-color: {PRIMARY};
        border-color: {PRIMARY};
    }}

    QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
        border-color: {PRIMARY};
    }}

    /* =================================================================
       LABELS
       ================================================================= */

    QLabel {{
        color: {text_primary};
        font-size: {FONT_SIZE_BODY}pt;
    }}

    QLabel#H1 {{
        font-size: {FONT_SIZE_H1}pt;
        font-weight: bold;
        color: {text_primary};
    }}

    QLabel#H2 {{
        font-size: {FONT_SIZE_H2}pt;
        font-weight: bold;
        color: {text_primary};
    }}

    QLabel#H3 {{
        font-size: {FONT_SIZE_H3}pt;
        font-weight: 600;
        color: {text_primary};
    }}

    QLabel#H4 {{
        font-size: {FONT_SIZE_H4}pt;
        font-weight: 600;
        color: {text_primary};
    }}

    QLabel#Caption {{
        font-size: {FONT_SIZE_SMALL}pt;
        color: {text_secondary};
    }}

    /* =================================================================
       BADGES / CHIPS
       ================================================================= */

    QLabel#Badge {{
        background-color: {NEUTRAL_200};
        color: {NEUTRAL_900};
        border-radius: {BORDER_RADIUS_ROUND}px;
        padding: {SPACING_XS}px {SPACING_SM}px;
        font-size: {FONT_SIZE_SMALL}pt;
        font-weight: 600;
    }}

    QLabel#Badge[type="success"] {{
        background-color: {SUCCESS};
        color: white;
    }}

    QLabel#Badge[type="warning"] {{
        background-color: {WARNING};
        color: {ACCENT_CONTRAST};
    }}

    QLabel#Badge[type="danger"] {{
        background-color: {DANGER};
        color: white;
    }}

    QLabel#Badge[type="info"] {{
        background-color: {INFO};
        color: white;
    }}

    /* =================================================================
       CARDS / PANELS
       ================================================================= */

    QFrame#Card {{
        background-color: {surface_elevated};
        border: 1px solid {border};
        border-radius: {BORDER_RADIUS_MD}px;
        padding: {SPACING_MD}px;
    }}

    QFrame#Panel {{
        background-color: {surface};
        border: 1px solid {border};
        border-radius: {BORDER_RADIUS_SM}px;
    }}

    /* =================================================================
       CONTEXT DRAWER
       ================================================================= */

    QWidget#ContextDrawer {{
        background-color: {surface_elevated};
        border-left: 1px solid {border};
        min-width: {CONTEXT_DRAWER_WIDTH}px;
        max-width: {CONTEXT_DRAWER_WIDTH}px;
    }}

    /* =================================================================
       SCROLLBARS
       ================================================================= */

    QScrollBar:vertical {{
        background: {surface};
        width: {SCROLLBAR_WIDTH}px;
        border-radius: {BORDER_RADIUS_SM}px;
    }}

    QScrollBar::handle:vertical {{
        background: {border};
        min-height: {SPACING_LG}px;
        border-radius: {BORDER_RADIUS_SM}px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {text_secondary};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QScrollBar:horizontal {{
        background: {surface};
        height: {SCROLLBAR_WIDTH}px;
        border-radius: {BORDER_RADIUS_SM}px;
    }}

    QScrollBar::handle:horizontal {{
        background: {border};
        min-width: {SPACING_LG}px;
        border-radius: {BORDER_RADIUS_SM}px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background: {text_secondary};
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    /* =================================================================
       TABLE / LIST VIEWS
       ================================================================= */

    QTableView, QListView, QTreeView {{
        background-color: {surface_elevated};
        color: {text_primary};
        border: 1px solid {border};
        gridline-color: {border};
        selection-background-color: {PRIMARY};
        selection-color: {PRIMARY_CONTRAST};
        alternate-background-color: {surface};
    }}

    QHeaderView::section {{
        background-color: {surface};
        color: {text_primary};
        border: none;
        border-bottom: 2px solid {border};
        padding: {SPACING_SM}px {SPACING_MD}px;
        font-weight: 600;
    }}

    /* =================================================================
       TABS
       ================================================================= */

    QTabWidget::pane {{
        border: 1px solid {border};
        border-radius: {BORDER_RADIUS_SM}px;
        background-color: {surface_elevated};
    }}

    QTabBar::tab {{
        background-color: {surface};
        color: {text_secondary};
        border: none;
        padding: {SPACING_SM}px {SPACING_MD}px;
        min-width: {MIN_TOUCH_TARGET}px;
        min-height: {MIN_TOUCH_TARGET}px;
        font-size: {FONT_SIZE_BODY}pt;
    }}

    QTabBar::tab:hover {{
        background-color: {PRIMARY_LIGHT};
        color: {PRIMARY_CONTRAST};
    }}

    QTabBar::tab:selected {{
        background-color: transparent;
        color: {PRIMARY};
        border-bottom: 3px solid {PRIMARY};
    }}

    /* =================================================================
       DIALOG / MODAL
       ================================================================= */

    QDialog {{
        background-color: {surface_elevated};
        border-radius: {BORDER_RADIUS_LG}px;
    }}

    /* =================================================================
       TOOLTIPS
       ================================================================= */

    QToolTip {{
        background-color: {NEUTRAL_800};
        color: {NEUTRAL_100};
        border: 1px solid {NEUTRAL_700};
        border-radius: {BORDER_RADIUS_SM}px;
        padding: {SPACING_XS}px {SPACING_SM}px;
        font-size: {FONT_SIZE_SMALL}pt;
    }}

    /* =================================================================
       PROGRESS BAR
       ================================================================= */

    QProgressBar {{
        background-color: {surface};
        border: 1px solid {border};
        border-radius: {BORDER_RADIUS_SM}px;
        height: {SPACING_SM}px;
        text-align: center;
    }}

    QProgressBar::chunk {{
        background-color: {PRIMARY};
        border-radius: {BORDER_RADIUS_SM}px;
    }}

    /* =================================================================
       SPLITTERS
       ================================================================= */

    QSplitter::handle {{
        background-color: {border};
    }}

    QSplitter::handle:horizontal {{
        width: {PANEL_RESIZE_HANDLE_WIDTH}px;
    }}

    QSplitter::handle:vertical {{
        height: {PANEL_RESIZE_HANDLE_WIDTH}px;
    }}

    QSplitter::handle:hover {{
        background-color: {PRIMARY};
    }}
    """
