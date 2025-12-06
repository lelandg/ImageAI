# Lip-Sync and Talking Head Video Generation Integration Plan

*Last Updated: 2025-12-05 18:45*

## Key Clarification: Lip-Sync vs Video Generation

**MuseTalk is NOT a video generator** - it applies lip-sync to existing video/images.

### Workflow
```
[Video Content] + [Audio] → [MuseTalk] → [Lip-Synced Video]
     ↑
     └── From Veo 3, Sora, LTX, or imported footage
```

### Best Video Model Combinations

| Video Generator | + Lip-Sync | Quality | Use Case |
|-----------------|------------|---------|----------|
| **Veo 3.1** | MuseTalk | ★★★★★ | Generate avatar → lip-sync to audio |
| **Sora** | MuseTalk | ★★★★★ | Generate face video → lip-sync |
| **LTX Video** | MuseTalk | ★★★★☆ | Local video gen → lip-sync |
| **Imported Video** | MuseTalk | ★★★★★ | Use existing footage |

**Recommended Pipeline for Lyric Videos:**
1. Generate character/scene with Veo 3.1 or Sora
2. Apply MuseTalk lip-sync with song audio
3. Composite with lyric overlays

---

## Executive Summary

This plan outlines the integration of lip-sync and talking head video generation capabilities into ImageAI. Based on comprehensive research, we recommend a **multi-tier approach** starting with the highest quality solutions first.

**Priority Order:**
1. **Tier 1 (Best Quality):** MuseTalk (open-source SOTA) + D-ID API (commercial backup)
2. **Tier 2 (Proven Options):** Wav2Lip (accuracy) + SadTalker (expression)
3. **Tier 3 (Future):** Hallo2, LatentSync, AniPortrait

---

## Phase 1: MuseTalk Integration (SOTA Open-Source) ⏳ IN PROGRESS

**Goal:** Integrate MuseTalk as the primary local lip-sync engine

**Status:** Phase 1 is **0% complete**. Planning stage.

### Why MuseTalk First?

| Metric | MuseTalk | Wav2Lip | SadTalker |
|--------|----------|---------|-----------|
| **Lip Accuracy** | ★★★★★ | ★★★★★ | ★★★★☆ |
| **Visual Quality** | ★★★★★ | ★★★☆☆ | ★★★★☆ |
| **Emotional Expression** | ★★★★☆ | ★☆☆☆☆ | ★★★★★ |
| **License** | MIT (commercial OK) | Research only | Apache 2.0 |
| **Real-time Capable** | Yes (30fps on V100) | Yes (CPU or GPU) | No |
| **VRAM Required** | 4GB+ | 2GB | 8GB+ |

**Key Advantages:**
- MIT License - no commercial restrictions
- Version 1.5 (March 2025) - significantly improved quality
- Real-time capable on consumer GPUs
- Best balance of quality, speed, and flexibility
- No upscaler needed (unlike Wav2Lip)

### Tasks

1. Create MuseTalk installer module - **PENDING**
   - File: `core/musetalk_installer.py`
   - Follow pattern from `core/package_installer.py`
   - `MuseTalkPackageInstaller(QThread)` - pip packages
   - `MuseTalkModelDownloader(QThread)` - model weights
   - Auto-detect GPU (reuse `detect_nvidia_gpu()`)

2. Create install confirmation dialog - **PENDING**
   - File: `gui/video/musetalk_install_dialog.py`
   - Follow pattern from `gui/install_dialog.py`
   - Show disk space requirements (~7GB)
   - Show GPU detection status
   - Offer to auto-download models

3. Create MuseTalk provider - **PENDING**
   - File: `providers/video/musetalk_provider.py`
   - `MuseTalkProvider` class
   - Check if models installed, prompt if not
   - Support video + audio input
   - Output lip-synced video

4. Create GUI widget for lip-sync - **PENDING**
   - File: `gui/video/lipsync_widget.py`
   - Input: source video/image + audio file
   - Parameters: bbox_shift (mouth openness: -7 to +7)
   - "Install MuseTalk" button if not installed
   - Preview and progress display

5. Add to Video tab - **PENDING**
   - Add lip-sync section to video project workflow
   - Apply to generated Veo/Sora clips
   - Support imported footage

### Auto-Download System

**Following existing pattern from `core/package_installer.py`:**

```python
# core/musetalk_installer.py
class MuseTalkPackageInstaller(QThread):
    """Install MuseTalk pip dependencies."""
    progress = Signal(str)
    finished = Signal(bool, str)
    percentage = Signal(int)

class MuseTalkModelDownloader(QThread):
    """Download MuseTalk model weights from HuggingFace."""
    progress = Signal(str)
    finished = Signal(bool, str)
    percentage = Signal(int)

def get_musetalk_packages() -> Tuple[List[str], str]:
    """Get packages with GPU detection."""
    has_gpu, gpu_name = detect_nvidia_gpu()
    # Return appropriate torch version
```

### Model Storage

**Location:** `~/.cache/imageai/musetalk/` (platform-specific user cache)

**Model Structure (~5GB total):**
```
~/.cache/imageai/musetalk/
├── musetalk/
│   ├── musetalk.json (~1KB)
│   └── pytorch_model.bin (~1.5GB)
├── dwpose/
│   └── dw-ll_ucoco_384.pth (~300MB)
├── face-parse-bisent/
│   ├── 79999_iter.pth (~50MB)
│   └── resnet18-5c106cde.pth (~45MB)
├── sd-vae-ft-mse/
│   ├── config.json (~1KB)
│   └── diffusion_pytorch_model.bin (~335MB)
└── whisper/
    └── tiny.pt (~75MB)
```

**Download Sources (HuggingFace):**
- Main model: `TMElyralab/MuseTalk`
- DWPose: `yzd-v/DWPose`
- Face parsing: `Linaqruf/insightface`
- VAE: `stabilityai/sd-vae-ft-mse`
- Whisper: `openai/whisper-tiny`

### Technical Requirements

**Pip Dependencies (~2GB download):**
```bash
# Core (with GPU detection like Real-ESRGAN)
torch==2.4.1  # or CPU version
torchvision==0.19.1

# MMLab packages (via pip, not mim)
mmengine
mmcv>=2.0.1
mmdet>=3.1.0
mmpose>=1.1.0

# MuseTalk specific
diffusers>=0.21.0
transformers>=4.30.0
accelerate
av  # for video processing
```

**Disk Space:**
- Pip packages: ~2GB (with PyTorch CUDA)
- Model weights: ~5GB
- **Total: ~7GB** (same as Real-ESRGAN install)

**Key Parameters:**
- `bbox_shift`: Adjust mouth openness (-7 = less open, +7 = more open)
- `video_path`: Source video or directory of images
- `audio_path`: Audio file (wav recommended)

**Known Limitations:**
- Audio silences can cause Whisper hallucination
- Blur in tooth area, especially in close-ups
- Changing bbox_shift requires re-preprocessing

### Deliverables

- [ ] `providers/video/musetalk_provider.py` - MuseTalk integration
- [ ] `gui/video/lipsync_widget.py` - GUI for lip-sync generation
- [ ] Model download script: `scripts/download_musetalk_models.py`
- [ ] Documentation: `Docs/LipSyncGuide.md`

---

## Phase 2: D-ID API Integration (Commercial Backup)

**Goal:** Add D-ID API as a cloud-based alternative for users without GPU

**Status:** Phase 2 is **0% complete**. Pending Phase 1 completion.

### Why D-ID?

- **Easiest integration** - Just API calls
- **No GPU required** - Cloud processing
- **100 FPS rendering** - 4X faster than real-time
- **$50/month Launch plan** - Affordable entry point
- **150M+ videos generated** - Proven at scale

### Tasks

1. Add D-ID API key management - **PENDING**
   - Add to `core/config.py`
   - Store in user config directory
   - Support environment variable override

2. Create D-ID provider - **PENDING**
   - File: `providers/video/did_provider.py`
   - Implement `DIDProvider` class
   - Support:
     - Text-to-speech with avatar
     - Custom audio with avatar
     - URL-based source images

3. Add polling for job completion - **PENDING**
   - Async job submission
   - Status polling
   - Result download

4. GUI integration - **PENDING**
   - Add to lip-sync widget
   - Provider selection dropdown
   - API status indicator

### API Integration Pattern

```python
# D-ID API Integration
class DIDProvider:
    BASE_URL = "https://api.d-id.com"

    def generate_talking_head(
        self,
        source_url: str,          # URL to image/video
        script_text: str = None,   # Text for TTS
        audio_url: str = None,     # Or provide audio
        voice_id: str = "en-US-JennyNeural"
    ) -> dict:
        # Submit job to D-ID
        # Poll for completion
        # Return video URL
```

### Pricing Consideration

| Plan | Price | Videos (~30s) | Use Case |
|------|-------|---------------|----------|
| Launch | $50/mo | ~100 | Testing, light use |
| Scale | Custom | Custom | Production |

### Deliverables

- [ ] `providers/video/did_provider.py` - D-ID API integration
- [ ] API key management in config system
- [ ] GUI provider selection

---

## Phase 3: Whisper Integration for Lyric Alignment

**Goal:** Add word-level timestamp extraction for lyric-synced video

**Status:** Phase 3 is **0% complete**. Pending Phase 1-2.

### Recommended Library: whisper-timestamped

**Why whisper-timestamped?**
- More accurate word timestamps than base Whisper
- VAD to avoid hallucinations
- Little additional memory overhead
- Can process long files

### Tasks

1. Add whisper-timestamped dependency - **PENDING**
   ```bash
   pip install whisper-timestamped
   ```

2. Create WhisperSync utility - **PENDING**
   - File: `core/video/whisper_sync.py`
   - Extract word-level timestamps
   - Align with provided lyrics
   - Export to LRC/SRT format

3. Integrate with video project - **PENDING**
   - Auto-generate timestamps from audio
   - Manual adjustment interface
   - Preview with waveform

### Integration Pattern

```python
import whisper_timestamped as whisper

class WhisperSync:
    def get_word_timestamps(self, audio_path: str) -> List[Dict]:
        model = whisper.load_model("base")
        audio = whisper.load_audio(audio_path)
        result = whisper.transcribe(model, audio)

        return [
            {"text": w["text"], "start": w["start"], "end": w["end"]}
            for segment in result["segments"]
            for w in segment["words"]
        ]
```

### Deliverables

- [ ] `core/video/whisper_sync.py` - Whisper timestamp utility
- [ ] LRC/SRT export functionality
- [ ] GUI timestamp editor

---

## Phase 4: Additional Providers (Future)

**Goal:** Add alternative lip-sync providers for different use cases

### Wav2Lip (Accuracy Focus)

**Use Case:** When exact lip-sync is critical (e.g., dubbing)

**Pros:**
- Sub-frame precision lip-sync
- Fast inference (CPU or GPU)
- Well-documented

**Cons:**
- Research license (commercial needs Sync Labs API)
- Lower visual quality without upscaler
- No head motion generation

### SadTalker (Expression Focus)

**Use Case:** Expressive talking heads from single images

**Pros:**
- 3D head motion synthesis
- Emotional realism
- Works from still images

**Cons:**
- Heavy GPU requirements (A100 recommended)
- Slower processing
- Complex setup

### Hallo2 (Cutting Edge)

**Use Case:** Long-duration, high-resolution content

**Pros:**
- ICLR 2025 accepted
- Long video support
- High resolution

**Cons:**
- Very heavy GPU (A100 tested)
- Large model downloads
- Newer, less tested

### LatentSync (ByteDance)

**Use Case:** Efficient high-quality lip-sync

**Pros:**
- Only 6.5GB VRAM required
- High-resolution output
- From TikTok's parent company

**Cons:**
- Newer model
- Less community support

---

## Architecture Overview

```
providers/video/
├── __init__.py           # Provider factory
├── base_lipsync.py       # Base class for lip-sync providers
├── musetalk_provider.py  # MuseTalk integration (Phase 1)
├── did_provider.py       # D-ID API integration (Phase 2)
├── wav2lip_provider.py   # Wav2Lip integration (Phase 4)
└── sadtalker_provider.py # SadTalker integration (Phase 4)

core/video/
├── whisper_sync.py       # Whisper timestamp utility (Phase 3)
└── lipsync_pipeline.py   # Orchestration layer

gui/video/
├── lipsync_widget.py     # Main lip-sync generation UI
└── timestamp_editor.py   # Manual timestamp adjustment
```

### Provider Factory Pattern

```python
# providers/video/__init__.py
from enum import Enum

class LipSyncBackend(Enum):
    MUSETALK = "musetalk"
    DID = "d-id"
    WAV2LIP = "wav2lip"
    SADTALKER = "sadtalker"

def get_lipsync_provider(backend: LipSyncBackend, **kwargs):
    if backend == LipSyncBackend.MUSETALK:
        from .musetalk_provider import MuseTalkProvider
        return MuseTalkProvider(**kwargs)
    elif backend == LipSyncBackend.DID:
        from .did_provider import DIDProvider
        return DIDProvider(**kwargs)
    # ... etc
```

---

## GPU Requirements Summary

| Provider | Min VRAM | Recommended | CPU Fallback? |
|----------|----------|-------------|---------------|
| MuseTalk | 4GB | RTX 3060 12GB | Slow |
| D-ID API | N/A | N/A (cloud) | N/A |
| Wav2Lip | 2GB | RTX 3060 | Yes (fast!) |
| SadTalker | 8GB | A100 | No |
| Hallo2 | 12GB | A100 | No |
| LatentSync | 6.5GB | RTX 4070+ | No |

---

## Cost Analysis

### Open-Source (Local)
- **MuseTalk:** Free, MIT license
- **Wav2Lip:** Free for research, commercial needs Sync Labs API
- **SadTalker:** Free, Apache 2.0 license

### Commercial APIs

| Service | Monthly Cost | Videos/Month | Per Video |
|---------|--------------|--------------|-----------|
| D-ID Launch | $50 | ~100 (30s) | ~$0.50 |
| HeyGen Pro | $99 | 100 credits | ~$1.00 |
| Synthesia Creator | $67 | 360 min/year | ~$2.23/min |

### Recommended Strategy

1. **Development/Testing:** D-ID Free tier (10 credits)
2. **Light Production:** D-ID Launch ($50/mo)
3. **Heavy Production:** MuseTalk (local, free)
4. **Hybrid:** D-ID for demos + MuseTalk for bulk

---

## References

### Official Repositories
- [MuseTalk](https://github.com/TMElyralab/MuseTalk) - MIT License, v1.5 March 2025
- [Wav2Lip](https://github.com/Rudrabha/Wav2Lip) - Research license
- [SadTalker](https://github.com/OpenTalker/SadTalker) - Apache 2.0
- [Hallo2](https://github.com/fudan-generative-vision/hallo2) - ICLR 2025
- [AniPortrait](https://github.com/Zejun-Yang/AniPortrait) - 2024

### API Documentation
- [D-ID API Docs](https://docs.d-id.com/reference/get-started)
- [HeyGen API Docs](https://docs.heygen.com/)
- [Synthesia API Docs](https://docs.synthesia.io/reference/introduction)

### Whisper Tools
- [whisper-timestamped](https://github.com/linto-ai/whisper-timestamped) - Recommended
- [WhisperX](https://pypi.org/project/whisperx/) - Forced alignment
- [stable-ts](https://pypi.org/project/stable-ts/) - Stabilized timestamps

---

## Next Steps

1. **Immediate:** Begin Phase 1 (MuseTalk integration)
   - Set up conda environment with dependencies
   - Download models
   - Test basic inference

2. **Short-term:** Complete Phase 1 + 2
   - Full MuseTalk provider implementation
   - D-ID API integration as backup
   - GUI widgets

3. **Medium-term:** Phase 3
   - Whisper integration for lyric sync
   - Timestamp editor

4. **Long-term:** Phase 4
   - Additional providers based on user feedback
   - Quality presets (fast/balanced/quality)
