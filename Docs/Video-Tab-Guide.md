# Video Tab Guide

Comprehensive guide to the Video Project tab in ImageAI, covering the complete workflow from text/lyrics to rendered video.

---

## Table of Contents

- [Top-Down Workflow](#top-down-workflow)
- [Generation Settings](#generation-settings)
  - [Enable Visual Continuity](#enable-visual-continuity)
  - [Enhanced Storyboard](#enhanced-storyboard)
  - [Continuity Mode](#continuity-mode)
  - [Other Settings](#other-settings)
- [Storyboard Details](#storyboard-details)
  - [Scene Table Columns](#scene-table-columns)
  - [Prompt Enhancement](#prompt-enhancement)
  - [Frame Management](#frame-management)
- [Video Export](#video-export)
  - [FFmpeg Slideshow](#ffmpeg-slideshow)
  - [Veo Video Generation](#veo-video-generation)
- [All Controls Reference](#all-controls-reference)

---

## Top-Down Workflow

The Video tab follows a sequential workflow from text input to final rendered video:

### 1. Project Setup
1. **Create/Open Project**: Use the project header to create new or open existing projects
   - **New**: Creates a fresh project
   - **Open**: Load a previously saved project by name
   - **Browse**: View all projects in a list dialog
   - **Save/Save As**: Persist your work

2. **Configure LLM Provider**: Select the AI provider for prompt enhancement
   - Choose provider: Google, OpenAI, Anthropic, or None
   - Select specific model from the Model dropdown
   - This applies globally to all prompt enhancement operations

### 2. Input Your Content

**Input Panel** (left side):
1. **Format**: Choose how your text is formatted
   - **Auto-detect**: Automatically detects timestamps and structure
   - **Timestamped**: Text with `[MM:SS]` timestamps like `[00:15] First line of lyrics`
   - **Structured**: JSON or structured data (advanced)
   - **Plain text**: Unformatted lyrics or narration

2. **Load File** or paste text directly into the text area
   - Supports `.txt`, `.lrc`, `.srt`, and other text formats
   - Paste lyrics, narration, or scene descriptions

3. **Set Timing**:
   - **Target Length**: Total video duration in seconds (10-600s)
   - **Pacing**: Scene transition speed
     - **Fast**: Quick cuts, energetic (3-5s per scene)
     - **Medium**: Balanced (5-8s per scene)
     - **Slow**: Contemplative, longer scenes (8-12s per scene)
   - **Match Target** ☑️: (For manual storyboards without MIDI)
     - **Checked**: LLM scales scene durations to match target length
     - **Unchecked**: LLM uses natural timing estimates
     - Only applies when using LLM timing estimation (no MIDI file)

4. **Generate Storyboard**: Breaks your text into timed scenes
   - Creates a scene for each line of text
   - Distributes timing based on pacing and target length
   - Populates the Scene Table with your content

### Advanced Timing Options

#### Explicit Duration Syntax

You can specify exact durations for individual scenes using **`[Xs]` markers** in your input text:

**Prefix format**:
```
[5s] Wide shot of cityscape at sunset
[3s] Quick cut to character's face
[8s] Slow pan across the room
```

**Suffix format**:
```
Wide shot of cityscape at sunset [5s]
Quick cut to character's face [3s]
Slow pan across the room [8s]
```

**Features**:
- Supports both whole numbers (`[5s]`) and decimals (`[5.5s]`)
- Mix explicit timing with LLM-estimated scenes
- LLM will estimate timing for scenes without `[Xs]` markers
- Explicit timing overrides all other duration calculations

**Example - Mixed Mode**:
```
[5s] Opening establishing shot (exactly 5 seconds)
Main dialogue scene (LLM will estimate duration)
Action sequence (LLM will estimate duration)
[3s] Quick reaction shot (exactly 3 seconds)
[8s] Closing wide shot (exactly 8 seconds)
```

#### LLM Timing Estimation (No MIDI)

When no MIDI file is loaded, ImageAI can use an LLM to estimate realistic timing:

1. **Select LLM Provider and Model** in settings
2. **Enter scene descriptions** (plain text format)
3. **Check/uncheck "Match Target"**:
   - ✅ **Checked**: LLM estimates durations, then scales to match target length
   - ⬜ **Unchecked**: LLM freely estimates optimal duration per scene
4. **Click "Generate Storyboard"**

The LLM analyzes each scene description and estimates duration based on:
- Scene complexity (simple vs. complex action)
- Action described (quick cuts vs. slow pans vs. establishing shots)
- Typical video pacing (2-12 seconds per scene)
- Veo 3 clip generation constraints (8-second batches)

**Status messages**:
- `⏱️ Estimating scene timing with [Provider]/[Model]...` - LLM is analyzing scenes
- `📏 Target duration: Xs` - Shows target when "Match Target" is checked
- `✓ Found N scenes with explicit [Xs] timing` - Shows count of explicit timings
- `✓ LLM estimated timing for N scenes` - Estimation complete

**Fallback behavior**: If LLM timing fails, falls back to even distribution based on pacing preset

### 3. Configure Generation Settings

**Generation Settings Panel**:

1. **Image Provider**: Select AI provider for image generation
   - **Google**: Gemini models (recommended for flexibility)
   - **OpenAI**: DALL-E models
   - **Stability**: Stable Diffusion models
   - **Local SD**: Local Stable Diffusion installation

2. **Image Model**: Specific model to use (auto-populated based on provider)

3. **Style**: Visual aesthetic for all images
   - Built-in styles: Cinematic, Artistic, Photorealistic, Animated, Noir, Documentary, etc.
   - **+ button**: Manage custom styles (add, edit, delete)
   - **(Custom)**: Freeform text input for unique styles

4. **Aspect Ratio**: Video dimensions
   - **16:9**: Widescreen landscape (YouTube, TV)
   - **9:16**: Vertical portrait (TikTok, Instagram Stories)
   - **1:1**: Square (Instagram posts)

5. **Resolution**: Output quality
   - **720p**: HD (1280x720) - faster, smaller files
   - **1080p**: Full HD (1920x1080) - higher quality

6. **Seed**: Reproducibility control
   - **-1 (Random)**: Different result each time
   - **Specific number**: Same result with same prompt

7. **Continuity**: Visual continuity for start frame generation
   - **None**: Each scene generated independently
   - **Style Only**: Matches lighting, colors, mood from previous frame
   - **Transition**: Full visual continuation from previous frame

8. **Negative Prompt**: Things to avoid (e.g., "blurry, low quality, text")

9. **Enable Visual Continuity**: Advanced consistency features (see [Enable Visual Continuity](#enable-visual-continuity))

10. **Enhanced Storyboard**: Advanced scene analysis (see [Enhanced Storyboard](#enhanced-storyboard))

### 4. Optional: Audio & MIDI

**Audio & MIDI Panel**:

1. **Audio File**: Background music/narration
   - **Browse**: Select `.mp3`, `.wav`, `.flac`, etc.
   - **Clear**: Remove audio
   - Audio is mixed into final video

2. **MIDI File**: Musical timing data
   - **Browse**: Select `.mid` or `.midi` file
   - **Extract Lyrics**: Pull embedded lyrics from MIDI
   - **Sync Mode**: Align scenes to musical structure
     - **None**: No MIDI sync
     - **Beat**: Align to beats
     - **Measure**: Align to measures (bars)
     - **Section**: Align to song sections
   - **Snap**: How strongly to snap to MIDI timing (0-100%)

3. **Audio Controls**:
   - **Volume**: 0-100%
   - **Fade In/Out**: Smooth audio transitions (0-5 seconds)

4. **Karaoke Options** (optional):
   - **Style**: Bouncing Ball, Highlight, Fade In
   - **Position**: Bottom, Top, Center
   - **Font Size**: 16-72 pt
   - **Export formats**: LRC, SRT, ASS subtitle files

### 5. Enhance Prompts (Storyboard Panel)

The **Storyboard** panel shows all scenes in a table with multiple enhancement options:

1. **Enhance All Prompts**: Uses LLM to create detailed image prompts from source text
   - Processes all scenes in a single batch API call
   - Generates vivid, detailed descriptions optimized for image generation
   - Fills the "Start Prompt" column

2. **Generate Video Prompts**: Adds camera movement and motion instructions
   - Uses LLM to add cinematic camera work
   - Optimizes prompts for Google Veo video generation
   - Fills the "Video Prompt" column
   - Examples: "slow zoom in", "camera pans left", "dolly shot forward"

3. **Per-Scene Enhancement**: Click ✨ button in any prompt field
   - Customize individual scenes
   - Regenerate if you don't like the result
   - Undo/Redo with ↶↷ buttons

### 6. Generate Images

**Generate Images** button creates visual content for all scenes:

1. Click **Generate Images** in Storyboard panel
2. For each scene:
   - Uses Image Provider + Model from settings
   - Generates image(s) based on Start Prompt
   - Applies Style, Aspect Ratio, Resolution
   - **If Continuity Mode is enabled** (not "None"):
     - For scene 2+: Analyzes previous scene's last frame
     - Extracts style information (lighting, colors, composition)
     - Incorporates into current scene's prompt
   - Saves images to project's `images/` directory
   - Creates thumbnails for quick preview

3. **Visual Continuity options**:
   - **Use last frame for continuous video**: Uses previous clip's last frame as seed for next clip
   - **Auto-link end frames (Veo 3.1)**: Automatically sets next scene's start as current scene's end frame

4. Click on scene row to preview generated image
5. Hover over 🖼️ icon for thumbnail preview

### 7. Generate Video Clips (Optional - Veo)

For video generation instead of static images:

1. **Video Export Panel** → Set **Video Provider** to "Gemini Veo"
2. **Select Veo Model**:
   - **veo-3.0-generate-001**: Highest quality, 4/6/8s clips, supports audio
   - **veo-3.0-fast-generate-001**: Faster generation, 5s max
   - **veo-2.0-generate-001**: Legacy model

3. **Generation Options**:
   - **Smooth Transitions**: Uses previous clip's last frame as next clip's seed (sequential chaining)
   - Automatically extracts first and last frames for each clip

4. **Generate video clips**:
   - Right-click scene row → "Generate Video Clip"
   - Or double-click 🎬 column
   - Uses Video Prompt (with camera movement)
   - Creates `.mp4` clip in project's `clips/` directory
   - Extracts first and last frames to `first_frames/` and `frames/`

5. Click 🎬 button to preview video (click once for first frame, click again to play)

### 8. Render Final Video

**Video Export Panel** (bottom right):

1. **Choose rendering method**:
   - **Video Provider: None** → FFmpeg slideshow with images
   - **Video Provider: Gemini Veo** → Concatenates Veo video clips

2. **FFmpeg Options** (if using images):
   - **Ken Burns Effect**: Slow zoom/pan on static images
   - **Transitions**: Crossfade between scenes
   - **Captions**: Overlay source text on video

3. **Click "Render Video"**:
   - **FFmpeg mode**: Creates slideshow from images with audio
   - **Veo mode**: Concatenates all video clips with audio
   - Saves final video to project directory
   - Filename: `ProjectName_YYYYMMDD_HHMMSS.mp4`

4. **Preview button**: Quick low-quality preview before final render

---

## Generation Settings

### Enable Visual Continuity

**Location**: Generation Settings → "Enable Visual Continuity" checkbox

**Purpose**: Maintains visual consistency across all scenes in your project using provider-specific techniques.

**How It Works**:

This is an advanced feature that goes beyond the basic "Continuity Mode" dropdown. When enabled, it uses specialized techniques based on your selected image provider:

- **Gemini (Google)**:
  - Uses **iterative refinement** with previous images
  - Each new scene generation includes context from previous scenes
  - Maintains consistent lighting, color palette, and artistic style
  - More computationally expensive but highest consistency

- **OpenAI (DALL-E)**:
  - Uses **reference IDs** for style consistency
  - DALL-E 3 can reference previous generation IDs
  - Maintains consistent character features and style
  - Faster than iterative refinement

- **Claude (Anthropic)**:
  - Uses **style guides and character descriptions**
  - Builds a cumulative style document
  - Each new prompt includes condensed style information
  - Good for maintaining narrative consistency

**When to Use**:
- ✅ Music videos or narratives with recurring characters/locations
- ✅ Story-driven projects requiring visual coherence
- ✅ Professional projects where consistency matters
- ❌ Abstract videos where variety is desired
- ❌ Quick experiments or drafts

**Performance Impact**:
- Adds 10-30% more generation time
- May use additional API credits depending on provider
- Results in more consistent visual narrative

**Interaction with Continuity Mode**:
- "Enable Visual Continuity" and "Continuity Mode" work together
- Continuity Mode (None/Style Only/Transition) controls frame-to-frame analysis
- Enable Visual Continuity adds provider-specific consistency techniques
- For maximum consistency: Enable both

---

### Enhanced Storyboard

**Location**: Generation Settings → "Enhanced Storyboard" checkbox

**Purpose**: Uses advanced storyboard generation with structured scene descriptions for more cinematic and narrative-driven results.

**Standard Storyboard** (checkbox OFF):
- Simple line-by-line breakdown
- One line of text = one scene
- Timing distributed evenly or by pacing
- Minimal scene analysis
- **Best for**: Lyrics, simple narration, quick projects

**Enhanced Storyboard** (checkbox ON):
- Advanced scene analysis with LLM
- Identifies:
  - Scene boundaries (even within paragraphs)
  - Key visual moments
  - Emotional beats
  - Narrative structure
- Suggests optimal scene durations based on content
- Creates structured scene metadata:
  - Setting/location
  - Characters/subjects
  - Mood/emotion
  - Camera suggestions
  - Lighting notes
- **Best for**: Scripts, stories, complex narratives, professional projects

**Example Comparison**:

**Standard Input:**
```
A lone astronaut floats in the vast emptiness of space.
Earth hangs in the distance, a blue marble against the void.
She reaches out, desperate to return home.
```

**Standard Storyboard**:
- Scene 1 (8s): "A lone astronaut floats in the vast emptiness of space."
- Scene 2 (8s): "Earth hangs in the distance, a blue marble against the void."
- Scene 3 (8s): "She reaches out, desperate to return home."

**Enhanced Storyboard**:
- **Scene 1** (6s):
  - **Source**: "A lone astronaut floats in the vast emptiness of space."
  - **Setting**: Deep space, black void with distant stars
  - **Subject**: Astronaut in white spacesuit, tethered
  - **Mood**: Isolation, loneliness
  - **Camera**: Wide shot establishing scale
  - **Lighting**: Harsh sunlight from one side, deep shadows

- **Scene 2** (10s):
  - **Source**: "Earth hangs in the distance, a blue marble against the void."
  - **Setting**: Same as Scene 1, but with Earth visible
  - **Subject**: Earth as background element, astronaut in foreground
  - **Mood**: Longing, perspective shift
  - **Camera**: Medium shot, astronaut looking toward Earth
  - **Transition**: Slow reveal of Earth as camera pans

- **Scene 3** (8s):
  - **Source**: "She reaches out, desperate to return home."
  - **Setting**: Close-up in space
  - **Subject**: Astronaut's gloved hand reaching toward Earth
  - **Mood**: Desperation, yearning
  - **Camera**: Close-up on hand with Earth in background (shallow DoF)
  - **Lighting**: Backlit by Earth's reflected light

**Performance Impact**:
- 20-40% more processing time for storyboard generation
- Uses additional LLM API calls for scene analysis
- Significantly better prompt quality for complex narratives
- More coherent pacing and scene transitions

**When to Use**:
- ✅ Story-based videos with narrative arcs
- ✅ Complex scripts or screenplays
- ✅ Professional/commercial projects
- ✅ Content requiring specific visual beats
- ❌ Simple lyric videos
- ❌ Abstract or experimental projects
- ❌ Quick drafts or tests

---

### Continuity Mode

**Location**: Generation Settings → "Continuity" dropdown

**Purpose**: Controls how each scene's start frame relates to the previous scene's last frame during image generation.

**Available Modes**:

1. **None**:
   - Each scene generated completely independently
   - No reference to previous frames
   - **Best for**: Varied, abstract videos; scene changes between different locations
   - **Example**: Music video with completely different visuals per lyric

2. **Style Only**:
   - Analyzes previous scene's last frame for visual style
   - Extracts and applies:
     - Lighting direction and quality
     - Color palette and saturation
     - Composition style
     - Mood and atmosphere
     - Artistic/rendering style (photorealistic, cartoon, 3D render, etc.)
   - Does NOT copy content/subjects
   - **Best for**: Maintaining aesthetic consistency while changing subjects
   - **Example**: Travel video showing different locations but same "golden hour" lighting

3. **Transition**:
   - Full visual continuation from previous frame
   - Analyzes previous frame's content AND style
   - Creates smooth visual evolution
   - LLM creates prompt that bridges previous frame to new content
   - **Best for**: Narrative continuity, smooth scene transitions, following a character
   - **Example**: Character walking through different rooms (continuous action)

**How It's Implemented**:

When Continuity Mode is "Style Only" or "Transition":

1. **For Scene 1**: No previous frame exists
   - Uses Style from Generation Settings directly
   - Example: "Cinematic style: [scene description]"

2. **For Scene 2+**: Previous scene's last frame exists
   - Sends previous frame image to LLM (StyleAnalyzer)
   - LLM analyzes image and returns style/transition information
   - **Style Only**: Returns style description (e.g., "Warm cinematic lighting with golden tones, medium shot composition, photorealistic rendering style")
   - **Transition**: Returns full scene prompt incorporating previous content (e.g., "Continue from previous frame showing astronaut floating. Camera slowly pans right to reveal Earth in the distance...")
   - This information is prepended/merged with scene's base prompt
   - Image generation uses enhanced prompt

**Technical Details**:

- Uses `StyleAnalyzer` class (`core/video/style_analyzer.py`)
- Supports Google Gemini, OpenAI GPT-4V, Anthropic Claude vision models
- Requires vision-capable LLM (uses same provider/model as Image Provider)
- Previous frame = last frame extracted from generated image or video clip
- Stored in project's `frames/` directory

**Performance Impact**:
- Adds LLM vision API call per scene (Scene 2 onwards)
- Approximately 2-5 seconds per scene overhead
- Higher API costs due to vision model usage
- Significantly better visual coherence

**Interaction with Other Features**:
- Works independently of "Enable Visual Continuity"
- Complements "Use last frame for continuous video" (Veo)
- Used during START FRAME generation, not video generation

---

### Other Settings

#### Negative Prompt
**Purpose**: Describe what you DON'T want in images
**Examples**:
- "blurry, low quality, watermark, text, signatures"
- "distorted faces, extra limbs, anatomical errors"
- "modern elements, cars, technology" (for historical scenes)

**How it works**:
- Passed to image generation API
- Provider-specific implementation:
  - **Stable Diffusion**: Native negative prompt support
  - **DALL-E**: Incorporated into positive prompt as exclusions
  - **Gemini**: Used as guidance for what to avoid

---

## Storyboard Details

### Scene Table Columns

The scene table has 10 columns optimized for Veo 3.1 workflow:

| Column | Name | Description |
|--------|------|-------------|
| **#** | Scene Number | Sequential scene index (1, 2, 3...) |
| **Start Frame** | Start Frame Image | First frame for video generation<br>- 🖼️ = Image exists (hover for preview)<br>- Click to view full size<br>- Right-click for options (Upload, Select from history, Generate with LLM) |
| **End Frame** | End Frame Image | Last frame for Veo 3.1 interpolation<br>- Optional for single-frame video<br>- Required for frame-to-frame interpolation<br>- Right-click for same options as Start Frame |
| **🎬** | Video Button | Video clip control<br>- ⬜ = No video<br>- 🎞️ = Video exists<br>- Click once = Show first frame<br>- Click again = Play video<br>- Double-click = Regenerate video |
| **Time** | Duration | Scene duration in seconds<br>- Editable by clicking<br>- Used for timing calculations<br>- Veo requires 4, 6, or 8 seconds |
| **⤵️** | Wrap Toggle | Toggle word wrap for this row<br>- Unwrapped (default): Single line with ellipsis<br>- Wrapped: Full text visible, row expands |
| **Source** | Original Text | Input lyrics/narration line<br>- Read-only display of source material |
| **Start Prompt** | Image Generation Prompt | Detailed description for start frame image<br>- ✨ button: Generate with LLM<br>- ↶↷ buttons: Undo/Redo edits<br>- Editable field for manual refinement |
| **End Prompt** | End Frame Prompt | Optional prompt for end frame (Veo 3.1)<br>- Leave empty for Veo 3 (single frame)<br>- Use for frame-to-frame interpolation<br>- ✨/↶↷ buttons same as Start Prompt |
| **Video Prompt** | Motion & Camera Prompt | Enhanced prompt with camera movement<br>- Generated by "Generate Video Prompts" button<br>- Includes camera work (pan, zoom, dolly, etc.)<br>- ✨/↶↷ buttons for LLM and undo/redo |

**Table Features**:

1. **Hover Preview**: Hover over 🖼️ icon to see thumbnail
2. **Click to View**: Click Start Frame or End Frame to display full-size
3. **Resizable Columns**: Drag column borders to resize
   - Double-click header to auto-fit
   - Ctrl+Double-click to auto-fit ALL columns
4. **Row Height**: Fixed height for consistency (wrapping expands internally)
5. **No Auto-Scroll**: Prevents annoying jumping while editing
6. **Word Wrap Toggle**: Per-row control for long prompts

---

### Prompt Enhancement

Each prompt field (Start Prompt, End Prompt, Video Prompt) has enhancement tools:

#### ✨ LLM Generation Button

**Start Prompt**:
- Opens "Generate Start Frame Prompt" dialog
- Shows:
  - Source text (original lyric/narration)
  - Current prompt (if exists)
  - Continuity mode indicator
- Generates detailed visual description using selected LLM
- If Continuity Mode enabled:
  - Analyzes previous frame (Scene 2+)
  - Incorporates style/transition information
- Result appears in dialog for review/edit
- Click OK to apply, Cancel to keep original

**End Prompt**:
- Opens "Generate End Frame Prompt" dialog
- Shows:
  - Current scene's start prompt
  - Next scene's start prompt (if exists)
  - Duration
- Generates ending frame that transitions to next scene
- Creates smooth visual bridge between scenes
- Uses LLM to imagine logical progression

**Video Prompt**:
- Opens "Generate Video Prompt" dialog
- Shows:
  - Start frame prompt
  - Duration
- Generates camera movement and motion instructions
- Optimized for Google Veo
- Examples of output:
  - "Camera slowly pans left while zooming in slightly"
  - "Dolly shot moving forward, subject remains center frame"
  - "Slow tilt up revealing the sky, gentle ambient motion"

#### ↶↷ Undo/Redo Buttons

- Each prompt field maintains its own history
- **↶ Undo**: Reverts to previous version
- **↷ Redo**: Re-applies undone change
- Unlimited undo/redo depth
- Persists across save/load
- Useful for comparing LLM variations

---

### Frame Management

Start Frame and End Frame columns support multiple input methods:

#### Right-Click Menu Options:

1. **Upload Image**:
   - Browse for image file on disk
   - Supports: PNG, JPG, JPEG, BMP, GIF, WEBP
   - Image copied to project's `images/` directory
   - Thumbnail generated automatically

2. **Select from History**:
   - Opens dialog showing all generated images
   - Images from current project or main Generate tab
   - Click to select
   - Useful for reusing previous generations

3. **Generate with LLM** (Start Frame only):
   - Opens Start Prompt dialog
   - Generates prompt, then generates image
   - All in one workflow

4. **Clear Frame**:
   - Removes frame reference
   - Keeps image file on disk
   - Allows reassignment

#### Automatic Frame Extraction:

When video clips are generated:
- **First Frame**: Extracted from video start → `first_frames/scene_XXX_first_frame.png`
- **Last Frame**: Extracted from video end → `frames/scene_XXX_last_frame.png`
- Automatically assigned to scene
- Used for sequential chaining

---

## Video Export

Two rendering methods available:

### FFmpeg Slideshow

**When to Use**: When using generated images (not video clips)

**Video Export Settings**:
- Video Provider: **None**
- Ken Burns Effect: ✓ Enabled for slow zoom/pan on images
- Transitions: ✓ Enabled for crossfades between scenes
- Captions: ✓ Enabled to overlay source text

**How It Works**:
1. Collects all approved/generated images from scenes
2. Calculates timing based on scene durations
3. Applies Ken Burns effect (slow zoom/pan) if enabled
   - Random direction per scene
   - Subtle 10% zoom over duration
4. Creates crossfade transitions between scenes (0.5s default)
5. Overlays captions if enabled
   - Source text appears as subtitle
   - Positioned at bottom center
   - Fades in/out with scene
6. Mixes background audio at specified volume
7. Outputs final MP4 with H.264 video, AAC audio

**Output Location**: `ProjectDirectory/ProjectName_YYYYMMDD_HHMMSS.mp4`

**Settings**:
- Resolution: From Generation Settings (720p/1080p)
- FPS: 24 (default for cinematic look)
- Aspect Ratio: From Generation Settings
- Bitrate: Auto-calculated based on resolution

---

### Veo Video Generation

**When to Use**: When using Google Veo for AI-generated video clips

**Video Export Settings**:
- Video Provider: **Gemini Veo**
- Select Veo Model:
  - **veo-3.0-generate-001**: Best quality, 4/6/8s clips, audio support
  - **veo-3.0-fast-generate-001**: Faster, 5s max, no audio
  - **veo-2.0-generate-001**: Legacy
- Smooth Transitions: Uses previous clip's last frame as seed

**Workflow**:

1. **Per-Scene Video Generation**:
   - Right-click scene → "Generate Video Clip"
   - Or double-click 🎬 column
   - Uses Video Prompt (with camera movement)
   - Optional: Start Frame and End Frame for interpolation
   - Veo generates 4/6/8 second clip (duration snapped to Veo requirements)
   - Clip saved to `clips/scene_X_timestamp.mp4`
   - First and last frames extracted automatically

2. **Smooth Transitions** (Checkbox):
   - When enabled: Uses Scene N's last frame as Scene N+1's start frame
   - Creates seamless transitions between clips
   - Sequential chaining: Each clip flows into the next
   - Best for continuous narrative

3. **Auto-Link End Frames** (Veo 3.1):
   - Automatically assigns Scene N+1's start frame as Scene N's end frame
   - Enables frame-to-frame interpolation
   - Veo 3.1 generates smooth transition between two frames
   - Creates ultra-smooth scene changes

4. **Final Render**:
   - Click "Render Video"
   - Concatenates all video clips in sequence
   - Mixes background audio
   - Adjusts timing if clips don't match scene durations exactly
   - Removes audio from clips (uses background audio only)
   - Outputs final MP4

**Veo-Specific Considerations**:

- **Duration Snapping**: Veo requires 4, 6, or 8 second clips
  - If scene is 7s, Veo generates 6s or 8s
  - Warning shown in status console
- **Aspect Ratio Matching**:
  - Start/End frames must match requested aspect ratio
  - If mismatch detected, transparent canvas centering applied automatically
- **Generation Time**: 1-6 minutes per clip
  - Fast model: 11-60 seconds
- **Regional Restrictions**:
  - Person generation restricted in some countries (MENA, some EU)
  - Detected automatically
- **Cost**: ~$0.10 per second (Veo 3 Generate)

---

## All Controls Reference

### Project Header
| Control | Type | Description |
|---------|------|-------------|
| Project Name | Text Input | Project name (editable) |
| New | Button | Create new project |
| Open | Button | Load project by name |
| Browse | Button | View all projects in list |
| Save | Button | Save current project |
| Save As | Button | Save with new name |

---

### LLM Provider Panel
| Control | Type | Description |
|---------|------|-------------|
| LLM Provider | Combo | AI provider for prompts (Google, OpenAI, Anthropic, None) |
| Model | Combo | Specific LLM model (auto-populated) |

---

### Input Panel
| Control | Type | Description | Values/Options |
|---------|------|-------------|----------------|
| Format | Combo | Input text format | Auto-detect, Timestamped, Structured, Plain text |
| Load File | Button | Load text from file | Supports .txt, .lrc, .srt, etc. |
| Input Text | Text Area | Paste lyrics/narration | Multiline text input |
| Target Length | Spin | Total video duration | 10-600 seconds |
| Pacing | Combo | Scene speed | Fast, Medium, Slow |
| Generate Storyboard | Button | Create scene breakdown | Populates scene table |

---

### Generation Settings Panel
| Control | Type | Description | Values/Options |
|---------|------|-------------|----------------|
| Image Provider | Combo | Image generation service | Google, OpenAI, Stability, Local SD |
| Image Model | Combo | Specific model | Auto-populated per provider |
| Style | Combo | Visual aesthetic | Built-in styles + custom |
| + (Manage Styles) | Button | Add/edit custom styles | Opens style manager dialog |
| Custom Style | Text Input | Freeform style text | Shown when "(Custom)" selected |
| Aspect Ratio | Combo | Video dimensions | 16:9, 9:16, 1:1 |
| Resolution | Combo | Output quality | 720p, 1080p |
| Seed | Spin | Reproducibility | -1 (Random) or 0-999999 |
| Continuity | Combo | Frame-to-frame mode | None, Style Only, Transition |
| Negative | Text Input | Avoid in images | Freeform text |
| Enable Visual Continuity | Checkbox | Provider-specific consistency | Off/On |
| Enhanced Storyboard | Checkbox | Advanced scene analysis | Off/On |

---

### Audio & MIDI Panel
| Control | Type | Description | Values/Options |
|---------|------|-------------|----------------|
| Audio File | Label + Button | Background music | Browse for .mp3, .wav, .flac |
| Clear Audio | Button | Remove audio | Clears selection |
| MIDI File | Label + Button | Musical timing | Browse for .mid, .midi |
| Clear MIDI | Button | Remove MIDI | Clears selection |
| MIDI Info | Label | File details | Shows tempo, time sig, track count |
| Sync Mode | Combo | Timing alignment | None, Beat, Measure, Section |
| Snap Strength | Slider | Sync intensity | 0-100% |
| Extract Lyrics | Button | Pull MIDI lyrics | Populates input text |
| Volume | Slider | Audio level | 0-100% |
| Fade In | Spin | Audio fade in | 0-5 seconds |
| Fade Out | Spin | Audio fade out | 0-5 seconds |

**Karaoke Options** (expandable):
| Control | Type | Description | Values/Options |
|---------|------|-------------|----------------|
| Enable Karaoke | Checkbox | Show karaoke panel | Off/On |
| Style | Combo | Visual style | Bouncing Ball, Highlight, Fade In |
| Position | Combo | Text location | Bottom, Top, Center |
| Font Size | Spin | Text size | 16-72 points |
| Export LRC | Checkbox | LRC subtitle file | Off/On |
| Export SRT | Checkbox | SRT subtitle file | Off/On |
| Export ASS | Checkbox | ASS subtitle file | Off/On |

---

### Storyboard Panel
| Control | Type | Description |
|---------|------|-------------|
| Enhance All Prompts | Button | LLM batch prompt generation for images |
| Generate Video Prompts | Button | Add camera movement to all prompts |
| Generate Images | Button | Create images for all scenes |
| Use last frame for continuous video | Checkbox | Chain clips with last frame as seed |
| Auto-link end frames (Veo 3.1) | Checkbox | Set next start as current end frame |
| Total Duration | Label | Calculated total video length |

**Scene Table** - See [Scene Table Columns](#scene-table-columns) above

---

### Video Export Panel
| Control | Type | Description | Values/Options |
|---------|------|-------------|----------------|
| Video Provider | Combo | Rendering method | None (FFmpeg), Gemini Veo |
| Veo Model | Combo | Veo version | veo-3.0-generate-001, veo-3.0-fast-generate-001, veo-2.0-generate-001 |
| Ken Burns Effect | Checkbox | Slow zoom/pan on images | Off/On (FFmpeg only) |
| Transitions | Checkbox | Crossfade between scenes | Off/On (FFmpeg only) |
| Captions | Checkbox | Overlay source text | Off/On (FFmpeg only) |
| Smooth Transitions | Checkbox | Use last frame as seed | Off/On (Veo only) |
| Preview | Button | Low-quality preview render | Creates preview.mp4 |
| Render Video | Button | Final high-quality render | Creates final .mp4 |

---

### Media Viewer (Bottom Panel)
| Control | Type | Description |
|---------|------|-------------|
| Image View | Label | Displays generated images |
| Video Player | Widget | Plays video clips |
| ▶ Play / ⏸ Pause | Button | Control playback |
| 🔇 Unmute / 🔊 Mute | Button | Toggle audio |
| Position Slider | Vertical Slider | Seek through video |
| Time Label | Label | Current / Total time |

---

### Status Console
| Element | Description |
|---------|-------------|
| Status Console | Terminal-style log output |
| - Shows all LLM interactions |
| - Displays generation progress |
| - Logs errors and warnings |
| - Color-coded messages (INFO, SUCCESS, ERROR) |

---

### Wizard Panel (Left Side, Collapsible)
| Control | Type | Description |
|---------|------|-------------|
| ◀ Hide / ▶ Show | Button | Toggle wizard visibility |
| Workflow Steps | Interactive Guide | Shows current workflow stage |
| - Highlights active step |
| - Checkmarks for completed steps |
| - Click to jump to step |

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+N | New project |
| Ctrl+O | Open project |
| Ctrl+S | Save project |
| Ctrl+Shift+S | Save As |
| Ctrl+Enter | Confirm dialog (when in dialog) |
| Escape | Cancel dialog / Close dialog |
| Space | Play/Pause video (when video viewer focused) |
| Ctrl+Z | Undo (in prompt fields) |
| Ctrl+Y | Redo (in prompt fields) |
| Double-click header | Auto-resize column |
| Ctrl+Double-click header | Auto-resize ALL columns |

---

## Tips & Best Practices

### For Best Results:

1. **Start with good source text**:
   - Clear, descriptive lines work better than vague phrases
   - Include visual details when possible
   - Structure matters: verses, choruses, narrative beats

2. **Use Enhanced Storyboard for narratives**:
   - Stories, scripts, complex videos benefit greatly
   - Simple lyrics can use standard storyboard

3. **Enable continuity features for consistency**:
   - "Enable Visual Continuity" + "Continuity Mode: Style Only" = cohesive look
   - "Continuity Mode: Transition" = smooth scene flow for narratives

4. **Experiment with styles**:
   - Try built-in styles first
   - Create custom styles for unique aesthetics
   - Save successful styles for reuse

5. **Review prompts before generating images**:
   - Click ✨ to generate LLM prompts
   - Edit if needed for specific vision
   - Undo/redo to compare variations

6. **Veo workflow**:
   - Generate images first (start frames)
   - Review and approve images
   - Then generate video clips using approved images
   - Use "Smooth Transitions" for continuous flow

7. **Audio integration**:
   - Add audio early to inform timing
   - Use MIDI sync for musical projects
   - Adjust scene durations to match audio beats

### Performance Optimization:

- **Batch operations are faster**: "Enhance All Prompts" uses 1 API call, not N calls
- **Preview before final render**: Use Preview button to check before long render
- **Save frequently**: Complex projects can be restored from history
- **Use lower resolution for drafts**: 720p renders faster, switch to 1080p for final

---

## Troubleshooting

### "No LLM provider available"
- Check API keys in Settings tab
- Select provider from LLM Provider dropdown
- Verify API key is valid (test in Generate tab)

### "Image generation failed"
- Check Image Provider API key
- Verify model selection is compatible with provider
- Review prompt for forbidden content (OpenAI moderation)
- Check negative prompt isn't too restrictive

### "Veo generation timeout"
- Veo can take 1-6 minutes per clip
- Fast model is quicker but lower quality
- Check internet connection
- Verify Google API key has Veo access

### "Aspect ratio mismatch warning"
- Start/End frames must match video aspect ratio
- Auto-correction applies transparent canvas
- Or manually resize images before uploading

### "Duration snapped to X seconds"
- Veo requires 4, 6, or 8 second clips
- Adjust scene durations to match Veo constraints
- Or use FFmpeg slideshow for arbitrary durations

### "Continuity analysis failed"
- Requires vision-capable LLM
- Verify LLM provider supports vision (Gemini, GPT-4V, Claude)
- Previous frame must exist (Scene 2+)
- Check previous scene has generated image or video

---

## File Structure

Projects are stored in `~/.imageai/video_projects/` (or platform equivalent):

```
ProjectName/
├── project.json              # Project metadata and scene data
├── images/                   # Generated images
│   ├── scene_0_timestamp_v0.png
│   ├── scene_0_timestamp_v1.png
│   └── ...
├── clips/                    # Generated video clips
│   ├── scene_0_timestamp.mp4
│   └── ...
├── frames/                   # Last frames extracted from videos
│   ├── scene_0_last_frame.png
│   └── ...
├── first_frames/             # First frames extracted from videos
│   ├── scene_001_first_frame.png
│   └── ...
├── temp/                     # Temporary processing files
│   └── canvas_seed_scene_0.png
└── ProjectName_timestamp.mp4 # Rendered final video
```

---

## Advanced Topics

### Custom Style Presets

Create reusable style definitions:

1. Click **+ button** next to Style dropdown
2. Click **Add** in Style Manager
3. Enter name and style description
4. Examples:
   - "Retro Synthwave: Neon colors, 1980s aesthetic, grid floors, purple/pink sunset, chromatic aberration"
   - "Anime Studio Ghibli: Hand-drawn animation style, watercolor backgrounds, soft colors, whimsical details"
   - "Noir Detective: Black and white, high contrast, venetian blind shadows, 1940s fashion, foggy streets"
5. Saved styles appear in Style dropdown
6. Edit or delete from Style Manager

### MIDI Sync Deep Dive

MIDI sync aligns scene changes to musical structure:

- **Beat**: Scene boundaries snap to nearest beat
- **Measure**: Scenes align to measure (bar) boundaries
- **Section**: Scenes align to major song sections (intro, verse, chorus, bridge, outro)
- **Snap Strength**:
  - 100% = Hard snap, scenes exactly on beats
  - 50% = Soft snap, gentle pull toward beats
  - 0% = No snap, original timing preserved

Best for:
- Music videos where visuals should hit on beats
- Karaoke videos (lyrics in sync with music)
- Rhythm-driven content

### Batch Processing Tips

For large projects (100+ scenes):

1. **Generate in chunks**: Select 10-20 scenes at a time
2. **Use saved checkpoints**: Save after each chunk completion
3. **Monitor API quotas**: Track usage to avoid rate limits
4. **Use lower quality for drafts**: Test with 720p before 1080p final
5. **Parallel workflows**: Generate prompts, then images, then videos separately

---

## Conclusion

The Video tab provides a powerful, AI-assisted workflow from text to polished video. Experiment with different settings, use the LLM enhancement tools, and leverage continuity features for professional results.

For questions or issues, check the logs in the Status Console and `imageai_current.log` file in the project directory.
