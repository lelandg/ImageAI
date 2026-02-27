# Image Generation

## Overview

ImageAI lets you generate AI images from text prompts using a choice of cloud and local AI providers. You control every aspect of the output — size, style, number of variations — through a clean desktop interface or from the command line.

## Features

### Choosing a Provider and Model

Select your preferred AI provider from the dropdown at the top of the Generate tab. Models update automatically based on your selection.

Supported providers and their notable models:

| Provider | Models Available |
|----------|-----------------|
| Google Gemini | Gemini 2.5 Flash Image, Nano Banana Pro (4K) |
| OpenAI DALL-E | GPT Image 1.5, DALL-E 3, DALL-E 2 |
| Stability AI | Stable Diffusion XL, SD 2.1, and more |
| Local Stable Diffusion | Any locally installed model (GPU recommended) |
| Midjourney | Midjourney generation via integration |
| Ollama | Local models via Ollama server |

### Writing Your Prompt

Type or paste your prompt in the multi-line text box. The prompt field supports Ctrl+F to search within a long prompt.

Tips:
- Be descriptive — include subject, style, lighting, and mood.
- Use the Prompt Builder (see separate guide) for structured prompts.
- Use Enhance Prompt (one click) to let AI improve your text automatically.

### Aspect Ratio and Resolution

Click the aspect ratio buttons to set your output shape visually:

| Button | Ratio | Best for |
|--------|-------|---------|
| 1:1 | Square | Profile pictures, icons |
| 3:4 | Portrait | Phone wallpapers |
| 4:3 | Landscape | Presentations |
| 16:9 | Widescreen | YouTube thumbnails |
| 9:16 | Vertical video | Reels, TikTok |
| 21:9 | Ultrawide | Cinematic banners |

You can also type a custom ratio ("16:10") or a decimal ("1.6") in the custom ratio field.

Toggle to Resolution Mode to set exact pixel dimensions directly (e.g., 1024x768).

### Generating Multiple Variations

Set the count field to 1, 2, 3, or 4 to generate that many images in one batch. Each image is saved automatically and appears in History.

### Cost Estimation

Before clicking Generate, the estimated API cost appears below the prompt. This updates as you change provider, model, resolution, and count.

### Advanced Controls

Available for providers that support them (Stability AI, local SD):

| Control | What It Does | Range |
|---------|-------------|-------|
| Inference Steps | More steps = higher quality but slower | 1–50 |
| Guidance Scale (CFG) | How strictly to follow the prompt | 0–20 |
| Seed | Enter a number for reproducible results | Any integer |
| Negative Prompt | Describe what to exclude from the image | Free text |
| Prompt Rewriting | AI rewrites your prompt for better results | Toggle on/off |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+Enter | Generate (works from anywhere in the Generate tab) |
| Ctrl+S | Save the generated image |
| Ctrl+Shift+C | Copy image to clipboard |
| Ctrl+N | Start a new generation |

## Common Questions

**Q: Why is the Generate button greyed out?**
You need a valid API key configured in Settings, and a prompt entered.

**Q: How do I reproduce an image I generated before?**
Enter the same seed number from the History entry. Double-click any history row to reload all settings including the seed.

**Q: Can I use ImageAI offline?**
Yes — select the Local Stable Diffusion or Ollama provider. These run entirely on your computer without an internet connection (GPU strongly recommended for speed).

**Q: My Stability AI/OpenAI models are not listed — why?**
Check that your API key is saved in Settings and is valid. The model list is populated after a successful key check.
