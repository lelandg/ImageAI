# Google GenAI ImageConfig Error Fix

**Date**: 2025-10-18
**Error**: `module 'google.genai.types' has no attribute 'ImageConfig'`

## Problem

The application is trying to use `types.ImageConfig` to set aspect ratios for Gemini image generation, but this class doesn't exist in older versions of the `google-genai` package.

## Root Cause

- **`ImageConfig` was added in google-genai version 1.39.1** (released September 26, 2025)
- Older versions (1.24.x - 1.26.x) do NOT have `ImageConfig` support
- The code in `providers/google.py:379` uses `types.ImageConfig(aspect_ratio=aspect_ratio)` which fails on older versions

## Solution

Upgrade the `google-genai` package to version 1.39.1 or later:

```powershell
# In PowerShell (the main Python environment)
.\.venv\Scripts\Activate.ps1
pip install --upgrade google-genai
```

Or update `requirements.txt` to pin a minimum version:

```
google-genai>=1.39.1
```

## Verification

After upgrading, check the installed version:

```powershell
pip show google-genai
```

Should show version 1.39.1 or higher.

## Alternative (Temporary Workaround)

If upgrading isn't immediately possible, modify `providers/google.py` to use dictionary-based config instead of types:

```python
# Instead of:
config = types.GenerateContentConfig(
    response_modalities=["IMAGE"],
    image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
    **config_params
)

# Use:
config_dict = {
    "response_modalities": ["IMAGE"],
    "image_config": {"aspect_ratio": aspect_ratio},
    **config_params
}
config = types.GenerateContentConfig(**config_dict)
```

However, this may not work reliably in older versions. **Upgrading is the recommended solution.**

## References

- [Google Developers Blog - Gemini 2.5 Flash Image with Aspect Ratios](https://developers.googleblog.com/en/gemini-2-5-flash-image-now-ready-for-production-with-new-aspect-ratios/)
- [googleapis/python-genai Releases](https://github.com/googleapis/python-genai/releases)
- [Google Gen AI SDK Documentation](https://googleapis.github.io/python-genai/)
