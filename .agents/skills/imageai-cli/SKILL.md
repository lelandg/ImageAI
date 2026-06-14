---
name: imageai-cli
description: Use when generating, editing, batching, or scripting images with the ImageAI CLI (`python main.py ...`) from inside the ImageAI repo, across any provider — Google Gemini / Nano Banana, OpenAI (gpt-image-2/1.5/1, DALL·E), Stability AI, or local Stable Diffusion. Covers model selection, sizing/aspect, references & masks, streaming, Batch API, lyrics-to-prompts, gcloud auth, and key management. Trigger whenever the user wants to make or edit an image (or set up/test a provider key) from the command line in this working directory.
---

# imageai-cli

The cheat-sheet for driving **everything** the ImageAI CLI can do from
`python main.py`. Four image providers, the lyrics-to-prompts pipeline, the
OpenAI Batch API, and key/auth management — all from one entry point.

> GUI is the default when no action flag is given. Add `--gui` to force it, or
> pass `-p/--prompt`, `-t/--test`, `-s/--set-key`, or `--lyrics-to-prompts` to
> stay in the CLI.

## Pick a provider first

| Provider        | `--provider` | Auth                          | Best for                                              |
|-----------------|--------------|-------------------------------|-------------------------------------------------------|
| Google Gemini   | `google` (default) | API key **or** `gcloud` ADC | Nano Banana family; fast, high-quality, up to 4K (NBP) |
| OpenAI          | `openai`     | API key                       | gpt-image-2 "thinking" model, DALL·E 3                 |
| Stability AI    | `stability`  | API key (hosted)              | SDXL / SD hosted endpoints                             |
| Local SD        | `local_sd`   | none (local GPU/CPU)          | offline generation, no per-image cost                  |

Default provider is **google**, default model **`gemini-2.5-flash-image`**.

## Universal invocation

```bash
# Minimal: default provider/model, auto-named output in the images dir
python main.py -p "a red fox in snow"

# Explicit provider + model + output path
python main.py --provider <prov> -m <model> -p "your prompt" -o out.png

# N images in one call
python main.py --provider openai -m gpt-image-2 -n 4 -p "logo ideas" -o logo.png
```

`-o/--out` is optional — without it, images auto-save with a sanitized,
prompt-derived filename under the platform images dir. Each image gets a `.json`
metadata sidecar.

---

## Google Gemini (Nano Banana)

| Model                              | Alias            | Max output |
|------------------------------------|------------------|------------|
| `gemini-3-pro-image-preview`       | Nano Banana Pro  | 4K         |
| `gemini-3.1-flash-image-preview`   | Nano Banana 2    | 2K         |
| `gemini-2.5-flash-image` (default) | Nano Banana      | 1024px     |

```bash
# Default Nano Banana
python main.py -p "watercolor harbor at dawn" -o harbor.png

# Nano Banana Pro at 16:9 (provider maps --size to an aspect ratio)
python main.py -m gemini-3-pro-image-preview --size 1920x1080 \
    -p "cinematic desert highway" -o road.png

# gcloud Application Default Credentials instead of an API key
python main.py --auth-mode gcloud -p "..." -o out.png
```

- **Aspect ratio, not pixels in the prompt.** Set sizing via `--size`; the
  provider converts to an aspect ratio (`image_config`). Never bake dimensions
  like "(1024x768)" into prompt text — Gemini renders them as literal text.
- **Supported aspect ratios:** 1:1, 3:2, 2:3, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9.
- **Scaling:** NB caps at 1024px; the app scales proportionally (max edge 1024)
  then upscales. NB2 → 2K native, NBP → 4K native.
- **gcloud auth** (`--auth-mode gcloud`) works for the Gemini image models with
  no API key; run `gcloud auth application-default login` first.
- Operations: **generate**, **edit**, **compose** (pass `--reference` for edit/compose).

## OpenAI

| Model            | Notes                                                            |
|------------------|------------------------------------------------------------------|
| `gpt-image-2`    | "Thinking" model — `--quality` drives reasoning. Best quality.   |
| `gpt-image-1.5`  | Latest non-thinking; supports `--output-format`.                 |
| `gpt-image-1`    | Prior gen.                                                        |
| `gpt-image-1-mini` | Fast/cheap.                                                     |
| `dall-e-3`       | `--quality standard|hd`, fixed size presets, `style` (legacy).   |
| `dall-e-2`       | Legacy.                                                          |

```bash
# gpt-image-2, explicit reasoning
python main.py --provider openai -m gpt-image-2 --quality high \
    -p "complex composition with legible text" -o gen.png

# DALL·E 3 in HD
python main.py --provider openai -m dall-e-3 --quality hd \
    -p "isometric city" -o city.png
```

See the **gpt-image-2 deep-dive** below for custom sizes, masks, streaming,
and batch — it has the most surface area.

## Stability AI (hosted)

| Model                            | Label              |
|----------------------------------|--------------------|
| `stable-diffusion-xl-1024-v1-0` (default) | SDXL 1.0  |
| `stable-diffusion-xl-beta-v2-2-2`| SDXL Beta          |
| `stable-diffusion-512-v2-1`      | SD 2.1             |
| `stable-diffusion-v1-6`          | SD 1.6             |

```bash
python main.py --provider stability -m stable-diffusion-xl-1024-v1-0 \
    -p "fantasy castle, concept art" -o castle.png
```

Needs a Stability API key (`--provider stability -s` to store one; `-t` to test).

## Local Stable Diffusion (offline)

| Model                                    | Label            |
|------------------------------------------|------------------|
| `stabilityai/stable-diffusion-xl-base-1.0` | SDXL Base 1.0  |
| `segmind/SSD-1B`                         | SSD-1B (Fast SDXL) |
| `stabilityai/stable-diffusion-2-1` (default) | SD 2.1       |
| `runwayml/stable-diffusion-v1-5`         | SD 1.5           |
| `CompVis/stable-diffusion-v1-4`          | SD 1.4           |

```bash
python main.py --provider local_sd -m segmind/SSD-1B \
    -p "studio portrait, soft light" -o portrait.png
```

- No API key. First run **downloads weights from Hugging Face** (slow, large).
- Uses GPU (CUDA / Apple MPS) when available, falls back to CPU (slow).
- Requires the local-SD extras (`torch`, `diffusers`) to be installed; if they're
  missing, tell the user what to install rather than installing it yourself.

---

## gpt-image-2 deep-dive

ImageAI ships first-class support for OpenAI's `gpt-image-2` (released 2026-04-21).

```bash
# Custom size (edges multiples of 16, max 3840, aspect ≤3:1, pixels 655K-8.3M)
python main.py --provider openai -m gpt-image-2 \
    --custom-size 2048x1152 -p "ultrawide wallpaper" -o gen.png

# Multi-reference compose (up to 10 images) → /v1/images/edits
python main.py --provider openai -m gpt-image-2 \
    --reference ref/a.png --reference ref/b.png \
    -p "combine these styles" -o composed.png

# Mask inpainting (transparent pixels in mask = edit zone)
python main.py --provider openai -m gpt-image-2 \
    --reference base.png --mask mask.png \
    -p "replace the sky with stormy clouds" -o edited.png

# Streaming partials (writes gen.p0.png, gen.p1.png, then gen.png)
python main.py --provider openai -m gpt-image-2 \
    --stream-partials --quality high \
    -p "intricate technical diagram" -o gen.png

# JPEG output with compression
python main.py --provider openai -m gpt-image-2 \
    --output-format jpeg --output-compression 85 \
    -p "photorealistic landscape" -o landscape.jpg

# Permissive moderation
python main.py --provider openai -m gpt-image-2 --moderation low -p "..." -o gen.png
```

### Cost estimator (1024×1024)

| Quality | Per image | At n=10 |
|---------|-----------|---------|
| low     | ~$0.006   | ~$0.06  |
| medium  | ~$0.053   | ~$0.53  |
| high    | ~$0.211   | ~$2.11  |
| Batch   | 50% off all of the above |

Costs scale with output tokens; custom sizes bigger than 1024² cost more.

### Snapshot pinning

```python
from core.constants import GPT_IMAGE_2_SNAPSHOT  # "gpt-image-2-2026-04-21"
```

Pass the snapshot ID as `-m` when you need bit-for-bit reruns across releases.

---

## Batch API (OpenAI)

```bash
# Submit (50% discount, up to 24h turnaround) — prints a job ID
python main.py --provider openai -m gpt-image-2 --batch -p "your prompt" -o gen.png
# → Submitted batch job: batch_abc123...

python main.py --provider openai --batch-status batch_abc123
python main.py --provider openai --batch-fetch  batch_abc123
```

Jobs are tracked in `~/.imageai/batch_jobs.json` (also surfaced in the GUI's
**Batch Jobs** tab).

## Lyrics → prompts (LLM pipeline)

Turns a lyrics file into a set of image prompts using an LLM (not an image model).

```bash
python main.py --lyrics-to-prompts song.txt \
    --lyrics-model gpt-4o \
    --lyrics-style cinematic \
    --lyrics-temperature 0.7 \
    --lyrics-output prompts.json
```

`--lyrics-model` accepts any LiteLLM id (`gpt-4o`, `gemini/gemini-2.0-flash-exp`,
`Codex-sonnet-4-6`, …). Feed the resulting prompts back into image generation.

## Keys, testing & auth

```bash
# Store a key for the selected provider (interactive)
python main.py --provider openai -s

# Provide a key inline or from a file for a one-off run
python main.py --provider stability -k "$STABILITY_KEY" -p "..." -o out.png
python main.py --provider openai -K /path/to/key.txt -p "..." -o out.png

# Verify the configured key works
python main.py --provider openai -t

# Setup instructions
python main.py --help-api-key
```

Key resolution order: **CLI flag (`-k`/`-K`) > stored config > environment**.
`--auth-mode gcloud` is Google-only and bypasses API keys via ADC.

---

## Full flag reference

| Flag | Values | Notes |
|------|--------|-------|
| `--provider` | `google` \| `openai` \| `stability` \| `local_sd` | Default `google`. |
| `-m`, `--model` | provider model id | See per-provider tables. |
| `-p`, `--prompt` | text | Triggers CLI generation. |
| `-o`, `--out` | path | Optional; auto-named if omitted. |
| `-n`, `--num-images` | int | Default 1. gpt-image-2 up to 10. |
| `--size` | `WxH` or preset | Mutex with `--custom-size`. Google maps to aspect. |
| `--custom-size` | `WxH` | **gpt-image-2 only.** Edges ×16, max 3840, aspect ≤3:1, pixels 655K–8.3M. |
| `--quality` | `auto` \| `low` \| `medium` \| `high` \| `standard` \| `hd` | gpt-image-2: `auto/low/medium/high`; dall-e-3: `standard/hd`. |
| `--output-format` | `png` \| `jpeg` \| `webp` | gpt-image-2 / gpt-image-1.5 only. |
| `--output-compression` | `0..100` | jpeg/webp only. |
| `--moderation` | `auto` \| `low` | gpt-image-2 only; `low` = permissive. |
| `--reference` | path (repeatable ≤10) | Routes to `/v1/images/edits`. |
| `--mask` | PNG path | Alpha mask inpainting; transparent = edit zone. |
| `--stream-partials` | flag | gpt-image-2 only; writes `out.pN.png`. |
| `--batch` / `--batch-status` / `--batch-fetch` | flag / JOB_ID | OpenAI Batch API. |
| `--lyrics-to-prompts` | LYRICS_FILE | Plus `--lyrics-model/-temperature/-style/-output`. |
| `--auth-mode` | `api-key` \| `gcloud` | `gcloud` is Google-only. |
| `-k`/`-K`/`-s`/`-t` | — | Key inline / from file / store / test. |
| `--gui` | flag | Force the GUI. |

## Anti-footguns

- **Provider/model mismatch.** A model id only works with its provider. `dall-e-3`
  needs `--provider openai`; `gemini-*` needs `--provider google` (or default).
- **gpt-image-2 has no transparent background, no `input_fidelity`, no
  variations endpoint, no `style`.** The provider raises clear errors. For alpha
  PNG output use `gpt-image-1.5`/`gpt-image-1`.
- **gpt-image-2 custom-size:** the #1 mistake is non-multiple-of-16 edges. Pre-flight
  validation rejects it; the GUI shows a live red label.
- **gpt-image-2 reasoning is just `--quality`** (`auto/low/medium/high`) — there is no
  separate `reasoning_effort` knob. Higher quality = more thinking compute.
- **Org Verification gate:** gpt-image-2 requires OpenAI Organization Verification.
  If `--provider openai -t` returns a verification message, complete it at
  https://platform.openai.com/settings/organization/general.
- **Google sizing:** never put pixel dimensions in the prompt text; use `--size`.
- **`--quality standard/hd`** are DALL·E values; `--quality auto/low/medium/high`
  are gpt-image-2 values. Don't cross them.
- **local_sd first run** downloads multi-GB weights and may need GPU extras — warn
  the user; don't `pip install` system deps without asking.

## GUI entry points

- **Generate tab** — provider + model pickers; for gpt-image-2 the quality buttons
  flip to `Low | Medium | High | Auto`, and output-format / moderation rows appear.
- **Resolution selector** — "Custom…" opens a W/H dialog with live validation.
- **Generate → Submit as Batch Job…** — submits via the OpenAI Batch API.
- **Batch Jobs tab** — lists jobs from `~/.imageai/batch_jobs.json` with Check/Download.
- **Settings tab** — per-provider API keys and auth mode.
