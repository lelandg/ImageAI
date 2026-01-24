# Character Animator Puppet Creator Guide

> Transform any character image into an animatable Adobe Character Animator puppet with AI-powered facial features.

## Overview

The Character Animator Puppet Creator is a wizard-based tool that converts a static character image into a fully rigged puppet compatible with Adobe Character Animator. Using cloud AI services (Google Gemini or OpenAI), it automatically generates:

- **14 Mouth Visemes** - Lip-sync mouth shapes for natural speech animation
- **Eye Blink States** - Open and closed positions for each eye
- **Body Part Layers** - Properly named and organized layer structure

## Quick Start

1. Open ImageAI and go to **Tools > Character Animator Puppet Creator**
2. Follow the wizard steps (dependency check happens automatically on first use)
3. Select a front-facing character image
4. Review detected body parts
5. Generate visemes with your preferred AI provider
6. Export to PSD or SVG

## Wizard Steps

### Step 1: Dependency Check

On first use, the wizard checks for required AI components:

| Component | Purpose | Size |
|-----------|---------|------|
| SAM 2 Segmentation | Body part detection | ~2GB |
| MediaPipe Pose/Face | Facial landmark detection | ~100MB |
| Cloud AI (Gemini/OpenAI) | Viseme generation | API-based |
| PSD Export | Photoshop format output | ~50MB |
| SVG Export | Vector format output | ~10MB |

Click **Install AI Components** to download and install missing components. Total download is approximately 8-12GB.

### Step 2: Image Selection

Select your source character image. For best results:

- **Front-facing** - Character should face the camera directly
- **Clear features** - Eyes and mouth should be clearly visible
- **Good lighting** - Even illumination without harsh shadows
- **Minimum size** - 1024x1024 pixels recommended
- **Supported formats** - PNG, JPEG, WebP, BMP

The preview shows your selected image with dimension information.

### Step 3: Body Part Detection

The AI analyzes your image to detect:

**Body Parts:**
- Head (with facial features)
- Torso
- Left Arm
- Right Arm

**Facial Features:**
- Left Eye / Right Eye
- Mouth region
- Left Eyebrow / Right Eyebrow

The results panel shows a checklist of detected components with bounding box overlays on the image. Click **Re-detect** if initial detection needs adjustment.

### Step 4: Viseme Generation

This step uses cloud AI to generate facial variations.

**Provider Selection:**
- **Google Gemini** - gemini-2.5-flash-image (fast, $0.039/img) or gemini-3-pro-image-preview (quality, $0.10/img)
- **OpenAI** - gpt-image-1 (standard, $0.08/img) or gpt-image-1.5 (quality, $0.12/img)

**Generation Options:**
- **14 Mouth Visemes** - Required for lip-sync (enabled by default)
- **Eye Blink States** - 2 images per eye (enabled by default)
- **Eyebrow Variants** - 6 optional expression images
- **Force Regenerate** - Bypass cache for fresh results

**Cost Estimate:**
The wizard calculates estimated cost based on provider and options. Typical cost for visemes + blinks is $0.50-$2.00.

Click **Start Generation** to begin. Progress shows each viseme as it's generated.

### Step 5: Export

Configure and save your puppet:

**Puppet Name:** Enter a name for your character (used in file name and layer structure).

**Export Format:**
- **PSD (Photoshop)** - Best for photorealistic characters, preserves layer hierarchy
- **SVG (Vector)** - Best for cartoon/flat styles, groups map to layers
- **Both formats** - Export to both formats simultaneously

**Output Location:** Choose where to save the exported file(s).

Click **Export Puppet** to save. The wizard confirms success with file path(s).

## The 14 Visemes

Character Animator uses these mouth shapes for automatic lip-sync:

| Viseme | Phonemes | Description |
|--------|----------|-------------|
| Neutral | Rest | Resting/closed mouth |
| Ah | A, AI, AU | Open mouth |
| D | D, T, N, TH | Tongue behind teeth |
| Ee | E, EE | Wide smile |
| F | F, V | Lower lip under teeth |
| L | L | Tongue up |
| M | M, B, P | Closed lips |
| Oh | O, OO | Rounded open |
| R | R | Slightly rounded |
| S | S, Z, SH, CH | Teeth together |
| Uh | U, UH | Slightly open |
| W-Oo | W, OO, Q | Pursed lips |
| Smile | Expression | Camera-driven |
| Surprised | Expression | Camera-driven |

## Layer Structure

The exported puppet follows Adobe's naming conventions:

```
+[CharacterName]
├── Body
│   ├── Torso
│   ├── Left Arm
│   └── Right Arm
└── Head
    ├── +Left Eyebrow
    ├── +Right Eyebrow
    ├── Left Eye
    │   ├── Left Pupil Range
    │   └── +Left Pupil
    ├── Right Eye
    │   ├── Right Pupil Range
    │   └── +Right Pupil
    ├── Left Blink
    ├── Right Blink
    └── Mouth
        ├── Neutral
        ├── Ah, D, Ee, F, L, M, Oh, R, S, Uh, W-Oo
        ├── Smile
        └── Surprised
```

The `+` prefix indicates layers that warp independently in Character Animator.

## Caching

Generated visemes are cached locally to avoid redundant API calls. The cache key is based on:
- Source image hash
- Provider and model
- Generation settings

Use **Force Regenerate** checkbox to bypass the cache and generate fresh results.

## Troubleshooting

### Detection Failed
- Ensure the character face is clearly visible
- Try a different image angle (front-facing works best)
- Check that lighting is even without harsh shadows

### API Key Errors
- Verify your API key in Settings tab
- Google: Requires valid Gemini API key
- OpenAI: Requires valid OpenAI API key with image generation access

### Rate Limit Errors
- Wait a few minutes and retry
- Consider switching to the other provider
- Reduce the number of optional features (eyebrows)

### Export Issues
- Ensure output directory is writable
- Check available disk space
- Try a different export format

## Tips for Best Results

1. **Use high-resolution images** - At least 1024x1024 pixels
2. **Keep faces centered** - The face should be clearly visible in frame
3. **Avoid complex backgrounds** - Simple or solid backgrounds work best
4. **Use consistent lighting** - Even lighting helps AI detection
5. **Start with Gemini Flash** - Fastest and most cost-effective for initial testing
6. **Preview before full generation** - Check body part detection before generating visemes

## Related Documentation

- [ImageAI Features](ImageAI_Features.md)
- [Video Tab Guide](Video-Tab-Guide.md)

---

*Part of ImageAI v0.32.0 | [GitHub Repository](https://github.com/lelandg/ImageAI)*
