# Veo 3.1 Integration Plan

*Created: 2025-12-02*
*Last Updated: 2025-12-02 14:45*

## Executive Summary

Google Veo 3.1 was released October 14, 2025 as an incremental improvement over Veo 3.0. **Good news: ImageAI's existing `veo_client.py` already supports most Veo 3.1 features.** This plan focuses on the updates needed to fully support Veo 3.1 and its Fast variant.

---

## Model Evolution

### Model Lineage

| Model | Model ID | Key Features |
|-------|----------|--------------|
| Veo 2.0 | `veo-2.0-generate-001` | 720p, 8s max, ref images (3), no audio |
| Veo 3.0 | `veo-3.0-generate-001` | 1080p, 8s fixed, audio, **NO ref images** |
| **Veo 3.1** | `veo-3.1-generate-preview` | 1080p, 8s, audio, ref images (3), scene extension, frame interpolation |
| **Veo 3.1 Fast** | `veo-3.1-fast-generate-preview` | 720p, 4-8s, audio, ref images (3), 11-60s generation |

### Key Differentiators

| Feature | Veo 2.0 | Veo 3.0 | Veo 3.1 |
|---------|---------|---------|---------|
| Max Resolution | 720p | 1080p | 1080p |
| Aspect Ratios | 16:9 only | 16:9, 9:16, 1:1 | 16:9, 9:16, 1:1 |
| Native Audio | No | Yes | Yes (enhanced) |
| Reference Images | Yes (3 max) | **No** | Yes (3 max) |
| Scene Extension | No | Limited | Yes |
| Frame Interpolation | No | No | Yes |
| Generation Time | 1-3 min | 1-6 min | 1-6 min (11-60s for Fast) |
| Duration | 4-8 sec | 8 sec only | 8 sec (4-8 for Fast) |

---

## Key Features

### 1. Reference Images (Restored in 3.1)

**Purpose:** Guide video generation with up to 3 reference images for:
- Character consistency across scenes
- Product appearance preservation
- Environmental look and feel

**Important:** Veo 3.1 does NOT support style images - only asset/character references.

**Our Implementation:** Already handles this in `veo_client.py:385-492` including aspect ratio mismatch fix with transparent canvas.

### 2. Scene Extension (New)

**Purpose:** Extend previous videos to create 60+ second sequences.

**How it works:**
- Uses the final 1 second of previous clip as seed
- Chain multiple extensions for longer content
- Extended segments run at 720p (may drop from 1080p)

### 3. Frame-to-Frame Interpolation (New)

**Purpose:** Specify both start and end frames, model generates smooth transition.

**Our Implementation:** Already supported via `last_frame` parameter (`veo_client.py:367-383, 510-513`).

### 4. Audio Generation

**Audio Types:**
- **Dialogue**: Use quotes in prompt (e.g., `"A woman says 'Hello!'"`
- **Sound Effects (SFX)**: Explicit descriptions (e.g., `"sound of thunder"`)
- **Ambient Noise**: Environmental soundscape (e.g., `"busy city traffic"`)

**Control:** `generateAudio: true/false` parameter

---

## Pricing (October 2025)

### API Pricing (Pay-Per-Use)

| Model | With Audio | Video Only |
|-------|------------|------------|
| Veo 3.1 Standard | $0.40/sec | $0.20/sec |
| Veo 3.1 Fast | $0.15/sec | $0.10/sec |
| Veo 3.0 | $0.40/sec | $0.20/sec |
| Veo 2.0 | $0.35/sec | $0.35/sec |

### Cost Examples

| Scenario | Cost |
|----------|------|
| 8-sec Veo 3.1 clip with audio | $3.20 |
| 8-sec Veo 3.1 Fast with audio | $1.20 |
| 60-sec extended sequence (8 clips, standard) | $25.60 |
| 60-sec extended sequence (8 clips, fast) | $9.60 |

---

## Current Implementation Status

### ✅ Already Implemented (No Changes Needed)

| Feature | Location | Status |
|---------|----------|--------|
| Dual authentication (API key + gcloud) | `veo_client.py:182-268` | ✅ Working |
| Veo 3.1 model enum | `veo_client.py:45-51` | ✅ Defined |
| Reference image support (up to 3) | `veo_client.py:385-492` | ✅ Working |
| Aspect ratio canvas fix | `veo_client.py:410-468` | ✅ Working |
| Frame-to-frame interpolation | `veo_client.py:367-383, 510-513` | ✅ Working |
| Video download & caching | `veo_client.py:741-809` | ✅ Working |
| Comprehensive error handling | `veo_client.py:288-322, 783-809` | ✅ Working |
| Region detection | `veo_client.py:270-286` | ✅ Working |

### ⏳ Updates Needed

| Feature | Location | Status |
|---------|----------|--------|
| Add Veo 3.1 Fast model | `veo_client.py` VeoModel enum | ⏳ Pending |
| Update pricing | `veo_client.py:941-959` | ⏳ Pending |
| Add scene extension method | `veo_client.py` new method | ⏳ Pending |
| Add Veo 3.1 Fast constraints | `veo_client.py:145-180` | ⏳ Pending |

---

## Implementation Plan

### Phase 1: Model Updates ⏳ PENDING

**Goal:** Add Veo 3.1 Fast model support

**Tasks:**

1. Add Veo 3.1 Fast to VeoModel enum (`veo_client.py:45-51`)
   ```python
   VEO_3_1_FAST = "veo-3.1-fast-generate-preview"
   ```

2. Add Veo 3.1 Fast constraints (`veo_client.py:145-180`)
   ```python
   VeoModel.VEO_3_1_FAST: {
       "max_duration": 8,
       "fixed_duration": None,  # Can be 4, 6, or 8
       "resolutions": ["720p"],
       "aspect_ratios": ["16:9", "9:16"],
       "supports_audio": True,
       "supports_reference_images": True,
       "generation_time": (11, 60)  # 11-60 seconds
   }
   ```

3. Update model selection in UI to include Veo 3.1 Fast option

### Phase 2: Pricing Updates ⏳ PENDING

**Goal:** Update cost estimation to reflect current pricing

**Current code (`veo_client.py:941-959`):**
```python
pricing = {
    VeoModel.VEO_3_GENERATE: 0.10,  # Wrong
    VeoModel.VEO_3_FAST: 0.05,      # Wrong
}
```

**Updated code:**
```python
def estimate_cost(self, config: VeoGenerationConfig) -> float:
    """Estimate generation cost in USD based on October 2025 pricing."""
    pricing_with_audio = {
        VeoModel.VEO_3_1_GENERATE: 0.40,
        VeoModel.VEO_3_1_FAST: 0.15,
        VeoModel.VEO_3_GENERATE: 0.40,
        VeoModel.VEO_3_FAST: 0.15,
        VeoModel.VEO_2_GENERATE: 0.35,
    }
    pricing_video_only = {
        VeoModel.VEO_3_1_GENERATE: 0.20,
        VeoModel.VEO_3_1_FAST: 0.10,
        VeoModel.VEO_3_GENERATE: 0.20,
        VeoModel.VEO_3_FAST: 0.10,
        VeoModel.VEO_2_GENERATE: 0.35,
    }

    if config.include_audio:
        cost_per_second = pricing_with_audio.get(config.model, 0.40)
    else:
        cost_per_second = pricing_video_only.get(config.model, 0.20)

    return config.duration * cost_per_second
```

### Phase 3: Scene Extension Feature ⏳ PENDING

**Goal:** Add ability to extend videos for 60+ second sequences

**New method to add:**
```python
async def extend_video_async(
    self,
    previous_video_path: Path,
    prompt: str,
    config: VeoGenerationConfig
) -> VeoGenerationResult:
    """
    Extend a previous video by generating a new clip that continues from it.
    Uses the final 1 second of previous video as seed.

    Args:
        previous_video_path: Path to the video to extend
        prompt: Prompt for the new segment
        config: Generation configuration

    Returns:
        Generation result for extended clip

    Note: Extended segments run at 720p even if original was 1080p.
    """
    # Load previous video bytes
    with open(previous_video_path, 'rb') as f:
        video_bytes = f.read()

    video_dict = {
        'videoBytes': video_bytes,
        'mimeType': 'video/mp4'
    }

    # Generate extension using video parameter
    operation = self.client.models.generate_videos(
        model=config.model.value,
        prompt=prompt,
        config=types.GenerateVideosConfig(
            aspect_ratio=config.aspect_ratio,
            duration_seconds=config.duration
        ),
        video=video_dict  # Previous video for continuity
    )

    # Poll and return result (reuse existing polling logic)
    return await self._poll_operation_async(operation, config)
```

### Phase 4: UI Enhancements ⏳ PENDING

**Goal:** Expose new features in the GUI

**Tasks:**

1. Add Veo 3.1 Fast to model dropdown
2. Add cost estimation display before generation
3. Add "Extend Video" button for scene extension
4. Add audio prompt syntax help tooltip:
   - Dialogue: `"Person says 'Hello!'"`
   - SFX: `"sound of thunder"`
   - Ambient: `"busy city traffic"`

### Phase 5: Testing ⏳ PENDING

**Test Cases:**

1. **Veo 3.1 Fast**
   - Verify 11-60 second generation time
   - Compare quality vs standard
   - Test 4, 6, 8 second durations

2. **Reference Images (up to 3)**
   - Single reference image
   - Three reference images
   - Mismatched aspect ratio (canvas fix)

3. **Frame-to-Frame Interpolation**
   - Provide both start and end frames
   - Verify smooth transition

4. **Scene Extension**
   - Generate first clip
   - Extend with new prompt
   - Verify visual continuity

5. **Audio Generation**
   - Dialogue prompt
   - SFX prompt
   - Ambient prompt

---

## Important Limitations

### Duration Restrictions
- Veo 3.1 Standard: **8 seconds only** (fixed)
- Veo 3.1 Fast: 4, 6, or 8 seconds

### Reference Image Restrictions
- Veo 3.0: **Does NOT support reference images**
- Veo 3.1: Up to 3 asset/character references (NOT style references)

### Regional Restrictions
- Person generation disabled in EU, UK, Switzerland, MENA
- Already validated in our code (`veo_client.py:270-286`)

### URL Expiration
- Video URLs expire after **2 days**
- Our code downloads immediately to local cache ✅

### Extended Segments Resolution
- Native clips: 1080p supported
- Extended clips: **720p only** (may drop detail)

### SynthID Watermarking
- All Veo videos include invisible SynthID watermark
- Cannot be disabled

---

## Files to Modify

| File | Changes |
|------|---------|
| `core/video/veo_client.py` | Add Veo 3.1 Fast enum, update constraints, update pricing, add extend_video_async |
| `gui/video/video_project_tab.py` | Add Veo 3.1 Fast to model dropdown, add extend button |
| `gui/video/veo_controls_widget.py` | Add cost estimation display, audio prompt tooltips |

---

## API Code Examples

### Basic Veo 3.1 Generation

```python
from google import genai
from google.genai import types

client = genai.Client(api_key="YOUR_API_KEY")

operation = client.models.generate_videos(
    model="veo-3.1-generate-preview",
    prompt="A calico kitten playing with yarn. SFX: soft purring.",
    config=types.GenerateVideosConfig(
        aspect_ratio="16:9",
        duration_seconds=8,
    )
)

# Poll for completion
while not operation.done:
    time.sleep(10)
    operation = client.operations.get(operation)

video_url = operation.response.generated_videos[0].video.uri
```

### Scene Extension

```python
# Generate first clip
operation1 = client.models.generate_videos(
    model="veo-3.1-generate-preview",
    prompt="A car driving down a highway at sunset",
    config=types.GenerateVideosConfig(aspect_ratio="16:9", duration_seconds=8)
)

# Wait for completion...
video1 = operation1.response.generated_videos[0].video

# Extend the video
operation2 = client.models.generate_videos(
    model="veo-3.1-generate-preview",
    prompt="The car turns off onto a dirt road",
    config=types.GenerateVideosConfig(aspect_ratio="16:9", duration_seconds=8),
    video={'videoBytes': video1.video_bytes, 'mimeType': 'video/mp4'}
)
```

### Frame-to-Frame Interpolation

```python
with open("start_frame.png", "rb") as f:
    start_bytes = f.read()
with open("end_frame.png", "rb") as f:
    end_bytes = f.read()

operation = client.models.generate_videos(
    model="veo-3.1-generate-preview",
    prompt="Smooth transition with camera pan",
    image={'imageBytes': start_bytes, 'mimeType': 'image/png'},
    config=types.GenerateVideosConfig(
        aspect_ratio="16:9",
        duration_seconds=8,
        last_frame={'imageBytes': end_bytes, 'mimeType': 'image/png'}
    )
)
```

---

## Sources

- [Introducing Veo 3.1 and new creative capabilities in the Gemini API](https://developers.googleblog.com/en/introducing-veo-3-1-and-new-creative-capabilities-in-the-gemini-api/)
- [Veo 3.1 | Generative AI on Vertex AI | Google Cloud Documentation](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/veo/3-1-generate)
- [Veo on Vertex AI video generation API Reference](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation)
- [Generate videos with Veo 3.1 in Gemini API](https://ai.google.dev/gemini-api/docs/video)
- [Veo 3.1 - DeepMind](https://deepmind.google/models/veo/)
- [Veo 3.1 Pricing & Access (2025)](https://skywork.ai/blog/veo-3-1-pricing-access-2025/)
- [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing)
