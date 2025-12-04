# OpenAI API Upgrade and Sora 2 Integration Plan

**Last Updated:** 2025-12-04 (implementation in progress - Phase 1, 2, 4 complete)

**Status:** Core implementation complete. Phase 1 (gpt-image-1), Phase 2 (SoraClient), and Phase 4 (Templates) are done. GUI integration (Phase 3), CLI (Phase 5), and Documentation (Phase 6) pending.

---

## Goals
- Update ImageAI to align with the latest OpenAI API patterns (Python SDK v1)
- Expand OpenAI image capabilities beyond DALL-E 3 to include `gpt-image-1`
- Integrate OpenAI's Sora 2 video generation, mirroring our VeoClient approach

---

## Current State Analysis

### Existing Infrastructure
- **OpenAI Provider**: `providers/openai.py` - supports DALL-E 2/3 image generation
- **VeoClient**: `core/video/veo_client.py` (972 lines) - comprehensive Google Veo integration with:
  - Async generation with polling
  - Model constraints validation
  - Text-to-video and image-to-video support
  - Reference images for style consistency
  - Cost estimation
  - Batch generation with concurrency control
- **Video Project Tab**: `gui/video/video_project_tab.py` - currently Veo-only for video generation
- **Templates**: `templates/video/shot_prompt.j2` - cinematic prompt templates

### API Research Findings (December 2025)

**Sora 2 API** (from [OpenAI Platform](https://platform.openai.com/docs/api-reference/videos)):
- **Endpoints**:
  - `POST /v1/videos` - Create video generation
  - `GET /v1/videos/{video_id}` - Retrieve status/metadata
  - `GET /v1/videos/{video_id}/content` - Download MP4 file
  - `DELETE /v1/videos/{video_id}` - Delete video
  - `POST /v1/videos/{video_id}/remix` - Modify existing videos

- **Models**:
  - `sora-2` - Flagship model, up to 90 seconds, 4K capable
  - `sora-2-pro` - Most advanced, highest quality

- **Parameters**:
  - `model`: "sora-2" or "sora-2-pro"
  - `prompt`: Text description
  - `size`: "1280x720" (720p landscape), "720x1280" (720p portrait), "1792x1024" (1080p landscape), "1024x1792" (1080p portrait)
  - `seconds`: "4", "8", or "12"
  - `input_reference`: Optional image for image-to-video (multipart/form-data)

- **Pricing** (per second):
  - Sora 2 @ 720p: $0.10/second
  - Sora 2 Pro @ 720p: $0.30/second
  - Sora 2 Pro @ 1080p+: $0.50/second

---

## Phase 1: OpenAI Image Generation Updates

### 1.1 Add gpt-image-1 Support

**File**: `providers/openai.py`

**Tasks**:
- [ ] Add `gpt-image-1` to `get_models()` return dict
- [ ] Add `gpt-image-1` to `get_models_with_details()` with description
- [ ] Update `generate()` method to handle model-specific parameters:
  - For `gpt-image-1`: Support `background` parameter ("transparent", "white", "black")
  - For `gpt-image-1`: Do NOT pass `style` or `quality` parameters
- [ ] Add size mappings for `gpt-image-1` (same as DALL-E 3: 1024x1024, 1792x1024, 1024x1792)

**Code Changes**:

```python
# In get_models()
def get_models(self) -> Dict[str, str]:
    return {
        "gpt-image-1": "GPT Image 1",
        "dall-e-3": "DALL-E 3",
        "dall-e-2": "DALL-E 2",
    }

# In get_models_with_details()
def get_models_with_details(self) -> Dict[str, Dict[str, str]]:
    return {
        "gpt-image-1": {
            "name": "GPT Image 1",
            "description": "High quality, supports transparency"
        },
        "dall-e-3": {
            "name": "DALL-E 3",
            "description": "Most advanced, highest quality images"
        },
        "dall-e-2": {
            "name": "DALL-E 2",
            "description": "Previous generation, lower cost"
        },
    }

# In generate() - model-specific parameter handling
if model == "gpt-image-1":
    gen_params = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "n": num_images,
        "response_format": response_format,
    }
    background = kwargs.get('background')
    if background in {"transparent", "white", "black"}:
        gen_params["background"] = background
    # Do NOT add style or quality for gpt-image-1
elif model == "dall-e-3":
    # Existing DALL-E 3 logic with style/quality
```

### 1.2 GUI Updates for Background Option

**File**: `gui/generate_tab.py` or relevant settings widget

**Tasks**:
- [ ] Add "Background" dropdown when `gpt-image-1` is selected
- [ ] Options: "Default", "Transparent", "White", "Black"
- [ ] Hide dropdown for other models

---

## Phase 2: Sora 2 Client Implementation

### 2.1 Create SoraClient Module

**File**: `core/video/sora_client.py` (new file)

**Architecture** (mirroring VeoClient):

```python
"""
OpenAI Sora 2 API client for AI video generation.

This module handles video generation using OpenAI's Sora models
with support for text-to-video and image-to-video generation.
"""

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import requests

# Check if openai is available
try:
    import importlib.util
    OPENAI_AVAILABLE = importlib.util.find_spec("openai") is not None
except ImportError:
    OPENAI_AVAILABLE = False

OpenAIClient = None


class SoraModel(Enum):
    """Available Sora models"""
    SORA_2 = "sora-2"
    SORA_2_PRO = "sora-2-pro"


@dataclass
class SoraGenerationConfig:
    """Configuration for Sora video generation"""
    model: SoraModel = SoraModel.SORA_2
    prompt: str = ""
    aspect_ratio: str = "16:9"  # 16:9, 9:16
    resolution: str = "720p"  # 720p, 1080p (1080p only for pro)
    duration: int = 8  # 4, 8, or 12 seconds
    image: Optional[Path] = None  # Input reference for image-to-video
    seed: Optional[int] = None  # May not be supported

    def __post_init__(self):
        """Validate configuration after initialization"""
        # Validate duration
        if self.duration not in [4, 8, 12]:
            raise ValueError(
                f"Sora duration must be 4, 8, or 12 seconds, got {self.duration}"
            )

        # Validate resolution for model
        if self.resolution == "1080p" and self.model == SoraModel.SORA_2:
            raise ValueError(
                "1080p resolution requires Sora 2 Pro model. "
                "Use SoraModel.SORA_2_PRO or reduce to 720p."
            )

        # Validate aspect ratio
        if self.aspect_ratio not in ["16:9", "9:16"]:
            raise ValueError(
                f"Sora aspect ratio must be 16:9 or 9:16, got {self.aspect_ratio}"
            )

    def get_size_string(self) -> str:
        """Convert aspect_ratio and resolution to size string for API"""
        size_map = {
            ("16:9", "720p"): "1280x720",
            ("9:16", "720p"): "720x1280",
            ("16:9", "1080p"): "1792x1024",
            ("9:16", "1080p"): "1024x1792",
        }
        return size_map.get((self.aspect_ratio, self.resolution), "1280x720")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls"""
        return {
            "prompt": self.prompt,
            "size": self.get_size_string(),
            "seconds": str(self.duration),
        }


@dataclass
class SoraGenerationResult:
    """Result of a Sora generation operation"""
    success: bool = False
    video_url: Optional[str] = None
    video_path: Optional[Path] = None
    video_id: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None
    generation_time: float = 0.0

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class SoraClient:
    """Client for OpenAI Sora video generation API"""

    # Model constraints
    MODEL_CONSTRAINTS = {
        SoraModel.SORA_2: {
            "max_duration": 12,
            "durations": [4, 8, 12],
            "resolutions": ["720p"],
            "aspect_ratios": ["16:9", "9:16"],
            "supports_image_input": True,
            "generation_time": (60, 120),  # 1-2 minutes typical
            "cost_per_second": {
                "720p": 0.10,
            }
        },
        SoraModel.SORA_2_PRO: {
            "max_duration": 12,
            "durations": [4, 8, 12],
            "resolutions": ["720p", "1080p"],
            "aspect_ratios": ["16:9", "9:16"],
            "supports_image_input": True,
            "generation_time": (90, 180),  # 1.5-3 minutes typical
            "cost_per_second": {
                "720p": 0.30,
                "1080p": 0.50,
            }
        }
    }

    def __init__(self, api_key: str):
        """
        Initialize Sora client.

        Args:
            api_key: OpenAI API key
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            )

        global OpenAIClient
        if OpenAIClient is None:
            from openai import OpenAI as OpenAIClient

        self.api_key = api_key
        self.client = OpenAIClient(api_key=api_key)
        self.logger = logging.getLogger(__name__)

    def validate_config(self, config: SoraGenerationConfig) -> Tuple[bool, Optional[str]]:
        """
        Validate generation configuration against model constraints.

        Args:
            config: Generation configuration

        Returns:
            Tuple of (is_valid, error_message)
        """
        constraints = self.MODEL_CONSTRAINTS.get(config.model)
        if not constraints:
            return False, f"Unknown model: {config.model.value}"

        # Check duration
        if config.duration not in constraints["durations"]:
            return False, f"Duration {config.duration}s not supported. Use: {constraints['durations']}"

        # Check resolution
        if config.resolution not in constraints["resolutions"]:
            return False, f"Resolution {config.resolution} not supported for {config.model.value}. Use: {constraints['resolutions']}"

        # Check aspect ratio
        if config.aspect_ratio not in constraints["aspect_ratios"]:
            return False, f"Aspect ratio {config.aspect_ratio} not supported. Use: {constraints['aspect_ratios']}"

        return True, None

    async def generate_video_async(self, config: SoraGenerationConfig) -> SoraGenerationResult:
        """
        Generate video asynchronously using Sora API.

        Args:
            config: Generation configuration

        Returns:
            Generation result
        """
        result = SoraGenerationResult()

        # Validate configuration
        is_valid, error = self.validate_config(config)
        if not is_valid:
            result.success = False
            result.error = error
            return result

        try:
            start_time = time.time()

            # Build request parameters
            create_params = {
                "model": config.model.value,
                "prompt": config.prompt,
                "size": config.get_size_string(),
                "seconds": str(config.duration),
            }

            self.logger.info(f"Starting Sora generation with {config.model.value}")
            self.logger.info(f"Config: {config.aspect_ratio}, {config.resolution}, {config.duration}s")
            self.logger.info(f"Size string: {config.get_size_string()}")
            self.logger.info(f"Prompt: {config.prompt[:100]}...")

            # Create video generation request
            # Handle image-to-video vs text-to-video
            if config.image and config.image.exists():
                self.logger.info(f"Using input reference image: {config.image}")
                with open(config.image, 'rb') as f:
                    # Use multipart/form-data for image upload
                    response = self.client.videos.create(
                        **create_params,
                        input_reference=f
                    )
            else:
                response = self.client.videos.create(**create_params)

            # Store video ID for polling
            video_id = response.id
            result.video_id = video_id
            result.metadata["model"] = config.model.value
            result.metadata["prompt"] = config.prompt
            result.metadata["started_at"] = datetime.now().isoformat()

            self.logger.info(f"Video creation initiated, ID: {video_id}")

            # Poll for completion
            constraints = self.MODEL_CONSTRAINTS[config.model]
            max_wait = 480  # 8 minutes max

            video_result = await self._poll_for_completion(video_id, max_wait)

            if video_result:
                result.video_url = video_result.get("url")
                result.success = True

                # Download video to local storage
                if result.video_url:
                    result.video_path = await self._download_video(video_id)

                result.metadata["completed_at"] = datetime.now().isoformat()
            else:
                result.success = False
                result.error = "Generation timed out or failed"

            result.generation_time = time.time() - start_time
            self.logger.info(f"Generation completed in {result.generation_time:.1f} seconds")

        except Exception as e:
            self.logger.error(f"Sora generation failed: {e}")
            result.success = False
            result.error = str(e)

        return result

    def generate_video(self, config: SoraGenerationConfig) -> SoraGenerationResult:
        """
        Generate video synchronously (blocking).

        Args:
            config: Generation configuration

        Returns:
            Generation result
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.generate_video_async(config))
        finally:
            loop.close()

    async def _poll_for_completion(self, video_id: str, max_wait: int) -> Optional[Dict[str, Any]]:
        """
        Poll for video generation completion.

        Args:
            video_id: Video generation ID
            max_wait: Maximum wait time in seconds

        Returns:
            Video info dict if successful, None otherwise
        """
        start_time = time.time()
        poll_interval = 10  # 10 second intervals as recommended
        poll_count = 0

        self.logger.info(f"Polling for completion (max wait: {max_wait}s)")

        while time.time() - start_time < max_wait:
            try:
                elapsed = time.time() - start_time
                poll_count += 1

                if poll_count <= 5 or poll_count % 4 == 0:
                    self.logger.info(f"Poll #{poll_count}: Checking status... ({elapsed:.0f}s elapsed)")

                # Retrieve video status
                status_response = self.client.videos.retrieve(video_id)

                status = status_response.status
                self.logger.debug(f"Status: {status}")

                if status == "completed":
                    self.logger.info(f"Video completed after {elapsed:.1f}s ({poll_count} polls)")
                    return {
                        "url": getattr(status_response, "url", None),
                        "status": status,
                    }
                elif status == "failed":
                    error = getattr(status_response, "error", "Unknown error")
                    self.logger.error(f"Video generation failed: {error}")
                    return None
                elif status in ["queued", "in_progress", "processing"]:
                    # Still processing, continue polling
                    await asyncio.sleep(poll_interval)
                else:
                    self.logger.warning(f"Unknown status: {status}")
                    await asyncio.sleep(poll_interval)

            except Exception as e:
                self.logger.error(f"Error polling for completion: {e}")
                return None

        self.logger.warning(f"Generation timed out after {max_wait}s")
        return None

    async def _download_video(self, video_id: str) -> Optional[Path]:
        """
        Download video content to local storage.

        Args:
            video_id: Video ID

        Returns:
            Local path to downloaded video
        """
        try:
            # Create cache directory
            cache_dir = Path.home() / ".imageai" / "cache" / "sora_videos"
            cache_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sora_{timestamp}_{video_id[:8]}.mp4"
            video_path = cache_dir / filename

            self.logger.info(f"Downloading video {video_id}...")

            # Download video content using the API
            content_response = self.client.videos.retrieve_content(video_id)

            # Write to file
            with open(video_path, 'wb') as f:
                f.write(content_response.content)

            file_size = video_path.stat().st_size
            self.logger.info(f"Video downloaded to {video_path} ({file_size / (1024*1024):.2f} MB)")

            return video_path

        except Exception as e:
            self.logger.error(f"Failed to download video: {e}")
            return None

    def estimate_cost(self, config: SoraGenerationConfig) -> float:
        """
        Estimate generation cost in USD.

        Args:
            config: Generation configuration

        Returns:
            Estimated cost
        """
        constraints = self.MODEL_CONSTRAINTS.get(config.model, {})
        cost_map = constraints.get("cost_per_second", {})
        cost_per_second = cost_map.get(config.resolution, 0.10)
        return config.duration * cost_per_second

    def get_model_info(self, model: SoraModel) -> Dict[str, Any]:
        """Get information about a Sora model"""
        constraints = self.MODEL_CONSTRAINTS.get(model, {})
        return {
            "name": model.value,
            "max_duration": constraints.get("max_duration", 12),
            "durations": constraints.get("durations", [4, 8, 12]),
            "resolutions": constraints.get("resolutions", []),
            "aspect_ratios": constraints.get("aspect_ratios", []),
            "supports_image_input": constraints.get("supports_image_input", False),
            "generation_time": constraints.get("generation_time", (60, 180)),
        }

    def generate_batch(
        self,
        configs: List[SoraGenerationConfig],
        max_concurrent: int = 2
    ) -> List[SoraGenerationResult]:
        """
        Generate multiple videos in batch with concurrency control.

        Args:
            configs: List of generation configurations
            max_concurrent: Maximum concurrent generations (default 2 for rate limits)

        Returns:
            List of generation results
        """
        results = []

        for i in range(0, len(configs), max_concurrent):
            batch = configs[i:i + max_concurrent]

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                tasks = [self.generate_video_async(config) for config in batch]
                batch_results = loop.run_until_complete(asyncio.gather(*tasks))
                results.extend(batch_results)
            finally:
                loop.close()

        return results
```

### 2.2 Update Video Module Exports

**File**: `core/video/__init__.py`

**Tasks**:
- [ ] Export SoraClient, SoraModel, SoraGenerationConfig, SoraGenerationResult

---

## Phase 3: GUI Integration

### 3.1 Video Provider Selection

**Files**:
- `gui/video/video_project_tab.py`
- `gui/video/workspace_widget.py` (if provider selection exists there)

**Tasks**:
- [ ] Add video provider dropdown: "Veo 3 (Google)" | "Sora 2 (OpenAI)"
- [ ] When Sora 2 selected:
  - Load SoraClient instead of VeoClient
  - Show Sora-specific model options (Sora 2 vs Sora 2 Pro)
  - Adjust duration options (4, 8, 12 seconds)
  - Adjust resolution options based on model
- [ ] Use existing OpenAI API key from settings (same key for image + video)

**Integration Pattern** (from `video_project_tab.py:727`):

```python
# Current Veo integration:
from core.video.veo_client import VeoClient, VeoGenerationConfig, VeoModel

# Add Sora integration:
from core.video.sora_client import SoraClient, SoraGenerationConfig, SoraModel

# In video generation worker:
video_provider = self.kwargs.get('video_provider', 'veo')

if video_provider == 'sora':
    openai_api_key = config.get_api_key('openai')
    if not openai_api_key:
        self.generation_complete.emit(False, "OpenAI API key required for Sora")
        return

    sora_client = SoraClient(api_key=openai_api_key)

    sora_config = SoraGenerationConfig(
        model=SoraModel.SORA_2_PRO,  # or SORA_2 based on selection
        prompt=scene_prompt,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        duration=duration,
        image=start_frame_path if use_image_to_video else None
    )

    result = sora_client.generate_video(sora_config)
else:
    # Existing Veo logic
    veo_client = VeoClient(...)
```

### 3.2 Cost Estimation Display

**Tasks**:
- [ ] Show estimated cost before generation (use `estimate_cost()`)
- [ ] Display cost comparison between Sora 2 vs Sora 2 Pro
- [ ] Show total project cost estimate for all scenes

---

## Phase 4: Prompt Templates

### 4.1 Sora-Optimized Templates

**File**: `templates/video/sora_shot_prompt.j2` (new file)

**Content**:
```jinja2
{% raw %}
{# Template for generating Sora-optimized cinematic shot descriptions #}
{# Sora excels at physics, motion, and realistic transitions #}

{{ shot_type|default('medium shot') }} of {{ subject }}

{# Core action - Sora is strong with continuous motion #}
{% if action %}
Motion: {{ action }}
{% endif %}

{# Camera work - Sora handles complex camera movements well #}
Camera: {{ camera_angle|default('eye level') }}
{% if camera_movement %}Movement: {{ camera_movement }}{% endif %}
Lens: {{ lens|default('50mm') }}, {{ dof|default('cinematic depth of field') }}

{# Environment - Sora excels at atmospheric details #}
Setting: {{ location }}
Time: {{ time_of_day|default('golden hour') }}
{% if weather %}Weather: {{ weather }}{% endif %}
Atmosphere: {{ atmosphere|default('cinematic lighting with natural shadows') }}

{# Style guidance for Sora #}
Style: {{ visual_style|default('photorealistic, cinematic') }}
Color: {{ color_grading|default('natural with subtle color grading') }}

{# Physics hints - Sora's strength #}
{% if physics_elements %}
Physics: {{ physics_elements }}
{% endif %}

{% if continuity_notes %}
Continuity: {{ continuity_notes }}
{% endif %}
{% endraw %}
```

---

## Phase 5: CLI Integration

### 5.1 Video Command Extension

**File**: `cli/commands.py` or create `cli/video_commands.py`

**Tasks**:
- [ ] Add `--video-provider` flag: "veo" (default) | "sora"
- [ ] Add `--sora-model` flag: "sora-2" | "sora-2-pro"
- [ ] Example: `python main.py video --video-provider sora --sora-model sora-2-pro -p "A drone shot..." -o video.mp4`

---

## Phase 6: Configuration & Auth

### 6.1 API Key Management

**Already supported**: OpenAI API key is already managed via:
- `OPENAI_API_KEY` environment variable
- Config file in user config directory
- CLI `--api-key` flag

**Tasks**:
- [ ] Verify same key works for both images and videos (it should)
- [ ] Add documentation note about API tier requirements for Sora access

---

## Implementation Task Checklist

**Last Updated:** 2025-12-04 (implementation progress)

### Phase 1: Image Generation (Priority: High) - ✅ COMPLETED
- [x] Add `gpt-image-1` to `providers/openai.py:get_models()` - **DONE** (line 223)
- [x] Add `gpt-image-1` to `providers/openai.py:get_models_with_details()` - **DONE** (line 238)
- [x] Update `providers/openai.py:generate()` for model-specific params - **DONE** (lines 126-189)
- [x] Add background option handling for `gpt-image-1` - **DONE** (lines 135-138)
- [ ] Test transparent PNG generation with `gpt-image-1` - **PENDING** (requires testing)

**Improvements made:**
- Model-specific parameter handling to avoid sending unsupported style/quality params to gpt-image-1
- Background parameter support for transparent, white, or black backgrounds
- Enhanced logging to show model-specific parameters sent to API

### Phase 2: Sora Client (Priority: High) - ✅ COMPLETED
- [x] Create `core/video/sora_client.py` with full implementation - **DONE** (630 lines)
- [x] Implement `SoraModel` enum - **DONE** (line 35)
- [x] Implement `SoraGenerationConfig` dataclass - **DONE** (line 55)
- [x] Implement `SoraGenerationResult` dataclass - **DONE** (line 103)
- [x] Implement `SoraClient` class with:
  - [x] `__init__()` with API key setup - **DONE** (line 168)
  - [x] `validate_config()` for constraint checking - **DONE** (line 246)
  - [x] `generate_video_async()` with polling - **DONE** (line 269)
  - [x] `generate_video()` sync wrapper - **DONE** (line 541)
  - [x] `_poll_for_completion()` with status handling - **DONE** (line 427)
  - [x] `_download_video()` for local caching - **DONE** (line 498)
  - [x] `estimate_cost()` for pricing - **DONE** (line 556)
  - [x] `get_model_info()` for UI display - **DONE** (line 568)
  - [x] `generate_batch()` for multi-scene projects - **DONE** (line 583)
- [x] Update `core/video/__init__.py` exports - **DONE** (lines 13-47)

**Improvements over plan:**
- Added `SoraErrorType` enum for better error categorization
- Retry logic with exponential backoff and jitter (MAX_RETRIES=3)
- Progress callback support for GUI integration
- Cancellation support via `cancel()` and `reset_cancellation()`
- HTTP API fallback if SDK doesn't have `.videos` namespace
- `delete_video()` method for cleanup

### Phase 3: GUI Integration (Priority: Medium) - ⏳ PENDING
- [ ] Add video provider selector to video project tab
- [ ] Wire SoraClient into video generation worker
- [ ] Show Sora-specific options when selected
- [ ] Add cost estimation display
- [ ] Add background dropdown for gpt-image-1 in image generation
- [ ] Test with Sora 2 and Sora 2 Pro models

**Integration Notes:**
See `gui/video/video_project_tab.py:30` for VideoGenerationThread pattern.
Example integration in `_generate_video_clip()` method:

```python
# Check video provider selection
video_provider = self.kwargs.get('video_provider', 'veo')
if video_provider == 'sora':
    from core.video.sora_client import SoraClient, SoraGenerationConfig, SoraModel
    openai_key = config.get_api_key('openai')
    sora_client = SoraClient(
        api_key=openai_key,
        progress_callback=lambda p, m: self.progress_update.emit(p, m)
    )
    sora_config = SoraGenerationConfig(
        model=SoraModel.SORA_2_PRO,
        prompt=scene_prompt,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        duration=duration,
    )
    result = sora_client.generate_video(sora_config)
```

### Phase 4: Templates (Priority: Low) - ✅ COMPLETED
- [x] Create `templates/video/sora_shot_prompt.j2` - **DONE** (55 lines)
- [ ] Test prompt template with Sora generation - **PENDING** (requires testing)

**Template features:**
- Optimized for Sora's motion and physics capabilities
- Camera movement presets (tracking, drone, steadicam, etc.)
- Physics hints for realistic motion
- Particle and atmospheric effects support
- Motion quality descriptors

### Phase 5: CLI (Priority: Low) - ⏳ PENDING
- [ ] Add `--video-provider` flag
- [ ] Add `--sora-model` flag
- [ ] Test CLI video generation with Sora

### Phase 6: Documentation (Priority: Low) - ⏳ PENDING
- [ ] Update README.md with Sora usage examples
- [ ] Add CHANGELOG entry
- [ ] Document API tier requirements

---

## Testing Plan

### Image Generation Tests
```bash
# Test gpt-image-1 basic generation
python main.py -p "Logo test" -o test.png --provider openai --model gpt-image-1

# Test transparent background
python main.py -p "Phoenix logo, flat vector" -o logo.png --provider openai --model gpt-image-1 --background transparent
```

### Video Generation Tests
```bash
# Test Sora 2 text-to-video (once implemented)
python main.py video --video-provider sora -p "Drone shot over mountains at sunset" -o test.mp4 --duration 8

# Test Sora 2 Pro with higher resolution
python main.py video --video-provider sora --sora-model sora-2-pro --resolution 1080p -p "..." -o test.mp4
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Sora API access may be limited/invite-only | Implement graceful error handling; check API access before showing Sora option |
| API rate limits (1-2 RPM for Pro at Tier 1) | Implement queue-based generation; default to 2 concurrent max |
| Higher costs than Veo | Show clear cost estimates before generation; warn on expensive configs |
| SDK surface may change | Use try/except around SDK calls; log detailed errors for debugging |
| Video download format variations | Support both direct URL and content endpoint patterns |

---

## References

- [OpenAI Video Generation API](https://platform.openai.com/docs/api-reference/videos)
- [Sora 2 Model](https://platform.openai.com/docs/models/sora-2)
- [Sora 2 Pro Model](https://platform.openai.com/docs/models/sora-2-pro)
- Internal parity with `core/video/veo_client.py` (972 lines)
- [OpenAI Sora Announcement](https://openai.com/index/sora-2/)

---

## Appendix: API Quick Reference

### Sora Video Creation
```python
from openai import OpenAI
client = OpenAI()

# Text-to-video
response = client.videos.create(
    model="sora-2-pro",
    prompt="A cinematic drone shot over terraced rice fields at golden hour",
    size="1792x1024",  # 1080p landscape
    seconds="8"
)

video_id = response.id

# Poll for completion
while True:
    status = client.videos.retrieve(video_id)
    if status.status == "completed":
        break
    time.sleep(10)

# Download video
content = client.videos.retrieve_content(video_id)
with open("output.mp4", "wb") as f:
    f.write(content.content)
```

### GPT Image 1 (Transparent Background)
```python
from openai import OpenAI
client = OpenAI()

response = client.images.generate(
    model="gpt-image-1",
    prompt="Minimal phoenix logo, flat, vector, orange/teal",
    size="1024x1024",
    background="transparent",
    response_format="b64_json",
)
```
