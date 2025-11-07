# Reference Images Unlimited & History Tab Improvements

**Last Updated:** 2025-11-07

## Overview

Implementation plan for supporting unlimited reference images and improving the History tab UX.

## Phase 1: Reference Image Unlimited Support ✅ COMPLETED

**Status:** Phase 1 is **100% complete**.

### Goals
- Remove the 4-image limit for reference images
- Support dynamic canvas sizing for any number of images
- Update UI to handle unlimited images with proper layout

### Completed Tasks

#### 1.1 Remove Reference ID Validation Limit ✅
**File:** `core/reference/imagen_reference.py`

**Changes:**
- Line 74-75: Changed validation from `if not 1 <= self.reference_id <= 4:` to `if self.reference_id < 1:`
- Line 214-216: Removed `elif len(references) > 4:` check in `validate_references()`
- Now allows any positive reference ID (>= 1)

**Reasoning:** The 1-4 limit was artificial and prevented users from adding more than 4 reference images. The compositor and underlying systems already support unlimited images.

#### 1.2 Update Reference Widget Layout ✅
**File:** `gui/imagen_reference_widget.py`

**Changes:**
- Lines 28-110: Added new `FlowLayout` class that wraps widgets automatically
- Lines 540-550: Replaced `QHBoxLayout` with `FlowLayout` in scrollable container
- Line 634: Simplified `_add_reference` to use `addWidget()` instead of `insertWidget()`

**Implementation Details:**
```python
class FlowLayout(QLayout):
    """Layout that wraps widgets left-to-right, top-to-bottom"""
    - Automatically calculates when to wrap to new row
    - Responds to parent width changes
    - Supports dynamic addition/removal of widgets
```

**UI Changes:**
- Reference images now appear in a wrapping grid
- Container has vertical scroll bar
- Horizontal scroll bar disabled (all wrapping is automatic)
- Maintains 20px spacing between items

#### 1.3 Image Compositor Already Supports Unlimited ✅
**File:** `core/reference/image_compositor.py`

**No changes needed** - The compositor already had dynamic grid calculation:
- Line 127: `cols = math.ceil(math.sqrt(num_images))` - calculates grid size
- Line 128: `rows = math.ceil(num_images / cols)` - distributes evenly
- Lines 131-133: Dynamically calculates cell sizes based on image count
- Supports any number of images

**Result:** Compositor creates appropriately sized canvas for any number of images.

### Testing Notes

**Before:** Adding 5+ reference images caused `ValueError: reference_id must be 1-4, got 5`

**After:**
- Can add unlimited reference images in Flexible mode
- Images automatically wrap to new rows
- Vertical scrolling works correctly
- No errors when adding 10+ images

### Files Modified in Phase 1
1. `core/reference/imagen_reference.py` - 2 changes (lines 74-75, 214-216)
2. `gui/imagen_reference_widget.py` - 3 sections (FlowLayout class, layout setup, add method)
3. `core/reference/image_compositor.py` - No changes (already supported unlimited)

---

## Phase 2: History Tab Improvements ⏳ IN PROGRESS

**Status:** Phase 2 is **25% complete** (1 of 4 tasks).

**Last Updated:** 2025-11-07

### Goals
- Add hover preview for full-size images
- Add search/filter functionality to history
- Persist scroll position across sessions
- Support double-click to load prompt into Generate tab

### Task Breakdown

#### 2.1 Add Hover Image Preview ⏳ IN PROGRESS
**File:** `gui/main_window.py` (~line 2943-3102)

**Requirements:**
- Show full-size image in tooltip/popup when hovering over thumbnail
- Display image at reasonable size (max 512px) in popup
- Show full prompt text on hover over prompt column
- Use QToolTip or custom QWidget popup

**Implementation Approach:**
```python
# Option A: Use QToolTip with rich text and embedded image
def show_image_tooltip(self, pos, image_path):
    pixmap = QPixmap(image_path).scaled(512, 512, Qt.KeepAspectRatio)
    # Convert to tooltip somehow

# Option B: Create custom hover widget
class ImagePreviewPopup(QWidget):
    def __init__(self, image_path):
        # Show borderless window at cursor with full image
```

**Estimated Complexity:** Medium - Need to handle QEvent.Enter/Leave on table cells

#### 2.2 Add Search Box to History Tab ⏸️ PENDING
**File:** `gui/main_window.py` (~line 2951-2960)

**Requirements:**
- Add QLineEdit search box above history table
- Filter table rows based on:
  - Prompt text (case-insensitive)
  - Provider name
  - Model name
  - Date range (optional)
- Update table in real-time as user types
- Show "X of Y entries" when filtered

**Implementation Approach:**
```python
# Add search box to layout
self.history_search = QLineEdit()
self.history_search.setPlaceholderText("Search prompts, provider, model...")
self.history_search.textChanged.connect(self._filter_history_table)

def _filter_history_table(self, search_text):
    search_lower = search_text.lower()
    for row in range(self.history_table.rowCount()):
        # Check all searchable columns
        prompt = self.history_table.item(row, 4).text().lower()
        provider = self.history_table.item(row, 2).text().lower()
        model = self.history_table.item(row, 3).text().lower()

        match = (search_lower in prompt or
                 search_lower in provider or
                 search_lower in model)

        self.history_table.setRowHidden(row, not match)

    # Update count label
    visible = sum(1 for r in range(self.history_table.rowCount())
                  if not self.history_table.isRowHidden(r))
    self.history_label.setText(f"History ({visible} of {len(self.history)} items)")
```

**Estimated Complexity:** Low - Standard Qt filtering pattern

#### 2.3 Remember Scroll Position Across Sessions ⏸️ PENDING
**File:** `gui/main_window.py` (~line 3098)

**Requirements:**
- Save vertical scroll position when closing app
- Restore scroll position on startup after table is populated
- Use QSettings to persist across sessions
- Store as percentage (not absolute) for different screen sizes

**Implementation Approach:**
```python
def _save_history_scroll_position(self):
    """Called in closeEvent or on tab change"""
    scrollbar = self.history_table.verticalScrollBar()
    if scrollbar.maximum() > 0:
        position_pct = scrollbar.value() / scrollbar.maximum()
    else:
        position_pct = 0.0

    self.settings.setValue("history_scroll_position", position_pct)

def _restore_history_scroll_position(self):
    """Called after table is populated"""
    position_pct = self.settings.value("history_scroll_position", 0.0, type=float)
    scrollbar = self.history_table.verticalScrollBar()

    # Use QTimer to restore after layout is complete
    QTimer.singleShot(100, lambda: scrollbar.setValue(
        int(position_pct * scrollbar.maximum())
    ))
```

**Estimated Complexity:** Low - Standard QSettings pattern

#### 2.4 Double-Click to Load Prompt ⏸️ PENDING
**File:** `gui/main_window.py` (~line 6428)

**Requirements:**
- Double-click on history row loads full prompt into Generate tab prompt field
- Load all generation settings (model, resolution, provider)
- Optionally load the generated image as reference (ask user?)
- Switch to Generate tab automatically
- Set focus to prompt field for editing

**Current Implementation:**
- Line 3099: `self.history_table.itemClicked.connect(self._on_history_item_clicked)`
- Line 6428: `_on_history_item_clicked` currently handles single clicks

**New Implementation:**
```python
# Update line 3099 to use doubleClicked instead
self.history_table.itemDoubleClicked.connect(self._load_history_item)

def _load_history_item(self, item):
    """Load a history item into the Generate tab (double-click)"""
    row = self.history_table.row(item)
    datetime_item = self.history_table.item(row, 1)  # Date column has data
    history_data = datetime_item.data(Qt.UserRole)

    if not history_data:
        return

    # Load prompt
    prompt = history_data.get('prompt', '')
    self.prompt.setPlainText(prompt)

    # Load provider if different
    provider = history_data.get('provider', '')
    if provider and provider != self.current_provider:
        # Find provider in combo and switch
        idx = self.provider_combo.findText(provider, Qt.MatchFixedString)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)

    # Load model
    model = history_data.get('model', '')
    if model:
        idx = self._find_model_in_combo(model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)

    # Load resolution
    width = history_data.get('width', 1024)
    height = history_data.get('height', 1024)
    if hasattr(self, 'resolution_selector'):
        self.resolution_selector.set_dimensions(width, height)

    # Switch to Generate tab
    self.tabs.setCurrentWidget(self.tab_generate)

    # Set focus to prompt for immediate editing
    self.prompt.setFocus()

    self.console_log(f"Loaded history item: {prompt[:50]}...")
```

**Estimated Complexity:** Low - Data is already structured correctly

---

## Phase 3: Dialog History Improvements (Future)

**Status:** Not started - lower priority than Phase 2.

### Goals
- Apply same improvements to `DialogHistoryWidget` (used in prompt dialogs)
- Hover preview for LLM responses
- Search within dialog history
- Double-click to reload into dialog fields

### Files to Modify
- `gui/history_widget.py` (316 lines)
- `gui/prompt_generation_dialog.py`
- `gui/prompt_question_dialog.py`

---

## Testing Checklist

### Phase 1 Testing ✅
- [x] Add 5+ reference images in Flexible mode - no errors
- [x] Add 10+ reference images - wrapping works
- [x] Remove images - IDs renumber correctly
- [x] Switch between Flexible and Strict modes
- [x] Generate with 2+ images in Flexible mode - compositing works
- [x] Scroll vertically through reference images

### Phase 2 Testing (When Complete)
- [ ] Hover over thumbnail - full image appears
- [ ] Hover over long prompt - full text shows
- [ ] Type in search box - table filters correctly
- [ ] Clear search - all items reappear
- [ ] Close app - scroll position saved
- [ ] Reopen app - scroll position restored
- [ ] Double-click history row - prompt loads into Generate tab
- [ ] Double-click loads correct provider/model/resolution

---

## Known Issues

### Issue: Horizontal Overflow Before Fix
**Symptom:** Adding 5+ reference images caused them to extend horizontally off-screen
**Root Cause:** Using `QHBoxLayout` with no wrapping
**Fix:** Replaced with `FlowLayout` that wraps automatically
**Status:** ✅ RESOLVED

### Issue: ValueError When Adding 5th Image
**Symptom:** `ValueError: reference_id must be 1-4, got 5`
**Root Cause:** Hard-coded validation in `ImagenReference.__post_init__`
**Fix:** Changed to `if self.reference_id < 1:`
**Status:** ✅ RESOLVED

---

## Implementation Notes

### Why FlowLayout Instead of QGridLayout?
- QGridLayout requires explicit row/column assignment
- FlowLayout automatically calculates positioning
- FlowLayout responds to parent width changes (responsive)
- Simpler to maintain - just add/remove widgets

### Why Compositor Already Worked?
The compositor's grid calculation was already dynamic:
```python
cols = math.ceil(math.sqrt(num_images))  # 1→1x1, 4→2x2, 9→3x3, 10→4x3
rows = math.ceil(num_images / cols)
```

This creates approximately square grids regardless of image count.

### Reference Widget Modes
- **Flexible Mode**: Unlimited images, composited before sending to API
- **Strict Mode**: Max 3 images, uses Imagen 3 Customization API directly
- Switching from Flexible to Strict with >3 images prompts user to select which 3 to keep

---

## Future Enhancements

### Phase 4: Advanced Features (Backlog)
- Drag-and-drop reordering of reference images
- Batch operations on history (delete multiple, export selection)
- History filtering by date range picker
- Save frequently used reference image sets as "templates"
- Export/import reference image configurations

---

## Performance Considerations

### Current Performance
- FlowLayout calculates geometry on every resize (negligible for <100 widgets)
- History table loads all rows at once (tested with 500 items - fast enough)
- Thumbnail cache prevents repeated image loading

### Future Optimizations (if needed)
- Virtual scrolling for history table (if >1000 items)
- Lazy loading of history table rows
- Background thumbnail generation for reference images

---

## Related Documentation
- `Docs/Reference-Image-Composite-Feature.md` - Original compositing design
- `Plans/Google-Imagen3-Multi-Reference-Implementation.md` - Imagen 3 API integration
- `gui/reference_selection_dialog.py` - Dialog for selecting references when switching modes
- `core/reference/image_compositor.py` - Compositing engine implementation
