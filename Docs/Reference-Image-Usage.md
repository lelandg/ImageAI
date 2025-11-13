# Reference Image Usage Guide

This document explains how to use reference images with different providers in ImageAI.

## Overview

Reference images allow you to guide image generation by providing an example image whose style, composition, or characteristics you want to replicate. Each provider handles reference images differently based on their API capabilities.

## Supported Providers

### ✅ Stability AI (Native Support)
**Implementation**: Image-to-image (img2img) API

Stability AI has full native support for reference images through their img2img endpoint.

**Usage**:
```python
provider = get_provider("stability", config)

# Generate with reference image
texts, images = provider.generate(
    prompt="A futuristic cityscape",
    reference_image="/path/to/reference.png",  # Can be Path, str, or bytes
    reference_strength=0.5,  # 0.0 = ignore reference, 1.0 = follow closely
    model="stable-diffusion-xl-1024-v1-0"
)
```

**Parameters**:
- `reference_image`: Path to image file, or raw bytes
- `reference_strength`: Float 0.0-1.0 (default: 0.5)
  - **0.3-0.4**: Close to reference, minor variations
  - **0.5**: Balanced between reference and prompt
  - **0.7-0.8**: More creative interpretation
  - **Note**: Stability API uses inverted strength internally

**How it works**: Stability's img2img API takes the reference image and modifies it according to your prompt, controlled by the strength parameter.

---

### ❌ OpenAI (Not Supported)
**Status**: No reference image support

OpenAI's DALL-E 3 only supports text-to-image generation and does not support reference images. DALL-E 2 supports `edit_image()` for editing existing images, but not as style/composition references for new generation.

**Alternative approaches**:
- Use the Reference Image Dialog to analyze an image with vision API and manually copy the description
- Use DALL-E 2's `create_variations()` method to create variations of an existing image
- Switch to Stability AI or Google Imagen providers for reference image support

---

### ✅ Google Gemini/Imagen (Native Support)
**Implementation**: Native reference image API

Google has the most advanced native reference image support through Imagen's customization API.

**Note**: Already fully implemented in `imagen_customization.py`. Not modified per user request.

**Usage**: See `imagen_customization.py` → `generate_with_references()` method

**Features**:
- Multiple reference images simultaneously
- Per-reference strength control
- Advanced subject/style extraction

---

## Code Examples

### Basic Usage Pattern
```python
from providers import get_provider

# Initialize provider
config = {"api_key": "your-api-key"}
provider = get_provider("stability", config)

# Load reference image (multiple ways)
reference = "/path/to/image.png"  # Path as string
# or
reference = Path("/path/to/image.png")  # Path object
# or
with open("/path/to/image.png", "rb") as f:
    reference = f.read()  # Raw bytes

# Generate with reference
texts, images = provider.generate(
    prompt="Your creative prompt here",
    reference_image=reference,
    reference_strength=0.5
)

# Save results
for i, img_bytes in enumerate(images):
    with open(f"output_{i}.png", "wb") as f:
        f.write(img_bytes)
```

### Checking Provider Support
```python
provider = get_provider("stability", config)

# Check if reference images are supported
if provider.supports_feature("reference_image"):
    print("✅ Reference images supported")
    texts, images = provider.generate(
        prompt="...",
        reference_image="reference.png"
    )
else:
    print("❌ Reference images not supported")
    # For OpenAI, use variations or edit_image instead
    texts, images = provider.generate(prompt="...")
```

## Best Practices

### Strength Parameter Guidelines

**For Stability AI**:
- **0.2-0.3**: Very close to reference, minimal changes
- **0.4-0.5**: Balanced blend of reference and prompt (recommended starting point)
- **0.6-0.7**: More creative, loosely inspired by reference
- **0.8-0.9**: Highly creative, reference used as loose guide

### Prompt Writing with References

**Good practices**:
- Keep prompts focused on what to change/add, not what to keep
- Mention style differences if you want them ("...but in watercolor style")
- Be specific about desired changes ("add a sunset", "change to winter season")

**Example**:
```python
# Good: Focused on changes
prompt = "Transform to autumn season with falling leaves and warm lighting"

# Less effective: Describing what's already in reference
prompt = "A forest scene with trees" # Reference already shows this
```

### Reference Image Quality

- **Resolution**: Higher quality references yield better results
- **Clarity**: Avoid blurry or low-resolution references
- **Relevance**: Reference should relate to your desired output

## API Cost Considerations

### Stability AI
- **Community License**: Free for businesses < $1M revenue
- **Paid plans**: Variable pricing based on API tier
- **No extra cost**: img2img same price as text-to-image

### OpenAI
- **Reference images not supported**: DALL-E does not support reference images
- **DALL-E 3 generation**: ~$0.04-0.12 per image (text-to-image only)

## Implementation Details

### Base Provider Interface

The base `ImageProvider` class includes helper method:

```python
def _load_reference_image(self, reference_image) -> Optional[bytes]:
    """Load reference image from path or bytes."""
```

All providers can use this helper to standardize reference image loading.

### Provider-Specific Implementation

**Stability AI** (`providers/stability.py`):
- Intercepts `reference_image` in `generate()`
- Redirects to `edit_image()` with appropriate strength
- Uses img2img API endpoint

**OpenAI** (`providers/openai.py`):
- Does not support reference images in `generate()`
- Use `create_variations()` for image variations
- Use `edit_image()` for image editing (DALL-E 2 only)

## Troubleshooting

### "Reference image not supported" error
- Check provider with `supports_feature("reference_image")`
- Currently supported: Stability AI, Google Imagen
- Not supported: OpenAI, Local SD, Ollama, Midjourney

### Stability: "Image dimensions invalid"
- Stability resizes automatically based on model
- SDXL: Resized to 1024x1024 if needed
- SD 1.x/2.x: Resized to 512x512 or 768x768

## Future Enhancements

Potential improvements for future versions:
- Local SD reference image support via img2img
- Reference image caching for faster loading
- UI integration for drag-and-drop reference images
- Batch processing with reference images

---

*Last Updated: 2025-11-13*
