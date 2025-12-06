# Lip-Sync Implementation Checklist

*Last Updated: 2025-12-06 11:21*

## Overview

This is an actionable implementation checklist for integrating MuseTalk lip-sync into ImageAI. Tasks are ordered by dependency and sized for single work sessions.

**Pipeline:** `[Video/Image] + [Audio] → [MuseTalk] → [Lip-Synced Video]`

---

## Phase 1: MuseTalk Core Integration

**Goal:** Get MuseTalk running locally with auto-install support

**Status:** In Progress - Core structure complete, needs real MuseTalk inference integration

### 1.1 Infrastructure Setup

- [x] **Create `core/musetalk_installer.py`** (~200 lines)
  - [x] Import pattern from `core/package_installer.py`
  - [x] `MuseTalkPackageInstaller(QThread)` class
    - [x] `progress = Signal(str)`
    - [x] `finished = Signal(bool, str)`
    - [x] `percentage = Signal(int)`
  - [x] `MuseTalkModelDownloader(QThread)` class
    - [x] Download from HuggingFace repos
    - [x] Progress tracking per model file
    - [x] Resume support for interrupted downloads
  - [x] `get_musetalk_packages() -> Tuple[List[str], str]`
    - [x] Detect GPU via `detect_nvidia_gpu()`
    - [x] Return CUDA or CPU torch version
  - [x] `check_musetalk_installed() -> bool`
    - [x] Check pip packages exist
    - [x] Check model weights exist
  - [x] `get_musetalk_model_path() -> Path`
    - [x] Platform-specific: `~/.cache/imageai/musetalk/`

### 1.2 Package Dependencies

**Packages to install (~2GB):**

```
Core:
- [x] torch==2.4.1 (or CPU version based on GPU detection)
- [x] torchvision==0.19.1

MMLab Stack:
- [x] mmengine
- [x] mmcv>=2.0.1
- [x] mmdet>=3.1.0
- [x] mmpose>=1.1.0

MuseTalk Specific:
- [x] diffusers>=0.21.0
- [x] transformers>=4.30.0
- [x] accelerate
- [x] av (video processing)
```

### 1.3 Model Downloads

**Models to download (~5GB total):**

| Model | Source | Size | File |
|-------|--------|------|------|
| [x] MuseTalk core | `TMElyralab/MuseTalk` | ~1.5GB | `musetalk/pytorch_model.bin` |
| [x] DWPose | `yzd-v/DWPose` | ~300MB | `dwpose/dw-ll_ucoco_384.pth` |
| [x] Face parsing | `Linaqruf/insightface` | ~95MB | `face-parse-bisent/*.pth` |
| [x] VAE | `stabilityai/sd-vae-ft-mse` | ~335MB | `sd-vae-ft-mse/*.bin` |
| [x] Whisper | `openai/whisper-tiny` | ~75MB | `whisper/tiny.pt` |

**Storage structure:**
```
~/.cache/imageai/musetalk/
├── musetalk/
│   ├── musetalk.json
│   └── pytorch_model.bin
├── dwpose/
│   └── dw-ll_ucoco_384.pth
├── face-parse-bisent/
│   ├── 79999_iter.pth
│   └── resnet18-5c106cde.pth
├── sd-vae-ft-mse/
│   ├── config.json
│   └── diffusion_pytorch_model.bin
└── whisper/
    └── tiny.pt
```

---

## Phase 1.4: Install Dialog

- [x] **Create `gui/video/musetalk_install_dialog.py`** (~150 lines)
  - [x] Follow pattern from `gui/install_dialog.py`
  - [x] `MuseTalkInstallConfirmDialog(QDialog)`
    - [x] Show GPU detection status
    - [x] Show disk space requirements (~7GB)
    - [x] List what will be installed
    - [x] Install / Cancel buttons
  - [x] `MuseTalkInstallProgressDialog(QDialog)`
    - [x] Progress bar with percentage
    - [x] Log output text area
    - [x] Cancel button (stops thread)
    - [x] Handle package install → model download sequence

---

## Phase 1.5: Provider Implementation

- [x] **Create `providers/video/base_lipsync.py`** (~50 lines)
  - [x] Abstract base class `BaseLipSyncProvider`
  - [x] `generate(video_path, audio_path, **kwargs) -> Path`
  - [x] `is_available() -> bool`
  - [x] `get_install_prompt() -> str`

- [x] **Create `providers/video/musetalk_provider.py`** (~250 lines)
  - [x] `MuseTalkProvider(BaseLipSyncProvider)`
  - [x] `__init__(model_path: Path = None)`
    - [x] Auto-detect model path if not provided
  - [x] `is_available() -> bool`
    - [x] Check models exist
    - [x] Check packages installed
  - [x] `generate(video_path, audio_path, bbox_shift=0, **kwargs) -> Path`
    - [x] Load models on first use (lazy init)
    - [x] Process video frames
    - [x] Extract audio features with Whisper
    - [~] Generate lip-synced frames - *Placeholder implementation, needs real MuseTalk inference*
    - [x] Encode output video with audio
  - [x] `_preprocess_video(video_path) -> List[np.ndarray]`
  - [x] `_extract_audio_features(audio_path) -> np.ndarray`
  - [~] `_generate_frames(frames, audio_features, bbox_shift) -> List[np.ndarray]` - *Needs real implementation*
  - [x] `_encode_video(frames, audio_path, output_path) -> Path`

- [x] **Update `providers/video/__init__.py`**
  - [x] Add `LipSyncBackend` enum
  - [x] Add `get_lipsync_provider(backend)` factory function

---

## Phase 1.6: GUI Widget

- [x] **Create `gui/video/lipsync_widget.py`** (~300 lines)
  - [x] `LipSyncWidget(QWidget)`
  - [x] **Source Input Section**
    - [x] Video/image file selector (drag-drop support)
    - [ ] Thumbnail preview
    - [ ] Duration display (if video)
  - [x] **Audio Input Section**
    - [x] Audio file selector (.wav, .mp3, .m4a)
    - [ ] Waveform preview (optional)
    - [ ] Duration display
  - [x] **Parameters Section**
    - [x] `bbox_shift` slider (-7 to +7, default 0)
    - [x] Tooltip: "Adjust mouth openness"
    - [x] Provider selector (future: MuseTalk/D-ID)
  - [x] **Action Buttons**
    - [x] "Generate Lip-Sync" button
    - [x] "Install MuseTalk" button (if not installed)
  - [x] **Progress/Output Section**
    - [x] Progress bar
    - [x] Status messages
    - [ ] Output video preview (after completion)
  - [x] **Signals**
    - [x] `generation_started = Signal()`
    - [x] `generation_finished = Signal(str)`  # output path
    - [x] `generation_failed = Signal(str)`  # error message

---

## Phase 1.7: Video Tab Integration

- [x] **Update `gui/video/video_project_tab.py`**
  - [x] Add "Lip-Sync" section/tab
  - [x] Wire up LipSyncWidget
  - [x] Connect to existing video clips (Veo/Sora output)
  - [x] Add to project workflow

- [ ] **Update video project data model** (if needed)
  - [ ] Store lip-sync settings in project
  - [ ] Track source video + audio pairs
  - [ ] Store output paths

---

## Phase 1.8: Testing & Documentation

- [ ] **Create `scripts/download_musetalk_models.py`** (~50 lines)
  - [ ] Standalone script for manual model download
  - [ ] CLI arguments for model selection
  - [ ] Progress output

- [ ] **Create `Docs/LipSyncGuide.md`** (~100 lines)
  - [ ] Installation instructions
  - [ ] GPU requirements
  - [ ] Parameter explanations
  - [ ] Known limitations
  - [ ] Troubleshooting

- [ ] **Manual Testing Checklist**
  - [ ] Test on Windows with NVIDIA GPU
  - [ ] Test model download (fresh install)
  - [ ] Test with video input
  - [ ] Test with image input (creates static video)
  - [ ] Test different bbox_shift values
  - [ ] Test cancellation during install
  - [ ] Test cancellation during generation

---

## Phase 2: D-ID API Integration (Cloud Backup)

**Status:** Pending Phase 1 completion

### 2.1 Configuration

- [ ] **Update `core/config.py`**
  - [ ] Add `DID_API_KEY` constant
  - [ ] Add `get_did_api_key() -> str` method
  - [ ] Add `set_did_api_key(key: str)` method
  - [ ] Support env var: `DID_API_KEY`

### 2.2 Provider

- [ ] **Create `providers/video/did_provider.py`** (~200 lines)
  - [ ] `DIDProvider(BaseLipSyncProvider)`
  - [ ] `BASE_URL = "https://api.d-id.com"`
  - [ ] `generate_talking_head(source_url, script_text, audio_url, voice_id)`
  - [ ] `_submit_job(payload) -> str`  # returns job_id
  - [ ] `_poll_job(job_id) -> dict`  # returns result
  - [ ] `_download_result(url) -> Path`

### 2.3 GUI Updates

- [ ] **Update `gui/video/lipsync_widget.py`**
  - [ ] Add provider dropdown (MuseTalk / D-ID)
  - [ ] Show API key status for D-ID
  - [ ] Link to D-ID settings

- [ ] **Update `gui/settings_widgets.py`**
  - [ ] Add D-ID API key field
  - [ ] Add "Test D-ID Connection" button

---

## Phase 3: Whisper Lyric Alignment

**Status:** Pending Phase 1-2

### 3.1 Core Utility

- [ ] **Create `core/video/whisper_sync.py`** (~150 lines)
  - [ ] `WhisperSync` class
  - [ ] `get_word_timestamps(audio_path) -> List[Dict]`
  - [ ] `align_lyrics(timestamps, lyrics_text) -> List[Dict]`
  - [ ] `export_lrc(aligned, output_path)`
  - [ ] `export_srt(aligned, output_path)`

### 3.2 Dependencies

- [ ] Add to requirements: `whisper-timestamped`

### 3.3 GUI

- [ ] **Create `gui/video/timestamp_editor.py`** (~200 lines)
  - [ ] Waveform display
  - [ ] Word markers (draggable)
  - [ ] Lyric text input
  - [ ] Play/pause with position indicator
  - [ ] Export LRC/SRT buttons

---

## Quick Reference

### File Locations

| File | Purpose | Lines (est) | Status |
|------|---------|-------------|--------|
| `core/musetalk_installer.py` | Package/model installation | ~200 | Done |
| `gui/video/musetalk_install_dialog.py` | Install UI | ~150 | Done |
| `providers/video/base_lipsync.py` | Base class | ~50 | Done |
| `providers/video/musetalk_provider.py` | MuseTalk integration | ~250 | Done (needs inference) |
| `gui/video/lipsync_widget.py` | Main lip-sync UI | ~300 | Done |
| `providers/video/did_provider.py` | D-ID cloud API | ~200 | Pending |
| `core/video/whisper_sync.py` | Lyric alignment | ~150 | Pending |
| `gui/video/timestamp_editor.py` | Manual timing editor | ~200 | Pending |

### Commands Reference

```bash
# Test MuseTalk packages manually
pip install torch==2.4.1 torchvision==0.19.1 --index-url https://download.pytorch.org/whl/cu121
pip install mmengine mmcv mmdet mmpose diffusers transformers accelerate av

# Download models manually
huggingface-cli download TMElyralab/MuseTalk --local-dir ~/.cache/imageai/musetalk/musetalk

# Run basic inference (standalone test)
python -c "from providers.video.musetalk_provider import MuseTalkProvider; p = MuseTalkProvider(); print(p.is_available())"
```

### Key Parameters

| Parameter | Range | Default | Effect |
|-----------|-------|---------|--------|
| `bbox_shift` | -7 to +7 | 0 | Mouth openness adjustment |

### GPU Requirements

| Provider | Min VRAM | Recommended |
|----------|----------|-------------|
| MuseTalk | 4GB | RTX 3060 12GB |
| D-ID | N/A (cloud) | N/A |

---

## Progress Tracking

Use this section to mark progress during implementation:

```
Phase 1: [########--] 80%  - Core structure complete, needs real inference
Phase 2: [----------] 0%   (blocked by Phase 1)
Phase 3: [----------] 0%   (blocked by Phase 1-2)
```

---

## Notes

- MuseTalk v1.5 (March 2025) is the target version
- MIT license allows commercial use
- Audio silences may cause Whisper hallucination - consider pre-processing
- Blur in tooth area is a known limitation
- Changing bbox_shift requires full re-preprocessing
- The MuseTalk inference code (`_generate_lipsync_frames`) is a placeholder - needs to integrate actual MuseTalk API
- **2025-12-06**: Fixed model download to use direct HuggingFace CDN URLs with fallback to huggingface_hub (like Real-ESRGAN pattern)

## Implementation Summary (2025-12-06)

### Files Created:
1. `core/musetalk_installer.py` - Package and model installation infrastructure
2. `gui/video/musetalk_install_dialog.py` - Installation confirmation and progress dialogs
3. `providers/video/base_lipsync.py` - Abstract base class for lip-sync providers
4. `providers/video/musetalk_provider.py` - MuseTalk provider implementation
5. `providers/video/__init__.py` - Updated with LipSync exports
6. `gui/video/lipsync_widget.py` - Main lip-sync UI widget

### Files Modified:
1. `gui/video/video_project_tab.py` - Added Lip-Sync tab integration
