"""
HQ Command GUI Search and Filter System (Phase 3).

Provides components for:
- Global search functionality (3-15)
- Filter persistence and presets (3-16)
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any, Callable
import json
from pathlib import Path

from .qt_compat import (
    QWidget,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QComboBox,
    Qt,
    pyqtSignal,
)
from .styles import theme
from .components import Input, Button, ButtonVariant, Card, Heading


# =============================================================================
# GLOBAL SEARCH BAR (3-15)
# =============================================================================

class GlobalSearchBar(QWidget):
    """
    Global search bar component (3-15).

    Allows searching across tasks, responders, and calls.
    """

    search_requested = pyqtSignal(str, str)  # query, scope

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.search_history: List[str] = []

        self._build_ui()

    def _build_ui(self):
        """Build search bar UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Scope selector
        self.scope_select = QComboBox()
        self.scope_select.addItems([
            "All",
            "Tasks",
            "Responders",
            "Calls",
        ])
        layout.addWidget(self.scope_select)

        # Search input
        self.search_input = Input(placeholder="Search... (Ctrl+F)")
        self.search_input.returnPressed.connect(self._perform_search)
        layout.addWidget(self.search_input, 1)

        # Search button
        search_btn = Button("🔍", ButtonVariant.PRIMARY)
        search_btn.setMaximumWidth(50)
        search_btn.clicked.connect(self._perform_search)
        layout.addWidget(search_btn)

    def _perform_search(self):
        """Perform search."""
        query = self.search_input.text().strip()

        if not query:
            return

        # Add to history
        if query not in self.search_history:
            self.search_history.insert(0, query)
            # Keep only last 10
            self.search_history = self.search_history[:10]

        scope = self.scope_select.currentText().lower()
        self.search_requested.emit(query, scope)

    def set_focus(self):
        """Set focus to search input."""
        self.search_input.setFocus()
        self.search_input.selectAll()


class SearchResultsPanel(QFrame):
    """
    Search results panel (3-15).

    Displays search results with highlighting and navigation.
    """

    result_selected = pyqtSignal(str, dict)  # result_type, result_data

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setObjectName("Panel")
        self.results: List[Dict[str, Any]] = []

        self._build_ui()

    def _build_ui(self):
        """Build search results UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header_layout = QHBoxLayout()
        self.results_label = QLabel("Search Results")
        self.results_label.setStyleSheet("font-weight: bold; font-size: 14pt;")
        header_layout.addWidget(self.results_label)
        layout.addLayout(header_layout)

        # Results list
        self.results_list = QListWidget()
        self.results_list.itemClicked.connect(self._on_result_clicked)
        layout.addWidget(self.results_list)

        # Empty state
        self.empty_label = QLabel("No results found")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(f"color: {theme.NEUTRAL_500}; padding: 40px;")
        self.empty_label.setVisible(True)
        layout.addWidget(self.empty_label)

    def set_results(self, query: str, results: List[Dict[str, Any]]):
        """Set search results."""
        self.results = results
        self.results_list.clear()

        if not results:
            self.results_label.setText("Search Results (0)")
            self.empty_label.setVisible(True)
            self.results_list.setVisible(False)
            return

        self.results_label.setText(f"Search Results ({len(results)})")
        self.empty_label.setVisible(False)
        self.results_list.setVisible(True)

        for result in results:
            item_text = self._format_result(result, query)
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, result)
            self.results_list.addItem(item)

    def _format_result(self, result: Dict[str, Any], query: str) -> str:
        """Format result for display with highlighting."""
        result_type = result.get('type', 'unknown')
        result_id = result.get('id', 'unknown')

        if result_type == 'task':
            priority = result.get('priority', '')
            return f"[Task] {result_id} (P{priority}) - {result.get('location', '')}"
        elif result_type == 'responder':
            status = result.get('status', '')
            caps = ', '.join(result.get('capabilities', []))
            return f"[Responder] {result_id} ({status}) - {caps}"
        elif result_type == 'call':
            incident = result.get('incident_type', '')
            return f"[Call] {result_id} - {incident}"
        else:
            return f"[{result_type}] {result_id}"

    def _on_result_clicked(self, item: QListWidgetItem):
        """Handle result click."""
        result = item.data(Qt.UserRole)
        self.result_selected.emit(result.get('type', ''), result)


# =============================================================================
# FILTER PERSISTENCE (3-16)
# =============================================================================

class FilterPreset:
    """Filter preset data structure."""

    def __init__(
        self,
        name: str,
        filters: Dict[str, Any],
        description: str = "",
    ):
        self.name = name
        self.filters = filters
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'filters': self.filters,
            'description': self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FilterPreset':
        """Create from dictionary."""
        return cls(
            name=data['name'],
            filters=data['filters'],
            description=data.get('description', ''),
        )


class FilterManager:
    """
    Filter persistence manager (3-16).

    Manages saving, loading, and applying filter presets.
    """

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path.home() / ".hq_command" / "filter_presets.json"

        self.config_path = config_path
        self.presets: Dict[str, FilterPreset] = {}

        self._ensure_config_dir()
        self._load_presets()

    def _ensure_config_dir(self):
        """Ensure configuration directory exists."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_presets(self):
        """Load presets from disk."""
        if not self.config_path.exists():
            # Create with default presets
            self._create_default_presets()
            return

        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)

            self.presets = {
                name: FilterPreset.from_dict(preset_data)
                for name, preset_data in data.items()
            }
        except Exception:
            # If loading fails, use defaults
            self._create_default_presets()

    def _create_default_presets(self):
        """Create default filter presets."""
        self.presets = {
            'high_priority': FilterPreset(
                name='High Priority Tasks',
                filters={'priority_max': 2, 'status': 'queued'},
                description='Show only high priority (P1-P2) queued tasks',
            ),
            'escalated': FilterPreset(
                name='Escalated Tasks',
                filters={'status': 'escalated'},
                description='Show only escalated tasks',
            ),
            'available_units': FilterPreset(
                name='Available Units',
                filters={'status': 'available', 'capacity_min': 1},
                description='Show units currently available with capacity',
            ),
            'overloaded_units': FilterPreset(
                name='Overloaded Units',
                filters={'capacity': 0, 'status': 'available'},
                description='Show available units at full capacity',
            ),
        }

        self._save_presets()

    def _save_presets(self):
        """Save presets to disk."""
        try:
            data = {
                name: preset.to_dict()
                for name, preset in self.presets.items()
            }

            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass  # Fail silently

    def save_preset(self, preset: FilterPreset):
        """Save a filter preset."""
        self.presets[preset.name] = preset
        self._save_presets()

    def delete_preset(self, name: str):
        """Delete a filter preset."""
        if name in self.presets:
            del self.presets[name]
            self._save_presets()

    def get_preset(self, name: str) -> Optional[FilterPreset]:
        """Get a filter preset by name."""
        return self.presets.get(name)

    def list_presets(self) -> List[str]:
        """List all preset names."""
        return list(self.presets.keys())


class FilterPresetsPanel(QFrame):
    """
    Filter presets panel (3-16).

    UI for managing and applying filter presets.
    """

    preset_applied = pyqtSignal(dict)  # filters
    preset_saved = pyqtSignal(str)  # preset_name

    def __init__(
        self,
        filter_manager: FilterManager,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self.filter_manager = filter_manager
        self.setObjectName("Panel")

        self._build_ui()

    def _build_ui(self):
        """Build filter presets UI."""
        layout = QVBoxLayout(self)

        # Header
        layout.addWidget(Heading("Filter Presets", level=4))

        # Presets list
        self.presets_list = QListWidget()
        self.presets_list.itemDoubleClicked.connect(self._apply_preset)
        self._refresh_presets_list()
        layout.addWidget(self.presets_list)

        # Actions
        actions_layout = QHBoxLayout()

        apply_btn = Button("Apply", ButtonVariant.PRIMARY)
        apply_btn.clicked.connect(self._apply_selected_preset)
        actions_layout.addWidget(apply_btn)

        save_current_btn = Button("Save Current", ButtonVariant.SECONDARY)
        save_current_btn.clicked.connect(self._save_current_filters)
        actions_layout.addWidget(save_current_btn)

        delete_btn = Button("Delete", ButtonVariant.DANGER)
        delete_btn.clicked.connect(self._delete_selected_preset)
        actions_layout.addWidget(delete_btn)

        layout.addLayout(actions_layout)

        # Reset button
        reset_btn = Button("Reset All Filters", ButtonVariant.OUTLINE)
        reset_btn.clicked.connect(self._reset_filters)
        layout.addWidget(reset_btn)

    def _refresh_presets_list(self):
        """Refresh the presets list."""
        self.presets_list.clear()

        for name in self.filter_manager.list_presets():
            preset = self.filter_manager.get_preset(name)
            if preset:
                item_text = f"{preset.name}\n  {preset.description}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, name)
                self.presets_list.addItem(item)

    def _apply_preset(self, item: QListWidgetItem):
        """Apply selected preset."""
        preset_name = item.data(Qt.UserRole)
        preset = self.filter_manager.get_preset(preset_name)

        if preset:
            self.preset_applied.emit(preset.filters)

    def _apply_selected_preset(self):
        """Apply currently selected preset."""
        current_item = self.presets_list.currentItem()
        if current_item:
            self._apply_preset(current_item)

    def _save_current_filters(self):
        """Save current filters as preset."""
        # This would typically be implemented with a dialog
        # For now, emit signal for parent to handle
        self.preset_saved.emit("custom_preset")

    def _delete_selected_preset(self):
        """Delete selected preset."""
        current_item = self.presets_list.currentItem()
        if current_item:
            preset_name = current_item.data(Qt.UserRole)
            self.filter_manager.delete_preset(preset_name)
            self._refresh_presets_list()

    def _reset_filters(self):
        """Reset all filters."""
        self.preset_applied.emit({})


# =============================================================================
# CONTEXT DRAWER CONTENT (3-14)
# =============================================================================

class ContextDrawerManager:
    """
    Manager for context drawer content (3-14).

    Provides different content types for the context drawer.
    """

    def __init__(self, context_drawer):
        self.context_drawer = context_drawer

    def show_call_transcript(self, call_data: Dict[str, Any]):
        """Show call transcript in drawer."""
        self.context_drawer.clear_content()
        self.context_drawer.set_title(f"Call: {call_data.get('call_id', '')}")

        card = Card()
        card.add_widget(Heading("Call Details", level=4))

        # Caller info
        caller_name = call_data.get('caller_name', 'Unknown')
        callback = call_data.get('callback_number', 'N/A')
        card.add_widget(QLabel(f"Caller: {caller_name}"))
        card.add_widget(QLabel(f"Callback: {callback}"))

        # Location
        location = call_data.get('location', 'Unknown')
        card.add_widget(QLabel(f"Location: {location}"))

        # Incident details
        incident_type = call_data.get('incident_type', 'Unknown')
        severity = call_data.get('severity', 'Unknown')
        card.add_widget(QLabel(f"Type: {incident_type}"))
        card.add_widget(QLabel(f"Severity: {severity}"))

        # Description
        description = call_data.get('description', '')
        if description:
            card.add_widget(Heading("Description", level=5))
            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            card.add_widget(desc_label)

        # Timestamp
        timestamp = call_data.get('timestamp', '')
        card.add_widget(QLabel(f"Time: {timestamp}"))

        self.context_drawer.add_content(card)
        self.context_drawer.open_drawer()

    def show_responder_roster(self, responders: List[Dict[str, Any]]):
        """Show responder roster quick-view."""
        self.context_drawer.clear_content()
        self.context_drawer.set_title("Responder Roster")

        card = Card()
        card.add_widget(Heading(f"Active Responders ({len(responders)})", level=4))

        for responder in responders[:10]:  # Show first 10
            unit_id = responder.get('unit_id', '')
            status = responder.get('status', '')
            caps = ', '.join(responder.get('capabilities', [])[:3])  # First 3 caps

            responder_label = QLabel(f"• {unit_id} ({status}) - {caps}")
            card.add_widget(responder_label)

        if len(responders) > 10:
            more_label = QLabel(f"... and {len(responders) - 10} more")
            more_label.setStyleSheet(f"color: {theme.NEUTRAL_500};")
            card.add_widget(more_label)

        self.context_drawer.add_content(card)
        self.context_drawer.open_drawer()

    def show_analytics_summary(self, analytics: Dict[str, Any]):
        """Show analytics summary panel."""
        self.context_drawer.clear_content()
        self.context_drawer.set_title("Analytics Summary")

        card = Card()
        card.add_widget(Heading("System Metrics", level=4))

        # Display key metrics
        for key, value in analytics.items():
            metric_label = QLabel(f"{key}: {value}")
            card.add_widget(metric_label)

        self.context_drawer.add_content(card)
        self.context_drawer.open_drawer()
