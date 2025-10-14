# MIDI/Lyrics Timing Synchronization Design

**Purpose**: Ensure perfect synchronization between MIDI timing, lyric display, and video generation for music videos.

**Created**: 2025-10-14
**Status**: Design Document

## Problem Statement

When generating music videos, we need to ensure:

1. Video scenes start/end at exact MIDI timestamps (beats, measures, or lyrics)
2. Lyrics appear at precise timing matching the audio
3. Veo video generation respects exact duration constraints from MIDI
4. Scene transitions align with musical boundaries (beats/measures)

## Current Infrastructure

### Existing Components

**`core/video/midi_processor.py`**:
- `MidiProcessor` class for extracting timing from MIDI files
- `MidiTimingData` dataclass with:
  - Beat timestamps
  - Measure (downbeat) timestamps
  - Lyric events with timing `(time, text)`
  - Tempo changes
  - Time signatures
  - Musical sections (verse, chorus, bridge)
- Methods:
  - `extract_timing()`: Get all timing data from MIDI
  - `align_scenes_to_beats()`: Snap scene boundaries to beats/measures
  - `extract_lyrics_with_timing()`: Get word-level lyric timing

**`core/video/project.py`**:
- `Scene` class with:
  - `source`: Original lyric text
  - `duration_sec`: Scene duration
  - `metadata`: Additional data storage
- `AudioTrack` class for audio file management

**`core/video/veo_client.py`**:
- `VeoGenerationConfig` with `duration` parameter (must match MIDI timing)
- `VeoModel` constraints for max duration (8s for VEO_3_GENERATE)

## Design Solution

### 1. Enhanced Scene Timing Metadata

Add MIDI timing information to each scene's `metadata`:

```python
scene.metadata = {
    'midi_start_time': 12.5,      # Exact MIDI timestamp (seconds)
    'midi_end_time': 16.0,         # Exact end timestamp
    'aligned_to': 'measure',       # 'beat', 'measure', 'lyric', or 'custom'
    'beat_markers': [12.5, 13.0, 13.5, 14.0, 14.5, 15.0, 15.5],  # Beats within scene
    'lyric_words': [               # Word-level lyric timing within scene
        {'time': 12.5, 'text': 'Walking', 'duration': 0.4},
        {'time': 12.9, 'text': 'down', 'duration': 0.3},
        {'time': 13.2, 'text': 'the', 'duration': 0.2},
        {'time': 13.4, 'text': 'street', 'duration': 0.6}
    ],
    'musical_section': 'verse',    # Detected section type
    'tempo_bpm': 120.0,           # Tempo at this scene
    'time_signature': '4/4'        # Time signature at this scene
}
```

### 2. MIDI-Aware Scene Generation Workflow

**New method**: `VideoProject.sync_scenes_to_midi(midi_path: Path, alignment: str = 'measure')`

```python
def sync_scenes_to_midi(self, midi_path: Path, alignment: str = 'measure',
                       snap_strength: float = 1.0) -> None:
    """
    Synchronize all scene timings to MIDI structure.

    Args:
        midi_path: Path to MIDI file
        alignment: 'beat', 'measure', 'lyric', or 'section'
        snap_strength: 0.0-1.0, how strongly to snap to grid (1.0 = exact)
    """
    from core.video.midi_processor import MidiProcessor

    processor = MidiProcessor()
    timing = processor.extract_timing(midi_path)

    # 1. If lyrics exist in MIDI, use them to update scene sources
    if timing.lyrics:
        self._update_scenes_from_midi_lyrics(timing.lyrics)

    # 2. Align scene boundaries to musical structure
    scene_dicts = [scene.to_dict() for scene in self.scenes]
    aligned = processor.align_scenes_to_beats(
        scene_dicts,
        timing,
        alignment=alignment,
        snap_strength=snap_strength
    )

    # 3. Update scene durations and metadata
    for scene, aligned_data in zip(self.scenes, aligned):
        scene.duration_sec = aligned_data['duration_sec']
        scene.metadata.update({
            'midi_start_time': aligned_data['start_time'],
            'midi_end_time': aligned_data['end_time'],
            'aligned_to': alignment,
            'beat_markers': aligned_data.get('beat_markers', []),
            'tempo_bpm': timing.tempo_bpm,
            'time_signature': timing.time_signature
        })

        # 4. Add word-level lyric timing for this scene
        scene_start = aligned_data['start_time']
        scene_end = aligned_data['end_time']

        scene_lyrics = [
            {'time': t - scene_start, 'text': text, 'duration': 0.5}
            for t, text in timing.lyrics
            if scene_start <= t < scene_end
        ]
        scene.metadata['lyric_words'] = scene_lyrics
```

### 3. Video Generation with Exact Timing

**Update `VideoGenerationThread._generate_video_clip()`** to respect MIDI timing:

```python
def _generate_video_clip(self):
    # ... existing code ...

    # Get exact duration from MIDI metadata (if available)
    if 'midi_start_time' in scene.metadata and 'midi_end_time' in scene.metadata:
        # Use EXACT duration from MIDI timing
        exact_duration = scene.metadata['midi_end_time'] - scene.metadata['midi_start_time']
        logger.info(f"Using MIDI-synchronized duration: {exact_duration:.3f}s")
    else:
        # Fall back to scene.duration_sec
        exact_duration = scene.duration_sec

    # Ensure duration doesn't exceed Veo model limits
    model_constraints = veo_client.MODEL_CONSTRAINTS[VeoModel.VEO_3_GENERATE]
    max_duration = model_constraints['max_duration']

    if exact_duration > max_duration:
        logger.warning(
            f"Scene duration {exact_duration:.1f}s exceeds Veo max {max_duration}s. "
            f"Consider splitting scene into multiple clips."
        )
        # Option 1: Clip to max duration (loses end content)
        exact_duration = max_duration
        # Option 2: Split into multiple clips (implement scene splitting)

    # Configure with EXACT duration
    config = VeoGenerationConfig(
        model=VeoModel.VEO_3_GENERATE,
        prompt=prompt,
        duration=int(round(exact_duration)),  # Veo requires integer seconds
        aspect_ratio=aspect_ratio,
        image=seed_image_path
    )

    # Store actual vs requested duration for validation
    scene.metadata['requested_duration'] = exact_duration
    scene.metadata['veo_duration'] = int(round(exact_duration))
```

### 4. Lyric Display Synchronization

**New component**: `LyricOverlayRenderer` for frame-accurate lyric display

```python
class LyricOverlayRenderer:
    """Render word-level lyrics synchronized to video frames"""

    def render_lyrics_to_video(self, video_path: Path, scene: Scene,
                               output_path: Path) -> Path:
        """
        Add synchronized lyric overlays to video using FFmpeg.

        Args:
            video_path: Input video file
            scene: Scene with lyric_words in metadata
            output_path: Output video path
        """
        import subprocess

        lyric_words = scene.metadata.get('lyric_words', [])
        if not lyric_words:
            return video_path  # No lyrics to overlay

        # Build FFmpeg drawtext filters for each word
        filters = []
        for word_data in lyric_words:
            start_time = word_data['time']
            duration = word_data['duration']
            text = word_data['text']

            # Escape text for FFmpeg
            text_escaped = text.replace("'", "\\\\'").replace(":", "\\:")

            # Create timed text overlay
            filter_str = (
                f"drawtext=text='{text_escaped}':"
                f"fontfile=/path/to/font.ttf:fontsize=48:fontcolor=white:"
                f"x=(w-text_w)/2:y=h-100:"  # Centered bottom
                f"enable='between(t,{start_time},{start_time + duration})'"
            )
            filters.append(filter_str)

        # Combine all filters
        filter_complex = ','.join(filters)

        # Run FFmpeg
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-vf', filter_complex,
            '-c:a', 'copy',  # Copy audio without re-encoding
            '-y', str(output_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        return output_path
```

### 5. Timing Validation and Debugging

**New utility**: `validate_timing_sync()`

```python
def validate_timing_sync(project: VideoProject) -> Dict[str, Any]:
    """
    Validate that video timing matches MIDI/audio timing.

    Returns report with any timing discrepancies.
    """
    report = {
        'total_scenes': len(project.scenes),
        'scenes_with_midi_timing': 0,
        'timing_errors': [],
        'total_video_duration': 0.0,
        'total_midi_duration': 0.0
    }

    for i, scene in enumerate(project.scenes):
        # Check if scene has MIDI timing metadata
        if 'midi_start_time' in scene.metadata:
            report['scenes_with_midi_timing'] += 1

            midi_duration = (
                scene.metadata['midi_end_time'] -
                scene.metadata['midi_start_time']
            )
            scene_duration = scene.duration_sec

            # Check for timing mismatch (>0.1s tolerance)
            if abs(midi_duration - scene_duration) > 0.1:
                report['timing_errors'].append({
                    'scene_index': i,
                    'scene_id': scene.id,
                    'midi_duration': midi_duration,
                    'scene_duration': scene_duration,
                    'difference': abs(midi_duration - scene_duration)
                })

            report['total_midi_duration'] += midi_duration

        report['total_video_duration'] += scene.duration_sec

    return report
```

## Implementation Plan

### Phase 1: MIDI Integration (Priority: HIGH)
1. ✅ Add `sync_scenes_to_midi()` method to `VideoProject`
2. ✅ Update scene metadata structure to include MIDI timing
3. ✅ Modify `_generate_video_clip()` to use exact MIDI durations
4. ✅ Add timing validation utilities

### Phase 2: Lyric Display (Priority: MEDIUM)
1. Implement `LyricOverlayRenderer` class
2. Add lyric overlay option to render settings
3. Support multiple lyric display styles (karaoke, fade-in, etc.)
4. Add font selection and styling options

### Phase 3: Advanced Features (Priority: LOW)
1. Auto-detect optimal scene split points for long durations
2. Beat-synchronized visual effects (pulse on beats)
3. Section-aware styling (different looks for verse/chorus)
4. Multi-track audio mixing support

## Testing Strategy

### Unit Tests
- `test_midi_scene_alignment()`: Verify scene boundaries snap correctly
- `test_exact_duration_preservation()`: Ensure MIDI durations preserved
- `test_lyric_timing_accuracy()`: Validate word-level timing

### Integration Tests
- Generate test video with known MIDI file
- Measure video duration frame-by-frame
- Compare with MIDI timestamps (tolerance: ±1 frame @ 24fps = ±0.042s)

### User Testing
1. Import MIDI with lyrics
2. Sync scenes to measures
3. Generate video with Veo
4. Verify lyrics appear at correct timestamps
5. Check audio/video sync throughout

## Technical Constraints

### Veo Limitations
- **Integer duration only**: Veo accepts only whole seconds
  - Round MIDI timing: `int(round(exact_duration))`
  - Max error: ±0.5s per scene
  - Cumulative error can drift over long videos

**Mitigation**:
- Keep scenes aligned to measure boundaries (usually whole seconds)
- Use `snap_strength=1.0` for exact alignment
- Periodically "reset" timing at section boundaries

### FFmpeg Frame Accuracy
- Frame-accurate timing requires `-vsync 0` and careful filter timing
- Text overlay timing uses decimal seconds
- Font rendering can affect performance

### MIDI File Quality
- Not all MIDI files have lyric events
- Tempo changes complicate timing calculations
- Need fallback for MIDI-less workflows

## Success Criteria

1. **Timing Accuracy**: Video scenes start/end within ±0.1s of MIDI timestamps
2. **Lyric Sync**: Words appear within ±0.05s of intended time
3. **No Drift**: Timing error doesn't accumulate over video length
4. **Robustness**: System handles MIDI with tempo changes, time signature changes
5. **User Experience**: Simple "Sync to MIDI" button in GUI

## Future Enhancements

1. **Phoneme-level alignment**: Use speech synthesis tools for syllable timing
2. **Beat detection from audio**: Support MP3/WAV without MIDI
3. **Visual beat indicators**: Animated markers on timeline
4. **Export timing data**: Generate subtitle files (SRT, VTT)
5. **Real-time preview**: Scrub timeline with synced lyric display

## References

- Google Veo API: https://ai.google.dev/gemini-api/docs/video
- pretty_midi documentation: https://craffel.github.io/pretty-midi/
- FFmpeg drawtext filter: https://ffmpeg.org/ffmpeg-filters.html#drawtext
- MusicXML format: For enhanced music structure analysis
