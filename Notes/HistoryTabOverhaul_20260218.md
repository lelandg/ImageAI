# History Tab Overhaul — Implementation Summary

**Date:** 2026-02-18 09:29
**Issues:** [#8](https://github.com/lelandg/ImageAI/issues/8), [#9](https://github.com/lelandg/ImageAI/issues/9)
**Status:** Implemented, ready for testing

## What Changed

### Issue #8: History errors & enhancements
- **Removed 500-image cap** — `scan_disk_history()` now returns all images (default unlimited)
- **Correct count display** — Dynamic label shows "Showing X of Y images" (filtered vs total)
- **Search/filter** — Search bar filters by filename, prompt text, provider, model name
- **Date range filter** — From/To date pickers to filter by date range

### Issue #9: Tablet support & scroll preservation
- **Kinetic scrolling** — `QScroller.grabGesture()` enables pen-drag-to-scroll
- **Single selection mode** — Pen tap selects one row cleanly (no drag-select)
- **Scroll position preserved** — Saved when leaving history tab, restored when returning
- **No scroll jump on external image detection** — New images added via model without resetting scroll

## Architecture Change

Replaced `QTableWidget` with `QAbstractTableModel` + `QSortFilterProxyModel` + `QTableView`:
- **`gui/history_model.py`** (NEW) — `HistoryTableModel`, `HistoryFilterProxyModel`, `ThumbnailDelegate`, `ThumbnailCache`
- **`gui/main_window.py`** — Rewrote `_init_history_tab()`, simplified 6+ mutation methods, updated all event handlers
- **`core/utils.py`** — Removed hard 500 cap from `scan_disk_history()`

## Files Changed

| File | Change |
|------|--------|
| `gui/history_model.py` | NEW — 390 lines, all model/view classes |
| `gui/main_window.py` | Major refactor — removed old ThumbnailCache/Delegate, rewrote history tab init, simplified ~15 methods |
| `core/utils.py` | `scan_disk_history()` default `max_items` 500→0, removed early-exit logic |

## Testing Notes

- Syntax check: All 3 files pass `py_compile`
- PySide6 runtime testing needed (run app in PowerShell)
- Test: Search by prompt text, provider name
- Test: Date range filtering
- Test: Scroll position preserved when switching tabs
- Test: Wacom tablet interaction (scroll, tap to select, double-click to load)
- Test: Large history (>500 images) loads correctly with background loader
- Test: "Show non-project images" toggle still works
