# ImageAI CLI Guide

Everything the ImageAI command line can do — from a one-liner image to scripted,
agent-driven image **and** video generation. All of it runs through a single
entry point: `python main.py`.

This guide is written to be useful to both humans and **autonomous agents**: it
documents every flag, the machine-readable output contracts, exit codes, and a
large section of agent-oriented use cases and recipes at the end.

> **Environment note.** Leland runs the app from PowerShell with `.venv`
> (`python`); agents/WSL use `.venv_linux` (`python3`). Commands below use
> `python main.py`; substitute `python3` in WSL.

---

## Table of contents

- [Quick start](#quick-start)
- [How the entry point decides CLI vs GUI](#how-the-entry-point-decides-cli-vs-gui)
- [Image generation](#image-generation)
  - [Providers at a glance](#providers-at-a-glance)
  - [Google Gemini (Nano Banana)](#google-gemini-nano-banana)
  - [OpenAI](#openai)
  - [Stability AI](#stability-ai-hosted)
  - [Local Stable Diffusion](#local-stable-diffusion-offline)
  - [gpt-image-2 deep dive](#gpt-image-2-deep-dive)
  - [References, composition & masks](#references-composition--masks)
  - [Batch API](#batch-api-openai)
- [Video generation](#video-generation)
- [Lyrics → prompts pipeline](#lyrics--prompts-pipeline)
- [Publication layout engine](#publication-layout-engine)
- [Keys, auth & testing](#keys-auth--testing)
- [Machine-readable output & exit codes](#machine-readable-output--exit-codes)
- [Full flag reference](#full-flag-reference)
- [Anti-footguns](#anti-footguns)
- [Use cases for autonomous & other agents](#use-cases-for-autonomous--other-agents)

---

## Quick start

```bash
# Simplest possible image (default provider google, default model Nano Banana)
python main.py -p "a red fox in snow"

# Pick provider + model + explicit output
python main.py --provider openai -m gpt-image-2 -p "a red fox in snow" -o fox.png

# A single video clip (default video provider: Veo)
python main.py --video -p "a red fox running through snow" -o fox.mp4

# Verify a provider's API key works
python main.py --provider openai -t
```

`-o/--out` is optional for images — without it, files auto-save with a sanitized,
prompt-derived name in the platform images directory. **Every generated image
gets a `.json` metadata sidecar** (prompt + generation details); every generated
video gets one too.

---

## How the entry point decides CLI vs GUI

`python main.py` launches the **GUI by default**. It stays in the **CLI** when
you pass any action flag:

| Trigger | Mode |
|---------|------|
| `-p/--prompt` | CLI image generation |
| `--video` | CLI video generation |
| `-t/--test` | CLI key test |
| `-s/--set-key` | CLI key storage |
| `--lyrics-to-prompts` | CLI lyrics pipeline |
| `--layout-design` / `--layout-fill` / `--layout-export` | CLI layout engine |
| `--gui` | Force the GUI even alongside other flags |
| *(none of the above)* | GUI |

This matters for automation: an agent can always stay headless by supplying an
action flag, and never accidentally block on a window.

---

## Image generation

### Providers at a glance

| Provider | `--provider` | Auth | Best for |
|----------|--------------|------|----------|
| Google Gemini | `google` *(default)* | API key **or** `gcloud` ADC | Nano Banana family; fast, high quality, up to 4K (NBP) |
| OpenAI | `openai` | API key | `gpt-image-2` "thinking" model, DALL·E 3 |
| Stability AI | `stability` | API key (hosted) | SDXL / SD hosted endpoints |
| Local SD | `local_sd` | none (local GPU/CPU) | offline generation, no per-image cost |

Default provider **`google`**, default model **`gemini-2.5-flash-image`**.

```bash
# Provider + model + N images in one call
python main.py --provider openai -m gpt-image-2 -n 4 -p "logo ideas" -o logo.png
```

### Google Gemini (Nano Banana)

| Model | Alias | Max output |
|-------|-------|-----------|
| `gemini-3-pro-image-preview` | Nano Banana Pro | 4K |
| `gemini-3.1-flash-image-preview` | Nano Banana 2 | 2K |
| `gemini-2.5-flash-image` *(default)* | Nano Banana | 1024px |

```bash
# Default Nano Banana
python main.py -p "watercolor harbor at dawn" -o harbor.png

# Nano Banana Pro, 16:9 (the provider maps --size to an aspect ratio)
python main.py -m gemini-3-pro-image-preview --size 1920x1080 \
    -p "cinematic desert highway" -o road.png

# gcloud Application Default Credentials instead of an API key
python main.py --auth-mode gcloud -p "aurora over pines" -o aurora.png
```

- **Aspect ratio, not pixels in the prompt.** Set sizing via `--size`; Gemini
  converts to an aspect ratio internally. Never bake `"(1024x768)"` into the
  prompt — Gemini renders it as literal text in the image.
- **Supported aspect ratios:** `1:1, 3:2, 2:3, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9`.
- **Scaling:** Nano Banana caps at 1024px (app scales max-edge to 1024 then
  upscales); NB2 → 2K native; NBP → 4K native.
- Operations: **generate**, **edit**, **compose** (add `--reference` for the
  latter two).

### OpenAI

| Model | Notes |
|-------|-------|
| `gpt-image-2` | "Thinking" model — `--quality` drives reasoning. Best quality. |
| `gpt-image-1.5` | Latest non-thinking; supports `--output-format`, alpha PNG. |
| `gpt-image-1` | Prior gen. |
| `gpt-image-1-mini` | Fast / cheap. |
| `dall-e-3` | `--quality standard|hd`, fixed size presets. |
| `dall-e-2` | Legacy. |

```bash
# gpt-image-2 with explicit reasoning level
python main.py --provider openai -m gpt-image-2 --quality high \
    -p "complex composition with legible text" -o gen.png

# DALL·E 3 in HD
python main.py --provider openai -m dall-e-3 --quality hd \
    -p "isometric city" -o city.png
```

### Stability AI (hosted)

| Model | Label |
|-------|-------|
| `stable-diffusion-xl-1024-v1-0` *(default)* | SDXL 1.0 |
| `stable-diffusion-xl-beta-v2-2-2` | SDXL Beta |
| `stable-diffusion-512-v2-1` | SD 2.1 |
| `stable-diffusion-v1-6` | SD 1.6 |

```bash
python main.py --provider stability -m stable-diffusion-xl-1024-v1-0 \
    -p "fantasy castle, concept art" -o castle.png
```

### Local Stable Diffusion (offline)

| Model | Label |
|-------|-------|
| `stabilityai/stable-diffusion-xl-base-1.0` | SDXL Base 1.0 |
| `segmind/SSD-1B` | SSD-1B (Fast SDXL) |
| `stabilityai/stable-diffusion-2-1` *(default)* | SD 2.1 |
| `runwayml/stable-diffusion-v1-5` | SD 1.5 |
| `CompVis/stable-diffusion-v1-4` | SD 1.4 |

```bash
python main.py --provider local_sd -m segmind/SSD-1B \
    -p "studio portrait, soft light" -o portrait.png
```

- No API key. **First run downloads multi-GB weights from Hugging Face.**
- Uses CUDA / Apple MPS when available, else CPU (slow).
- Needs local-SD extras (`torch`, `diffusers`). If missing, install them
  deliberately — don't let an automated run silently pull system deps.

### gpt-image-2 deep dive

`gpt-image-2` (released 2026-04-21) has the largest CLI surface.

```bash
# Custom size (edges multiples of 16, max 3840, aspect <=3:1, pixels 655K-8.3M)
python main.py --provider openai -m gpt-image-2 \
    --custom-size 2048x1152 -p "ultrawide wallpaper" -o gen.png

# Streaming partials -> writes gen.p0.png, gen.p1.png, ... then gen.png
python main.py --provider openai -m gpt-image-2 \
    --stream-partials --quality high \
    -p "intricate technical diagram" -o gen.png

# JPEG output with compression
python main.py --provider openai -m gpt-image-2 \
    --output-format jpeg --output-compression 85 \
    -p "photorealistic landscape" -o landscape.jpg

# Permissive moderation
python main.py --provider openai -m gpt-image-2 --moderation low \
    -p "..." -o gen.png
```

**Cost estimator (1024×1024):**

| Quality | Per image | At n=10 |
|---------|-----------|---------|
| low | ~$0.006 | ~$0.06 |
| medium | ~$0.053 | ~$0.53 |
| high | ~$0.211 | ~$2.11 |
| Batch | 50% off all of the above | |

**Snapshot pinning** for reproducible reruns:

```python
from core.constants import GPT_IMAGE_2_SNAPSHOT  # "gpt-image-2-2026-04-21"
```

Pass the snapshot ID as `-m` for bit-for-bit reruns across model releases.

### References, composition & masks

```bash
# Multi-reference compose (up to 10 images) -> /v1/images/edits
python main.py --provider openai -m gpt-image-2 \
    --reference ref/a.png --reference ref/b.png \
    -p "combine these styles" -o composed.png

# Mask inpainting (transparent pixels in the mask = the edit zone)
python main.py --provider openai -m gpt-image-2 \
    --reference base.png --mask mask.png \
    -p "replace the sky with stormy clouds" -o edited.png
```

`--reference` is repeatable (≤10) and routes to the edits endpoint; `--mask`
takes a PNG whose transparent pixels mark where the model may paint. Google
Gemini also supports references for edit/compose.

### Batch API (OpenAI)

```bash
# Submit (50% discount, up to 24h turnaround) -> prints a job ID
python main.py --provider openai -m gpt-image-2 --batch -p "your prompt" -o gen.png
# -> Submitted batch job: batch_abc123...

python main.py --provider openai --batch-status batch_abc123
python main.py --provider openai --batch-fetch  batch_abc123
```

Jobs are tracked in `~/.imageai/batch_jobs.json` (and the GUI's **Batch Jobs** tab).

---

## Video generation

Single-clip video generation, designed to be **agent-friendly** (predictable,
scriptable, machine-readable). Enable it with `--video`; it reuses `-p/--prompt`
and `-o/--out`.

```bash
# Text -> video (Veo is the default video provider)
python main.py --video -p "a fox running through snow" -o fox.mp4

# Gemini Omni, portrait, with audio baked into the output
python main.py --video --video-provider omni --aspect 9:16 \
    -p "neon city at night" -o city.mp4

# Reference images (up to 3 for both providers; 2+ on Omni = subject references)
python main.py --video -p "she walks toward camera" -o walk.mp4 \
    --ref-image style.png --ref-image character.png

# Extend an existing clip (Veo only) — continues from the given video
python main.py --video --extend fox.mp4 -p "the fox leaps over a log" -o fox2.mp4

# Veo frame-to-frame interpolation (end frame)
python main.py --video -p "sunrise timelapse" -o sunrise.mp4 \
    --ref-image start.png --last-frame end.png

# Machine-readable result for agents (exactly one JSON object on stdout)
python main.py --video -p "a fox in snow" -o fox.mp4 --json

# Conversationally refine the previous clip (Omni only; id = operation_id in the sidecar)
python main.py --video --video-provider omni --refine-from int_abc123 \
    -p "make the violin invisible" -o v2.mp4

# Edit your own footage (Omni only; uploads via the Files API first)
python main.py --video --video-provider omni --edit-video input.mp4 \
    -p "make the mirror ripple like liquid" -o edited.mp4

# Large/720p clips: ask for URI delivery (Omni only)
python main.py --video --video-provider omni --delivery uri -p "city timelapse" -o city.mp4
```

### Omni prompt superpowers (in the prompt text, not flags)

- **Image roles**: `<FIRST_FRAME>` (start frame) vs `<IMAGE_REF_N>` (subject refs,
  N=0,1,2); declare with `[# Sources <FIRST_FRAME>@Image1]`.
- **Timing**: natural language ("after 3 seconds, ...") or timecodes
  (`[0-3s] a woman enters`, "every 2s cut to a new angle").
- **Audio direction**: describe music/sound design in the prompt — Omni
  soundtracks every clip by default.
- **On-screen text**: Omni renders readable/animated text ("a neon sign that
  reads OPEN").
- Aspect ratio goes in `--aspect` (16:9 or 9:16), **never** in the prompt.

Omni does **not** support: video extension (`--extend` is Veo-only), video
references > 3s, negative-prompt configs, temperature/system instructions.

### Providers & capabilities

| Capability | Gemini Omni (`omni`) | Veo (`veo`, default) |
|------------|----------------------|----------------------|
| Text → video | ✅ | ✅ |
| Image/reference → video | ✅ (up to 3 refs) | ✅ (≤3 refs) |
| Frame-to-frame interpolation (`--last-frame`) | ❌ | ✅ |
| Extend an existing clip (`--extend`) | ❌ | ✅ (extends run at 720p) |
| Conversational refine (`--refine-from`) | ✅ Omni only | ❌ |
| Edit uploaded video (`--edit-video`) | ✅ Omni only | ❌ |
| URI delivery (`--delivery uri`) | ✅ Omni only | ❌ |
| Audio in output | ✅ | ✅ (Veo 3) |
| Aspect ratios | `16:9`, `9:16` | `16:9`, `9:16`, `1:1` |
| Auth | Google **API key only** | Google API key **or** `--auth-mode gcloud` |

- **Clip length is model-fixed (~8 s).** There is no `--duration` knob by design.
- Both providers authenticate with the **Google** key (same resolution order as
  images). For Veo + ADC: `--auth-mode gcloud` with `GOOGLE_CLOUD_PROJECT` set.
- `--extend`/`--last-frame` require `--video-provider veo` — pairing them with
  `omni` is a clear validation error (exit code 2).
- `--refine-from`/`--edit-video`/`--delivery` require `--video-provider omni` —
  Veo rejects them with a validation error (exit code 2).

### Output & reporting contract

- Writes the `.mp4` to `-o` (or a prompt-derived name if omitted), plus a
  `<output>.json` **sidecar** (prompt, provider, resolved model, aspect,
  status, operation/interaction id, timestamps).
- **Human/progress text always goes to stderr.**
- With `--json`, **stdout carries exactly one JSON object and nothing else**, so
  a parser never trips on log lines:

```json
{
  "status": "completed",
  "output_path": "fox.mp4",
  "provider": "veo",
  "model": "veo-3.1-generate-001",
  "aspect_ratio": "16:9",
  "operation_id": "operations/abc123",
  "error": null
}
```

---

## Lyrics → prompts pipeline

Turns a lyrics file into a set of image prompts using an **LLM** (not an image
model). Feed the results back into image generation.

```bash
python main.py --lyrics-to-prompts song.txt \
    --lyrics-model gpt-4o \
    --lyrics-style cinematic \
    --lyrics-temperature 0.7 \
    --lyrics-output prompts.json
```

`--lyrics-model` accepts any LiteLLM id (`gpt-4o`,
`gemini/gemini-2.0-flash-exp`, `claude-sonnet-4-6`, …).

---

## Publication layout engine

The CLI also drives ImageAI's publication layout engine (design a page from a
description, fill regions, export to PDF/PNG):

```bash
# Design a layout project (.json) from a text description
python main.py --layout-design "3-panel comic, action scene" -o comic.json \
    --content-kind comic --page-size "US Comic" --orientation portrait --dpi 300

# Fill a layout's regions with generated images
python main.py --layout-fill comic.json

# Export to PDF or PNG (extension decides the format)
python main.py --layout-export comic.json -o comic.pdf
```

Text-LLM provider/model for `--layout-design` are overridable with
`--layout-llm-provider` / `--layout-llm-model` (default: the configured layout
provider).

---

## Keys, auth & testing

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
`--auth-mode gcloud` is Google-only (images + Veo) and bypasses API keys via ADC
(`gcloud auth application-default login` first).

Environment variables recognized: `GOOGLE_API_KEY` / `GEMINI_API_KEY`,
`OPENAI_API_KEY`, `STABILITY_KEY` / `STABILITY_API_KEY`, and
`GOOGLE_CLOUD_PROJECT` (for Veo + gcloud).

---

## Machine-readable output & exit codes

This is the part that makes the CLI safe to drive from another program.

**Video `--json`:** exactly one JSON object on **stdout**; all diagnostics on
**stderr**. Parse `stdout` directly.

**Video exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Generation failed (provider returned a failure) |
| `2` | User / validation error (bad flags, missing key, unsupported combo) |
| `3` | Unexpected exception |

**Sidecars everywhere.** Images and videos both write a `<output>.json` next to
the artifact — a durable record an agent can read later even without `--json`.

**Logging goes to stderr.** Console diagnostics (warnings/errors) are routed to
stderr specifically so `stdout` stays clean for `--json` consumers.

```bash
# Robust agent pattern: capture JSON, branch on exit code
if out=$(python main.py --video -p "$PROMPT" -o clip.mp4 --json 2>err.log); then
    path=$(printf '%s' "$out" | jq -r .output_path)
    echo "clip at $path"
else
    echo "failed (exit $?):"; cat err.log
fi
```

---

## Full flag reference

### Image / shared

| Flag | Values | Notes |
|------|--------|-------|
| `--provider` | `google` \| `openai` \| `stability` \| `local_sd` | Default `google`. |
| `-m`, `--model` | provider model id | See per-provider tables. |
| `-p`, `--prompt` | text | Triggers CLI image generation. |
| `-o`, `--out` | path | Optional for images; auto-named if omitted. |
| `-n`, `--num-images` | int | Default 1; gpt-image-2 up to 10. |
| `--size` | `WxH` or preset | Mutex with `--custom-size`. Google maps to aspect. |
| `--custom-size` | `WxH` | **gpt-image-2 only.** Edges ×16, max 3840, aspect ≤3:1, pixels 655K–8.3M. |
| `--quality` | `auto\|low\|medium\|high\|standard\|hd` | gpt-image-2: `auto/low/medium/high`; dall-e-3: `standard/hd`. |
| `--output-format` | `png` \| `jpeg` \| `webp` | gpt-image-2 / gpt-image-1.5. |
| `--output-compression` | `0..100` | jpeg/webp only. |
| `--moderation` | `auto` \| `low` | gpt-image-2 only; `low` = permissive. |
| `--reference` | path (repeatable ≤10) | Routes to `/v1/images/edits`. |
| `--mask` | PNG path | Alpha mask inpainting; transparent = edit zone. |
| `--stream-partials` | flag | gpt-image-2 only; writes `out.pN.png`. |
| `--batch` / `--batch-status` / `--batch-fetch` | flag / JOB_ID | OpenAI Batch API. |

### Video

| Flag | Values | Notes |
|------|--------|-------|
| `--video` | flag | Enable video mode (uses `-p`/`-o`). |
| `--video-provider` | `omni` \| `veo` | Default `veo`. |
| `--video-model` | model id | Optional; else the provider's resolved default. |
| `--aspect` | e.g. `16:9`, `9:16` | Validated per provider. |
| `--ref-image` | path (repeatable) | Reference image (repeatable; omni: up to 3, veo: up to 3). |
| `--last-frame` | path | End frame for Veo frame-to-frame interpolation (veo only). |
| `--extend` | path | Extend this existing video (veo only); implies extend mode. |
| `--delivery` | `inline` \| `uri` | Omni only: video delivery ('uri' recommended for large/720p clips). |
| `--refine-from` | INTERACTION_ID | Omni only: conversationally refine a previous generation (interaction id = `operation_id` in the JSON sidecar). |
| `--edit-video` | path | Omni only: upload this video and edit it with the prompt. |
| `--json` | flag | One JSON result object on stdout. |

### Lyrics / layout / keys / auth

| Flag | Values | Notes |
|------|--------|-------|
| `--lyrics-to-prompts` | LYRICS_FILE | Plus `--lyrics-model` / `--lyrics-temperature` / `--lyrics-style` / `--lyrics-output`. |
| `--layout-design` / `--layout-fill` / `--layout-export` | text / project.json / project.json | Layout engine; `--content-kind`, `--page-size`, `--orientation`, `--dpi`, `--layout-llm-provider`, `--layout-llm-model`. |
| `--auth-mode` | `api-key` \| `gcloud` | `gcloud` is Google-only (images + Veo). |
| `-k` / `-K` / `-s` / `-t` | — | Key inline / from file / store / test. |
| `--help-api-key` | flag | Print API-key setup instructions. |
| `--gui` | flag | Force the GUI. |

---

## Anti-footguns

- **Provider/model must match.** `dall-e-3` needs `--provider openai`; `gemini-*`
  needs `--provider google` (or default). Video: `--extend`/`--last-frame` need
  `--video-provider veo`.
- **Google sizing:** never put pixel dimensions in the prompt text; use `--size`.
- **gpt-image-2 custom-size:** the #1 mistake is non-multiple-of-16 edges —
  pre-flight validation rejects it.
- **gpt-image-2 reasoning is just `--quality`** (`auto/low/medium/high`); there is
  no separate reasoning knob. It also has **no** transparent background, no
  `style`, no variations endpoint — use `gpt-image-1.5`/`gpt-image-1` for alpha PNG.
- **Don't cross quality vocabularies:** `standard/hd` = DALL·E; `auto/low/medium/high` = gpt-image-2.
- **gpt-image-2 requires OpenAI Org Verification.** If `-t` reports a verification
  message, complete it in the OpenAI dashboard.
- **Video clip length is fixed (~8 s).** Chain `--extend` for longer results
  (Veo; extensions render at 720p).
- **local_sd first run** downloads multi-GB weights and may need GPU extras.
- **In `--json` mode, read stdout only.** Logs and progress are on stderr by design.

---

## Use cases for autonomous & other agents

The CLI is deliberately headless-friendly: action flags avoid the GUI, `--json`
gives a clean stdout contract, exit codes are meaningful, and every artifact has
a `.json` sidecar. Ideas, from simple to ambitious:

### 1. Deterministic single-shot generation
Give an agent a prompt → get a file path back. Use `--json` for video, or read
the image sidecar for metadata.
```bash
python main.py --video -p "$PROMPT" -o out.mp4 --json | jq -r .output_path
```

### 2. Prompt A/B fan-out and self-selection
Generate `n` variants, then have a vision/LLM step pick the best.
```bash
python main.py --provider openai -m gpt-image-2 -n 6 -p "$PROMPT" -o variant.png
# agent then scores variant*.png and keeps the winner
```

### 3. Cost-aware tiering
An agent can pick quality per budget: draft at `--quality low` (~$0.006), then
re-render only the chosen concept at `--quality high`. Or route bulk jobs through
`--batch` for a 50% discount when latency is acceptable.

### 4. Lyrics/story → storyboard → clips pipeline
Chain the built-in stages: `--lyrics-to-prompts` produces prompts, feed each into
image generation, then animate keyframes with `--video --ref-image`.
```bash
python main.py --lyrics-to-prompts song.txt --lyrics-output prompts.json
# for each prompt: generate a keyframe image, then:
python main.py --video --ref-image key.png -p "$LINE" -o scene.mp4 --json
```

### 5. Reference-consistent character/brand sets
Keep a character or brand style consistent across many images/clips by always
passing the same `--reference`/`--ref-image` set (Veo takes up to 3).

### 6. Iterative video refinement via extend
Build a longer sequence by chaining Veo `--extend`, each step continuing the last
clip — an agent can loop until a target length or a "scene change" cue.
```bash
python main.py --video -p "establishing shot" -o s1.mp4 --json
python main.py --video --extend s1.mp4 -p "camera pushes in" -o s2.mp4 --json
```

### 7. Masked, localized edits
For "change only X" tasks, an agent generates a mask (transparent = edit zone)
and calls `--reference base.png --mask mask.png`. Great for automated retouching
or object replacement.

### 8. Layout-driven publication assembly
Design → fill → export entirely headlessly for comics, one-pagers, or reports:
```bash
python main.py --layout-design "$BRIEF" -o page.json --content-kind magazine
python main.py --layout-fill page.json
python main.py --layout-export page.json -o page.pdf
```

### 9. Long-running batch orchestration
Submit many prompts with `--batch`, persist the returned job IDs, and poll
`--batch-status` / `--batch-fetch` on a schedule. Jobs survive process restarts
via `~/.imageai/batch_jobs.json`, so an agent can resume after a crash.

### 10. Provider fallback / resilience
On failure (non-zero exit or `status:"failed"` in JSON), an agent can retry on a
different provider — e.g. Veo → Omni for video, or gpt-image-2 → Nano Banana Pro
for images — without human intervention.

### 11. Fully offline / air-gapped generation
Use `--provider local_sd` where no API egress is allowed. No keys, no network
after weights are cached — suitable for sandboxed agents.

### 12. Reproducible evaluation harnesses
Pin `gpt-image-2` to its snapshot ID for bit-for-bit reruns, generate a fixed
prompt suite, and diff outputs across model/prompt changes as a regression test.

### Agent integration checklist

- Prefer `--json` for video and parse **stdout only**; treat **stderr** as logs.
- Branch on **exit codes** (`0/1/2/3`), not on stdout text.
- Read the `.json` **sidecar** for durable metadata (prompt, model, ids).
- Pass keys via env vars or `-K <file>` — never inline secrets in a logged command.
- For headless CI/agents, always supply an action flag so the GUI never launches.
- Respect **model↔provider** pairing and per-provider aspect/size rules to avoid
  validation errors (exit `2`).
```
