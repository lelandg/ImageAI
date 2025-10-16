# Veo 3.1 Table Refactor - Implementation Specification

**Status**: Ready for Implementation
**Created**: 2025-10-16
**Target File**: `gui/video/workspace_widget.py`

## Overview

Refactor scene table from 14 columns to 10 optimized columns with integrated PromptFieldWidget (text + ✨ LLM + ↶↷ undo/redo) for all prompt fields.

---

## ✅ Completed Prerequisites

- [x] Create PromptHistory class (core/video/project.py:79-144)
- [x] Create PromptFieldWidget (gui/video/prompt_field_widget.py)
- [x] Create FrameButton widget (gui/video/frame_button.py)
- [x] Create EndPromptDialog (gui/video/end_prompt_dialog.py)
- [x] Update table to 10 columns (workspace_widget.py:1027)
- [x] Update column widths (workspace_widget.py:1060-1069)
- [x] Add PromptFieldWidget import (workspace_widget.py:35)

---

## 📋 Implementation Checklist

### Phase 1: Create LLM Dialog for Start Prompts

**File**: `gui/video/start_prompt_dialog.py` (NEW)

**Specification**:
```python
class StartPromptDialog(QDialog):
    """
    Dialog for generating start prompts using LLM.

    Similar to EndPromptDialog but for start frame descriptions.
    Shows: source text, current prompt (if any), generates enhanced prompt.
    """

    def __init__(self, generator, source: str, current_prompt: str,
                 provider: str, model: str, parent=None):
        # generator: Can reuse EndPromptGenerator or create StartPromptGenerator
        # source: The original lyric/text line
        # current_prompt: Existing prompt (for regeneration)
        # provider/model: LLM settings
        pass

    def get_prompt(self) -> str:
        """Returns the generated/edited prompt"""
        pass
```

**UI Layout**:
- Title: "Generate Start Frame Prompt with LLM"
- Source text display (read-only QTextEdit, max height 80px)
- Current prompt display (read-only QTextEdit, max height 80px) - show if exists
- Generated prompt edit (QTextEdit, editable, min height 120px)
- Progress bar (indeterminate, hidden when not generating)
- Regenerate button (🔄)
- OK/Cancel buttons

**LLM System Prompt**:
```
You are an AI image prompt specialist. Create a detailed, vivid description for generating a single image frame.

The user provides a text line (lyric, narration, or scene description). Generate a comprehensive prompt that:
- Captures the mood, setting, and key visual elements
- Is 1-2 sentences describing what should be visible in the frame
- Focuses on composition, lighting, color palette, and atmosphere
- Is specific and concrete (avoid vague or abstract language)

Format: 1-2 sentences describing the visual scene.
```

**User Prompt Format**:
```
Create an image prompt from this text:

Source: "{source}"
Current prompt: "{current_prompt}" (if exists, otherwise "None - generate new")

Generate a detailed visual description suitable for AI image generation.
```

**Thread Safety**: Use QThread for generation (same pattern as EndPromptDialog)

---

### Phase 2: Create LLM Dialog for Video Prompts

**File**: `gui/video/video_prompt_dialog.py` (NEW)

**Specification**:
```python
class VideoPromptDialog(QDialog):
    """
    Dialog for generating video prompts using LLM.

    Takes start frame prompt and generates motion/camera instructions for Veo.
    Shows: start prompt, duration, generates video-optimized prompt.
    """

    def __init__(self, generator, start_prompt: str,
                 duration: float, provider: str, model: str, parent=None):
        # start_prompt: The start frame description
        # duration: Scene duration in seconds
        pass

    def get_prompt(self) -> str:
        """Returns the generated/edited video prompt"""
        pass
```

**UI Layout**:
- Title: "Generate Video Prompt with LLM"
- Start prompt display (read-only QTextEdit, max height 80px)
- Duration display (read-only label: "Duration: X.Xs")
- Generated video prompt edit (QTextEdit, editable, min height 120px)
- Progress bar (indeterminate)
- Regenerate button (🔄)
- OK/Cancel buttons

**LLM System Prompt**:
```
You are a video motion specialist. Given a static image description, generate a video prompt that describes camera movement and action.

The video prompt should:
- Start with the static scene description
- Add camera movement (pan, zoom, dolly, tilt, etc.)
- Add subtle motion or changes over time
- Be optimized for Google Veo video generation
- Be 2-3 sentences maximum

Format: [Static scene], [camera movement], [motion/changes]
```

**User Prompt Format**:
```
Create a video motion prompt:

Start frame: "{start_prompt}"
Duration: {duration} seconds

Generate a prompt describing camera movement and scene evolution for Veo video generation.
```

---

### Phase 3: Rewrite populate_scene_table()

**Location**: workspace_widget.py, line ~1953

**Current Issues**:
- 14 columns (too many)
- Separate buttons for generate/enhance/undo
- No integrated undo/redo
- End prompt column has stub widget

**New 10-Column Layout**:

| Col | Header | Widget Type | Width | Notes |
|-----|--------|-------------|-------|-------|
| 0 | # | QTableWidgetItem (text) | 35px | Scene number |
| 1 | Start Frame | FrameButton | 70px | All start frame operations |
| 2 | Source | QTableWidgetItem (text) | 120px | Original text/lyric |
| 3 | Start Prompt | PromptFieldWidget | 360px | Text + ✨ + ↶↷ |
| 4 | End Prompt | PromptFieldWidget | 360px | Text + ✨ + ↶↷ |
| 5 | End Frame | FrameButton | 70px | All end frame operations |
| 6 | 🎬 | QPushButton | 40px | Video generation |
| 7 | Time | QTableWidgetItem (text) | 45px | Duration |
| 8 | Video Prompt | PromptFieldWidget | 360px | Text + ✨ + ↶↷ |
| 9 | ⤵️ | QPushButton | 40px | Wrap toggle |

**Implementation Steps**:

#### Step 3.1: Column 0 - Scene Number
```python
# Column 0: Scene # (unchanged)
scene_num_item = QTableWidgetItem(str(i + 1))
scene_num_item.setTextAlignment(Qt.AlignCenter)
self.scene_table.setItem(i, 0, scene_num_item)
```

#### Step 3.2: Column 1 - Start Frame (FrameButton)
```python
# Column 1: Start Frame (FrameButton widget)
start_frame_btn = FrameButton(frame_type="start", parent=self)
start_frame_path = scene.approved_image or (scene.images[0].path if scene.images else None)
if start_frame_path:
    start_frame_btn.set_frame(start_frame_path, auto_linked=False)

# Connect ALL frame operations through FrameButton's built-in signals
start_frame_btn.generate_requested.connect(lambda idx=i: self.generate_single_scene(idx))
start_frame_btn.view_requested.connect(lambda idx=i: self._view_start_frame(idx))
start_frame_btn.select_requested.connect(lambda idx=i: self._select_start_frame_variant(idx))
start_frame_btn.clear_requested.connect(lambda idx=i: self._clear_start_frame(idx))

self.scene_table.setCellWidget(i, 1, start_frame_btn)
```

#### Step 3.3: Column 2 - Source Text
```python
# Column 2: Source text (unchanged)
source_item = QTableWidgetItem(scene.source[:50] if scene.source else "")
source_item.setToolTip(scene.source if scene.source else "")
self.scene_table.setItem(i, 2, source_item)
```

#### Step 3.4: Column 3 - Start Prompt (PromptFieldWidget)
```python
# Column 3: Start Prompt (PromptFieldWidget with LLM + undo/redo)
start_prompt_widget = PromptFieldWidget(
    placeholder="Click ✨ to generate start frame prompt",
    parent=self
)
start_prompt_widget.set_text(scene.prompt)

# Connect text changes to auto-save
start_prompt_widget.text_changed.connect(
    lambda text, idx=i: self._on_start_prompt_changed(idx, text)
)

# Connect LLM button to dialog
start_prompt_widget.llm_requested.connect(
    lambda idx=i: self._show_start_prompt_llm_dialog(idx)
)

# Store widget reference for later retrieval (optional, for history persistence)
# You might want: self._start_prompt_widgets[i] = start_prompt_widget

self.scene_table.setCellWidget(i, 3, start_prompt_widget)
```

#### Step 3.5: Column 4 - End Prompt (PromptFieldWidget)
```python
# Column 4: End Prompt (PromptFieldWidget with LLM + undo/redo)
end_prompt_widget = PromptFieldWidget(
    placeholder="Optional: click ✨ for end frame prompt",
    parent=self
)
end_prompt_widget.set_text(scene.end_prompt)

# Connect text changes to auto-save
end_prompt_widget.text_changed.connect(
    lambda text, idx=i: self._on_end_prompt_changed(idx, text)
)

# Connect LLM button to dialog
end_prompt_widget.llm_requested.connect(
    lambda idx=i: self._show_end_prompt_llm_dialog(idx)
)

self.scene_table.setCellWidget(i, 4, end_prompt_widget)
```

#### Step 3.6: Column 5 - End Frame (FrameButton)
```python
# Column 5: End Frame (FrameButton widget)
end_frame_btn = FrameButton(frame_type="end", parent=self)
is_auto_linked = scene.end_frame_auto_linked
end_frame_path = scene.end_frame
if end_frame_path:
    end_frame_btn.set_frame(end_frame_path, auto_linked=is_auto_linked)

# Connect ALL end frame operations through FrameButton
end_frame_btn.generate_requested.connect(lambda idx=i: self._generate_end_frame(idx))
end_frame_btn.view_requested.connect(lambda idx=i: self._view_end_frame(idx))
end_frame_btn.select_requested.connect(lambda idx=i: self._select_end_frame_variant(idx))
end_frame_btn.clear_requested.connect(lambda idx=i: self._clear_end_frame(idx))
end_frame_btn.auto_link_requested.connect(lambda idx=i: self._auto_link_end_frame(idx))

self.scene_table.setCellWidget(i, 5, end_frame_btn)
```

#### Step 3.7: Column 6 - Video Button
```python
# Column 6: Video button (🎬)
video_btn = QPushButton("🎬")
has_video_prompt = bool(hasattr(scene, 'video_prompt') and scene.video_prompt and len(scene.video_prompt) > 0)

if has_video_prompt:
    if scene.uses_veo_31():
        video_btn.setToolTip("Generate video clip (Veo 3.1: start → end transition)")
    else:
        video_btn.setToolTip("Generate video clip (Veo 3: single-frame animation)")
else:
    video_btn.setToolTip("Generate video prompt first (✨ in Video Prompt column)")

video_btn.setMaximumWidth(40)
video_btn.setStyleSheet("QPushButton { padding: 0px; margin: 0px; }")
video_btn.setEnabled(has_video_prompt)
video_btn.clicked.connect(lambda checked, idx=i: self.generate_video_clip(idx))
self.scene_table.setCellWidget(i, 6, video_btn)
```

#### Step 3.8: Column 7 - Time
```python
# Column 7: Time (narrowed, no 's' suffix)
time_item = QTableWidgetItem(f"{scene.duration_sec:.1f}")
time_item.setToolTip(f"Duration: {scene.duration_sec:.1f} seconds")
time_item.setTextAlignment(Qt.AlignCenter)
self.scene_table.setItem(i, 7, time_item)
```

#### Step 3.9: Column 8 - Video Prompt (PromptFieldWidget)
```python
# Column 8: Video Prompt (PromptFieldWidget with LLM + undo/redo)
video_prompt_widget = PromptFieldWidget(
    placeholder="Click ✨ to generate video motion prompt",
    parent=self
)
video_prompt_widget.set_text(scene.video_prompt if hasattr(scene, 'video_prompt') else "")

# Connect text changes to auto-save
video_prompt_widget.text_changed.connect(
    lambda text, idx=i: self._on_video_prompt_changed(idx, text)
)

# Connect LLM button to dialog
video_prompt_widget.llm_requested.connect(
    lambda idx=i: self._show_video_prompt_llm_dialog(idx)
)

self.scene_table.setCellWidget(i, 8, video_prompt_widget)
```

#### Step 3.10: Column 9 - Wrap Button
```python
# Column 9: Wrap button (⤵️)
wrap_btn = QPushButton("⤵️")
wrap_btn.setToolTip("Toggle text wrapping for this row")
wrap_btn.setMaximumWidth(40)
wrap_btn.setStyleSheet("QPushButton { padding: 0px; margin: 0px; }")
wrap_btn.setCheckable(True)

# Check if row is already wrapped (from metadata or previous state)
is_wrapped = scene.metadata.get('wrapped', False)
wrap_btn.setChecked(is_wrapped)

# Connect to toggle handler
wrap_btn.clicked.connect(lambda checked, idx=i: self._toggle_row_wrap(idx, checked))
self.scene_table.setCellWidget(i, 9, wrap_btn)

# Apply initial wrap state
if is_wrapped:
    self._apply_row_wrap(i, True)
```

---

### Phase 4: Add New Handler Methods

**Location**: After existing frame interaction methods (~line 2850)

#### Method 4.1: _on_start_prompt_changed
```python
def _on_start_prompt_changed(self, scene_index: int, text: str):
    """Handle start prompt text change"""
    if not self.current_project or scene_index >= len(self.current_project.scenes):
        return

    scene = self.current_project.scenes[scene_index]
    scene.prompt = text.strip()
    self.save_project()
```

#### Method 4.2: _show_start_prompt_llm_dialog
```python
def _show_start_prompt_llm_dialog(self, scene_index: int):
    """Show LLM dialog for generating start prompt"""
    if not self.current_project or scene_index >= len(self.current_project.scenes):
        return

    scene = self.current_project.scenes[scene_index]

    if not scene.source:
        from gui.common.dialog_manager import get_dialog_manager
        dialog_manager = get_dialog_manager(self)
        dialog_manager.show_warning("No Source Text", "Please enter source text first.")
        return

    # Get LLM provider/model
    llm_provider = self.llm_provider_combo.currentText().lower()
    llm_model = self.llm_model_combo.currentText()

    # Create generator (can reuse EndPromptGenerator)
    from gui.video.start_prompt_dialog import StartPromptDialog
    generator = EndPromptGenerator(llm_provider=None)  # Will use litellm directly

    # Show dialog
    dialog = StartPromptDialog(
        generator,
        scene.source,
        scene.prompt,
        llm_provider,
        llm_model,
        self
    )

    if dialog.exec_():
        generated_prompt = dialog.get_prompt()
        if generated_prompt:
            # Get widget and update it (with history)
            start_prompt_widget = self.scene_table.cellWidget(scene_index, 3)
            if isinstance(start_prompt_widget, PromptFieldWidget):
                start_prompt_widget.set_text(generated_prompt, add_to_history=True)

            scene.prompt = generated_prompt
            self.save_project()
```

#### Method 4.3: _on_video_prompt_changed
```python
def _on_video_prompt_changed(self, scene_index: int, text: str):
    """Handle video prompt text change"""
    if not self.current_project or scene_index >= len(self.current_project.scenes):
        return

    scene = self.current_project.scenes[scene_index]
    scene.video_prompt = text.strip()
    self.save_project()

    # Update video button enabled state
    video_btn = self.scene_table.cellWidget(scene_index, 6)
    if video_btn:
        video_btn.setEnabled(bool(text.strip()))
```

#### Method 4.4: _show_video_prompt_llm_dialog
```python
def _show_video_prompt_llm_dialog(self, scene_index: int):
    """Show LLM dialog for generating video prompt"""
    if not self.current_project or scene_index >= len(self.current_project.scenes):
        return

    scene = self.current_project.scenes[scene_index]

    if not scene.prompt:
        from gui.common.dialog_manager import get_dialog_manager
        dialog_manager = get_dialog_manager(self)
        dialog_manager.show_warning("No Start Prompt", "Please generate a start prompt first.")
        return

    # Get LLM provider/model
    llm_provider = self.llm_provider_combo.currentText().lower()
    llm_model = self.llm_model_combo.currentText()

    # Create generator
    from gui.video.video_prompt_dialog import VideoPromptDialog
    generator = EndPromptGenerator(llm_provider=None)  # Reuse for simplicity

    # Show dialog
    dialog = VideoPromptDialog(
        generator,
        scene.prompt,
        scene.duration_sec,
        llm_provider,
        llm_model,
        self
    )

    if dialog.exec_():
        generated_prompt = dialog.get_prompt()
        if generated_prompt:
            # Get widget and update it (with history)
            video_prompt_widget = self.scene_table.cellWidget(scene_index, 8)
            if isinstance(video_prompt_widget, PromptFieldWidget):
                video_prompt_widget.set_text(generated_prompt, add_to_history=True)

            scene.video_prompt = generated_prompt
            self.save_project()

            # Enable video button
            video_btn = self.scene_table.cellWidget(scene_index, 6)
            if video_btn:
                video_btn.setEnabled(True)
```

#### Method 4.5: _toggle_row_wrap
```python
def _toggle_row_wrap(self, row_index: int, wrapped: bool):
    """Toggle text wrapping for a row"""
    if not self.current_project or row_index >= len(self.current_project.scenes):
        return

    scene = self.current_project.scenes[row_index]
    scene.metadata['wrapped'] = wrapped

    self._apply_row_wrap(row_index, wrapped)
    self.save_project()
```

#### Method 4.6: _apply_row_wrap
```python
def _apply_row_wrap(self, row_index: int, wrapped: bool):
    """Apply wrap state to all text fields in a row"""
    # For PromptFieldWidget, we need to access the internal QLineEdit
    for col in [3, 4, 8]:  # Start Prompt, End Prompt, Video Prompt
        widget = self.scene_table.cellWidget(row_index, col)
        if isinstance(widget, PromptFieldWidget):
            # Note: PromptFieldWidget uses QLineEdit which doesn't wrap
            # We might need to enhance PromptFieldWidget to support QTextEdit instead
            # For now, this is a placeholder
            pass
```

---

### Phase 5: Update Existing Methods

#### Update 5.1: Remove Old Methods (SAFE TO DELETE)
These methods are no longer needed:
- `_on_enhance_clicked()` - Replaced by LLM button in PromptFieldWidget
- Any column-specific generate buttons - Now handled by FrameButton

#### Update 5.2: Update _on_end_prompt_changed
**Current location**: Line ~2846

**Change from**:
```python
def _on_end_prompt_changed(self, scene_index: int, text: str):
    """Handle end prompt text change"""
    if not self.current_project or scene_index >= len(self.current_project.scenes):
        return

    scene = self.current_project.scenes[scene_index]
    scene.end_prompt = text.strip()
    self.save_project()
```

**To**:
```python
def _on_end_prompt_changed(self, scene_index: int, text: str):
    """Handle end prompt text change"""
    if not self.current_project or scene_index >= len(self.current_project.scenes):
        return

    scene = self.current_project.scenes[scene_index]
    scene.end_prompt = text.strip()
    self.save_project()

    # Note: This method is now called from PromptFieldWidget in column 4
```

---

## 🧪 Testing Checklist

### Basic Functionality
- [ ] Table displays with 10 columns
- [ ] Scene numbers show correctly
- [ ] Start Frame FrameButton shows ➕ when empty, 🖼️ when populated
- [ ] End Frame FrameButton shows ➕ when empty, 🖼️ when populated, 🔗 when auto-linked
- [ ] Source text displays correctly
- [ ] Time column shows duration

### PromptFieldWidget - Start Prompt (Column 3)
- [ ] Placeholder text shows when empty
- [ ] Text edit works and saves on change
- [ ] ✨ button opens StartPromptDialog
- [ ] LLM generation populates field
- [ ] ↶ Undo button is disabled when no history
- [ ] ↶ Undo works after LLM generation
- [ ] ↷ Redo button is disabled when at end of history
- [ ] ↷ Redo works after undo
- [ ] History persists up to 256 levels
- [ ] Manual edits commit to history on LLM click

### PromptFieldWidget - End Prompt (Column 4)
- [ ] Placeholder text shows when empty
- [ ] Text edit works and saves on change
- [ ] ✨ button opens EndPromptDialog (existing)
- [ ] LLM generation with context (start prompt, next scene)
- [ ] ↶ Undo button works
- [ ] ↷ Redo button works
- [ ] History management works

### PromptFieldWidget - Video Prompt (Column 8)
- [ ] Placeholder text shows when empty
- [ ] Text edit works and saves on change
- [ ] ✨ button opens VideoPromptDialog
- [ ] LLM generation uses start prompt + duration
- [ ] ↶ Undo button works
- [ ] ↷ Redo button works
- [ ] Video button enables when video prompt exists

### Frame Operations
- [ ] Start frame context menu: View, Select, Generate, Clear
- [ ] End frame context menu: View, Select, Generate, Clear, Auto-link
- [ ] Generate start frame creates images in scene.images
- [ ] Generate end frame creates images in scene.end_frame_images
- [ ] Auto-link copies next scene's start frame
- [ ] Auto-link shows 🔗 icon
- [ ] Hover preview works on frame buttons (200x200px)

### Video Generation
- [ ] Video button disabled when no video prompt
- [ ] Video button enabled when video prompt exists
- [ ] Tooltip shows Veo 3 vs 3.1 correctly
- [ ] Click calls generate_video_clip() with correct params

### Wrap Toggle
- [ ] ⤵️ button toggles row wrap state
- [ ] Wrap state persists in scene.metadata
- [ ] Wrap state restored on project load

### Integration
- [ ] Auto-link checkbox in global controls works
- [ ] Bulk auto-link applies to all eligible scenes
- [ ] Project save/load preserves all prompt states
- [ ] Undo/redo history survives table refresh (populate_scene_table)

---

## 📝 Implementation Notes

### Order of Implementation
1. Phase 1: StartPromptDialog (can copy/modify EndPromptDialog)
2. Phase 2: VideoPromptDialog (can copy/modify EndPromptDialog)
3. Phase 3: Rewrite populate_scene_table() - do columns 0-9 sequentially
4. Phase 4: Add handler methods (_on_*_changed, _show_*_dialog)
5. Phase 5: Update existing methods, remove obsolete code
6. Phase 6: Testing with real project

### Performance Considerations
- PromptFieldWidget is lightweight (QLineEdit-based)
- For very long projects (100+ scenes), consider lazy widget creation
- PromptHistory memory: 256 × 3 fields × N scenes = manageable for typical projects

### Backward Compatibility
- Old projects load fine (Scene dataclass has defaults)
- Old prompt_history field (List[str]) is now unused but preserved for compatibility
- PromptHistory lives at UI level, not serialized to project file

### Edge Cases to Handle
- Empty/new projects
- Projects with no source text
- Scenes without prompts
- LLM generation failures
- Very long prompts (500+ characters)

---

## 🚀 Ready for Implementation

This specification provides everything needed to complete the table refactor. Implementation should take 2-3 hours for an experienced developer familiar with the codebase.

**Start with**: Phase 1 (StartPromptDialog) - smallest, most isolated component.
