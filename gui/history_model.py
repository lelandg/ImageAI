"""Model/View classes for the history tab."""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, QDate, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QStyledItemDelegate, QStyle

logger = logging.getLogger(__name__)

# Column indices
COL_THUMBNAIL = 0
COL_DATETIME = 1
COL_PROVIDER = 2
COL_MODEL = 3
COL_PROMPT = 4
COL_RESOLUTION = 5
COL_COST = 6
COL_REFS = 7
NUM_COLUMNS = 8

COLUMN_HEADERS = [
    "Thumbnail", "Date & Time", "Provider", "Model",
    "Prompt", "Resolution", "Cost", "Refs"
]

# Custom roles
ROLE_ENTRY_DICT = Qt.UserRole + 10      # Full history entry dict
ROLE_THUMBNAIL_PATH = Qt.UserRole + 11  # Path string for thumbnail
ROLE_SORT_VALUE = Qt.UserRole + 12      # Sortable value (datetime obj, float, etc.)


class ThumbnailCache:
    """LRU cache for thumbnail QPixmaps."""

    def __init__(self, max_size: int = 200):
        self.cache: Dict[str, QPixmap] = {}
        self.max_size = max_size
        self.access_order: List[str] = []
        self.hits = 0
        self.misses = 0

    def get(self, path: str) -> Optional[QPixmap]:
        """Get thumbnail from cache, creating it if needed."""
        if path in self.cache:
            self.hits += 1
            self.access_order.remove(path)
            self.access_order.append(path)
            return self.cache[path]

        self.misses += 1
        if Path(path).exists():
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                thumbnail = pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.FastTransformation)
                self.cache[path] = thumbnail
                self.access_order.append(path)
                if len(self.cache) > self.max_size:
                    oldest = self.access_order.pop(0)
                    del self.cache[oldest]
                return thumbnail
        return None

    def get_stats(self):
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            'size': len(self.cache),
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': hit_rate
        }

    def clear(self):
        """Clear the cache."""
        self.cache.clear()
        self.access_order.clear()


class ThumbnailDelegate(QStyledItemDelegate):
    """Custom delegate for rendering thumbnails in the history table."""

    def __init__(self, thumbnail_cache: ThumbnailCache, parent=None):
        super().__init__(parent)
        self.thumbnail_cache = thumbnail_cache

    def paint(self, painter, option, index):
        """Custom painting for thumbnail column."""
        if index.column() == COL_THUMBNAIL:
            path_str = index.data(ROLE_THUMBNAIL_PATH)
            if path_str and Path(path_str).exists():
                thumbnail = self.thumbnail_cache.get(path_str)
                if thumbnail:
                    x = option.rect.center().x() - thumbnail.width() // 2
                    y = option.rect.center().y() - thumbnail.height() // 2
                    if option.state & QStyle.State_Selected:
                        painter.fillRect(option.rect, option.palette.highlight())
                    painter.drawPixmap(x, y, thumbnail)
                    return
        super().paint(painter, option, index)

    def sizeHint(self, option, index):
        """Provide size hint for thumbnail column."""
        if index.column() == COL_THUMBNAIL:
            return QSize(80, 80)
        return super().sizeHint(option, index)


class HistoryTableModel(QAbstractTableModel):
    """Table model for image generation history.

    Holds all history entries in memory. Only visible rows are rendered by the view.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[Dict] = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return NUM_COLUMNS

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if 0 <= section < NUM_COLUMNS:
                return COLUMN_HEADERS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._data)):
            return None

        item = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            return self._display_data(item, col)
        elif role == Qt.ToolTipRole:
            return self._tooltip_data(item, col)
        elif role == ROLE_ENTRY_DICT:
            return item
        elif role == ROLE_THUMBNAIL_PATH:
            if col == COL_THUMBNAIL:
                path = item.get('path', '')
                return str(path) if path else ''
            return None
        elif role == ROLE_SORT_VALUE:
            return self._sort_value(item, col)
        elif role == Qt.TextAlignmentRole:
            if col == COL_REFS:
                return int(Qt.AlignCenter)
            return None

        return None

    def _display_data(self, item: Dict, col: int) -> str:
        if col == COL_THUMBNAIL:
            return ""  # Handled by delegate
        elif col == COL_DATETIME:
            return self._format_timestamp(item.get('timestamp', ''))
        elif col == COL_PROVIDER:
            provider = item.get('provider', '')
            return provider.title() if provider else 'Unknown'
        elif col == COL_MODEL:
            model = item.get('model', '')
            return model.split('/')[-1] if '/' in model else model
        elif col == COL_PROMPT:
            return item.get('prompt', 'No prompt')
        elif col == COL_RESOLUTION:
            w = item.get('width', '')
            h = item.get('height', '')
            return f"{w}x{h}" if w and h else ''
        elif col == COL_COST:
            cost = item.get('cost', 0.0)
            return f"${cost:.2f}" if cost and cost > 0 else '-'
        elif col == COL_REFS:
            count = self._ref_count(item)
            if count > 1:
                return f"\U0001f4ce {count}"
            elif count == 1:
                return "\U0001f4ce"
            return ""
        return ""

    def _tooltip_data(self, item: Dict, col: int) -> Optional[str]:
        if col == COL_MODEL:
            return item.get('model', '')
        elif col == COL_PROMPT:
            return f"Full prompt:\n{item.get('prompt', '')}"
        elif col == COL_REFS:
            return self._ref_tooltip(item)
        return None

    def _sort_value(self, item: Dict, col: int) -> Any:
        """Return a sortable value for the column."""
        if col == COL_DATETIME:
            return self._parse_timestamp(item.get('timestamp', ''))
        elif col == COL_COST:
            return item.get('cost', 0.0) or 0.0
        elif col == COL_REFS:
            return self._ref_count(item)
        # For text columns, return display value
        return self._display_data(item, col)

    def _format_timestamp(self, timestamp) -> str:
        if isinstance(timestamp, (int, float)):
            try:
                return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            except (OSError, ValueError):
                return str(timestamp)
        elif isinstance(timestamp, str) and 'T' in timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                parts = timestamp.split('T')
                date_str = parts[0]
                time_str = parts[1].split('.')[0] if len(parts) > 1 else ''
                return f"{date_str} {time_str}"
        return str(timestamp) if timestamp else ''

    def _parse_timestamp(self, timestamp) -> float:
        """Parse timestamp to a float for sorting."""
        if isinstance(timestamp, (int, float)):
            return float(timestamp)
        elif isinstance(timestamp, str) and 'T' in timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return dt.timestamp()
            except (ValueError, TypeError):
                pass
        return 0.0

    @staticmethod
    def _ref_count(item: Dict) -> int:
        if 'imagen_references' in item:
            refs_data = item['imagen_references']
            if isinstance(refs_data, dict) and 'references' in refs_data:
                return len(refs_data['references'])
        elif 'reference_image' in item:
            return 1
        return 0

    @staticmethod
    def _ref_tooltip(item: Dict) -> Optional[str]:
        if 'imagen_references' in item:
            refs_data = item['imagen_references']
            if isinstance(refs_data, dict) and 'references' in refs_data:
                names = []
                for ref in refs_data['references']:
                    ref_path = ref.get('path', '')
                    name = Path(ref_path).name if ref_path else 'Unknown'
                    ref_type = ref.get('type', '').upper()
                    names.append(f"{name} ({ref_type})" if ref_type else name)
                return "Reference Images:\n" + "\n".join(names)
        elif 'reference_image' in item:
            ref_path = item['reference_image']
            name = Path(ref_path).name if ref_path else 'Unknown'
            return f"Reference Image:\n{name}"
        return None

    # --- Mutation methods ---

    def add_entry(self, entry: Dict):
        """Add a single entry to the model."""
        row = len(self._data)
        self.beginInsertRows(QModelIndex(), row, row)
        self._data.append(entry)
        self.endInsertRows()

    def add_entries(self, entries: List[Dict]):
        """Add multiple entries (batch from background loader)."""
        if not entries:
            return
        first = len(self._data)
        last = first + len(entries) - 1
        self.beginInsertRows(QModelIndex(), first, last)
        self._data.extend(entries)
        self.endInsertRows()

    def set_data(self, entries: List[Dict]):
        """Replace all data."""
        self.beginResetModel()
        self._data = list(entries)
        self.endResetModel()

    def clear(self):
        """Remove all entries."""
        self.beginResetModel()
        self._data.clear()
        self.endResetModel()

    def get_entry(self, row: int) -> Optional[Dict]:
        """Get the history entry dict for a row."""
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def total_count(self) -> int:
        """Total number of entries in the model."""
        return len(self._data)

    def entry_paths(self) -> set:
        """Return set of all path strings currently in the model."""
        return {str(item.get('path', '')) for item in self._data if item.get('path')}


class HistoryFilterProxyModel(QSortFilterProxyModel):
    """Filter proxy that supports text search and date range filtering."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_text = ""
        self._date_from: Optional[QDate] = None
        self._date_to: Optional[QDate] = None
        # Sort by the ROLE_SORT_VALUE role for proper sorting
        self.setSortRole(ROLE_SORT_VALUE)

    def setFilterText(self, text: str):
        """Set text filter - matches against filename, prompt, provider, model."""
        self._filter_text = text.lower().strip()
        self.invalidateFilter()

    def setDateRange(self, date_from: Optional[QDate], date_to: Optional[QDate]):
        """Set date range filter."""
        self._date_from = date_from if date_from and date_from.isValid() else None
        self._date_to = date_to if date_to and date_to.isValid() else None
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return True

        entry = model.get_entry(source_row)
        if entry is None:
            return False

        # Text filter
        if self._filter_text:
            searchable = " ".join([
                str(Path(entry.get('path', '')).stem).replace('_', ' '),
                entry.get('prompt', ''),
                entry.get('provider', ''),
                entry.get('model', ''),
            ]).lower()
            if self._filter_text not in searchable:
                return False

        # Date range filter
        if self._date_from or self._date_to:
            ts = entry.get('timestamp', '')
            entry_date = self._extract_date(ts)
            if entry_date:
                if self._date_from and entry_date < self._date_from:
                    return False
                if self._date_to and entry_date > self._date_to:
                    return False
            else:
                # No parseable date - exclude if date filter is active
                return False

        return True

    @staticmethod
    def _extract_date(timestamp) -> Optional[QDate]:
        """Extract QDate from a timestamp value."""
        if isinstance(timestamp, (int, float)):
            try:
                dt = datetime.fromtimestamp(timestamp)
                return QDate(dt.year, dt.month, dt.day)
            except (OSError, ValueError):
                return None
        elif isinstance(timestamp, str):
            # Try ISO format with 'T' separator
            if 'T' in timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    return QDate(dt.year, dt.month, dt.day)
                except (ValueError, TypeError):
                    pass
            # Try space-separated datetime (e.g. "2025-01-15 10:30:00")
            try:
                dt = datetime.fromisoformat(timestamp)
                return QDate(dt.year, dt.month, dt.day)
            except (ValueError, TypeError):
                pass
            # Try date-only string (e.g. "2025-01-15")
            try:
                parts = timestamp.split('-')
                if len(parts) == 3:
                    return QDate(int(parts[0]), int(parts[1]), int(parts[2].split()[0]))
            except (ValueError, IndexError):
                pass
            # Try numeric string (timestamp as string)
            try:
                ts_float = float(timestamp)
                dt = datetime.fromtimestamp(ts_float)
                return QDate(dt.year, dt.month, dt.day)
            except (ValueError, OSError):
                pass
        return None

    def filtered_count(self) -> int:
        """Number of rows after filtering."""
        return self.rowCount()
