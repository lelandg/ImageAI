# OpenAI API Upgrade and Sora 2 Integration Plan

*Created: 2025-12-04*
*Last Updated: 2025-12-05 14:30*

## Quick Status

| Phase | Status | Blocker |
|-------|--------|---------|
| Phase 1: API Verification | ✅ 100% | **API IS NOW AVAILABLE** |
| Phase 2: GUI Integration | ⏳ 0% | Ready to start |
| Phase 3: Workflow Integration | ⏸️ 0% | Blocked on Phase 2 |
| Phase 4: API Key Management | ✅ 50% | None |
| Phase 5: Testing | ⏳ 10% | Can begin with API access |

**API Status:** ✅ **LIVE** - OpenAI Sora API is publicly available via `client.videos.create()`

## Overview

This plan documents the integration of OpenAI's Sora 2 video generation API into ImageAI as an alternative/complement to Google Veo 3 for the video project workflow.

## Current Implementation Status

### Completed Work ✅

| Component | Status | Location | Notes |
|-----------|--------|----------|-------|
| SoraClient Core | ✅ Complete | `core/video/sora_client.py` (1374 lines) | Full async client with retry, progress callbacks, cancellation, remix, webhooks |
| Module Exports | ✅ Complete | `core/video/__init__.py` | Lazy import with SORA_AVAILABLE flag |
| Shot Prompt Template | ✅ Complete | `templates/video/sora_shot_prompt.j2` | Jinja2 template optimized for Sora's strengths |
| OpenAI Image Provider | ✅ Complete | `providers/openai.py` | DALL-E/GPT-Image generation (images only) |

### SoraClient Features (Already Implemented)

The `SoraClient` class in `core/video/sora_client.py` includes:

1. **Models Supported**
   - `SoraModel.SORA_2` - Standard model (720p, 4/8/12s)
   - `SoraModel.SORA_2_PRO` - Pro model (720p/1080p, 4/8/12s)

2. **Generation Capabilities**
   - Text-to-video generation
   - Image-to-video generation (with reference image input)
   - Aspect ratios: 16:9, 9:16
   - Resolutions: 720p (standard), 1080p (pro only)
   - Durations: 4, 8, or 12 seconds

3. **Robustness Features**
   - Async generation with polling
   - Retry logic with exponential backoff
   - Progress callbacks for GUI integration
   - Cancellation support
   - Error classification (rate limit, content policy, auth, etc.)
   - HTTP fallback if SDK lacks `.videos` namespace

4. **Cost Estimation**
   - Per-second pricing by model/resolution
   - Sora 2: $0.10/sec @ 720p
   - Sora 2 Pro: $0.30/sec @ 720p, $0.50/sec @ 1080p

5. **Video Remix** ✅ NEW (2025-12-05)
   - `remix_video()` - Refine existing video with new prompt
   - `remix_video_async()` - Async version
   - `remix_batch()` - Create multiple variations from single source
   - Preserves visual style while adjusting mood, palette, staging

6. **Webhook Support** ✅ NEW (2025-12-05)
   - `register_webhook_handler()` - Register callback for events
   - `process_webhook()` - Process incoming webhook payloads
   - `verify_webhook_signature()` - HMAC-SHA256 signature verification
   - `generate_with_webhook()` - Start generation without polling
   - Events: `video.completed`, `video.failed`

---

## Phase 1: API Availability Verification ✅ COMPLETE

**Goal:** Verify Sora 2 API access and correct endpoint structure

**Status:** Phase 1 is **100% complete**. API is live and verified.

### Verified API Methods (2025-12-04)

| Method | SDK Call | Purpose |
|--------|----------|---------|
| Create | `client.videos.create(model, prompt, size, seconds)` | Start generation |
| Retrieve | `client.videos.retrieve(video_id)` | Poll status |
| Download | `client.videos.download_content(video_id, variant="video")` | Get video file |

### Verified Parameters

| Parameter | Type | Values | Notes |
|-----------|------|--------|-------|
| `model` | string | `"sora-2"`, `"sora-2-pro"` | Required |
| `prompt` | string | Max 500 chars | Required |
| `size` | string | `"1280x720"`, `"1920x1080"` | Resolution |
| `seconds` | string | `"4"`, `"8"`, `"12"` | Duration |
| `input_reference` | file | Image file object | For image-to-video |

### Status Values

`queued` → `preprocessing` → `running` → `processing` → `completed` | `failed` | `cancelled`

### Tasks

1. ✅ API is now publicly available via OpenAI Python SDK
2. ✅ Verified endpoint structure matches our implementation
3. ✅ Updated SoraClient with correct `download_content()` method
4. ✅ Added `cancelled` and additional status handling

### API Access

| Platform | Status | Notes |
|----------|--------|-------|
| OpenAI API | ✅ **LIVE** | `pip install openai --upgrade` for `.videos` namespace |
| Azure AI Foundry | ✅ Available | Enterprise option |
| sora.com | Consumer | Web/mobile app only |

---

## Phase 2: GUI Integration

**Goal:** Add Sora provider selection and controls to video project workflow

**Status:** Phase 2 is **0% complete**. Blocked on Phase 1.

### Tasks

1. **Video Provider Selection** (Priority: High)
   - [ ] Add provider dropdown to video generation UI (Veo 3 / Sora 2)
   - [ ] Location: `gui/video/workspace_widget.py` or similar
   - [ ] Save provider preference in project settings

2. **Sora Controls Widget** (Priority: High)
   - [ ] Create `gui/video/sora_controls_widget.py`
   - [ ] Model selector (Sora 2 / Sora 2 Pro)
   - [ ] Resolution selector (720p / 1080p for Pro)
   - [ ] Duration selector (4s / 8s / 12s)
   - [ ] Aspect ratio selector (16:9 / 9:16)
   - [ ] Cost estimation display

3. **Progress Integration** (Priority: Medium)
   - [ ] Connect SoraClient progress callbacks to UI progress bar
   - [ ] Show polling status in status console
   - [ ] Handle cancellation from UI

4. **Error Handling UI** (Priority: Medium)
   - [ ] Display error types appropriately
   - [ ] Rate limit: Show retry countdown
   - [ ] Content policy: Show policy violation message
   - [ ] Auth error: Prompt for API key

### UI Design Notes

```
┌─────────────────────────────────────────────────────────────┐
│ Video Provider: [Veo 3 ▼] [Sora 2 ▼]                       │
├─────────────────────────────────────────────────────────────┤
│ ┌─ Sora Settings ─────────────────────────────────────────┐│
│ │ Model:      [Sora 2 ▼] [Sora 2 Pro ▼]                   ││
│ │ Resolution: [720p ▼] [1080p ▼] (Pro only)               ││
│ │ Duration:   [4s] [8s] [12s]                             ││
│ │ Aspect:     [16:9] [9:16]                               ││
│ │                                                         ││
│ │ Estimated Cost: $0.80 (8 seconds @ $0.10/sec)           ││
│ └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 3: Video Project Workflow Integration

**Goal:** Enable Sora generation within storyboard/scene workflow

**Status:** Phase 3 is **0% complete**. Blocked on Phases 1-2.

### Tasks

1. **Project Model Updates** (Priority: High)
   - [ ] Add `video_provider` field to `VideoProject` model
   - [ ] Add Sora-specific settings to scene config
   - [ ] Location: `core/video/project.py`

2. **Scene Generation Worker** (Priority: High)
   - [ ] Create/update worker to support Sora generation
   - [ ] Use SoraClient for generation
   - [ ] Handle Sora-specific result format

3. **Template Integration** (Priority: Medium)
   - [ ] Use `sora_shot_prompt.j2` for Sora prompt optimization
   - [ ] Different prompt styles for Veo vs Sora

4. **Batch Generation** (Priority: Low)
   - [ ] Use SoraClient's `generate_batch()` for multi-scene generation
   - [ ] Respect concurrency limits (default: 2)

### Workflow Differences: Veo vs Sora

| Feature | Veo 3 | Sora 2 |
|---------|-------|--------|
| Max Duration | 8s | 12s |
| Audio | Built-in | Built-in |
| Resolutions | 720p, 1080p | 720p (std), 1080p (pro) |
| Reference Images | Yes (3 max) | Yes (image-to-video) |
| Generation Time | ~60-120s | ~60-180s |
| Aspect Ratios | 16:9, 9:16, 1:1 | 16:9, 9:16 |

---

## Phase 4: API Key Management

**Goal:** Unified API key handling for OpenAI image and video

**Status:** Phase 4 is **50% complete**. OpenAI key exists for images.

### Current State

- OpenAI API key is already managed for DALL-E/GPT-Image
- Same key should work for Sora (when available)
- Key stored in user config directory

### Tasks

1. ✅ API key storage (already exists for OpenAI images)
2. [ ] Validate key has video API access (may require specific permissions)
3. [ ] Handle case where key works for images but not video
4. [ ] UI indication of video API access status

---

## Phase 5: Testing and Validation

**Goal:** Comprehensive testing of Sora integration

**Status:** Phase 5 is **0% complete**. Blocked on API access.

### Test Scenarios

1. **Unit Tests**
   - [ ] SoraGenerationConfig validation
   - [ ] Cost estimation accuracy
   - [ ] Error classification logic

2. **Integration Tests**
   - [ ] Text-to-video generation
   - [ ] Image-to-video generation
   - [ ] Progress callback flow
   - [ ] Cancellation handling
   - [ ] Retry logic

3. **UI Tests**
   - [ ] Provider switching
   - [ ] Settings persistence
   - [ ] Error display

---

## Technical Notes

### Sora vs Veo Architecture Comparison

```
┌─────────────────────────────────────────────────────────────┐
│                    Video Generation Flow                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐  │
│  │  Prompt     │────▶│  Template   │────▶│  Provider   │  │
│  │  (User)     │     │  Processor  │     │  Router     │  │
│  └─────────────┘     └─────────────┘     └──────┬──────┘  │
│                                                  │         │
│                      ┌───────────────────────────┼──────┐  │
│                      ▼                           ▼      │  │
│             ┌─────────────┐              ┌─────────────┐│  │
│             │  VeoClient  │              │ SoraClient  ││  │
│             │ (veo_client │              │(sora_client ││  │
│             │   .py)      │              │   .py)      ││  │
│             └──────┬──────┘              └──────┬──────┘│  │
│                    ▼                            ▼       │  │
│             ┌─────────────┐              ┌─────────────┐│  │
│             │ Google Veo  │              │ OpenAI Sora ││  │
│             │   API       │              │   API       ││  │
│             └─────────────┘              └─────────────┘│  │
│                                                         │  │
└─────────────────────────────────────────────────────────────┘
```

### SoraClient Key Methods

| Method | Purpose |
|--------|---------|
| `generate_video_async()` | Main async generation method |
| `generate_video()` | Blocking sync wrapper |
| `generate_batch()` | Batch generation with concurrency control |
| `validate_config()` | Pre-generation config validation |
| `estimate_cost()` | Cost estimation in USD |
| `cancel()` | Cancel ongoing generation |

### HTTP Fallback Endpoints (Assumed)

```python
# Create video
POST /v1/videos
{
    "model": "sora-2",
    "prompt": "...",
    "size": "1280x720",
    "seconds": "8"
}

# Check status
GET /v1/videos/{video_id}
{
    "status": "in_progress" | "completed" | "failed",
    "url": "..." (when completed)
}

# Download content
GET /v1/videos/{video_id}/content
```

---

## API Availability Monitoring

### URLs to Check Periodically

| Resource | URL | What to Look For |
|----------|-----|------------------|
| OpenAI API Docs | https://platform.openai.com/docs/api-reference | New `/videos` endpoint |
| OpenAI Changelog | https://platform.openai.com/docs/changelog | Sora API announcement |
| Azure OpenAI | https://learn.microsoft.com/azure/ai-services/openai/whats-new | GA announcement |
| OpenAI Blog | https://openai.com/blog | Sora developer access |
| Sora Dev Portal | https://sora.com/developers | Developer API launch |

### Monitoring Schedule

| Date | Action | Result |
|------|--------|--------|
| 2025-12-04 | Initial research | API not available, preview on Azure only |
| 2025-01-15 | Scheduled check | *Pending* |
| 2025-02-15 | Scheduled check | *Pending* |

### Signs API is Available

1. OpenAI Python SDK gets `.videos` namespace
2. `/v1/videos` endpoint documented
3. Sora mentioned in API pricing page
4. Developer blog post about Sora API

---

## Next Steps

1. **Immediate** (when API available)
   - Verify API endpoint structure
   - Test with real API key
   - Update SoraClient if needed

2. **Short-term**
   - Add provider selection UI
   - Create Sora controls widget
   - Integrate with video project workflow

3. **Medium-term**
   - Comprehensive testing
   - Documentation
   - User guide for Sora vs Veo selection

---

## When API Becomes Available: Quick Start

```bash
# 1. Test if SDK has videos namespace
python3 -c "from openai import OpenAI; print(hasattr(OpenAI(), 'videos'))"

# 2. Quick API test (if available)
python3 << 'EOF'
from core.video import SoraClient, SoraGenerationConfig, SoraModel

# Get API key from config
from core.config import ConfigManager
config = ConfigManager()
api_key = config.get_api_key('openai')

# Test generation
client = SoraClient(api_key)
config = SoraGenerationConfig(
    model=SoraModel.SORA_2,
    prompt="A golden retriever playing in autumn leaves",
    duration=4
)
result = client.generate_video(config)
print(f"Success: {result.success}")
print(f"Path: {result.video_path}")
EOF
```

---

## Resources

- [Sora 2 Research Notes](./Sora2-Research-Notes.md) - Background research
- [Azure AI Foundry Docs](https://learn.microsoft.com/azure/ai-services/)
- [OpenAI Sora](https://sora.com/) - Consumer site
- [VeoClient Implementation](../core/video/veo_client.py) - Reference for pattern
- [OpenAI Platform Status](https://status.openai.com/) - API status

---

## Changelog

| Date | Change |
|------|--------|
| 2025-12-04 | Initial plan created based on existing implementation |
| 2025-12-04 | Added monitoring schedule and quick-start test script |
| 2025-12-04 | **API CONFIRMED LIVE** - Verified against official docs |
| 2025-12-04 | Fixed `download_content()` method (was `retrieve_content()`) |
| 2025-12-04 | Added `cancelled`, `preprocessing`, `running` status handling |
| 2025-12-05 | Added `create_and_poll()`, `list_videos()`, `get_video()` methods |
| 2025-12-05 | Added `download_thumbnail()`, `download_spritesheet()` methods |
| 2025-12-05 | Updated README.md with Sora access requirements and resource links |
| 2025-12-05 | Documented 403 error cause: API is in preview, requires ChatGPT Pro/Plus |
| 2025-12-05 | **Added Remix feature**: `remix_video()`, `remix_video_async()`, `remix_batch()` |
| 2025-12-05 | **Added Webhook support**: `register_webhook_handler()`, `process_webhook()`, `verify_webhook_signature()`, `generate_with_webhook()` |
| 2025-12-05 | SoraClient now at 100% API feature coverage (1374 lines) |
