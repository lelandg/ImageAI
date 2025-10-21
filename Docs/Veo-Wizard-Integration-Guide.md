# Veo 3 Music Sync & Wizard Integration Guide

**Created:** 2025-10-14
**Status:** Implementation Ready
**Related Documents:**
- `Plans/Veo3-Music-Sync-Strategy.md` - Full technical proposal
- `core/video/workflow_wizard.py` - Wizard implementation
- `core/video/midi_processor.py` - MIDI duration utilities

---

## What Was Implemented

### ✅ Completed

1. **Fixed Veo Duration Bug** (`core/video/veo_client.py:242-268`)
   - Now properly passes `duration` parameter to API (not embedded in prompt)
   - Added validation in `VeoGenerationConfig.__post_init__()` for 4/6/8 values
   - Fixed location: `core/video/veo_client.py:52-60`

2. **MIDI Duration Mapping Utilities** (`core/video/midi_processor.py:448-589`)
   - `snap_duration_to_veo(duration)` - Converts float to nearest 4/6/8
   - `align_scene_durations_for_veo()` - Aligns scenes to MIDI + Veo constraints
   - `estimate_veo_scene_count()` - Estimates scenes needed for duration

3. **Workflow Wizard System** (`core/video/workflow_wizard.py`)
   - 8-step guided workflow with resumable state
   - Smart analysis of project to determine current step
   - Contextual help text and choices for each step
   - Progress tracking and blocking logic

4. **VideoProject Integration** (`core/video/project.py:504-534`)
   - `get_workflow_wizard()` - Creates wizard for project
   - `get_wizard_next_step()` - Quick helper for next step
   - `wizard_enabled` flag (default: True)

---

## How to Use in GUI

### Basic Integration Example

```python
from core.video.project import VideoProject
from core.video.workflow_wizard import WorkflowWizard

# Create or load project
project = VideoProject(name="My Music Video")

# Get wizard for this project
wizard = project.get_workflow_wizard()

# Get current step and suggested action
next_action = wizard.get_next_action()

# Display to user
print(f"Step: {next_action['step_title']}")
print(f"Action: {next_action['action']}")
print(f"Progress: {next_action['progress_percent']}%")

# Show help text if user requests it
if user_clicked_help:
    print(next_action['help_text'])

# Show choices if available
if next_action['choices']:
    for choice_key, choice_info in next_action['choices'].items():
        print(f"\nOption: {choice_info['label']}")
        print(f"  {choice_info['description']}")
        for benefit in choice_info['benefits']:
            print(f"  ✓ {benefit}")
```

### GUI Widget Structure Recommendation

```
┌───────────────────────────────────────────────────────┐
│ Video Project: "American Reckoning"                   │
│ Progress: ████████████░░░░░░░░  75% Complete          │
├───────────────────────────────────────────────────────┤
│                                                       │
│ ✓ 1. Input Text/Lyrics                   [Edit]       │
│ ✓ 2. MIDI File (optional)                [Change]     │
│ ✓ 3. Audio Track (optional)              [Change]     │
│ ✓ 4. Generate Storyboard                              │
│ ✓ 5. Enhance Prompts (optional)                       │
│ ● 6. Generate Images/Videos             [Current]     │
│ ○ 7. Review & Approve                                 │
│ ○ 8. Export Final Video                               │
│                                                       │
├───────────────────────────────────────────────────────┤
│ Current Step: Generate Images/Videos                  │
│                                                       │
│ Click 'Generate Video Prompts' to create visuals.     │
│                                                       │
│ [?] Help: Shows generation options explanation        │
│                                                       │
│ ┌───────────────────────────────────────────────┐     │
│ │ Choose Generation Method:                     │     │
│ │                                               │     │
│ │ ○ Images (Gemini) + Ken Burns Effect          │     │
│ │   Fast, cheaper (~$0.02/image)                │     │
│ │                                               │     │
│ │ ● Video Clips (Veo 3)                         │     │
│ │   Native motion, MIDI-synced durations        │     │
│ │   (~$0.60/scene for 6s clip)                  │     │
│ │                                               │     │
│ └───────────────────────────────────────────────┘     │
│                                                       │
│ [Generate for Videos]  [Skip for Now]                 │
└───────────────────────────────────────────────────────┘
```

### Code for GUI Display

```python
class VideoProjectWizardWidget(QWidget):
    """Widget displaying workflow wizard progress and guidance"""

    def __init__(self, project: VideoProject, parent=None):
        super().__init__(parent)
        self.project = project
        self.wizard = project.get_workflow_wizard()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_label = QLabel()
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)

        # Step list (clickable)
        self.step_list = QListWidget()
        self.step_list.itemClicked.connect(self._on_step_clicked)
        layout.addWidget(self.step_list)

        # Current step info panel
        self.step_panel = QGroupBox("Current Step")
        step_layout = QVBoxLayout()

        self.step_title_label = QLabel()
        self.step_title_label.setFont(QFont("Arial", 12, QFont.Bold))
        step_layout.addWidget(self.step_title_label)

        self.step_desc_label = QLabel()
        self.step_desc_label.setWordWrap(True)
        step_layout.addWidget(self.step_desc_label)

        # Help button
        self.help_button = QPushButton("?  Show Help")
        self.help_button.clicked.connect(self._show_help)
        step_layout.addWidget(self.help_button)

        # Choices panel (dynamically shown)
        self.choices_widget = QWidget()
        self.choices_layout = QVBoxLayout(self.choices_widget)
        step_layout.addWidget(self.choices_widget)

        # Action buttons
        button_layout = QHBoxLayout()
        self.action_button = QPushButton()
        self.action_button.clicked.connect(self._on_action_clicked)
        button_layout.addWidget(self.action_button)

        self.skip_button = QPushButton("Skip (optional)")
        self.skip_button.clicked.connect(self._on_skip_clicked)
        button_layout.addWidget(self.skip_button)

        step_layout.addLayout(button_layout)

        self.step_panel.setLayout(step_layout)
        layout.addWidget(self.step_panel)

        # Initialize display
        self.refresh_wizard_display()

    def refresh_wizard_display(self):
        """Update wizard display based on current project state"""
        # Re-analyze project state
        self.wizard._analyze_project_state()
        next_action = self.wizard.get_next_action()

        # Update progress
        progress = next_action['progress_percent']
        self.progress_bar.setValue(progress)
        self.progress_label.setText(f"Progress: {progress}% Complete")

        # Update step list
        self.step_list.clear()
        for step_info in self.wizard.get_all_steps():
            # Create list item
            status_icon = {
                "completed": "●",
                "in_progress": "◐",
                "not_started": "○",
                "optional_skipped": "─"
            }.get(step_info.status.value, "?")

            optional_tag = " (optional)" if step_info.is_optional else ""
            item_text = f"{status_icon} {step_info.title}{optional_tag}"

            item = QListWidgetItem(item_text)

            # Color code by status
            if step_info.status.value == "completed":
                item.setForeground(QColor("green"))
            elif step_info.status.value == "in_progress":
                item.setForeground(QColor("blue"))
                item.setFont(QFont("Arial", 10, QFont.Bold))

            self.step_list.addItem(item)

        # Update current step panel
        self.step_title_label.setText(next_action['step_title'])
        self.step_desc_label.setText(next_action['action'])
        self.action_button.setText(next_action['button_text'])

        # Show/hide skip button
        self.skip_button.setVisible(next_action['is_optional'])

        # Update choices if available
        self._update_choices_panel(next_action.get('choices'))

        # Disable action button if blocked
        if not next_action['can_proceed'] and next_action['blocking_reason']:
            self.action_button.setEnabled(False)
            self.action_button.setToolTip(next_action['blocking_reason'])
        else:
            self.action_button.setEnabled(True)
            self.action_button.setToolTip("")

    def _update_choices_panel(self, choices):
        """Show choices if available"""
        # Clear existing choices
        while self.choices_layout.count():
            item = self.choices_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not choices:
            self.choices_widget.setVisible(False)
            return

        self.choices_widget.setVisible(True)

        choices_label = QLabel("<b>Choose an option:</b>")
        self.choices_layout.addWidget(choices_label)

        # Create radio buttons for each choice
        self.choice_buttons = QButtonGroup()

        for i, (choice_key, choice_info) in enumerate(choices.items()):
            radio = QRadioButton(choice_info['label'])
            radio.setProperty("choice_key", choice_key)

            # Add description
            desc_text = f"<small>{choice_info['description']}</small><br>"

            # Add benefits
            if 'benefits' in choice_info:
                desc_text += "<ul>"
                for benefit in choice_info['benefits']:
                    desc_text += f"<li><small>{benefit}</small></li>"
                desc_text += "</ul>"

            desc_label = QLabel(desc_text)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("margin-left: 20px;")

            self.choices_layout.addWidget(radio)
            self.choices_layout.addWidget(desc_label)
            self.choice_buttons.addButton(radio, i)

            # Select first option by default
            if i == 0:
                radio.setChecked(True)

    def _show_help(self):
        """Show detailed help for current step"""
        next_action = self.wizard.get_next_action()
        help_text = next_action['help_text']

        if help_text:
            dialog = QMessageBox(self)
            dialog.setWindowTitle(f"Help: {next_action['step_title']}")
            dialog.setText(help_text)
            dialog.setIcon(QMessageBox.Information)

            # Add estimated time
            if next_action['estimated_time']:
                dialog.setInformativeText(f"Estimated Time: {next_action['estimated_time']}")

            dialog.exec()

    def _on_action_clicked(self):
        """Handle action button click"""
        current_step = self.wizard.get_current_step()

        # Get selected choice if choices are available
        selected_choice = None
        if hasattr(self, 'choice_buttons') and self.choice_buttons.checkedButton():
            selected_choice = self.choice_buttons.checkedButton().property("choice_key")

        # Emit signal for parent to handle actual action
        self.action_requested.emit(current_step, selected_choice)

    def _on_skip_clicked(self):
        """Handle skip button for optional steps"""
        current_step = self.wizard.get_current_step()
        try:
            self.wizard.mark_step_skipped(current_step)
            self.refresh_wizard_display()
        except ValueError as e:
            QMessageBox.warning(self, "Cannot Skip", str(e))

    def _on_step_clicked(self, item):
        """Allow clicking on step to show its info (but can't jump ahead)"""
        # Just show info, don't allow jumping to step
        pass

    # Define signals
    from PySide6.QtCore import Signal
    action_requested = Signal(object, object)  # (step, choice)
```

---

## MIDI-Synced Veo Generation Example

Here's how to use the MIDI utilities to generate Veo videos with proper durations:

```python
from pathlib import Path
from core.video.project import VideoProject, Scene
from core.video.midi_processor import MidiProcessor, align_scene_durations_for_veo
from core.video.veo_client import VeoClient, VeoGenerationConfig, VeoModel

# 1. Load project with MIDI
project = VideoProject.load(Path("my_project.iaproj.json"))

# 2. Extract MIDI timing
processor = MidiProcessor()
midi_timing = processor.extract_timing(project.midi_file_path)

# 3. Convert scenes to dictionaries for alignment
scene_dicts = [{"prompt": s.prompt, "source": s.source} for s in project.scenes]

# 4. Align scenes to MIDI with Veo constraints
aligned_scenes = align_scene_durations_for_veo(
    scenes=scene_dicts,
    timing=midi_timing,
    alignment="measure",  # Align to musical measures
    allowed_durations=[4, 6, 8],  # Veo 3 constraints
    total_duration_target=midi_timing.duration_sec
)

# 5. Update project scenes with Veo-compatible durations
for i, aligned in enumerate(aligned_scenes):
    project.scenes[i].duration_sec = aligned["duration_sec"]
    # Note: aligned["veo_duration"] is the snapped value
    # aligned["midi_aligned_duration"] preserves original MIDI timing

# 6. Generate Veo videos with correct durations
veo_client = VeoClient(api_key="YOUR_GOOGLE_API_KEY")

for scene in project.scenes:
    config = VeoGenerationConfig(
        model=VeoModel.VEO_3_GENERATE,
        prompt=scene.video_prompt or scene.prompt,
        duration=int(scene.duration_sec),  # Will be 4, 6, or 8
        aspect_ratio=project.style["aspect_ratio"],
        resolution=project.style["resolution"],
        include_audio=False  # Mute Veo audio for music videos
    )

    print(f"Generating {config.duration}s clip for: {scene.prompt[:50]}...")

    result = veo_client.generate_video(config)

    if result.success:
        scene.video_clip = result.video_path
        scene.status = SceneStatus.COMPLETED
        print(f"✓ Generated: {result.video_path}")
    else:
        scene.status = SceneStatus.ERROR
        print(f"✗ Failed: {result.error}")

# 7. Save project
project.save()

print(f"\n✓ All scenes generated with MIDI-aligned durations")
print(f"Total video duration: {project.get_total_duration()}s")
print(f"MIDI song duration: {midi_timing.duration_sec}s")
```

---

## Wizard Step Actions Reference

### Step 1: Input Text
**Action:** User enters lyrics/text
**GUI Update:** Enable "Continue" button when text is present
**Wizard Call:** `wizard.mark_step_complete(WorkflowStep.INPUT_TEXT)`

### Step 2: MIDI File (Optional)
**Action:** User uploads MIDI or clicks "Skip"
**GUI Update:**
- If uploaded: Process MIDI, store in `project.midi_file_path`
- If skipped: `wizard.mark_step_skipped(WorkflowStep.MIDI_FILE)`

**Code:**
```python
if midi_file_selected:
    # Process MIDI
    processor = MidiProcessor()
    timing_data = processor.extract_timing(midi_file)
    project.midi_file_path = midi_file
    project.midi_timing_data = timing_data
    project.sync_mode = "measure"  # Default to measure alignment
    wizard.mark_step_complete(WorkflowStep.MIDI_FILE)
```

### Step 3: Audio File (Optional)
**Action:** User uploads audio or clicks "Skip"
**Code:**
```python
if audio_file_selected:
    track = project.add_audio_track(audio_file, track_type='music')
    wizard.mark_step_complete(WorkflowStep.AUDIO_FILE)
```

### Step 4: Generate Storyboard
**Action:** Parse input text into scenes
**Code:**
```python
# Parse input text (implementation depends on format)
lines = project.input_text.split('\n')
for line in lines:
    if line.strip():
        project.add_scene(source=line, prompt=line, duration=6.0)

# If MIDI available, align durations
if project.midi_timing_data:
    scene_dicts = [{"prompt": s.prompt} for s in project.scenes]
    aligned = align_scene_durations_for_veo(
        scenes=scene_dicts,
        timing=project.midi_timing_data,
        alignment=project.sync_mode
    )
    for i, aligned_scene in enumerate(aligned):
        project.scenes[i].duration_sec = aligned_scene["duration_sec"]

wizard.mark_step_complete(WorkflowStep.GENERATE_STORYBOARD)
```

### Step 5: Enhance Prompts (Optional)
**Action:** Use LLM to enhance prompts
**Code:**
```python
from core.prompt_enhancer_llm import enhance_prompts_with_llm

for scene in project.scenes:
    enhanced = enhance_prompts_with_llm(
        scene.prompt,
        provider=project.llm_provider,
        model=project.llm_model
    )
    scene.add_prompt_to_history(enhanced)

wizard.mark_step_complete(WorkflowStep.ENHANCE_PROMPTS)
```

### Step 6: Generate Media
**Action:** Generate images or Veo videos
**Code:** See "MIDI-Synced Veo Generation Example" above

### Step 7: Review & Approve
**Action:** User reviews and approves variants
**GUI:** Show image gallery for each scene, allow selection
**Update:** Set `scene.approved_image = selected_variant.path`

### Step 8: Export Video
**Action:** Render final video
**Code:**
```python
from core.video.ffmpeg_renderer import FFmpegRenderer, RenderSettings

renderer = FFmpegRenderer()
settings = RenderSettings(
    resolution=project.style["resolution"],
    fps=24,
    video_codec="libx264",
    crf=23
)

output_path = project.project_dir / f"{project.name}.mp4"

final_video = renderer.render_slideshow(
    project=project,
    output_path=output_path,
    settings=settings,
    add_karaoke=bool(project.karaoke_config)
)

project.export_path = final_video
wizard.mark_step_complete(WorkflowStep.EXPORT_VIDEO)
```

---

## Best Practices

### 1. Always Refresh Wizard After Project Changes

```python
# After ANY change to project state
project.scenes.append(new_scene)
wizard_widget.refresh_wizard_display()  # Re-analyze project
```

### 2. Provide Clear Visual Feedback

- ✓ Green checkmark for completed steps
- ◐ Blue partial circle for in-progress
- ○ Gray circle for not started
- ─ Gray dash for skipped optional steps

### 3. Show Progress Percentage

```python
progress = wizard.get_next_action()['progress_percent']
self.progress_bar.setValue(progress)
```

### 4. Display Blocking Reasons

```python
if not can_proceed:
    reason = next_action['blocking_reason']
    QMessageBox.information(self, "Cannot Proceed", reason)
```

### 5. Save Project Frequently

```python
# After each major action
project.save()
```

---

## GUI Components Needed

To fully integrate the wizard, you'll need:

1. **Wizard Panel Widget** (see example above)
   - Step list with status indicators
   - Progress bar
   - Current step info panel
   - Action/Skip buttons
   - Choices radio buttons

2. **Help Dialog**
   - Shows detailed help text for current step
   - Displays estimated time
   - Links to relevant documentation

3. **Step-Specific UI**
   - Text editor for Input Text step
   - File browser for MIDI/Audio steps
   - LLM enhancement dialog
   - Image generation controls
   - Review gallery
   - Export settings dialog

4. **Integration Points**
   - Video Project Tab: Add wizard panel to left sidebar
   - Each action button triggers corresponding workflow step
   - Wizard updates after each action completes

---

## Testing the Wizard

```python
# Create test project
project = VideoProject(name="Test Project")

# Step through workflow
wizard = project.get_workflow_wizard()

# Test 1: Initial state
assert wizard.get_current_step() == WorkflowStep.INPUT_TEXT
assert wizard.get_next_action()['progress_percent'] == 0

# Test 2: Add input text
project.input_text = "Test lyric line 1\nTest lyric line 2"
wizard._analyze_project_state()
assert wizard.steps[WorkflowStep.INPUT_TEXT].status == StepStatus.COMPLETED

# Test 3: Skip optional MIDI
wizard.mark_step_skipped(WorkflowStep.MIDI_FILE)
assert wizard.steps[WorkflowStep.MIDI_FILE].status == StepStatus.OPTIONAL_SKIPPED

# Test 4: Generate storyboard
for line in project.input_text.split('\n'):
    project.add_scene(source=line, prompt=line)
wizard._analyze_project_state()
assert len(project.scenes) == 2
assert wizard.steps[WorkflowStep.GENERATE_STORYBOARD].status == StepStatus.COMPLETED

# Test 5: Progress calculation
progress = wizard._calculate_progress()
assert progress > 25  # Should be past first few steps

print("✓ All wizard tests passed!")
```

---

## Summary of Benefits

1. **User-Friendly:** Step-by-step guidance reduces confusion
2. **Resumable:** Close and reopen project, pick up where you left off
3. **Smart:** Analyzes project to suggest next action
4. **Flexible:** Optional steps can be skipped
5. **Educational:** Help text explains each step and choices
6. **Professional:** Progress tracking and clear feedback

---

## Next Steps for Full Integration

1. **Add wizard panel to Video Project GUI** (left sidebar)
2. **Connect action buttons to workflow steps**
3. **Implement step-specific dialogs** (if not already present)
4. **Add keyboard shortcuts** (e.g., Ctrl+W to toggle wizard)
5. **Persist wizard_enabled preference** in user settings
6. **Add "Wizard Mode" toggle** in View menu
7. **Create tutorial/walkthrough** for first-time users

---

**This integration allows users to create MIDI-synced Veo 3 music videos with zero confusion about what to do next!**
