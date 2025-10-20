# Reference Image System - UI Implementation

**Date**: 2025-10-20
**Status**: ✅ Complete

---

## Overview

This document describes the UI components created for the Reference Image System, including the reference generation wizard and reference library management panel.

---

## Components Created

### 1. Reference Generation Wizard ✅

**File**: `gui/video/reference_generation_dialog.py` (400+ lines)

**Purpose**: Auto-generate 3-angle character reference images for project-wide consistency.

**Features**:
- Character description input (text area)
- Style preset selector (editable combo box)
- Quality selector
- Auto-generates 3 views:
  - Front view portrait
  - 3/4 side view
  - Full body standing view
- Real-time progress bar and status updates
- Live preview thumbnails (3 slots)
- Validation status for each generated image
- One-click "Add to Project" button
- Auto-closes after adding to project

**UI Layout**:
```
┌─────────────────────────────────────────┐
│ Generate Character References           │
│                                         │
│ Instructions...                         │
│                                         │
│ ┌─ Character Description ─────────────┐│
│ │ [Text area for description]         ││
│ └─────────────────────────────────────┘│
│                                         │
│ ┌─ Style Settings ──────────────────┐  │
│ │ Visual Style: [Combo box]        │  │
│ │ Quality: [Combo box]             │  │
│ └──────────────────────────────────┘  │
│                                         │
│ [🎨 Generate 3 Reference Images]        │
│ [Progress bar] Status message...        │
│                                         │
│ ─ Generated References (Preview) ────   │
│ ┌───────┐ ┌───────┐ ┌───────┐        │
│ │ Front │ │ Side  │ │ Full  │        │
│ │ View  │ │ View  │ │ Body  │        │
│ │[Image]│ │[Image]│ │[Image]│        │
│ │ ✓ OK  │ │ ✓ OK  │ │ ✓ OK  │        │
│ └───────┘ └───────┘ └───────┘        │
│                                         │
│ [✓ Add to Project]  [Close]            │
└─────────────────────────────────────────┘
```

**Classes**:

#### `ReferenceGenerationWorker(QThread)`
- Generates 3 reference images in background thread
- Emits progress updates (0-100%)
- Emits reference_generated for each completed ref
- Emits generation_complete when all done
- Validates each generated image

**Signals**:
- `progress(int, str)` - Progress percent and status message
- `reference_generated(int, str)` - Index (1-3) and file path
- `generation_complete(bool, str)` - Success flag and message

#### `ReferenceGenerationDialog(QDialog)`
- Main dialog window
- Manages worker thread
- Updates UI with generation results
- Adds references to project

**Signals**:
- `references_generated(list)` - List of generated Path objects

**Methods**:
- `start_generation()` - Start generation process
- `on_progress(int, str)` - Handle progress update
- `on_reference_generated(int, str)` - Handle single ref complete
- `on_generation_complete(bool, str)` - Handle all complete
- `add_to_project()` - Add generated refs to project

---

### 2. Reference Library Widget ✅

**File**: `gui/video/reference_library_widget.py` (550+ lines)

**Purpose**: Display and manage global reference images for the project.

**Features**:
- Grid display of all global references (max 3)
- Add existing image button
- Generate character refs button (opens wizard)
- Per-reference actions:
  - Remove
  - Edit (type, name, description)
  - Context menu
- Visual validation indicators:
  - Green border: Valid reference
  - Orange border: Valid with warnings
  - Red border: Invalid reference
- Type badges (colored):
  - CHARACTER (green)
  - OBJECT (blue)
  - ENVIRONMENT (orange)
  - STYLE (purple)
- Validation status below each image
- Empty state message when no references
- Auto-disables add buttons when max (3) reached

**UI Layout**:
```
┌───────────────────────────────────────────────────────┐
│ 📸 Reference Library                    (2/3)         │
│ [🎨 Generate Character Refs] [📁 Add Existing Image]  │
│                                                       │
│ Reference images maintain character/object/...       │
│                                                       │
│ ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│ │CHARACTER ✕│  │OBJECT   ✕│  │[Empty]   │           │
│ │          │  │          │  │          │           │
│ │ [Image]  │  │ [Image]  │  │  Add     │           │
│ │          │  │          │  │  Image   │           │
│ │ Sarah    │  │ Car      │  │          │           │
│ │ Ref 1/3  │  │ Vintage  │  │          │           │
│ │ ✓ Valid  │  │ ⚠ Warning│  │          │           │
│ └──────────┘  └──────────┘  └──────────┘           │
└───────────────────────────────────────────────────────┘
```

**Classes**:

#### `ReferenceCard(QFrame)`
- Card widget for displaying a single reference
- Shows thumbnail preview (180×180px)
- Type badge (colored)
- Name and description
- Validation status
- Remove button (✕)
- Context menu for edit/remove

**Signals**:
- `remove_clicked(ReferenceImage)` - Remove button clicked
- `edit_clicked(ReferenceImage)` - Edit requested

**Methods**:
- `update_validation_status()` - Update validation display
- `update_validation_border()` - Update border color
- `_get_type_color()` - Get badge color for type
- `contextMenuEvent()` - Show context menu

#### `ReferenceLibraryWidget(QWidget)`
- Main library management widget
- Grid layout for reference cards
- Add/generate buttons
- Empty state handling

**Signals**:
- `references_changed()` - References added/removed/edited

**Methods**:
- `set_project(VideoProject)` - Set current project
- `refresh()` - Rebuild UI from project data
- `on_generate_clicked()` - Open generation wizard
- `on_add_existing_clicked()` - Add existing image
- `on_remove_reference(ReferenceImage)` - Remove reference
- `on_edit_reference(ReferenceImage)` - Edit reference details
- `on_references_generated(List[Path])` - Handle wizard completion

---

### 3. Integration into VideoProjectTab ✅

**File**: `gui/video/video_project_tab.py` (UPDATED)

**Changes**:

#### Added New Tab
```python
# Create reference library tab
from gui.video.reference_library_widget import ReferenceLibraryWidget
self.reference_library_widget = ReferenceLibraryWidget(self, None)
self.reference_library_widget.references_changed.connect(self.on_references_changed)
self.tab_widget.addTab(self.reference_library_widget, "📸 References")
```

**Tab Structure**:
```
┌─────────────────────────────────────┐
│ [Workspace] [History] [📸 References]│
│                                     │
│ ← New References tab added here     │
│                                     │
└─────────────────────────────────────┘
```

#### Updated on_project_changed()
```python
def on_project_changed(self, project: VideoProject):
    """Handle project change from workspace"""
    self.current_project = project
    # Update history tab with new project
    if project and hasattr(project, 'id'):
        self.history_widget.set_project(project.id)
    # Update reference library with new project  ← NEW
    if hasattr(self, 'reference_library_widget'):
        self.reference_library_widget.set_project(project)
```

#### Added on_references_changed()
```python
def on_references_changed(self):
    """Handle reference library changes"""
    # Refresh workspace if it needs to update
    if hasattr(self.workspace_widget, 'refresh_references'):
        self.workspace_widget.refresh_references()
    self.logger.info("Reference library updated")
```

#### Added generate_reference_image_sync()
```python
def generate_reference_image_sync(
    self,
    prompt: str,
    output_dir: Path,
    filename_prefix: str
) -> Optional[Path]:
    """
    Generate a reference image synchronously for the reference generation wizard.

    Uses workspace image provider to generate images.
    Returns path to generated image or None.
    """
    # Implementation uses self.workspace_widget.image_provider
    # Generates 1:1 square images for references
    # Returns Path or None
```

---

## User Workflows

### Workflow 1: Generate Character References (Recommended)

1. User opens project
2. User clicks **📸 References** tab
3. User clicks **🎨 Generate Character Refs** button
4. Dialog opens
5. User enters character description:
   ```
   Sarah - young woman, 25, long dark hair, green eyes, blue jacket
   ```
6. User selects style: `cinematic lighting, high detail, photorealistic`
7. User clicks **🎨 Generate 3 Reference Images**
8. Progress bar shows generation progress
9. Preview thumbnails update as each image completes
10. Validation status shows ✓ or errors
11. User clicks **✓ Add to Project as Global References**
12. Dialog closes automatically
13. References appear in Reference Library
14. **All subsequent video generations will use these references!**

### Workflow 2: Add Existing Image

1. User clicks **📁 Add Existing Image**
2. File dialog opens
3. User selects PNG or JPEG image
4. System validates image:
   - Checks resolution (≥720p)
   - Checks format
   - Checks file size
5. If warnings, user confirms
6. Dialog asks for details:
   - Type: CHARACTER / OBJECT / ENVIRONMENT / STYLE
   - Name: "Sarah"
   - Description: "Main character reference"
7. User clicks OK
8. Reference added to library
9. Card appears in grid with validation status

### Workflow 3: Edit Reference

1. User right-clicks reference card
2. Context menu opens
3. User clicks "Edit Info"
4. Dialog opens with current values
5. User changes:
   - Type
   - Name
   - Description
6. User clicks OK
7. Card updates with new info
8. Project auto-saves

### Workflow 4: Remove Reference

1. User clicks ✕ button on card
   OR right-clicks and selects "Remove"
2. Confirmation dialog appears
3. User clicks Yes
4. Card removed from grid
5. Project auto-saves
6. Add buttons re-enable if < 3 refs

---

## Validation Features

### Reference Card Validation

**Visual Indicators**:
- **Border Color**:
  - Green: ✓ Valid, no issues
  - Orange: ⚠ Valid with warnings
  - Red: ✗ Invalid, has errors

- **Status Text**:
  - `✓ Valid (1920×1080)` - All good
  - `⚠ 2 warning(s)` - Hover for details
  - `✗ 3 error(s)` - Hover for details
  - `✗ File not found` - File missing

**Validation Checks**:
1. File exists
2. Resolution ≥ 720p (Veo requirement)
3. Format is PNG or JPEG
4. File size < 50MB
5. Aspect ratio (warns if non-standard)

### Add Image Validation

When adding existing images:
- **Blocking Errors** (prevents adding):
  - File not found
  - Resolution too low (<720p)
  - Invalid format (not PNG/JPEG)

- **Warnings** (user can override):
  - Large file size (>50MB)
  - Non-standard aspect ratio
  - Low quality

---

## Integration with Video Generation

### Automatic Usage

Once references are added to the project, they are **automatically used** in video generation:

```python
# In _generate_video_clip() (video_project_tab.py)

# Get effective reference images for this scene
scene_refs = self.project.get_effective_references_for_scene(scene, max_refs=3)
reference_image_paths = [ref.path for ref in scene_refs if ref.path.exists()]

# Configure Veo generation
config = VeoGenerationConfig(
    prompt=scene.video_prompt,
    reference_images=reference_image_paths,  # ← Automatically included!
    duration=scene.duration_sec,
    aspect_ratio=aspect_ratio
)

# Generate video
result = veo_client.generate_video(config)
```

**Result**: All scenes in the project will use the global references automatically for character/style consistency!

---

## Error Handling

### Generation Wizard Errors

**Scenario**: Image generation fails for one or more references

**Handling**:
- Worker continues generating remaining references
- Failed slots show "✗ Not generated" status
- Preview shows "(Failed)" or "(Load failed)"
- User can still add successfully generated refs
- Error logged to console and log file

**Example**:
```
Reference 1: ✓ Generated
Reference 2: ✗ Failed (generation error)
Reference 3: ✓ Generated

Result: 2/3 references available to add
```

### Validation Errors

**Scenario**: User tries to add invalid image

**Handling**:
- Show error dialog with specific issues
- List all validation errors
- Prevent adding to project
- User can select different image

**Example Dialog**:
```
┌─────────────────────────────────────┐
│ Invalid Reference Image             │
│                                     │
│ The selected image does not meet    │
│ Veo 3 requirements:                 │
│                                     │
│ • Resolution too low: 640×480.      │
│   Minimum 720p required.            │
│ • Format not supported: BMP.        │
│   Use PNG or JPEG.                  │
│                                     │
│            [OK]                      │
└─────────────────────────────────────┘
```

### Max References Reached

**Scenario**: User tries to add 4th reference

**Handling**:
- Add buttons disabled
- Count label shows "(3/3)" in orange/bold
- Tooltip explains max reached
- User must remove existing ref first

---

## Keyboard Shortcuts

### Reference Generation Dialog
- **Enter**: (in description) Start generation
- **Escape**: Close dialog

### Reference Library
- **Delete**: (on selected card) Remove reference
- **F2**: (on selected card) Edit reference
- **Right-click**: Show context menu

---

## Styling and Theme

### Color Scheme

**Type Badges**:
- CHARACTER: `#4CAF50` (green)
- OBJECT: `#2196F3` (blue)
- ENVIRONMENT: `#FF9800` (orange)
- STYLE: `#9C27B0` (purple)

**Validation Colors**:
- Valid: `#4CAF50` (green)
- Warning: `#FF9800` (orange)
- Error: `#ff4444` (red)

**Buttons**:
- Generate: Font-weight bold, padding 10px
- Remove: Red background `#ff4444`, circular
- Add to Project: Green, bold

---

## Performance Considerations

### Reference Card Loading

**Optimization**:
- Images loaded at fixed size (180×180px)
- Scaled with `Qt.SmoothTransformation`
- Cached in QPixmap
- Only visible cards loaded (scroll area)

**Memory**:
- Max 3 references = Max 3 thumbnails loaded
- Minimal memory footprint
- Original images not kept in memory

### Generation Worker

**Threading**:
- Runs in separate QThread
- UI remains responsive during generation
- Progress updates every image
- Can be cancelled (user closes dialog)

### Validation

**Lazy Validation**:
- Only validates when:
  - Card first displayed
  - User explicitly validates
  - Image added to project
- Results cached until file changes

---

## Testing

### Manual Test Cases

#### Test 1: Generate Character References
1. Open project
2. Go to References tab
3. Click "Generate Character Refs"
4. Enter: "Sarah - young woman, dark hair"
5. Select style: "cinematic lighting"
6. Click Generate
7. **Expected**: 3 previews update, all valid
8. Click "Add to Project"
9. **Expected**: Dialog closes, 3 cards appear in library

#### Test 2: Add Existing Image
1. Click "Add Existing Image"
2. Select valid PNG (1920×1080)
3. **Expected**: No errors
4. Set Type: CHARACTER, Name: "John"
5. Click OK
6. **Expected**: Card appears with valid status

#### Test 3: Validation - Invalid Image
1. Click "Add Existing Image"
2. Select small JPEG (640×480)
3. **Expected**: Error dialog shows resolution too low
4. Click OK on error
5. **Expected**: Image not added, can try again

#### Test 4: Max References
1. Add 3 references (any method)
2. **Expected**: Count shows "(3/3)" in orange
3. **Expected**: Add buttons disabled
4. **Expected**: Tooltips explain max reached
5. Remove one reference
6. **Expected**: Buttons re-enable, count shows "(2/3)"

#### Test 5: Edit Reference
1. Right-click reference card
2. Click "Edit Info"
3. Change name to "Main Character"
4. Change type to OBJECT
5. Click OK
6. **Expected**: Card updates, badge changes color

#### Test 6: Remove Reference
1. Click ✕ button on card
2. **Expected**: Confirmation dialog
3. Click Yes
4. **Expected**: Card removed, project saved

---

## Files Modified/Created

### New Files
1. **`gui/video/reference_generation_dialog.py`** (400 lines)
   - ReferenceGenerationWorker class
   - ReferenceGenerationDialog class

2. **`gui/video/reference_library_widget.py`** (550 lines)
   - ReferenceCard class
   - ReferenceLibraryWidget class

3. **`Docs/Reference-UI-Implementation.md`** (This file)

### Modified Files
1. **`gui/video/video_project_tab.py`**
   - Added reference library tab
   - Added on_references_changed() method
   - Added generate_reference_image_sync() method
   - Updated on_project_changed() to sync reference library

---

## Future Enhancements

### Potential Improvements

1. **Drag-and-Drop**
   - Drag images from file system to library
   - Reorder references by dragging

2. **Batch Generation**
   - Generate multiple character sets
   - Save reference templates

3. **Reference Preview in Workspace**
   - Show active references for current scene
   - Hover tooltip in storyboard

4. **Reference Collections**
   - Save/load reference sets
   - Switch between different character sets
   - "Character A", "Character B", etc.

5. **Smart Suggestions**
   - Analyze scene prompts
   - Suggest relevant references
   - Auto-tag references by prompt keywords

6. **Reference History**
   - Track which references used for each scene
   - "Used in 5 scenes" badge
   - Warn before removing heavily-used refs

---

## Summary

**Status**: ✅ UI Integration Complete

**Components Delivered**:
- ✅ Reference Generation Wizard (auto-generate 3 refs)
- ✅ Reference Library Widget (manage global refs)
- ✅ Integration into VideoProjectTab (new tab)
- ✅ Validation system with visual indicators
- ✅ Edit/remove functionality
- ✅ Add existing image support

**Ready to Use**: Yes! Users can now:
1. Generate character references automatically
2. Add/edit/remove references via GUI
3. See validation status visually
4. References automatically used in video generation

**Next Steps**: Test with real projects and gather user feedback!

