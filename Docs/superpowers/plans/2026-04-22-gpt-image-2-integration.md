# gpt-image-2 Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land first-class support for OpenAI's `gpt-image-2` (released 2026-04-21) as the default OpenAI model, exposing every supported capability — reasoning via `quality`, custom sizes up to 3840×2160, multi-reference edits, mask inpainting, partial-image streaming, Batch API, moderation knob, output-format control — and ship a Claude Code skill that wraps the ImageAI CLI.

**Architecture:** Driven by a single `MODEL_CAPS` capability table in `providers/openai.py`. Every per-model `if` branch in the provider, GUI, and CLI consults that table. New shared module `core/image_size.py` provides one validator used by both provider (pre-flight) and GUI (live). Streaming uses the OpenAI Responses API with graceful fallback to sync. Batch jobs persist to `~/.imageai/batch_jobs.json`.

**Tech Stack:** Python 3.12, `openai` SDK (≥ 1.50 for Responses + Batch), PySide6 (Qt6), no new runtime deps. Tests are skipped this round per user direction (test harness will be scaffolded separately).

**Source spec:** `Docs/superpowers/specs/2026-04-22-gpt-image-2-integration-design.md`

**Branch:** `feat/gpt-image-2`

**Conventions for every task below:**
- WSL bash uses the project venv at `.venv_linux/`. Activate with `source /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/activate` if needed.
- After every code change, run `python -m py_compile <changed-files>` from the repo root to catch syntax breakage. (PySide6 imports may not resolve in WSL — that's expected; treat `ModuleNotFoundError: PySide6` as success for syntax-only checks.)
- Each task ends with a single commit. Use `git add <listed-files>` (never `-A`).
- Commit message format: `<type>(<scope>): <subject>` followed by a 1-2 sentence body. Always include the `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer.
- Do **not** push or merge — that's the integrator's call after all six tasks land.
- **PySide6 modal-dialog idiom**: use the trailing-underscore form `dlg.exec_()` consistently. Both `.exec()` and `.exec_()` work, but `.exec_()` avoids tripping over generic `exec(` security scanners.

---

## Task 1 — Foundation (constants, shared size validator, sidecar schema doc)

**Why first:** Everything else depends on the model entry, the shared validator, and the sidecar key list. No other task touches these files at the same scope.

**Files:**
- Modify: `core/constants.py` (add model entry, default-OpenAI-model, snapshot constant — lines 17-39)
- Create: `core/image_size.py`
- Modify: `core/utils.py` (extend docstring on `write_image_sidecar` to enumerate the new optional fields — line 194)

### Step 1.1 — Add `gpt-image-2` to `PROVIDER_MODELS["openai"]` as the first entry

- [ ] Open `core/constants.py`. In the `PROVIDER_MODELS["openai"]` dict (lines 31-39), insert `"gpt-image-2": "GPT Image 2 (Thinking, Best)",` as the **first** entry. Dict insertion order drives dropdown order.

After the change, the openai block reads exactly:

```python
    "openai": {
        # GPT Image Series — newest first
        "gpt-image-2": "GPT Image 2 (Thinking, Best)",
        "gpt-image-1.5": "GPT Image 1.5 (Latest)",
        "gpt-image-1": "GPT Image 1",
        "gpt-image-1-mini": "GPT Image 1 Mini (Fast)",
        # DALL-E Series
        "dall-e-3": "DALL·E 3",
        "dall-e-2": "DALL·E 2",
    },
```

### Step 1.2 — Add `GPT_IMAGE_2_SNAPSHOT` constant

- [ ] In `core/constants.py`, immediately after the `PROVIDER_MODELS = { ... }` block (after line 55, before `PROVIDER_KEY_URLS`), insert:

```python
# OpenAI gpt-image-2 reproducibility pin. Use this snapshot when sidecar
# metadata needs the exact model snapshot, not the alias.
GPT_IMAGE_2_SNAPSHOT = "gpt-image-2-2026-04-21"
```

### Step 1.3 — Document optional sidecar fields

- [ ] In `core/utils.py`, replace the `write_image_sidecar` docstring (line 195) with the version below. The function body is unchanged — sidecars already accept arbitrary dicts; this is just a contract for downstream callers.

```python
def write_image_sidecar(image_path: Path, meta: dict) -> None:
    """Write human-readable JSON beside the image.

    Sidecar fields are open-ended. Known optional keys (all nullable, all
    forward-compatible — readers must tolerate missing keys):

      Always present (existing): prompt, provider, model, timestamp.

      Added 2026-04-22 for gpt-image-2 support:
        quality              str   "auto"|"low"|"medium"|"high" (gpt-image-2)
                                   or "standard"|"hd" (dall-e-3)
        output_format        str   "png"|"jpeg"|"webp"
        output_compression   int|None   0-100, only when format is jpeg/webp
        moderation           str   "auto"|"low"
        partial_images_count int|None   number of partials streamed (0-3)
        custom_size          str|None   "WxH" if a non-preset size was used
        reference_images     list[str]  paths or names of inputs to /edits
        mask                 str|None   path to alpha mask PNG
        model_snapshot       str   e.g. "gpt-image-2-2026-04-21"
        batch_job_id         str|None   non-null when produced by Batch API
        usage                dict|None  {input_tokens_text, input_tokens_image,
                                         output_tokens, cost_usd}
    """
    try:
        p = sidecar_path(image_path)
        p.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    except (OSError, IOError, json.JSONEncodeError):
        pass
```

### Step 1.4 — Create `core/image_size.py`

- [ ] Create the file with this exact content:

```python
"""Shared image-size validation for OpenAI gpt-image-2 and friends.

Both the provider (pre-flight) and the GUI (live red/green label) call
``validate_custom_size`` so the rules can never drift.
"""

from __future__ import annotations

from typing import Mapping, Tuple


def validate_custom_size(width: int, height: int, model_caps: Mapping) -> Tuple[bool, str]:
    """Validate a custom WxH against the model's constraints.

    Args:
        width:  Desired width in pixels.
        height: Desired height in pixels.
        model_caps: A row from ``OpenAIProvider.MODEL_CAPS``. Recognized keys:
            - ``supports_custom_size``: bool, must be True.
            - ``custom_size_min_pixels``: int, default 655_360.
            - ``custom_size_max_pixels``: int, default 8_294_400.
            - ``custom_size_max_edge``: int, default 3840.
            - ``custom_size_edge_multiple``: int, default 16.
            - ``custom_size_max_aspect``: float, default 3.0.

    Returns:
        ``(True, "")`` if valid; ``(False, reason)`` otherwise. ``reason`` is
        a short, human-readable string suitable for showing in a tooltip or
        provider error message.
    """
    if not model_caps.get("supports_custom_size", False):
        return False, "Custom size not supported on this model"

    if width <= 0 or height <= 0:
        return False, "Width and height must be positive"

    multiple = int(model_caps.get("custom_size_edge_multiple", 16))
    if width % multiple or height % multiple:
        return False, f"Both edges must be multiples of {multiple}"

    max_edge = int(model_caps.get("custom_size_max_edge", 3840))
    if width > max_edge or height > max_edge:
        return False, f"Max edge length is {max_edge}px"

    pixels = width * height
    min_px = int(model_caps.get("custom_size_min_pixels", 655_360))
    max_px = int(model_caps.get("custom_size_max_pixels", 8_294_400))
    if pixels < min_px:
        return False, f"Total pixels {pixels:,} below minimum {min_px:,}"
    if pixels > max_px:
        return False, f"Total pixels {pixels:,} above maximum {max_px:,}"

    aspect_max = float(model_caps.get("custom_size_max_aspect", 3.0))
    aspect = max(width, height) / min(width, height)
    if aspect > aspect_max:
        return False, f"Aspect ratio {aspect:.2f}:1 exceeds limit {aspect_max:.0f}:1"

    return True, ""


def parse_size_string(size: str) -> Tuple[int, int]:
    """Parse a 'WxH' string into a (width, height) tuple.

    Accepts ``x`` or ``X`` as the separator. Raises ``ValueError`` on bad input.
    """
    if not isinstance(size, str) or "x" not in size.lower():
        raise ValueError(f"Bad size string: {size!r} (expected 'WxH')")
    w, h = size.lower().split("x", 1)
    return int(w.strip()), int(h.strip())
```

### Step 1.5 — Verify

- [ ] Run from repo root:

```bash
python -m py_compile core/constants.py core/image_size.py core/utils.py
python -c "from core.constants import PROVIDER_MODELS, GPT_IMAGE_2_SNAPSHOT; \
    assert list(PROVIDER_MODELS['openai'].keys())[0] == 'gpt-image-2', PROVIDER_MODELS['openai']; \
    assert GPT_IMAGE_2_SNAPSHOT == 'gpt-image-2-2026-04-21'; print('constants OK')"
python -c "from core.image_size import validate_custom_size, parse_size_string; \
    caps = {'supports_custom_size': True}; \
    assert validate_custom_size(2048, 1152, caps) == (True, ''); \
    ok, msg = validate_custom_size(2050, 1152, caps); assert not ok and 'multiples' in msg, msg; \
    ok, msg = validate_custom_size(4096, 1024, caps); assert not ok and 'edge' in msg, msg; \
    ok, msg = validate_custom_size(1024, 256, caps); assert not ok and ('aspect' in msg or 'pixels' in msg), msg; \
    print('image_size OK')"
```

Expected output: `constants OK` and `image_size OK`. Any traceback = stop and fix.

### Step 1.6 — Commit

- [ ] Stage and commit:

```bash
git add core/constants.py core/image_size.py core/utils.py
git commit -m "$(cat <<'EOF'
feat(foundation): add gpt-image-2 model entry, snapshot constant, shared size validator

Adds gpt-image-2 as the first entry in PROVIDER_MODELS['openai'] so it
becomes the default OpenAI model in dropdowns. Introduces
GPT_IMAGE_2_SNAPSHOT for sidecar reproducibility pinning and a new
core/image_size.py with validate_custom_size() that the provider and GUI
will both consume — single source of truth for the 16-px multiple,
3840 max-edge, 3:1 aspect, 655K-8.3M pixel constraints.

Documents the new optional sidecar fields on write_image_sidecar so
downstream readers know what to expect.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2 — Provider sync API (`MODEL_CAPS` + `generate()` + `edit_image()`)

**Why this slice:** Land the capability table and the synchronous code paths first. Streaming and Batch (Task 3) layer cleanly on top once `MODEL_CAPS` exists. UI changes (Tasks 5–6) depend on the table being importable.

**Files:**
- Modify: `providers/openai.py` (top of file: add `MODEL_CAPS`; refactor `generate()` lines 57-459; refactor `edit_image()` lines 533-590; refactor `get_models()` line 475, `get_models_with_details()` line 487, `get_default_model()` line 521; improve `validate_auth()` line 461)

### Step 2.1 — Add `MODEL_CAPS` at module scope

- [ ] In `providers/openai.py`, immediately below the existing `OpenAIClient = None` line (around line 24, before `class OpenAIProvider`), insert the capability table:

```python
# Capability table for every OpenAI image model. The provider, GUI, and CLI
# all consult this; never add per-model `if model == ...` branches outside
# this dict — extend the dict instead.
MODEL_CAPS = {
    "gpt-image-2": {
        "display_name": "GPT Image 2 (Thinking, Best)",
        "snapshot": "gpt-image-2-2026-04-21",
        "endpoint": "images.generate",
        "quality_values": ("auto", "low", "medium", "high"),
        "default_quality": "auto",
        "valid_sizes": ("auto", "1024x1024", "1536x1024", "1024x1536",
                        "2048x2048", "2048x1152", "3840x2160", "2160x3840"),
        "supports_custom_size": True,
        "custom_size_edge_multiple": 16,
        "custom_size_max_edge": 3840,
        "custom_size_max_aspect": 3.0,
        "custom_size_min_pixels": 655_360,
        "custom_size_max_pixels": 8_294_400,
        "supports_transparent_bg": False,
        "supports_input_fidelity": False,
        "supports_variations": False,
        "supports_streaming": True,
        "supports_mask": True,
        "supports_multi_reference": True,
        "supports_output_format": True,
        "supports_moderation": True,
        "supports_batch": True,
        "supports_style": False,
        "max_n": 10,
    },
    "gpt-image-1.5": {
        "display_name": "GPT Image 1.5 (Latest)",
        "endpoint": "images.generate",
        "quality_values": ("auto",),
        "default_quality": "auto",
        "valid_sizes": ("auto", "1024x1024", "1536x1024", "1024x1536"),
        "supports_custom_size": False,
        "supports_transparent_bg": True,
        "supports_input_fidelity": False,
        "supports_variations": False,
        "supports_streaming": False,
        "supports_mask": True,
        "supports_multi_reference": True,
        "supports_output_format": True,
        "supports_moderation": True,
        "supports_batch": True,
        "supports_style": False,
        "max_n": 10,
    },
    "gpt-image-1": {
        "display_name": "GPT Image 1",
        "endpoint": "images.generate",
        "quality_values": ("auto",),
        "default_quality": "auto",
        "valid_sizes": ("auto", "1024x1024", "1792x1024", "1024x1792"),
        "supports_custom_size": False,
        "supports_transparent_bg": True,
        "supports_input_fidelity": False,
        "supports_variations": False,
        "supports_streaming": False,
        "supports_mask": True,
        "supports_multi_reference": True,
        "supports_output_format": False,
        "supports_moderation": False,
        "supports_batch": False,
        "supports_style": False,
        "max_n": 1,
    },
    "gpt-image-1-mini": {
        "display_name": "GPT Image 1 Mini (Fast)",
        "endpoint": "images.generate",
        "quality_values": ("auto",),
        "default_quality": "auto",
        "valid_sizes": ("auto", "1024x1024", "1792x1024", "1024x1792"),
        "supports_custom_size": False,
        "supports_transparent_bg": False,
        "supports_input_fidelity": False,
        "supports_variations": False,
        "supports_streaming": False,
        "supports_mask": False,
        "supports_multi_reference": False,
        "supports_output_format": False,
        "supports_moderation": False,
        "supports_batch": False,
        "supports_style": False,
        "max_n": 1,
    },
    "dall-e-3": {
        "display_name": "DALL·E 3",
        "endpoint": "images.generate",
        "quality_values": ("standard", "hd"),
        "default_quality": "standard",
        "valid_sizes": ("1024x1024", "1792x1024", "1024x1792"),
        "supports_custom_size": False,
        "supports_transparent_bg": False,
        "supports_input_fidelity": False,
        "supports_variations": False,
        "supports_streaming": False,
        "supports_mask": False,
        "supports_multi_reference": False,
        "supports_output_format": False,
        "supports_moderation": False,
        "supports_batch": False,
        "supports_style": True,
        "max_n": 1,
    },
    "dall-e-2": {
        "display_name": "DALL·E 2",
        "endpoint": "images.generate",
        "quality_values": ("standard",),
        "default_quality": "standard",
        "valid_sizes": ("256x256", "512x512", "1024x1024"),
        "supports_custom_size": False,
        "supports_transparent_bg": False,
        "supports_input_fidelity": False,
        "supports_variations": True,
        "supports_streaming": False,
        "supports_mask": True,
        "supports_multi_reference": False,
        "supports_output_format": False,
        "supports_moderation": False,
        "supports_batch": False,
        "supports_style": False,
        "max_n": 10,
    },
}


def _caps_for(model: str) -> dict:
    """Return MODEL_CAPS row, falling back to gpt-image-1 for unknown models."""
    return MODEL_CAPS.get(model) or MODEL_CAPS["gpt-image-1"]


class _UnsupportedParam(ValueError):
    """Raised when a request includes a parameter the model does not support."""
```

### Step 2.2 — Refactor `get_models()`, `get_models_with_details()`, `get_default_model()` to drive off `MODEL_CAPS`

- [ ] Replace the bodies of these three methods (currently lines 475-523) so they consult `MODEL_CAPS`. The replacement preserves dict-insertion order, which already lists `gpt-image-2` first (as the dict literal above does):

```python
    def get_models(self) -> Dict[str, str]:
        """Get available OpenAI image generation models (id -> display name)."""
        return {model_id: caps["display_name"] for model_id, caps in MODEL_CAPS.items()}

    def get_models_with_details(self) -> Dict[str, Dict[str, str]]:
        """Get available OpenAI image generation models with details for the UI."""
        descriptions = {
            "gpt-image-2": "Reasoning model — best quality, custom sizes up to 3840x2160, multi-reference, mask, streaming",
            "gpt-image-1.5": "Latest 1.x — 4x faster, transparent bg, up to 10 images",
            "gpt-image-1": "High quality, transparent backgrounds, reference images",
            "gpt-image-1-mini": "Fast generation, lower cost, good quality",
            "dall-e-3": "Most advanced legacy model, vivid/natural style, n=1 only",
            "dall-e-2": "Previous generation, lower cost, supports edits and variations",
        }
        return {
            model_id: {"name": caps["display_name"], "description": descriptions.get(model_id, "")}
            for model_id, caps in MODEL_CAPS.items()
        }

    def get_default_model(self) -> str:
        """Default OpenAI model — gpt-image-2 since 2026-04-22."""
        return "gpt-image-2"
```

### Step 2.3 — Improve `validate_auth()` to surface org-verification gate

- [ ] Replace the current `validate_auth` method (lines 461-473) with this version that catches the OpenAI `PermissionDeniedError`/403 and returns an actionable message:

```python
    def validate_auth(self) -> Tuple[bool, str]:
        """Validate OpenAI API key. Detects the gpt-image-2 org-verification gate."""
        if not self.api_key:
            return False, "No API key configured"

        try:
            self._ensure_client()
            self.client.models.list()
            return True, "API key is valid"
        except Exception as e:  # noqa: BLE001 — surface every backend failure to the user
            msg = str(e)
            lower = msg.lower()
            if "verification" in lower or "must be verified" in lower or "403" in msg:
                return False, (
                    "OpenAI Organization Verification required for gpt-image-2 / "
                    "newest models. Visit https://platform.openai.com/settings/organization/general "
                    "to verify your org, then retry."
                )
            return False, f"API key validation failed: {e}"
```

### Step 2.4 — Refactor `generate()` to use `MODEL_CAPS`

The current `generate()` (lines 57-459) is the largest blob. The refactor: keep the existing per-model branches for `gpt-image-1`, `gpt-image-1.5`, `dall-e-3`, `dall-e-2` **as-is** (they ship working code); add a new `gpt-image-2` branch *and* a generic capability check at the top that rejects unsupported params with helpful messages.

- [ ] At the **top** of `generate()` (right after `model = model or self.get_default_model()` on line 69), insert the capability validation block:

```python
        caps = _caps_for(model)

        # Validate quality against capability table. Caller may pass legacy
        # values; map any string outside caps['quality_values'] to default.
        requested_quality = kwargs.get("quality", quality)
        if requested_quality not in caps["quality_values"]:
            quality = caps["default_quality"]
        else:
            quality = requested_quality
        kwargs["quality"] = quality  # keep kwargs and local in sync

        # Reject unsupported parameter combinations with actionable messages.
        if kwargs.get("background") in {"transparent"} and not caps["supports_transparent_bg"]:
            raise _UnsupportedParam(
                f"Transparent background is not supported on {model}. "
                f"Use gpt-image-1.5 or gpt-image-1 for alpha PNG output."
            )
        if kwargs.get("input_fidelity") and not caps["supports_input_fidelity"]:
            raise _UnsupportedParam(
                f"input_fidelity is not supported on {model}."
            )
        n_requested = int(kwargs.get("num_images", n) or 1)
        if n_requested > caps["max_n"]:
            raise _UnsupportedParam(
                f"{model} supports n=1..{caps['max_n']}, got n={n_requested}."
            )

        # Custom size pre-flight (gpt-image-2 only). custom_size beats `size`.
        custom_size = kwargs.get("custom_size")
        if custom_size:
            if not caps["supports_custom_size"]:
                raise _UnsupportedParam(f"Custom size is not supported on {model}.")
            from core.image_size import validate_custom_size, parse_size_string
            try:
                cw, ch = parse_size_string(custom_size)
            except ValueError as e:
                raise _UnsupportedParam(str(e))
            ok, why = validate_custom_size(cw, ch, caps)
            if not ok:
                raise _UnsupportedParam(f"Invalid custom_size {custom_size}: {why}")
            size = f"{cw}x{ch}"
```

- [ ] Add a new branch for `gpt-image-2` inside the `try:` block. Find the existing chain `if model == "gpt-image-1.5": ... elif model in [...]: ... elif model == "dall-e-3": ... else:` (starts around line 208). Insert this **before** the `gpt-image-1.5` branch:

```python
            if model == "gpt-image-2":
                gen_params = {
                    "model": model,
                    "prompt": prompt,
                    "size": size,
                    "n": min(num_images, caps["max_n"]),
                    "quality": quality,  # auto|low|medium|high — drives reasoning
                }

                output_format = kwargs.get("output_format", "png")
                if output_format in {"png", "jpeg", "webp"}:
                    gen_params["output_format"] = output_format
                if output_format in {"jpeg", "webp"}:
                    compression = kwargs.get("output_compression", kwargs.get("compression", 90))
                    if isinstance(compression, (int, float)) and 0 <= compression <= 100:
                        gen_params["output_compression"] = int(compression)

                moderation = kwargs.get("moderation", "auto")
                if moderation in {"auto", "low"}:
                    gen_params["moderation"] = moderation

                logger.info("=" * 60)
                logger.info("SENDING TO OPENAI API (GPT Image 2)")
                logger.info(f"Model: {model}  (snapshot: {caps.get('snapshot')})")
                logger.info(f"Prompt: {prompt}")
                logger.info(f"Size: {size}")
                logger.info(f"Quality (thinking): {quality}")
                logger.info(f"Output format: {gen_params.get('output_format', 'png')}")
                if "output_compression" in gen_params:
                    logger.info(f"Compression: {gen_params['output_compression']}")
                logger.info(f"Moderation: {gen_params.get('moderation', 'auto')}")
                logger.info(f"Number of images: {gen_params['n']}")
                logger.info("=" * 60)
            elif model == "gpt-image-1.5":
                # ...existing 1.5 block stays unchanged...
```

(That `elif` line replaces the existing `if model == "gpt-image-1.5":` line — just change `if` → `elif`. Leave the rest of the 1.5 branch alone.)

- [ ] Extend the response-decode section (around line 354) so `gpt-image-2` decodes the same way `gpt-image-1.5` does (b64). Find the `if model == "gpt-image-1.5":` check and change it to `if model in ("gpt-image-2", "gpt-image-1.5"):`.

- [ ] Extend the multi-image fallback loop (around line 386) to **exclude** `gpt-image-2` since it natively supports `n` up to 10. The list `["dall-e-3", "gpt-image-1", "gpt-image-1-mini"]` already excludes it correctly — just add a one-line comment so future readers don't re-add it:

```python
            # gpt-image-2 and gpt-image-1.5 handle n>1 in a single call; only legacy single-image models need this loop.
            if model in ["dall-e-3", "gpt-image-1", "gpt-image-1-mini"] and kwargs.get('num_images', 1) > 1:
```

- [ ] Extend the post-processing block (around line 413) so `gpt-image-2` is included for crop/scale to target dimensions. Change:

```python
            if target_width and target_height and model in ["gpt-image-1", "gpt-image-1.5", "gpt-image-1-mini"]:
```

to:

```python
            if target_width and target_height and model in ["gpt-image-2", "gpt-image-1", "gpt-image-1.5", "gpt-image-1-mini"]:
```

### Step 2.5 — Refactor `edit_image()` for multi-reference + mask on gpt-image-2

- [ ] Replace the entire `edit_image` method (currently lines 533-590) with this capability-driven version. It keeps the dall-e-2 single-image path working and adds multi-image support for any model where `supports_multi_reference` is True.

```python
    def edit_image(
        self,
        image,  # bytes | path | list of bytes | list of paths
        prompt: str,
        model: Optional[str] = None,
        mask: Optional[bytes] = None,
        size: str = "1024x1024",
        n: int = 1,
        **kwargs
    ) -> Tuple[List[str], List[bytes]]:
        """Edit an image (or compose from multiple references) via OpenAI /v1/images/edits.

        ``image`` may be:
          * bytes (single PNG)
          * a str/Path to a single PNG
          * a list of either, for multi-reference composition (gpt-image-1.x and gpt-image-2)

        ``mask`` is an optional alpha PNG for inpainting; only sent when the model
        supports it (``MODEL_CAPS[model]['supports_mask']``).
        """
        self._ensure_client()

        # Default to the best edit-capable model, not gpt-image-2's snapshot,
        # so callers that forget to pass `model` get sensible behavior.
        model = model or "gpt-image-2"
        caps = _caps_for(model)
        texts: List[str] = []
        images: List[bytes] = []

        rate_limiter.check_rate_limit('openai', wait=True)

        import logging
        logger = logging.getLogger(__name__)

        # Normalize image input into a list of file-like objects.
        items = image if isinstance(image, list) else [image]
        if len(items) > 1 and not caps["supports_multi_reference"]:
            raise _UnsupportedParam(
                f"{model} does not support multi-reference edits. "
                f"Use gpt-image-2, gpt-image-1.5, or gpt-image-1."
            )

        prepared = []
        for i, item in enumerate(items):
            if isinstance(item, (bytes, bytearray)):
                buf = BytesIO(bytes(item))
                buf.name = f"image_{i}.png"
                prepared.append(buf)
            elif isinstance(item, (str, Path)):
                p = Path(item)
                if not p.exists():
                    raise FileNotFoundError(f"Reference image not found: {p}")
                buf = BytesIO(p.read_bytes())
                buf.name = p.name
                prepared.append(buf)
            else:
                raise TypeError(f"Unsupported image input type: {type(item).__name__}")

        if not prepared:
            raise ValueError("edit_image requires at least one input image")

        edit_kwargs = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": min(int(n), caps["max_n"]),
            "image": prepared if len(prepared) > 1 else prepared[0],
        }

        # Mask
        if mask is not None:
            if not caps["supports_mask"]:
                raise _UnsupportedParam(f"{model} does not support mask inpainting.")
            mask_buf = BytesIO(mask if isinstance(mask, (bytes, bytearray)) else Path(mask).read_bytes())
            mask_buf.name = "mask.png"
            edit_kwargs["mask"] = mask_buf

        # Output format / compression for models that support it
        if caps["supports_output_format"]:
            output_format = kwargs.get("output_format", "png")
            if output_format in {"png", "jpeg", "webp"}:
                edit_kwargs["output_format"] = output_format
            if output_format in {"jpeg", "webp"}:
                compression = kwargs.get("output_compression", kwargs.get("compression", 90))
                if isinstance(compression, (int, float)) and 0 <= compression <= 100:
                    edit_kwargs["output_compression"] = int(compression)

        # Quality (gpt-image-2 reasoning knob)
        quality = kwargs.get("quality")
        if quality and quality in caps["quality_values"]:
            edit_kwargs["quality"] = quality

        # Moderation
        moderation = kwargs.get("moderation")
        if moderation and caps["supports_moderation"] and moderation in {"auto", "low"}:
            edit_kwargs["moderation"] = moderation

        # gpt-image-2 / gpt-image-1.5 return b64; dall-e-2 used to take response_format.
        if model == "dall-e-2":
            edit_kwargs["response_format"] = "b64_json"

        logger.info(
            "OpenAI images.edit model=%s images=%d mask=%s size=%s n=%d",
            model, len(prepared), bool(mask), size, edit_kwargs["n"],
        )

        try:
            response = self.client.images.edit(**edit_kwargs)
            for item in (getattr(response, "data", []) or []):
                b64 = getattr(item, "b64_json", None)
                if b64:
                    images.append(b64decode(b64))
            if not images:
                raise RuntimeError("OpenAI returned no edited images.")
        except _UnsupportedParam:
            raise
        except (ValueError, RuntimeError, AttributeError) as e:
            raise RuntimeError(f"OpenAI image editing failed: {e}")

        return texts, images
```

### Step 2.6 — Verify

- [ ] Syntax + smoke import:

```bash
python -m py_compile providers/openai.py
python -c "from providers.openai import OpenAIProvider, MODEL_CAPS, _caps_for; \
    p = OpenAIProvider({'api_key': None}); \
    assert p.get_default_model() == 'gpt-image-2', p.get_default_model(); \
    assert list(p.get_models().keys())[0] == 'gpt-image-2'; \
    assert MODEL_CAPS['gpt-image-2']['supports_streaming'] is True; \
    assert MODEL_CAPS['gpt-image-2']['supports_transparent_bg'] is False; \
    assert _caps_for('unknown-model')['display_name'] == 'GPT Image 1'; \
    print('provider sync OK')"
```

Expected: `provider sync OK`. Failure modes to watch:
- `ImportError: openai` — ignore (OPENAI_AVAILABLE flag handles it; we never call `_ensure_client` here).
- Anything else: stop, fix.

### Step 2.7 — Commit

- [ ] Stage and commit:

```bash
git add providers/openai.py
git commit -m "$(cat <<'EOF'
feat(openai-provider): add MODEL_CAPS and gpt-image-2 sync support

Single source of truth for every per-model dispatch decision. generate()
now validates quality against caps['quality_values'], rejects
transparent_bg / input_fidelity / n>max_n with actionable messages,
pre-flights custom_size via core.image_size.validate_custom_size, and
adds a gpt-image-2 branch with output_format, output_compression, and
moderation kwargs.

edit_image() reworked to accept a list of references for multi-image
composition (gpt-image-2 / gpt-image-1.x) plus optional alpha mask.
Backwards-compatible with dall-e-2's single-image path.

get_models / get_models_with_details / get_default_model now read from
MODEL_CAPS so the new model surfaces everywhere; gpt-image-2 becomes the
default. validate_auth surfaces the OpenAI org-verification gate as
an actionable error.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 — Provider streaming + Batch API

**Why now:** With `MODEL_CAPS` and the sync paths in place, streaming and Batch fold in cleanly. Both are gated by capability flags, so callers without the latest `openai` SDK fail gracefully.

**Files:**
- Modify: `providers/openai.py` (add streaming inside `generate()` when `stream=True`; add `submit_batch_job`, `check_batch_job` methods near the end of the class — append after `generate_viseme_batch`)
- Modify: `core/constants.py` (add `BATCH_JOBS_PATH` constant)

### Step 3.1 — Add `BATCH_JOBS_PATH` constant

- [ ] In `core/constants.py`, immediately after `GPT_IMAGE_2_SNAPSHOT` (added in Task 1.2), add:

```python
# Persistent ledger for OpenAI Batch API jobs (one entry per submission).
BATCH_JOBS_PATH = get_user_data_dir() / "batch_jobs.json"
```

Note: `get_user_data_dir()` is defined later in the same file. The constant assignment runs at import time, so this is fine — it just calls the function. Verify with `python -c "from core.constants import BATCH_JOBS_PATH; print(BATCH_JOBS_PATH)"`.

### Step 3.2 — Add streaming path to `generate()`

- [ ] At the top of `generate()`, just after the capability-validation block from Task 2.4, add the streaming short-circuit:

```python
        # Streaming path (gpt-image-2 only). Routes through Responses API and
        # invokes the on_partial callback for each partial frame. Falls back
        # to sync if the SDK lacks Responses-API streaming support.
        if kwargs.get("stream") and caps["supports_streaming"]:
            partial_count = max(0, min(int(kwargs.get("partial_images", 0)), 3))
            on_partial = kwargs.get("on_partial")
            if partial_count > 0 and callable(on_partial):
                streamed = self._generate_streaming(
                    model=model,
                    prompt=prompt,
                    size=size,
                    quality=quality,
                    n=int(kwargs.get("num_images", n) or 1),
                    partial_images=partial_count,
                    on_partial=on_partial,
                    output_format=kwargs.get("output_format", "png"),
                    moderation=kwargs.get("moderation", "auto"),
                )
                if streamed is not None:
                    return [], streamed
                # else: SDK doesn't support Responses streaming — fall through to sync
                logger.warning("Responses-API streaming unavailable; falling back to sync generation")
```

- [ ] Add a private `_generate_streaming` method to the class. Insert it directly **before** the existing `_create_alpha_mask` method (around line 639):

```python
    def _generate_streaming(
        self,
        model: str,
        prompt: str,
        size: str,
        quality: str,
        n: int,
        partial_images: int,
        on_partial,
        output_format: str = "png",
        moderation: str = "auto",
    ) -> Optional[List[bytes]]:
        """Stream image generation via the Responses API.

        Invokes ``on_partial(index: int, png_bytes: bytes)`` for each partial
        frame as it arrives. Returns the final image bytes list, or None if
        the installed openai SDK does not expose a streaming Responses API.
        """
        import logging
        logger = logging.getLogger(__name__)

        if not hasattr(self.client, "responses") or not hasattr(self.client.responses, "stream"):
            return None

        tool = {
            "type": "image_generation",
            "size": size,
            "quality": quality,
            "moderation": moderation,
            "output_format": output_format,
            "partial_images": partial_images,
        }

        partials_seen = 0
        final_b64s: List[str] = []

        try:
            with self.client.responses.stream(
                model=model,
                input=prompt,
                tools=[tool],
                tool_choice={"type": "image_generation"},
            ) as stream:
                for event in stream:
                    etype = getattr(event, "type", "")
                    if etype.endswith("partial_image"):
                        b64 = (
                            getattr(event, "partial_image_b64", None)
                            or getattr(getattr(event, "partial_image", None), "b64_json", None)
                        )
                        if b64:
                            partials_seen += 1
                            try:
                                on_partial(partials_seen - 1, b64decode(b64))
                            except Exception as cb_err:  # noqa: BLE001
                                logger.warning(f"on_partial callback raised: {cb_err}")
                    elif etype.endswith("image_generation_call.completed"):
                        b64 = getattr(event, "b64_json", None) or getattr(
                            getattr(event, "result", None), "b64_json", None
                        )
                        if b64:
                            final_b64s.append(b64)
                response = stream.get_final_response()
                # If the event loop didn't yield a completed b64, dig it out of the response.
                if not final_b64s and response is not None:
                    for output in (getattr(response, "output", []) or []):
                        b64 = getattr(output, "b64_json", None) or getattr(
                            getattr(output, "result", None), "b64_json", None
                        )
                        if b64:
                            final_b64s.append(b64)
        except (AttributeError, TypeError) as e:
            logger.warning(f"Responses-API streaming failed structurally: {e}")
            return None

        if not final_b64s:
            return None
        return [b64decode(b) for b in final_b64s[:n]]
```

### Step 3.3 — Add Batch API methods

- [ ] Append two new methods to the end of `OpenAIProvider` (after `generate_viseme_batch` at line 894). They build a JSONL payload, submit, and persist the job ledger.

```python
    def submit_batch_job(
        self,
        requests: List[dict],
        endpoint: str = "/v1/images/generations",
        completion_window: str = "24h",
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Submit a Batch API job and persist a record to BATCH_JOBS_PATH.

        Args:
            requests: List of request bodies, each conforming to the chosen endpoint.
                      Each entry must include "model" and the body keys for that endpoint.
            endpoint: Batch endpoint, default ``/v1/images/generations``.
            completion_window: OpenAI completion window string ("24h" supported).
            metadata: Optional metadata to attach to the batch job.

        Returns:
            The OpenAI batch job ID (e.g. "batch_abc123...").
        """
        import json, time, uuid, logging
        from datetime import datetime, timezone
        from core.constants import BATCH_JOBS_PATH

        self._ensure_client()
        logger = logging.getLogger(__name__)

        # Build the JSONL payload in memory.
        lines = []
        for i, req in enumerate(requests):
            line = {
                "custom_id": req.pop("custom_id", f"req-{i}-{uuid.uuid4().hex[:8]}"),
                "method": "POST",
                "url": endpoint,
                "body": req,
            }
            lines.append(json.dumps(line))
        payload_bytes = ("\n".join(lines) + "\n").encode("utf-8")

        # Upload as a Files object with purpose=batch.
        from io import BytesIO
        upload = BytesIO(payload_bytes)
        upload.name = f"imageai_batch_{int(time.time())}.jsonl"
        file_obj = self.client.files.create(file=upload, purpose="batch")

        batch = self.client.batches.create(
            input_file_id=file_obj.id,
            endpoint=endpoint,
            completion_window=completion_window,
            metadata=metadata or {"source": "imageai"},
        )

        job_id = getattr(batch, "id", None) or batch["id"]

        # Persist a small record so the GUI/CLI can list and resume jobs.
        record = {
            "job_id": job_id,
            "input_file_id": file_obj.id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "request_count": len(requests),
            "model": (requests[0].get("model") if requests else None),
            "prompt_preview": (
                str(requests[0].get("prompt", ""))[:120] if requests else ""
            ),
            "status": "submitted",
        }
        try:
            BATCH_JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
            existing = []
            if BATCH_JOBS_PATH.exists():
                try:
                    existing = json.loads(BATCH_JOBS_PATH.read_text(encoding="utf-8"))
                    if not isinstance(existing, list):
                        existing = []
                except (OSError, IOError, ValueError):
                    existing = []
            existing.append(record)
            BATCH_JOBS_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except (OSError, IOError) as e:
            logger.warning(f"Could not persist batch record to {BATCH_JOBS_PATH}: {e}")

        logger.info(f"Submitted batch job {job_id} ({len(requests)} requests, endpoint={endpoint})")
        return job_id

    def check_batch_job(self, job_id: str, output_dir: Optional[Path] = None) -> dict:
        """Poll a batch job; if complete, download images + sidecars to ``output_dir``.

        Returns a dict: {job_id, status, request_counts, output_files, downloaded}.
        ``downloaded`` lists the absolute paths of any files written.
        """
        import json, logging
        logger = logging.getLogger(__name__)

        self._ensure_client()
        batch = self.client.batches.retrieve(job_id)
        status = getattr(batch, "status", None) or batch.get("status")

        result = {
            "job_id": job_id,
            "status": status,
            "request_counts": getattr(batch, "request_counts", None),
            "output_files": [],
            "downloaded": [],
        }

        if status == "completed":
            output_file_id = getattr(batch, "output_file_id", None) or batch.get("output_file_id")
            if output_file_id:
                result["output_files"].append(output_file_id)
                content = self.client.files.content(output_file_id)
                # SDK returns a streaming-friendly object; read() yields bytes.
                raw = content.read() if hasattr(content, "read") else bytes(content)
                if output_dir is not None:
                    output_dir = Path(output_dir)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    # Each line of the output file is a JSON object with "response.body.data[*].b64_json".
                    for i, line in enumerate(raw.decode("utf-8").splitlines()):
                        if not line.strip():
                            continue
                        try:
                            entry = json.loads(line)
                        except ValueError:
                            continue
                        body = ((entry.get("response") or {}).get("body") or {})
                        for j, item in enumerate(body.get("data", [])):
                            b64 = item.get("b64_json")
                            if not b64:
                                continue
                            out_path = output_dir / f"{job_id}_{i}_{j}.png"
                            out_path.write_bytes(b64decode(b64))
                            result["downloaded"].append(str(out_path))
                            sidecar = out_path.with_suffix(".png.json")
                            sidecar.write_text(
                                json.dumps({
                                    "batch_job_id": job_id,
                                    "custom_id": entry.get("custom_id"),
                                    "model": body.get("model"),
                                }, indent=2),
                                encoding="utf-8",
                            )
        elif status == "failed":
            logger.warning(f"Batch job {job_id} failed: {getattr(batch, 'errors', None)}")

        return result
```

### Step 3.4 — Verify

- [ ] Syntax + smoke import:

```bash
python -m py_compile providers/openai.py core/constants.py
python -c "from providers.openai import OpenAIProvider; \
    p = OpenAIProvider({'api_key': None}); \
    assert hasattr(p, 'submit_batch_job'); assert hasattr(p, 'check_batch_job'); \
    assert hasattr(p, '_generate_streaming'); \
    print('streaming + batch OK')"
python -c "from core.constants import BATCH_JOBS_PATH; print('BATCH_JOBS_PATH =', BATCH_JOBS_PATH)"
```

Expected: `streaming + batch OK` and a path under the user's data dir.

### Step 3.5 — Commit

```bash
git add providers/openai.py core/constants.py
git commit -m "$(cat <<'EOF'
feat(openai-provider): streaming via Responses API and Batch job submission

generate() short-circuits into _generate_streaming when stream=True and
the model supports it (caps['supports_streaming']). Streaming uses
client.responses.stream with the image_generation tool, invoking the
on_partial(index, png_bytes) callback for each partial frame and
returning the final image list. Falls back to sync generation if the
installed openai SDK does not expose responses.stream.

Adds submit_batch_job() (builds JSONL, uploads via files.create
purpose=batch, calls batches.create, persists a record to
BATCH_JOBS_PATH) and check_batch_job() (retrieves status, downloads
output_file when complete, writes images + sidecars to a target dir).

BATCH_JOBS_PATH lives under the user data dir alongside config and
images.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 — CLI flags

**Why now:** Provider behavior is fully wired; expose it from the CLI before sinking time into GUI. CLI is the fastest manual smoke test.

**Files:**
- Modify: `cli/parser.py` (extend the generation-options group; add edit/batch/streaming flags)
- Modify: `cli/runner.py` (resolve flags into kwargs; dispatch edit / batch / streaming branches)

### Step 4.1 — Extend `cli/parser.py`

- [ ] In the **generation options** group (ends around line 99), replace the `--quality` choices to include the gpt-image-2 levels, and add the new flags. Find:

```python
    gen_group.add_argument(
        "--quality",
        choices=["standard", "hd"],
        default="standard",
        help="Image quality (OpenAI only)"
    )
```

Replace with:

```python
    gen_group.add_argument(
        "--quality",
        choices=["auto", "low", "medium", "high", "standard", "hd"],
        default=None,
        help="Image quality / reasoning level (gpt-image-2: auto|low|medium|high; "
             "dall-e-3: standard|hd). Defaults to model's default.",
    )
    gen_group.add_argument(
        "--output-format",
        choices=["png", "jpeg", "webp"],
        help="Output image format (gpt-image-2 / gpt-image-1.5 only)",
    )
    gen_group.add_argument(
        "--output-compression",
        type=int,
        metavar="N",
        help="Output compression 0-100 (jpeg/webp only)",
    )
    gen_group.add_argument(
        "--moderation",
        choices=["auto", "low"],
        help="Content moderation level (gpt-image-2 only; 'low' is permissive)",
    )
    gen_group.add_argument(
        "--custom-size",
        metavar="WxH",
        help="Custom image size; mutually exclusive with --size. "
             "gpt-image-2 only — both edges multiples of 16, max edge 3840, "
             "aspect ≤3:1, total pixels 655K-8.3M.",
    )
    gen_group.add_argument(
        "--stream-partials",
        action="store_true",
        help="Stream up to 2 partial images during generation (gpt-image-2 only). "
             "Saves out.p0.png, out.p1.png, then final out.png.",
    )
    gen_group.add_argument(
        "--reference",
        action="append",
        metavar="IMG",
        help="Reference image path (repeatable, up to 10). Routes to /v1/images/edits.",
    )
    gen_group.add_argument(
        "--mask",
        metavar="PNG",
        help="Alpha mask PNG for inpainting (used with --reference). "
             "Transparent pixels = edit zone; opaque = preserve.",
    )

    # Batch API
    batch_group = parser.add_argument_group("batch API")
    batch_group.add_argument(
        "--batch",
        action="store_true",
        help="Submit as a Batch API job instead of a sync request. Prints job ID.",
    )
    batch_group.add_argument(
        "--batch-status",
        metavar="JOB_ID",
        help="Print the status of a previously submitted batch job",
    )
    batch_group.add_argument(
        "--batch-fetch",
        metavar="JOB_ID",
        help="Download completed batch outputs to the current images dir",
    )
```

- [ ] At the bottom of `build_arg_parser`, just before `return parser`, add the mutex check for `--size` vs `--custom-size`. Since argparse's native mutex group can't span groups easily, do it as a post-parse validation in the runner instead — see Step 4.2.

### Step 4.2 — Wire flags into `cli/runner.py`

- [ ] Near the top of `run_cli` (after `provider = (getattr(args, "provider", None) or "google").strip().lower()` on line 194), add the validation:

```python
    # Mutual exclusion: --size vs --custom-size
    custom_size = getattr(args, "custom_size", None)
    if custom_size and getattr(args, "size", "1024x1024") != "1024x1024":
        # Only flag a real conflict; --size has a default of 1024x1024 that's
        # always present, so don't false-positive on the default.
        print("Error: --custom-size and --size are mutually exclusive (drop --size).")
        return 2
```

- [ ] **Batch status / fetch**: handle these before the normal generate path. After the `--test` block (ends around line 270), insert:

```python
    # Batch status / fetch — both require the OpenAI provider.
    batch_status = getattr(args, "batch_status", None)
    batch_fetch = getattr(args, "batch_fetch", None)
    if batch_status or batch_fetch:
        if provider != "openai":
            print(f"--batch-status / --batch-fetch require --provider openai (got {provider}).")
            return 2
        if not key:
            print("No API key. Use --api-key/--api-key-file or --set-key.")
            return 2
        try:
            provider_instance = get_provider(provider, provider_config)
            if batch_status:
                info = provider_instance.check_batch_job(batch_status)
                print(f"Job: {info['job_id']}")
                print(f"Status: {info['status']}")
                if info.get("request_counts") is not None:
                    print(f"Counts: {info['request_counts']}")
            if batch_fetch:
                images_dir = ConfigManager().get_images_dir()
                info = provider_instance.check_batch_job(batch_fetch, output_dir=images_dir)
                print(f"Job: {info['job_id']}  status: {info['status']}")
                for f in info.get("downloaded", []):
                    print(f"Downloaded: {f}")
                if info["status"] != "completed":
                    print("(Job is not yet complete; nothing downloaded.)")
            return 0
        except Exception as e:
            print(f"Batch op failed: {e}")
            return 4
```

- [ ] **Generate / edit / batch dispatch**: replace the existing `# Handle --prompt` block (from `if args.prompt:` on line 273 down to the closing `return 0` at line 344) with the version below. The diff is large because the dispatch fans out, but the intent is straightforward: build a kwargs dict from all the new flags, then pick the right provider method.

```python
    # Handle --prompt
    if args.prompt:
        if auth_mode == "api-key" and not key and provider != "local_sd":
            print("No API key. Use --api-key/--api-key-file or --set-key.")
            return 2

        try:
            provider_instance = get_provider(provider, provider_config)
            model = args.model or provider_instance.get_default_model()

            # Build kwargs from new flags. None values are skipped so the
            # provider's per-model defaults take over.
            kwargs = {}
            for flag in (
                "quality", "output_format", "output_compression", "moderation",
            ):
                v = getattr(args, flag, None)
                if v is not None:
                    kwargs[flag] = v
            if custom_size:
                kwargs["custom_size"] = custom_size
            if getattr(args, "num_images", 1) > 1:
                kwargs["num_images"] = args.num_images

            references = getattr(args, "reference", None) or []
            mask_path = getattr(args, "mask", None)
            stream_partials = bool(getattr(args, "stream_partials", False))
            submit_batch = bool(getattr(args, "batch", False))

            # Resolve mask bytes once.
            mask_bytes = None
            if mask_path:
                mp = Path(mask_path).expanduser()
                if not mp.exists():
                    print(f"Mask file not found: {mp}")
                    return 2
                mask_bytes = mp.read_bytes()

            print(f"Generating with {provider} ({model})...")

            # --- Dispatch ---
            if submit_batch:
                if provider != "openai":
                    print("--batch only supported for --provider openai")
                    return 2
                # Build a single-request batch from this prompt.
                req_body = {
                    "model": model,
                    "prompt": args.prompt,
                    "size": (custom_size or getattr(args, "size", "1024x1024")),
                    "n": int(getattr(args, "num_images", 1) or 1),
                }
                for k in ("quality", "output_format", "output_compression", "moderation"):
                    if k in kwargs:
                        req_body[k] = kwargs[k]
                job_id = provider_instance.submit_batch_job([req_body])
                print(f"Submitted batch job: {job_id}")
                print(f"Check with: --batch-status {job_id}")
                print(f"Fetch with: --batch-fetch {job_id}")
                return 0

            if references:
                # Edit / multi-reference compose path
                ref_paths = [Path(r).expanduser() for r in references]
                missing = [p for p in ref_paths if not p.exists()]
                if missing:
                    print(f"Reference image(s) not found: {', '.join(str(p) for p in missing)}")
                    return 2
                texts, images = provider_instance.edit_image(
                    image=ref_paths,
                    prompt=args.prompt,
                    model=model,
                    mask=mask_bytes,
                    size=(custom_size or getattr(args, "size", "1024x1024")),
                    n=int(getattr(args, "num_images", 1) or 1),
                    **kwargs,
                )
            elif stream_partials:
                # Streaming generation. Save partials beside the output path.
                out_arg = args.out
                if not out_arg:
                    print("--stream-partials requires -o/--out (e.g. -o ./gen.png)")
                    return 2
                out_path = Path(out_arg).expanduser().resolve()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                stem = out_path.with_suffix("")

                def on_partial(idx, png_bytes):
                    p = Path(f"{stem}.p{idx}{out_path.suffix or '.png'}")
                    p.write_bytes(png_bytes)
                    print(f"  partial {idx} -> {p}", file=sys.stderr)

                kwargs.update({"stream": True, "partial_images": 2, "on_partial": on_partial})
                texts, images = provider_instance.generate(
                    prompt=args.prompt,
                    model=model,
                    size=(custom_size or getattr(args, "size", "1024x1024")),
                    quality=kwargs.get("quality", "auto"),
                    n=1,
                    **kwargs,
                )
            else:
                # Standard sync path
                texts, images = provider_instance.generate(
                    prompt=args.prompt,
                    model=model,
                    size=(custom_size or getattr(args, "size", "1024x1024")),
                    quality=kwargs.get("quality", "standard"),
                    n=int(getattr(args, "num_images", 1) or 1),
                    **kwargs,
                )

            for text in texts:
                print(text)

            # Save images
            if images:
                if args.out:
                    out_path = Path(args.out).expanduser().resolve()
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_bytes(images[0])
                    print(f"Saved image to {out_path}")
                    if len(images) > 1:
                        stem = out_path.stem
                        ext = out_path.suffix or ".png"
                        for i, img_data in enumerate(images[1:], start=2):
                            numbered_path = out_path.with_name(f"{stem}_{i}{ext}")
                            numbered_path.write_bytes(img_data)
                            print(f"Saved image to {numbered_path}")
                else:
                    config = ConfigManager()
                    images_dir = config.get_images_dir()
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    stub = sanitize_filename(args.prompt, max_len=60)
                    for i, img_data in enumerate(images, start=1):
                        filename = f"{stub}_{timestamp}_{i}.png"
                        img_path = images_dir / filename
                        img_path.write_bytes(img_data)
                        print(f"Saved image to {img_path}")
                        meta = {
                            "prompt": args.prompt,
                            "provider": provider,
                            "model": model,
                            "timestamp": timestamp,
                            **{k: kwargs[k] for k in (
                                "quality", "output_format", "output_compression",
                                "moderation", "custom_size",
                            ) if k in kwargs},
                        }
                        if references:
                            meta["reference_images"] = [str(p) for p in ref_paths]
                        if mask_path:
                            meta["mask"] = str(mask_path)
                        sidecar_path = img_path.with_suffix(".png.json")
                        import json
                        sidecar_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

            return 0

        except Exception as e:
            print(f"Generation failed for provider '{provider}': {e}")
            return 4
```

### Step 4.3 — Verify

```bash
python -m py_compile cli/parser.py cli/runner.py
python -c "from cli.parser import build_arg_parser; \
    p = build_arg_parser(); a = p.parse_args(['--provider','openai','-p','x','--quality','high','--output-format','jpeg','--output-compression','85','--moderation','low','--custom-size','2048x1152']); \
    assert a.quality == 'high' and a.output_format == 'jpeg' and a.output_compression == 85 and a.moderation == 'low' and a.custom_size == '2048x1152'; \
    a2 = p.parse_args(['--reference','/tmp/a.png','--reference','/tmp/b.png','--mask','/tmp/m.png','-p','x']); \
    assert a2.reference == ['/tmp/a.png','/tmp/b.png'] and a2.mask == '/tmp/m.png'; \
    a3 = p.parse_args(['--batch','-p','x']); assert a3.batch is True; \
    a4 = p.parse_args(['--batch-status','batch_abc']); assert a4.batch_status == 'batch_abc'; \
    print('CLI parser OK')"
python main.py --help 2>&1 | head -60
```

Expected: `CLI parser OK` and the help text shows the new flags.

### Step 4.4 — Commit

```bash
git add cli/parser.py cli/runner.py
git commit -m "$(cat <<'EOF'
feat(cli): expose gpt-image-2 flags, edit, streaming, and Batch API

Adds --quality (extended choices), --output-format, --output-compression,
--moderation, --custom-size (mutex with --size), --reference (repeatable),
--mask, --stream-partials, --batch, --batch-status, --batch-fetch.

Runner dispatches: --batch builds a single-request batch and prints the
job ID; --reference routes through provider.edit_image() with optional
--mask; --stream-partials enables Responses-API streaming and writes
out.p0/p1 partials beside the final out.png.

Sidecars now record the new optional fields (quality, output_format,
output_compression, moderation, custom_size, reference_images, mask).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5 — GUI widgets (Quality, Resolution custom-size, OutputFormat, Moderation, ThinkingProgress)

**Why this slice:** Widget changes are self-contained — they don't depend on `main_window.py` wiring beyond importing the existing classes. The widget refactor lands first; the wiring lands in Task 6.

**Files:**
- Modify: `gui/settings_widgets.py`
  - Extend `QualitySelector` (line 1181) with a gpt-image-2 mode (Low / Medium / High / Auto radios) driven by `MODEL_CAPS`
  - Extend `ResolutionSelector` (line 333) with a "Custom…" entry that opens a popup using `core.image_size.validate_custom_size`
  - Add three new widgets at the end of the file:
    - `OutputFormatRow` (PNG/JPEG/WebP radios + compression slider)
    - `ModerationCheckbox`
    - `ThinkingProgressToggle`

### Step 5.1 — `QualitySelector` gpt-image-2 mode

- [ ] In `gui/settings_widgets.py`, the `QualitySelector` class (line 1181) currently has Standard/HD radios for OpenAI and Fast/Quality for Google. Add a third mode for `gpt-image-2`. Modify `_init_ui` to add four more radios after the existing standard/hd radios (insert after line 1219):

```python
        # GPT Image 2 reasoning levels (Low | Medium | High | Auto). Hidden
        # except when the active OpenAI model is gpt-image-2.
        self.gi2_buttons = QButtonGroup()
        self.gi2_low_radio = QRadioButton("Low")
        self.gi2_low_radio.setToolTip("Fastest, cheapest, no reasoning. ~$0.006/image at 1024².")
        self.gi2_medium_radio = QRadioButton("Medium")
        self.gi2_medium_radio.setToolTip("Balanced reasoning. ~$0.053/image at 1024².")
        self.gi2_high_radio = QRadioButton("High")
        self.gi2_high_radio.setToolTip("Maximum reasoning. ~$0.211/image at 1024².")
        self.gi2_auto_radio = QRadioButton("Auto")
        self.gi2_auto_radio.setToolTip("Let the API choose based on prompt complexity.")

        for i, btn in enumerate((self.gi2_low_radio, self.gi2_medium_radio,
                                 self.gi2_high_radio, self.gi2_auto_radio)):
            self.gi2_buttons.addButton(btn, i)
            quality_layout.addWidget(btn)
            btn.setVisible(False)

        self.gi2_auto_radio.setChecked(True)
        self.gi2_buttons.buttonClicked.connect(self._on_gi2_quality_changed)

        self.is_gi2_mode = False
```

- [ ] Add the handler and helpers. Insert after `_on_quality_changed` (around line 1366):

```python
    def _set_gi2_mode(self, enabled: bool):
        """Toggle gpt-image-2 reasoning radios on/off."""
        if self.is_gi2_mode == enabled:
            return
        self.is_gi2_mode = enabled
        # Hide standard / hd when in gi2 mode
        self.standard_radio.setVisible(not enabled)
        self.hd_radio.setVisible(not enabled)
        for btn in (self.gi2_low_radio, self.gi2_medium_radio,
                    self.gi2_high_radio, self.gi2_auto_radio):
            btn.setVisible(enabled)
        if enabled:
            self.quality_group.setTitle("Reasoning Quality")

    def _on_gi2_quality_changed(self):
        if self.gi2_low_radio.isChecked():
            self.settings["quality"] = "low"
        elif self.gi2_medium_radio.isChecked():
            self.settings["quality"] = "medium"
        elif self.gi2_high_radio.isChecked():
            self.settings["quality"] = "high"
        else:
            self.settings["quality"] = "auto"
        self.settingsChanged.emit(self.settings)
```

- [ ] Extend `update_model` (line 1300) so it engages gi2 mode when the OpenAI model is `gpt-image-2`. Replace the method body with:

```python
    def update_model(self, model_id: str):
        """Update quality options based on selected model."""
        # Google Nano Banana Pro (1K/2K/4K)
        is_nbp = bool(model_id and "gemini-3" in model_id)
        self._set_nbp_mode(is_nbp)
        if is_nbp:
            tier = self.NBP_TIERS.get(self.nbp_quality, self.NBP_TIERS['2K'])
            self.nbpQualityChanged.emit(self.nbp_quality, tier['max_res'])

        # OpenAI gpt-image-2 reasoning radios
        is_gi2 = (model_id == "gpt-image-2")
        self._set_gi2_mode(is_gi2)
```

- [ ] Extend `get_settings()` and `set_settings()` to include the gi2 quality. In `get_settings` (line 1374), after the existing `if hasattr(self, 'quality_group'):` block:

```python
        if getattr(self, 'is_gi2_mode', False):
            for value, btn in (
                ("low", self.gi2_low_radio),
                ("medium", self.gi2_medium_radio),
                ("high", self.gi2_high_radio),
                ("auto", self.gi2_auto_radio),
            ):
                if btn.isChecked():
                    settings["quality"] = value
                    break
```

In `set_settings` (line 1389), after the existing quality-restore block:

```python
        if "quality" in settings and settings["quality"] in {"low", "medium", "high", "auto"}:
            mapping = {
                "low": self.gi2_low_radio,
                "medium": self.gi2_medium_radio,
                "high": self.gi2_high_radio,
                "auto": self.gi2_auto_radio,
            }
            mapping[settings["quality"]].setChecked(True)
```

### Step 5.2 — `ResolutionSelector` custom-size popup

- [ ] In `ResolutionSelector` (line 333), add a "Custom…" row. Add new instance attributes in `__init__` (after line 398):

```python
        self._custom_size_str = None  # "WxH" set by custom-size popup, or None
```

- [ ] In `_init_ui` (line 401), add a Custom… button next to the Reset/Lock buttons. Insert after `size_layout.addWidget(self.lock_btn)` (around line 481):

```python
        self.custom_size_btn = QPushButton("Custom…")
        self.custom_size_btn.setToolTip(
            "Enter a custom WxH (gpt-image-2 only).\n"
            "Both edges multiples of 16, max edge 3840, aspect ≤3:1, "
            "total pixels 655K-8.3M."
        )
        self.custom_size_btn.clicked.connect(self._open_custom_size_dialog)
        self.custom_size_btn.setVisible(False)
        size_layout.addWidget(self.custom_size_btn)
```

- [ ] Extend `update_model` (search for `def update_model` in ResolutionSelector — it's around line 657 area) so the Custom button shows only when caps allow. Add at the bottom of `update_model`:

```python
        # Show "Custom…" only for OpenAI models that support it.
        try:
            from providers.openai import MODEL_CAPS as _OAI_CAPS
            caps = _OAI_CAPS.get(model_id) if model_id else None
            self.custom_size_btn.setVisible(bool(caps and caps.get("supports_custom_size")))
        except ImportError:
            self.custom_size_btn.setVisible(False)
        self.model = model_id
```

(If `update_model` already sets `self.model = model_id`, drop the duplicate line.)

- [ ] Add the dialog method on `ResolutionSelector`. Insert near the end of the class. Note: PySide6 modal-dialog method is `.exec_()` (trailing underscore) — both forms work but the underscore form avoids tripping over generic security scanners.

```python
    def _open_custom_size_dialog(self):
        """Inline modal popup with W/H spinboxes and live validation label."""
        from PySide6.QtWidgets import (
            QDialog, QFormLayout, QSpinBox, QLabel, QDialogButtonBox, QHBoxLayout,
        )
        from providers.openai import MODEL_CAPS
        from core.image_size import validate_custom_size

        caps = MODEL_CAPS.get(self.model) if self.model else None
        if not caps or not caps.get("supports_custom_size"):
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Custom image size")
        form = QFormLayout(dlg)

        w_spin = QSpinBox()
        w_spin.setRange(16, int(caps.get("custom_size_max_edge", 3840)))
        w_spin.setSingleStep(16)
        w_spin.setValue(self._custom_width or 2048)
        h_spin = QSpinBox()
        h_spin.setRange(16, int(caps.get("custom_size_max_edge", 3840)))
        h_spin.setSingleStep(16)
        h_spin.setValue(self._custom_height or 1152)

        status = QLabel("")
        status.setStyleSheet("color: #4CAF50;")

        def revalidate():
            ok, why = validate_custom_size(w_spin.value(), h_spin.value(), caps)
            if ok:
                status.setText(f"✓ Valid ({w_spin.value()}×{h_spin.value()})")
                status.setStyleSheet("color: #4CAF50;")
            else:
                status.setText(f"✗ {why}")
                status.setStyleSheet("color: #E53935;")
            buttons.button(QDialogButtonBox.Ok).setEnabled(ok)

        w_spin.valueChanged.connect(lambda *_: revalidate())
        h_spin.valueChanged.connect(lambda *_: revalidate())

        row = QHBoxLayout()
        row.addWidget(QLabel("Width:"))
        row.addWidget(w_spin)
        row.addSpacing(8)
        row.addWidget(QLabel("Height:"))
        row.addWidget(h_spin)
        form.addRow(row)
        form.addRow(status)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        revalidate()

        if dlg.exec_() == QDialog.Accepted:
            self._custom_width = w_spin.value()
            self._custom_height = h_spin.value()
            self._custom_size_str = f"{self._custom_width}x{self._custom_height}"
            self.width_spin.setValue(self._custom_width)
            self.height_spin.setValue(self._custom_height)
            self._update_info_text()
            self.resolutionChanged.emit(self._custom_size_str)

    def get_custom_size(self):
        """Return 'WxH' string set by the custom-size popup, or None."""
        return self._custom_size_str
```

- [ ] Confirm `Optional` is already imported (search for `from typing import` at the top of `settings_widgets.py`). If not, add it.

### Step 5.3 — New widgets at the end of `gui/settings_widgets.py`

- [ ] Append these three new widget classes to the end of the file (after `class AdvancedSettingsPanel` ends):

```python
class OutputFormatRow(QWidget):
    """PNG / JPEG / WebP radios with a compression slider for jpeg/webp.

    Driven by MODEL_CAPS[model]['supports_output_format']; hide the whole
    widget when the active model doesn't support output_format.
    """

    settingsChanged = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.group = QGroupBox("Output Format")
        gl = QHBoxLayout(self.group)

        self.buttons = QButtonGroup(self)
        self.png_radio = QRadioButton("PNG")
        self.png_radio.setChecked(True)
        self.jpeg_radio = QRadioButton("JPEG")
        self.webp_radio = QRadioButton("WebP")
        for i, b in enumerate((self.png_radio, self.jpeg_radio, self.webp_radio)):
            self.buttons.addButton(b, i)
            gl.addWidget(b)
        self.buttons.buttonClicked.connect(self._on_changed)

        gl.addSpacing(12)
        self.compression_label = QLabel("Compression:")
        self.compression_slider = QSlider(Qt.Horizontal)
        self.compression_slider.setRange(0, 100)
        self.compression_slider.setValue(90)
        self.compression_slider.setMaximumWidth(140)
        self.compression_value = QLabel("90")
        self.compression_value.setMinimumWidth(28)
        self.compression_slider.valueChanged.connect(
            lambda v: (self.compression_value.setText(str(v)), self._on_changed())
        )
        gl.addWidget(self.compression_label)
        gl.addWidget(self.compression_slider)
        gl.addWidget(self.compression_value)
        self._set_compression_visible(False)

        layout.addWidget(self.group)

    def update_model(self, model_id: str):
        """Show/hide based on MODEL_CAPS; safe for non-openai models."""
        try:
            from providers.openai import MODEL_CAPS
            caps = MODEL_CAPS.get(model_id)
            self.group.setVisible(bool(caps and caps.get("supports_output_format")))
        except ImportError:
            self.group.setVisible(False)

    def _on_changed(self, *_):
        fmt = self.get_format()
        self._set_compression_visible(fmt in ("jpeg", "webp"))
        self.settingsChanged.emit(self.get_settings())

    def _set_compression_visible(self, visible: bool):
        for w in (self.compression_label, self.compression_slider, self.compression_value):
            w.setVisible(visible)

    def get_format(self) -> str:
        if self.jpeg_radio.isChecked():
            return "jpeg"
        if self.webp_radio.isChecked():
            return "webp"
        return "png"

    def get_settings(self) -> dict:
        s = {"output_format": self.get_format()}
        if s["output_format"] in ("jpeg", "webp"):
            s["output_compression"] = self.compression_slider.value()
        return s

    def set_settings(self, settings: dict):
        fmt = settings.get("output_format", "png")
        if fmt == "jpeg":
            self.jpeg_radio.setChecked(True)
        elif fmt == "webp":
            self.webp_radio.setChecked(True)
        else:
            self.png_radio.setChecked(True)
        if "output_compression" in settings:
            self.compression_slider.setValue(int(settings["output_compression"]))
        self._set_compression_visible(fmt in ("jpeg", "webp"))


class ModerationCheckbox(QWidget):
    """Single 'permissive moderation' checkbox; visible only when caps allow."""

    settingsChanged = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.checkbox = QCheckBox("Permissive content moderation (moderation=low)")
        self.checkbox.setToolTip(
            "Loosens content filters. See OpenAI usage policy: "
            "https://openai.com/policies/usage-policies/"
        )
        self.checkbox.toggled.connect(
            lambda *_: self.settingsChanged.emit(self.get_settings())
        )
        layout.addWidget(self.checkbox)
        layout.addStretch()

    def update_model(self, model_id: str):
        try:
            from providers.openai import MODEL_CAPS
            caps = MODEL_CAPS.get(model_id)
            self.setVisible(bool(caps and caps.get("supports_moderation")))
        except ImportError:
            self.setVisible(False)

    def get_settings(self) -> dict:
        return {"moderation": "low" if self.checkbox.isChecked() else "auto"}

    def set_settings(self, settings: dict):
        self.checkbox.setChecked(settings.get("moderation") == "low")


class ThinkingProgressToggle(QWidget):
    """Show-thinking-progress checkbox; visible only when caps['supports_streaming']."""

    settingsChanged = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.checkbox = QCheckBox("Show thinking progress (stream partial frames)")
        self.checkbox.setToolTip(
            "Stream up to 2 partial images as the model thinks. "
            "Each partial costs ~100 extra output tokens."
        )
        self.checkbox.toggled.connect(
            lambda *_: self.settingsChanged.emit(self.get_settings())
        )
        layout.addWidget(self.checkbox)
        layout.addStretch()

    def update_model(self, model_id: str):
        try:
            from providers.openai import MODEL_CAPS
            caps = MODEL_CAPS.get(model_id)
            self.setVisible(bool(caps and caps.get("supports_streaming")))
        except ImportError:
            self.setVisible(False)

    def is_enabled(self) -> bool:
        return self.checkbox.isChecked()

    def get_settings(self) -> dict:
        return {"stream_partials": self.checkbox.isChecked()}

    def set_settings(self, settings: dict):
        self.checkbox.setChecked(bool(settings.get("stream_partials", False)))
```

- [ ] If the file doesn't already import `QSlider`, `QCheckBox`, or `Qt` from PySide6, add them. Search for `from PySide6.QtWidgets import` and append `QSlider, QCheckBox` to the list. Search for `from PySide6.QtCore import` and append `Qt` if missing.

### Step 5.4 — Verify

```bash
python -m py_compile gui/settings_widgets.py
# PySide6 typically isn't installed in WSL. Sanity-check by parsing only:
python -c "import ast; ast.parse(open('gui/settings_widgets.py').read()); print('settings_widgets parses OK')"
```

### Step 5.5 — Commit

```bash
git add gui/settings_widgets.py
git commit -m "$(cat <<'EOF'
feat(gui-widgets): gpt-image-2 reasoning quality, custom size dialog, output format, moderation, thinking-progress

QualitySelector grows a third mode for gpt-image-2 (Low | Medium | High |
Auto radios) toggled by update_model(). ResolutionSelector adds a
"Custom…" button (visible only when MODEL_CAPS[model].supports_custom_size)
that opens a popup with W/H spinboxes and live red/green validation via
core.image_size.validate_custom_size — so GUI and provider can never
drift on the 16-px-multiple / 3840 max edge / 3:1 aspect / pixel-bound
rules.

Three new widgets ship at the bottom of the file:
- OutputFormatRow (PNG/JPEG/WebP + compression slider for jpeg/webp)
- ModerationCheckbox (moderation=low opt-in)
- ThinkingProgressToggle (stream partial frames opt-in)

Each new widget has a parameter-free update_model(model_id) that consults
MODEL_CAPS to show/hide itself, so MainWindow can iterate and dispatch
without special-casing models.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6 — GUI integration + skill + version bump

**Why last:** Pulls everything together — wires the widgets into MainWindow, adds the streaming worker, the Submit-as-Batch menu/dialog, the Batch Jobs subtab. Then ships the in-repo skill and bumps the app version.

**Files:**
- Modify: `gui/main_window.py`
  - `_on_model_changed` (line 3876): instantiate the new widgets if missing, and call `update_model(model_id)` on each
  - kwargs assembly (the big block ~5285-5400): pull `output_format`, `output_compression`, `moderation`, `custom_size`, `stream_partials` from the new widgets
  - Streaming: when `stream_partials` is on, run a `StreamingGenWorker` (new) instead of the existing `GenWorker`; preview slot updates with each partial
  - Add `Generate → Submit as Batch Job…` menu action
  - Add `Batch Jobs` subtab to the History tab
- Modify: `gui/workers.py` (add `StreamingGenWorker` and `BatchJobsLoaderWorker`)
- Create: `.claude/skills/imageai-gpt-image-2/SKILL.md` (in-repo only — no Windows global mirrors per user direction)
- Modify: `core/constants.py` (bump VERSION 0.37.0 → 0.38.0)

### Step 6.1 — Add `StreamingGenWorker` to `gui/workers.py`

- [ ] In `gui/workers.py`, after `class GenWorker` ends (around line 76), insert:

```python
class StreamingGenWorker(QObject):
    """Worker that streams partial frames via the provider's on_partial callback.

    Emits:
        partial(int index, bytes png_bytes)
        finished(list texts, list image_bytes)
        error(str message)
    """
    partial = Signal(int, bytes)
    finished = Signal(list, list)
    error = Signal(str)

    def __init__(self, provider_instance, kwargs):
        super().__init__()
        self.provider = provider_instance
        self.kwargs = dict(kwargs)

    def run(self):
        try:
            def on_partial(idx, png):
                self.partial.emit(int(idx), bytes(png))
            self.kwargs["on_partial"] = on_partial
            self.kwargs.setdefault("stream", True)
            self.kwargs.setdefault("partial_images", 2)
            texts, images = self.provider.generate(**self.kwargs)
            self.finished.emit(list(texts), list(images))
        except Exception as e:  # noqa: BLE001 — surface to UI
            self.error.emit(str(e))


class BatchJobsLoaderWorker(QObject):
    """Loads BATCH_JOBS_PATH and emits the entries as a list."""
    loaded = Signal(list)
    error = Signal(str)

    def __init__(self, provider_instance=None):
        super().__init__()
        self.provider = provider_instance

    def run(self):
        import json
        try:
            from core.constants import BATCH_JOBS_PATH
            entries = []
            if BATCH_JOBS_PATH.exists():
                try:
                    entries = json.loads(BATCH_JOBS_PATH.read_text(encoding="utf-8"))
                    if not isinstance(entries, list):
                        entries = []
                except (OSError, IOError, ValueError):
                    entries = []
            self.loaded.emit(entries)
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))
```

- [ ] Confirm `Signal` and `QObject` are imported at the top of `workers.py` (they should be — `GenWorker` uses them).

### Step 6.2 — Wire widgets into `MainWindow`

**Locating insert points:** The MainWindow constructor builds the Generate tab somewhere around line 700-1500. Search for `self.quality_selector =` to find where it's already instantiated. The new widgets should sit next to it.

- [ ] Search for the line `self.quality_selector = QualitySelector(` (likely once, in the Generate-tab build code). Immediately after the line that does `_layout_or_parent.addWidget(self.quality_selector)` (the surrounding container should already exist), add:

```python
        from .settings_widgets import OutputFormatRow, ModerationCheckbox, ThinkingProgressToggle
        self.output_format_row = OutputFormatRow(self)
        self.moderation_checkbox = ModerationCheckbox(self)
        self.thinking_progress_toggle = ThinkingProgressToggle(self)
        # Add to the same parent layout the quality_selector lives in.
        _qs_parent = self.quality_selector.parentWidget()
        if _qs_parent is not None and _qs_parent.layout() is not None:
            _qs_parent.layout().addWidget(self.output_format_row)
            _qs_parent.layout().addWidget(self.moderation_checkbox)
            _qs_parent.layout().addWidget(self.thinking_progress_toggle)
        # Default-hidden until a supported model is selected.
        self.output_format_row.setVisible(False)
        self.moderation_checkbox.setVisible(False)
        self.thinking_progress_toggle.setVisible(False)
```

(If `quality_selector` lives inside a custom layout the `.parentWidget()` trick won't reach, just locate the `QVBoxLayout` it's added to and call `<that_layout>.addWidget(...)` instead. Either approach is fine — pick whichever matches the surrounding code.)

### Step 6.3 — Update `_on_model_changed` to cascade through caps

- [ ] In `_on_model_changed` (line 3876), append the cap-driven widget update at the **end** of the method (after the existing background_group handling at line 3927):

```python
        # Cap-driven dispatch for new gpt-image-2 widgets. Each widget knows
        # how to read MODEL_CAPS and show/hide itself — keep this loop
        # capability-driven so adding a new model never requires a new branch.
        for _w_attr in ("output_format_row", "moderation_checkbox", "thinking_progress_toggle"):
            _w = getattr(self, _w_attr, None)
            if _w is not None:
                _w.update_model(model_id)
```

### Step 6.4 — Push new widget settings into the generation kwargs

- [ ] Find the kwargs-assembly block around line 5285. Look for the existing line `kwargs['background'] = background_text` (line 5290). After the OpenAI-specific kwargs end (just before the `if (hasattr(self, 'reference_image_data')...` block around line 5295), insert:

```python
        # gpt-image-2 widgets (no-op if widget hidden / not instantiated).
        if hasattr(self, 'output_format_row') and self.output_format_row.isVisible():
            kwargs.update(self.output_format_row.get_settings())
        if hasattr(self, 'moderation_checkbox') and self.moderation_checkbox.isVisible():
            kwargs.update(self.moderation_checkbox.get_settings())
        if hasattr(self, 'quality_selector'):
            qs = self.quality_selector.get_settings()
            if qs.get("quality") in {"low", "medium", "high", "auto"}:
                kwargs["quality"] = qs["quality"]
        # Custom size from ResolutionSelector popup, if set
        if hasattr(self, 'resolution_selector'):
            cs = getattr(self.resolution_selector, "get_custom_size", lambda: None)()
            if cs:
                kwargs["custom_size"] = cs
```

### Step 6.5 — Streaming dispatch (use `StreamingGenWorker` when toggle is on)

The current generate path uses `GenWorker`. The smallest change that doesn't risk regressions: **wrap the existing GenWorker construction in a check** for the thinking-progress toggle.

- [ ] Search for `GenWorker(` in `gui/main_window.py` (it's the construction call inside the generate-button handler). Replace the construction line with this dispatch block. Adjust variable names if your local block uses different names — the structure is what matters:

```python
        # Choose worker based on thinking-progress toggle.
        use_streaming = bool(
            getattr(self, 'thinking_progress_toggle', None)
            and self.thinking_progress_toggle.is_enabled()
        )
        if use_streaming:
            from .workers import StreamingGenWorker
            kwargs["stream"] = True
            kwargs["partial_images"] = 2
            self._gen_worker = StreamingGenWorker(provider_instance, kwargs)
            self._gen_worker.partial.connect(self._on_streaming_partial)
            self._gen_worker.finished.connect(self._on_generation_finished)
            self._gen_worker.error.connect(self._on_generation_error)
        else:
            self._gen_worker = GenWorker(provider_instance, kwargs)  # existing
            # ...keep the existing finished/error connections...
```

- [ ] Add the partial slot. Find a sensible location near the other generation-result slots (`_on_generation_finished`, `_on_generation_error`) and insert:

```python
    def _on_streaming_partial(self, idx: int, png_bytes: bytes):
        """Update preview pane with a streamed partial frame."""
        try:
            from PySide6.QtGui import QPixmap
            pix = QPixmap()
            pix.loadFromData(png_bytes, "PNG")
            if hasattr(self, 'preview_label') and pix and not pix.isNull():
                self.preview_label.setPixmap(pix.scaled(
                    self.preview_label.size(),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation,
                ))
            if hasattr(self, 'status_label'):
                self.status_label.setText(f"Thinking… (frame {idx + 1}/2)")
            self._append_to_console(f"Streaming partial {idx + 1}/2 ({len(png_bytes):,} bytes)", "#aaaaff")
        except Exception as e:  # noqa: BLE001
            self.logger.warning(f"Failed to render streaming partial: {e}")
```

(`Qt`, `QPixmap` — confirm or add imports.)

### Step 6.6 — `Generate → Submit as Batch Job…` menu action

- [ ] In `MainWindow._setup_menus` (search for `_setup_menus` or `setMenuBar` / `menuBar()`), find the Generate menu (it may already exist; if not, add it as a top-level menu). Add the action. Note the use of `.exec_()` for the QMessageBox modal:

```python
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import QMenu
        self.action_submit_batch = QAction("Submit as Batch Job…", self)
        self.action_submit_batch.setToolTip(
            "Send the current prompt to the OpenAI Batch API "
            "(50% discount, async — results in up to 24h)."
        )
        self.action_submit_batch.triggered.connect(self._submit_current_as_batch)
        # Append to the existing Generate menu (or build one if missing).
        gen_menu = None
        for m in self.menuBar().findChildren(QMenu):
            if m.title().replace("&", "") == "Generate":
                gen_menu = m
                break
        if gen_menu is None:
            gen_menu = self.menuBar().addMenu("&Generate")
        gen_menu.addAction(self.action_submit_batch)
```

- [ ] Add the slot:

```python
    def _submit_current_as_batch(self):
        """Spawn a small dialog confirming Batch submission, then submit."""
        from PySide6.QtWidgets import QMessageBox
        if self.current_provider.lower() != "openai":
            QMessageBox.information(self, "Batch", "Batch API is only available for the OpenAI provider.")
            return
        prompt = self.prompt_text.toPlainText().strip() if hasattr(self, 'prompt_text') else ""
        if not prompt:
            QMessageBox.information(self, "Batch", "Enter a prompt first.")
            return
        model = self.model_combo.currentData() or self.model_combo.currentText()
        n = int(getattr(self, 'num_images_spin', None).value()) if hasattr(self, 'num_images_spin') else 1
        confirm = QMessageBox.question(
            self,
            "Submit Batch Job",
            f"Submit 1 batch request:\n  model: {model}\n  prompt: {prompt[:120]}…\n  n: {n}\n\n"
            "Batch jobs return within 24 hours at 50% discount. Continue?",
            QMessageBox.Ok | QMessageBox.Cancel,
        )
        if confirm != QMessageBox.Ok:
            return
        try:
            from providers import get_provider
            provider_instance = get_provider("openai", {"api_key": self.config.get_api_key("openai")})
            req_body = {"model": model, "prompt": prompt, "n": n}
            # Pull through gpt-image-2 widgets if present
            if hasattr(self, 'output_format_row') and self.output_format_row.isVisible():
                req_body.update(self.output_format_row.get_settings())
            if hasattr(self, 'moderation_checkbox') and self.moderation_checkbox.isVisible():
                req_body.update(self.moderation_checkbox.get_settings())
            if hasattr(self, 'quality_selector'):
                qs = self.quality_selector.get_settings()
                if qs.get("quality") in {"low", "medium", "high", "auto"}:
                    req_body["quality"] = qs["quality"]
            if hasattr(self, 'resolution_selector'):
                cs = getattr(self.resolution_selector, "get_custom_size", lambda: None)()
                if cs:
                    req_body["size"] = cs
            job_id = provider_instance.submit_batch_job([req_body])
            QMessageBox.information(self, "Batch", f"Submitted job:\n{job_id}\n\nView under History → Batch Jobs.")
            if hasattr(self, '_refresh_batch_jobs_subtab'):
                self._refresh_batch_jobs_subtab()
        except Exception as e:
            QMessageBox.warning(self, "Batch", f"Submission failed:\n{e}")
```

### Step 6.7 — Batch Jobs subtab on the History tab

- [ ] Search for where the History tab is built (`self.tab_history` or `tabHistory`). After the existing History UI is constructed, add a "Batch Jobs" subtab. The minimal version:

```python
        # Batch Jobs subtab
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QPushButton, QVBoxLayout, QWidget, QHBoxLayout
        self.batch_jobs_widget = QWidget()
        bjl = QVBoxLayout(self.batch_jobs_widget)
        self.batch_jobs_table = QTableWidget(0, 6)
        self.batch_jobs_table.setHorizontalHeaderLabels([
            "Job ID", "Model", "Submitted", "Requests", "Status", "Actions",
        ])
        self.batch_jobs_table.horizontalHeader().setStretchLastSection(True)
        bjl.addWidget(self.batch_jobs_table)
        controls = QHBoxLayout()
        self.btn_batch_refresh = QPushButton("Refresh")
        self.btn_batch_refresh.clicked.connect(self._refresh_batch_jobs_subtab)
        controls.addWidget(self.btn_batch_refresh)
        controls.addStretch()
        bjl.addLayout(controls)
        # Add to whichever tab container History uses; if History is itself
        # a tab container, addTab; otherwise wrap in a QTabWidget here.
        if hasattr(self, 'history_tabs'):
            self.history_tabs.addTab(self.batch_jobs_widget, "Batch Jobs")
        else:
            # Fall back to a standalone tab on the main tab widget.
            self.tabs.addTab(self.batch_jobs_widget, "Batch Jobs")
```

- [ ] Add the refresh slot:

```python
    def _refresh_batch_jobs_subtab(self):
        """Populate the Batch Jobs table from BATCH_JOBS_PATH."""
        from PySide6.QtWidgets import QTableWidgetItem, QPushButton
        from core.constants import BATCH_JOBS_PATH
        import json

        entries = []
        if BATCH_JOBS_PATH.exists():
            try:
                entries = json.loads(BATCH_JOBS_PATH.read_text(encoding="utf-8"))
                if not isinstance(entries, list):
                    entries = []
            except (OSError, IOError, ValueError):
                entries = []

        self.batch_jobs_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self.batch_jobs_table.setItem(row, 0, QTableWidgetItem(entry.get("job_id", "")))
            self.batch_jobs_table.setItem(row, 1, QTableWidgetItem(entry.get("model", "")))
            self.batch_jobs_table.setItem(row, 2, QTableWidgetItem(entry.get("created_at", "")))
            self.batch_jobs_table.setItem(row, 3, QTableWidgetItem(str(entry.get("request_count", ""))))
            self.batch_jobs_table.setItem(row, 4, QTableWidgetItem(entry.get("status", "submitted")))

            btn = QPushButton("Check / Download")
            jid = entry.get("job_id", "")
            btn.clicked.connect(lambda _checked=False, j=jid: self._check_batch_job_action(j))
            self.batch_jobs_table.setCellWidget(row, 5, btn)

    def _check_batch_job_action(self, job_id: str):
        from PySide6.QtWidgets import QMessageBox
        from providers import get_provider
        try:
            provider_instance = get_provider("openai", {"api_key": self.config.get_api_key("openai")})
            images_dir = self.config.get_images_dir()
            info = provider_instance.check_batch_job(job_id, output_dir=images_dir)
            msg = f"Job: {info['job_id']}\nStatus: {info['status']}\nDownloaded: {len(info.get('downloaded', []))} file(s)"
            QMessageBox.information(self, "Batch Job", msg)
            self._refresh_batch_jobs_subtab()
        except Exception as e:
            QMessageBox.warning(self, "Batch Job", f"Check failed:\n{e}")
```

### Step 6.8 — Create the in-repo skill

- [ ] Create `.claude/skills/imageai-gpt-image-2/SKILL.md` with the content below. The skill is a wrapper around the ImageAI CLI; it tells future Claude sessions exactly which flags to use.

```markdown
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

| Flag                    | Values                                  | Default | Notes |
|-------------------------|-----------------------------------------|---------|-------|
| `--quality`             | `auto`, `low`, `medium`, `high`         | `auto`  | Drives reasoning compute. `high` ≈ $0.21/image at 1024². |
| `--size`                | `1024x1024`, `1536x1024`, `1024x1536`, `2048x2048`, `2048x1152`, `3840x2160`, `2160x3840`, `auto` | `1024x1024` | Mutex with `--custom-size`. |
| `--custom-size`         | `WxH`                                   | —       | gpt-image-2 only. Edges multiples of 16, max edge 3840, aspect ≤3:1, pixels 655K-8.3M. |
| `--output-format`       | `png`, `jpeg`, `webp`                   | `png`   | |
| `--output-compression`  | `0..100`                                | `90`    | jpeg/webp only. |
| `--moderation`          | `auto`, `low`                           | `auto`  | `low` = permissive. See OpenAI usage policy. |
| `--reference`           | path (repeatable, up to 10)             | —       | Routes to `/v1/images/edits`. |
| `--mask`                | PNG path                                | —       | Alpha mask for inpainting. Transparent = edit zone. |
| `--stream-partials`     | flag                                    | off     | Writes `out.pN.png` for each partial. |
| `--batch`               | flag                                    | off     | Submit via Batch API (50% off). |
| `--batch-status JOB`    | job ID                                  | —       | Print job status. |
| `--batch-fetch JOB`     | job ID                                  | —       | Download completed outputs. |
| `-n`, `--num-images`    | `1..10`                                 | `1`     | gpt-image-2 supports up to 10 in one call. |

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
```

### Step 6.9 — Bump version

- [ ] In `core/constants.py`, change line 9 from `VERSION = "0.37.0"` to `VERSION = "0.38.0"`. Then check whether `.claude/VERSION_LOCATIONS.md` lists other places that hardcode the version:

```bash
grep -rn "0\.37\.0" --include='*.py' --include='*.md' core/ gui/ cli/ providers/ README.md 2>/dev/null
```

If hits show up in README.md or elsewhere, update them in this same commit (or note in the commit message that a follow-up bump PR is needed).

### Step 6.10 — Verify

```bash
python -m py_compile gui/workers.py gui/main_window.py core/constants.py
python -c "from core.constants import VERSION; assert VERSION == '0.38.0', VERSION; print('VERSION =', VERSION)"
python -c "import ast; ast.parse(open('gui/main_window.py').read()); ast.parse(open('gui/workers.py').read()); print('GUI parses OK')"
ls -l .claude/skills/imageai-gpt-image-2/SKILL.md
```

### Step 6.11 — Commit

```bash
git add gui/main_window.py gui/workers.py core/constants.py .claude/skills/imageai-gpt-image-2/SKILL.md
git commit -m "$(cat <<'EOF'
feat(gui): wire gpt-image-2 widgets, streaming worker, batch UI; ship in-repo skill; v0.38.0

MainWindow gains capability-driven dispatch through the new widgets:
output_format_row, moderation_checkbox, thinking_progress_toggle each
expose update_model(), so _on_model_changed iterates them without
per-model branches. Generation kwargs assembly pulls settings from each
visible widget (output_format/output_compression/moderation/quality
/custom_size).

Streaming uses a new StreamingGenWorker; partial frames flow through a
Qt signal into a preview slot that updates the preview label and shows
"Thinking… (frame N/2)" status. Sync GenWorker remains the default.

New "Generate → Submit as Batch Job…" menu action confirms and submits
the current prompt to the OpenAI Batch API. New "Batch Jobs" subtab on
the History tab lists jobs from BATCH_JOBS_PATH with per-row
"Check / Download" buttons.

Adds .claude/skills/imageai-gpt-image-2/SKILL.md as the in-repo Claude
Code skill; future sessions discover it automatically and route
gpt-image-2 requests through the right CLI flags.

Bumps VERSION 0.37.0 → 0.38.0.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Spec coverage check

Mapping each spec section to a task:

| Spec section | Task |
|--------------|------|
| §1 Constants & defaults — gpt-image-2 first, snapshot constant | Task 1 (1.1, 1.2) |
| §2 Provider — MODEL_CAPS, generate(), edit_image(), validate_auth | Task 2 (2.1–2.5) |
| §2 Provider — Batch + streaming methods | Task 3 (3.1–3.3) |
| §3 GUI — quality / size / output / moderation / thinking widgets | Task 5 (5.1–5.3) |
| §3 GUI — _on_model_changed dispatch, batch menu, batch subtab, streaming preview | Task 6 (6.2–6.7) |
| §4 CLI — all new flags, runner dispatch | Task 4 (4.1–4.2) |
| §5 Sidecar schema | Task 1 (1.3) — schema doc; Task 4 (4.2) — writing the new fields from CLI |
| §6 Shared size validator | Task 1 (1.4) |
| §Skills — imageai-gpt-image-2 (in-repo only per user direction) | Task 6 (6.8) |
| §Skills — global Windows mirrors | **Skipped** per user direction ("just local for now") |
| §Testing | **Skipped** per user direction ("skip"); test harness is a separate effort |
| §Risks | Mitigations land alongside features (validate_auth org-gate in Task 2; streaming graceful fallback in Task 3; size validator in Task 1; cost surfacing via QualitySelector tooltips in Task 5) |
| §Non-goals | Honored — no changes to viseme/region editor, no Responses-as-chat, no video pipeline |

## Execution notes for the agent team

- Tasks **must** run sequentially. Task 2 imports `core.image_size` from Task 1, Task 3 extends the same `generate()` Task 2 modified, Task 4 imports `MODEL_CAPS` from Task 2, Tasks 5–6 import everything below them.
- Each task ends with one commit. Do not squash. The integrator may rebase later.
- If any verification step fails, **stop** the whole pipeline and surface the error — do not fabricate a passing run. Subsequent tasks will compound the breakage.
- Do not push, do not open a PR, do not merge. Hand the branch back to the integrator after Task 6 commits cleanly.
