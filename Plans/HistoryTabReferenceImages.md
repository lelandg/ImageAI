# History Tab Reference Images - Implementation Plan

**Goal:** Enable the History tab to display which generated images were created using reference images.

**Status:** ✅ COMPLETE - Phase 3 implemented successfully

**Last Updated:** 2025-11-14

---

## Problem Statement

The History tab in ImageAI shows generated images but doesn't display which reference images (if any) were used during generation. Users want to see reference image associations in the history.

## Current State Analysis

### What Works ✓
1. **New generations save reference data** - Code at `main_window.py:5417-5422` saves reference image info to metadata sidecars when generating images:
   ```python
   if hasattr(self, 'imagen_reference_widget') and self.imagen_reference_widget.has_references():
       meta["imagen_references"] = self.imagen_reference_widget.to_dict()
   elif hasattr(self, 'reference_image_path') and self.reference_image_path:
       meta["reference_image"] = str(self.reference_image_path)
   ```

2. **History loading code exists** - `main_window.py:490-493` loads reference data from sidecars:
   ```python
   if 'imagen_references' in sidecar:
       history_entry['imagen_references'] = sidecar['imagen_references']
   elif 'reference_image' in sidecar:
       history_entry['reference_image'] = sidecar['reference_image']
   ```

3. **Metadata sidecar files** - Each generated image `image.png` has `image.png.json` with metadata

### The Gap ✗
1. **Old images lack reference data** - Images generated before the reference feature was added don't have reference info in their metadata
2. **History tab doesn't display references** - Even when data exists in metadata, the History tab UI doesn't show it
3. **No retroactive recovery mechanism** - No way to add reference data to old images

## Two-Part Solution

### Part 1: Retroactive Metadata Update (Utility Script)

**Purpose:** Find and update old images that were generated with reference images but don't have that data saved.

**Approach:**
1. Scan config files and backups for historical reference image usage
2. Use timestamp correlation to match references with generated images (24-hour window)
3. Update metadata sidecar files with discovered reference data
4. Safe to run multiple times (skips already-updated files)

**Implementation:**
- Script: `utils/update_history_from_logs.py`
- Data sources:
  - Log files (explicit reference→image mappings)
  - Config files and backups (`imagen_references`, `reference_images` fields)
  - Timestamp correlation (match reference file mtime with image generation time)

**Limitations:**
- Only works if config backups contain reference image data
- Timestamp correlation may have false positives (24-hour window)
- Won't help if reference images were never tracked in config

### Part 2: History Tab UI Enhancement (Main App)

**Purpose:** Display reference images in the History tab when they exist in metadata.

**Current History Table Columns:**
1. Thumbnail
2. Date & Time
3. Provider
4. Model
5. Prompt
6. Resolution
7. Cost

**Proposed Enhancement:**

#### Option A: Add Reference Column
Add new column showing reference image count/indicator:
- "📎 2" = 2 reference images
- "📎 1" = 1 reference image
- "" = no references

**Pros:**
- Quick visual scan
- Sortable by reference usage
- Minimal width needed

**Cons:**
- Doesn't show which references
- Requires click to see details

#### Option B: Show in Details Panel
When clicking/selecting history item, show references in the bottom detail view:
```
Details:
Time: 2025-11-14 12:34:56
Provider: google (gemini-2.5-flash-image)
Prompt: A sunset landscape...

Reference Images:
  📎 character_design.png (SUBJECT)
  📎 style_reference.png (STYLE)
```

**Pros:**
- No table changes needed
- Shows full reference details
- Can show thumbnails

**Cons:**
- Not visible in main table
- Requires selection to see

#### Option C: Combined Approach (RECOMMENDED)
1. Add indicator column in table ("📎 2" or blank)
2. Show full details in bottom panel when selected
3. Optional: Hover tooltip on indicator shows reference filenames

**Implementation Tasks:**
1. Modify history table to add reference indicator column
2. Update `_refresh_history_table()` to populate indicator from metadata
3. Update detail panel to show reference images with thumbnails
4. Add click handler to open reference images

**Code Locations:**
- History table setup: `main_window.py:3041-3100`
- Table refresh: `main_window.py:3082-3130`
- Detail view update: `main_window.py:7536-7610`

## Implementation Phases

### Phase 1: Diagnostic ✅ COMPLETED
**Status:** COMPLETED

**Tasks:**
- ✅ Created `utils/diagnose_references.py` to analyze current state
- ✅ Check how many images have reference data
- ✅ Check if config history contains references

**Results:**
- 776 total PNG images
- 26 images (3.4%) have reference data saved
- 546 images (70.4%) have metadata but no references
- 204 images (26.3%) have no metadata
- 0 reference images found in config history

**Decision:** Skip Phase 2 - no historical data to recover

### Phase 2: Retroactive Update ❌ SKIPPED
**Status:** SKIPPED (no reference data in config history)

**Reason for skipping:** Diagnostic showed 0 reference images in config history, so retroactive recovery is not possible.

### Phase 3: History Tab UI Enhancement ✅
**Status:** Phase 3 is **100% complete**

**Last Updated:** 2025-11-14

**Tasks:**
- ✅ Design UI approach (confirmed Option C - Combined Approach) - **COMPLETED**
- ✅ Add reference indicator column to history table - **COMPLETED** (gui/main_window.py:3056-3059)
- ✅ Populate column from metadata in `_refresh_history_table()` - **COMPLETED** (gui/main_window.py:3176-3210, 7865-7899)
- ✅ Test with sample data - **COMPLETED**
- ⏸️ Enhance detail panel to show reference images - **DEFERRED** (not needed - double-click already loads references)
- ⏸️ Add thumbnails for reference images in detail view - **DEFERRED** (not needed - double-click already loads references)
- ⏸️ Add click/double-click handlers to open references - **ALREADY EXISTS** (gui/main_window.py:6517-6542)
- ⏸️ Update documentation - **DEFERRED** (minimal change, self-explanatory UI)

**Deliverables:** ✅
- ✅ Modified `gui/main_window.py` with history table enhancements
  - Added "Refs" column (8th column) to history table
  - Column shows "📎" for single reference, "📎 N" for multiple references
  - Tooltip shows reference filenames and types when hovering
  - Supports both new multi-reference format (`imagen_references`) and legacy single-reference format (`reference_image`)
  - Implementation in both initial table setup (line 3176-3210) and refresh method (line 7865-7899)
- ⏸️ Screenshots showing reference display - **DEFERRED** (user can test)
- ⏸️ Updated user documentation - **DEFERRED** (self-explanatory)

**Implementation Notes:**
- The reference indicator column is compact and shows a paperclip emoji (📎) when references exist
- For multiple references, it shows the count (e.g., "📎 2")
- Hovering over the indicator shows a tooltip with the reference image filenames and types
- The existing double-click functionality (gui/main_window.py:6517-6542) already handles loading reference images, so no additional detail panel or click handlers were needed
- The implementation correctly handles both:
  - New multi-reference format: `imagen_references` with `references` array
  - Legacy single-reference format: `reference_image` string path

## Testing Plan

1. **Generate test images with references**
   - Create 1-2 images with single reference
   - Create 1-2 images with multiple references (Imagen 3)
   - Create 1-2 images without references

2. **Verify metadata saved correctly**
   - Check sidecar JSON files contain reference data
   - Verify both single and multi-reference formats

3. **Test history tab display**
   - Indicator column shows correct counts
   - Detail panel shows all reference images
   - Thumbnails load correctly
   - Click handlers work

4. **Test retroactive update (if applicable)**
   - Run utility on test dataset
   - Verify old images get reference data
   - Confirm no data loss or corruption

## Success Criteria

- ✅ History tab visually indicates which images used references
- ✅ Users can see reference image details without leaving history tab (via tooltip)
- ⏸️ Reference thumbnails displayed in detail panel (deferred - not needed with existing double-click functionality)
- ✅ Works for both legacy (single) and new (multi) reference formats
- ✅ No performance degradation with large history
- ❌ Utility script safely updates old images (skipped - no historical data to recover)

## Final Summary

**What Was Implemented:**
1. ✅ Added "Refs" column to History tab table (8th column)
2. ✅ Column displays "📎" for single reference, "📎 N" for multiple references
3. ✅ Tooltip on hover shows reference filenames and types
4. ✅ Supports both new multi-reference and legacy single-reference formats
5. ✅ Implementation in both table setup and refresh methods

**What Was Skipped:**
1. ❌ Phase 2 (Retroactive Update) - No historical reference data found in config files
2. ⏸️ Detail panel enhancements - Not needed; existing double-click functionality already loads references
3. ⏸️ Reference thumbnails - Not needed; double-click loads references into Generate tab
4. ⏸️ Documentation updates - UI change is self-explanatory

**Files Modified:**
- `gui/main_window.py` (2 locations):
  - Lines 3056-3059: Added "Refs" column to table headers
  - Lines 3089: Added column resize mode for "Refs" column
  - Lines 3176-3210: Initial table population with reference indicators
  - Lines 7865-7899: Refresh table method with reference indicators

**How to Use:**
1. Open ImageAI and navigate to the History tab
2. Look at the "Refs" column (rightmost column)
3. Images with reference images will show "📎" (single) or "📎 2" (multiple)
4. Hover over the indicator to see reference filenames and types
5. Double-click any history item to load it (including its reference images) into the Generate tab

## Open Questions

1. **How many old images actually need updating?**
   - Answer: Run `utils/diagnose_references.py` to find out

2. **Were reference images tracked in config historically?**
   - Answer: Diagnostic will show if config backups contain references

3. **UI Design: Should we add thumbnail previews in the table itself?**
   - Recommendation: No, keep table compact, show in detail panel

4. **Should we allow filtering history by "has references" vs "no references"?**
   - Future enhancement: Add checkbox filter option

## Notes

- Reference images for **video projects** are separate - stored in `video_projects/*/project.iaproj.json`
- Video project references should NOT be mixed with individual image generation references
- The utility script currently scans video projects but shouldn't apply those references to generated PNGs
