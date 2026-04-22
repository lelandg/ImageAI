# Design: gpt-image-2 Integration

**Date:** 2026-04-22
**Status:** Approved, pending implementation plan
**Model released:** 2026-04-21 (alias `gpt-image-2`, snapshot `gpt-image-2-2026-04-21`)

## Goal

Add full first-class support for OpenAI's `gpt-image-2` to ImageAI, making it the **default** OpenAI model and the **top** entry in every model list. Expose every capability the API supports (thinking via quality, custom sizes up to 3840×2160, multi-reference edits, mask inpainting, streaming partial images, Batch API, moderation knob, output format control). Ship two companion Claude Code skills.

## Why it matters

`gpt-image-2` is the first image model with reasoning baked in — higher `quality` levels spend more compute planning composition, counting, and checking constraints before rendering. It also raises the resolution ceiling to 3840×2160 (2K reliable, 4K experimental) and renders multilingual text (CJK, Hindi, Bengali) cleanly. For ImageAI users it should be the default pick.

## Reference API facts (locked)

- **Endpoints**: `/v1/images/generations`, `/v1/images/edits`, `/v1/chat/completions`, `/v1/responses` (via `image_generation` tool), `/v1/batch`. **No variations.**
- **Thinking knob**: `quality` ∈ `{auto, low, medium, high}`. No separate `reasoning_effort`.
- **Sizes**: presets (1024², 1536×1024, 1024×1536, 2048², 2048×1152, 3840×2160, 2160×3840) **plus any custom WxH** that satisfies: both edges multiples of 16, max edge ≤3840, aspect ≤3:1, total pixels 655,360–8,294,400.
- **Batch**: `n` 1–10+ in a single call.
- **Streaming**: `stream=true` + `partial_images` (0–3). Each partial adds ~100 output tokens.
- **Edits**: `image[]` array (multi-reference) + optional `mask` (alpha PNG). Same `/v1/images/edits` endpoint for both.
- **Output**: `output_format` ∈ `{png, jpeg, webp}`, `output_compression` 0–100 (jpeg/webp only).
- **Moderation**: `auto` (default) | `low` (permissive).
- **Does NOT support** (reject with clear error): `background="transparent"`, `input_fidelity`, `/v1/images/variations`, `style`.
- **Pricing**: $5/$10/$8/$30 per 1M tokens (text-in/text-cached/image-in/output). Batch API = 50% off. Per-image cost ≈ $0.006 low / $0.053 medium / $0.211 high at 1024².
- **Rate limits**: Tier 1 = 5 IPM, Tier 5 = 250 IPM.
- **Access gate**: requires OpenAI Organization Verification.

## Architecture

Six changesets, one isolation boundary each.

### 1. Constants & defaults (`core/constants.py`)

- Add `"gpt-image-2": "GPT Image 2 (Thinking, Best)"` as the **first** entry in `PROVIDER_MODELS["openai"]`. Dict insertion order drives dropdown order.
- Add `GPT_IMAGE_2_SNAPSHOT = "gpt-image-2-2026-04-21"` for reproducibility pins.

### 2. Provider (`providers/openai.py`)

**Capability table** — new module-level dict at the top of `OpenAIProvider`:

```python
MODEL_CAPS = {
    "gpt-image-2": {
        "quality_values": ("auto", "low", "medium", "high"),
        "valid_sizes": ("auto", "1024x1024", "1536x1024", "1024x1536",
                        "2048x2048", "2048x1152", "3840x2160", "2160x3840"),
        "supports_custom_size": True,
        "supports_transparent_bg": False,
        "supports_input_fidelity": False,
        "supports_variations": False,
        "supports_streaming": True,
        "supports_mask": True,
        "supports_multi_reference": True,
        "max_n": 10,
        "default_quality": "auto",
        "snapshot": "gpt-image-2-2026-04-21",
    },
    # existing rows for gpt-image-1.5, gpt-image-1, gpt-image-1-mini, dall-e-3, dall-e-2
}
```

Replaces the scattered `if model == "..."` branches in `generate()`, `edit_image()`, and `get_models_with_details()`. One source of truth.

**`generate()` changes** (around openai.py:57):
- Accept new kwargs: `output_format`, `output_compression`, `moderation`, `partial_images`, `stream`, `on_partial` (callback), `custom_size`.
- Validate `quality` against `MODEL_CAPS[model]["quality_values"]`.
- Validate size: if in `valid_sizes`, pass through; if `custom_size` and `supports_custom_size`, validate against constraints (edges mult of 16, aspect ≤3:1, pixel bounds); else raise.
- If `stream=True` and `partial_images > 0`: route through Responses API (`client.responses.create` with `tools=[{"type": "image_generation", ...}]`) and invoke `on_partial(index, bytes)` for each `response.image_generation_call.partial_image` event. Final image returned normally.
- Reject unsupported params per capability table with actionable messages ("Transparent background not supported on gpt-image-2; use gpt-image-1.5 for alpha PNG").

**`edit_image()` changes** (around openai.py:533):
- Accept `image` as list-of-paths. For gpt-image-2 / gpt-image-1.x, send `image[]` multipart. Keep single-image path for dall-e-2.
- `mask` stays optional. If present and model supports mask, send through.

**New method `submit_batch_job(requests: list, endpoint: str) -> str`:**
- Builds JSONL, calls `/v1/batch` create, returns job ID.
- Persists job record to `~/.imageai/batch_jobs.json`: `{job_id, created_at, model, endpoint, request_count, prompt_preview}`.

**New method `check_batch_job(job_id) -> dict`** — polls status, downloads output file when complete, writes images + sidecars to the user's output directory.

### 3. GUI (`gui/main_window.py`, `gui/settings_widgets.py`)

**Quality selector** (`settings_widgets.py:1181`, QualitySelector):
- Driven off `MODEL_CAPS[current_model]["quality_values"]`.
- For gpt-image-2: radio group `Low | Medium | High | Auto`. Tooltip on each explains thinking-compute tradeoff.
- For dall-e-3: existing Standard/HD + Vivid/Natural.
- For dall-e-2 / gpt-image-1-mini: hidden.

**Size selector** (existing `ResolutionSelector`):
- Add aspect presets: `16:9 → 3840x2160` when model is gpt-image-2 (otherwise fall back).
- New "Custom…" option at bottom of size dropdown. Opens inline popup with W/H spinboxes (step=16), live validator label turning green when valid, red with reason when not. Validator runs the same function the provider uses — shared module `core/image_size.py`.

**Output format row** (new widget, `settings_widgets.py`):
- Visible when `MODEL_CAPS[model].get("output_format")` (new cap flag: true for gpt-image-2 and gpt-image-1.5).
- Radio: `PNG | JPEG | WebP`. Compression slider (0–100, default 90) appears only for jpeg/webp.

**Moderation checkbox** (new, gpt-image-2 only):
- "Permissive content moderation (`moderation=low`)" — tooltip links to OpenAI's usage policy page.

**Thinking progress toggle** (new, gpt-image-2 only):
- Checkbox "Show thinking progress". Default off.
- When on, worker thread is invoked with `stream=True, partial_images=2` and a Qt signal-emitting `on_partial` callback. MainWindow slot updates preview pane with each partial frame; a "Thinking… (frame N/2)" label replaces the spinner.

**Reference images & mask panel**:
- Existing reference-image list becomes proper multi-file with thumbnails + remove buttons (already partially there at main_window.py reference handling).
- "Mask (PNG alpha)…" button next to reference list. Shown only when `MODEL_CAPS[model]["supports_mask"]`.

**Batch API submission**:
- New menu: `Generate → Submit as Batch Job…`.
- Dialog shows: request count, estimated cost at 50% discount, "Submit" / "Cancel". On submit, spawns a QThread that calls `submit_batch_job`, shows job ID.
- New History subtab `Batch Jobs`: lists jobs from `~/.imageai/batch_jobs.json`. Per-row: status (polled on-demand via "Refresh"), "Download results" when complete.

**Model-change handler** (`_on_model_changed` at `main_window.py:3903`):
- Reads `MODEL_CAPS[new_model]` and shows/hides each widget accordingly. Single dispatch, no per-model `if` branches.

### 4. CLI (`cli/parser.py`, `cli/runner.py`)

New flags (all optional):
- `--quality {low,medium,high,auto,standard,hd}` — extended values; validated against MODEL_CAPS.
- `--output-format {png,jpeg,webp}`
- `--output-compression N` (0–100)
- `--moderation {auto,low}`
- `--custom-size WxH` — mutually exclusive with `--size`.
- `--stream-partials` — sets `partial_images=2, stream=True`; prints progress to stderr, saves each partial as `out.p0.png`, `out.p1.png`, final as `out.png`.
- `--reference IMG` (repeatable), `--mask PNG` — passes to `edit_image()` path.
- `--batch` — submits via Batch API instead of sync generation. Prints job ID.
- `--batch-status JOB_ID` — prints status.
- `--batch-fetch JOB_ID` — downloads and writes outputs.

Runner dispatches sync/async/edit/batch based on flag combination.

### 5. Metadata sidecar (`core/utils.py:190`)

Extend `write_image_sidecar()` to capture:

```python
{
  # existing fields stay
  "quality": "high",
  "output_format": "png",
  "output_compression": None,
  "moderation": "auto",
  "partial_images_count": 2,
  "custom_size": null,
  "reference_images": ["path/a.png", "path/b.png"],
  "mask": null,
  "model_snapshot": "gpt-image-2-2026-04-21",
  "batch_job_id": null,
  "usage": {
    "input_tokens_text": 123,
    "input_tokens_image": 0,
    "output_tokens": 4096,
    "cost_usd": 0.211
  }
}
```

All fields nullable. Readers tolerate missing fields (forward compatibility).

### 6. Shared size validator (new: `core/image_size.py`)

Single function `validate_custom_size(w, h, model_caps) -> tuple[bool, str]` used by both provider and GUI. Prevents UI/API drift.

## Skills

### Skill A: `imageai-gpt-image-2` (wrapper)

**Locations:**
- `D:\Documents\Code\GitHub\ImageAI\.claude\skills\imageai-gpt-image-2\SKILL.md`
- `C:\Users\aboog\.claude\skills\imageai-gpt-image-2\SKILL.md` (global mirror)

**Triggers:** "generate image with gpt-image-2 in ImageAI", "use ImageAI to…", or any mention of gpt-image-2 when CWD is under `ImageAI\`.

**Behavior:** Invokes the ImageAI CLI. Handles prompt → file path → `python main.py --provider openai -m gpt-image-2 ...` with all the right flags. Provides the parameter matrix, cost estimator examples, and the footgun list (no transparent, no input_fidelity, no variations).

### Skill B: `gpt-image-2` (direct API)

**Locations:**
- `C:\Users\aboog\.claude\skills\gpt-image-2\SKILL.md` (global)
- `D:\Documents\Code\GitHub\.claude_code\.claude\skills\gpt-image-2\SKILL.md`

**Triggers:** "use gpt-image-2", "generate with OpenAI gpt-image-2", or any image-generation ask in a repo that's NOT ImageAI.

**Behavior:** Self-contained Python snippet using the `openai` SDK. Covers generation, multi-reference edit, mask inpaint, streaming, Batch submission, cost estimation. Reads `OPENAI_API_KEY` from env. No ImageAI dependency.

Both skills ship with:
- Full parameter matrix (every kwarg, valid values, defaults)
- Custom-size validation rules
- The thinking = quality clarification (no `reasoning_effort`)
- Anti-footgun callouts
- Copy-paste Python snippets for every endpoint

## Testing

**Unit** (pytest, offline):
- `MODEL_CAPS` dispatch returns correct values per model.
- `validate_custom_size()` accepts/rejects the right shapes.
- Sidecar schema round-trips (write → read → equality).
- CLI parser handles new flags + mutual-exclusion rules.
- Provider raises helpful errors for unsupported param combos (transparent bg on gpt-image-2, input_fidelity on gpt-image-2, mask on dall-e-3, n>1 on dall-e-3, etc.).

**Integration** (live API, gated by `IMAGEAI_LIVE_TESTS=1`):
- One generation at each quality level.
- One 1536×1024 generation.
- One custom-size (e.g., 2048×1152) generation.
- One multi-reference edit.
- One mask inpaint.
- One streaming run with `partial_images=2` (verify 2 partials + final delivered).
- One Batch API submission (don't wait for completion; just verify job ID returned).

**Manual GUI smoke**:
- Switch model gpt-image-2 ↔ dall-e-3 ↔ gpt-image-1.5; verify quality/size/format widgets show/hide correctly.
- Generate with "Show thinking progress" on; verify preview updates as partials arrive.
- Submit a batch job; verify entry appears in Batch Jobs subtab.

## Non-goals

- Not rebuilding the region/viseme editor — those keep using gpt-image-1.5 path.
- Not exposing Responses-API-as-chat (web_search + image_generation tool-chaining). Future enhancement.
- Not touching video pipeline.
- Not auto-migrating existing code paths off gpt-image-1.x — they stay supported.

## Risks & mitigations

- **Org Verification gate**: some users may lack access. Provider's `validate_auth()` should detect 403 "verification required" and return a clear message pointing to the OpenAI dashboard.
- **Streaming complexity**: Responses API path is new in the codebase. Mitigation: keep streaming off by default; sync path is the fallback if Responses SDK method missing.
- **Custom-size footgun**: users may enter non-mult-of-16 sizes. Validated both in GUI (live) and provider (pre-flight).
- **Cost surprise at `quality=high` + `n=10`**: GUI cost estimator updates live as user adjusts; shows per-image and total.

## Files touched (summary)

- `core/constants.py` — add model entry, snapshot constant.
- `core/utils.py` — extend sidecar schema.
- `core/image_size.py` — new file, shared validator.
- `providers/openai.py` — capability table, generate/edit/batch methods.
- `gui/main_window.py` — model-change handler, batch menu, batch subtab, streaming worker wiring.
- `gui/settings_widgets.py` — quality selector, size selector, output format row, moderation checkbox, thinking toggle.
- `cli/parser.py` — new flags.
- `cli/runner.py` — dispatch for edit/batch/streaming paths.
- `.claude/skills/imageai-gpt-image-2/SKILL.md` — new.
- `tests/` — unit + integration tests.

**Estimated scope:** ~800–1200 lines touched, bulk in `providers/openai.py` (capability table + streaming) and `gui/main_window.py` (widget wiring).
