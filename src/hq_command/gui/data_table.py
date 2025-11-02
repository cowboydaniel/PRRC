"""
Data Table Framework for HQ Command GUI.

Provides reusable table components with sorting, filtering, pagination,
and custom cell rendering capabilities.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, List, Dict
from enum import Enum

from .qt_compat import (
    QWidget,
    QTableView,
    QHeaderView,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFrame,
    QAbstractItemModel,
    QModelIndex,
    QStyledItemDelegate,
    QPainter,
    QStyleOptionViewItem,
    QSize,
    Qt,
    QtCore,
    pyqtSignal,
)
from .components import Input, Button, ButtonVariant, Badge, BadgeType
from .styles import theme


class SortOrder(Enum):
    """Sort order for table columns."""
    ASCENDING = Qt.AscendingOrder
    DESCENDING = Qt.DescendingOrder
    NONE = -1


class DataTableModel(QAbstractItemModel):
    """
    Table model for displaying structured data with column headers.

    Supports sorting, filtering, and custom data formatting.
    """

    def __init__(self, columns: List[str], parent: Optional[QWidget] = None):
        """
        Initialize the data table model.

        Args:
            columns: List of column header names
            parent: Parent widget
        """
        super().__init__(parent)
        self._columns = columns
        self._data: List[Dict[str, Any]] = []
        self._filtered_data: List[Dict[str, Any]] = []
        self._sort_column = -1
        self._sort_order = SortOrder.NONE
        self._filter_func: Optional[Callable[[Dict[str, Any]], bool]] = None

    def set_data(self, data: List[Dict[str, Any]]) -> None:
        """Set the table data and apply current filters."""
        self.beginResetModel()
        self._data = data
        self._apply_filter()
        self.endResetModel()

    def _apply_filter(self) -> None:
        """Apply current filter function to data."""
        if self._filter_func:
            self._filtered_data = [row for row in self._data if self._filter_func(row)]
        else:
            self._filtered_data = self._data.copy()

        # Re-apply sorting after filtering
        if self._sort_column >= 0:
            self._sort_data()

    def _sort_data(self) -> None:
        """Sort filtered data by current sort column and order."""
        if self._sort_column < 0 or self._sort_column >= len(self._columns):
            return

        col_key = self._columns[self._sort_column]
        reverse = self._sort_order == SortOrder.DESCENDING

        try:
            self._filtered_data.sort(
                key=lambda row: row.get(col_key, ""),
                reverse=reverse
            )
        except TypeError:
            # Mixed types - convert to strings for comparison
            self._filtered_data.sort(
                key=lambda row: str(row.get(col_key, "")),
                reverse=reverse
            )

    def set_filter(self, filter_func: Optional[Callable[[Dict[str, Any]], bool]]) -> None:
        """Set a filter function to limit displayed rows."""
        self.beginResetModel()
        self._filter_func = filter_func
        self._apply_filter()
        self.endResetModel()

    def sort(self, column: int, order: SortOrder) -> None:
        """Sort data by specified column."""
        self.beginResetModel()
        self._sort_column = column
        self._sort_order = order
        self._sort_data()
        self.endResetModel()

    # Qt Model Interface
    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        """Create model index for given row/column."""
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        return self.createIndex(row, column)

    def parent(self, index: QModelIndex) -> QModelIndex:
        """Return parent index (always invalid for flat table)."""
        return QModelIndex()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return number of rows."""
        if parent.isValid():
            return 0
        return len(self._filtered_data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return number of columns."""
        if parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """Return data for given index and role."""
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        if not (0 <= row < len(self._filtered_data)):
            return None
        if not (0 <= col < len(self._columns)):
            return None

        row_data = self._filtered_data[row]
        col_key = self._columns[col]

        if role == Qt.DisplayRole or role == Qt.EditRole:
            return row_data.get(col_key, "")
        elif role == Qt.UserRole:
            # Return full row data for custom delegates
            return row_data

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        """Return header data for columns."""
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            if 0 <= section < len(self._columns):
                return self._columns[section]

        return None

    def get_row_data(self, row: int) -> Optional[Dict[str, Any]]:
        """Get full row data dictionary."""
        if 0 <= row < len(self._filtered_data):
            return self._filtered_data[row]
        return None

    @property
    def columns(self) -> List[str]:
        """Get column names."""
        return self._columns.copy()


class DataTableDelegate(QStyledItemDelegate):
    """
    Custom delegate for rendering table cells with rich content.

    Can be subclassed to provide custom rendering logic.
    """

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        """Paint cell content."""
        # Default implementation - subclasses can override
        super().paint(painter, option, index)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        """Return size hint for cell."""
        return super().sizeHint(option, index)


class DataTable(QWidget):
    """
    Reusable data table component with filtering, sorting, and pagination.

    Features:
    - Column sorting (click headers)
    - Column resizing and reordering
    - Search/filter box
    - Row selection
    - Custom cell delegates
    - Pagination controls (optional)
    """

    # Signals
    row_clicked = pyqtSignal(int)  # Emits row index
    row_double_clicked = pyqtSignal(int)
    selection_changed = pyqtSignal(list)  # Emits list of selected row indices

    def __init__(
        self,
        columns: List[str],
        show_search: bool = True,
        show_pagination: bool = False,
        parent: Optional[QWidget] = None,
    ):
        """
        Initialize data table.

        Args:
            columns: List of column header names
            show_search: Whether to show search box
            show_pagination: Whether to show pagination controls
            parent: Parent widget
        """
        super().__init__(parent)

        self._columns = columns
        self._show_pagination = show_pagination
        self._page_size = 50
        self._current_page = 0

        # Create model and view
        self._model = DataTableModel(columns)
        self._setup_ui(show_search, show_pagination)

    def _setup_ui(self, show_search: bool, show_pagination: bool) -> None:
        """Set up the table UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.SPACING_SM)

        # Search box
        if show_search:
            search_layout = QHBoxLayout()
            search_label = QLabel("Search:")
            self._search_input = Input(placeholder="Filter table...")
            self._search_input.textChanged.connect(self._on_search_changed)
            search_layout.addWidget(search_label)
            search_layout.addWidget(self._search_input, 1)
            layout.addLayout(search_layout)
        else:
            self._search_input = None

        # Table view
        self._table_view = QTableView()
        self._table_view.setModel(self._model)
        self._table_view.setSortingEnabled(True)
        self._table_view.setSelectionBehavior(QTableView.SelectRows)
        self._table_view.setAlternatingRowColors(True)

        # Configure headers
        h_header = self._table_view.horizontalHeader()
        h_header.setStretchLastSection(True)
        h_header.setSectionsMovable(True)
        h_header.setSectionsClickable(True)
        h_header.sectionClicked.connect(self._on_header_clicked)

        # Allow column resizing
        for i in range(len(self._columns)):
            h_header.setSectionResizeMode(i, QHeaderView.Interactive)

        # Connect signals
        self._table_view.clicked.connect(self._on_row_clicked)
        self._table_view.doubleClicked.connect(self._on_row_double_clicked)

        layout.addWidget(self._table_view, 1)

        # Pagination controls
        if show_pagination:
            pagination_layout = QHBoxLayout()
            self._prev_button = Button("Previous", ButtonVariant.OUTLINE)
            self._next_button = Button("Next", ButtonVariant.OUTLINE)
            self._page_label = QLabel("Page 1")

            self._prev_button.clicked.connect(self._on_prev_page)
            self._next_button.clicked.connect(self._on_next_page)

            pagination_layout.addWidget(self._prev_button)
            pagination_layout.addWidget(self._page_label)
            pagination_layout.addWidget(self._next_button)
            pagination_layout.addStretch()

            layout.addLayout(pagination_layout)
        else:
            self._prev_button = None
            self._next_button = None
            self._page_label = None

    def set_data(self, data: List[Dict[str, Any]]) -> None:
        """Set table data."""
        self._model.set_data(data)
        self._update_pagination()

    def set_delegate(self, column: int, delegate: QStyledItemDelegate) -> None:
        """Set custom delegate for a column."""
        self._table_view.setItemDelegateForColumn(column, delegate)

    def set_column_width(self, column: int, width: int) -> None:
        """Set width for a specific column."""
        self._table_view.setColumnWidth(column, width)

    def set_filter(self, filter_func: Optional[Callable[[Dict[str, Any]], bool]]) -> None:
        """Set a custom filter function."""
        self._model.set_filter(filter_func)
        self._update_pagination()

    def get_selected_rows(self) -> List[int]:
        """Get indices of selected rows."""
        selection = self._table_view.selectionModel()
        if not selection:
            return []

        indices = selection.selectedRows()
        return [index.row() for index in indices]

    def get_row_data(self, row: int) -> Optional[Dict[str, Any]]:
        """Get data for a specific row."""
        return self._model.get_row_data(row)

    def _on_search_changed(self, text: str) -> None:
        """Handle search text changes."""
        text = text.lower().strip()

        if not text:
            self._model.set_filter(None)
        else:
            # Search across all columns
            def search_filter(row_data: Dict[str, Any]) -> bool:
                for value in row_data.values():
                    if text in str(value).lower():
                        return True
                return False

            self._model.set_filter(search_filter)

        self._update_pagination()

    def _on_header_clicked(self, logical_index: int) -> None:
        """Handle header click for sorting."""
        # Qt's built-in sorting handles this, but we track it
        order = self._table_view.horizontalHeader().sortIndicatorOrder()
        sort_order = SortOrder.ASCENDING if order == Qt.AscendingOrder else SortOrder.DESCENDING
        self._model.sort(logical_index, sort_order)

    def _on_row_clicked(self, index: QModelIndex) -> None:
        """Handle row click."""
        self.row_clicked.emit(index.row())

    def _on_row_double_clicked(self, index: QModelIndex) -> None:
        """Handle row double-click."""
        self.row_double_clicked.emit(index.row())

    def _on_prev_page(self) -> None:
        """Go to previous page."""
        if self._current_page > 0:
            self._current_page -= 1
            self._update_pagination()

    def _on_next_page(self) -> None:
        """Go to next page."""
        total_pages = self._get_total_pages()
        if self._current_page < total_pages - 1:
            self._current_page += 1
            self._update_pagination()

    def _get_total_pages(self) -> int:
        """Calculate total number of pages."""
        total_rows = self._model.rowCount()
        return max(1, (total_rows + self._page_size - 1) // self._page_size)

    def _update_pagination(self) -> None:
        """Update pagination controls."""
        if not self._show_pagination:
            return

        total_pages = self._get_total_pages()

        if self._page_label:
            self._page_label.setText(f"Page {self._current_page + 1} of {total_pages}")

        if self._prev_button:
            self._prev_button.setEnabled(self._current_page > 0)

        if self._next_button:
            self._next_button.setEnabled(self._current_page < total_pages - 1)


class ExportDialog(QWidget):
    """Dialog for exporting table data to various formats."""

    def export_csv(self, data: List[Dict[str, Any]], filename: str) -> None:
        """Export data to CSV file."""
        import csv

        if not data:
            return

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)

    def export_json(self, data: List[Dict[str, Any]], filename: str) -> None:
        """Export data to JSON file."""
        import json

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
