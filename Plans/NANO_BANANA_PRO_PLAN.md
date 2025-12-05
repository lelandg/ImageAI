# Nano Banana Pro Integration Plan

*Created: 2025-12-02*
*Last Updated: 2025-12-05 16:30*

## Executive Summary

**IMPORTANT CLARIFICATION**: "Nano Banana Pro" is Google's marketing name for **Gemini 3 Pro Image** (`gemini-3-pro-image-preview`), NOT a service from banana.dev.

Since ImageAI already has Google Gemini integration (`providers/google.py`), adding Nano Banana Pro support requires updating the existing Google provider.

---

## Part 1: Nano Banana Pro (Google Gemini 3 Pro Image)

### What is Nano Banana Pro?

**Nano Banana Pro** is Google DeepMind's marketing codename for **Gemini 3 Pro Image Preview** (`gemini-3-pro-image-preview`), released November 20, 2025. It's Google's state-of-the-art image generation and editing model.

**Model Hierarchy:**
- **Nano Banana** = `gemini-2.5-flash-image` (fast, lower cost)
- **Nano Banana Pro** = `gemini-3-pro-image-preview` (advanced, higher quality)

### Key Features

1. **High-Resolution Output**
   - Native support for 1K, 2K, and 4K generation
   - Up to 4096px maximum dimension
   - Built-in upscaling capabilities

2. **Advanced Text Rendering**
   - Legible, well-placed text in images
   - Ideal for logos, infographics, diagrams, posters, menus
   - Multilingual support with accurate typography

3. **Multi-Image Composition**
   - Support for up to **14 reference images** in a single request
   - Character consistency across up to **5 people**
   - High-fidelity blending and composition

4. **Search Grounding**
   - Integration with Google Search for real-world factuality
   - Generate images based on current events and real-time data

5. **Iterative Refinement**
   - Conversational multi-turn refinement
   - Edit and improve images across multiple requests
   - Maintains context with "thought signatures"

6. **SynthID Watermarking**
   - All generated images include Google's SynthID watermark

### API Structure and Authentication

**Authentication Method:**
- Uses Google API key (same as existing Gemini integration)
- Available through Google AI Studio and Vertex AI
- Environment variable: `GEMINI_API_KEY` or `GOOGLE_API_KEY`

**SDK Requirements:**
```bash
pip install google-genai>=1.52.0
```

**Model Identifier:**
```python
model = "gemini-3-pro-image-preview"
```

### Supported Parameters

#### Aspect Ratios (10 options)
```python
aspect_ratios = [
    "1:1", "2:3", "3:2", "3:4", "4:3",
    "4:5", "5:4", "9:16", "16:9", "21:9"
]
```

#### Resolutions
```python
resolutions = ["1K", "2K", "4K"]  # Must use uppercase 'K'
```

### Request/Response Format

**Python Example (Basic Text-to-Image):**
```python
from google import genai
from google.genai import types
import os

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

response = client.models.generate_content(
    model="gemini-3-pro-image-preview",
    contents="A futuristic city skyline at sunset with flying cars",
    config=types.GenerateContentConfig(
        response_modalities=['TEXT', 'IMAGE'],
        image_config=types.ImageConfig(
            aspect_ratio="16:9",
            image_size="2K"
        ),
    )
)

for part in response.parts:
    if part.inline_data:
        image_bytes = part.inline_data.data
    if part.text:
        print(part.text)
```

**Python Example (Multi-Image with Reference Images):**
```python
from PIL import Image

prompt = "An office group photo of these people making funny faces"

response = client.models.generate_content(
    model="gemini-3-pro-image-preview",
    contents=[
        prompt,
        Image.open('person1.png'),
        Image.open('person2.png'),
        Image.open('person3.png'),
    ],
    config=types.GenerateContentConfig(
        response_modalities=['TEXT', 'IMAGE'],
        image_config=types.ImageConfig(
            aspect_ratio="5:4",
            image_size="2K"
        ),
    )
)
```

### Pricing (as of December 2025)

| Resolution | Price per Image |
|------------|-----------------|
| 1K/2K      | $0.134          |
| 4K         | $0.24           |

**Comparison:**
- Nano Banana (Flash): $0.039 per image
- Nano Banana Pro: $0.134 per image (3.4x more expensive, higher quality)

### Generation Performance

Based on 16:9 landscape with 50-character prompt:
- **1K**: ~13 seconds
- **2K**: ~16 seconds
- **4K**: ~22 seconds

---

## Part 2: banana.dev Platform (Separate Service)

### What is banana.dev?

**banana.dev** is a **serverless GPU infrastructure platform** for deploying custom ML models. It's NOT an image generation service itself.

### When to Consider banana.dev

**Use banana.dev if you need:**
1. Custom/fine-tuned models not available via public APIs
2. Local Stable Diffusion with specific configurations
3. Hybrid deployment (some local, some cloud)
4. Cost optimization for high-volume generation

**Skip banana.dev if:**
1. Standard model access is sufficient (use provider APIs)
2. You don't want to manage deployment infrastructure
3. Existing providers (Google, OpenAI, Stability) meet your needs

---

## Implementation Plan

### Phase 1: Update Google Provider ✅ COMPLETED

**Goal:** Add Nano Banana Pro model support to existing Google provider

**Tasks:**

1. ✅ Update model definitions in `providers/google.py`
   - Model already in SUPPORTED_MODELS (was already added)
   - Model metadata available via `get_models_with_details()`

2. ✅ Add resolution parameter support
   - Implemented `image_size` parameter (1K, 2K, 4K) in ImageConfig
   - Only enabled for Nano Banana Pro model (`gemini-3` check)

3. ✅ Enhance multi-image support
   - Support up to 14 reference images for NBP
   - Dynamic limits via `MODEL_REF_LIMITS` in `ImagenReferenceWidget`

4. ✅ Update UI components
   - Added `NBPQualitySelector` widget for 1K/2K/4K selection
   - Shows only when NBP model selected
   - Integrated with batch cost display

**Files modified:**
- `providers/google.py` - Added `image_size` to ImageConfig
- `gui/settings_widgets.py` - Added NBPQualitySelector class
- `gui/imagen_reference_widget.py` - Added MODEL_REF_LIMITS and update_model()
- `gui/main_window.py` - Wired up NBP quality selector

### Phase 2: UI Enhancements ✅ COMPLETED

**Goal:** Expose new features in the GUI

**Tasks:**

1. ✅ Add resolution dropdown/selector
   - `NBPQualitySelector` with 1K, 2K, 4K radio buttons
   - Default: 2K
   - Hidden for non-Pro models, visible for NBP

2. ✅ Update reference image widget
   - Dynamic `max_references_strict` based on model
   - NBP: 14 images, Standard: 5, Default: 3
   - Count indicator updates automatically

3. ✅ Add cost estimation display
   - NBP pricing: $0.134 (1K/2K), $0.24 (4K)
   - Updates when quality tier changes
   - Integrated with BatchSelector

### Phase 3: Advanced Features ✅ COMPLETED

**Goal:** Implement advanced NBP features

**Status:** Phase 3 is **100% complete**. All major features implemented.

**Last Updated:** 2025-12-05 16:30

**Tasks:**

1. ✅ **Search Grounding** - Real-time data integration - **COMPLETED**
   - Added UI toggle "Ground with Google Search" in Advanced Settings
   - Implemented `google_search` tool in provider config when enabled
   - Files: `gui/settings_widgets.py:1553-1564`, `providers/google.py:612-621`

2. ✅ **Conversational Editing (Multi-Turn)** - **COMPLETED**
   - Created `ConversationManager` for storing chat sessions
   - Created `RefineImageDialog` for iterative image editing
   - SDK handles thought signatures automatically via chat feature
   - Files: `core/conversation_manager.py` (227 lines), `gui/refine_image_dialog.py` (315 lines)

3. ⏳ **Localized Edits** - **DEFERRED**
   - Fine-grained edits to specific regions of an image
   - Requires mask/region selection UI (complex implementation)
   - Deferred to future release

4. ✅ **Thought Signatures Support** - **COMPLETED**
   - SDK chat feature handles thought signatures automatically
   - Added `create_chat_session()` and `get_last_chat_session()` to GoogleProvider
   - No manual signature management needed when using chat
   - Files: `providers/google.py:208-270`

5. ✅ **Batch API Integration** - **COMPLETED**
   - Created `BatchManager` for managing async batch jobs
   - Created `BatchModeWidget` for queue UI and job monitoring
   - 50% discount applied automatically for batch processing
   - Files: `core/batch_manager.py` (350 lines), `gui/batch_mode_widget.py` (400 lines)

**Deliverables:** ✅
- ✅ `gui/settings_widgets.py` - Search grounding toggle added
- ✅ `providers/google.py` - Search grounding, chat sessions support
- ✅ `core/conversation_manager.py` - Multi-turn conversation storage
- ✅ `gui/refine_image_dialog.py` - Iterative refinement dialog
- ✅ `core/batch_manager.py` - Batch job management
- ✅ `gui/batch_mode_widget.py` - Batch mode UI widget

### Phase 4: Testing & Documentation ⏳ PENDING

**Tasks:**

1. ⏳ Test all resolution options (user testing)
2. ⏳ Test multi-image generation with various counts (user testing)
3. ⏳ Verify aspect ratio + resolution combinations (user testing)
4. ✅ Test Search Grounding with real-time data prompts
5. ✅ Test multi-turn conversational editing workflow
6. ⏳ Update user documentation
7. ⏳ Update CodeMap.md

---

## Feature Implementation Summary

| Feature | Priority | Complexity | Status |
|---------|----------|------------|--------|
| Search Grounding | Medium | Medium | ✅ Completed |
| Conversational Editing | High | High | ✅ Completed |
| Thought Signatures | High | Medium | ✅ Completed (SDK handles) |
| Localized Edits | Low | High | ⏳ Deferred |
| Batch API (50% discount) | Medium | Medium | ✅ Completed |

---

## Code Changes Required

### providers/google.py

```python
# Add to SUPPORTED_MODELS
SUPPORTED_MODELS = {
    'gemini-2.5-flash-image': {
        'name': 'Nano Banana (Flash)',
        'max_resolution': '1K',
        'cost_per_image': 0.039,
        'supports_multi_image': True,
        'max_reference_images': 5
    },
    'gemini-3-pro-image-preview': {
        'name': 'Nano Banana Pro',
        'max_resolution': '4K',
        'cost_per_image': 0.134,  # 1K/2K price
        'cost_4k': 0.24,
        'supports_multi_image': True,
        'max_reference_images': 14,
        'supports_resolution': True
    }
}

# Update generate_image to support image_size parameter
def generate_image(self, prompt, ..., resolution="2K"):
    config = types.GenerateContentConfig(
        response_modalities=['TEXT', 'IMAGE'],
        image_config=types.ImageConfig(
            aspect_ratio=aspect_ratio,
            image_size=resolution if self.model == "gemini-3-pro-image-preview" else None
        ),
    )
```

---

## Sources

- [Image generation with Gemini API Documentation](https://ai.google.dev/gemini-api/docs/image-generation)
- [How to Access the Nano Banana Pro API](https://apidog.com/blog/nano-banana-pro-api/)
- [Introducing Nano Banana Pro: Complete Developer Tutorial](https://dev.to/googleai/introducing-nano-banana-pro-complete-developer-tutorial-5fc8)
- [Nano Banana Pro: Gemini 3 Pro Image from Google DeepMind](https://blog.google/technology/ai/nano-banana-pro/)
- [Nano Banana AI Pricing Guide 2025](https://www.launchvault.dev/blog/nano-banana-ai-pricing-guide-2025)
- [Nano Banana Pro 4K HD Image Generation Guide](https://help.apiyi.com/nano-banana-pro-4k-generation-guide-en.html)
- [Nano Banana Pro on OpenRouter](https://openrouter.ai/google/gemini-3-pro-image-preview)
