"""
HQ Command GUI Icon System.

Provides icon loading and management utilities.
Uses Unicode emoji as fallback when icon libraries unavailable.
"""

from typing import Optional, Dict
from pathlib import Path

from .qt_compat import QIcon, QPixmap, QSize
from .styles import theme


# =============================================================================
# ICON SIZES
# =============================================================================

ICON_SIZE_SMALL = 16
ICON_SIZE_MEDIUM = 24
ICON_SIZE_LARGE = 32
ICON_SIZE_XLARGE = 48


# =============================================================================
# EMOJI ICON FALLBACKS
# =============================================================================

EMOJI_ICONS: Dict[str, str] = {
    # Navigation
    "live_ops": "📡",
    "task_board": "📋",
    "telemetry": "📊",
    "audit": "🔍",
    "admin": "⚙️",
    "settings": "⚙️",
    # Actions
    "add": "➕",
    "edit": "✏️",
    "delete": "🗑️",
    "save": "💾",
    "cancel": "✕",
    "close": "✕",
    "refresh": "🔄",
    "search": "🔍",
    "filter": "🔽",
    "sort": "⇅",
    "upload": "⬆️",
    "download": "⬇️",
    # Status
    "success": "✓",
    "error": "✕",
    "warning": "⚠",
    "info": "ℹ",
    # Connectivity
    "connected": "🟢",
    "disconnected": "🔴",
    "syncing": "🔄",
    "offline": "📵",
    # Tasks
    "task": "📋",
    "task_pending": "⏳",
    "task_active": "▶️",
    "task_complete": "✓",
    "escalate": "⬆️",
    # Responders
    "responder": "👤",
    "team": "👥",
    "available": "🟢",
    "busy": "🟡",
    "offline_status": "🔴",
    # Calls
    "call": "📞",
    "incoming_call": "📞",
    "call_complete": "✓",
    # System
    "help": "❓",
    "notification": "🔔",
    "menu": "☰",
    "expand": "▼",
    "collapse": "▲",
    "forward": "▶",
    "back": "◀",
    # Data
    "chart": "📊",
    "table": "📋",
    "calendar": "📅",
    "clock": "🕐",
    "location": "📍",
}


# =============================================================================
# ICON MANAGER
# =============================================================================

class IconManager:
    """
    Manages icon loading from various sources.

    Attempts to load from icon libraries, falls back to emoji.
    """

    def __init__(self, icon_dir: Optional[Path] = None):
        """
        Initialize icon manager.

        Args:
            icon_dir: Directory containing icon files (SVG/PNG)
        """
        self.icon_dir = icon_dir
        self._cache: Dict[str, QIcon] = {}

    def get_icon(
        self,
        name: str,
        size: int = ICON_SIZE_MEDIUM,
        color: Optional[str] = None,
    ) -> QIcon:
        """
        Get icon by name.

        Args:
            name: Icon name
            size: Icon size in pixels
            color: Icon color (for SVG colorization)

        Returns:
            QIcon instance
        """
        cache_key = f"{name}_{size}_{color}"

        # Check cache
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try to load from file
        icon = self._load_from_file(name, size, color)

        # Fall back to emoji
        if icon is None or icon.isNull():
            icon = self._create_emoji_icon(name, size)

        # Cache and return
        self._cache[cache_key] = icon
        return icon

    def _load_from_file(
        self,
        name: str,
        size: int,
        color: Optional[str] = None,
    ) -> Optional[QIcon]:
        """
        Load icon from file.

        Args:
            name: Icon name
            size: Icon size
            color: Icon color (for SVG)

        Returns:
            QIcon or None if not found
        """
        if self.icon_dir is None:
            return None

        # Try SVG first
        svg_path = self.icon_dir / f"{name}.svg"
        if svg_path.exists():
            # TODO: Implement SVG colorization if needed
            icon = QIcon(str(svg_path))
            return icon

        # Try PNG
        png_path = self.icon_dir / f"{name}.png"
        if png_path.exists():
            pixmap = QPixmap(str(png_path))
            pixmap = pixmap.scaled(
                size,
                size,
                aspectRatioMode=1,  # KeepAspectRatio
                transformMode=1,  # SmoothTransformation
            )
            icon = QIcon(pixmap)
            return icon

        return None

    def _create_emoji_icon(self, name: str, size: int) -> QIcon:
        """
        Create icon from emoji fallback.

        Args:
            name: Icon name
            size: Icon size

        Returns:
            QIcon with emoji
        """
        from .qt_compat import QPixmap, QPainter, QFont, QColor

        emoji = EMOJI_ICONS.get(name, "❓")

        # Create pixmap
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))  # Transparent

        # Draw emoji
        painter = QPainter(pixmap)
        font = QFont(theme.FONT_FAMILY, int(size * 0.7))
        painter.setFont(font)
        painter.drawText(pixmap.rect(), 0x84, emoji)  # AlignCenter
        painter.end()

        return QIcon(pixmap)

    def clear_cache(self):
        """Clear icon cache."""
        self._cache.clear()


# =============================================================================
# GLOBAL ICON MANAGER INSTANCE
# =============================================================================

_global_icon_manager: Optional[IconManager] = None


def get_icon_manager() -> IconManager:
    """
    Get global icon manager instance.

    Returns:
        Global IconManager
    """
    global _global_icon_manager
    if _global_icon_manager is None:
        # Try to find icons directory
        icon_dir = Path(__file__).parent / "icons"
        if not icon_dir.exists():
            icon_dir = None

        _global_icon_manager = IconManager(icon_dir)

    return _global_icon_manager


def get_icon(name: str, size: int = ICON_SIZE_MEDIUM) -> QIcon:
    """
    Convenience function to get icon.

    Args:
        name: Icon name
        size: Icon size

    Returns:
        QIcon instance
    """
    return get_icon_manager().get_icon(name, size)
