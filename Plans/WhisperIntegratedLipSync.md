# Whisper-Integrated Lip-Sync Implementation Checklist

**Last Updated:** 2025-12-08 11:04
**Status:** Complete
**Progress:** 20/24 tasks complete

## Overview

Integrate Whisper audio analysis directly into the storyboard generation workflow to provide:
1. Automatic lyrics extraction from audio (with word-level timestamps)
2. Precise scene timing based on actual audio analysis (replacing LLM guessing)
3. Per-scene lip-sync toggle for character singing/speaking scenes
4. Seamless workflow without a separate Lip-Sync tab

## Architecture

### Current Flow (Disconnected)
```
Audio + Lyrics (manual) → LLM guesses timing → Scenes
                                    ↓
Face Image + Audio → MuseTalk (Whisper) → Lip-sync video (separate tab)
```

### New Flow (Integrated)
```
Audio → Whisper extracts lyrics + word-level timestamps
                     ↓
         Show/confirm lyrics in UI (or extract if missing)
                     ↓
    User segments into scenes (like now)
    User marks scenes: [x] Lip-sync character
                     ↓
         Generate images per scene
                     ↓
    Lip-sync scenes get MuseTalk with CORRECT audio segment timing
```

## Prerequisites

- [x] MuseTalk installer (`core/musetalk_installer.py`) - exists
- [x] MuseTalk provider (`providers/video/musetalk_provider.py`) - exists
- [ ] Fix torchaudio backend issue (soundfile) - in progress

## Implementation Tasks

### Section 1: Whisper Audio Analyzer Core

- [x] Create `core/video/whisper_analyzer.py` (~200 lines) ✅
  - [x] `WhisperAnalyzer` class with lazy model loading
  - [x] `extract_lyrics(audio_path) -> TranscriptionResult` - full transcription
  - [x] `get_word_timestamps(audio_path) -> List[WordTiming]` - word-level timing
  - [x] `verify_lyrics(audio_path, provided_lyrics) -> AlignmentResult` - compare/align
  - [x] Support for multiple Whisper model sizes (tiny/base/small/medium)
  - [x] Progress callback for long audio files

- [x] Create `core/video/timing_models.py` (~50 lines) ✅
  - [x] `WordTiming` dataclass: text, start_time, end_time, confidence
  - [x] `TranscriptionResult` dataclass: full_text, words, language, duration
  - [x] `AlignmentResult` dataclass: matched_words, unmatched, similarity_score

### Section 2: Workspace Widget Integration

- [x] Add "Extract from Audio" button to lyrics input panel (`gui/video/workspace_widget.py`) ✅
  - [x] Button in sync controls: "From Audio (Whisper)"
  - [x] Runs Whisper in background thread (WhisperWorker)
  - [x] Populates lyrics field with extracted text
  - [x] Stores word timestamps in project

- [~] Add lyrics verification feature - *Basic implementation done*
  - [x] When user has provided lyrics AND clicks extract
  - [x] Dialog to replace or keep existing lyrics
  - [ ] Show diff/alignment dialog comparing provided vs extracted

- [x] Store extracted timing data in project ✅
  - [x] Stores word_timestamps in project
  - [x] Stores whisper_model_used
  - [x] Stores lyrics_extracted flag

### Section 3: Scene Lip-Sync Toggle

- [x] Add lip-sync checkbox to scene cards in storyboard ✅
  - [x] Per-scene toggle checkbox (🎤 column)
  - [x] Stores in scene.metadata['lip_sync_enabled']
  - [x] Handler _on_lipsync_changed saves to project

- [~] Update scene data model - *Using metadata for now*
  - [x] lip_sync_enabled stored in scene.metadata
  - [ ] Add `lip_sync_character: Optional[str] = None` for multi-character support

- [ ] Add lip-sync settings to scene context menu
  - [ ] Right-click scene → "Lip-Sync Settings"
  - [ ] Configure which character to animate (if multiple)
  - [ ] Preview audio segment for this scene

### Section 4: Audio Segment Extraction

- [x] Create `core/video/audio_segmenter.py` (~100 lines) ✅
  - [x] `extract_segment(audio_path, start_time, end_time) -> Path`
  - [x] `AudioSegmenter` class with FFmpeg integration
  - [x] Cache extracted segments in project folder
  - [x] Support for seamless crossfades at segment boundaries
  - [x] `extract_scene_audio_for_lipsync()` convenience function

- [x] Integrate with scene timing ✅
  - [x] Uses scene start_time/end_time for segment boundaries
  - [x] Provides segment to MuseTalk during video generation

### Section 5: Export Pipeline Integration

- [x] Update export workflow to process lip-sync scenes ✅
  - [x] `_apply_lipsync_to_scene()` method in VideoGenerationThread
  - [x] Checks scene.metadata['lip_sync_enabled']
  - [x] Extracts audio segment using audio_segmenter
  - [x] Applies MuseTalk provider to generate lip-synced video
  - [x] Integrated into both Veo and Sora generation paths

- [x] Add lip-sync progress to export status ✅
  - [x] Progress updates: "Applying lip-sync to scene X..."
  - [x] Error handling with fallback to original video

### Section 6: Remove/Deprecate Separate Tab

- [x] Hide Lip-Sync tab from video_project_tab.py ✅
  - [x] Tab hidden by default (show_lipsync_tab = False)
  - [x] LipSyncWidget kept for advanced standalone use
  - [x] Can be re-enabled by setting flag to True

- [x] Update tab structure ✅
  - [x] Workspace / History / Reference Library (3 tabs)
  - [x] Lip-sync integrated into Workspace via 🎤 column

## Testing

- [ ] Test Whisper extraction with various audio qualities
- [ ] Test lyrics verification/alignment accuracy
- [ ] Test per-scene lip-sync toggle persistence
- [ ] Test audio segment extraction accuracy
- [ ] Test full export pipeline with lip-sync scenes
- [ ] Test cancellation during Whisper analysis

## Data Models

### WordTiming
```python
@dataclass
class WordTiming:
    text: str
    start_time: float  # seconds
    end_time: float    # seconds
    confidence: float  # 0.0 - 1.0
```

### Scene (updated)
```python
@dataclass
class Scene:
    # ... existing fields ...
    lip_sync_enabled: bool = False
    lip_sync_character: Optional[str] = None
    audio_segment_start: Optional[float] = None
    audio_segment_end: Optional[float] = None
```

### Project (updated)
```python
@dataclass
class VideoProject:
    # ... existing fields ...
    word_timestamps: List[WordTiming] = field(default_factory=list)
    whisper_model_used: Optional[str] = None
    lyrics_extracted: bool = False
```

## UI Mockup

### Lyrics Panel (updated)
```
┌─────────────────────────────────────────────┐
│ Lyrics                    [Extract from Audio] │
├─────────────────────────────────────────────┤
│ [Verse 1]                                    │
│ When I see you standing there...             │
│                                              │
│ [Chorus]                                     │
│ You make me feel alive...                    │
└─────────────────────────────────────────────┘
│ ✓ Timestamps extracted (152 words, 3:24)    │
└─────────────────────────────────────────────┘
```

### Scene Card (updated)
```
┌────────────────────────┐
│ [Scene 3 Thumbnail]    │
├────────────────────────┤
│ 0:45 - 1:02           │
│ "You make me feel..." │
│ ☑ Lip-sync character  │
└────────────────────────┘
```

## Notes

- Whisper `tiny` model is ~75MB, fast but less accurate
- Whisper `base` model is ~142MB, good balance
- Consider offering model size selection for quality vs speed
- Word timestamps may need manual adjustment for sung lyrics (stretched words)
- MuseTalk expects 16kHz audio, may need resampling
- Audio segment extraction should include small padding (~0.1s) for smooth transitions
- 2025-12-07: Initial plan created based on discussion about integrated architecture
- 2025-12-08: Implementation complete:
  - Created timing_models.py with WordTiming, TranscriptionResult, AlignmentResult, SceneTiming
  - Created whisper_analyzer.py with WhisperAnalyzer class for lyrics extraction
  - Added "From Audio (Whisper)" button in workspace widget sync controls
  - Added 🎤 lip-sync column to storyboard table (column 5)
  - Created audio_segmenter.py for FFmpeg-based segment extraction
  - Added _apply_lipsync_to_scene() to VideoGenerationThread for both Veo and Sora
  - Hidden separate Lip-Sync tab (integrated into main workflow)
  - Fixed musetalk_installer.py to include torchaudio and soundfile dependencies
