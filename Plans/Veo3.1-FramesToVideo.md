# Veo 3.1 Start/End Frame Video Generation Plan

**Status**: Planning - Storyboard Enhancement
**Created**: 2025-10-16
**Updated**: 2025-10-16
**Feature**: Add optional end frame to each video using Veo 3.1

## Overview

Google released Veo 3.1 on October 15, 2025, with "Frames to Video" capability that generates videos transitioning from a start frame to an end frame. This plan integrates this into ImageAI's Video Tab storyboard by adding an optional end frame to each row. Each video can now transition smoothly from its start frame to its end frame, and when auto-link is enabled, videos flow seamlessly into each other.

## Executive Summary

**Goal**: Allow each video to have an optional end frame, using Veo 3.1 to create smooth transitions within each video clip.

**Key Features**:
- Each row has optional **End Prompt** and **End Frame** columns
- Videos can be generated with start frame only (Veo 3, current behavior) OR start + end frames (Veo 3.1, new)
- Auto-link option: Use next row's start frame as this row's end frame
- LLM can generate transition prompts for end frames
- Hover previews for quick visual feedback
- Right-click "Clear" on all buttons
- Enhance all prompts creates prompts for all start and end frames. 
  - If any exist, prompt with, "replace all, replace selected, or cancel"
  - Enable multi-row select for this. 

**Impact**: Videos can have cinematic evolution within each clip, and when auto-linked, the entire project flows seamlessly from start to finish with no jump cuts.

## Current vs New Workflow

### Current Workflow (Veo 3)
```
Row 1: [Start Frame: "walking in rain"] → Video (start frame animates)
Row 2: [Start Frame: "moonlit path"] → Video (start frame animates)
Final: Concatenate videos → jump cut between Row 1 and Row 2
```

### New Workflow (Veo 3.1)
```
Row 1: [Start Frame: "walking in rain"] → [End Frame: "reaching clearing"]
       → Video transitions from rain to clearing

Row 2: [Start Frame: "moonlit path"] → [End Frame: "stars emerge"]
       → Video transitions from moonlit path to stars

Final: Concatenate videos → still has jump cut (unless auto-linked)
```

### Auto-Linked Workflow (Seamless)
```
Row 1: [Start: "walking in rain"] → [End: AUTO-LINK to Row 2 start]
       → Video transitions from rain to moonlit path

Row 2: [Start: "moonlit path"] → [End: "stars emerge"]
       → Video transitions from moonlit path to stars

Final: Concatenate → Row 1 ends where Row 2 starts = seamless!
```

## Storyboard Design

### New Table Structure 

```
Global Controls adds to top:
┌──────────────────────────────────────────────────────────────────────┐
│ [✓] Auto-link end frames (use next row's start frame as end frame)   │
└──────────────────────────────────────────────────────────────────────┘

Table Columns adds colums like this:
|-------------------------+--------+-------------------------+--------+--------+------+
| Start Prompt            | Start  | End Prompt              | End    | Video  | Time |
| (wide, like Image       | Frame  | (wide, like Image       | Frame  |        |(40px)|
| Prompt column)          | (icon) | Prompt column)          | (icon) | (icon) |      |
+-------------------------+--------+-------------------------+--------+--------+------+
| "walking in rain,       | [🖼️]   | "reaching moonlit       | [🖼️]   | [▶️]   | 6    |
|  droplets on leaves"    |        | clearing, mist rising"  |        |        |      |
+-------------------------+--------+-------------------------+--------+--------+------+
| "moonlit forest path"   | [🖼️]   | [✨ LLM]                | [➕]   | [▶️]   | 8    |
+-------------------------+--------+-------------------------+--------+--------+------+
| "stars twinkling"       | [🖼️]   | "sunrise breaking"      | [🔗]   | [▶️]   | 6    |
|                         |        |                         |(auto)  |        |      |
+-------------------------+--------+-------------------------+--------+--------+------+

Legend:
🖼️ = Image exists (hover for preview, click to view)
🔗 = Auto-linked from next row's start frame
✨ = When empty, prompt fields have this button to generate prompt
➕ = Optional (empty = single-frame video) click to generate image
▶️ = Video exists - show thumbnail on hover, click to view
```

### Column Specifications

**Start Prompt** (existing, unchanged):
- Wide column (same width as current "Image Prompt")
- Describes the starting frame of the video
- Generate button creates start frame image

**Start Frame** (existing "Image Preview", unchanged):
- 60-80px icon button
- Hover: Show 200x200px thumbnail preview
- Click: Open full image viewer
- Right-click menu: View, Select, Regenerate, **Clear** (new), Copy

**End Prompt** (NEW):
- Wide column (same width as Start Prompt)
- Optional text field describing the ending frame of the video
- **[✨ LLM]** button: Generate prompt using LLM based on:
  - Current row's start prompt
  - Next row's start prompt (if exists)
  - Generates description like: "smooth transition from rain to clearing with mist"
- Empty = single-frame video (current Veo 3 behavior)

**End Frame** (NEW):
- 60-80px icon button
- Hover: Show 200x200px thumbnail preview
- Click: Open full image viewer
- **Pop-up on generation**: Show preview dialog when end frame is generated/assigned
- States:
  - Empty `[➕]`: Optional, no end frame
  - Generated `[🖼️]`: End frame exists
  - Auto-linked `[🔗]`: Using next row's start frame
- Right-click menu: View, Select, Generate, Use Next Start Frame, **Clear** (new), Copy

**Video** (existing, enhanced):
- Icon shows if video used start only `[▶️]` or start+end `[▶️→]`
- Right-click menu: Play, Regenerate, **Clear** (new), **Extract First Frame** (new), Export

**Time** (existing, renamed/narrowed):
- **Narrowed to 40-50px** (previously "Duration")
- Label changed to "Time"
- Just shows number (e.g., "6", "8")

## How It Works

### Video Generation Logic

**When user clicks "Generate Video" button:**

1. **Check for end frame:**
   ```python
   if row.end_frame_path is None:
       # Use Veo 3 (current behavior)
       video = generate_video_from_single_frame(
           frame=row.start_frame_path,
           prompt=row.start_prompt,
           duration=row.duration
       )
   else:
       # Use Veo 3.1 (new behavior)
       video = generate_video_from_start_and_end(
           start_frame=row.start_frame_path,
           end_frame=row.end_frame_path,
           prompt=row.end_prompt or row.start_prompt,
           duration=row.duration
       )
   ```

2. **Store video path in same row**
3. **No additional frames added to workflow** - still one video per row
4. **Concatenation works exactly the same** - just concatenate all row videos in order

### Auto-Link Feature

**Purpose**: Make videos flow seamlessly by ensuring Row N ends where Row N+1 starts.

**How it works:**

1. User enables "Auto-link end frames" checkbox at top
2. When generating Row N video:
   - If Row N has no end frame AND Row N+1 exists
   - Check if Row N+1 has a start frame
   - If yes: Copy Row N+1's start frame to be Row N's end frame
   - Generate Row N video with start → end (which equals Row N+1 start)

3. Result: When videos are concatenated:
   ```
   Row N video ends with: [Frame X]
   Row N+1 video starts with: [Frame X]
   → No jump cut! Seamless transition.
   ```

**Visual Indicator:**
- End frame button shows `[🔗]` icon when auto-linked
- Tooltip: "Auto-linked from Row 2 start frame"
- If user manually sets end frame, override auto-link

### LLM Prompt Generation

**Purpose**: Help user create good transition descriptions for end frames.

**How it works:**

1. User clicks `[✨ LLM]` button in End Prompt column
2. Dialog opens showing:
   ```
   ┌─────────────────────────────────────────┐
   │ Generate End Frame Prompt with LLM      │
   ├─────────────────────────────────────────┤
   │                                         │
   │ Current scene (start):                  │
   │ "walking in rain, droplets on leaves"   │
   │                                         │
   │ Next scene (Row 2 start):               │
   │ "moonlit forest path, ethereal glow"    │
   │                                         │
   │ Generated end prompt:                   │
   │ ┌─────────────────────────────────────┐ │
   │ │ The rain gradually fades as soft    │ │
   │ │ moonlight breaks through the clouds,│ │
   │ │ revealing a mystical forest path    │ │
   │ │ ahead with ethereal glow.           │ │
   │ └─────────────────────────────────────┘ │
   │                                         │
   │ [Use] [Regenerate] [Edit] [Cancel]     │
   └─────────────────────────────────────────┘
   ```

3. User can:
   - Use prompt as-is
   - Regenerate for different variation
   - Edit before using
   - Cancel

4. Chosen prompt is inserted into End Prompt field
5. User then generates end frame from that prompt

**LLM System Prompt:**
```
You are a video transition specialist. Generate a description for the END
FRAME of a video that starts with [start_prompt].

The end frame should naturally transition toward [next_prompt if exists].

Describe what the final frame should look like - focus on the visual
elements, not camera movement. The Veo API will handle the transition.

Format: 1-2 sentences describing the end state.
```

## User Workflows

### Workflow 1: Single-Frame Video (Current Behavior, No Change)

1. Enter Start Prompt: "walking in rain"
2. Generate Start Frame
3. Leave End Prompt and End Frame empty
4. Generate Video → Uses Veo 3, animates start frame
5. **Result**: Same as current behavior

### Workflow 2: Start+End Video (New)

1. Enter Start Prompt: "walking in rain"
2. Generate Start Frame
3. Enter End Prompt: "reaching moonlit clearing"
4. Generate End Frame
5. Generate Video → Uses Veo 3.1, transitions from start to end
6. **Result**: ONE video that evolves from rain to clearing

### Workflow 3: LLM-Assisted End Prompt

1. Enter Start Prompt: "walking in rain"
2. Generate Start Frame
3. Add Row 2 with Start Prompt: "moonlit forest path"
4. Back to Row 1: Click `[✨ LLM]` button
5. LLM generates end prompt based on both prompts
6. Review/edit, click Use
7. Generate End Frame from LLM prompt
8. Generate Video
9. **Result**: Video with AI-crafted transition

### Workflow 4: Auto-Linked Project (Seamless)

1. Enable "Auto-link end frames" checkbox
2. Add 3 rows with start prompts, generate all start frames
3. Generate videos in order:
   - Row 1: Auto-links to Row 2 start, generates video (start → Row 2 start)
   - Row 2: Auto-links to Row 3 start, generates video (start → Row 3 start)
   - Row 3: No auto-link (last row), generates single-frame or manual end
4. Concatenate all videos
5. **Result**: Seamless video with no jump cuts between rows

### Workflow 5: Mixed Single and Start+End

1. Row 1: Start only → Single-frame video (static scene)
2. Row 2: Start + End → Transition video (evolving scene)
3. Row 3: Start + Auto-linked End → Transition to Row 4
4. **Result**: Flexible project with both static and evolving scenes

## Technical Implementation

### Data Model Updates

**StoryboardRow Class:**
```python
@dataclass
class StoryboardRow:
    """Single row in the video storyboard."""

    # Existing fields (unchanged)
    index: int
    start_prompt: str
    start_frame_path: Optional[Path] = None
    video_path: Optional[Path] = None
    duration: float = 6.0

    # New fields for Veo 3.1
    end_prompt: str = ""  # Optional end scene description
    end_frame_path: Optional[Path] = None  # Optional end frame
    end_frame_auto_linked: bool = False  # True if using next row's start

    def uses_veo_31(self) -> bool:
        """Check if this row will use Veo 3.1 (has end frame)."""
        return self.end_frame_path is not None

    def can_generate_video(self) -> bool:
        """Check if ready for video generation."""
        return self.start_frame_path is not None
```

**Project JSON:**
```json
{
  "project_name": "My Video",
  "version": "2.0",
  "auto_link_enabled": true,
  "rows": [
    {
      "index": 0,
      "start_prompt": "walking in rain",
      "start_frame_path": "images/row_0_start.png",
      "end_prompt": "reaching moonlit clearing",
      "end_frame_path": "images/row_0_end.png",
      "end_frame_auto_linked": false,
      "video_path": "videos/row_0.mp4",
      "duration": 6.0
    },
    {
      "index": 1,
      "start_prompt": "moonlit forest path",
      "start_frame_path": "images/row_1_start.png",
      "end_prompt": "",
      "end_frame_path": null,
      "end_frame_auto_linked": false,
      "video_path": "videos/row_1.mp4",
      "duration": 8.0
    }
  ]
}
```

### Video Generation

**File**: `core/video/generator.py`

```python
def generate_video_for_row(self, row: StoryboardRow) -> Path:
    """
    Generate video for a storyboard row.
    Uses Veo 3 if only start frame, Veo 3.1 if start + end frames.

    Args:
        row: Storyboard row with frame info

    Returns:
        Path to generated video
    """
    if row.end_frame_path is None:
        # Single-frame video (Veo 3)
        return self._generate_single_frame_video(
            frame=row.start_frame_path,
            prompt=row.start_prompt,
            duration=row.duration
        )
    else:
        # Start+End video (Veo 3.1)
        return self._generate_start_end_video(
            start_frame=row.start_frame_path,
            end_frame=row.end_frame_path,
            prompt=row.end_prompt or row.start_prompt,
            duration=row.duration
        )

def _generate_start_end_video(
    self,
    start_frame: Path,
    end_frame: Path,
    prompt: str,
    duration: float
) -> Path:
    """
    Generate video using Veo 3.1 with start and end frames.

    Args:
        start_frame: Starting frame image
        end_frame: Ending frame image
        prompt: Description (usually of the transition/end state)
        duration: Video length in seconds

    Returns:
        Path to generated video
    """
    # Validate aspect ratios match
    if not self._validate_aspect_ratios(start_frame, end_frame):
        raise ValueError("Start and end frames must have matching aspect ratios")

    # Call Google provider
    provider = get_provider('google')

    operation = provider.client.models.generate_videos(
        model="veo-3.1-generate-preview",
        prompt=prompt,
        image=self._load_image(start_frame),
        config=GenerateVideosConfig(
            last_frame=self._load_image(end_frame),
            aspect_ratio=self._get_aspect_ratio(start_frame),
        ),
    )

    # Poll for completion
    while not operation.done:
        time.sleep(15)
        operation = provider.client.operations.get(operation)

    # Save video
    video_data = operation.response.videos[0].video
    output_path = self.project_dir / "videos" / f"row_{row.index}.mp4"
    output_path.write_bytes(video_data)

    return output_path
```

### Auto-Link Logic

**File**: `gui/video_tab.py`

```python
def generate_video_with_auto_link(self, row_index: int):
    """
    Generate video for row, applying auto-link if enabled.

    Args:
        row_index: Index of row to generate video for
    """
    row = self.rows[row_index]

    # Apply auto-link if enabled and no manual end frame
    if self.auto_link_enabled and row.end_frame_path is None:
        next_row_index = row_index + 1

        if next_row_index < len(self.rows):
            next_row = self.rows[next_row_index]

            if next_row.start_frame_path is not None:
                # Copy next row's start frame as this row's end frame
                row.end_frame_path = next_row.start_frame_path
                row.end_frame_auto_linked = True

                # Update UI to show auto-link indicator
                self.update_end_frame_button(row_index, auto_linked=True)

                logger.info(f"Row {row_index} end frame auto-linked to Row {next_row_index} start frame")

    # Generate video (will use Veo 3.1 if end frame exists)
    video_path = self.video_generator.generate_video_for_row(row)
    row.video_path = video_path

    # Update UI
    self.update_video_button(row_index)

    # Show success message
    self.show_notification(f"Video generated for Row {row_index}")
```

### LLM Prompt Generator

**File**: `core/llm/end_prompt_generator.py`

```python
class EndPromptGenerator:
    """Generate end frame prompts using LLM."""

    def generate_end_prompt(
        self,
        start_prompt: str,
        next_start_prompt: Optional[str] = None,
        duration: float = 6.0
    ) -> str:
        """
        Generate end frame description using LLM.

        Args:
            start_prompt: Starting scene description
            next_start_prompt: Next row's start prompt (if exists)
            duration: Video duration

        Returns:
            Generated end frame description
        """
        system_prompt = """You are a video transition specialist. Generate a description
for the END FRAME of a video that starts with the given prompt.

The end frame should naturally transition toward the next scene if provided.

Describe what the final frame should look like - focus on the visual elements,
not camera movement. The Veo API will handle the transition animation.

Format: 1-2 sentences describing the end state."""

        if next_start_prompt:
            user_prompt = f"""Create an end frame description:

Starting frame: "{start_prompt}"
Next scene starts with: "{next_start_prompt}"
Duration: {duration} seconds

Describe the ending frame that bridges these scenes."""
        else:
            user_prompt = f"""Create an end frame description:

Starting frame: "{start_prompt}"
Duration: {duration} seconds

Describe a natural ending frame for this scene."""

        try:
            response = self.llm_client.complete(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.8,
                max_tokens=150
            )

            return response.content.strip()

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Fallback
            if next_start_prompt:
                return f"transitioning from {start_prompt} toward {next_start_prompt}"
            else:
                return f"{start_prompt} with natural conclusion"
```

## UI Components

### End Prompt Widget

```python
class EndPromptWidget(QWidget):
    """Widget for end prompt column with LLM button."""

    def __init__(self, row_index: int):
        super().__init__()
        self.row_index = row_index

        layout = QHBoxLayout()

        # Text input
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Optional: describe ending frame")
        layout.addWidget(self.prompt_input, stretch=1)

        # LLM button
        self.llm_button = QPushButton("✨")
        self.llm_button.setToolTip("Generate end prompt with LLM")
        self.llm_button.setFixedWidth(30)
        self.llm_button.clicked.connect(self.show_llm_dialog)
        layout.addWidget(self.llm_button)

        self.setLayout(layout)

    def show_llm_dialog(self):
        """Open LLM generation dialog."""
        start_prompt = self.get_start_prompt(self.row_index)
        next_prompt = self.get_next_start_prompt(self.row_index)

        dialog = LLMEndPromptDialog(
            start_prompt=start_prompt,
            next_prompt=next_prompt,
            parent=self
        )

        if dialog.exec_() == QDialog.Accepted:
            generated_prompt = dialog.get_prompt()
            self.prompt_input.setText(generated_prompt)
```

### Frame Button with Hover Preview

```python
class FrameButton(QPushButton):
    """Button for start/end frame with hover preview."""

    def __init__(self, frame_path: Optional[Path] = None):
        super().__init__()
        self.frame_path = frame_path
        self.preview_widget = None

        self.update_appearance()

    def update_appearance(self):
        """Update button icon/text based on state."""
        if self.frame_path:
            self.setIcon(QIcon(":/icons/image.png"))
            self.setText("")
        else:
            self.setText("➕")
            self.setIcon(QIcon())

    def enterEvent(self, event):
        """Show preview on hover."""
        if self.frame_path and self.frame_path.exists():
            self.show_preview()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hide preview on mouse leave."""
        self.hide_preview()
        super().leaveEvent(event)

    def show_preview(self):
        """Show 200x200px thumbnail preview."""
        if not self.preview_widget:
            self.preview_widget = QLabel(self, Qt.ToolTip)
            self.preview_widget.setFixedSize(200, 200)

        pixmap = QPixmap(str(self.frame_path)).scaled(
            200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.preview_widget.setPixmap(pixmap)

        # Position near cursor
        cursor_pos = QCursor.pos()
        self.preview_widget.move(cursor_pos + QPoint(20, 20))
        self.preview_widget.show()

    def hide_preview(self):
        """Hide preview."""
        if self.preview_widget:
            self.preview_widget.hide()
```

## Implementation Phases

### Phase 1: UI and Data Model (12-15 hours)

**Tasks:**
1. Add End Prompt and End Frame columns to storyboard table (3-4 hours)
   - Wide End Prompt column with LLM button
   - End Frame icon button column
   - Narrow Time column (40-50px)

2. Update StoryboardRow dataclass (1-2 hours)
   - Add end_prompt, end_frame_path, end_frame_auto_linked fields
   - Update JSON serialization

3. Implement frame button with hover preview (3-4 hours)
   - 200x200px thumbnail popup on hover
   - Click opens full viewer
   - Right-click menu with Clear option

4. Add auto-link checkbox at top (2-3 hours)
   - Toggle functionality
   - UI state management

5. Add right-click Clear menus (2-3 hours)
   - Clear on start frame, end frame, video buttons
   - Confirmation dialogs

**Deliverables:**
- New storyboard layout with all columns
- Hover previews working
- Data model supports end frames
- Auto-link checkbox (UI only, logic in Phase 2)

### Phase 2: LLM Integration (8-10 hours)

**Tasks:**
1. Create EndPromptGenerator class (3-4 hours)
   - LLM client integration
   - System/user prompts
   - Fallback generation

2. Build LLM dialog UI (3-4 hours)
   - Show start/next prompts
   - Display generated prompt
   - Edit, regenerate, use buttons

3. Wire up ✨ button (2-3 hours)
   - Call LLM generator
   - Handle errors
   - Insert prompt into field

**Deliverables:**
- LLM generates end prompts
- Dialog UI complete
- Fallback for no LLM

### Phase 3: Veo 3.1 API Integration (10-12 hours)

**Tasks:**
1. Update Google provider (4-5 hours)
   - Add Veo 3.1 API call with last_frame parameter
   - Handle operation polling
   - Error handling

2. Update video generator (3-4 hours)
   - Add generate_video_for_row() method
   - Route to Veo 3 or Veo 3.1 based on end frame
   - Validate aspect ratios

3. Implement auto-link logic (3-4 hours)
   - Check for next row's start frame
   - Copy as end frame if auto-link enabled
   - Update UI indicators

4. Test end-to-end (1-2 hours)
   - Generate single-frame videos
   - Generate start+end videos
   - Verify auto-linking

**Deliverables:**
- Veo 3.1 integration working
- Auto-link fully functional
- Videos generate correctly with both modes

### Phase 4: Polish and Testing (8-10 hours)

**Tasks:**
1. Add pop-up on end frame generation (2-3 hours)
   - Show preview dialog when end frame generated
   - Same style as existing image generation popup

2. Visual indicators (2-3 hours)
   - Show 🔗 for auto-linked frames
   - Tooltips explaining state
   - Video button shows single vs start+end

3. Error handling (2-3 hours)
   - Aspect ratio mismatch warnings
   - Missing frames validation
   - API error messages

4. Testing (2-3 hours)
   - All workflows
   - Edge cases
   - UI responsiveness

**Deliverables:**
- Polished UI with all indicators
- Comprehensive error handling
- Fully tested feature

## Total Estimate

**Phase 1**: 12-15 hours (UI & Data Model)
**Phase 2**: 8-10 hours (LLM)
**Phase 3**: 10-12 hours (Veo 3.1 API)
**Phase 4**: 8-10 hours (Polish & Testing)

**Total**: 38-47 hours (~1 week full-time)

## Key Implementation Notes

### No Changes to Existing Workflow

**Important**: This feature adds optional capabilities without breaking current behavior:

- **Existing code unchanged**: Single-frame video generation still works exactly the same
- **Backward compatible**: Old projects without end frames still load and work
- **Optional feature**: Users can ignore end frame columns and use current workflow
- **Same concatenation**: Final video assembly unchanged

### Veo 3 vs Veo 3.1 Selection

**Automatic routing based on row state:**

```python
if row.end_frame_path is None:
    use_veo_3()  # Current behavior
else:
    use_veo_31()  # New behavior
```

### Auto-Link is Simple

**Not complex dependency chains:**

- Just copies next row's start frame as this row's end frame
- Happens at video generation time
- No complex tracking or updates
- Visual indicator shows it's auto-linked

### LLM is Optional

**Three ways to get end prompt:**

1. User types it manually
2. User clicks LLM button (if LLM configured)
3. User leaves it empty (uses start prompt)

## Success Metrics

**User Experience:**
- Users can optionally add end frames to create evolving videos
- Auto-link makes seamless projects with one checkbox
- LLM helps users craft good transitions
- Hover previews provide quick visual feedback

**Technical:**
- No breaking changes to existing workflow
- Clean routing between Veo 3 and Veo 3.1
- Auto-link works reliably
- Performance remains good

**Quality:**
- Videos smoothly transition from start to end frames
- Auto-linked projects have no jump cuts
- Aspect ratio validation prevents errors

## API Reference

### Veo 3.1 Documentation
- [Gemini API - Generate Videos](https://ai.google.dev/gemini-api/docs/video)
- [Veo 3.1 Release Blog](https://blog.google/technology/ai/veo-updates-flow/)
- [Introducing Veo 3.1 - Developers Blog](https://developers.googleblog.com/en/introducing-veo-3-1-and-new-creative-capabilities-in-the-gemini-api/)
- [Vertex AI - First and Last Frames](https://cloud.google.com/vertex-ai/generative-ai/docs/video/generate-videos-from-first-and-last-frames)

### Technical Specs
- **Model**: `veo-3.1-generate-preview`
- **Resolution**: 720p or 1080p
- **Frame Rate**: 24fps
- **Duration**: 4, 6, or 8 seconds
- **Aspect Ratios**: 16:9, 9:16, 1:1
- **Pricing**: $0.15/sec (Fast), $0.40/sec (Standard)

## Examples

### Example 1: Nature Documentary Style

**Row 1:**
- Start: "butterfly on flower, morning dew"
- End: "butterfly taking flight, wings spread"
- Video: 6 seconds, butterfly emerges and flies

**Row 2:**
- Start: "butterfly flying through garden"
- End: "butterfly landing on new flower"
- Video: 6 seconds, flight to landing

**Result**: Each video has internal evolution, natural progression

### Example 2: Auto-Linked Music Video

**Enable auto-link, then:**

**Row 1:**
- Start: "singer in spotlight, dramatic lighting"
- End: AUTO-LINK (uses Row 2 start)
- Video: Ends exactly where Row 2 starts

**Row 2:**
- Start: "singer on stage, crowd visible"
- End: AUTO-LINK (uses Row 3 start)
- Video: Ends exactly where Row 3 starts

**Row 3:**
- Start: "crowd cheering, hands up"
- End: "confetti falling, celebration"
- Video: Final scene with evolution

**Result**: Seamless music video with no jump cuts

### Example 3: Mixed Approach

**Row 1:** Start only → Static establishing shot (Veo 3)
**Row 2:** Start + End → Action sequence (Veo 3.1)
**Row 3:** Start + Auto-link → Transitions to Row 4 (Veo 3.1)
**Row 4:** Start + End → Finale (Veo 3.1)

**Result**: Strategic use of both single-frame and evolving shots

---

**Status**: Plan ready for implementation. Adds optional end frame support without changing existing workflow. Estimated: 1 week full-time (38-47 hours).

**Next Steps**: Review plan, approve approach, begin Phase 1 (UI and Data Model).
