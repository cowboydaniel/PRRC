"""
HQ Command GUI Window Management.

Provides window state persistence, positioning, and configuration.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any

from .qt_compat import QWidget, QMainWindow, QScreen, Qt


class WindowManager:
    """
    Manages window state persistence and multi-monitor handling.

    Saves and restores window geometry, position, and fullscreen state.
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize window manager.

        Args:
            config_dir: Directory for storing window state config
        """
        if config_dir is None:
            config_dir = Path.home() / ".config" / "hq_command"

        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.config_dir / "window_state.json"

    def save_window_state(self, window: QMainWindow, window_id: str = "main"):
        """
        Save window state to config file.

        Args:
            window: Main window to save state from
            window_id: Identifier for this window
        """
        state = {
            "geometry": {
                "x": window.x(),
                "y": window.y(),
                "width": window.width(),
                "height": window.height(),
            },
            "is_maximized": window.isMaximized(),
            "is_fullscreen": window.isFullScreen(),
        }

        # Load existing state
        all_state = self._load_state_file()
        all_state[window_id] = state

        # Save to file
        with open(self.state_file, "w") as f:
            json.dump(all_state, f, indent=2)

    def restore_window_state(
        self,
        window: QMainWindow,
        window_id: str = "main",
        default_width: int = 1280,
        default_height: int = 800,
    ):
        """
        Restore window state from config file.

        Args:
            window: Main window to restore state to
            window_id: Identifier for this window
            default_width: Default width if no saved state
            default_height: Default height if no saved state
        """
        all_state = self._load_state_file()
        state = all_state.get(window_id)

        if state:
            # Restore geometry
            geom = state.get("geometry", {})
            window.setGeometry(
                geom.get("x", 100),
                geom.get("y", 100),
                geom.get("width", default_width),
                geom.get("height", default_height),
            )

            # Restore maximized/fullscreen state
            if state.get("is_fullscreen", False):
                window.showFullScreen()
            elif state.get("is_maximized", False):
                window.showMaximized()
        else:
            # No saved state - use defaults and center on screen
            window.resize(default_width, default_height)
            self._center_window(window)

    def _load_state_file(self) -> Dict[str, Any]:
        """Load state from config file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _center_window(self, window: QMainWindow):
        """Center window on primary screen."""
        screen = window.screen()
        if screen:
            screen_geometry = screen.availableGeometry()
            window_geometry = window.frameGeometry()
            center_point = screen_geometry.center()
            window_geometry.moveCenter(center_point)
            window.move(window_geometry.topLeft())

    def toggle_fullscreen(self, window: QMainWindow):
        """Toggle fullscreen mode."""
        if window.isFullScreen():
            window.showNormal()
        else:
            window.showFullScreen()

    def get_optimal_size(
        self,
        screen: Optional[QScreen] = None,
        scale: float = 0.8,
    ) -> tuple:
        """
        Get optimal window size based on screen dimensions.

        Args:
            screen: Screen to size for (None = primary screen)
            scale: Fraction of screen to use (default 0.8 = 80%)

        Returns:
            Tuple of (width, height)
        """
        if screen is None:
            from .qt_compat import QApplication
            screen = QApplication.primaryScreen()

        if screen:
            geometry = screen.availableGeometry()
            return (
                int(geometry.width() * scale),
                int(geometry.height() * scale),
            )

        # Fallback
        return (1280, 800)

    def ensure_on_screen(self, window: QMainWindow):
        """
        Ensure window is visible on a connected screen.

        Moves window if it's positioned off-screen.
        """
        window_geometry = window.frameGeometry()
        screen = window.screen()

        if screen:
            screen_geometry = screen.availableGeometry()

            # Check if window is off-screen
            if not screen_geometry.intersects(window_geometry):
                # Move to center of screen
                self._center_window(window)
