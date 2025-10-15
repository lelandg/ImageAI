# Wizard Integration - Step-by-Step Instructions

This document provides exact code changes to integrate the Workflow Wizard into the Video Project GUI.

---

## Files Created

✅ **Already Created:**
1. `core/video/workflow_wizard.py` - Workflow wizard logic
2. `gui/video/wizard_widget.py` - Wizard GUI widget
3. `core/video/midi_processor.py` - Added Veo duration utilities (lines 448-589)
4. Fixed `core/video/veo_client.py` - Veo duration parameter bug

---

## Integration Steps

### Step 1: Add Wizard to WorkspaceWidget

**File:** `gui/video/workspace_widget.py`

**Location:** In the `__init__` method, after existing UI initialization

**Add this import at the top:**
```python
from .wizard_widget import WorkflowWizardWidget
```

**In the `__init__` method, after creating the main layout:**

Find the line where the main layout is created (look for `main_layout = QHBoxLayout(self)`), and add:

```python
# Create wizard widget (left sidebar)
self.wizard_widget = None  # Will be created when project is loaded
self.wizard_container = QWidget()
self.wizard_layout = QVBoxLayout(self.wizard_container)
self.wizard_layout.setContentsMargins(0, 0, 0, 0)

# Add wizard toggle button
self.wizard_toggle_btn = QPushButton("Show Wizard Guide")
self.wizard_toggle_btn.setCheckable(True)
self.wizard_toggle_btn.setChecked(True)
self.wizard_toggle_btn.clicked.connect(self._toggle_wizard)
self.wizard_layout.addWidget(self.wizard_toggle_btn)

# Wizard placeholder
self.wizard_placeholder = QLabel("Load or create a project to see workflow guide")
self.wizard_placeholder.setStyleSheet("color: #666; padding: 20px;")
self.wizard_placeholder.setWordWrap(True)
self.wizard_placeholder.setAlignment(Qt.AlignCenter)
self.wizard_layout.addWidget(self.wizard_placeholder)

# Add wizard container to main layout (on the left side)
main_splitter = QSplitter(Qt.Horizontal)
main_splitter.addWidget(self.wizard_container)
main_splitter.addWidget(existing_main_widget)  # Your existing main UI widget
main_splitter.setStretchFactor(0, 0)  # Wizard doesn't stretch
main_splitter.setStretchFactor(1, 1)  # Main content stretches
main_splitter.setSizes([300, 700])  # Initial sizes

main_layout.addWidget(main_splitter)
```

**Add these methods to WorkspaceWidget class:**

```python
def _toggle_wizard(self, checked):
    """Toggle wizard visibility"""
    if self.wizard_widget:
        self.wizard_widget.setVisible(checked)
    self.wizard_toggle_btn.setText("Hide Wizard Guide" if checked else "Show Wizard Guide")

def _create_wizard_widget(self):
    """Create wizard widget for current project"""
    if not self.current_project:
        return

    # Remove old wizard if exists
    if self.wizard_widget:
        self.wizard_layout.removeWidget(self.wizard_widget)
        self.wizard_widget.deleteLater()

    # Remove placeholder
    if self.wizard_placeholder:
        self.wizard_placeholder.setVisible(False)

    # Create new wizard
    self.wizard_widget = WorkflowWizardWidget(self.current_project, self)
    self.wizard_widget.action_requested.connect(self._on_wizard_action)
    self.wizard_widget.step_skipped.connect(self._on_wizard_step_skipped)

    self.wizard_layout.addWidget(self.wizard_widget)
    self.wizard_widget.setVisible(self.wizard_toggle_btn.isChecked())

def _on_wizard_action(self, step, choice):
    """Handle wizard action request"""
    from core.video.workflow_wizard import WorkflowStep

    # Map wizard steps to actual actions
    if step == WorkflowStep.INPUT_TEXT:
        # Focus on input text field
        if hasattr(self, 'input_text'):
            self.input_text.setFocus()

    elif step == WorkflowStep.MIDI_FILE:
        # Open MIDI file dialog
        self._browse_midi_file()

    elif step == WorkflowStep.AUDIO_FILE:
        # Open audio file dialog
        self._browse_audio_file()

    elif step == WorkflowStep.GENERATE_STORYBOARD:
        # Trigger storyboard generation
        self._generate_storyboard()

    elif step == WorkflowStep.ENHANCE_PROMPTS:
        # Trigger prompt enhancement
        if choice == "enhance":
            self._enhance_prompts()
        elif choice == "skip":
            if self.wizard_widget:
                self.wizard_widget.wizard.mark_step_skipped(step)
                self.wizard_widget.refresh_wizard_display()

    elif step == WorkflowStep.GENERATE_MEDIA:
        # Trigger media generation based on choice
        if choice == "images":
            self._generate_images()
        elif choice == "videos":
            self._generate_video_clips()

    elif step == WorkflowStep.REVIEW_APPROVE:
        # Focus on scene table for review
        if hasattr(self, 'scene_table'):
            self.scene_table.setFocus()

    elif step == WorkflowStep.EXPORT_VIDEO:
        # Trigger video export
        self._render_video()

def _on_wizard_step_skipped(self, step):
    """Handle wizard step skipped"""
    self.logger.info(f"Skipped workflow step: {step.value}")
    # Save project with updated state
    if self.current_project:
        self.save_project()

def _refresh_wizard(self):
    """Refresh wizard display after project changes"""
    if self.wizard_widget and self.wizard_widget.isVisible():
        self.wizard_widget.refresh_wizard_display()
```

**Update existing methods to refresh wizard:**

Add `self._refresh_wizard()` at the end of these methods:
- `new_project()` - After creating new project
- `open_project()` - After opening project
- `save_project()` - After saving
- `populate_scene_table()` - After updating scenes
- Any method that modifies project state

**In `new_project()` method, add:**
```python
def new_project(self):
    # ... existing code ...

    self.current_project = project

    # Create wizard widget
    self._create_wizard_widget()

    # ... rest of existing code ...
```

**In `open_project()` method, add:**
```python
def open_project(self):
    # ... existing code ...

    self.current_project = project

    # Create wizard widget
    self._create_wizard_widget()

    # ... rest of existing code ...
```

---

### Step 2: Connect Wizard Actions to Existing Handlers

**File:** `gui/video/workspace_widget.py`

Make sure these methods exist (they probably already do):

```python
def _browse_midi_file(self):
    """Browse for MIDI file"""
    file_path, _ = QFileDialog.getOpenFileName(
        self,
        "Select MIDI File",
        "",
        "MIDI Files (*.mid *.midi);;All Files (*)"
    )

    if file_path:
        self._load_midi_file(file_path)

def _load_midi_file(self, file_path: str):
    """Load and process MIDI file"""
    try:
        from core.video.midi_processor import MidiProcessor
        from pathlib import Path

        midi_path = Path(file_path)

        # Process MIDI
        processor = MidiProcessor()
        timing_data = processor.extract_timing(midi_path)

        # Store in project
        self.current_project.midi_file_path = midi_path
        self.current_project.midi_timing_data = timing_data
        self.current_project.sync_mode = "measure"  # Default

        # Update UI
        if hasattr(self, 'midi_file_label'):
            self.midi_file_label.setText(midi_path.name)

        # Show success message
        dialog_manager = get_dialog_manager(self)
        dialog_manager.show_success(
            "MIDI File Loaded",
            f"Loaded {len(timing_data.beats)} beats, {len(timing_data.measures)} measures\n"
            f"Duration: {timing_data.duration_sec:.1f}s, Tempo: {timing_data.tempo_bpm:.1f} BPM"
        )

        # Refresh wizard
        self._refresh_wizard()

        # If scenes exist, offer to re-align durations
        if self.current_project.scenes:
            reply = QMessageBox.question(
                self,
                "Re-align Scene Durations?",
                f"You have {len(self.current_project.scenes)} scenes.\n\n"
                "Would you like to re-align their durations to the MIDI timing?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self._align_scenes_to_midi()

    except Exception as e:
        self.logger.error(f"Failed to load MIDI file: {e}", exc_info=True)
        dialog_manager = get_dialog_manager(self)
        dialog_manager.show_error("MIDI Load Failed", str(e))

def _align_scenes_to_midi(self):
    """Align scene durations to MIDI timing with Veo constraints"""
    try:
        from core.video.midi_processor import align_scene_durations_for_veo

        if not self.current_project.midi_timing_data:
            return

        # Convert scenes to dicts
        scene_dicts = [
            {"prompt": s.prompt, "source": s.source}
            for s in self.current_project.scenes
        ]

        # Align with Veo constraints
        aligned = align_scene_durations_for_veo(
            scenes=scene_dicts,
            timing=self.current_project.midi_timing_data,
            alignment=self.current_project.sync_mode or "measure",
            total_duration_target=self.current_project.midi_timing_data.duration_sec
        )

        # Update scene durations
        for i, aligned_scene in enumerate(aligned):
            self.current_project.scenes[i].duration_sec = aligned_scene["duration_sec"]

        # Refresh UI
        self.populate_scene_table()
        self._refresh_wizard()

        # Show summary
        durations = [s.duration_sec for s in self.current_project.scenes]
        unique_durations = set(int(d) for d in durations)

        dialog_manager = get_dialog_manager(self)
        dialog_manager.show_success(
            "Scenes Aligned",
            f"Aligned {len(self.current_project.scenes)} scenes to MIDI timing.\n\n"
            f"Durations used: {sorted(unique_durations)} seconds (Veo-compatible)\n"
            f"Total duration: {sum(durations):.1f}s"
        )

    except Exception as e:
        self.logger.error(f"Failed to align scenes: {e}", exc_info=True)
        dialog_manager = get_dialog_manager(self)
        dialog_manager.show_error("Alignment Failed", str(e))

def _browse_audio_file(self):
    """Browse for audio file"""
    file_path, _ = QFileDialog.getOpenFileName(
        self,
        "Select Audio File",
        "",
        "Audio Files (*.mp3 *.wav *.ogg *.flac *.m4a);;All Files (*)"
    )

    if file_path:
        self._load_audio_file(file_path)

def _load_audio_file(self, file_path: str):
    """Load audio file"""
    try:
        from pathlib import Path

        audio_path = Path(file_path)

        # Add to project
        self.current_project.add_audio_track(audio_path, track_type='music')

        # Update UI
        if hasattr(self, 'audio_file_label'):
            self.audio_file_label.setText(audio_path.name)

        # Show success
        dialog_manager = get_dialog_manager(self)
        dialog_manager.show_success("Audio File Loaded", f"Loaded: {audio_path.name}")

        # Refresh wizard
        self._refresh_wizard()

    except Exception as e:
        self.logger.error(f"Failed to load audio file: {e}", exc_info=True)
        dialog_manager = get_dialog_manager(self)
        dialog_manager.show_error("Audio Load Failed", str(e))
```

---

### Step 3: Update Generation Handlers

**File:** `gui/video/workspace_widget.py`

Make sure these methods call `self._refresh_wizard()` after completion:

```python
def _generate_storyboard(self):
    """Generate storyboard from input text"""
    # ... existing code ...

    # At the end, after storyboard is generated:
    self._refresh_wizard()

def _enhance_prompts(self):
    """Enhance prompts with LLM"""
    # ... existing code ...

    # At the end, after prompts are enhanced:
    self._refresh_wizard()

def _generate_images(self):
    """Generate images for scenes"""
    # ... existing code ...

    # At the end, after images are generated:
    self._refresh_wizard()

def _generate_video_clips(self):
    """Generate video clips with Veo"""
    # ... existing code ...

    # At the end, after videos are generated:
    self._refresh_wizard()
```

---

### Step 4: Add Wizard to Settings/Preferences

**Optional:** Add a setting to enable/disable wizard mode

**File:** `gui/tabs/settings_tab.py` or equivalent

```python
# In settings UI
self.wizard_enabled_checkbox = QCheckBox("Show Workflow Wizard in Video Projects")
self.wizard_enabled_checkbox.setChecked(True)  # Default enabled

# Save to config
config.set("video_wizard_enabled", self.wizard_enabled_checkbox.isChecked())

# In workspace widget __init__:
wizard_enabled = self.config.get("video_wizard_enabled", True)
if wizard_enabled:
    self.wizard_container.setVisible(True)
else:
    self.wizard_container.setVisible(False)
```

---

## Testing the Integration

### Test 1: Create New Project

1. Open ImageAI
2. Go to Video Project tab
3. Click "New Project"
4. **Expected:** Wizard appears on left showing "Step 1: Input Text"
5. Enter some text in input field
6. **Expected:** Wizard updates to show step completed

### Test 2: MIDI Integration

1. With project open, wizard shows "Step 2: MIDI File"
2. Click "Upload MIDI File" button (from wizard or from UI)
3. Select a MIDI file
4. **Expected:**
   - Wizard shows MIDI step completed
   - If scenes exist, prompted to re-align durations
   - Durations snap to 4, 6, or 8 seconds

### Test 3: Complete Workflow

1. Follow wizard through all steps:
   - Input text ✓
   - MIDI file (optional - can skip)
   - Audio file (optional - can skip)
   - Generate storyboard ✓
   - Enhance prompts (optional)
   - Generate media ✓
   - Review & approve ✓
   - Export video ✓

2. **Expected:** Progress bar shows 100% at end

### Test 4: Resume Project

1. Save project and close
2. Reopen project
3. **Expected:** Wizard shows correct current step based on project state

### Test 5: Wizard Help

1. Click "? Show Help" button
2. **Expected:** Detailed help dialog appears with:
   - Step description
   - Benefits/drawbacks of choices
   - Estimated time
   - Requirements

---

## Troubleshooting

### Wizard doesn't appear
- Check that `wizard_container` is added to layout
- Verify `_create_wizard_widget()` is called in `new_project()` and `open_project()`
- Check console for errors

### Wizard shows wrong step
- Make sure `_refresh_wizard()` is called after project changes
- Verify project state (scenes, midi_file_path, etc.) is being saved correctly

### Actions don't trigger
- Check that `_on_wizard_action()` is connected to `wizard_widget.action_requested`
- Verify method names match (e.g., `_generate_storyboard()` exists)

### MIDI alignment not working
- Ensure `pretty_midi` is installed: `pip install pretty-midi mido`
- Check that MIDI file is valid
- Verify `midi_timing_data` is being stored in project

---

## Summary of Changes

**New Files:**
- `gui/video/wizard_widget.py` - Wizard UI widget
- `core/video/workflow_wizard.py` - Wizard logic (already created)

**Modified Files:**
- `gui/video/workspace_widget.py`:
  - Import WorkflowWizardWidget
  - Add wizard container to layout
  - Add `_create_wizard_widget()` method
  - Add `_on_wizard_action()` handler
  - Add `_refresh_wizard()` calls throughout
  - Add MIDI/audio loading methods

**Dependencies:**
- `pretty-midi` - For MIDI processing
- `mido` - For MIDI file reading

Install with:
```bash
pip install pretty-midi mido
```

---

## Next Steps After Integration

1. **Test thoroughly** with various project states
2. **Gather user feedback** on wizard helpfulness
3. **Consider adding**:
   - Keyboard shortcuts (Ctrl+W to toggle wizard)
   - Animated transitions between steps
   - Video tutorials linked from help dialogs
   - Tooltips on hover
4. **Document** in user guide / help tab

---

**Integration Complete!** 🎉

Users now have a guided, resumable workflow for creating MIDI-synced music videos with Veo 3!
