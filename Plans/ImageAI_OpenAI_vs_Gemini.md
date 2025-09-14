# Image Generation API Comparison: OpenAI GPT vs Google Gemini

This document compares **OpenAI GPT Image API** (`gpt-image-1`) and **Google Gemini Image Generation API**, highlighting features, differences, and how ImageAI can implement them.

---

## Core Features

| Feature | OpenAI GPT Image API | Google Gemini Image Generation API |
|---------|----------------------|------------------------------------|
| **Models** | `gpt-image-1` | `gemini-2.0-flash`, `imagen-3.0` (depending on region & access) |
| **Base Sizes** | 1024×1024, 1536×1024, 1024×1536 | Arbitrary sizes supported (e.g., 512×512, 768×1024) |
| **Transparency** | PNG/WEBP with alpha (`background="transparent"`) | Supported via PNG with alpha |
| **Formats** | PNG, JPEG, WEBP | PNG, JPEG, WEBP |
| **Compression** | `output_compression` (JPEG/WEBP) | `mimeType` + quality options |
| **Quality Levels** | `low | medium | high | auto` | `quality: draft | standard | high` |
| **Prompting** | Text prompt | Text prompt + negative prompt |
| **Edits / Masking** | Supported (`images.edit`) with alpha mask | Supported (`mask` param, alpha channel) |
| **Seed Control** | `seed` param (not guaranteed stable) | `seed` param (better determinism in Imagen) |
| **Multiple Outputs** | `n` parameter (default 1) | `n` parameter (default 1) |
| **Cost** | Per image generated, higher for quality | Generally cheaper for draft quality, scales with resolution |

---

## Implementation in ImageAI

### 1. Provider Layer (`providers/google.py`)
- Add wrapper for Gemini endpoint:
```python
from google import genai

client = genai.Client()

def generate_gemini_image(prompt, sizes=[(512,512)], transparent=False, quality="high", seed=None, fmt="png"):
    results = []
    for w,h in sizes:
        resp = client.models.generate_images(
            model="imagen-3.0",
            prompt=prompt,
            negativePrompt=None,
            size=f"{w}x{h}",
            mimeType=f"image/{fmt}",
            quality=quality,
            seed=seed
        )
        for img in resp.images:
            results.append(((w,h), img.data))
    return results
```

### 2. Base Provider Interface (`providers/base.py`)
```python
supports = {
  "exact_export_sizes": True,   # Gemini supports arbitrary size directly
  "transparent_output": True,
  "seed": True,
  "edits": True,
  "masking": True,
  "negative_prompt": True       # New vs OpenAI
}
```

### 3. GUI / CLI Extensions
- **Negative Prompt Field**: Add textbox for "avoid these elements".
- **Quality Dropdown**: `draft | standard | high` for Gemini.
- **Direct Sizes**: Allow any WxH instead of snapping to OpenAI base sizes.

---

## Key Differences
1. **Size Handling**  
   - GPT: must snap to 1024 or 1536 base sizes → resize afterwards.  
   - Gemini: can request arbitrary sizes directly.

2. **Negative Prompts**  
   - Gemini natively supports `negativePrompt`.  
   - GPT requires rewriting prompt text manually.

3. **Seed Stability**  
   - Gemini’s Imagen offers more consistent seeding than GPT.  
   - Good for continuity in videos/scenes.

4. **Quality Tiers**  
   - Both support multiple quality levels. Gemini explicitly supports `draft`, useful for quick iterations.

---

## Suggested Enhancements for ImageAI
- Add **negative prompt support** (Gemini only).  
- Bypass resizing for Gemini (export exact size directly).  
- Add a **“quick draft” mode** for Gemini (`quality=draft`).  
- Offer **cross-provider fallback**: if Gemini unavailable, fall back to OpenAI.  
- Allow per-scene **seed locking** to improve continuity.  
- Enable **multi-output** (`n > 1`) for user review and batch export.

---

## Example CLI Usage

```
# OpenAI
imageai --provider openai --prompt "logo of a phoenix" --sizes 256,512 --transparent --fmt png --seed 123

# Gemini
imageai --provider google --prompt "logo of a phoenix" --sizes 256x256,512x512 --transparent --fmt png --seed 123 --negative "realistic photo" --quality draft
```

---

## Conclusion
- **OpenAI GPT Image API** is better for controlled prompts, transparency, and consistent output with resizing.  
- **Google Gemini API** is better for **arbitrary resolutions**, **negative prompts**, and **faster draft-quality iterations**.  
- Implementing both in ImageAI provides maximum flexibility for end users.
