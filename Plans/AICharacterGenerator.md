# AI-Powered Character Generator Implementation Checklist

**Last Updated:** 2026-01-03 09:07
**Status:** In Progress (Core + GUI Complete)
**Progress:** 53/57 tasks complete (Parts 1-5 done)

## Overview

Replace the local Stable Diffusion inpainting system with cloud AI image editing APIs (Gemini 2.5 Flash Image / GPT-Image-1.5) for generating Character Animator puppet visemes, eye blinks, and expressions. This approach provides higher quality results, better style consistency, and eliminates 8-12GB of local dependencies.

---

## Part 1: Remove Inpainting System ✅

### Files to Delete
- [x] Delete `core/character_animator/inpainter.py` (584 lines) ✅
- [x] Delete `scripts/check_gpu_and_download_sdxl.py` ✅
- [x] Delete `weights/character_animator/control_v11p_sd15_openpose` directory ✅

### Dependencies to Remove from `package_installer.py`
- [x] Remove `diffusers>=0.25.0` from puppet packages (`core/package_installer.py:574-575`) ✅
- [x] Remove `accelerate>=0.25.0` from puppet packages ✅
- [x] Remove `controlnet-aux>=0.0.7` from puppet packages ✅
- [x] Remove `transformers>=4.35.0` from puppet packages (depth estimation) ✅
- [x] Keep `mediapipe` (still needed for face landmark detection) ✅
- [x] Keep `psd-tools` and `svgwrite` (export formats) ✅

### Update `availability.py`
- [x] Remove `INPAINTING_AVAILABLE` flag and related checks (`core/character_animator/availability.py:20-24`) ✅
- [x] Remove diffusers import check ✅
- [x] Update `check_all_dependencies()` to remove inpainting (`availability.py:93-118`) ✅
- [x] Update `get_missing_dependencies()` to remove "Stable Diffusion Inpainting" (`availability.py:121-144`) ✅
- [x] Update `can_create_puppet()` to use AI_EDITING_AVAILABLE (`availability.py:178-202`) ✅
- [x] Update `is_full_installation()` to remove `INPAINTING_AVAILABLE` (`availability.py:205-217`) ✅
- [x] Update `get_feature_availability()` to remove inpainting entry (`availability.py:220-258`) ✅
- [x] Add new `AI_EDITING_AVAILABLE` flag for cloud API availability (`availability.py:24,43-70`) ✅

### Update `__init__.py`
- [x] Remove `INPAINTING_AVAILABLE` export (`core/character_animator/__init__.py:25-31`) ✅
- [x] Add `AI_EDITING_AVAILABLE` export ✅
- [x] Add new `AIFaceEditor`, `EditResult`, `StyleInfo` exports (`__init__.py:32-33,56-62`) ✅

### Update `constants.py`
- [x] Remove `INPAINTING_DEFAULTS` section (`core/character_animator/constants.py:281-287`) ✅
- [x] Remove `SAM_DEFAULTS` section ✅
- [x] Remove `DEPTH_DEFAULTS` section ✅
- [x] Keep `VISEME_PROMPTS` - still needed for AI prompts ✅
- [x] Update viseme prompts with `AI_VISEME_PROMPTS`, `AI_EYE_BLINK_PROMPTS`, `AI_EYEBROW_PROMPTS`, `STYLE_HINT_TEMPLATES` (`constants.py:290-380`) ✅

### Update `face_generator.py`
- [x] Remove `from .inpainter import OcclusionInpainter` import (`core/character_animator/face_generator.py`) ✅
- [x] Remove `from .availability import INPAINTING_AVAILABLE` import ✅
- [x] Stub methods for `AIFaceEditor` (Part 2 will implement) ✅
- [x] Update `generate_viseme()` signature for cloud AI (stubbed) ✅
- [x] Update `generate_blink_states()` signature for cloud AI (stubbed) ✅
- [x] Update `generate_eyebrow_variants()` signature for cloud AI (stubbed) ✅

### Update `segmenter.py`
- [x] Remove depth estimation (Depth-Anything) (`core/character_animator/segmenter.py`) ✅
- [x] Keep SAM2 as optional enhancement (not removed, but optional) ✅
- [x] Remove `handle_occlusions()` method ✅
- [x] Simplify to just pose + face landmark detection with optional SAM ✅

---

## Part 2: Create AI Face Editor ✅

### New File: `core/character_animator/ai_face_editor.py`

This module provides the core AI editing capability using cloud APIs.

**Architecture:**
```
AIFaceEditor
├── __init__(provider: str, model: str)
├── edit_face_region(image, mask, prompt, preserve_regions)
├── generate_viseme(image, mouth_bbox, viseme_name)
├── generate_eye_blink(image, eye_bbox, side)
├── generate_expression(image, face_bbox, expression)
└── _call_api(image, mask, prompt) → dispatch to provider
```

**Provider Support:**
| Provider | Model | Mask Support | Face Preservation | Notes |
|----------|-------|--------------|-------------------|-------|
| Google | gemini-2.5-flash-image | Via conversation | Built-in | Best for iterative editing |
| Google | gemini-3-pro-image | Via conversation | Built-in | Higher quality tier |
| OpenAI | gpt-image-1.5 | PNG alpha mask | `input_fidelity=high` | Best face preservation |
| OpenAI | gpt-image-1 | PNG alpha mask | `input_fidelity=high` | Alternative |

**Implementation Tasks:**
- [x] Create `AIFaceEditor` class with provider abstraction (`core/character_animator/ai_face_editor.py:82-130`) ✅
- [x] Implement Gemini conversational editing for face regions (`ai_face_editor.py:327-384`) ✅
- [x] Implement OpenAI mask-based editing with `input_fidelity=high` (`ai_face_editor.py:386-452`) ✅
- [x] Add caching layer (hash-based like current system) (`ai_face_editor.py:220-246`) ✅
- [x] Add quality validation (compare edited vs original) (`ai_face_editor.py:454-506`) ✅
- [x] Add retry logic with exponential backoff (`ai_face_editor.py:274-320`) ✅

**Additional Implementation:**
- [x] Updated `face_generator.py` to use AIFaceEditor (`core/character_animator/face_generator.py:28,84-90`) ✅
- [x] Updated `__init__.py` exports (`core/character_animator/__init__.py:32-33,56-60`) ✅
- [x] Added AI_VISEME_PROMPTS enhanced for cloud AI editing (`ai_face_editor.py:45-60`) ✅
- [x] Added conversation session support for Gemini batch editing (`ai_face_editor.py:572-598`) ✅

---

## Part 3: Enhanced Viseme Generation ✅

### AI Prompting Strategy

The key insight: AI image editing can fully regenerate facial features (not just blend/inpaint). This means:

1. **Mouth shapes can change size/shape** - AI understands facial anatomy
2. **Eyebrows can raise/lower naturally** - No seam artifacts
3. **Style consistency is automatic** - AI preserves overall character style
4. **Works with any art style** - Cartoon, anime, realistic, pixel art

### Viseme Generation Prompts (Enhanced)

Update `VISEME_PROMPTS` for AI editing context:

```python
AI_VISEME_PROMPTS = {
    "Neutral": "Edit the mouth to show a relaxed, neutral expression with lips gently together",
    "Ah": "Edit the mouth to be wide open as if saying 'AH', jaw dropped, showing some tongue, maintaining character style",
    "D": "Edit the mouth showing tongue tip touching behind upper front teeth, slightly open, as if saying 'D' or 'T'",
    "Ee": "Edit the mouth into a wide smile with teeth visible, lips pulled back horizontally, as if saying 'EE'",
    "F": "Edit the mouth with top teeth resting on lower lip, as if saying 'F' or 'V'",
    "L": "Edit the mouth slightly open with tongue tip visible at roof of mouth, as if saying 'L'",
    "M": "Edit the mouth with lips firmly pressed together, closed, as if saying 'M', 'B', or 'P'",
    "Oh": "Edit the mouth into a rounded 'O' shape, lips pursed forward, as if saying 'OH'",
    "R": "Edit the mouth slightly pursed and rounded, barely open, as if saying 'R'",
    "S": "Edit the mouth with teeth together, slight smile, lips parted, as if saying 'S' or 'Z'",
    "Uh": "Edit the mouth slightly open with relaxed jaw, neutral lip position, as if saying 'UH'",
    "W-Oo": "Edit the mouth with lips pursed forward like whistling, small rounded opening, as if saying 'W' or 'OO'",
    "Smile": "Edit the mouth into a warm, happy smile with raised cheeks, teeth may be visible",
    "Surprised": "Edit the mouth wide open in surprise with raised eyebrows, shocked expression",
}
```

### Implementation Tasks
- [x] Create enhanced viseme prompts optimized for AI editing (`constants.py:290-380`) ✅
- [x] Implement iterative refinement with retry logic (`ai_face_editor.py:362-395`) ✅
- [x] Add character style extraction: `extract_style_info()`, `_detect_art_style()`, `_extract_dominant_colors()` (`ai_face_editor.py:618-773`) ✅
- [x] Support user-provided style hints via `style_hint` parameter and `_build_prompt_with_style()` (`ai_face_editor.py:93-106,775-803`) ✅

---

## Part 4: Provider-Specific Implementation ✅

### Gemini 2.5 Flash Image Implementation

**API Pattern:** Conversational multi-turn editing

```python
# Pseudo-code
chat = client.chats.create(
    model="gemini-2.5-flash-image",
    config=types.GenerateContentConfig(response_modalities=['IMAGE'])
)

# Initial: Upload character image
chat.send_message([character_image, "This is my character. I'll ask you to edit facial expressions."])

# Generate each viseme
for viseme in REQUIRED_VISEMES:
    response = chat.send_message(f"Edit the mouth region to show: {AI_VISEME_PROMPTS[viseme]}")
    viseme_images[viseme] = response.image
```

**Advantages:**
- Maintains character consistency across edits via conversation context
- Natural language masking ("edit only the mouth area")
- Can reference previous edits

**Tasks:**
- [x] Implement Gemini chat-based editing in `providers/google.py` (`providers/google.py:1799-1906`) ✅
- [x] Add `edit_image_region()` method (`providers/google.py:1799`) ✅
- [x] Handle multi-turn context for batch viseme generation (`providers/google.py:1867-1870`) ✅
- [x] Add conversation reset for new characters (`providers/google.py:1908-1987`) ✅

### GPT-Image-1.5 Implementation

**API Pattern:** Mask-based single edits

```python
# Create mask with transparent area where editing should occur
mask = create_alpha_mask(mouth_bbox, image_size)

result = client.images.edit(
    model="gpt-image-1.5",
    image=open(character_image_path, "rb"),
    mask=mask,  # PNG with alpha channel
    prompt=f"Edit this character's mouth to show: {viseme_prompt}",
    input_fidelity="high"  # Preserve face accurately
)
```

**Advantages:**
- Precise mask control
- `input_fidelity="high"` preserves facial features
- Batch processing (no conversation context needed)

**Tasks:**
- [x] Implement OpenAI mask-based editing in `providers/openai.py` (`providers/openai.py:693-840`) ✅
- [x] Add `edit_image_region()` method with mask support (`providers/openai.py:693`) ✅
- [x] Create mask generation utility (PIL → PNG with alpha) (`providers/openai.py:639-691`) ✅
- [x] Implement batch generation for all visemes (`providers/openai.py:842-895`) ✅

---

## Part 5: GUI Updates ✅

### Settings Integration
- [x] Add model selection for character generation (separate from image generation) (`puppet_wizard.py:533-564`) ✅
- [x] Add provider & model dropdowns in VisemeGenerationPage (`puppet_wizard.py:537-552`) ✅
- [x] Options: "Gemini 2.5 Flash Image", "Gemini 3 Pro", "GPT-Image-1.5", "GPT-Image-1" (`puppet_wizard.py:504-518`) ✅
- [x] Show per-image cost estimate based on selected model (`puppet_wizard.py:646-681`) ✅

### Wizard Updates
- [x] Remove dependency check for "AI Inpainting" / diffusers (`puppet_wizard.py:70-76`) ✅
- [x] Update progress messages for cloud AI generation (`puppet_wizard.py:1106-1164`) ✅
- [x] Add estimated time based on viseme count × API latency (`puppet_wizard.py:668-681`) ✅
- [s] Show per-viseme preview during generation - Skipped (already shows progress text)

### Error Handling
- [x] Handle API rate limits gracefully (queue + retry) (`puppet_wizard.py:1135-1145`) ✅
- [x] Show clear error if API key missing for selected provider (`puppet_wizard.py:780-795`) ✅
- [x] Suggest switching providers if one fails (`puppet_wizard.py:791-795`) ✅

---

## Part 6: Quality Optimization

### Face Region Detection (Keep from Current)
- [ ] Keep MediaPipe face mesh for precise landmark detection
- [ ] Use landmarks to create accurate mouth/eye bounding boxes
- [ ] No changes needed to landmark detection code

### Quality Validation
- [ ] Compare generated viseme to original (histogram/SSIM)
- [ ] Detect if mouth region actually changed
- [ ] Detect style drift (generated looks different from character)
- [ ] Auto-retry with modified prompt if validation fails

### Caching Strategy
- [ ] Cache by: `hash(image) + provider + model + viseme_name`
- [ ] Store in `cache/ai_visemes/` directory
- [ ] Include generation metadata JSON sidecar
- [ ] Clear cache when source image changes

---

## Cost Analysis

| Model | Cost per Image | 14 Visemes + 2 Blinks | Full Puppet (w/ expressions) |
|-------|---------------|------------------------|------------------------------|
| Gemini 2.5 Flash Image | $0.039 | $0.62 | ~$1.00 |
| Gemini 3 Pro | ~$0.10 | $1.60 | ~$2.50 |
| GPT-Image-1.5 | ~$0.04-0.12 | $0.80-2.00 | ~$1.50-3.00 |
| GPT-Image-1 | ~$0.02-0.08 | $0.40-1.20 | ~$0.75-2.00 |

**Note:** Cloud AI costs ~$1-3 per character vs. 8-12GB download + GPU requirements for local SD. The convenience and quality improvement justify the cost.

---

## Testing Plan

- [ ] Test with cartoon character (simple style)
- [ ] Test with anime character (distinct style)
- [ ] Test with realistic photo
- [ ] Test with pixel art character
- [ ] Verify all 14 visemes look correct
- [ ] Verify eye blinks look natural
- [ ] Verify import into Adobe Character Animator
- [ ] Test with both Gemini and OpenAI providers

---

## Migration Notes

### Breaking Changes
- Characters generated with old system (SD inpainting) will continue to work
- New characters require API key for Gemini or OpenAI
- Users without cloud API access can still use manual viseme creation

### Backwards Compatibility
- Keep export formats (PSD, SVG) unchanged
- Keep layer naming conventions unchanged
- Keep viseme names and structure unchanged
- Only the generation method changes

---

## Future Enhancements (Out of Scope)

- Video-based lip sync directly via AI (instead of viseme switching)
- Real-time expression transfer using AI
- Multi-angle character generation
- Body pose variation generation

---

## Sources

- [Gemini 2.5 Flash Image Guide](https://ai.google.dev/gemini-api/docs/image-generation)
- [OpenAI GPT Image Documentation](https://platform.openai.com/docs/guides/image-generation)
- [GPT-Image-1.5 High Input Fidelity](https://cookbook.openai.com/examples/generate_images_with_high_input_fidelity)
- [Gemini Conversational Editing](https://www.datacamp.com/tutorial/gemini-2-5-flash-image-guide)
- [OpenAI Mask Editing](https://www.cometapi.com/how-to-edit-images-using-openai-gpt-image-1-api/)
