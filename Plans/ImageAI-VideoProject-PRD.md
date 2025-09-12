# 🎬 ImageAI – Video Project Feature (PRD & Build Plan)
*Version:* 1.0 • *Date:* 2025-09-11 20:30 UTC  
*Owner:* ImageAI • *Status:* Implementation Ready

Veo API reference: 
https://ai.google.dev/gemini-api/docs/video?example=dialogue

---

## 1) Overview
Add a **Video Project** workflow to ImageAI that turns **lyrics/text** into an **auto‑storyboard** → **AI-powered prompt generation** → **image generation** pipeline → **video assembly**.  

**Key Features:**
- **AI Prompt Generation**: Use Gemini or OpenAI to generate cinematic prompts from lyrics/text
- **Full Edit Control**: All AI-generated prompts are editable by the user
- **Comprehensive History**: Complete versioning system with time-travel restore capability
- **Image Generation**: Leverage existing providers (Gemini, OpenAI, Stable Diffusion/local)
- **Video Assembly**: Two paths:
  - **Gemini Veo API** (veo-3.0-generate-001): Generate 8-second AI video clips
  - **Local FFmpeg**: Create slideshow videos with Ken Burns effects and transitions

**Out of scope now:** beat detection/sync, TTS, automated song mixing (manual audio tracks ARE supported).

**Additional development data:** I used ChatGPT-5 to create lyrics, image prompts, and "Veo project." Everything is in the (project root) `./Sample/` folder. It shows examples of image prompts based on lyrics, and a template folder layout for each Veo scene. I don't care what format the output is in, since it will produce a valid MP4. So consider this an example. It *would* be nice to save projects so the user can switch between them, and always restore the same images/videos.

---

## 2) Goals & Non‑Goals
### ✅ Goals
- Paste lyrics/text (the same format you used in *My Country Tis of Thee*) or load from file.
- **AI-powered prompt generation** using Gemini or OpenAI LLMs with full user edit capability.
- Auto‑derive a **shotlist/storyboard** with scene durations that sum to either:
  - a user‑specified total length (e.g., 2:45), or
  - an auto‑estimate (based on line counts and pacing presets).
- Generate **N images** (per scene) using a selected **provider/model** (already wired in ImageAI).
- Human‑in‑the‑loop **review/approve/reorder/regenerate**.
- **Comprehensive version history** with time-travel restore to any previous state.
- **Custom audio support**: Link to any local audio file (MP3, WAV, M4A, etc.) without copying.
- **Render video** via:
  - **Gemini Veo API** (veo-3.0-generate-001): Generate 8-second AI video clips with optional audio.
  - **Local slideshow** (Ken Burns, crossfades, captions) with custom soundtrack.
- Save a **project file** (`.iaproj.json`) and all assets under a dedicated project folder.
- Keep detailed **metadata** for reproducibility & cost tracking.

### 🚫 Non‑Goals (initial)
- Vocal synthesis, automatic music generation.
- Advanced continuity (face/character locking across all scenes) beyond seed/prompt carry‑over.
- Multi‑track timelines; we'll ship a single-track MVP, then iterate.

---

## 3) AI Prompt Generation & Editing

### Prompt Generation Pipeline
1. **Input Analysis**: Parse lyrics/text to identify scenes and key elements
2. **LLM Enhancement**: Use cloud or local LLMs to generate cinematic prompts
3. **User Review**: Present generated prompts with inline editing capability
4. **Version Tracking**: Save all prompt versions (AI-generated and user-edited)

### LLM Provider Support
#### Cloud Providers
- **OpenAI** (GPT-4, GPT-4 Turbo, GPT-3.5)
- **Anthropic Claude** (Claude 3 Opus, Sonnet, Haiku)
- **Google Gemini** (Gemini Pro, Gemini Ultra)

#### Local LLM Support
- **Ollama** (Llama 3.1, Mistral, Mixtral, etc.)
- **LM Studio** (Any GGUF model via OpenAI-compatible API)
- **Direct Model Loading** (via llama.cpp bindings)

### Prompt Generation Features
- **Provider Selection**: Choose any cloud or local LLM for prompt generation
- **Unified Interface**: LiteLLM integration for consistent API across all providers
- **Style Templates**: Apply cinematic, artistic, or photorealistic styles
- **Batch Generation**: Generate all scene prompts in one operation
- **Regeneration**: Re-generate individual prompts while preserving others
- **Edit History**: Track all changes with diff visualization
- **Cost Optimization**: Use local LLMs for drafts, cloud for final generation

### Example Prompt Enhancement
```
Input: "My Country Tis of Thee"

Claude 3 Output: "Cinematic wide shot of an elderly man in worn denim overalls, 
sitting on a weathered porch in rural America, golden hour lighting casting long 
shadows, American flag gently waving, nostalgic 1960s aesthetic, Norman Rockwell 
style, weathered hands holding a coffee mug, distant fields visible"

Local Llama 3.1 Output: "Wide establishing shot: elderly gentleman on wooden 
porch, late afternoon sun, rural farmhouse, American heartland, vintage clothing, 
contemplative mood, documentary photography style"
```

### LLM Provider Implementation
```python
from litellm import completion

class UnifiedLLMProvider:
    """Single interface for all LLM providers"""
    
    PROVIDER_MODELS = {
        'openai': ['gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo'],
        'anthropic': ['claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku'],
        'gemini': ['gemini-pro', 'gemini-ultra'],
        'ollama': ['llama3.1:8b', 'mistral:7b', 'mixtral:8x7b'],
        'lmstudio': ['local-model']  # Uses OpenAI-compatible endpoint
    }
    
    def enhance_prompt(self, text: str, provider: str, model: str, style: str):
        response = completion(
            model=f"{provider}/{model}",
            messages=[{
                "role": "system", 
                "content": f"Enhance prompts for {style} image generation"
            }, {
                "role": "user",
                "content": f"Enhance: {text}"
            }],
            temperature=0.7
        )
        return response.choices[0].message.content
```

---

## 4) Version History & Time Travel

### Event Sourcing Architecture
Every action creates an immutable event, enabling complete reconstruction of any previous state:

#### Event Types
- **Project Events**: Creation, settings changes, exports
- **Scene Events**: Addition, deletion, reordering, duration changes
- **Prompt Events**: AI generation, user edits, regeneration
- **Image Events**: Generation, selection, deletion
- **Render Events**: Video generation, export settings

### History Features
#### History Tab (Per Project)
- **Timeline View**: Visual representation of all project events
- **Filter Controls**: Show/hide event types, search by content
- **Diff Viewer**: Compare any two versions side-by-side
- **Restore Points**: One-click restore to any previous state
- **Branch Support**: Create alternate versions from any point

#### Storage Strategy
- **Event Store**: SQLite with JSON columns for flexibility
- **Snapshots**: Periodic full-state captures for fast restoration
- **Delta Compression**: Efficient storage of incremental changes
- **Media Caching**: Preserve generated images/videos with events

### Implementation Example
```python
@dataclass
class ProjectEvent:
    event_id: str
    project_id: str
    event_type: str
    event_data: Dict[str, Any]
    timestamp: datetime
    user_action: bool  # True if user-initiated, False if AI-generated
    
class ProjectHistory:
    def save_prompt_edit(self, scene_id: str, old_prompt: str, new_prompt: str):
        event = ProjectEvent(
            event_id=uuid.uuid4(),
            project_id=self.project_id,
            event_type="prompt_edited",
            event_data={
                "scene_id": scene_id,
                "old_prompt": old_prompt,
                "new_prompt": new_prompt,
                "diff": difflib.unified_diff(old_prompt, new_prompt)
            },
            timestamp=datetime.now(),
            user_action=True
        )
        self.event_store.append(event)
```

---

## 5) MIDI-Based Synchronization & Timing

### Overview
When both MIDI and audio files are available (e.g., from AI song generators like aisonggenerator.ai), we can achieve frame-accurate synchronization using MIDI's precise timing data. This enables:
- **Perfect beat/measure alignment** for scene transitions
- **Word-level lyric synchronization** for karaoke effects
- **Musical structure awareness** (verse, chorus, bridge detection)
- **Tempo-aware scene pacing** that follows the music's rhythm

### MIDI Processing Pipeline
1. **MIDI Analysis**: Extract tempo, time signatures, beat positions, and lyric events
2. **Beat Grid Generation**: Create a timeline of beats, measures, and musical sections
3. **Lyric Extraction**: Parse MIDI lyric meta-events or align external lyrics to beats
4. **Scene Mapping**: Auto-align scenes to musical boundaries (measures, phrases, sections)
5. **Fine-Tuning**: Allow manual adjustment while maintaining musical alignment

### Technical Implementation
```python
@dataclass
class MidiTimingData:
    """MIDI timing information for synchronization"""
    file_path: Path
    tempo_changes: List[Tuple[float, float]]  # (time, bpm)
    time_signatures: List[Tuple[float, int, int]]  # (time, numerator, denominator)
    beats: List[float]  # Beat timestamps in seconds
    measures: List[float]  # Measure timestamps in seconds
    lyrics: List[Tuple[float, str]]  # (time, lyric_text)
    
class MidiProcessor:
    """Process MIDI files for timing extraction"""
    
    def extract_timing(self, midi_path: Path) -> MidiTimingData:
        """Extract all timing information from MIDI file"""
        import pretty_midi
        pm = pretty_midi.PrettyMIDI(midi_path)
        
        # Get beat and downbeat locations
        beats = pm.get_beats()
        downbeats = pm.get_downbeats()
        
        # Extract tempo changes
        tempo_changes = pm.get_tempo_changes()
        
        # Extract lyric events if present
        lyrics = self.extract_lyrics(pm)
        
        return MidiTimingData(...)
    
    def align_scenes_to_beats(self, scenes: List[Scene], 
                            timing: MidiTimingData,
                            alignment: str = "measure") -> List[Scene]:
        """Align scene transitions to musical boundaries"""
        if alignment == "measure":
            boundaries = timing.measures
        elif alignment == "beat":
            boundaries = timing.beats
        else:  # "section" - detect verse/chorus boundaries
            boundaries = self.detect_musical_sections(timing)
        
        # Snap scene durations to nearest boundaries
        return self.snap_to_grid(scenes, boundaries)
```

### Libraries Required
```txt
# Add to requirements.txt for MIDI support
pretty-midi>=0.2.10  # High-level MIDI analysis
mido>=1.3.0  # Low-level MIDI manipulation
music21>=9.1.0  # Advanced music theory analysis (optional)
```

### MIDI Features in GUI
- **MIDI Import Panel**:
  - Browse button for MIDI file selection
  - Display detected tempo, time signature, duration
  - Beat grid visualization overlay
  - Section markers (verse, chorus, etc.)
  
- **Sync Options**:
  - **Alignment Mode**: Beat / Measure / Section / Free
  - **Snap Strength**: 0-100% (how strongly to snap to grid)
  - **Lead Time**: Offset scenes ahead of beats (ms)
  - **Transition Style**: Cut on beat / Fade through beat

- **Preview**:
  - Waveform with beat markers
  - Play with click track
  - Visual metronome during preview

## 6) Karaoke & Music Notation Overlays

### Karaoke Overlay System
Post-processing feature to add synchronized lyrics overlays to generated videos:

#### Bouncing Ball Implementation
```python
@dataclass
class KaraokeOverlay:
    """Karaoke overlay configuration"""
    style: str  # "bouncing_ball", "highlight", "fade_in"
    position: str  # "bottom", "top", "center"
    font_size: int
    font_color: str
    background_opacity: float  # 0.0-1.0
    ball_image: Optional[Path]  # Custom ball sprite
    lead_time: float  # Seconds before word to start animation
    
class KaraokeRenderer:
    """Render karaoke overlays on video"""
    
    def add_bouncing_ball(self, video_path: Path, 
                          lyrics: List[Tuple[float, str, float]],  # (start, word, duration)
                          overlay: KaraokeOverlay) -> Path:
        """Add bouncing ball karaoke to video using FFmpeg"""
        # Generate ball animation keyframes
        # Create subtitle file with word-level timing
        # Use FFmpeg drawtext and overlay filters
        pass
    
    def generate_lrc_from_midi(self, midi_path: Path, 
                               lyrics_text: str) -> str:
        """Generate LRC file from MIDI timing + lyrics"""
        # Extract MIDI beats/measures
        # Align lyrics to timing
        # Output enhanced LRC format with word timing
        pass
```

#### Karaoke Formats Support
- **LRC** (Lyrics): Simple timestamp format for music players
- **Enhanced LRC**: Word-level timing with `<mm:ss.xx>` tags
- **SRT** (SubRip): Video subtitle format with start/end times
- **ASS/SSA**: Advanced SubStation for styled karaoke effects

#### FFmpeg Karaoke Filters
```bash
# Bouncing ball with drawtext filter
ffmpeg -i video.mp4 -i ball.png \
  -filter_complex "[0:v][1:v]overlay=x='if(gte(t,2),100+50*sin(t*3.14),NAN)':y='400-abs(sin(t*3.14)*50)':enable='between(t,2,5)'[v1]; \
  [v1]drawtext=text='Hello World':fontsize=40:x=(w-text_w)/2:y=450:fontcolor=white[out]" \
  -map "[out]" -map 0:a output.mp4

# Highlight words progressively
ffmpeg -i video.mp4 -vf "subtitles=lyrics.srt:force_style='Fontsize=24,PrimaryColour=&H00FFFF&'" output.mp4
```

### Sheet Music Overlay
Optional music notation display for educational/performance videos:

#### Music Notation Features
- **Staff Display**: Show current measure's notation
- **Scrolling Mode**: Continuous horizontal scroll
- **Highlight Current**: Mark playing notes/measures
- **Position Options**: Bottom strip, side panel, or corner

#### Implementation Approach
```python
class SheetMusicOverlay:
    """Generate and overlay sheet music notation"""
    
    def midi_to_notation(self, midi_path: Path) -> List[Path]:
        """Convert MIDI to sheet music images"""
        import music21
        score = music21.converter.parse(midi_path)
        
        # Generate PNG images per measure/system
        measures = []
        for measure in score.measures(1, None):
            # Render measure to PNG
            measures.append(self.render_measure(measure))
        return measures
    
    def overlay_notation(self, video_path: Path,
                        notation_images: List[Path],
                        timing: MidiTimingData) -> Path:
        """Overlay sheet music synchronized to video"""
        # Create scrolling notation strip
        # Sync to MIDI measure timing
        # Composite over video with FFmpeg
        pass
```

### LLM-Assisted Synchronization
For complex synchronization tasks without precise MIDI:

#### GPT-5 Integration
```python
class LLMSyncAssistant:
    """Use advanced LLMs for audio/lyric alignment"""
    
    async def analyze_audio_structure(self, audio_path: Path) -> Dict:
        """Use GPT-5 to analyze song structure"""
        # Upload audio to GPT-5
        # Request beat detection, section identification
        # Return structured timing data
        pass
    
    async def align_lyrics_to_audio(self, audio_path: Path, 
                                   lyrics: str) -> List[Tuple[float, str]]:
        """Use GPT-5 for forced alignment"""
        # Upload audio + lyrics
        # Request word-level timing alignment
        # Return synchronized lyrics
        pass
    
    async def generate_karaoke_timing(self, midi_path: Path,
                                     lyrics: str) -> str:
        """Generate professional karaoke timing"""
        # Upload MIDI + lyrics to GPT-5
        # Request LRC/SRT generation with proper sync
        # Include syllable-level timing if needed
        pass
```

## 7) Audio Track Support

### Audio Features
- **File Linking**: Reference audio files in-place without copying (saves disk space)
- **Format Support**: MP3, WAV, M4A, FLAC, OGG, AAC, and other common formats
- **Multiple Tracks**: Support for music track + optional narration/sound effects
- **Volume Control**: Adjustable volume levels per track
- **Fade In/Out**: Configurable audio fades at start/end
- **Preview**: Audio playback with video preview synchronization

### Audio Implementation
```python
@dataclass
class AudioTrack:
    track_id: str
    file_path: Path  # Absolute path to audio file (not copied)
    track_type: str  # 'music', 'narration', 'sfx'
    volume: float = 1.0  # 0.0 to 1.0
    fade_in_duration: float = 0.0  # seconds
    fade_out_duration: float = 0.0  # seconds
    start_offset: float = 0.0  # trim from beginning
    end_offset: float = 0.0  # trim from end
    
class AudioManager:
    def add_audio_track(self, audio_file: Path, track_type: str = 'music'):
        """Link to audio file without copying"""
        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")
        
        track = AudioTrack(
            track_id=str(uuid.uuid4()),
            file_path=audio_file.absolute(),  # Store absolute path
            track_type=track_type
        )
        return track
    
    def mix_with_video(self, video_path: Path, audio_tracks: List[AudioTrack]):
        """Mix audio tracks with video using FFmpeg"""
        # Build FFmpeg command with audio mixing
        pass
```

### FFmpeg Audio Integration
```bash
# Add single audio track to video
ffmpeg -i video.mp4 -i /path/to/music.mp3 -c:v copy -c:a aac -shortest output.mp4

# Mix multiple audio tracks with volume control
ffmpeg -i video.mp4 -i music.mp3 -i narration.wav \
  -filter_complex "[1:a]volume=0.8[music];[2:a]volume=1.0[narration];
  [music][narration]amix=inputs=2[aout]" \
  -map 0:v -map "[aout]" -shortest output.mp4

# Add fade effects
ffmpeg -i video.mp4 -i music.mp3 \
  -af "afade=t=in:st=0:d=2,afade=t=out:st=58:d=2" \
  -c:v copy -shortest output.mp4
```

---

## 8) UX Spec (GUI)
### New Tab: **🎬 Video Project**
- **Project header**: name, base folder, open/save.
- **Input panel**:
  - Text area + “Load from file…” (accepts `.txt`, `.md`, `.iaproj.json`).
  - **Format selector** (auto‑detect):  
    - *Timestamped lines:* `[mm:ss] line` (also accept `[mm:ss.mmm]`)  
    - *Structured lyrics:* `# Verse`, `# Chorus`, etc. (no timestamps)  
  - **Pacing preset**: *Fast / Medium / Slow* (affects scene durations when no timestamps).  
  - **Target Length**: `hh:mm:ss` (optional).

- **Provider & Prompting**:
  - **LLM Provider**: Dropdown for prompt generation (OpenAI / Claude / Gemini / Ollama / LM Studio)
  - **LLM Model**: Model selection based on provider (GPT-4, Claude 3, Llama 3.1, etc.)
  - **Image Provider**: Gemini / OpenAI / Stability / Local SD (+ model dropdown).  
  - **Style controls**: aspect ratio (pre‑set to **16:9**), quality, negative prompt, seed.  
  - **Prompt strategy**:  
    - "Literal line" vs "Cinematic rewrite" (LLM rewrites each line into a robust image prompt).
    - **Draft mode**: Use local LLM for quick iterations, cloud for final.
    - Template picker (Jinja‑like): `templates/lyric_prompt.j2`.

- **Audio & MIDI panel**:
  - **Audio Section**:
    - **Browse button**: Select audio file (no copy, just link)
    - **Audio file path**: Display linked file with folder location
    - **Waveform preview**: Visual audio waveform display
    - **Volume slider**: 0-100% with real-time preview
    - **Fade controls**: In/out duration in seconds
    - **Trim controls**: Start/end offset for audio
    - **Test play button**: Preview audio with current settings
  - **MIDI Section**:
    - **Browse MIDI**: Select MIDI file for timing sync
    - **MIDI info display**: BPM, time signature, duration
    - **Beat grid toggle**: Show/hide beat markers on timeline
    - **Sync mode**: None / Beat / Measure / Section
    - **Snap strength**: 0-100% slider
    - **Extract lyrics button**: Pull lyrics from MIDI if present
  - **Karaoke Options** (appears when MIDI loaded):
    - **Enable karaoke**: Checkbox to add lyric overlay
    - **Style**: Bouncing ball / Highlight / Fade-in
    - **Position**: Bottom / Top / Center
    - **Font settings**: Size, color, background opacity
    - **Export formats**: LRC / SRT / ASS checkboxes

- **Storyboard panel**:
  - Auto‑computed **scenes table** (line → prompt → duration).
  - **Inline prompt editing** with syntax highlighting and AI suggestions.
  - Per‑scene **N variants** (e.g., 1–4) with thumbnail grid. Re‑roll per scene.  
  - Drag to reorder scenes; duration knob per scene; title/caption toggle.
  - **Prompt history dropdown** showing all versions for each scene.

- **Preview & Export**:
  - **Preview cut**: quick render (low res, fast transitions).  
  - **Export**:
    - **Local Slideshow** → `MP4 (H.264, 24fps)`; pan/zoom + crossfades; optional burned‑in captions.  
    - **Gemini Veo**: choose model (**Veo 3**, **Veo 3 Fast**, **Veo 2**), aspect ratio 16:9, resolution 720p/1080p (per model constraints), negative prompt; clip chaining with concat.  
    - **Mute audio** option (for Veo 3 outputs).  
  - **Render queue** with progress & logs.

### New Tab: **📜 Project History**
- **Timeline View**: Interactive timeline showing all project events
- **Event Filters**: Toggle visibility of different event types
- **Diff Viewer**: Side-by-side comparison of any two versions
- **Restore Controls**: 
  - Restore button for any historical state
  - Create branch from any point
  - Export history as JSON
- **Search**: Find events by content, date, or type
- **Statistics Panel**: Event counts, storage usage, activity graph

---

## 7) Data & Files
```
{
  "schema": "imageai.video_project.v1",
  "name": "My Country Tis of Thee",
  "created": "ISO-8601",
  "provider": {
    "llm": { "provider": "openai|anthropic|gemini|ollama|lmstudio", "model": "gpt-4|claude-3-opus|gemini-pro|llama3.1:8b|…" },
    "images": { "provider": "gemini|openai|stability|local", "model": "…" },
    "video":   { "provider": "veo|slideshow", "model": "veo-3.0-generate-001|veo-2.0-generate-001|…" }
  },
  "prompt_template": "templates/lyric_prompt.j2",
  "style": { "aspect_ratio": "16:9", "negative": "…", "seed": 1234 },
  "input": { "raw": "…lyrics…", "format": "timestamped|structured" },
  "timing": { "target": "00:02:45", "preset": "medium" },
  "audio": {
    "tracks": [
      {
        "track_id": "audio-001",
        "file_path": "/absolute/path/to/music.mp3",
        "track_type": "music",
        "volume": 0.8,
        "fade_in": 2.0,
        "fade_out": 3.0,
        "start_offset": 0.0,
        "end_offset": 0.0
      }
    ]
  },
  "midi": {
    "file_path": "/absolute/path/to/song.mid",
    "tempo_bpm": 120,
    "time_signature": "4/4",
    "duration_sec": 165.5,
    "sync_mode": "measure",
    "snap_strength": 0.8,
    "beat_timestamps": [0.0, 0.5, 1.0, 1.5, ...],
    "measure_timestamps": [0.0, 2.0, 4.0, 6.0, ...],
    "extracted_lyrics": [
      {"time": 0.0, "text": "My"},
      {"time": 0.25, "text": "Country"},
      {"time": 0.75, "text": "Tis"},
      {"time": 1.0, "text": "of"},
      {"time": 1.25, "text": "Thee"}
    ]
  },
  "karaoke": {
    "enabled": true,
    "style": "bouncing_ball",
    "position": "bottom",
    "font_size": 32,
    "font_color": "#FFFFFF",
    "background_opacity": 0.7,
    "ball_image": "assets/karaoke/ball.png",
    "lead_time": 0.2,
    "export_formats": ["lrc", "srt"],
    "generated_files": {
      "lrc": "exports/lyrics.lrc",
      "srt": "exports/lyrics.srt"
    }
  },
  "scenes": [
    {
      "id": "scene-001",
      "source": "[00:12] My Country Tis of Thee…",
      "prompt": "Cinematic Americana kitchen…",
      "duration_sec": 4.5,
      "images": [
        {
          "path": "assets/scene-001/var-1.png",
          "provider": "gemini",
          "model": "imagen-4.0-generate-001",
          "seed": 1234,
          "cost": 0.02,
          "metadata": {…}
        }
      ],
      "approved_image": "assets/scene-001/var-1.png"
    }
  ],
  "export": { "path": "exports/mycountry_2025-09-11.mp4" }
}
```

**Folders under project root**
- `assets/scene-xxx/*.png` (all variants + chosen)  
- `exports/*.mp4` (finals + previews)  
- `logs/*.jsonl` (events & cost)  
- `project.iaproj.json`

---

## 8) Architecture & Code Layout (Detailed)

### Directory Structure
```
/gui
  video/
    video_project_tab.py         # Main tab widget with all panels
    storyboard_table.py          # Scene management table widget
    render_queue.py              # Export queue with progress tracking
    timeline_widget.py           # Visual timeline for scene durations
    preview_player.py            # Video preview widget

/core
  video/
    __init__.py                  # Video module exports
    project.py                   # VideoProject data model & persistence
    storyboard.py                # Scene parsing and management
    timing.py                    # Duration allocation algorithms
    prompt_engine.py             # LLM-based prompt enhancement
    image_batcher.py             # Concurrent image generation
    cache.py                     # Content-addressed storage
    
  video/renderers/
    ffmpeg_slideshow.py          # Local slideshow generator
    veo_renderer.py              # Veo API video generation
    base_renderer.py             # Abstract renderer interface

/providers
  video/
    __init__.py                  # Video provider exports
    gemini_veo.py                # Veo 2/3 implementation
    base_video.py                # Abstract video provider

/templates
  video/
    lyric_prompt.j2              # Template for lyric → image prompt
    shot_prompt.j2               # Template for cinematic shots
    scene_description.j2         # Template for scene metadata

/cli
  commands/
    video.py                     # Video subcommand implementation
```

### Integration Points with Existing Code

#### main.py modifications:
```python
# Add to GUI tab registration
if self.config.get("features", {}).get("video_enabled", True):
    from gui.video.video_project_tab import VideoProjectTab
    self.video_tab = VideoProjectTab(self.config, self.providers)
    self.tabs.addTab(self.video_tab, "🎬 Video Project")

# Add to CLI argument parser
subparsers = parser.add_subparsers(dest='command')
video_parser = subparsers.add_parser('video', help='Video generation')
cli.commands.video.setup_parser(video_parser)
```

#### Provider Interface Extension:
```python
# providers/base.py - Add video generation interface
class BaseProvider:
    def generate_image(self, prompt: str, **kwargs) -> Path:
        """Existing image generation"""
        pass
    
    def generate_video(self, prompt: str, image: Path = None, **kwargs) -> Path:
        """New video generation interface"""
        raise NotImplementedError("Video generation not supported")

# providers/google.py - Extend for Veo
class GoogleProvider(BaseProvider):
    def generate_video(self, prompt: str, image: Path = None, **kwargs):
        from providers.video.gemini_veo import VeoRenderer
        renderer = VeoRenderer(self.client)
        return renderer.generate(prompt, image, **kwargs)
```

#### Configuration Schema:
```python
# core/config.py - Add video settings
VIDEO_CONFIG_SCHEMA = {
    "video_projects_dir": str,  # Default: user_config_dir / "video_projects"
    "default_video_provider": str,  # "veo" or "slideshow"
    "veo_model": str,  # "veo-3.0-generate-001"
    "ffmpeg_path": str,  # Auto-detect or user-specified
    "cache_size_mb": int,  # Max cache size (default: 5000)
    "concurrent_images": int,  # Max parallel generations (default: 3)
}

---

## 9) Core Algorithms
### 6.1 Lyric/Text → Scenes
- **Timestamped** lines: exact cut points from `[mm:ss(.mmm)]`; otherwise use **pacing preset** to distribute total length over lines, weighted by line length.
- **Shot count**: `ceil(total_length / target_shot_seconds)` (defaults: 3–5s per shot).  
- **LLM rewrite** (optional): for each line, produce a **cinematic** prompt (subject, action, style, camera, ambiance, negative).

### 6.2 Image Batch
- Concurrency capped per provider.
- **Idempotent cache** by hash of `(provider, model, prompt, seed, size)`.
- Backoff on rate limits; light dedupe of semantically near‑identical prompts.

### 6.3 Video Assembly
- **Local slideshow**: 24fps, H.264 MP4, default 16:9; per‑scene pan/zoom + 0.5s crossfades; optional captions (line text).  
- **Gemini Veo**:
  - Clip generator → `generate_videos(model, prompt, image=approved_first_frame, config)` producing **5–8s** segments (Veo 3/3 Fast: **audio on**; Veo 2: **silent**).  
  - Concat clips; **mute** if requested.  
  - Download within **2 days** (server retention) and store locally.

---

## 10) Constraints & Model Notes
- **Veo 3 / Veo 3 Fast**: 8s, 24fps, 720p or 1080p (16:9 only), audio always on.  
- **Veo 2**: 5–8s, 24fps, 720p, silent; can do 9:16 portrait.  
- **Region/person rules**: `personGeneration` options vary by region; enforce in UI.  
- **Ops pattern**: long‑running operation; poll until `done`, then download video file.  
- **Watermarking**: SynthID applied to Veo output.
- **Token/Input limits**: keep prompts concise; image‑to‑video supported.

> See links in References for the official docs; implement guardrails in the tab (tooltips & validation).

---

## 11) CLI (initial sketch)
```bash
# Build storyboard and images, then render slideshow with music
imageai video --in lyrics.txt --provider gemini --model imagen-4.0-generate-001 \
  --length 00:02:30 --slideshow \
  --audio /path/to/music.mp3 --volume 0.8 --fade-in 2 --fade-out 3 \
  --out exports/mycountry.mp4

# Build Gemini Veo chain with custom audio
imageai video --in lyrics.txt --image-provider openai --image-model dall-e-3 \
  --veo-model veo-3.0-generate-001 \
  --audio /path/to/soundtrack.mp3 \
  --out exports/mycountry_veo.mp4

# No audio (silent video)
imageai video --in lyrics.txt --provider gemini --slideshow \
  --out exports/silent_video.mp4

# MIDI-synchronized video with karaoke overlay
imageai video --in lyrics.txt --provider gemini --slideshow \
  --audio /path/to/song.mp3 --midi /path/to/song.mid \
  --sync-mode measure --snap-strength 0.9 \
  --karaoke --karaoke-style bouncing_ball \
  --export-lrc --export-srt \
  --out exports/karaoke_video.mp4

# Extract timing from MIDI and generate perfectly synced scenes
imageai video --in lyrics.txt --midi /path/to/song.mid \
  --sync-mode beat --provider openai --model dall-e-3 \
  --audio /path/to/song.mp3 \
  --out exports/beat_synced.mp4
```

---

## 12) API Implementation Examples

### 9.1 Complete Veo Integration Class
```python
# providers/video/gemini_veo.py
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from google import genai
from google.genai import types

class VeoRenderer:
    """Gemini Veo video generation wrapper"""
    
    MODELS = {
        "veo-3": "veo-3.0-generate-001",
        "veo-3-fast": "veo-3.0-fast-generate-001", 
        "veo-2": "veo-2.0-generate-001"
    }
    
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.logger = logging.getLogger(__name__)
    
    def generate_video(self, 
                      prompt: str,
                      model: str = "veo-3",
                      image: Optional[Path] = None,
                      aspect_ratio: str = "16:9",
                      resolution: str = "720p",
                      negative_prompt: Optional[str] = None,
                      person_generation: str = "dont_allow",
                      seed: Optional[int] = None,
                      output_path: Optional[Path] = None,
                      timeout: int = 600) -> Path:
        """
        Generate video using Veo API
        
        Args:
            prompt: Text description for video
            model: Model key (veo-3, veo-3-fast, veo-2)
            image: Optional first frame image
            aspect_ratio: Video aspect ratio (16:9 or 9:16)
            resolution: Output resolution (720p or 1080p)
            negative_prompt: Things to avoid in generation
            person_generation: Person generation policy
            seed: Random seed for reproducibility
            output_path: Where to save the video
            timeout: Maximum wait time in seconds
            
        Returns:
            Path to saved video file
        """
        
        # Validate model
        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")
        
        model_name = self.MODELS[model]
        
        # Build config
        config_kwargs = {
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "person_generation": person_generation
        }
        
        if negative_prompt:
            config_kwargs["negative_prompt"] = negative_prompt
        if seed is not None:
            config_kwargs["seed"] = seed
            
        config = types.GenerateVideosConfig(**config_kwargs)
        
        # Load image if provided
        image_file = None
        if image and image.exists():
            with open(image, 'rb') as f:
                image_file = self.client.files.upload(f)
        
        # Start generation
        self.logger.info(f"Starting video generation with {model_name}")
        operation = self.client.models.generate_videos(
            model=model_name,
            prompt=prompt,
            image=image_file,
            config=config
        )
        
        # Poll for completion
        start_time = time.time()
        while not operation.done:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Video generation timed out after {timeout}s")
            
            time.sleep(10)
            operation = self.client.operations.get(operation)
            self.logger.debug(f"Generation status: {operation.metadata}")
        
        # Check for errors
        if operation.error:
            raise Exception(f"Video generation failed: {operation.error}")
        
        # Download result
        if not operation.result or not operation.result.generated_videos:
            raise Exception("No video was generated")
        
        video = operation.result.generated_videos[0]
        self.client.files.download(file=video.video)
        
        # Save to file
        if not output_path:
            output_path = Path(f"veo_{model}_{int(time.time())}.mp4")
        
        video.video.save(str(output_path))
        self.logger.info(f"Video saved to {output_path}")
        
        return output_path
    
    def concatenate_videos(self, video_paths: list[Path], output: Path) -> Path:
        """Concatenate multiple Veo clips into one video"""
        import subprocess
        
        # Create concat file
        concat_file = Path("concat.txt")
        with open(concat_file, 'w') as f:
            for path in video_paths:
                f.write(f"file '{path.absolute()}'\n")
        
        # Run ffmpeg concat
        cmd = [
            "ffmpeg", "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",  # No re-encoding
            str(output)
        ]
        
        subprocess.run(cmd, check=True)
        concat_file.unlink()
        
        return output
```

### 9.2 FFmpeg Slideshow Generator
```python
# core/video/renderers/ffmpeg_slideshow.py
import subprocess
import json
from pathlib import Path
from typing import List, Optional, Tuple

class FFmpegSlideshow:
    """Generate video slideshows from images using FFmpeg"""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg = ffmpeg_path
        self._verify_ffmpeg()
    
    def _verify_ffmpeg(self):
        """Check if FFmpeg is available"""
        try:
            subprocess.run([self.ffmpeg, "-version"], 
                         capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("FFmpeg not found. Please install FFmpeg.")
    
    def create_slideshow(self,
                        images: List[Path],
                        durations: List[float],
                        output: Path,
                        resolution: Tuple[int, int] = (1920, 1080),
                        fps: int = 24,
                        transition_duration: float = 0.5,
                        enable_ken_burns: bool = True,
                        captions: Optional[List[str]] = None) -> Path:
        """
        Create slideshow video from images
        
        Args:
            images: List of image paths
            durations: Duration for each image in seconds
            output: Output video path
            resolution: Output resolution (width, height)
            fps: Frames per second
            transition_duration: Crossfade duration
            enable_ken_burns: Enable pan/zoom effect
            captions: Optional captions for each image
        """
        
        # Build filter complex
        filter_parts = []
        
        for i, (img, duration) in enumerate(zip(images, durations)):
            # Scale and pad to resolution
            filter_parts.append(
                f"[{i}:v]scale={resolution[0]}:{resolution[1]}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={resolution[0]}:{resolution[1]}:(ow-iw)/2:(oh-ih)/2"
            )
            
            # Ken Burns effect (zoom and pan)
            if enable_ken_burns:
                zoom_factor = 1.1
                pan_x = "(iw-ow)/2+sin(t/10)*20"
                pan_y = "(ih-oh)/2+cos(t/10)*20"
                filter_parts[-1] += (
                    f",zoompan=z='min(zoom+0.002,{zoom_factor})':"
                    f"x='{pan_x}':y='{pan_y}':"
                    f"d={int(duration * fps)}:s={resolution[0]}x{resolution[1]}"
                )
            
            # Add caption if provided
            if captions and i < len(captions):
                caption = captions[i].replace("'", "\\'")
                filter_parts[-1] += (
                    f",drawtext=text='{caption}':"
                    f"fontsize=48:fontcolor=white:"
                    f"shadowcolor=black:shadowx=2:shadowy=2:"
                    f"x=(w-text_w)/2:y=h-80"
                )
            
            filter_parts[-1] += f"[v{i}]"
        
        # Build crossfade chain
        if len(images) > 1:
            # Start with first video
            concat_filter = f"[v0]"
            
            for i in range(1, len(images)):
                offset = sum(durations[:i]) - transition_duration * i
                concat_filter += (
                    f"[v{i}]xfade=transition=fade:"
                    f"duration={transition_duration}:"
                    f"offset={offset}"
                )
                if i < len(images) - 1:
                    concat_filter += f"[vx{i}];[vx{i}]"
            
            filter_parts.append(concat_filter + ",format=yuv420p[out]")
        else:
            filter_parts.append("[v0]format=yuv420p[out]")
        
        # Build FFmpeg command
        cmd = [self.ffmpeg, "-y"]
        
        # Add inputs
        for img in images:
            cmd.extend(["-loop", "1", "-i", str(img)])
        
        # Add filter complex
        cmd.extend([
            "-filter_complex", ";".join(filter_parts),
            "-map", "[out]",
            "-r", str(fps),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            str(output)
        ])
        
        # Run FFmpeg
        subprocess.run(cmd, check=True)
        
        return output
```

### 9.3 Scene-to-Video Pipeline
```python
# core/video/pipeline.py
from typing import List, Dict, Any
from pathlib import Path
import asyncio
import concurrent.futures

class VideoProjectPipeline:
    """End-to-end video generation pipeline"""
    
    def __init__(self, config: Dict[str, Any], providers: Dict[str, Any]):
        self.config = config
        self.providers = providers
        self.image_cache = {}
    
    async def process_scene(self, scene: Dict[str, Any]) -> List[Path]:
        """Generate images for a single scene"""
        
        # Check cache first
        cache_key = self._get_cache_key(scene)
        if cache_key in self.image_cache:
            return self.image_cache[cache_key]
        
        # Get provider
        provider_name = scene.get("provider", self.config["default_provider"])
        provider = self.providers[provider_name]
        
        # Generate variants
        images = []
        num_variants = scene.get("variants", 3)
        
        for i in range(num_variants):
            seed = scene.get("seed", 0) + i if scene.get("seed") else None
            
            image_path = await self._generate_image_async(
                provider=provider,
                prompt=scene["prompt"],
                seed=seed,
                negative=scene.get("negative_prompt"),
                size=(1920, 1080)  # 16:9 for video
            )
            images.append(image_path)
        
        # Cache results
        self.image_cache[cache_key] = images
        return images
    
    async def generate_all_scenes(self, scenes: List[Dict]) -> Dict[str, List[Path]]:
        """Generate images for all scenes concurrently"""
        
        # Limit concurrency
        semaphore = asyncio.Semaphore(self.config.get("concurrent_images", 3))
        
        async def process_with_limit(scene):
            async with semaphore:
                return await self.process_scene(scene)
        
        # Process all scenes
        tasks = [process_with_limit(scene) for scene in scenes]
        results = await asyncio.gather(*tasks)
        
        # Map scene IDs to images
        return {
            scene["id"]: images 
            for scene, images in zip(scenes, results)
        }
    
    def render_video(self, project: Dict, renderer: str = "slideshow") -> Path:
        """Render final video using specified renderer"""
        
        if renderer == "slideshow":
            from core.video.renderers.ffmpeg_slideshow import FFmpegSlideshow
            slideshow = FFmpegSlideshow()
            
            # Collect approved images
            images = []
            durations = []
            captions = []
            
            for scene in project["scenes"]:
                images.append(Path(scene["approved_image"]))
                durations.append(scene["duration_sec"])
                captions.append(scene.get("caption", ""))
            
            return slideshow.create_slideshow(
                images=images,
                durations=durations,
                captions=captions,
                output=Path(project["export"]["path"])
            )
        
        elif renderer == "veo":
            from providers.video.gemini_veo import VeoRenderer
            veo = VeoRenderer(self.config["google_api_key"])
            
            # Generate Veo clips for each scene
            clips = []
            for scene in project["scenes"]:
                clip = veo.generate_video(
                    prompt=scene["prompt"],
                    image=Path(scene["approved_image"]),
                    model=project["provider"]["video"]["model"]
                )
                clips.append(clip)
            
            # Concatenate clips
            return veo.concatenate_videos(
                clips, 
                Path(project["export"]["path"])
            )
```

---

## 13) Validation
- Golden sample projects checked into `Plans/samples/` with deterministic seeds.
- Headless **CI smoke**: generate 2 scenes with tiny images + 2s clips; assert MP4 exists.

---

## 14) Risks & Mitigations
- **Model safety blocks** → auto‑rewrite prompts (LLM), add negative terms, or switch provider.
- **Latency** (Veo ops) → queue + UI progress + local preview path.
- **Regional restrictions** → gate `personGeneration` options by `iso_region`.
- **Cost overruns** → show running cost estimate per batch.

---

## 15) Phased Delivery
1. **MVP Phase 1**: Core foundation - Event sourcing, AI prompt generation, storyboard, image batcher.
2. **MVP Phase 2**: Audio support - File linking, mixing, volume/fade controls.
3. **MVP Phase 3**: Video generation - Veo API integration (8s clips), FFmpeg slideshow with audio.
4. **Enhancement (v1.1)**: History tab, advanced transitions, captions, presets, caching, cost panel.
5. **Polish (v1.2)**: Drag-reorder UX, branch support, diff viewer, restore points.
6. **Continuity (v2.0)**: Seed carry-over, character consistency, style transfer.
7. **Advanced Audio (v3.0)**: Beat detection, automatic sync, multi-track timeline.

---

## 16) References
- Gemini API – Generate videos with Veo (models, durations, polling, retention): https://ai.google.dev/gemini-api/docs/video  
- Gemini API – Models catalog: https://ai.google.dev/gemini-api/docs/models  
- ImageAI repo README (providers, PySide6 GUI, CLI): https://github.com/lelandg/ImageAI

---

## 17) Acceptance Criteria (MVP)
- I can paste lyrics, click **Storyboard**, see scene rows with durations summing to target length.
- I can **Generate Images** and see thumbnails per scene; re‑roll one scene without touching others.
- I can **Add Audio** by browsing to a local file (MP3/WAV/M4A) without copying it.
- I can adjust audio **volume, fade in/out** and preview the settings.
- I can **Export → Slideshow** and get a valid MP4 at 24fps, 16:9 with my custom audio.
- I can **Export → Veo** and get 8-second AI video clips with optional audio mixing.
- All artifacts + a `project.iaproj.json` are saved under the project folder.
- Audio files remain **linked** (not copied) with absolute paths in the project file.
- Rerunning the same prompts with the same seed reuses cached images.

### Additional MIDI/Karaoke Criteria
- I can **Import MIDI** file and see tempo, time signature, and duration information.
- Scene transitions **snap to beats/measures** when MIDI sync is enabled.
- I can **Enable karaoke overlay** and choose from bouncing ball, highlight, or fade-in styles.
- The system **exports LRC/SRT files** with accurate word-level timing from MIDI.
- I can see a **beat grid overlay** on the timeline when MIDI is loaded.
- Karaoke overlays are **perfectly synchronized** to the music when using MIDI timing.

---

## 18) Implementation Notes

### Development Notice
- **IMPORTANT**: A development notice banner is currently displayed in the Video tab
- The notice warns users that the feature is under development
- **TODO**: Remove the notice from `gui/video/video_project_tab.py` line 131-142 once:
  - Image generation is connected and working
  - Video rendering (FFmpeg or Veo) is functional
  - Basic end-to-end workflow is tested and stable

### Documentation Updates Required
- **TODO**: Update the Help tab content once video generation is functional:
  - Add section explaining video project workflow
  - Document supported input formats with examples
  - Include video export options and requirements
  - Add troubleshooting section for common video issues
  - Include FFmpeg installation instructions
  - Document Veo API requirements and limitations

## 19) Implementation Checklist

### Phase 1: Foundation & Core Components
#### 1.1 Project Structure Setup
- [x] Create core video module directories: `core/video/`, `gui/video/`
- [x] Create templates directory: `templates/video/`
- [x] Set up project storage structure under user config directory
- [x] Create sample project structure in `Plans/samples/`

#### 1.2 Data Models & Storage
- [x] Define `VideoProject` class with schema version control
- [x] Implement `Scene` data model (id, source, prompt, duration, images, approved)
- [x] Create `ProjectManager` for save/load/migrate operations
- [x] Implement project file validation & schema migration

#### 1.3 Dependencies & Configuration
- [x] Add Jinja2 to requirements.txt for template processing
- [x] Add moviepy or imageio-ffmpeg for video processing
- [ ] Verify google-genai supports latest Veo models
- [x] Update config system to include video-specific settings
- [ ] Add pretty-midi for MIDI processing
- [ ] Add mido for low-level MIDI manipulation
- [ ] Add music21 for sheet music generation (optional)

### Phase 2: AI Prompt Generation & History System
#### 2.1 Version History Foundation
- [ ] Implement event sourcing with SQLite backend
- [ ] Create ProjectEvent dataclass and event types enum
- [ ] Build EventStore with append and query operations
- [ ] Implement snapshot system for performance
- [ ] Add delta compression for storage efficiency

#### 2.2 LLM Provider Integration
- [ ] Add LiteLLM dependency for unified LLM access
- [ ] Implement OpenAI provider for GPT-4/GPT-3.5
- [ ] Implement Anthropic provider for Claude 3 models
- [ ] Implement Google Gemini provider for Gemini Pro/Ultra
- [ ] Add Ollama integration for local LLMs
- [ ] Add LM Studio support via OpenAI-compatible API
- [ ] Create provider selection UI with model dropdowns
- [ ] Implement API key management for each provider

#### 2.3 AI Prompt Generation
- [ ] Create UnifiedLLMProvider class with LiteLLM
- [ ] Build prompt enhancement templates
- [ ] Implement batch prompt generation system
- [ ] Add style presets (cinematic, artistic, photorealistic)
- [ ] Create draft mode (local LLM) vs final mode (cloud)
- [ ] Add prompt regeneration with preservation of other prompts
- [ ] Implement cost tracking per provider/model

#### 2.4 Prompt Editing & Tracking
- [ ] Build inline prompt editor with syntax highlighting
- [ ] Implement prompt version tracking
- [ ] Create diff visualization for prompt changes
- [ ] Add prompt history dropdown per scene
- [ ] Build prompt lineage tracking system

### Phase 3: Text Processing & Storyboarding
#### 3.1 Input Parsing
- [x] Implement timestamped format parser: `[mm:ss] text` and `[mm:ss.mmm] text`
- [x] Implement structured lyrics parser: `# Verse`, `# Chorus`, etc.
- [x] Create format auto-detection logic
- [ ] Add file loaders for `.txt`, `.md`, `.iaproj.json`

#### 3.2 Timing & Scene Generation
- [x] Implement `TimingEngine` with pacing presets (Fast/Medium/Slow)
- [x] Create duration allocation algorithm for target length
- [x] Build scene splitter with configurable shot duration (3-5s default)
- [x] Add duration validation and adjustment logic

#### 3.3 Prompt Engineering
- [x] Create base Jinja2 templates: `lyric_prompt.j2`, `shot_prompt.j2`
- [x] Implement `PromptEngine` with LLM rewrite capability
- [x] Add template token system for style variables
- [x] Create cinematic prompt generator with camera/style/ambiance tokens

### Phase 4: Image Generation Pipeline
#### 4.1 Provider Integration
- [x] Ensure unified `generate_image()` interface across all providers
- [x] Add batch generation support with concurrency limits
- [x] Implement provider-specific error handling and retries
- [x] Add cost estimation and tracking per provider

#### 4.2 Image Caching & Management
- [x] Create idempotent cache with hash-based lookup
- [x] Implement cache invalidation and cleanup
- [x] Add image variant management (N per scene)
- [x] Build thumbnail generation for UI display

#### 4.3 Scene Management
- [x] Implement per-scene regeneration without affecting others
- [x] Add approved image selection and persistence
- [ ] Create scene reordering logic
- [x] Build metadata tracking for each generation

### Phase 5: GUI Implementation
#### 5.1 Video Project Tab
- [x] Create `VideoProjectTab` widget in PySide6
- [x] Implement project header with name/folder/save controls
- [x] Add input panel with text area and format selector
- [x] Build provider selection with model dropdowns

#### 5.2 Storyboard Interface
- [x] Create `StoryboardTable` widget with scene rows
- [x] Implement thumbnail grid display (N variants per scene)
- [ ] Add drag-and-drop scene reordering
- [x] Build duration adjustment controls per scene
- [x] Add caption/title toggle switches

#### 5.3 Style & Configuration
- [x] Add aspect ratio selector (16:9, 9:16)
- [x] Implement quality/resolution controls
- [x] Add negative prompt input
- [x] Create seed management UI
- [ ] Build template selector and editor

#### 5.4 Progress & Feedback
- [x] Implement `RenderQueue` widget with progress bars
- [x] Add real-time generation status display
- [x] Create cost estimate display
- [ ] Build error notification system

#### 5.5 History Tab Implementation
- [x] Create `HistoryTab` widget with timeline view
- [x] Implement event filtering and search
- [x] Build diff viewer for comparing versions
- [x] Add restore point creation and management
- [ ] Implement branch creation from historical states
- [x] Create history export functionality
- [x] Add storage usage analytics display

### Phase 6: Audio Integration
#### 6.1 Audio File Management
- [x] Implement AudioTrack dataclass with file linking (no copy)
- [x] Build AudioManager for track management
- [x] Add support for multiple audio formats (MP3, WAV, M4A, etc.)
- [ ] Create audio file validation and error handling
- [x] Implement path resolution for linked audio files

#### 6.2 Audio Controls
- [x] Build audio panel in GUI with file browser
- [ ] Implement waveform visualization
- [x] Add volume control with real-time preview
- [x] Create fade in/out controls
- [ ] Build trim controls for start/end offsets
- [ ] Add audio preview playback

#### 6.3 FFmpeg Audio Mixing
- [ ] Implement audio track mixing with video
- [ ] Add volume normalization
- [ ] Build fade effect processing
- [ ] Create multi-track mixing support
- [ ] Implement audio codec selection (AAC, MP3)
- [ ] Add -shortest flag handling for duration matching

### Phase 7: MIDI Synchronization & Karaoke Features
#### 7.1 MIDI Processing
- [ ] Implement `MidiProcessor` class with pretty-midi
- [ ] Extract tempo, time signatures, beats, measures
- [ ] Parse MIDI lyric meta-events
- [ ] Create beat grid generation system
- [ ] Build scene-to-beat alignment algorithm
- [ ] Add musical section detection (verse/chorus)
- [ ] Implement MIDI-to-timing data converter

#### 7.2 Karaoke System
- [ ] Create `KaraokeRenderer` class
- [ ] Implement bouncing ball animation generator
- [ ] Build word-level timing extraction from MIDI
- [ ] Add LRC format generator
- [ ] Add SRT format generator
- [ ] Implement ASS/SSA format support
- [ ] Create FFmpeg filter chains for overlays
- [ ] Add custom ball sprite support

#### 7.3 Sheet Music Overlay (Optional)
- [ ] Implement MIDI-to-notation converter with music21
- [ ] Create measure-by-measure PNG renderer
- [ ] Build scrolling notation overlay system
- [ ] Add current measure highlighting
- [ ] Implement notation positioning options

#### 7.4 LLM-Assisted Sync
- [ ] Create `LLMSyncAssistant` class
- [ ] Implement GPT-5 audio structure analysis
- [ ] Add forced alignment for lyrics without MIDI
- [ ] Build fallback sync when MIDI unavailable
- [ ] Create syllable-level timing generation

### Phase 8: Video Assembly - Local Slideshow
#### 8.1 FFmpeg Integration
- [x] Implement `FFmpegSlideshow` class
- [x] Add Ken Burns effect (pan/zoom) support
- [x] Create crossfade transition system (0.5s default)
- [x] Build caption overlay system
- [x] Integrate audio track mixing

#### 8.2 Video Export
- [x] Implement H.264 encoding at 24fps
- [x] Add resolution options (720p, 1080p)
- [x] Create preview generation (low-res, fast)
- [x] Build final export with quality settings
- [x] Ensure audio sync with video duration

### Phase 9: Veo API Integration
#### 9.1 Veo Client Implementation
- [x] Create `VeoClient` wrapper class using google.genai
- [x] Implement `generate_videos()` with all config options
- [x] Add polling mechanism for long-running operations (11s-6min)
- [x] Build download and local storage system (2-day retention handling)
- [x] Implement timeout and retry logic

#### 9.2 Veo Model Support
- [x] Add Veo 3.0 support (`veo-3.0-generate-001`)
- [x] Add Veo 3.0 Fast support (`veo-3.0-fast-generate-001`)
- [x] Add Veo 2.0 support (`veo-2.0-generate-001`)
- [x] Implement model-specific constraints (resolution, duration, audio)
- [x] Add aspect ratio support (16:9, 9:16)

#### 9.3 Regional Compliance
- [ ] Implement region detection system
- [ ] Add `personGeneration` option gating by region
- [ ] Create UI warnings for regional restrictions
- [ ] Build fallback strategies for blocked content
- [ ] Handle MENA/EU restrictions appropriately

#### 9.4 Video Processing
- [ ] Implement clip concatenation system using ffmpeg
- [ ] Add audio muting option for Veo 3 outputs
- [ ] Build 2-day retention warning system
- [ ] Create automatic local backup on generation
- [ ] Add SynthID watermark detection/display

### Phase 10: CLI Implementation
#### 10.1 Command Structure
- [ ] Add `video` subcommand to main CLI
- [ ] Implement all GUI features in CLI
- [ ] Add batch processing support
- [ ] Create progress indicators for terminal

#### 10.2 CLI Arguments
- [ ] `--in`: Input file path
- [ ] `--provider`: Image provider selection
- [ ] `--model`: Model selection
- [ ] `--length`: Target video length
- [ ] `--slideshow`: Use local slideshow renderer
- [ ] `--veo-model`: Veo model selection
- [ ] `--out`: Output file path
- [ ] `--audio`: Path to audio file (linked, not copied)
- [ ] `--midi`: Path to MIDI file for timing sync
- [ ] `--sync-mode`: Sync alignment (none|beat|measure|section)
- [ ] `--snap-strength`: Snap strength 0.0-1.0
- [ ] `--volume`: Audio volume (0.0-1.0)
- [ ] `--fade-in`: Fade in duration in seconds
- [ ] `--fade-out`: Fade out duration in seconds
- [ ] `--mute`: Mute audio option (for Veo)
- [ ] `--karaoke`: Enable karaoke overlay
- [ ] `--karaoke-style`: Style (bouncing_ball|highlight|fade_in)
- [ ] `--export-lrc`: Export LRC file
- [ ] `--export-srt`: Export SRT file

### Phase 11: Testing & Validation
#### 11.1 Unit Tests
- [ ] Test lyric parsing (all formats)
- [ ] Test timing allocation algorithms
- [ ] Test prompt generation and templates
- [ ] Test project save/load/migration

#### 11.2 Integration Tests
- [ ] Test provider image generation pipeline
- [ ] Test video assembly (slideshow)
- [ ] Test Veo API integration
- [ ] Test end-to-end workflow

#### 11.3 Sample Projects
- [ ] Create "My Country tis of Thee" reference project
- [ ] Add deterministic seed test cases
- [ ] Build CI/CD smoke tests
- [ ] Document expected outputs

### Phase 12: Documentation & Polish
#### 12.1 User Documentation
- [ ] Update README with video feature documentation
- [ ] Create video workflow tutorial
- [ ] Add troubleshooting guide
- [ ] Document all CLI options

#### 12.2 Developer Documentation
- [ ] Document API interfaces
- [ ] Create plugin architecture docs
- [ ] Add contribution guidelines
- [ ] Build architecture diagrams

#### 12.3 UI Polish
- [ ] Add tooltips and help text
- [ ] Implement keyboard shortcuts
- [ ] Create preset management
- [ ] Add export history viewer

### Technical Requirements & Notes

#### Dependencies to Add
```txt
# Add to requirements.txt
# LLM Support
litellm>=1.0.0  # Unified LLM provider interface
anthropic>=0.25.0  # Claude API support
ollama>=0.3.0  # Local LLM support (optional)

# Template & Video
Jinja2>=3.1.0  # Template processing
moviepy>=1.0.3  # Video processing (or imageio-ffmpeg)

# Already present:
# google-genai - Gemini support
# openai - GPT support
```

#### Local LLM Requirements
- **Ollama**: Separate installation from https://ollama.ai
- **LM Studio**: Separate installation from https://lmstudio.ai
- **Hardware**: 16GB+ RAM, RTX 4060 Ti+ recommended for 7B models

#### FFmpeg Requirements
- Must be installed separately by user
- Provide installation instructions per platform
- Implement graceful fallback if not available

#### File Size Considerations
- Image cache management (auto-cleanup old projects)
- Video file compression options
- Streaming preview instead of full download

#### Performance Optimizations
- Concurrent image generation with rate limiting
- Lazy loading of thumbnails in UI
- Background video rendering with queue
- Incremental project saves

#### Error Handling Priority
- Network timeouts and retries
- API rate limiting and backoff
- Provider safety blocks and fallbacks
- Disk space monitoring

---

## 19) Known Limitations & Future Enhancements

### Current Limitations
- No audio synchronization (music/beat alignment)
- Limited to 8-second Veo clips
- No character consistency across scenes
- Regional restrictions on person generation
- 2-day retention for Veo videos

### Future Enhancements (Post-MVP)
- Music beat detection and sync
- TTS narration integration
- Multi-track timeline editor
- Character consistency via ControlNet/IP-Adapter
- External audio track alignment
- Longer video generation via clip chaining
- Style transfer between scenes
- Motion templates and presets
