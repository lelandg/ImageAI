# History Tab Overhaul Design — Issues #8 & #9

**Date:** 2026-02-18 09:07
**Issues:** [#8 History errors & enhancements](https://github.com/lelandg/ImageAI/issues/8), [#9 Add tablet support](https://github.com/lelandg/ImageAI/issues/9)
**Status:** Approved

## Problem Summary

**Issue #8:** History capped at 500 images. Always displays "500" even when more exist. No search/filter. Need correct count, on-demand loading, and search by name/date/prompt.

**Issue #9:** Wacom tablet can't scroll, select, or drag properly in history. Scroll position lost when switching tabs. Need kinetic scrolling, proper pen input, and dynamic page loading around current position.

## Approach: Model/View Architecture (Approach A)

Replace `QTableWidget` with `QAbstractTableModel` + `QTableView`. This is Qt's native solution for large datasets — only visible rows are rendered, sorting/filtering is handled by proxy model, and scroll position is inherently preserved.

## Architecture

### 1. Data Layer — Remove 500 Cap

**File:** `core/utils.py`

`scan_disk_history()` default `max_items` changed to `0` (unlimited). Remove `scan_limit` early-exit logic. All image paths collected, sorted by mtime desc, returned in full. Metadata is ~200 bytes/entry — 10,000 files is ~2MB, trivially fits in memory.

Background loader (`HistoryLoaderWorker`) continues loading metadata in batches of 25 — no changes needed.

### 2. New File: `gui/history_model.py`

**`HistoryTableModel(QAbstractTableModel)`**
- Holds `self._data: List[dict]` (history entries)
- Columns: Thumbnail, Date & Time, Provider, Model, Prompt, Resolution, Cost, Refs
- Standard model interface: `rowCount()`, `columnCount()`, `data()`, `headerData()`
- `add_entry(entry)` / `add_entries(entries)` — for background loader batches, uses `beginInsertRows`/`endInsertRows`
- `get_entry(row)` — returns dict for a row
- Custom roles for thumbnail path (`Qt.UserRole`), sortable datetime (`Qt.UserRole + 1`), full entry dict (`Qt.UserRole + 2`)

**`HistoryFilterProxyModel(QSortFilterProxyModel)`**
- Sits between model and view
- `setFilterText(text)` — matches against filename, prompt, provider, model columns
- `setDateRange(start, end)` — optional date range filtering
- `filterAcceptsRow()` implements the matching logic
- Sorting delegated to proxy (handles sort indicators automatically)

**`ThumbnailDelegate(QStyledItemDelegate)`**
- Moved from `main_window.py` to `history_model.py`
- Reads path from model role instead of `QTableWidgetItem.data()`
- Thumbnail cache size increased from 50 to 200

### 3. UI Changes in `_init_history_tab()`

**Search bar** above the table:
```
[Search...                         ] [From: ____] [To: ____] [Clear]
[Show non-project images]
┌──────┬─────────────┬──────────┬───────┬────────┬─────┬──────┬─────┐
│Thumb │ Date & Time │ Provider │ Model │ Prompt │ Res │ Cost │Refs │
```

- `QLineEdit` search field with placeholder "Search by name, prompt, provider..."
- Two `QDateEdit` fields for optional date range (From/To)
- Clear button to reset all filters
- Search debounced via 300ms `QTimer` to avoid filtering on every keystroke

**Count label** — dynamic: `"Showing X of Y images"` (X = filtered, Y = total). Updates via model `rowsInserted`/`layoutChanged` signals.

### 4. Scroll Position Preservation

- `QTableView` + model inherently preserves scroll when switching tabs (widget persists)
- Save `verticalScrollBar().value()` in `_on_tab_changed()` when leaving history tab
- Restore scroll position when returning to history tab
- When adding external images, save/restore scroll position around the insert

### 5. Tablet / Pen Input Support

- `setDragEnabled(False)` — prevents drag-select behavior with pen
- `setSelectionMode(QAbstractItemView.SingleSelection)` — pen tap selects one row
- `QScroller.grabGesture(viewport, QScroller.LeftMouseButtonGesture)` — enables kinetic scrolling for pen/touch input (pen drag = scroll, pen tap = select)

### 6. Files Changed

| File | Change |
|------|--------|
| `gui/history_model.py` | **NEW** — `HistoryTableModel`, `HistoryFilterProxyModel`, `ThumbnailDelegate` |
| `gui/main_window.py` | Replace `QTableWidget` with `QTableView` + model. Update `_init_history_tab`, `_refresh_history_table`, `_add_to_history_table`, `_on_history_batch_loaded`, `_on_history_item_double_clicked`, `_load_selected_history`, `eventFilter`, `_check_for_external_images`, `_save_ui_state`, `_restore_ui_state`. Add search bar, scroll preservation, tablet support. |
| `core/utils.py` | Remove 500 cap from `scan_disk_history()` |
| `gui/workers.py` | No changes needed |

### 7. Backward Compatibility

- All existing signals (`batch_loaded`, `progress`, `finished`) still work
- History entry dict format unchanged
- Sidecar reading unchanged
- UI state save/restore updated for new column layout (same columns, different storage)
