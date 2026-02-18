# History Tab Overhaul — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the history tab's QTableWidget with a Model/View architecture to support unlimited images, search/filter, scroll preservation, and tablet input.

**Architecture:** New `HistoryTableModel` (QAbstractTableModel) + `HistoryFilterProxyModel` (QSortFilterProxyModel) + `QTableView` replaces the existing QTableWidget. ThumbnailDelegate moves to the new module. Search bar with text + date range filters above the table. QScroller enables kinetic scrolling for tablet/pen.

**Tech Stack:** PySide6 (QAbstractTableModel, QSortFilterProxyModel, QTableView, QScroller, QStyledItemDelegate)

**Design doc:** `Plans/2026-02-18-history-tab-overhaul-design.md`
**Issues:** [#8](https://github.com/lelandg/ImageAI/issues/8), [#9](https://github.com/lelandg/ImageAI/issues/9)

---

### Task 1: Remove 500-Image Cap from `scan_disk_history()`

**Files:**
- Modify: `core/utils.py:288-336`

**Step 1: Update `scan_disk_history()` to remove the hard cap**

Change the function signature and remove the `scan_limit` early-exit logic:

```python
def scan_disk_history(max_items: int = 0, project_only: bool = False) -> list[Path]:
    """Scan generated dir for images and return sorted list by mtime desc.

    Args:
        max_items: Maximum number of items to return (0 = unlimited)
        project_only: If True, only return images with metadata sidecar files
    """
    try:
        out_dir = images_output_dir()
        exts = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

        # Collect files with mtime in single pass
        items_with_time = []

        for p in out_dir.iterdir():
            # Skip DEBUG images entirely for performance
            if p.name.startswith("DEBUG_"):
                continue

            # Check file type
            if not (p.is_file() and p.suffix.lower() in exts):
                continue

            # Check for sidecar if project_only
            if project_only:
                sidecar = p.with_suffix(p.suffix + ".json")
                if not sidecar.exists():
                    continue

            # Get mtime once
            try:
                mtime = p.stat().st_mtime
                items_with_time.append((mtime, p))
            except (OSError, AttributeError):
                continue

        # Sort by mtime (descending) and return
        items_with_time.sort(reverse=True, key=lambda x: x[0])
        if max_items > 0:
            return [p for _, p in items_with_time[:max_items]]
        return [p for _, p in items_with_time]

    except (OSError, IOError, AttributeError):
        return []
```

**Step 2: Verify no callers pass explicit max_items that would break**

Check all call sites — they all use `scan_disk_history(project_only=...)` without specifying max_items, so the default change from 500 to 0 (unlimited) applies everywhere.

**Step 3: Commit**

```
feat: remove 500-image cap from scan_disk_history (fixes #8 partial)
```

---

### Task 2: Create `gui/history_model.py` — HistoryTableModel

**Files:**
- Create: `gui/history_model.py`

**Step 1: Create the model file with HistoryTableModel**

```python
"""Model/View classes for the history tab."""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, QDate
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
        from PySide6.QtCore import QSize
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
        """Set text filter — matches against filename, prompt, provider, model."""
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
            return True

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
                # No parseable date — exclude if date filter is active
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
        elif isinstance(timestamp, str) and 'T' in timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return QDate(dt.year, dt.month, dt.day)
            except (ValueError, TypeError):
                return None
        return None

    def filtered_count(self) -> int:
        """Number of rows after filtering."""
        return self.rowCount()
```

**Step 2: Commit**

```
feat: add HistoryTableModel and HistoryFilterProxyModel (issues #8, #9)
```

---

### Task 3: Update `_init_history_tab()` to Use Model/View

**Files:**
- Modify: `gui/main_window.py` — `_init_history_tab()` (lines 3205-3413)
- Modify: `gui/main_window.py` — imports at top (lines 1-20)

**Step 1: Update imports at top of main_window.py**

Remove the early `ThumbnailDelegate`/`ThumbnailCache` classes (lines 14-128) from `main_window.py`. They are now in `gui/history_model.py`.

Add import at the existing import block (around line 185):

```python
from gui.history_model import (
    HistoryTableModel, HistoryFilterProxyModel, ThumbnailDelegate,
    ThumbnailCache, COL_THUMBNAIL, COL_DATETIME, ROLE_ENTRY_DICT,
    ROLE_THUMBNAIL_PATH, NUM_COLUMNS
)
```

Update the `__init__` to use the new `ThumbnailCache` from the import (line 232 stays the same since the class API is identical, just bump cache size):

```python
self.thumbnail_cache = ThumbnailCache(max_size=200)
```

**Step 2: Rewrite `_init_history_tab()`**

Replace the entire method. Key changes:
- `QTableView` instead of `QTableWidget`
- Model/proxy setup
- Search bar with `QLineEdit`, two `QDateEdit`, clear button
- `QScroller` for tablet support
- Dynamic count label

```python
def _init_history_tab(self):
    """Initialize history tab with model/view table and search."""
    from PySide6.QtWidgets import (
        QHeaderView, QCheckBox, QHBoxLayout, QTableView,
        QAbstractItemView, QLineEdit, QDateEdit
    )
    from PySide6.QtCore import QTimer, QDate
    from PySide6.QtScroller import QScroller  # noqa — may need: from PySide6.QtWidgets import QScroller

    v = QVBoxLayout(self.tab_history)

    # --- Search / filter bar ---
    search_layout = QHBoxLayout()

    self.history_search_edit = QLineEdit()
    self.history_search_edit.setPlaceholderText("Search by name, prompt, provider...")
    self.history_search_edit.setClearButtonEnabled(True)
    search_layout.addWidget(self.history_search_edit, stretch=3)

    search_layout.addWidget(QLabel("From:"))
    self.history_date_from = QDateEdit()
    self.history_date_from.setCalendarPopup(True)
    self.history_date_from.setSpecialValueText("Any")
    self.history_date_from.setDate(self.history_date_from.minimumDate())
    search_layout.addWidget(self.history_date_from)

    search_layout.addWidget(QLabel("To:"))
    self.history_date_to = QDateEdit()
    self.history_date_to.setCalendarPopup(True)
    self.history_date_to.setSpecialValueText("Any")
    self.history_date_to.setDate(self.history_date_to.minimumDate())
    search_layout.addWidget(self.history_date_to)

    self.btn_clear_search = QPushButton("Clear")
    self.btn_clear_search.clicked.connect(self._clear_history_search)
    search_layout.addWidget(self.btn_clear_search)

    v.addLayout(search_layout)

    # --- Controls row ---
    controls_layout = QHBoxLayout()
    self.chk_show_all_images = QCheckBox("Show non-project images")
    self.chk_show_all_images.setChecked(False)
    self.chk_show_all_images.toggled.connect(self._on_show_all_images_toggled)
    controls_layout.addWidget(self.chk_show_all_images)
    controls_layout.addStretch()

    self.history_count_label = QLabel("Showing 0 of 0 images")
    controls_layout.addWidget(self.history_count_label)
    v.addLayout(controls_layout)

    # --- Model setup ---
    self.history_model = HistoryTableModel(self)
    self.history_model.set_data(self.history)

    self.history_proxy = HistoryFilterProxyModel(self)
    self.history_proxy.setSourceModel(self.history_model)
    self.history_proxy.setDynamicSortFilter(True)

    # --- Table view ---
    self.history_view = QTableView()
    self.history_view.setModel(self.history_proxy)
    self.history_view.setAlternatingRowColors(True)
    self.history_view.setSelectionBehavior(QAbstractItemView.SelectRows)
    self.history_view.setSelectionMode(QAbstractItemView.SingleSelection)
    self.history_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
    self.history_view.setSortingEnabled(True)
    self.history_view.setMouseTracking(True)
    self.history_view.viewport().setMouseTracking(True)
    self.history_view.verticalHeader().setVisible(False)
    self.history_view.verticalHeader().setDefaultSectionSize(80)

    # Tablet / pen support — kinetic scrolling
    self.history_view.setDragEnabled(False)
    try:
        QScroller.grabGesture(self.history_view.viewport(), QScroller.LeftMouseButtonGesture)
    except Exception:
        pass  # QScroller not available on all platforms

    # Thumbnail delegate
    thumbnail_delegate = ThumbnailDelegate(self.thumbnail_cache, self.history_view)
    self.history_view.setItemDelegateForColumn(COL_THUMBNAIL, thumbnail_delegate)

    # Hover preview popup
    from gui.image_preview_popup import ImagePreviewPopup
    self.preview_popup = ImagePreviewPopup(self, max_width=600, max_height=600)

    # Column widths
    header = self.history_view.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(3, QHeaderView.Interactive)
    header.setSectionResizeMode(4, QHeaderView.Stretch)
    header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(7, QHeaderView.ResizeToContents)

    # Sort by date descending
    self.history_view.sortByColumn(COL_DATETIME, Qt.DescendingOrder)

    v.addWidget(self.history_view)

    # --- Buttons ---
    h = QHBoxLayout()
    self.btn_load_history = QPushButton("&Load Selected")
    self.btn_clear_history = QPushButton("C&lear History")
    h.addWidget(self.btn_load_history)
    h.addStretch()
    h.addWidget(self.btn_clear_history)
    v.addLayout(h)

    # Shortcuts hint
    history_shortcuts_label = create_shortcut_hint(
        "Alt+L to load, Alt+C to clear, Double-click to load item"
    )
    v.addWidget(history_shortcuts_label)

    # --- Connect signals ---
    self.history_view.doubleClicked.connect(self._on_history_item_double_clicked)
    self.btn_load_history.clicked.connect(self._load_selected_history)
    self.btn_clear_history.clicked.connect(self._clear_history)

    # Search debounce timer
    self._search_timer = QTimer(self)
    self._search_timer.setSingleShot(True)
    self._search_timer.setInterval(300)
    self._search_timer.timeout.connect(self._apply_history_search)
    self.history_search_edit.textChanged.connect(lambda: self._search_timer.start())
    self.history_date_from.dateChanged.connect(lambda: self._search_timer.start())
    self.history_date_to.dateChanged.connect(lambda: self._search_timer.start())

    # Update count when model changes
    self.history_proxy.rowsInserted.connect(self._update_history_count)
    self.history_proxy.rowsRemoved.connect(self._update_history_count)
    self.history_proxy.layoutChanged.connect(self._update_history_count)
    self.history_model.rowsInserted.connect(self._update_history_count)

    # Install event filter for hover preview and keyboard nav
    self.history_view.viewport().installEventFilter(self)
    self.history_view.installEventFilter(self)

    # Initial count
    self._update_history_count()
```

**Step 3: Add new helper methods**

```python
def _apply_history_search(self):
    """Apply current search/date filters to the history proxy model."""
    self.history_proxy.setFilterText(self.history_search_edit.text())

    date_from = self.history_date_from.date()
    date_to = self.history_date_to.date()

    # Only apply date filter if not at minimum (the "Any" value)
    from_valid = date_from > self.history_date_from.minimumDate()
    to_valid = date_to > self.history_date_to.minimumDate()

    self.history_proxy.setDateRange(
        date_from if from_valid else None,
        date_to if to_valid else None
    )

def _clear_history_search(self):
    """Clear all search/filter fields."""
    self.history_search_edit.clear()
    self.history_date_from.setDate(self.history_date_from.minimumDate())
    self.history_date_to.setDate(self.history_date_to.minimumDate())

def _update_history_count(self):
    """Update the history count label."""
    if hasattr(self, 'history_count_label') and hasattr(self, 'history_model'):
        filtered = self.history_proxy.rowCount()
        total = self.history_model.total_count()
        if filtered == total:
            self.history_count_label.setText(f"{total} images")
        else:
            self.history_count_label.setText(f"Showing {filtered} of {total} images")
```

**Step 4: Commit**

```
feat: rewrite _init_history_tab with QTableView model/view + search bar
```

---

### Task 4: Update History Mutation Methods

**Files:**
- Modify: `gui/main_window.py` — `_on_history_batch_loaded`, `_refresh_history_table`, `_add_to_history_table`, `_check_for_external_images`, `add_to_history`, `_clear_history`

**Step 1: Simplify `_on_history_batch_loaded`**

```python
def _on_history_batch_loaded(self, batch_items: list):
    """Handle a batch of history items loaded in background."""
    self.history.extend(batch_items)
    self.history_loaded_count = len(self.history)
    if hasattr(self, 'history_model'):
        self.history_model.add_entries(batch_items)
```

**Step 2: Simplify `_refresh_history_table`**

```python
def _refresh_history_table(self):
    """Refresh the history table with current history data."""
    if hasattr(self, 'history_model'):
        self.history_model.set_data(self.history)
```

**Step 3: Simplify `_add_to_history_table`**

```python
def _add_to_history_table(self, history_entry):
    """Add a single new entry to the history table."""
    if hasattr(self, 'history_model'):
        self.history_model.add_entry(history_entry)
```

**Step 4: Update `add_to_history`**

```python
def add_to_history(self, history_entry):
    """Public method to add an entry to history from other tabs."""
    self.history.append(history_entry)
    self._add_to_history_table(history_entry)
```

(This one stays the same — already delegates correctly.)

**Step 5: Update `_check_for_external_images`**

Remove the `[:100]` limit on scanning. Use `history_model.entry_paths()` instead of rebuilding the set:

```python
def _check_for_external_images(self):
    """Check if there are new images in the folder that we didn't generate."""
    if hasattr(self, 'history_model'):
        current_paths = self.history_model.entry_paths()
    else:
        current_paths = {str(item.get('path', '')) for item in self.history if item.get('path')}

    show_all = hasattr(self, 'chk_show_all_images') and self.chk_show_all_images.isChecked()
    disk_paths = scan_disk_history(project_only=not show_all)

    new_entries = []
    for path in disk_paths:
        if str(path) not in current_paths:
            sidecar = read_image_sidecar(path)
            if sidecar:
                entry = {
                    'path': path,
                    'prompt': sidecar.get('prompt', ''),
                    'timestamp': sidecar.get('timestamp', path.stat().st_mtime),
                    'model': sidecar.get('model', ''),
                    'provider': sidecar.get('provider', ''),
                    'width': sidecar.get('width', ''),
                    'height': sidecar.get('height', ''),
                    'cost': sidecar.get('cost', 0.0)
                }
            else:
                entry = {
                    'path': path,
                    'prompt': path.stem.replace('_', ' '),
                    'timestamp': path.stat().st_mtime,
                    'model': '',
                    'provider': '',
                    'cost': 0.0
                }
            new_entries.append(entry)

    if new_entries:
        self.history.extend(new_entries)
        if hasattr(self, 'history_model'):
            self.history_model.add_entries(new_entries)
```

**Step 6: Update `_clear_history`**

```python
def _clear_history(self):
    """Clear history."""
    reply = QMessageBox.question(
        self, APP_NAME,
        "Clear all history?",
        QMessageBox.Yes | QMessageBox.No
    )
    if reply == QMessageBox.Yes:
        self.history.clear()
        if hasattr(self, 'history_model'):
            self.history_model.clear()
```

**Step 7: Commit**

```
feat: update history mutation methods for model/view architecture
```

---

### Task 5: Update Event Handlers (Double-Click, Selection, Event Filter)

**Files:**
- Modify: `gui/main_window.py` — `_on_history_item_double_clicked`, `_load_selected_history`, `eventFilter`

**Step 1: Rewrite `_on_history_item_double_clicked` for QModelIndex**

The signal is now `QTableView.doubleClicked(QModelIndex)` instead of `QTableWidget.itemDoubleClicked(QTableWidgetItem)`:

```python
def _on_history_item_double_clicked(self, proxy_index):
    """Handle double-click on history item — load into image/video tab."""
    if not proxy_index.isValid():
        return

    # Map proxy index to source model to get the entry dict
    source_index = self.history_proxy.mapToSource(proxy_index)
    history_item = self.history_model.get_entry(source_index.row())
    if not isinstance(history_item, dict):
        return

    source_tab = history_item.get('source_tab', 'image')

    if source_tab == 'video':
        if hasattr(self, 'tab_video'):
            self.tabs.setCurrentWidget(self.tab_video)
            path = history_item.get('path')
            if path and path.exists():
                from PySide6.QtGui import QPixmap
                pixmap = QPixmap(str(path))
                if not pixmap.isNull() and hasattr(self.tab_video, 'workspace_widget'):
                    scaled = pixmap.scaled(
                        self.tab_video.workspace_widget.output_image_label.size(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    self.tab_video.workspace_widget.output_image_label.setPixmap(scaled)
                    self.tab_video.workspace_widget._log_to_console(
                        f"Loaded from history: {path.name}", "INFO"
                    )
    else:
        path = history_item.get('path')
        if path and path.exists():
            try:
                self.tabs.setCurrentWidget(self.tab_generate)
                image_data = path.read_bytes()
                self._last_displayed_image_path = path
                self.current_image_data = image_data
                self._display_image(image_data)
                self.btn_save_image.setEnabled(True)
                self.btn_copy_image.setEnabled(True)

                prompt = history_item.get('prompt', '')
                self.prompt_edit.setPlainText(prompt)

                model = history_item.get('model', '')
                if model:
                    idx = self._find_model_in_combo(model)
                    if idx >= 0:
                        self.model_combo.setCurrentIndex(idx)

                provider = history_item.get('provider', '')
                if provider and provider != self.current_provider:
                    idx = self.provider_combo.findText(provider)
                    if idx >= 0:
                        self.provider_combo.setCurrentIndex(idx)

                if hasattr(self, 'imagen_reference_widget'):
                    if 'imagen_references' in history_item:
                        self.imagen_reference_widget.from_dict(history_item['imagen_references'])
                    elif 'reference_image' in history_item:
                        legacy_data = {
                            "mode": "strict",
                            "references": [{
                                "reference_id": 1,
                                "path": history_item['reference_image'],
                                "reference_type": "subject"
                            }]
                        }
                        self.imagen_reference_widget.from_dict(legacy_data)
                    else:
                        self.imagen_reference_widget.clear_all()

                self.status_label.setText("Loaded from history")
                self.status_bar.showMessage("Loaded from history", 3000)
                self._update_use_current_button_state()

            except Exception as e:
                self.output_image_label.setText(f"Error loading image: {e}")
```

**Step 2: Rewrite `_load_selected_history`**

```python
def _load_selected_history(self):
    """Load the selected history item."""
    indexes = self.history_view.selectionModel().selectedRows()
    if indexes:
        self._on_history_item_double_clicked(indexes[0])
```

**Step 3: Update `eventFilter` to use `history_view` instead of `history_table`**

Replace all references to `self.history_table` with `self.history_view`:

```python
def eventFilter(self, obj, event):
    """Handle events for history table — hover preview and keyboard navigation."""
    from PySide6.QtCore import QEvent

    if not hasattr(self, 'history_view'):
        return super().eventFilter(obj, event)

    # Handle hover preview on history view viewport
    if obj == self.history_view.viewport() and hasattr(self, 'preview_popup'):
        if event.type() == QEvent.MouseMove:
            pos = event.pos()
            index = self.history_view.indexAt(pos)
            if index.isValid() and index.column() == COL_THUMBNAIL:
                source_index = self.history_proxy.mapToSource(index)
                entry = self.history_model.get_entry(source_index.row())
                if isinstance(entry, dict):
                    image_path = entry.get('path')
                    if image_path:
                        global_pos = self.history_view.viewport().mapToGlobal(pos)
                        self.preview_popup.show_preview(image_path, global_pos)
                        return False
            if hasattr(self, 'preview_popup'):
                self.preview_popup.schedule_hide(100)
        elif event.type() == QEvent.Leave:
            if hasattr(self, 'preview_popup'):
                self.preview_popup.schedule_hide(100)

    # Handle keyboard navigation on history view
    if obj == self.history_view and event.type() == QEvent.KeyPress:
        key = event.key()
        if key == Qt.Key_Home:
            if self.history_proxy.rowCount() > 0:
                self.history_view.selectRow(0)
                self.history_view.scrollToTop()
            return True
        elif key == Qt.Key_End:
            if self.history_proxy.rowCount() > 0:
                last_row = self.history_proxy.rowCount() - 1
                self.history_view.selectRow(last_row)
                self.history_view.scrollToBottom()
            return True
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            self._load_selected_history()
            return True

    return super().eventFilter(obj, event)
```

**Step 4: Commit**

```
feat: update history event handlers for model/view (double-click, filter, keyboard)
```

---

### Task 6: Update Scroll Position Preservation & Tab Change Handler

**Files:**
- Modify: `gui/main_window.py` — `_on_tab_changed`, add scroll save/restore

**Step 1: Save/restore scroll position in `_on_tab_changed`**

Add scroll position tracking. When leaving history tab, save scroll value. When entering, restore it and check for external images:

```python
# In _on_tab_changed, update the history tab block:
# If switching to history tab, check for new images
if current_widget == self.tab_history:
    self._check_for_external_images()
    # Restore scroll position if saved
    if hasattr(self, '_history_scroll_pos') and hasattr(self, 'history_view'):
        QTimer.singleShot(0, lambda: self.history_view.verticalScrollBar().setValue(
            self._history_scroll_pos
        ))
```

Add a complementary save when leaving (before the existing if blocks):

```python
# Save history scroll position when leaving history tab
prev_widget = self.tabs.widget(self.tabs.currentIndex())  # Actually need to track previous
# Simpler: save scroll on every tab change if history_view exists
if hasattr(self, 'history_view'):
    self._history_scroll_pos = self.history_view.verticalScrollBar().value()
```

**Step 2: Commit**

```
feat: preserve history tab scroll position across tab switches (fixes #9 partial)
```

---

### Task 7: Update UI State Save/Restore

**Files:**
- Modify: `gui/main_window.py` — `_save_ui_state` (line ~8297), `_restore_ui_state` (line ~8472)

**Step 1: Update `_save_ui_state` to use `history_view`**

Replace the `history_table` block:

```python
# History tab — column widths
if hasattr(self, 'history_view'):
    header = self.history_view.horizontalHeader()
    column_widths = []
    for i in range(NUM_COLUMNS):
        column_widths.append(header.sectionSize(i))
    ui_state['history_column_widths'] = column_widths
    ui_state['history_sort_column'] = header.sortIndicatorSection()
    sort_order = header.sortIndicatorOrder()
    ui_state['history_sort_order'] = 0 if sort_order == Qt.AscendingOrder else 1
```

**Step 2: Update `_restore_ui_state` to use `history_view`**

```python
# Restore history table column widths
if hasattr(self, 'history_view'):
    if 'history_column_widths' in ui_state:
        header = self.history_view.horizontalHeader()
        widths = ui_state['history_column_widths']
        for i, w in enumerate(widths):
            if i < NUM_COLUMNS:
                header.resizeSection(i, w)
    if 'history_sort_column' in ui_state and 'history_sort_order' in ui_state:
        sort_order = Qt.AscendingOrder if ui_state['history_sort_order'] == 0 else Qt.DescendingOrder
        self.history_view.sortByColumn(ui_state['history_sort_column'], sort_order)
```

**Step 3: Commit**

```
feat: update UI state save/restore for model/view history
```

---

### Task 8: Update `_on_show_all_images_toggled`

**Files:**
- Modify: `gui/main_window.py` — `_on_show_all_images_toggled` (line ~358)

**Step 1: Update to use model instead of table refresh**

```python
def _on_show_all_images_toggled(self, checked: bool):
    """Handle toggle of show all images checkbox."""
    # Stop any running background loader
    if self.history_loader_worker:
        self.history_loader_worker.stop()
    if self.history_loader_thread and self.history_loader_thread.isRunning():
        self.history_loader_thread.quit()
        self.history_loader_thread.wait()

    # Reload history with new filter
    self.history_paths = scan_disk_history(project_only=not checked)

    # Clear existing history data
    self.history = []
    self.history_loaded_count = 0

    # Clear the model
    if hasattr(self, 'history_model'):
        self.history_model.clear()

    # Load initial batch
    print(f"Loading initial metadata for {min(self.history_initial_load_size, len(self.history_paths))} of {len(self.history_paths)} images...")
    self._load_history_from_disk()
    print(f"Loaded metadata for {len(self.history)} images")

    # Update model with loaded data
    if hasattr(self, 'history_model'):
        self.history_model.set_data(self.history)

    # Start background loading of remaining items
    if self.history_loaded_count < len(self.history_paths):
        self._start_background_history_loader()
```

**Step 2: Commit**

```
feat: update show-all-images toggle for model/view
```

---

### Task 9: Clean Up — Remove Old QTableWidget Code

**Files:**
- Modify: `gui/main_window.py`

**Step 1: Remove the old `ThumbnailCache` and `ThumbnailDelegate` classes from main_window.py (lines 14-128)**

These are now in `gui/history_model.py`. Keep the import guard structure but remove the class definitions. The import at line ~185 handles providing these classes.

**Step 2: Remove the old `_refresh_history_table` duplication**

The old method (line ~8676) with its massive row-building loop is replaced by the 3-line version in Task 4. Delete the old body.

**Step 3: Search for any remaining `history_table` references and update to `history_view`**

Check for any straggler references. Key areas:
- `_on_generation_complete` (line ~6242): `if hasattr(self, 'history_table'):` → `if hasattr(self, 'history_model'):`
- Any other `self.history_table` reference → `self.history_view`

**Step 4: Verify QScroller import**

QScroller may be at `PySide6.QtWidgets.QScroller` or need a try/except fallback. Add safe import:

```python
try:
    from PySide6.QtScroller import QScroller
except ImportError:
    try:
        from PySide6.QtWidgets import QScroller
    except ImportError:
        QScroller = None
```

Then in `_init_history_tab`, guard the call:

```python
if QScroller is not None:
    QScroller.grabGesture(self.history_view.viewport(), QScroller.LeftMouseButtonGesture)
```

**Step 5: Commit**

```
refactor: remove old QTableWidget code from main_window, clean up imports
```

---

### Task 10: Syntax Check

**Step 1: Run Python syntax check**

Run: `source /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/activate && python3 -c "import py_compile; py_compile.compile('gui/history_model.py', doraise=True); py_compile.compile('gui/main_window.py', doraise=True); py_compile.compile('core/utils.py', doraise=True); print('All files compile OK')"`

Expected: `All files compile OK`

If syntax errors, fix them and re-run.

**Step 2: Run import check**

Run: `source /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/activate && python3 -c "from gui.history_model import HistoryTableModel, HistoryFilterProxyModel, ThumbnailDelegate, ThumbnailCache; print('Imports OK')"`

Expected: `Imports OK`

**Step 3: Final commit if any fixes were needed**

```
fix: resolve syntax/import issues from history tab refactor
```

---

## Summary

| Task | Description | Estimated Complexity |
|------|-------------|---------------------|
| 1 | Remove 500-image cap | Small |
| 2 | Create `gui/history_model.py` (model, proxy, delegate) | Large — new file |
| 3 | Rewrite `_init_history_tab()` | Large — full rewrite |
| 4 | Update mutation methods | Medium — 6 methods |
| 5 | Update event handlers | Medium — 3 methods |
| 6 | Scroll position preservation | Small |
| 7 | UI state save/restore | Small |
| 8 | Show-all-images toggle | Small |
| 9 | Clean up old code | Medium — careful search |
| 10 | Syntax check | Small |
