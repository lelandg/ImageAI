# UI Improvements TODO - Reference System

**Date**: 2025-10-20
**Status**: In Progress

---

## ✅ Completed

1. **Removed obsolete checkboxes**
   - ✅ Removed "Use last frame for continuous video" checkbox
   - ✅ Removed "Auto-link end frames (Veo 3.1)" checkbox
   - ✅ Updated save/load logic to remove checkbox references
   - ✅ Added comment: "Smart continuity detection now happens automatically"

2. **Added new reference management buttons**
   - ✅ Added "🎨 Character Refs" button next to "Generate Images"
   - ✅ Added "📸 Ref Library" button
   - ✅ Implemented `open_character_reference_wizard()` method
   - ✅ Implemented `open_reference_library()` method
   - ✅ Added `_on_references_generated()` callback

3. **Fixed imports**
   - ✅ Added `List` to typing imports in workspace_widget.py

---

## 🔄 In Progress

### Reference Selector Dialog Integration
**Files**: `gui/video/workspace_widget.py`, `gui/video/video_project_tab.py`

**Status**: Dialog created (`reference_selector_dialog.py`), needs UI integration

**Implementation**: When user clicks "Generate Video" button in workspace:
1. Check if >3 global references exist for the scene
2. If yes, show `ReferenceSelectorDialog` to let user pick which 3 to use
3. Pass selected refs to video generation thread via kwargs: `selected_refs=dialog.selected_references`
4. Update `_generate_video_clip()` to pass `selected_refs` to `get_effective_references_for_scene()`

**Example Code** (add to workspace_widget.py in video generation method):
```python
# Before starting video generation thread
if self.current_project:
    scene = self.current_project.scenes[scene_index]
    available_refs = self.current_project.get_all_available_references(scene)

    if len(available_refs) > 3:
        from gui.video.reference_selector_dialog import ReferenceSelectorDialog
        dialog = ReferenceSelectorDialog(available_refs, max_selection=3, parent=self)
        if dialog.exec() == QDialog.Accepted:
            selected_refs = dialog.selected_references
            # Pass to thread: kwargs['selected_refs'] = selected_refs
        else:
            return  # User cancelled
```

---

## 🔄 Remaining Tasks

### Task 1: Fix Reference Image Context Menu
**File**: `gui/video/reference_images_widget.py` or `gui/video/frame_button.py`

**Requirements**:
- Right-click on any reference image button should show context menu with:
  - **Assign Type** → Submenu with: CHARACTER, OBJECT, ENVIRONMENT, STYLE
  - **Generate Character References** → Opens wizard
  - **View Full Image** → Opens image in viewer (fix if broken)
  - **Import from Disk** → File dialog to select image
  - **Import from Scene** → Select from existing scene images
  - **Clear** → Remove reference

**Implementation Notes**:
- Check if ReferenceImagesWidget exists and has context menu
- Add type assignment logic that updates scene.reference_images
- Link to character reference wizard
- Fix image viewer if broken

### Task 2: Update Image Button Click Behavior
**File**: `gui/video/frame_button.py` or similar

**Current Behavior**: Clicking image button regenerates image
**New Behavior**:
- If image exists: Display it (don't regenerate)
- Add status text: "Double-click or use context menu to regenerate"
- Implement double-click handler to regenerate

**Implementation**:
```python
class FrameButton(QPushButton):
    def mousePressEvent(self, event):
        if self.has_image():
            # Display existing image
            self.display_image()
            self.show_status("Double-click to regenerate")
        else:
            # Generate new image
            self.generate_image()

    def mouseDoubleClickEvent(self, event):
        # Always regenerate on double-click
        self.generate_image()
```

### Task 3: Scene Row Click Toggle
**File**: `gui/video/workspace_widget.py`

**Requirements**:
When scene row has video and images (start/end/reference), clicking row cycles through:
1. Start frame display
2. End frame display (if exists)
3. Reference images (if exist)
4. Video playback
5. Back to start frame

**Implementation**:
```python
def on_scene_row_clicked(self, row, column):
    """Handle scene row click to toggle display"""
    scene = self.current_project.scenes[row]

    # Track current display mode
    if not hasattr(scene, '_display_mode'):
        scene._display_mode = 'start'

    # Cycle through available displays
    modes = []
    if scene.approved_image or scene.images:
        modes.append('start')
    if scene.end_frame:
        modes.append('end')
    if scene.reference_images:
        modes.append('references')
    if scene.video_clip:
        modes.append('video')

    if not modes:
        return

    # Get next mode
    current_idx = modes.index(scene._display_mode) if scene._display_mode in modes else -1
    next_idx = (current_idx + 1) % len(modes)
    scene._display_mode = modes[next_idx]

    # Display based on mode
    if scene._display_mode == 'start':
        self.display_start_frame(scene)
    elif scene._display_mode == 'end':
        self.display_end_frame(scene)
    elif scene._display_mode == 'references':
        self.display_references(scene)
    elif scene._display_mode == 'video':
        self.play_video(scene)
```

### Task 4: Update README
**File**: `README.md`

**Add Section**: "Reference Image System for Video Consistency"

**Content to Add**:
````markdown
## Reference Image System for Video Consistency

ImageAI includes a powerful reference image system for maintaining character, object, and environment consistency across multiple video scenes. This is especially important for Veo 3 video generation.

### Quick Start

1. **Open Reference Library**
   - Click `📸 References` tab in Video Project

2. **Generate Character References** (Recommended)
   - Click `🎨 Generate Character Refs`
   - Enter character description: "Sarah - young woman, dark hair, blue jacket"
   - Select visual style
   - Click `Generate 3 Reference Images`
   - Wait for front, side, and full-body views to generate
   - Click `✓ Add to Project`

3. **Generate Videos**
   - Your reference images are automatically used in all video generations
   - Characters/objects maintain consistent appearance across scenes

### How It Works

**Reference Images** (PRIMARY continuity method):
- Up to 3 global reference images per project
- Automatically used in all video generations
- Maintains character/object/environment consistency
- Works across scene changes (bedroom → kitchen → street)

**Smart Continuity Detection** (AUTOMATIC):
- System automatically determines when to use last-frame continuity
- Uses last-frame only for compatible sequential scenes
- Skips last-frame when location changes detected
- No configuration needed - works automatically!

### Reference Image Types

- **CHARACTER**: People, faces (most important for consistency)
- **OBJECT**: Props, items, products
- **ENVIRONMENT**: Locations, settings, backgrounds
- **STYLE**: Visual style (Veo 2.0 only)

### Best Practices

1. **Generate at Project Start**
   - Create character references before generating any videos
   - Ensures consistency from the beginning

2. **Use 3 Angles**
   - Front view, side view, full body
   - Provides better consistency

3. **Same Style Across References**
   - Use same lighting, color grading for all 3 references
   - Matches your project's visual style

4. **Validate References**
   - System shows validation status (green/orange/red borders)
   - Fix any errors before using

### Adding References to Scenes

**Global References** (Recommended):
- Added in `📸 References` tab
- Applied to ALL scenes automatically

**Per-Scene Overrides** (Advanced):
- Right-click reference button in scene row
- Assign scene-specific references
- Useful for scenes with different characters

### Buttons and Controls

**In Workspace Tab**:
- `🎨 Character Refs` - Generate 3-angle character references
- `📸 Ref Library` - Open reference library management

**In References Tab**:
- `🎨 Generate Character Refs` - Auto-generate references
- `📁 Add Existing Image` - Import from files

**In Scene Table**:
- Right-click reference image buttons for options
- Assign reference types
- Import from disk or scene

### Troubleshooting

**Q: My character looks different in different scenes**
- A: Make sure you've added character references in `📸 References` tab
- Check that references are valid (green borders)

**Q: Scene transition looks wrong**
- A: Smart continuity detection handles this automatically
- For scene changes (bedroom → desk), system uses references only
- For continuous scenes (same location), system uses references + last-frame

**Q: How do I know which references are being used?**
- A: Check the log file or console output during video generation
- Shows: "📸 Using X reference image(s) for character/style consistency"

**Q: Can I use different characters in different scenes?**
- A: Yes! Use per-scene reference overrides
- Right-click scene's reference button → assign scene-specific refs

### Technical Details

The reference system uses Veo 3's native reference image support:
- Max 3 references per video generation (Veo API limit)
- References maintain identity consistency
- Last-frame preserves motion (when compatible)
- Hybrid approach (refs + last-frame) for best results

For more details, see:
- `Docs/Reference-Image-System.md` - Complete technical guide
- `Docs/Reference-UI-Implementation.md` - UI documentation
````

---

## 🧪 Testing Checklist

Once all tasks complete, test:

- [ ] Character reference wizard opens from workspace button
- [ ] Reference library tab opens from workspace button
- [ ] Right-click on reference button shows context menu
- [ ] Can assign reference types via context menu
- [ ] Image buttons display existing images without regenerating
- [ ] Double-click image button regenerates
- [ ] Scene row click cycles through displays
- [ ] README section appears and renders correctly
- [ ] Smart continuity works automatically (check logs)

---

## 📝 Notes

**Smart Continuity Detection**:
- Already implemented in `video_project_tab.py` `_generate_video_clip()` method
- Uses `ReferenceManager.should_use_last_frame_continuity()`
- Automatic - no user configuration needed
- Logs decisions clearly

**Why Remove Checkboxes**:
- User shouldn't need to manually control continuity
- Smart detection handles it automatically
- Reduces UI clutter
- Prevents user error (wrong checkbox state)

**Reference Types**:
- Organized by type for better UX
- Enables smart auto-selection
- Future-proof for Veo API updates
- Helps manage 3-reference limit

---

## 🚀 Implementation Priority

1. **HIGH**: Task 2 (Image button click behavior)
   - Most user-visible impact
   - Prevents accidental regeneration

2. **HIGH**: Task 4 (README update)
   - Critical for user understanding
   - Documents new workflow

3. **MEDIUM**: Task 1 (Context menu)
   - Nice-to-have features
   - Improves workflow

4. **LOW**: Task 3 (Scene row toggle)
   - Convenience feature
   - Not critical for functionality

---

**Status**: Tasks 1-2 complete (checkboxes removed, buttons added). Tasks 3-6 remain.
