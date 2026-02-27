# History, Settings, and Upscaling

## Overview

ImageAI tracks every image and video you generate in History, stores your configuration in Settings, and provides AI-powered upscaling to enhance resolution — all in one place.

## Features

### Generation History

The History tab shows a complete record of every image you have generated.

**What is stored per entry:**
- Thumbnail preview
- Date and time generated
- Provider and model used
- The full prompt
- Output resolution
- Estimated API cost
- Reference image indicator (hover for a tooltip showing linked files)

**Browsing and finding images:**

| Action | How to Do It |
|--------|-------------|
| Preview an image | Hover over a row |
| Open full image | Click the thumbnail |
| Reload all settings | Double-click any row |
| Filter by provider | Use the Provider dropdown |
| Search by prompt | Type in the Search field |
| Sort | Click a column header (date, cost, model) |

**Double-clicking a history entry** loads the original prompt, provider, model, aspect ratio, seed, and all other settings back into the Generate tab — ready to regenerate or refine.

Each generated image also has a JSON sidecar file saved alongside it containing complete metadata. These sidecar files power the double-click reload feature.

### Settings

Access Settings from the Settings tab or the menu.

**Provider & Authentication:**

| Setting | Description |
|---------|-------------|
| Active Provider | Which AI provider to use for image generation |
| API Key | Enter and save your key for each provider |
| Auth Mode | API Key (default) or Google Cloud ADC |
| LLM Provider | Provider used for prompt tools (can differ from image provider) |

**Google Cloud ADC (Application Default Credentials):**
For organizations using Google Cloud, enable ADC in Settings to authenticate without entering an API key. Run `gcloud auth application-default login` once in a terminal, and ImageAI will use your Google identity automatically.

**Output Options:**

| Setting | Default | Description |
|---------|---------|-------------|
| Auto-save | On | Automatically save every generated image |
| Output Directory | ~/ImageAI/generated | Where files are saved |
| Copy Filename | Off | Copy the file path to clipboard after each save |
| Image Format | PNG | Output format: PNG, JPEG, or WebP |

**Discord Rich Presence:**

Show your ImageAI activity in your Discord status:

| Privacy Level | What Discord Shows |
|--------------|-------------------|
| Full | Provider name, model, elapsed time |
| Activity Only | "Using ImageAI" without model details |
| Minimal | Just "Active" |

Enable/disable from Settings. ImageAI handles gracefully if Discord is not running.

**Secure Credential Storage:**
API keys are stored in platform-specific secure storage, not in plain text config files:
- Windows: `%APPDATA%\ImageAI\`
- macOS: `~/Library/Application Support/ImageAI/`
- Linux: `~/.config/ImageAI/`

### AI Image Upscaling

Enhance the resolution of any generated or imported image using AI.

**Real-ESRGAN upscaling:**
- Trained specifically on photorealistic images — produces sharper results than traditional algorithms.
- NVIDIA GPU acceleration is detected and used automatically when available.
- CPU fallback available on systems without a GPU (slower).

**Install upscaling:**
The upscaling model is not installed by default. Click Install in the Upscaling section and ImageAI handles the download.

**How to upscale:**
1. Select any image in History (or drag an image into the Upscaling panel).
2. Choose the upscale factor (2x or 4x).
3. Click Upscale.
4. The upscaled image is saved alongside the original with a `_4x` or `_2x` suffix.

**Additional upscaling methods available:**
- Lanczos — fast, high-quality traditional algorithm; no AI model needed.
- Cloud services — if you have a subscription to an upscaling cloud service, configure it in Settings.

## Common Questions

**Q: How do I find an image I generated last week?**
Open the History tab and sort by date (click the Date column header) or use the search field to search by any word from the original prompt.

**Q: My API key is saved but the app keeps asking for it. What is wrong?**
Secure storage uses the OS keychain. If your keychain is locked or your user permissions have changed, re-enter the key in Settings and save again.

**Q: Can I change the default output folder?**
Yes — in Settings, click the folder icon next to Output Directory and choose a new path. All future generations save there.

**Q: Does upscaling work on any image, not just ImageAI-generated ones?**
Yes — you can drag any PNG or JPEG into the Upscaling panel.

**Q: Real-ESRGAN upscaling is very slow on my computer. Why?**
Without an NVIDIA GPU, upscaling runs on the CPU and can take several minutes per image. A supported NVIDIA GPU (GTX 1060 or newer) reduces this to seconds.
