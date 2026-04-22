---
name: imageai-gpt-image-2
description: Use when generating, editing, or batching images with OpenAI's gpt-image-2 from inside the ImageAI repo. Drives `python main.py --provider openai -m gpt-image-2 ...` with the right flags for reasoning-quality, custom sizes, multi-reference edits, mask inpainting, partial-image streaming, and Batch API submission. Trigger when the user mentions gpt-image-2 inside the ImageAI working directory.
---

# imageai-gpt-image-2

ImageAI ships first-class support for OpenAI's `gpt-image-2` (released 2026-04-21).
This skill is the cheat-sheet for using it from the CLI.

## When to use

- Anywhere in the ImageAI working directory when the user asks to generate / edit
  / batch images with gpt-image-2 (or "the new OpenAI image model", or
  "thinking image generation").
- For non-ImageAI repos, use the standalone `gpt-image-2` skill instead.

## Quick reference

```bash
# Default: gpt-image-2, auto reasoning, 1024x1024 PNG
python main.py --provider openai -p "your prompt" -o gen.png

# Explicit reasoning level
python main.py --provider openai -m gpt-image-2 \
    --quality high -p "complex composition with text" -o gen.png

# Custom size (must satisfy: edges multiples of 16, max 3840, aspect ≤3:1,
# total pixels 655K-8.3M)
python main.py --provider openai -m gpt-image-2 \
    --custom-size 2048x1152 -p "ultrawide wallpaper" -o gen.png

# Multi-reference compose (up to 10 images)
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
python main.py --provider openai -m gpt-image-2 \
    --moderation low -p "..." -o gen.png

# Batch API (50% discount, up to 24h turnaround)
python main.py --provider openai -m gpt-image-2 \
    --batch -p "your prompt" -o gen.png
# returns: Submitted batch job: batch_abc123...
python main.py --provider openai --batch-status batch_abc123
python main.py --provider openai --batch-fetch  batch_abc123
```

## Parameter matrix

| Flag                    | Values                                                                                           | Default     | Notes                                                                                   |
|-------------------------|--------------------------------------------------------------------------------------------------|-------------|-----------------------------------------------------------------------------------------|
| `--quality`             | `auto`, `low`, `medium`, `high`                                                                  | `auto`      | Drives reasoning compute. `high` ≈ $0.21/image at 1024².                                |
| `--size`                | `1024x1024`, `1536x1024`, `1024x1536`, `2048x2048`, `2048x1152`, `3840x2160`, `2160x3840`, `auto`| `1024x1024` | Mutex with `--custom-size`.                                                             |
| `--custom-size`         | `WxH`                                                                                            | —           | gpt-image-2 only. Edges multiples of 16, max edge 3840, aspect ≤ 3:1, pixels 655K–8.3M. |
| `--output-format`       | `png`, `jpeg`, `webp`                                                                            | `png`       |                                                                                         |
| `--output-compression`  | `0..100`                                                                                         | `90`        | jpeg/webp only.                                                                         |
| `--moderation`          | `auto`, `low`                                                                                    | `auto`      | `low` = permissive. See OpenAI usage policy.                                            |
| `--reference`           | path (repeatable, up to 10)                                                                      | —           | Routes to `/v1/images/edits`.                                                           |
| `--mask`                | PNG path                                                                                         | —           | Alpha mask for inpainting. Transparent = edit zone.                                     |
| `--stream-partials`     | flag                                                                                             | off         | Writes `out.pN.png` for each partial.                                                   |
| `--batch`               | flag                                                                                             | off         | Submit via Batch API (50% off).                                                         |
| `--batch-status JOB`    | job ID                                                                                           | —           | Print job status.                                                                       |
| `--batch-fetch JOB`     | job ID                                                                                           | —           | Download completed outputs.                                                             |
| `-n`, `--num-images`    | `1..10`                                                                                          | `1`         | gpt-image-2 supports up to 10 in one call.                                              |

## Anti-footguns

- **No transparent background**: gpt-image-2 doesn't support `background=transparent`. The provider raises a clear error. For alpha output use `gpt-image-1.5` or `gpt-image-1`.
- **No `input_fidelity`**: not supported. Provider rejects with a clear error.
- **No image variations endpoint**: `/v1/images/variations` is not supported on gpt-image-2.
- **No `style`**: that's a DALL·E 3 thing. gpt-image-2 ignores it.
- **Custom size pitfalls**: the most common mistake is non-multiple-of-16 edges. The provider validates pre-flight and the GUI shows a live red label.
- **Reasoning ≠ a separate `reasoning_effort` knob**: it's *just* `quality` (`auto`/`low`/`medium`/`high`). Higher quality = more thinking compute.
- **Org Verification gate**: gpt-image-2 requires OpenAI Organization Verification. If `python main.py --provider openai -t` returns a verification message, complete the verification at https://platform.openai.com/settings/organization/general.

## Cost estimator (1024×1024)

| Quality | Per image | At n=10 |
|---------|-----------|---------|
| low     | ~$0.006   | ~$0.06  |
| medium  | ~$0.053   | ~$0.53  |
| high    | ~$0.211   | ~$2.11  |
| Batch   | 50% off all of the above |

Costs scale with output tokens. Custom sizes bigger than 1024² cost proportionally more.

## GUI entry points

- **Generate tab** — pick `GPT Image 2 (Thinking, Best)` (top of OpenAI model list). Quality buttons flip to `Low | Medium | High | Auto`. Output format and moderation rows appear. Thinking-progress toggle appears.
- **Resolution selector** — "Custom…" option at the bottom opens a W/H dialog with live validation.
- **Generate → Submit as Batch Job…** — menu action opens a confirmation dialog and submits via Batch API.
- **Batch Jobs tab** — lists submitted jobs from `~/.imageai/batch_jobs.json` with per-row Check/Download buttons.

## Snapshot pinning

For reproducibility, pin to the snapshot:

```python
from core.constants import GPT_IMAGE_2_SNAPSHOT  # "gpt-image-2-2026-04-21"
```

Pass the snapshot ID as `-m` on the CLI when you need bit-for-bit reruns across releases.
