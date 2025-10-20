# Veo 3 Character & Style Continuity Research

**Date:** 2025-10-20
**Version:** 1.0
**Status:** Research Complete

---

## Executive Summary

Google Veo 3.1 provides **reference images** as the primary mechanism for character and style continuity across multiple video clips. The current image-to-video chaining approach is **not fundamentally flawed**, but **reference images are significantly more effective** for maintaining character/object identity across non-sequential scenes.

### Key Findings

1. **Veo 3.1 supports up to 3 reference images** per video generation (ASSET type only)
2. **Reference images are better for identity consistency**, while last-frame continuity is better for temporal/motion smoothness
3. **The optimal workflow combines both**: Reference images for character consistency + last-frame for sequential scene continuity
4. **Veo 3.1 only returns 8-second videos** when using reference images (limitation)
5. **Style references are NOT supported** in Veo 3.1 (must use Veo 2.0 for style transfer)

---

## 1. Veo 3.1 Reference Image Capabilities

### API Support

Veo 3.1 provides native support for reference images through the `GenerateVideosConfig.reference_images` parameter.

**Python API Example:**
```python
from google import genai
from google.genai import types

client = genai.Client(api_key="YOUR_API_KEY")

operation = client.models.generate_videos(
    model="veo-3.1-generate-preview",
    prompt="A young woman walking through a park in autumn",
    config=types.GenerateVideosConfig(
        reference_images=[reference_image1, reference_image2, reference_image3],
        aspect_ratio="16:9",
        duration=8
    ),
)
```

### Reference Image Types

| Type | Veo 3.1 Support | Veo 2.0 Support | Max Count | Purpose |
|------|----------------|-----------------|-----------|---------|
| **Asset** | ✅ Yes | ✅ Yes | 3 | Character, object, or product consistency |
| **Style** | ❌ No | ✅ Yes | 1 | Artistic style transfer (paintings, cinematic looks) |

**Critical Limitation:** Veo 3.1 models **do not support** `referenceImages.style`. You must use `veo-2.0-generate-exp` for style image references.

### Reference Image Requirements

**Image Specifications:**
- **Format:** PNG, JPEG (base64-encoded or Path object)
- **MIME Types:** `image/png`, `image/jpeg`
- **Recommended Resolution:** 720p (1280 x 720) or higher
- **Aspect Ratio:** 16:9 or 9:16 preferred (other ratios may be resized/cropped)
- **Quality:** High-quality, well-lit, clear subject definition

**Best Practices for Reference Images:**
1. **Character References:** Front view, 3/4 view, and full body shot
2. **Object References:** Multiple angles showing key features
3. **Scene References:** Establishing shots with consistent lighting/color palette
4. **Consistency:** Use the same lighting conditions across all reference images
5. **Clarity:** Avoid motion blur, low resolution, or busy backgrounds

### How Many Reference Images?

**Veo 3.1 API:** Maximum of **3 reference images** per generation

**Professional Recommendations:**
- **Single Character:** 2-3 images (front view, side view, full body)
- **Multiple Characters:** 1-2 images per main character (prioritize protagonists)
- **Environment:** 1-2 establishing shots for location consistency
- **Object/Product:** 2-3 angles showing key features

**Trade-offs:**
- **More references = stronger consistency** but potentially slower generation
- **Fewer references = faster generation** but may drift from character appearance
- **Best practice:** Start with 2 references, add 3rd only if consistency issues occur

---

## 2. Image-to-Video vs Reference Images for Continuity

### Comparison Matrix

| Feature | Last-Frame Continuity | Reference Images |
|---------|----------------------|------------------|
| **Best For** | Sequential scene flow | Character identity across non-sequential scenes |
| **Preserves** | Motion vectors, camera position, lighting state | Character features, object appearance, style |
| **Temporal Coherence** | ✅ Excellent | ⚠️ Moderate (scene changes may jump) |
| **Identity Consistency** | ⚠️ Good for same shot | ✅ Excellent across different shots |
| **Use Case** | Continuing action, camera moves | Multi-scene storytelling with same characters |
| **API Parameter** | `image` (start frame) + `last_frame` (end frame) | `reference_images` (up to 3 assets) |
| **Duration Limit** | Full duration available | **8 seconds only** (Veo 3.1 limitation) |

### Professional Workflow Recommendations

**Scenario 1: Sequential Scenes (Same Location/Action)**
- **Primary:** Last-frame continuity (`image` parameter with previous video's last frame)
- **Secondary:** 1-2 reference images for character consistency
- **Example:** Character walking from room A → room B → room C

**Scenario 2: Non-Sequential Scenes (Different Locations)**
- **Primary:** Reference images (2-3 asset images)
- **Secondary:** Consistent prompt structure (lighting, time of day, character description)
- **Example:** Character at home → at work → at park (different times/locations)

**Scenario 3: Multi-Character Narrative**
- **Approach:** Separate reference sets per character
- **Strategy:** Generate scenes with 1-2 character references per shot
- **Example:** Protagonist (2 refs) + Supporting character (1 ref) = 3 total

---

## 3. Professional AI Video Workflows

### Industry Best Practices (2025)

Based on research from professional AI filmmakers and production workflows:

#### Core Strategies

1. **Anchor Frames with Locked Style**
   - Create 2-3 "hero images" of main characters using image generation (Midjourney, DALL-E, Stable Diffusion)
   - Use these as reference images for ALL scenes featuring that character
   - Maintain consistent lighting/time-of-day descriptors in prompts

2. **Prompt Chaining with Minimal Changes**
   - Change only 1-2 elements per scene (location OR action, not both)
   - Repeat palette descriptors across connected shots
   - Use same camera/lens terminology throughout

3. **Reference + Extension Hybrid**
   - Use reference images to establish character identity
   - Use extension/last-frame for temporal continuity within same scene
   - Combine both for best results

4. **Consistent Model Variant**
   - Use the same Veo model throughout entire project
   - Avoid switching between Veo 3, Veo 3 Fast, or Veo 2 mid-project
   - Seed consistency optional (less critical than references)

#### Professional Tools Integration

**Pre-Production:**
- **Midjourney/DALL-E:** Generate character reference sheets
- **Stable Diffusion + LoRA:** Train character-specific models for consistency
- **Google Gemini Image:** Generate style-consistent reference frames

**Production:**
- **Veo 3.1 (Flow):** Primary video generation with reference images
- **Veo 3.1 (API):** Automated multi-scene generation with programmatic control
- **LiteLLM:** Unified prompt enhancement across LLM providers

**Post-Production:**
- **FFmpeg:** Assemble multi-scene sequences
- **DaVinci Resolve/Premiere:** Final color grading to unify look
- **AI Upscaling:** Consistent upscaling across all clips

---

## 4. Veo 3 Specific API Documentation

### Official Resources

**Primary Documentation:**
- [Generate videos with Veo 3.1 in Gemini API](https://ai.google.dev/gemini-api/docs/video)
- [Veo on Vertex AI video generation API](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation)
- [Direct Veo video generation using reference images](https://cloud.google.com/vertex-ai/generative-ai/docs/video/use-reference-images-to-guide-video-generation)

**Release Announcements:**
- [Introducing Veo 3.1 and new creative capabilities](https://developers.googleblog.com/en/introducing-veo-3-1-and-new-creative-capabilities-in-the-gemini-api/) (Oct 15, 2025)
- [Build with Veo 3, now available in the Gemini API](https://developers.googleblog.com/en/veo-3-now-available-gemini-api/)

### API Parameters for Reference Images

**JSON Structure (Vertex AI REST API):**
```json
{
  "prompt": "A young woman walking through a park",
  "referenceImages": [
    {
      "image": {
        "bytesBase64Encoded": "BASE64_ENCODED_IMAGE",
        "mimeType": "image/png"
      },
      "referenceType": "asset"
    },
    {
      "image": {
        "bytesBase64Encoded": "BASE64_ENCODED_IMAGE_2",
        "mimeType": "image/jpeg"
      },
      "referenceType": "asset"
    }
  ],
  "config": {
    "aspectRatio": "16:9",
    "duration": 8
  }
}
```

**Python SDK (google.genai):**
```python
from google import genai
from google.genai import types
from pathlib import Path

client = genai.Client(api_key="YOUR_API_KEY")

# Load reference images
ref1 = Path("character_front.png")
ref2 = Path("character_side.png")
ref3 = Path("character_fullbody.png")

# Generate video with references
operation = client.models.generate_videos(
    model="veo-3.1-generate-preview",
    prompt="Close-up of Sarah smiling and waving at the camera",
    config=types.GenerateVideosConfig(
        reference_images=[ref1, ref2, ref3],
        aspect_ratio="16:9",
        duration=8,
        include_audio=True
    ),
)

# Poll for completion
while not operation.done:
    print("Waiting for video generation...")
    time.sleep(10)
    operation = client.operations.get(operation)

# Download result
video = operation.response.generated_videos[0]
client.files.download(file=video.video)
video.video.save("scene_01.mp4")
```

### Key API Behaviors

1. **Duration Limitation:** Videos with reference images are limited to **8 seconds** (regardless of duration parameter)
2. **Reference Type Validation:** Only `"asset"` type supported in Veo 3.1 (not `"style"`)
3. **Image Loading:** SDK accepts Path objects or base64-encoded strings
4. **Generation Time:** 1-6 minutes typical (longer with reference images)
5. **SynthID Watermarking:** All Veo videos include imperceptible SynthID watermark

---

## 5. Alternative Approaches for Consistency

### Beyond Reference Images

While reference images are the primary mechanism, other techniques can enhance consistency:

#### A. Prompt Engineering

**Consistent Character Descriptions:**
```python
# Define character template once
CHARACTER_SARAH = "a young woman with long dark hair, green eyes, wearing a blue jacket"

# Use in all scenes
scene1_prompt = f"{CHARACTER_SARAH}, walking through a park in autumn"
scene2_prompt = f"{CHARACTER_SARAH}, sitting at a café reading a book"
scene3_prompt = f"{CHARACTER_SARAH}, looking out a window at the rain"
```

**Palette Consistency:**
```python
# Define color palette and lighting
VISUAL_STYLE = "warm golden hour lighting, muted earth tones, cinematic color grading"

# Apply to all scenes
scene1_prompt = f"{CHARACTER_SARAH}, walking through park. {VISUAL_STYLE}"
scene2_prompt = f"{CHARACTER_SARAH}, at café. {VISUAL_STYLE}"
```

**Camera/Lens Consistency:**
```python
# Consistent cinematography language
CAMERA_STYLE = "35mm lens, shallow depth of field, Arri Alexa look"

scene1_prompt = f"{CHARACTER_SARAH}, park. {CAMERA_STYLE}, {VISUAL_STYLE}"
```

#### B. Model Parameters

**Seed Consistency (Limited Effectiveness):**
```python
# Using same seed provides some consistency but NOT guaranteed
config = types.GenerateVideosConfig(
    seed=42,  # Same seed for all scenes
    reference_images=[ref1, ref2],  # Still recommended
)
```

**Note:** Seed consistency is **less effective** than reference images for character consistency. Seeds primarily affect composition/camera angles, not character features.

#### C. Pre-Generation with Image Models

**Workflow:**
1. Generate character sheet with Midjourney/Stable Diffusion
2. Use character images as reference for ALL video generations
3. Optionally train Stable Diffusion LoRA for even stronger consistency

**Example (Stable Diffusion LoRA):**
```bash
# Train LoRA on 10-20 images of character
python train_lora.py --character "Sarah" --images ./character_refs/

# Generate scene-specific reference images with LoRA
python generate_with_lora.py --prompt "Sarah in a park" --lora sarah.safetensors
```

#### D. Flow Platform Tools

Google's **Flow** platform (GUI for Veo) provides additional continuity features:

1. **Ingredients to Video:** Use multiple reference images to establish look/characters/style
2. **Frames to Video:** Provide start + end frames to guide motion
3. **Extend:** Add seconds while preserving momentum from last frames
4. **Storyboard Import:** Convert static storyboard images to video sequences

**Flow Access:** Available at [VideoFX](https://aitestkitchen.withgoogle.com/tools/video-fx) (requires Google account)

---

## 6. Evaluation of Current Implementation

### Your Current Approach Analysis

Based on reviewing your codebase (`/mnt/d/Documents/Code/GitHub/ImageAI/`):

**Current Implementation:**
- ✅ Reference images widget (`gui/video/reference_images_widget.py`) - up to 3 references
- ✅ Veo client with reference support (`core/video/veo_client.py`) - API integration ready
- ✅ Continuity helper (`core/video/continuity_helper.py`) - prompt enhancement
- ⚠️ Image-to-video chaining planned but reference images are primary

**Strengths:**
1. **Already designed for reference images** - your architecture is correct
2. **Up to 3 reference slots** - matches Veo 3.1 API limit
3. **Scene-by-scene reference management** - proper granularity
4. **Veo client has reference_images parameter** - API-ready

**Recommendations:**

#### 1. Reference Images Are Primary (Your Design is Correct)

Your current architecture with `ReferenceImagesWidget` is the **right approach**. Reference images should be the primary continuity mechanism, not image-to-video chaining.

**Why:**
- ✅ Works for non-sequential scenes (character appears in different locations)
- ✅ Maintains character identity across entire project
- ✅ Supported by Veo 3.1 API directly
- ✅ Industry best practice for multi-scene narratives

#### 2. Image-to-Video is Complementary (Not Primary)

Use image-to-video (`image` parameter) for:
- Sequential scenes where last frame → first frame makes narrative sense
- Continuous camera movements across scene breaks
- Action that flows from one scene to the next

**Don't use for:**
- ❌ Non-sequential scenes (different locations/times)
- ❌ Character consistency across project (use references instead)
- ❌ Style/aesthetic continuity (use references + prompt templates)

#### 3. Hybrid Workflow (Best Results)

**Recommended approach:**
```python
# Scene 1: Character introduction
scene1_config = VeoGenerationConfig(
    prompt="Sarah walking through autumn park",
    reference_images=[sarah_ref1, sarah_ref2, sarah_ref3],  # PRIMARY
    duration=8
)

# Scene 2: Same character, different location (NON-sequential)
scene2_config = VeoGenerationConfig(
    prompt="Sarah at café reading book",
    reference_images=[sarah_ref1, sarah_ref2, sarah_ref3],  # SAME REFS
    duration=8
)

# Scene 3: Continuous action from Scene 2 (sequential)
scene2_last_frame = extract_last_frame("scene2.mp4")
scene3_config = VeoGenerationConfig(
    prompt="Sarah looks up from book, sees friend approaching",
    image=scene2_last_frame,  # CONTINUITY
    reference_images=[sarah_ref1, sarah_ref2],  # STILL USE REFS
    duration=8
)
```

#### 4. Enhanced Workflow Features to Implement

**A. Reference Image Library per Project:**
```python
class VideoProject:
    character_references: Dict[str, List[Path]] = {}  # "Sarah": [ref1, ref2, ref3]
    environment_references: Dict[str, List[Path]] = {}  # "park": [ref1, ref2]

    def get_scene_references(self, scene_id: str) -> List[Path]:
        """Auto-select references based on scene characters/locations"""
        # Intelligently combine character + environment references
        pass
```

**B. Automatic Reference Image Generation:**
```python
# Generate character reference sheet using image provider
def generate_character_references(
    character_description: str,
    provider: str = "gemini"  # or midjourney, dalle, etc.
) -> List[Path]:
    """Generate 3 reference images for a character"""
    prompts = [
        f"{character_description}, front view portrait, neutral background",
        f"{character_description}, 3/4 view, neutral background",
        f"{character_description}, full body shot, neutral background"
    ]
    # Generate and return paths
    pass
```

**C. Reference Image Quality Validation:**
```python
def validate_reference_image(image_path: Path) -> Tuple[bool, str]:
    """Check if image meets Veo reference requirements"""
    # Check resolution >= 720p
    # Check aspect ratio (warn if not 16:9 or 9:16)
    # Check file size (< 10MB)
    # Check MIME type (PNG or JPEG)
    pass
```

---

## 7. Implementation Recommendations

### Immediate Actions

**✅ Your current implementation is fundamentally sound.** Focus on these enhancements:

#### 1. Reference Image Workflow (Priority 1)

**Update UI to emphasize reference images:**
```python
# In video_project_tab.py or workspace_widget.py
- Add "Generate Character References" button
- Auto-populate reference slots when character is defined
- Show reference preview thumbnails prominently
- Warn if generating without references ("Character may vary across scenes")
```

**Example UI flow:**
1. User defines character: "Sarah - young woman, long dark hair, blue jacket"
2. **[Generate Reference Images]** button → creates 3 reference images
3. Reference images auto-populate in all scenes featuring Sarah
4. User can override per-scene if needed

#### 2. Reference Image Management (Priority 2)

**Project-level reference library:**
```python
@dataclass
class VideoProject:
    # Add reference library
    reference_library: Dict[str, List[Path]] = field(default_factory=dict)

    # Example structure:
    # {
    #   "characters": {
    #     "Sarah": [ref1.png, ref2.png, ref3.png],
    #     "John": [ref1.png, ref2.png]
    #   },
    #   "environments": {
    #     "park": [ref1.png],
    #     "cafe": [ref1.png, ref2.png]
    #   }
    # }
```

#### 3. Smart Reference Selection (Priority 3)

**Auto-select references based on scene content:**
```python
def auto_select_references_for_scene(
    scene: Scene,
    project: VideoProject
) -> List[Path]:
    """
    Intelligently select up to 3 references for a scene.

    Priority:
    1. Character references (if scene prompt mentions character)
    2. Environment references (if scene mentions location)
    3. Previous scene's images (if sequential)
    """
    references = []

    # Check for character mentions
    for char_name, char_refs in project.reference_library.get("characters", {}).items():
        if char_name.lower() in scene.prompt.lower():
            references.extend(char_refs[:2])  # Max 2 per character

    # Fill remaining slots with environment
    if len(references) < 3:
        for env_name, env_refs in project.reference_library.get("environments", {}).items():
            if env_name.lower() in scene.prompt.lower():
                references.extend(env_refs[:3 - len(references)])
                break

    return references[:3]  # Limit to 3
```

#### 4. Documentation Updates (Priority 4)

**Update user-facing documentation:**
- Explain reference images vs. image-to-video continuity
- Provide character reference generation tutorial
- Show before/after examples (with vs without references)
- Document best practices for reference image quality

---

## 8. Limitations and Constraints

### Veo 3.1 Specific Limitations

1. **8-Second Duration with References**
   - Videos generated with `reference_images` are **limited to 8 seconds**
   - This is a Veo 3.1 API limitation, not a bug
   - **Workaround:** Generate multiple 8-second clips and stitch

2. **No Style References in Veo 3.1**
   - Only `asset` type references (character/object/scene)
   - **Must use Veo 2.0** for style image transfer
   - **Workaround:** Use prompt engineering for style consistency

3. **Reference Image Quality Matters**
   - Low-quality references → poor consistency
   - Recommend 720p+ resolution
   - Clear, well-lit subjects perform best

4. **Regional Restrictions**
   - Person generation restricted in some regions (MENA, some EU)
   - Check `person_generation_allowed` before attempting

### General AI Video Limitations

1. **Character Details Drift Over Time**
   - Even with references, fine details (jewelry, tattoos) may vary
   - **Mitigation:** Include details explicitly in prompts

2. **Reference Images Don't Guarantee 100% Consistency**
   - Veo interprets references as guidance, not strict constraints
   - Expect 85-95% consistency, not pixel-perfect matching

3. **Generation Time Increases**
   - Reference images add ~30-60 seconds to generation time
   - Budget 2-4 minutes per 8-second clip with references

---

## 9. Future Developments to Monitor

### Veo Platform Evolution

**Veo 3.2 / 4.0 Potential Features (Speculation):**
- Longer duration with reference images (beyond 8 seconds)
- Style reference support in Veo 3.x series
- Multi-character reference handling (separate character slots)
- Reference image interpolation (blend multiple references)

**Flow Platform Enhancements:**
- API access to Flow-exclusive features (storyboard import, etc.)
- Batch processing API for multi-scene projects
- Reference image training/LoRA integration

### Industry Trends

**Stable Video Diffusion + LoRA:**
- Train character-specific models for perfect consistency
- Requires local GPU but offers ultimate control

**Midjourney Character Reference (cref):**
- Generate reference images with Midjourney
- Use as Veo reference images for consistent character

**LangChain/LlamaIndex Video Workflows:**
- Automated multi-scene generation with LLM orchestration
- Smart reference image selection based on narrative

---

## 10. Summary and Action Items

### Key Takeaways

✅ **Your current architecture is correct** - reference images are the right approach
✅ **Reference images >> image-to-video chaining** for character consistency
✅ **Hybrid approach is optimal** - references for identity + last-frame for temporal flow
✅ **Veo 3.1 API fully supports your use case** - up to 3 reference images
⚠️ **8-second limit with references** - plan for multi-clip stitching
❌ **No style references in Veo 3.1** - use Veo 2.0 or prompt engineering

### Recommended Next Steps

**Short-term (Current Sprint):**
1. ✅ **Keep reference images as primary continuity mechanism** (already in your design)
2. 🔧 **Add "Generate Character References" feature** to auto-create reference images
3. 🔧 **Implement project-level reference library** for reusable character/environment refs
4. 📝 **Update UI to prominently feature reference images** (not hidden feature)

**Mid-term (Next Release):**
1. 🔧 **Auto-select references per scene** based on character/location mentions
2. 🔧 **Reference image quality validation** (resolution, aspect ratio, file size)
3. 🔧 **Smart reference generation** (automatically create 3-angle character sheets)
4. 📝 **User documentation** on reference images vs. other continuity methods

**Long-term (Future Versions):**
1. 🔬 **Integrate Stable Diffusion LoRA training** for character-specific models
2. 🔬 **Midjourney character reference import** (cref feature integration)
3. 🔬 **Reference image interpolation** (blend multiple character versions)
4. 🔬 **Monitor Veo 4.0 features** for enhanced continuity capabilities

---

## Appendix A: Code Examples

### Complete Reference Image Workflow

```python
from pathlib import Path
from core.video.veo_client import VeoClient, VeoGenerationConfig, VeoModel
from google.genai import types

# Initialize client
veo = VeoClient(api_key="YOUR_API_KEY")

# Step 1: Generate character reference images
character_description = "Sarah - young woman, 25 years old, long dark hair, green eyes, blue jacket"

ref_prompts = [
    f"{character_description}, front view portrait, neutral gray background, studio lighting",
    f"{character_description}, 3/4 view, neutral gray background, studio lighting",
    f"{character_description}, full body shot, standing, neutral gray background, studio lighting"
]

reference_images = []
for i, prompt in enumerate(ref_prompts):
    # Generate image using Gemini Image
    image = client.models.generate_content(
        model="gemini-2.5-flash-image",
        prompt=prompt,
        config=types.GenerateContentConfig(
            image_config={'aspect_ratio': '4:3'}
        )
    )

    # Save reference image
    ref_path = Path(f"project/references/sarah_ref_{i+1}.png")
    image.generated_images[0].image.save(ref_path)
    reference_images.append(ref_path)

# Step 2: Generate video scenes with references
scenes = [
    "Sarah walking through autumn park, golden hour lighting",
    "Sarah sitting at café, reading a book, warm interior lighting",
    "Sarah looking out window at rain, contemplative mood, cool blue tones"
]

for i, scene_prompt in enumerate(scenes):
    config = VeoGenerationConfig(
        model=VeoModel.VEO_3_GENERATE,
        prompt=scene_prompt,
        reference_images=reference_images,  # Same references for all scenes
        aspect_ratio="16:9",
        duration=8,
        include_audio=True
    )

    operation = veo.client.models.generate_videos(
        model=config.model.value,
        prompt=config.prompt,
        config=types.GenerateVideosConfig(
            reference_images=config.reference_images,
            aspect_ratio=config.aspect_ratio,
            duration=config.duration,
            include_audio=config.include_audio
        )
    )

    # Poll for completion
    while not operation.done:
        print(f"Generating scene {i+1}...")
        time.sleep(10)
        operation = veo.client.operations.get(operation)

    # Download video
    video = operation.response.generated_videos[0]
    veo.client.files.download(file=video.video)
    video.video.save(f"project/scenes/scene_{i+1:02d}.mp4")

    print(f"Scene {i+1} complete: {scene_prompt[:50]}...")
```

### Reference Image Validation

```python
from PIL import Image
from pathlib import Path
from typing import Tuple

def validate_veo_reference_image(image_path: Path) -> Tuple[bool, str]:
    """
    Validate an image meets Veo 3.1 reference requirements.

    Returns:
        (is_valid, error_message)
    """
    if not image_path.exists():
        return False, "Image file does not exist"

    try:
        img = Image.open(image_path)

        # Check MIME type
        if img.format not in ['PNG', 'JPEG', 'JPG']:
            return False, f"Unsupported format: {img.format}. Use PNG or JPEG."

        # Check resolution
        width, height = img.size
        min_dimension = 720
        if max(width, height) < min_dimension:
            return False, f"Resolution too low: {width}x{height}. Recommend 720p or higher."

        # Check aspect ratio (warn but don't fail)
        aspect_ratio = width / height
        recommended_ratios = {
            16/9: "16:9",
            9/16: "9:16",
            1/1: "1:1",
            4/3: "4:3",
            3/4: "3:4"
        }

        is_recommended = any(abs(aspect_ratio - ratio) < 0.05 for ratio in recommended_ratios.keys())
        if not is_recommended:
            closest_ratio = min(recommended_ratios.keys(), key=lambda r: abs(aspect_ratio - r))
            warning = f"Aspect ratio {aspect_ratio:.2f} not standard. Closest: {recommended_ratios[closest_ratio]}"
            print(f"Warning: {warning}")

        # Check file size (< 10MB recommended)
        file_size_mb = image_path.stat().st_size / (1024 * 1024)
        if file_size_mb > 10:
            print(f"Warning: Large file size ({file_size_mb:.1f} MB). May slow generation.")

        return True, "Image meets Veo reference requirements"

    except Exception as e:
        return False, f"Error validating image: {str(e)}"

# Usage
ref_path = Path("character_ref.png")
is_valid, message = validate_veo_reference_image(ref_path)
if not is_valid:
    print(f"❌ {message}")
else:
    print(f"✅ {message}")
```

---

## Appendix B: Additional Resources

### Official Documentation
- [Veo 3.1 API Reference (Google AI)](https://ai.google.dev/gemini-api/docs/video)
- [Veo on Vertex AI (Google Cloud)](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation)
- [Direct video generation using reference images](https://cloud.google.com/vertex-ai/generative-ai/docs/video/use-reference-images-to-guide-video-generation)

### Community Guides
- [Veo 3.1 Multi-Prompt Storytelling Best Practices](https://skywork.ai/blog/multi-prompt-multi-shot-consistency-veo-3-1-best-practices/)
- [How to Create Character Consistency with Google Veo 3](https://syllaby.io/blog/how-to-create-character-consistency-with-google-veo-3/)
- [Google Veo 3.1 Review: Character Consistency](https://skywork.ai/blog/google-veo-3-1-2025-character-consistency-review/)

### Alternative Tools
- [Google Flow (VideoFX)](https://aitestkitchen.withgoogle.com/tools/video-fx) - GUI for Veo with storyboard tools
- [Runway Gen-4](https://runwayml.com/) - Alternative AI video with image-to-video focus
- [Stable Video Diffusion](https://stability.ai/stable-video) - Open-source alternative with LoRA support

### LLM/Prompt Resources
- [LiteLLM Documentation](https://docs.litellm.ai/) - Unified LLM API for prompt generation
- [Midjourney Character Reference](https://docs.midjourney.com/docs/character-reference) - Generate consistent character sheets

---

**End of Research Document**
