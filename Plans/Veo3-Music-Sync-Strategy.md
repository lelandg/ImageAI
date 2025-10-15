# Veo 3 Music Synchronization Strategy

**Created:** 2025-10-14
**Status:** Proposal
**Priority:** High - Required for Video Project Feature

## Executive Summary

**Key Finding:** Veo 3 does **NOT** always return 8-second videos. It supports **variable durations of 4, 6, or 8 seconds** via an API parameter.

**Current Bug:** ImageAI's `VeoClient` incorrectly embeds duration in the prompt text instead of using the API's `duration` parameter.

**Synchronization Challenge:** Veo 3 has no API for custom music/MIDI synchronization. The solution is **MIDI-driven scene timing with FFmpeg post-processing**.

---

## Table of Contents

1. [Veo 3 Duration Capabilities](#veo-3-duration-capabilities)
2. [Current Implementation Issues](#current-implementation-issues)
3. [Audio Synchronization Reality](#audio-synchronization-reality)
4. [Recommended Solutions](#recommended-solutions)
5. [Technical Implementation Plan](#technical-implementation-plan)
6. [Implementation Roadmap](#implementation-roadmap)
7. [References](#references)

---

## Veo 3 Duration Capabilities

### Supported Durations

Veo 3 supports **three discrete durations**:

| Duration | Use Case | Notes |
|----------|----------|-------|
| **4 seconds** | Quick cuts, transitions | Minimum duration |
| **6 seconds** | Medium scenes | Balanced option |
| **8 seconds** | Longer scenes | Maximum duration, default |

**Model Compatibility:**
- **Veo 3** (`veo-3.0-generate-001`): 4, 6, 8 seconds ✅
- **Veo 3 Fast** (`veo-3.0-fast-generate-001`): 4, 6, 8 seconds ✅
- **Veo 2** (`veo-2.0-generate-001`): 5-8 seconds (different range)

### API Usage

**Correct API Call:**
```python
from vertexai.preview.vision_models import GenerateVideosConfig

video_config = GenerateVideosConfig(
    aspect_ratio="16:9",
    resolution="1080p",
    duration=6  # MUST be 4, 6, or 8
)

response = client.models.generate_videos(
    model="veo-3.0-generate-001",
    prompt="Your prompt here",
    config=video_config
)
```

**Incorrect Usage (Current ImageAI Bug):**
```python
# ❌ WRONG - Duration embedded in prompt
enhanced_prompt = f"{duration}-second video of {prompt}"
response = client.models.generate_videos(
    model="veo-3.0-generate-001",
    prompt=enhanced_prompt,  # Duration in text doesn't work
    config=video_config  # Missing duration parameter
)
```

### Technical Constraints

**Hard Limits:**
- **Minimum:** 4 seconds (cannot go lower)
- **Maximum:** 8 seconds (cannot go higher, even with premium plans)
- **Increment:** Fixed values only (no 5s or 7s for Veo 3)

**For Videos Longer Than 8 Seconds:**
- Generate multiple clips and concatenate using FFmpeg
- Your codebase already has `VeoClient.concatenate_clips()` method

---

## Current Implementation Issues

### Bug Location

**File:** `core/video/veo_client.py`
**Lines:** 244-270
**Severity:** High - Prevents using 4s and 6s durations

### Current Code (INCORRECT)

```python
# Line 251 - Embedding duration in prompt text
enhanced_prompt = f"{config.duration}-second video of {config.prompt}"

# Lines 244-270 - Missing duration parameter
video_config = types.GenerateVideosConfig(
    aspect_ratio=config.aspect_ratio,
    resolution=config.resolution
    # ❌ MISSING: duration=config.duration
)

response = self.client.models.generate_videos(
    model=config.model.value,
    prompt=enhanced_prompt,  # Uses prompt with duration text
    config=video_config,
    image=seed_image
)
```

### Required Fix

```python
# Use original prompt, not enhanced
video_config = types.GenerateVideosConfig(
    aspect_ratio=config.aspect_ratio,
    resolution=config.resolution,
    duration=config.duration  # ✅ ADD THIS
)

response = self.client.models.generate_videos(
    model=config.model.value,
    prompt=config.prompt,  # ✅ Use original prompt
    config=video_config,
    image=seed_image
)
```

### Impact

**Current Behavior:**
- All videos default to 8 seconds
- Cannot generate 4s or 6s clips
- Prompt pollution (e.g., "8-second video of elderly man...")
- Limits music synchronization flexibility

**After Fix:**
- Full control over clip durations
- Cleaner prompts
- Better music alignment options
- Enables MIDI-driven timing strategies

---

## Audio Synchronization Reality

### What Veo 3 Can Do

✅ **Native Audio-Visual Synthesis:**
- Generates synchronized sound effects, ambient noise, dialogue
- First major AI video model with integrated audio
- Automatically syncs generated audio with video pixels

### What Veo 3 CANNOT Do

❌ **No Custom Music Synchronization:**
- No API for external audio file input
- Cannot sync to MIDI timing data
- Cannot control beat alignment or musical structure
- Cannot specify custom music tracks
- Audio generation is "take it or leave it"

### Reality for Music Videos

**For lyric-synced music videos:**
1. Veo 3's native audio is **not useful** - designed for sound effects/dialogue
2. You MUST **mute Veo's audio** and add your own soundtrack
3. Synchronization happens in **post-processing with FFmpeg**
4. MIDI files provide timing data for scene alignment

**Documented Limitation (from Google):**
> "Creating videos with natural and consistent spoken audio, particularly for shorter speech segments, remains an area of active development."

No mention of music synchronization in any official documentation.

---

## Recommended Solutions

### Solution A: MIDI-Driven Scene Timing ⭐ RECOMMENDED

**How It Works:**

1. Parse MIDI file to extract precise beat/measure timestamps
2. Align scene durations to musical boundaries (e.g., 4-beat measures)
3. Generate Veo clips at exact durations (4, 6, or 8s) matching musical structure
4. Concatenate clips and add custom audio in post-processing

**Implementation:**

```python
import pretty_midi

# Parse MIDI for timing data
pm = pretty_midi.PrettyMIDI("song.mid")
beats = pm.get_beats()  # [0.0, 0.5, 1.0, 1.5, 2.0, ...]
measures = pm.get_downbeats()  # [0.0, 2.0, 4.0, 6.0, ...]

# Align scenes to musical structure
scene_durations = []
for i in range(len(measures) - 1):
    duration = measures[i+1] - measures[i]
    # Snap to Veo-compatible duration (4, 6, or 8)
    veo_duration = snap_to_veo_duration(duration, [4, 6, 8])
    scene_durations.append(veo_duration)

# Generate Veo clips with specific durations
for scene, duration in zip(scenes, scene_durations):
    config = VeoGenerationConfig(
        prompt=scene.prompt,
        duration=duration,  # Use MIDI-aligned duration
        include_audio=False  # Mute Veo's audio
    )
    video = veo_client.generate_video(config)

# Concatenate and add music using FFmpeg
ffmpeg -f concat -i clips.txt -i music.mp3 \
  -c:v copy -c:a aac -shortest output.mp4
```

**Pros:**
- ✅ Frame-accurate synchronization possible
- ✅ Respects musical structure (verse/chorus boundaries)
- ✅ Leverages existing MIDI ecosystem
- ✅ Works with any song that has MIDI

**Cons:**
- ❌ Requires MIDI file (not always available)
- ❌ Scene durations limited to 4/6/8s chunks
- ❌ Manual segmentation for longer phrases

**Accuracy:** ⭐⭐⭐⭐⭐
**Complexity:** Medium
**MIDI Required:** Yes

---

### Solution B: Variable-Length Segment Mapping

**How It Works:**

1. Analyze music structure (intro, verse, chorus, bridge)
2. Map each musical section to Veo generation parameters
3. For segments >8s, split into multiple clips
4. Use strategic durations (4, 6, 8s) to minimize discontinuities

**Example Mapping:**

```python
music_structure = {
    "intro":   {"duration": 8,  "clips": 1},  # Single 8s clip
    "verse1":  {"duration": 16, "clips": 2},  # Two 8s clips
    "chorus":  {"duration": 12, "clips": 2},  # 4s + 8s clips
    "bridge":  {"duration": 6,  "clips": 1},  # Single 6s clip
    "verse2":  {"duration": 16, "clips": 2},  # Two 8s clips
    "outro":   {"duration": 4,  "clips": 1}   # Single 4s clip
}

# Generate with strategic durations
for section, params in music_structure.items():
    if params["clips"] == 1:
        generate_veo_clip(duration=params["duration"])
    else:
        durations = distribute_duration(
            total=params["duration"],
            clips=params["clips"],
            allowed=[4, 6, 8]
        )
        for d in durations:
            generate_veo_clip(duration=d)
```

**Pros:**
- ✅ No MIDI required
- ✅ Adapts to musical structure
- ✅ Minimizes jarring transitions
- ✅ Simple implementation

**Cons:**
- ❌ Still limited to 4/6/8s segments
- ❌ Manual music analysis required
- ❌ Less precise than MIDI

**Accuracy:** ⭐⭐⭐
**Complexity:** Low
**MIDI Required:** No

---

### Solution C: Beat-Matched Time-Stretch

**How It Works:**

1. Generate Veo clips at standard durations (4, 6, or 8s)
2. Use FFmpeg to **time-stretch** clips slightly to match exact beat positions
3. Concatenate with crossfades aligned to beats

**FFmpeg Time-Stretching:**

```bash
# Stretch 8-second video to 8.2 seconds to align with beat
ffmpeg -i input.mp4 -filter:v "setpts=1.025*PTS" -an stretched.mp4

# Speed up 6-second video to 5.8 seconds
ffmpeg -i input.mp4 -filter:v "setpts=0.967*PTS" -an sped_up.mp4

# Concatenate with beat-aligned crossfades
ffmpeg -i clip1.mp4 -i clip2.mp4 -filter_complex \
  "[0:v][1:v]xfade=transition=fade:duration=0.5:offset=7.7[out]" \
  -map "[out]" output.mp4
```

**Pros:**
- ✅ Can achieve near-perfect beat alignment
- ✅ Works with any video source
- ✅ Preserves visual quality (small adjustments <5%)

**Cons:**
- ❌ Requires careful timing calculations
- ❌ May introduce subtle motion artifacts
- ❌ Complex FFmpeg filter chains

**Accuracy:** ⭐⭐⭐⭐
**Complexity:** High
**MIDI Required:** Optional

---

### Solution D: Karaoke-Style Overlay

**How It Works:**

1. Generate Veo clips independently (any duration)
2. Concatenate all clips
3. Add synchronized lyric overlays using MIDI/LRC timing data
4. Overlay system handles word-level synchronization

**Note:** This is already documented in `ImageAI-VideoProject-PRD.md` (lines 272-328)

**FFmpeg Karaoke Implementation:**

```bash
# Generate subtitle file from MIDI timing (SRT or ASS format)

# Add bouncing ball + lyrics overlay
ffmpeg -i video.mp4 -i ball.png \
  -filter_complex "[0:v][1:v]overlay=x='lerp(100,500,t/8)':y='400-abs(sin(t*3.14)*50)'[v1]; \
  [v1]subtitles=lyrics.srt:force_style='Fontsize=32,PrimaryColour=&H00FFFF&'[out]" \
  -map "[out]" -map 0:a karaoke_output.mp4
```

**Pros:**
- ✅ Visual synchronization without affecting video generation
- ✅ Proven technique (used by all karaoke systems)
- ✅ Can add multiple overlay styles
- ✅ Frame-accurate lyric display

**Cons:**
- ❌ Doesn't solve video-music misalignment
- ❌ Only addresses lyric display
- ❌ Still need Solution A, B, or C for clip timing

**Accuracy:** ⭐⭐⭐⭐⭐ (for lyric display)
**Complexity:** Medium
**MIDI Required:** Recommended

---

## Comparison Matrix

| Approach | Accuracy | Complexity | MIDI Required | Best For |
|----------|----------|------------|---------------|----------|
| **MIDI-Driven Scene Timing** | ⭐⭐⭐⭐⭐ | Medium | Yes | Music videos with MIDI |
| **Variable-Length Mapping** | ⭐⭐⭐ | Low | No | Simple projects, manual control |
| **Beat-Matched Time-Stretch** | ⭐⭐⭐⭐ | High | Optional | Perfecting alignment |
| **Karaoke Overlay** | ⭐⭐⭐⭐⭐ | Medium | Recommended | Lyric display only |
| **Veo Native Audio** | ⭐ | N/A | N/A | ❌ NOT SUITABLE |

**Recommended Combination:**
- **Primary:** Solution A (MIDI-Driven Scene Timing)
- **Enhancement:** Solution D (Karaoke Overlay)
- **Refinement:** Solution C (Beat-Matched Time-Stretch) for critical scenes

---

## Technical Implementation Plan

### Phase 1: Fix Veo Duration Parameter (IMMEDIATE) 🔴

**Priority:** P0 - Blocking feature development
**Estimated Time:** 30 minutes
**Files to Modify:**
- `core/video/veo_client.py` (lines 244-270)
- `core/video/veo_client.py` (line 45) - Update default validation

**Changes:**

```python
# core/video/veo_client.py

# Line 45: Update VeoGenerationConfig dataclass
@dataclass
class VeoGenerationConfig:
    model: VeoModel = VeoModel.VEO_3_GENERATE
    prompt: str = ""
    duration: int = 8  # ✅ Keep default, but add validation
    aspect_ratio: str = "16:9"
    resolution: str = "1080p"
    include_audio: bool = False  # ✅ Default to False for music videos
    seed: Optional[int] = None

    def __post_init__(self):
        # ✅ ADD: Validate duration
        if self.duration not in [4, 6, 8]:
            raise ValueError(f"Duration must be 4, 6, or 8 seconds, got {self.duration}")

# Lines 244-270: Fix generate_video method
def generate_video(self, config: VeoGenerationConfig) -> VeoResult:
    """Generate video using Veo API"""

    # ✅ REMOVE: Don't enhance prompt with duration
    # enhanced_prompt = f"{config.duration}-second video of {config.prompt}"

    # ✅ ADD: Include duration parameter
    video_config = types.GenerateVideosConfig(
        aspect_ratio=config.aspect_ratio,
        resolution=config.resolution,
        duration=config.duration  # ✅ ADD THIS LINE
    )

    response = self.client.models.generate_videos(
        model=config.model.value,
        prompt=config.prompt,  # ✅ Use original prompt
        config=video_config,
        image=seed_image
    )

    # Rest of implementation unchanged
```

**Testing:**
```python
# Test all three durations
for duration in [4, 6, 8]:
    config = VeoGenerationConfig(
        prompt="Test scene",
        duration=duration,
        include_audio=False
    )
    result = veo_client.generate_video(config)
    assert result.success
    print(f"✅ {duration}s video generated")
```

---

### Phase 2: Implement MIDI Processing Module 🟡

**Priority:** P1 - Required for music sync
**Estimated Time:** 4 hours
**New Files:**
- `core/video/midi_processor.py` (new file)
- `requirements.txt` (add `pretty-midi`)

**Implementation:**

```python
# core/video/midi_processor.py

from pathlib import Path
from typing import List, Tuple, Optional
import pretty_midi

class MidiTimingExtractor:
    """Extract timing data from MIDI files for video synchronization"""

    def __init__(self, midi_path: Path):
        """
        Initialize MIDI processor.

        Args:
            midi_path: Path to MIDI file
        """
        self.midi_path = midi_path
        self.midi = pretty_midi.PrettyMIDI(str(midi_path))
        self.beats = self.midi.get_beats()
        self.measures = self.midi.get_downbeats()
        self.tempo_changes = self.midi.get_tempo_changes()

    def align_scenes_to_veo_durations(
        self,
        scene_count: int,
        total_duration: Optional[float] = None,
        alignment: str = "measure"
    ) -> List[int]:
        """
        Distribute scenes across song duration using Veo-compatible durations.

        Args:
            scene_count: Number of scenes to generate
            total_duration: Target total duration (uses MIDI length if None)
            alignment: "beat" | "measure" | "section"

        Returns:
            List of durations (4, 6, or 8 seconds) for each scene
        """
        if total_duration is None:
            total_duration = self.midi.get_end_time()

        boundaries = self.measures if alignment == "measure" else self.beats
        veo_durations = [4, 6, 8]

        # Calculate ideal duration per scene
        ideal_duration = total_duration / scene_count

        # Snap to closest Veo-compatible duration
        scene_durations = []
        remaining_time = total_duration

        for i in range(scene_count):
            # Find closest Veo duration to ideal
            veo_duration = min(veo_durations, key=lambda x: abs(x - ideal_duration))

            # Ensure we don't exceed total duration
            if remaining_time < veo_duration:
                veo_duration = min([d for d in veo_durations if d <= remaining_time], default=4)

            scene_durations.append(veo_duration)
            remaining_time -= veo_duration

        return scene_durations

    def get_beat_timestamps(self) -> List[float]:
        """Get all beat timestamps in seconds"""
        return self.beats.tolist()

    def get_measure_timestamps(self) -> List[float]:
        """Get all measure (downbeat) timestamps in seconds"""
        return self.measures.tolist()

    def get_tempo_at_time(self, time: float) -> float:
        """
        Get tempo (BPM) at specific time.

        Args:
            time: Time in seconds

        Returns:
            Tempo in beats per minute
        """
        tempo_times, tempos = self.tempo_changes

        # Find tempo at or before the given time
        for i in range(len(tempo_times) - 1, -1, -1):
            if tempo_times[i] <= time:
                return tempos[i]

        return tempos[0] if len(tempos) > 0 else 120.0

    def extract_lyrics_timing(self) -> List[Tuple[float, str]]:
        """
        Extract lyric events from MIDI for karaoke.

        Returns:
            List of (timestamp, lyric_text) tuples
        """
        lyrics = []

        for instrument in self.midi.instruments:
            # MIDI lyrics are often stored in specific tracks
            if instrument.name.lower() in ["lyrics", "words", "text"]:
                for note in instrument.notes:
                    # Assuming note pitch encodes lyric character/word
                    lyrics.append((note.start, chr(note.pitch)))

        # Also check for lyric metadata events
        for text_event in self.midi.text_events:
            lyrics.append((text_event.time, text_event.text))

        return sorted(lyrics, key=lambda x: x[0])

    def get_song_sections(self) -> List[Tuple[float, float, str]]:
        """
        Identify song sections (verse, chorus, bridge) based on structure.

        Returns:
            List of (start_time, end_time, section_name) tuples
        """
        # This is a simplified heuristic - real implementation would use
        # more sophisticated music structure analysis
        sections = []
        measures = self.get_measure_timestamps()

        # Example: Assume typical pop structure
        section_length = 8  # measures
        section_names = ["intro", "verse1", "chorus", "verse2", "chorus", "bridge", "chorus", "outro"]

        for i, name in enumerate(section_names):
            start_idx = i * section_length
            end_idx = (i + 1) * section_length

            if start_idx < len(measures):
                start_time = measures[start_idx]
                end_time = measures[end_idx] if end_idx < len(measures) else self.midi.get_end_time()
                sections.append((start_time, end_time, name))

        return sections

    def snap_to_nearest_beat(self, time: float, tolerance: float = 0.1) -> float:
        """
        Snap timestamp to nearest beat.

        Args:
            time: Time in seconds
            tolerance: Maximum distance to snap (seconds)

        Returns:
            Nearest beat timestamp
        """
        beats = self.get_beat_timestamps()
        closest_beat = min(beats, key=lambda b: abs(b - time))

        if abs(closest_beat - time) <= tolerance:
            return closest_beat
        return time
```

**Add to requirements.txt:**
```
pretty-midi>=0.2.10
```

**Testing:**
```python
# Test MIDI processing
midi = MidiTimingExtractor(Path("test_song.mid"))

# Test duration alignment
durations = midi.align_scenes_to_veo_durations(
    scene_count=10,
    alignment="measure"
)
print(f"Scene durations: {durations}")
assert all(d in [4, 6, 8] for d in durations)

# Test beat extraction
beats = midi.get_beat_timestamps()
print(f"First 10 beats: {beats[:10]}")

# Test lyric extraction
lyrics = midi.extract_lyrics_timing()
print(f"Lyrics: {lyrics[:5]}")
```

---

### Phase 3: Update Video Project GUI 🟡

**Priority:** P1 - User interface for MIDI sync
**Estimated Time:** 6 hours
**Files to Modify:**
- `gui/video/video_project_tab.py`
- `gui/video/video_project_dialog.py`

**GUI Changes:**

1. **Add MIDI File Upload:**
```python
# In VideoProjectTab
self.midi_file_input = QLineEdit()
self.midi_file_button = QPushButton("Browse MIDI...")
self.midi_file_button.clicked.connect(self._select_midi_file)

layout.addRow("MIDI File:", midi_layout)

def _select_midi_file(self):
    file_path, _ = QFileDialog.getOpenFileName(
        self,
        "Select MIDI File",
        "",
        "MIDI Files (*.mid *.midi);;All Files (*)"
    )
    if file_path:
        self.midi_file_input.setText(file_path)
        self._update_scene_durations_from_midi()
```

2. **Add Duration Selector Per Scene:**
```python
# Add duration dropdown to scene list
class SceneWidget(QWidget):
    def __init__(self, scene_data):
        super().__init__()
        layout = QHBoxLayout()

        self.prompt_edit = QLineEdit(scene_data.get("prompt", ""))
        self.duration_combo = QComboBox()
        self.duration_combo.addItems(["4 seconds", "6 seconds", "8 seconds"])
        self.duration_combo.setCurrentText(f"{scene_data.get('duration', 8)} seconds")

        layout.addWidget(self.prompt_edit)
        layout.addWidget(self.duration_combo)
        self.setLayout(layout)
```

3. **Add Sync Mode Options:**
```python
self.sync_mode_group = QGroupBox("Synchronization Mode")
self.sync_mode_layout = QVBoxLayout()

self.sync_beat = QRadioButton("Beat-aligned (faster cuts)")
self.sync_measure = QRadioButton("Measure-aligned (4-beat sections)")
self.sync_section = QRadioButton("Section-aligned (verse/chorus)")
self.sync_measure.setChecked(True)

self.sync_mode_layout.addWidget(self.sync_beat)
self.sync_mode_layout.addWidget(self.sync_measure)
self.sync_mode_layout.addWidget(self.sync_section)
self.sync_mode_group.setLayout(self.sync_mode_layout)
```

4. **Update Video Generation Logic:**
```python
def _generate_videos(self):
    """Generate videos with MIDI-aligned durations"""

    # Check if MIDI file is provided
    midi_file = self.midi_file_input.text()

    if midi_file and Path(midi_file).exists():
        # Use MIDI-driven timing
        from core.video.midi_processor import MidiTimingExtractor

        midi = MidiTimingExtractor(Path(midi_file))

        # Get sync mode
        if self.sync_beat.isChecked():
            alignment = "beat"
        elif self.sync_measure.isChecked():
            alignment = "measure"
        else:
            alignment = "section"

        # Align scene durations to music
        scene_durations = midi.align_scenes_to_veo_durations(
            scene_count=len(self.scenes),
            total_duration=self.target_duration,
            alignment=alignment
        )

        # Assign durations to scenes
        for scene, duration in zip(self.scenes, scene_durations):
            scene["duration"] = duration
    else:
        # Use manual durations from GUI
        for i, scene_widget in enumerate(self.scene_widgets):
            duration_text = scene_widget.duration_combo.currentText()
            duration = int(duration_text.split()[0])  # Extract number
            self.scenes[i]["duration"] = duration

    # Generate Veo clips
    for scene in self.scenes:
        config = VeoGenerationConfig(
            prompt=scene["prompt"],
            duration=scene["duration"],
            include_audio=False  # Mute Veo's audio for music videos
        )
        result = self.veo_client.generate_video(config)
        # ... handle result
```

---

### Phase 4: FFmpeg Post-Processing Integration 🟢

**Priority:** P2 - Final assembly
**Estimated Time:** 3 hours
**Files to Modify:**
- `core/video/ffmpeg_renderer.py`

**Implementation:**

```python
# core/video/ffmpeg_renderer.py

import subprocess
from pathlib import Path
from typing import Optional, List

class FFmpegRenderer:
    """FFmpeg-based video post-processing"""

    def add_music_track_with_sync(
        self,
        video_path: Path,
        audio_path: Path,
        midi_path: Optional[Path] = None,
        volume: float = 1.0,
        fade_in: float = 0.0,
        fade_out: float = 0.0
    ) -> Path:
        """
        Add music track to video with optional MIDI-based beat sync.

        Args:
            video_path: Input video file
            audio_path: Music audio file
            midi_path: Optional MIDI file for beat markers
            volume: Audio volume (0.0-1.0)
            fade_in: Fade in duration (seconds)
            fade_out: Fade out duration (seconds)

        Returns:
            Path to output video with music
        """
        output_path = video_path.parent / f"{video_path.stem}_with_music.mp4"

        cmd = [
            "ffmpeg", "-y",  # Overwrite output
            "-i", str(video_path),
            "-i", str(audio_path),
            "-filter_complex"
        ]

        # Build audio filter
        audio_filter = f"[1:a]volume={volume}"

        if fade_in > 0:
            audio_filter += f",afade=t=in:st=0:d={fade_in}"

        if fade_out > 0:
            # Calculate fade out start time
            duration = self._get_duration(video_path)
            fade_start = duration - fade_out
            audio_filter += f",afade=t=out:st={fade_start}:d={fade_out}"

        audio_filter += "[aout]"

        cmd.extend([
            audio_filter,
            "-map", "0:v",  # Video from first input
            "-map", "[aout]",  # Filtered audio
            "-c:v", "copy",  # Copy video codec
            "-c:a", "aac",  # Re-encode audio as AAC
            "-shortest",  # Match video duration
            str(output_path)
        ])

        subprocess.run(cmd, check=True)
        return output_path

    def add_karaoke_overlay(
        self,
        video_path: Path,
        lyrics: List[Tuple[float, str]],
        style: str = "bouncing_ball",
        position: str = "bottom"
    ) -> Path:
        """
        Add karaoke-style lyric overlay to video.

        Args:
            video_path: Input video file
            lyrics: List of (timestamp, lyric_text) tuples
            style: "bouncing_ball" | "highlight" | "fade"
            position: "top" | "bottom" | "center"

        Returns:
            Path to output video with karaoke overlay
        """
        output_path = video_path.parent / f"{video_path.stem}_karaoke.mp4"

        # Generate subtitle file (SRT format)
        srt_path = self._generate_srt(lyrics)

        # Position mapping
        y_positions = {
            "top": 50,
            "center": "h/2",
            "bottom": "h-100"
        }
        y_pos = y_positions.get(position, "h-100")

        # Style configuration
        subtitle_style = (
            f"Fontsize=32,"
            f"PrimaryColour=&H00FFFF&,"
            f"OutlineColour=&H000000&,"
            f"Outline=2,"
            f"Alignment=2,"  # Bottom center
            f"MarginV=50"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", f"subtitles={srt_path}:force_style='{subtitle_style}'",
            "-c:a", "copy",
            str(output_path)
        ]

        subprocess.run(cmd, check=True)
        return output_path

    def _generate_srt(self, lyrics: List[Tuple[float, str]]) -> Path:
        """Generate SRT subtitle file from lyrics"""
        srt_path = Path("/tmp/lyrics.srt")

        with open(srt_path, "w", encoding="utf-8") as f:
            for i, (timestamp, text) in enumerate(lyrics):
                # SRT format:
                # 1
                # 00:00:01,000 --> 00:00:03,000
                # Lyric text

                start_time = self._format_timestamp(timestamp)
                end_time = self._format_timestamp(timestamp + 2.0)  # 2s display

                f.write(f"{i+1}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")

        return srt_path

    def _format_timestamp(self, seconds: float) -> str:
        """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _get_duration(self, video_path: Path) -> float:
        """Get video duration in seconds"""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())
```

---

## Implementation Roadmap

### Sprint 1: Foundation (Week 1)

**Goals:**
- ✅ Fix Veo duration parameter bug
- ✅ Add MIDI processing module
- ✅ Update requirements.txt

**Deliverables:**
1. Working 4/6/8-second duration control
2. MIDI file parsing functional
3. Basic beat/measure extraction

**Testing:**
- Generate videos at all three durations
- Parse sample MIDI files
- Verify beat timestamp accuracy

---

### Sprint 2: GUI Integration (Week 2)

**Goals:**
- ✅ Add MIDI file upload to GUI
- ✅ Implement duration selectors per scene
- ✅ Add sync mode options

**Deliverables:**
1. MIDI file browser in Video Project tab
2. Per-scene duration controls
3. Beat/measure/section alignment modes

**Testing:**
- Load MIDI file and auto-assign durations
- Manual duration override per scene
- Verify alignment calculations

---

### Sprint 3: FFmpeg Post-Processing (Week 3)

**Goals:**
- ✅ Implement music track addition
- ✅ Add karaoke overlay system
- ✅ Integrate with video generation pipeline

**Deliverables:**
1. Music synchronization functional
2. Lyric overlay rendering
3. Complete end-to-end workflow

**Testing:**
- Generate multi-scene video with MIDI sync
- Verify audio-video alignment
- Test karaoke overlay display

---

### Sprint 4: Polish & Documentation (Week 4)

**Goals:**
- ✅ Error handling and edge cases
- ✅ User documentation
- ✅ Performance optimization

**Deliverables:**
1. Robust error messages
2. Help documentation in GUI
3. Example MIDI files and tutorials

**Testing:**
- Test with various MIDI formats
- Handle missing MIDI gracefully
- Verify performance with long videos

---

## Example Workflow

Here's a complete end-to-end example combining all solutions:

```python
from pathlib import Path
from core.video.veo_client import VeoClient, VeoGenerationConfig, VeoModel
from core.video.midi_processor import MidiTimingExtractor
from core.video.ffmpeg_renderer import FFmpegRenderer

# Step 1: Extract MIDI timing
midi_file = Path("american_reckoning.mid")
audio_file = Path("american_reckoning.mp3")
midi = MidiTimingExtractor(midi_file)

# Step 2: Define scenes with prompts
scenes = [
    {"prompt": "Elderly man on porch, golden hour, American flag"},
    {"prompt": "Rural farmland, wide shot, sunset"},
    {"prompt": "Close-up of weathered hands holding coffee mug"},
    {"prompt": "American flag waving in gentle breeze"},
    {"prompt": "Porch rocking chair, empty, peaceful"},
]

# Step 3: Align scene durations to music
scene_durations = midi.align_scenes_to_veo_durations(
    scene_count=len(scenes),
    total_duration=midi.midi.get_end_time(),
    alignment="measure"  # Align to musical measures
)

print(f"Scene durations: {scene_durations}")
# Example output: [8, 6, 8, 4, 8]

# Step 4: Generate Veo clips with MIDI-aligned durations
veo = VeoClient(api_key="YOUR_KEY")
clips = []

for scene, duration in zip(scenes, scene_durations):
    config = VeoGenerationConfig(
        model=VeoModel.VEO_3_GENERATE,
        prompt=scene["prompt"],
        duration=duration,  # Use MIDI-aligned duration (4, 6, or 8)
        aspect_ratio="16:9",
        resolution="1080p",
        include_audio=False,  # Mute Veo's audio
        seed=42
    )

    print(f"Generating {duration}s clip: {scene['prompt']}")
    result = veo.generate_video(config)

    if result.success:
        clips.append(result.video_path)
        print(f"✅ Saved: {result.video_path}")
    else:
        print(f"❌ Failed: {result.error}")

# Step 5: Concatenate clips (muted)
concat_output = Path("concatenated_muted.mp4")
veo.concatenate_clips(clips, concat_output, remove_audio=True)
print(f"✅ Concatenated video: {concat_output}")

# Step 6: Add music track with sync
ffmpeg = FFmpegRenderer()
video_with_music = ffmpeg.add_music_track_with_sync(
    video_path=concat_output,
    audio_path=audio_file,
    midi_path=midi_file,
    volume=0.8,
    fade_in=2.0,
    fade_out=3.0
)
print(f"✅ Video with music: {video_with_music}")

# Step 7: Add karaoke overlay (optional)
lyrics = midi.extract_lyrics_timing()
if lyrics:
    karaoke_output = ffmpeg.add_karaoke_overlay(
        video_path=video_with_music,
        lyrics=lyrics,
        style="bouncing_ball",
        position="bottom"
    )
    print(f"✅ Final video with karaoke: {karaoke_output}")
else:
    print("ℹ️ No lyrics found in MIDI, skipping karaoke overlay")
```

**Expected Output:**
```
Scene durations: [8, 6, 8, 4, 8]
Generating 8s clip: Elderly man on porch, golden hour, American flag
✅ Saved: /path/to/scene_001.mp4
Generating 6s clip: Rural farmland, wide shot, sunset
✅ Saved: /path/to/scene_002.mp4
Generating 8s clip: Close-up of weathered hands holding coffee mug
✅ Saved: /path/to/scene_003.mp4
Generating 4s clip: American flag waving in gentle breeze
✅ Saved: /path/to/scene_004.mp4
Generating 8s clip: Porch rocking chair, empty, peaceful
✅ Saved: /path/to/scene_005.mp4
✅ Concatenated video: /path/to/concatenated_muted.mp4
✅ Video with music: /path/to/concatenated_muted_with_music.mp4
✅ Final video with karaoke: /path/to/concatenated_muted_with_music_karaoke.mp4
```

---

## Key Takeaways

### Veo 3 Capabilities

1. ✅ **Variable durations supported:** 4, 6, or 8 seconds
2. ❌ **NOT fixed at 8 seconds** (common misconception)
3. ✅ **Duration is an API parameter** (not prompt text)
4. ❌ **No custom music synchronization** (FFmpeg required)

### Synchronization Strategy

1. **Use MIDI files** for precise timing data
2. **Align scenes** to musical structure (beats/measures)
3. **Generate clips** at strategic durations (4, 6, 8s)
4. **Post-process** with FFmpeg to add music
5. **Add karaoke overlays** for lyric synchronization

### Implementation Priority

1. **🔴 P0: Fix duration bug** (30 minutes)
2. **🟡 P1: Add MIDI processing** (4 hours)
3. **🟡 P1: Update GUI** (6 hours)
4. **🟢 P2: FFmpeg integration** (3 hours)

**Total Estimated Time:** ~14 hours (2 sprints)

---

## References

### Official Documentation

- **Veo API Reference:** https://ai.google.dev/gemini-api/docs/video
- **Vertex AI Veo 3 Preview:** https://cloud.google.com/vertex-ai/generative-ai/docs/models/veo/3-0-generate-preview
- **Model Reference:** https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation

### Research Papers

- **MuVi: Video-to-Music Generation:** https://arxiv.org/html/2410.12957v1
- **RFLAV: Rolling Flow for Audio-Video:** https://arxiv.org/html/2503.08307

### Tools & Libraries

- **pretty-midi:** https://github.com/craffel/pretty-midi
- **FFmpeg Filters:** https://ffmpeg.org/ffmpeg-filters.html
- **LiteLLM:** https://docs.litellm.ai/

### Related ImageAI Documentation

- **Video Project PRD:** `Plans/ImageAI-VideoProject-PRD.md`
- **Code Map:** `Docs/CodeMap.md`
- **Veo Client:** `core/video/veo_client.py`

---

**Document Version:** 1.0
**Last Updated:** 2025-10-14
**Author:** Claude Code (research-assistant + documentation)
**Status:** Ready for Implementation
