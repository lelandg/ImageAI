# OpenAI API Upgrade and Sora 2 Integration Plan

Last verified: 2024-10 (no external lookups during authoring)

---

## Goals
- Update ImageAI to align with the latest OpenAI API patterns available as of 2024-10 (Responses API, Python SDK v1).
- Expand OpenAI image capabilities beyond DALL·E 3 to include `gpt-image-1` where available.
- Define an integration path for OpenAI’s Sora 2 video generation (when generally accessible), mirroring our Veo client approach.

---

## Scope in This Repo
- Provider updates: `providers/openai.py` (image generation models and options)
- Video pipeline: new client for OpenAI video (Sora 2) under `core/video/`
- Prompt templates: additions in `templates/video/*.j2` for Sora‑oriented prompts
- GUI/CLI wiring: surface Sora 2 as a selectable backend in video project flows

This document does not ship code changes; it specifies concrete tasks and safe defaults.

---

## OpenAI API Overview (2024-10)

Key shifts relevant to ImageAI:
- Responses API: unified, multimodal interface (`client.responses.create(...)`) superseding legacy Chat Completions. Prefer Responses for text/vision/tool‑use.
- Python SDK v1+: top‑level `OpenAI` client; Images API via `client.images.generate(...)`.
- Image models: `dall-e-3` remains available; `gpt-image-1` provides strong quality, transparency/background control, and consistent SDK ergonomics.
- Audio: TTS/STT available (out of scope for this plan).

Implications for us:
- Keep `providers/openai.py` on the official SDK v1, avoid deprecated Chat Completions.
- Add `gpt-image-1` support while retaining `dall-e-3` for parity and continuity.

---

## Image Generation: Model & Parameter Plan

Models to expose in OpenAI provider:
- `gpt-image-1` (preferred for new work)
- `dall-e-3` (default today for continuity)
- `dall-e-2` (edits/variations only)

Parameters by model (pragmatic baseline):
- Common: `prompt`, `size` (e.g., `1024x1024`, `1792x1024`, `1024x1792`), `n`, `response_format` (`b64_json` or `url`)
- `dall-e-3`: supports `quality` (`standard|hd`) and often `style` (`vivid|natural`); `n` effectively 1 per request – loop for multiples.
- `gpt-image-1`: supports transparent backgrounds via `background="transparent"`; do not rely on `style`; treat `n` similarly to DALL·E 3 (loop if needed). Seeding may exist but is not guaranteed deterministic.

Provider changes (non‑breaking):
- Add `gpt-image-1` to `get_models()` and `get_models_with_details()`.
- Allow selecting `gpt-image-1` from GUI/CLI; when chosen:
  - Use `client.images.generate(model="gpt-image-1", prompt=..., size=..., response_format=..., background=...)` when background is requested.
  - Do not pass `style`/`quality` unless documented for the selected model.
- Preserve current logic mapping aspect ratio → size for ease of use.

Notes on edits/variations:
- Keep `edit_image()` and `create_variations()` bound to `dall-e-2` unless `gpt-image-1` parity is validated.

---

## Minimal Provider Diff Sketch (for reference only)

File: `providers/openai.py`

Add a selectable model and branch its parameters:

```python
# in get_models()
return {
    "gpt-image-1": "GPT Image 1",
    "dall-e-3": "DALL·E 3",
    "dall-e-2": "DALL·E 2",
}

# in get_models_with_details()
"gpt-image-1": {"name": "GPT Image 1", "description": "High quality, supports transparency"},

# in generate(...)
if model == "gpt-image-1":
    gen_params = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "response_format": response_format,
    }
    if kwargs.get("background") in {"transparent", "white", "black"}:
        gen_params["background"] = kwargs["background"]
elif model == "dall-e-3":
    # keep existing quality/style handling
```

---

## Sora 2 Integration Plan (Video)

Status & assumptions:
- As of 2024-10, OpenAI’s Sora was announced in limited access; details and stable SDK surface may vary. Treat Sora 2 as an upcoming, async job‑based video API with content safety constraints.
- This plan avoids guessing proprietary parameters; it focuses on robust integration points mirroring our Veo client.

Design goals:
- Build a `SoraClient` in `core/video/sora_client.py` analogous to `VeoClient` with:
  - Dataclasses for `SoraModel` and `SoraGenerationConfig`
  - Async `generate_video_async()` returning a `SoraGenerationResult`
  - Polling for long‑running operations and resilient download to cache
  - Constraints table per model for validation (durations, resolutions, aspect ratios)

Proposed module layout:

```python
# core/video/sora_client.py
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

class SoraModel(Enum):
    SORA_2_GENERATE = "sora-2.0-generate-001"  # placeholder until confirmed
    SORA_2_FAST = "sora-2.0-fast-generate-001"  # placeholder until confirmed

@dataclass
class SoraGenerationConfig:
    model: SoraModel
    prompt: str
    aspect_ratio: str = "16:9"
    resolution: str = "1080p"  # 720p|1080p (expand if/when 4K lands)
    duration: int = 8
    fps: int = 24
    include_audio: bool = False  # enable if Sora ships audio
    seed: Optional[int] = None

@dataclass
class SoraGenerationResult:
    success: bool = False
    video_url: Optional[str] = None
    video_path: Optional[Path] = None
    operation_id: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None

class SoraClient:
    # MODEL_CONSTRAINTS = { ... }  # durations/resolutions/ratios per model
    # generate_video_async() -> SoraGenerationResult
    # generate_video()  (sync wrapper)
    # _poll_for_completion(), _download_video()
    ...
```

Polling model:
- Expect job/operation IDs and an eventual URL; implement exponential backoff with a generous maximum time window (e.g., 6–8 minutes unless docs specify otherwise).

Download policy:
- Cache under `~/.imageai/cache/sora_videos/` with timestamp+hash naming (parity with Veo client approach).

Safety and watermarking:
- Respect OpenAI safety filters; surface policy errors clearly in UI; if watermarking metadata (SynthID‑like) exists, capture in `metadata`.

---

## GUI / CLI Wiring

GUI (video project):
- Add provider selector: `Veo 3 (Google)` or `Sora 2 (OpenAI)`.
- When `Sora 2` selected, show available, validated parameters (duration cap, supported aspect ratios, max resolution) using `SoraClient.MODEL_CONSTRAINTS`.
- Log all dialogs via `gui/dialog_utils.py` (repo convention) and copy logs on exit.

CLI:
- Extend `cli/commands` with a `video` subcommand flag `--provider sora2` to call `SoraClient`.

Templates:
- Add `templates/video/sora_shot_prompt.j2` for consistent cinematic prompting tuned for Sora.

---

## Configuration & Auth

- API key: `OPENAI_API_KEY` or via CLI `--api-key` (existing conventions).
- Optional: support `OPENAI_ORG_ID` / `OPENAI_PROJECT` if needed for Responses/Video endpoints when docs require them.
- Never log secrets; use `core.security.secure_storage` if persisting.

---

## Validation & Rate Limiting

- Keep using `core.security.rate_limiter` around OpenAI calls to avoid 429s.
- For Sora 2, constrain concurrency similarly to Veo (e.g., `max_concurrent=3`) and provide batch helpers.

---

## Test Plan (Manual)

Image (OpenAI):
- Keys: `python main.py -t --provider openai` (validates list models in `providers/openai.py:validate_auth`)
- Generation: `python main.py -p "logo test" -o out.png --provider openai --model gpt-image-1`
- Transparent output: repeat with `--background transparent` and verify PNG alpha.

Video (Sora 2) once available:
- Smoke: generate a 4–8s 1080p clip at 16:9, verify local caching and metadata.
- Timeout: simulate slow jobs and confirm UI messages stay responsive.

---

## Risks & Unknowns

- Sora 2 availability, limits, pricing, and exact SDK surface may differ from placeholders above.
- `gpt-image-1` edit/variation parity with `dall-e-2` should be validated before enabling edits under that model.
- Long‑running operations require robust cancellation and user feedback in GUI; ensure dialog logging is wired.

---

## Incremental Task Checklist

- [ ] Add `gpt-image-1` support in `providers/openai.py` (models list + param handling)
- [ ] Surface `background="transparent"` in GUI/CLI when `gpt-image-1` is selected
- [ ] Guard `style`/`quality` usage to DALL·E 3 only
- [ ] Create `core/video/sora_client.py` scaffold with constraints/polling/downloader
- [ ] Add Sora 2 as a selectable provider in video project UI and CLI
- [ ] Add `templates/video/sora_shot_prompt.j2`
- [ ] Update `README.md` usage examples (image + video)
- [ ] Add CHANGELOG entry once user‑visible

---

## Appendix: Example Calls (Python SDK v1)

Images (OpenAI SDK):
```python
from openai import OpenAI
client = OpenAI()

# GPT Image 1 (transparent background)
r = client.images.generate(
    model="gpt-image-1",
    prompt="Minimal phoenix logo, flat, vector, orange/teal",
    size="1024x1024",
    background="transparent",
    response_format="b64_json",
)

# DALL·E 3 (vivid style, HD)
r = client.images.generate(
    model="dall-e-3",
    prompt="Studio portrait of a red fox in the snow, 85mm, f/1.8",
    size="1792x1024",
    quality="hd",
    response_format="b64_json",
)
```

Video (Sora 2, placeholder):
```python
# Pseudo-code until API is public
from openai import OpenAI
client = OpenAI()

op = client.videos.generate(
    model="sora-2.0-generate-001",
    prompt="A cinematic drone shot over terraced rice fields at golden hour",
    aspect_ratio="16:9",
    resolution="1080p",
    duration=8,
    fps=24,
)

# Poll operation, then fetch resulting URL and download
```

---

## References
- OpenAI Python SDK v1 client patterns (Responses API, Images API)
- Internal parity with `core/video/veo_client.py` for long‑running jobs

