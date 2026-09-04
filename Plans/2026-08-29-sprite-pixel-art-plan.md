# Sprite Pixel-Art Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `Plans/2026-08-29-sprite-tab-design.md` §2 (`OutputProfile`, `SheetMeta.palette`) and §4.4 (pixel-art profile). Approved 2026-08-29.

**Goal:** The `pixel` output profile turns stabilized RGBA frames into engine-ready pixel art: an integer box-filter downscale into the cell (never a distortion, never a silent upscale), a binary alpha, one shared palette per project that stays locked across actions, and a selectable dither (none, Bayer 2/4/8, Floyd-Steinberg). `SheetMeta.palette` carries the palette to every exporter.

**Architecture:** One pure module `core/sprite/pixelart.py` (numpy + Pillow, no Qt) holds all math **and** the `pixel` stage runner. `run_pixel_stage` is registered through sub-project 1's stage registry (`register_stage("pixel", run_pixel_stage, settings_fn=pixel_stage_settings, code_version=2)`), so neither `core/sprite/pipeline.py` nor `core/sprite/project.py` is edited. Per action the runner reads the `stabilize` outputs, fits and pads, applies `keying.apply_profile_alpha`, `ensure_palette`, `quantize_to_palette`, and writes `stages/<action_id>/pixel/NNNN.png` plus a `pixel.json` manifest (scale, palette, warnings). Palette lock lives on `OutputProfile.locked_palette`; the opt-in upscale lives on `OutputProfile.upscale_small` / `upscale_method` (fields owned by sub-project 1); `SpriteProject.sheet_meta("pixel")` copies the palette into `SheetMeta.palette`. Pillow quantizes only a flattened RGB view; the alpha plane travels beside it. Ordered dither is an in-house Bayer pass because Pillow's `Dither.ORDERED` is a silent no-op.

**Tech Stack:** Python 3.11+ (project floor for the sprite feature), Pillow 11.3 (`Image.reduce`, `Image.quantize(palette=...)`), numpy, pytest. `core.upscaling.upscale_image` is imported lazily.

**Sub-project:** 4 of 8 — depends on 1 (models, project, pipeline, stabilize) and 3 (`keying.binary_alpha`, `keying.hex_to_rgb`); consumed by 5b (processing panel, pixel view), 6 (Aseprite palette chunk), 7 (CLI `--sprite-process`).

## Global Constraints

- Repo root: `/mnt/d/Documents/Code/GitHub/ImageAI`. Every command uses absolute paths. Never `cd`.
- Interpreter: `/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python` (WSL). Test form: `<interpreter> -m pytest <absolute test path> -v`.
- Branch: `feat/sprite-tab`. Commit after every task with a Conventional Commit subject. Never commit on red tests. No version bump here (sub-project 7 owns it).
- Prerequisites on the branch before Task 1: `core/sprite/models.py`, `core/sprite/project.py`, `core/sprite/pipeline.py`, `core/sprite/stabilize.py` (sub-project 1) and `core/sprite/keying.py` (sub-project 3). Verify with `ls /mnt/d/Documents/Code/GitHub/ImageAI/core/sprite/`.
- Binary alpha comes from `keying.apply_profile_alpha(image, profile)` (sub-project 3 plan, `Plans/2026-08-29-sprite-keying-plan.md`): unchanged image when `profile.binary_alpha` is False, else RGBA with alpha in {0, 255} from `binary_alpha(alpha, profile.alpha_threshold, profile.defringe_px)`. The stage never calls `binary_alpha` (float32 0/1 return) directly.
- **Never import `core.upscaling` at module level.** Its import pulls torchvision (measured 23.5 s on this machine, `REALESRGAN_AVAILABLE=False`). Import `upscale_image` inside `upscale_then_fit` only, the way `gui/main_window.py:6487` does.
- Images are scaled proportionally, never cropped, never distorted. The pixel profile never upscales unless the caller passes `upscale_small=True`.
- Pillow rules: quantize a flattened RGB view and carry alpha separately (`MEDIANCUT`/`MAXCOVERAGE` raise `ValueError` on RGBA); never use `Quantize.LIBIMAGEQUANT` (GPL, compiled out); `Dither.ORDERED` is a silent no-op, so Bayer is in-house numpy; call `Image.fromarray(arr)` without the `mode` argument (deprecated in Pillow 11.3, removed in 13).
- Tests use numpy-synthesized RGBA frames only; no binary fixtures. Tests that reach `upscale_then_fit` install a fake `core.upscaling` module in `sys.modules` so the suite never pays the torchvision import.
- Sub-project 1 owns the `tests/sprite/` layout (`__init__.py`, `conftest.py`, `synth.py`). This plan adds two test modules that define their own frame helpers and use none of those fixtures.
- Two `OutputProfile` fields beyond the design — `upscale_small: bool = False`, `upscale_method: str = "lanczos"` — are added by sub-project 1 (orchestrator decision 2026-08-29); this plan only reads them. `run_pipeline` keeps its design signature; the stage plugs in through `register_stage(..., code_version=2)`, so this plan edits neither `pipeline.py` nor `project.py`.
- No path built by hand: the stage writes only into the `out_dir` the pipeline passes. `tests/test_no_hardcoded_paths.py` stays green.
- Docstrings, log text, and warnings follow the Simplified Technical English style of `AGENTS.md`.

## File Structure

| Path | Action | Purpose |
|---|---|---|
| `core/sprite/pixelart.py` | Create (Tasks 1–7) | Integer fit/pad, resolution check, upscale-then-fit, Bayer matrices, shared palette, quantize + dither, lock/remap/ensure, the `pixel` stage runner + `register_stage` call. 409 lines when finished. |
| `tests/sprite/test_pixelart.py` | Create (Tasks 1–6) | Unit tests for the math; Pillow-trap regression test. 429 lines when finished. |
| `core/sprite/__init__.py` | Modify (Task 7) | `from . import pixelart` after `.pipeline`, so the stage registration runs on package load. |
| `tests/sprite/test_pipeline_pixel.py` | Create (Task 7) | Stage tests, registry + fingerprint tests, `run_pipeline` dispatch test, `sheet_meta` palette test. 214 lines. |

---

### Task 1: Module skeleton, integer scale, anchor offsets, fit-and-pad

**Files:**
- Create: `core/sprite/pixelart.py` (finished-file lines 1–105: header, constants, `integer_fit_scale`, `anchor_offset`, `fit_pad_integer`)
- Create: `tests/sprite/test_pixelart.py` (finished-file lines 1–124)

**Interfaces:**
- Consumes: `core.sprite.keying.hex_to_rgb` and `apply_profile_alpha`, `core.sprite.pipeline.CancelToken`, `ProgressFn`, `no_progress`, `register_stage` (all imported now; first used in Tasks 4 and 7), `PIL.Image.Image.reduce`.
- Produces:
  - `DITHER_MODES: Tuple[str, ...]`, `ANCHORS: Tuple[str, ...]`, `UPSCALE_METHODS: Tuple[str, ...]`, `PALETTE_ALPHA_MIN: int`, `MAX_PALETTE_SAMPLES: int`, `FLOYD_WARNING: str`
  - `integer_fit_scale(src: Size, cell: Size) -> int`
  - `anchor_offset(content: Size, cell: Size, anchor: str) -> Tuple[int, int]`
  - `fit_pad_integer(image: Image.Image, cell: Size, anchor: str, *, scale: Optional[int] = None) -> Image.Image`

- [x] **Step 1: Write the failing tests**

```python
# tests/sprite/test_pixelart.py
import io
import sys
import types
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from core.sprite import pixelart
from core.sprite.pixelart import (
    anchor_offset, fit_pad_integer, integer_fit_scale,
)


def square_frame(size, square, color=(200, 40, 40, 255), origin=(0, 0)):
    """RGBA frame of ``size`` with one opaque square of ``square`` px at ``origin``."""
    arr = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    x0, y0 = origin
    arr[y0:y0 + square[1], x0:x0 + square[0]] = color
    return Image.fromarray(arr)


def opaque_pixels(image):
    arr = np.asarray(image.convert("RGBA"))
    return int((arr[..., 3] > 0).sum())


def install_fake_upscaler(monkeypatch, calls):
    """Stand in for core.upscaling (its real import pulls torchvision, ~23 s)."""
    fake = types.ModuleType("core.upscaling")

    def upscale_image(image_data, target_width, target_height, method="lanczos", **kwargs):
        calls.append((target_width, target_height, method))
        img = Image.open(io.BytesIO(image_data))
        img.load()
        out = io.BytesIO()
        img.resize((target_width, target_height), Image.Resampling.LANCZOS).save(out, format="PNG")
        return out.getvalue()

    fake.upscale_image = upscale_image
    monkeypatch.setitem(sys.modules, "core.upscaling", fake)


# --- Task 1 -------------------------------------------------------------------------

def test_integer_fit_scale_exact_multiple():
    assert integer_fit_scale((256, 256), (64, 64)) == 4


def test_integer_fit_scale_rounds_up_to_fit():
    assert integer_fit_scale((500, 500), (64, 64)) == 8
    assert integer_fit_scale((100, 800), (64, 64)) == 13


def test_integer_fit_scale_is_one_when_source_fits():
    assert integer_fit_scale((64, 64), (64, 64)) == 1
    assert integer_fit_scale((10, 10), (64, 64)) == 1


def test_integer_fit_scale_rejects_zero():
    with pytest.raises(ValueError):
        integer_fit_scale((0, 10), (64, 64))


def test_anchor_offsets():
    assert anchor_offset((10, 20), (64, 64), "bottom_center") == (27, 44)
    assert anchor_offset((10, 20), (64, 64), "center") == (27, 22)
    assert anchor_offset((10, 20), (64, 64), "top_left") == (0, 0)
    assert anchor_offset((10, 20), (64, 64), "top_center") == (27, 0)
    assert anchor_offset((10, 20), (64, 64), "bottom_left") == (0, 44)


def test_anchor_offset_rejects_unknown_and_oversize():
    with pytest.raises(ValueError):
        anchor_offset((10, 10), (64, 64), "middle")
    with pytest.raises(ValueError):
        anchor_offset((65, 10), (64, 64), "center")


def test_fit_pad_integer_downscales_by_box_filter_and_pads():
    src = square_frame((256, 256), (128, 256), origin=(64, 0))
    out = fit_pad_integer(src, (64, 64), "bottom_center")
    assert out.size == (64, 64)
    assert out.mode == "RGBA"
    arr = np.asarray(out)
    assert arr[..., 3].sum() // 255 == 32 * 64
    assert (arr[:, 16:48, 3] == 255).all()
    assert (arr[:, :16, 3] == 0).all() and (arr[:, 48:, 3] == 0).all()


def test_fit_pad_integer_never_upscales_small_source():
    src = square_frame((16, 16), (16, 16))
    out = fit_pad_integer(src, (64, 64), "bottom_center")
    assert out.size == (64, 64)
    assert opaque_pixels(out) == 16 * 16
    arr = np.asarray(out)
    assert (arr[48:64, 24:40, 3] == 255).all()


def test_fit_pad_integer_honors_forced_scale():
    src = square_frame((64, 64), (64, 64))
    out = fit_pad_integer(src, (64, 64), "top_left", scale=2)
    assert opaque_pixels(out) == 32 * 32


def test_fit_pad_integer_box_filter_blends_alpha_edge():
    src = square_frame((8, 8), (4, 8))
    out = fit_pad_integer(src, (2, 2), "top_left")
    arr = np.asarray(out)
    assert tuple(arr[0, 0]) == (200, 40, 40, 255)
    assert tuple(arr[0, 1]) == (0, 0, 0, 0)


def test_fit_pad_integer_non_multiple_fits():
    src = square_frame((500, 300), (500, 300))
    out = fit_pad_integer(src, (64, 64), "bottom_center")
    assert out.size == (64, 64)
    assert opaque_pixels(out) == 63 * 38
```

- [x] **Step 2: Run the tests and confirm the failure**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pixelart.py -v
```

Expected: collection error `ModuleNotFoundError: No module named 'core.sprite.pixelart'`.

- [x] **Step 3: Create the module**

```python
# core/sprite/pixelart.py
"""Pixel-art output profile: integer fit, shared palette, dither, palette lock.

Pillow traps this module works around (verified on Pillow 11.3, 2026-08-29):

* ``Image.quantize(method=MEDIANCUT | MAXCOVERAGE)`` raises ``ValueError`` on
  an RGBA image. This module quantizes a flattened RGB view and carries the
  alpha plane separately.
* ``Image.Dither.ORDERED`` exists but is not implemented: Pillow silently
  behaves like ``Dither.NONE``. Ordered (Bayer) dither is an in-house numpy
  pass here.
* ``Image.Quantize.LIBIMAGEQUANT`` is compiled out (GPL). Never use it.
"""

from __future__ import annotations

import io
import json
import logging
import math
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from core.sprite.keying import apply_profile_alpha, hex_to_rgb
from core.sprite.pipeline import CancelToken, ProgressFn, no_progress, register_stage

logger = logging.getLogger(__name__)

Size = Tuple[int, int]

DITHER_MODES: Tuple[str, ...] = ("none", "bayer2", "bayer4", "bayer8", "floyd")
ANCHORS: Tuple[str, ...] = ("bottom_center", "center", "top_left", "top_center", "bottom_left")
# Mirrors core.upscaling.UpscalingMethod. core.upscaling is imported lazily in
# upscale_then_fit: its module import pulls torchvision (23 s on a machine
# with torch installed), and core.sprite must stay fast to import.
UPSCALE_METHODS: Tuple[str, ...] = ("lanczos", "realesrgan", "stability_api")
# Pixels below this alpha do not vote for palette colors (drops fringe blends).
PALETTE_ALPHA_MIN = 128
# Deterministic stride sub-sampling above this many opaque pixels keeps
# MEDIANCUT under a second for 16 frames of 720x720.
MAX_PALETTE_SAMPLES = 1_000_000

FLOYD_WARNING = (
    "Floyd-Steinberg diffuses quantization error from pixel to pixel, so the "
    "noise pattern changes on every frame. Animated sprites then show 'dither "
    "crawl'. Use bayer2, bayer4, bayer8, or none for animations. Use floyd "
    "only for a single exported frame."
)


# --- Task 1: integer fit + pad ----------------------------------------------

def integer_fit_scale(src: Size, cell: Size) -> int:
    """Smallest integer factor k with ceil(src / k) inside cell; 1 when src fits."""
    sw, sh = int(src[0]), int(src[1])
    cw, ch = int(cell[0]), int(cell[1])
    if sw < 1 or sh < 1 or cw < 1 or ch < 1:
        raise ValueError(f"sizes must be positive: src={src} cell={cell}")
    return max(1, math.ceil(sw / cw), math.ceil(sh / ch))


def anchor_offset(content: Size, cell: Size, anchor: str) -> Tuple[int, int]:
    """Top-left paste position of ``content`` inside ``cell`` for ``anchor``."""
    w, h = int(content[0]), int(content[1])
    cw, ch = int(cell[0]), int(cell[1])
    if w > cw or h > ch:
        raise ValueError(f"content {content} does not fit in cell {cell}")
    if anchor not in ANCHORS:
        raise ValueError(f"unknown anchor {anchor!r}; expected one of {ANCHORS}")
    x_center = (cw - w) // 2
    y_bottom = ch - h
    if anchor == "bottom_center":
        return x_center, y_bottom
    if anchor == "center":
        return x_center, (ch - h) // 2
    if anchor == "top_left":
        return 0, 0
    if anchor == "top_center":
        return x_center, 0
    return 0, y_bottom  # bottom_left


def fit_pad_integer(image: Image.Image, cell: Size, anchor: str,
                    *, scale: Optional[int] = None) -> Image.Image:
    """Box-filter downscale by an integer factor, then pad on a transparent canvas.

    The image is never distorted and never upscaled. Pass ``scale`` to force
    one factor across every frame of an action (all frames must share it so
    the animation does not jitter).
    """
    rgba = image if image.mode == "RGBA" else image.convert("RGBA")
    cell_wh = (int(cell[0]), int(cell[1]))
    factor = integer_fit_scale(rgba.size, cell_wh) if scale is None else int(scale)
    if factor < 1:
        raise ValueError(f"scale must be >= 1, got {scale}")
    reduced = rgba.reduce(factor) if factor > 1 else rgba
    canvas = Image.new("RGBA", cell_wh, (0, 0, 0, 0))
    canvas.paste(reduced, anchor_offset(reduced.size, cell_wh, anchor))
    return canvas
```

Notes for the implementer:
- `Image.reduce(k)` is an exact k×k box filter. Pillow converts RGBA to premultiplied `RGBa` inside `reduce`, so transparent neighbors do not darken edge pixels. The output size is `ceil(w/k) × ceil(h/k)`, which is why `integer_fit_scale` uses `ceil`.
- The header imports everything Tasks 2–7 need (`io`, `json`, `asdict`, `datetime`, `Path`, the keying and pipeline names). Keep them now so the module header never changes again. `core/sprite/pipeline.py` must never import `pixelart` (the package `__init__` imports `pixelart` after `.pipeline`).

- [x] **Step 4: Run the tests and confirm they pass**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pixelart.py -v
```

Expected: `11 passed`.

- [x] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/pixelart.py tests/sprite/test_pixelart.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): integer fit and pad for the pixel profile"
```

---

### Task 2: Resolution check and upscale-then-fit

**Files:**
- Modify: `core/sprite/pixelart.py` (append; finished-file lines 106–150)
- Modify: `tests/sprite/test_pixelart.py` (append; finished-file lines 125–177)

**Interfaces:**
- Consumes: `core.upscaling.upscale_image(image_data: bytes, target_width: int, target_height: int, method: str = "lanczos", **kwargs) -> bytes` (lazy import), `fit_pad_integer` (Task 1).
- Produces:
  - `resolution_check(src: Size, cell: Size) -> Optional[str]`
  - `upscale_then_fit(image: Image.Image, cell: Size, anchor: str, *, method: str = "lanczos") -> Image.Image`

- [x] **Step 1: Write the failing tests**

Add `resolution_check, upscale_then_fit` to the `from core.sprite.pixelart import (...)` block, then append:

```python
# --- Task 2 -------------------------------------------------------------------------

def test_resolution_check_none_when_source_large_enough():
    assert resolution_check((64, 64), (64, 64)) is None
    assert resolution_check((256, 256), (64, 64)) is None
    assert resolution_check((100, 40), (64, 64)) is None


def test_resolution_check_warns_when_smaller_in_both_axes():
    text = resolution_check((40, 30), (64, 64))
    assert text is not None
    assert "40x30" in text and "64x64" in text
    assert "upscale_small=True" in text
    assert "128x128" in text


def test_upscale_then_fit_upscales_small_source_proportionally(monkeypatch):
    calls = []
    install_fake_upscaler(monkeypatch, calls)
    src = square_frame((16, 8), (16, 8))
    out = upscale_then_fit(src, (64, 64), "bottom_center", method="lanczos")
    assert calls == [(64, 32, "lanczos")]
    assert out.size == (64, 64)
    arr = np.asarray(out)
    rows = np.where(arr[..., 3] > 0)[0]
    cols = np.where(arr[..., 3] > 0)[1]
    assert cols.min() == 0 and cols.max() == 63
    assert rows.max() == 63 and rows.min() == 32


def test_upscale_then_fit_is_fit_pad_when_source_large_enough():
    src = square_frame((128, 128), (128, 128))
    out = upscale_then_fit(src, (64, 64), "top_left", method="lanczos")
    assert np.array_equal(np.asarray(out), np.asarray(fit_pad_integer(src, (64, 64), "top_left")))


def test_upscale_then_fit_pads_when_upscaler_returns_original(monkeypatch):
    calls = []
    fake = types.ModuleType("core.upscaling")
    fake.upscale_image = lambda data, w, h, method="lanczos", **kw: (calls.append((w, h, method)), data)[1]
    monkeypatch.setitem(sys.modules, "core.upscaling", fake)
    src = square_frame((10, 20), (10, 20))
    out = upscale_then_fit(src, (64, 64), "center", method="lanczos")
    assert calls == [(32, 64, "lanczos")]
    assert out.size == (64, 64)
    assert opaque_pixels(out) == 10 * 20


def test_upscale_then_fit_rejects_unknown_method():
    with pytest.raises(ValueError):
        upscale_then_fit(square_frame((8, 8), (8, 8)), (64, 64), "center", method="magic")
```

- [x] **Step 2: Run the tests and confirm the failure**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pixelart.py -v
```

Expected: `ImportError: cannot import name 'resolution_check' from 'core.sprite.pixelart'`.

- [x] **Step 3: Append the implementation**

```python
# --- Task 2: resolution check + upscale ---------------------------------------

def resolution_check(src: Size, cell: Size) -> Optional[str]:
    """Warning text when the source is smaller than the cell in both axes."""
    sw, sh = int(src[0]), int(src[1])
    cw, ch = int(cell[0]), int(cell[1])
    if sw >= cw or sh >= ch:
        return None
    factor = min(cw / sw, ch / sh)
    return (
        f"Source frame {sw}x{sh} is smaller than the pixel cell {cw}x{ch}. "
        f"The pixel profile does not upscale by default, so the character fills "
        f"only part of the cell. Run the pipeline with upscale_small=True to "
        f"upscale {factor:.2f}x through core.upscaling first, or generate the "
        f"source at {cw}x{ch} or larger. An integer multiple such as "
        f"{2 * cw}x{2 * ch} gives the cleanest pixels."
    )


def upscale_then_fit(image: Image.Image, cell: Size, anchor: str,
                     *, method: str = "lanczos") -> Image.Image:
    """Upscale proportionally through ``core.upscaling`` when the source is
    smaller than the cell, then :func:`fit_pad_integer`."""
    if method not in UPSCALE_METHODS:
        raise ValueError(f"unknown upscale method {method!r}; expected one of {UPSCALE_METHODS}")
    rgba = image if image.mode == "RGBA" else image.convert("RGBA")
    cell_wh = (int(cell[0]), int(cell[1]))
    if resolution_check(rgba.size, cell_wh) is None:
        return fit_pad_integer(rgba, cell_wh, anchor)
    sw, sh = rgba.size
    factor = min(cell_wh[0] / sw, cell_wh[1] / sh)
    target_w = min(cell_wh[0], max(1, round(sw * factor)))
    target_h = min(cell_wh[1], max(1, round(sh * factor)))
    from core.upscaling import upscale_image  # lazy: see UPSCALE_METHODS note

    buf = io.BytesIO()
    rgba.save(buf, format="PNG")
    data = upscale_image(buf.getvalue(), target_w, target_h, method)
    upscaled = Image.open(io.BytesIO(data))
    upscaled.load()
    logger.info("pixel profile upscaled %dx%d -> %dx%d via %s", sw, sh,
                upscaled.width, upscaled.height, method)
    return fit_pad_integer(upscaled.convert("RGBA"), cell_wh, anchor)
```

Notes:
- The warning fires only when **both** axes are smaller than the cell. When one axis already reaches the cell, an upscale cannot make the character larger, so there is nothing to warn about.
- The target size is proportional (`factor = min(...)`), so `upscale_lanczos`'s exact-size resize never distorts. `upscale_image` swallows its own errors and returns the original bytes; `fit_pad_integer` then pads the small image. The stage never fails because an upscaler is missing.

- [x] **Step 4: Run the tests and confirm they pass**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pixelart.py -v
```

Expected: `17 passed`, total wall time under 3 s (proof that `core.upscaling` was not imported for real).

- [x] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/pixelart.py tests/sprite/test_pixelart.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): resolution check and upscale-then-fit for pixel frames"
```

---

### Task 3: Bayer threshold matrices

**Files:**
- Modify: `core/sprite/pixelart.py` (append; finished-file lines 151–165)
- Modify: `tests/sprite/test_pixelart.py` (append; finished-file lines 178–207)

**Interfaces:**
- Consumes: numpy.
- Produces: `bayer_matrix(n: int) -> np.ndarray` — shape `(n, n)`, float64, values `(rank + 0.5) / n²` in the open interval (0, 1), mean exactly 0.5, `n ∈ {2, 4, 8}`.

- [x] **Step 1: Write the failing tests**

Add `bayer_matrix` to the import block, then append:

```python
# --- Task 3 -------------------------------------------------------------------------

def test_bayer2_values():
    m = bayer_matrix(2)
    expected = (np.array([[0, 2], [3, 1]], dtype=np.float64) + 0.5) / 4.0
    assert np.allclose(m, expected)


def test_bayer_matrices_are_permutations_with_mean_half():
    for n in (2, 4, 8):
        m = bayer_matrix(n)
        assert m.shape == (n, n)
        ranks = np.round(m * n * n - 0.5).astype(int)
        assert sorted(ranks.flatten().tolist()) == list(range(n * n))
        assert abs(m.mean() - 0.5) < 1e-12
        assert m.min() > 0.0 and m.max() < 1.0


def test_bayer4_top_left_block_is_scaled_bayer2():
    m4 = bayer_matrix(4)
    ranks = np.round(m4 * 16 - 0.5).astype(int)
    assert ranks[:2, :2].tolist() == [[0, 8], [12, 4]]


def test_bayer_rejects_other_sizes():
    for bad in (1, 3, 16):
        with pytest.raises(ValueError):
            bayer_matrix(bad)
```

- [x] **Step 2: Run the tests and confirm the failure**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pixelart.py -v
```

Expected: `ImportError: cannot import name 'bayer_matrix' from 'core.sprite.pixelart'`.

- [x] **Step 3: Append the implementation**

```python
# --- Task 3: Bayer matrix ------------------------------------------------------

def bayer_matrix(n: int) -> np.ndarray:
    """Normalized n x n Bayer threshold matrix, n in {2, 4, 8}, values in (0, 1)."""
    if n not in (2, 4, 8):
        raise ValueError(f"bayer size must be 2, 4, or 8, got {n}")
    matrix = np.zeros((1, 1), dtype=np.int64)
    size = 1
    while size < n:
        matrix = np.block([[4 * matrix, 4 * matrix + 2],
                           [4 * matrix + 3, 4 * matrix + 1]])
        size *= 2
    return (matrix.astype(np.float64) + 0.5) / float(n * n)
```

- [x] **Step 4: Run the tests and confirm they pass**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pixelart.py -v
```

Expected: `21 passed`.

- [x] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/pixelart.py tests/sprite/test_pixelart.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): Bayer threshold matrices for ordered dither"
```

---

### Task 4: Hex helpers and the shared palette build

**Files:**
- Modify: `core/sprite/pixelart.py` (append; finished-file lines 166–213)
- Modify: `tests/sprite/test_pixelart.py` (append; finished-file lines 208–270)

**Interfaces:**
- Consumes: `core.sprite.keying.hex_to_rgb`, `PIL.Image.quantize(colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)`.
- Produces:
  - `hex_to_palette(palette: Sequence[str]) -> np.ndarray` — int32 `(P, 3)`; `(0, 3)` for an empty list
  - `palette_to_hex(colors: Sequence[Sequence[int]]) -> List[str]` — uppercase `#RRGGBB`
  - `build_shared_palette(frames: Sequence[Image.Image], colors: int) -> List[str]` — union of opaque pixels (alpha ≥ `PALETTE_ALPHA_MIN`), MEDIANCUT on a 1×N RGB mosaic, sorted dark to light, deduplicated, `[]` when nothing is opaque

- [x] **Step 1: Write the failing tests**

Add `build_shared_palette, hex_to_palette, palette_to_hex` to the import block, then append:

```python
# --- Task 4 -------------------------------------------------------------------------

def test_hex_round_trip():
    pal = hex_to_palette(["#FF0000", "#00ff00", "0000FF"])
    assert pal.shape == (3, 3)
    assert pal.tolist() == [[255, 0, 0], [0, 255, 0], [0, 0, 255]]
    assert palette_to_hex(pal) == ["#FF0000", "#00FF00", "#0000FF"]
    assert hex_to_palette([]).shape == (0, 3)


def test_pillow_mediancut_raises_on_rgba_but_our_path_does_not():
    rgba = Image.new("RGBA", (8, 8), (255, 0, 0, 255))
    with pytest.raises(ValueError):
        rgba.quantize(colors=4, method=Image.Quantize.MEDIANCUT)
    with pytest.raises(ValueError):
        rgba.quantize(colors=4, method=Image.Quantize.MAXCOVERAGE)
    assert build_shared_palette([rgba], 4) == ["#FF0000"]


def test_build_shared_palette_unions_frames_and_sorts_dark_to_light():
    f1 = square_frame((8, 8), (8, 8), color=(255, 0, 0, 255))
    f2 = square_frame((8, 8), (8, 8), color=(0, 0, 255, 255))
    f3 = square_frame((8, 8), (8, 8), color=(255, 255, 255, 255))
    assert build_shared_palette([f1, f2, f3], 8) == ["#0000FF", "#FF0000", "#FFFFFF"]


def test_build_shared_palette_ignores_transparent_and_fringe_pixels():
    arr = np.zeros((4, 4, 4), dtype=np.uint8)
    arr[:, :2] = (0, 255, 0, 255)
    arr[:, 2:] = (255, 0, 255, 100)
    frame = Image.fromarray(arr)
    assert build_shared_palette([frame], 8) == ["#00FF00"]


def test_build_shared_palette_empty_when_nothing_opaque():
    assert build_shared_palette([Image.new("RGBA", (4, 4), (0, 0, 0, 0))], 8) == []


def test_build_shared_palette_respects_color_budget_and_is_deterministic():
    rng = np.random.default_rng(7)
    arr = rng.integers(0, 256, (32, 32, 4), dtype=np.uint8)
    arr[..., 3] = 255
    frame = Image.fromarray(arr)
    pal_a = build_shared_palette([frame], 16)
    pal_b = build_shared_palette([frame], 16)
    assert pal_a == pal_b
    assert 1 <= len(pal_a) <= 16
    assert len(set(pal_a)) == len(pal_a)


def test_build_shared_palette_rejects_bad_sizes():
    frame = square_frame((4, 4), (4, 4))
    for bad in (0, 257):
        with pytest.raises(ValueError):
            build_shared_palette([frame], bad)


def test_build_shared_palette_subsamples_large_inputs(monkeypatch):
    monkeypatch.setattr(pixelart, "MAX_PALETTE_SAMPLES", 64)
    frame = square_frame((32, 32), (32, 32), color=(10, 200, 30, 255))
    assert build_shared_palette([frame], 4) == ["#0AC81E"]
```

- [x] **Step 2: Run the tests and confirm the failure**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pixelart.py -v
```

Expected: `ImportError: cannot import name 'build_shared_palette' from 'core.sprite.pixelart'`.

- [x] **Step 3: Append the implementation**

```python
# --- Task 4: shared palette ----------------------------------------------------

def hex_to_palette(palette: Sequence[str]) -> np.ndarray:
    """``["#RRGGBB", ...]`` -> int32 array of shape (P, 3)."""
    if len(palette) == 0:
        return np.zeros((0, 3), dtype=np.int32)
    return np.array([hex_to_rgb(c) for c in palette], dtype=np.int32)


def palette_to_hex(colors: Sequence[Sequence[int]]) -> List[str]:
    """Rows of (r, g, b) -> ``["#RRGGBB", ...]`` (uppercase)."""
    return ["#%02X%02X%02X" % (int(r), int(g), int(b)) for r, g, b in colors]


def _luma_key(rgb: Tuple[int, int, int]) -> Tuple[float, int, int, int]:
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b, r, g, b


def build_shared_palette(frames: Sequence[Image.Image], colors: int) -> List[str]:
    """MEDIANCUT over the union of every frame's opaque pixels.

    Returns at most ``colors`` hex strings, sorted dark to light, with no
    duplicates. Returns ``[]`` when no pixel reaches ``PALETTE_ALPHA_MIN``.
    """
    if not 1 <= int(colors) <= 256:
        raise ValueError(f"palette size must be 1..256, got {colors}")
    samples: List[np.ndarray] = []
    for frame in frames:
        arr = np.asarray(frame if frame.mode == "RGBA" else frame.convert("RGBA"))
        mask = arr[..., 3] >= PALETTE_ALPHA_MIN
        if mask.any():
            samples.append(arr[..., :3][mask])
    if not samples:
        return []
    pixels = np.concatenate(samples, axis=0)
    if len(pixels) > MAX_PALETTE_SAMPLES:
        step = math.ceil(len(pixels) / MAX_PALETTE_SAMPLES)
        pixels = pixels[::step]
    mosaic = Image.fromarray(np.ascontiguousarray(pixels.reshape(1, -1, 3)))
    quantized = mosaic.quantize(colors=int(colors), method=Image.Quantize.MEDIANCUT,
                                dither=Image.Dither.NONE)
    flat = quantized.getpalette()
    used = np.unique(np.asarray(quantized))
    entries = {(flat[3 * i], flat[3 * i + 1], flat[3 * i + 2]) for i in used}
    return palette_to_hex(sorted(entries, key=_luma_key))
```

Notes:
- The 1×N mosaic is a plain RGB image, so MEDIANCUT accepts it. Verified: a 1×200 000 mosaic quantizes to 32 colors in well under a second.
- `np.asarray(quantized)` on a `P` image yields the index plane; `used` drops any palette slot MEDIANCUT allocated but never referenced.
- The luminance sort makes the order independent of MEDIANCUT internals. `SheetMeta.palette` and the Aseprite palette chunk (sub-project 6) inherit that order.

- [x] **Step 4: Run the tests and confirm they pass**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pixelart.py -v
```

Expected: `29 passed`.

- [x] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/pixelart.py tests/sprite/test_pixelart.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): shared palette build with MEDIANCUT on flattened RGB"
```

---

### Task 5: Quantize to a fixed palette with none / Bayer / Floyd dither

**Files:**
- Modify: `core/sprite/pixelart.py` (append; finished-file lines 214–283)
- Modify: `tests/sprite/test_pixelart.py` (append; finished-file lines 271–364)

**Interfaces:**
- Consumes: `bayer_matrix` (Task 3), `hex_to_palette` (Task 4), `PIL.Image.quantize(palette=<P image>, dither=Image.Dither.FLOYDSTEINBERG)`.
- Produces:
  - `nearest_palette_indices(rgb_flat: np.ndarray, palette_rgb: np.ndarray, chunk: int = 65536) -> np.ndarray` — int64 `(N,)`; exact for integer input; ties → lowest index
  - `palette_spread(palette_rgb: np.ndarray) -> float` — mean nearest-neighbor RGB distance; 0.0 for fewer than 2 colors
  - `quantize_to_palette(image: Image.Image, palette: Sequence[str], dither: str) -> Image.Image` — RGBA out; alpha unchanged; fully transparent pixels become `(0, 0, 0, 0)`; empty palette → copy
  - `FLOYD_WARNING` (declared in Task 1; first consumer here and in Task 7)

- [x] **Step 1: Write the failing tests**

Add `FLOYD_WARNING, nearest_palette_indices, palette_spread, quantize_to_palette` to the import block, then append:

```python
# --- Task 5 -------------------------------------------------------------------------

PALETTE = ["#000000", "#FF0000", "#00FF00", "#0000FF", "#FFFFFF"]


def test_nearest_palette_indices_exact_and_tie_to_lowest():
    pal = hex_to_palette(PALETTE)
    rgb = np.array([[250, 5, 5], [0, 0, 0], [100, 100, 100], [10, 250, 10]], dtype=np.uint8)
    idx = nearest_palette_indices(rgb, pal)
    assert idx.tolist() == [1, 0, 0, 2]
    pal2 = hex_to_palette(["#000000", "#FFFFFF"])
    mid = np.array([[127, 127, 127], [128, 128, 128]], dtype=np.uint8)
    assert nearest_palette_indices(mid, pal2).tolist() == [0, 1]


def test_nearest_palette_indices_chunks_agree():
    rng = np.random.default_rng(3)
    rgb = rng.integers(0, 256, (1000, 3), dtype=np.uint8)
    pal = hex_to_palette(PALETTE)
    assert np.array_equal(nearest_palette_indices(rgb, pal, chunk=7),
                          nearest_palette_indices(rgb, pal, chunk=100000))


def test_palette_spread():
    assert palette_spread(hex_to_palette(["#000000"])) == 0.0
    assert palette_spread(hex_to_palette(["#000000", "#0000FF"])) == pytest.approx(255.0)


def test_quantize_none_maps_to_nearest_and_keeps_alpha():
    arr = np.zeros((2, 2, 4), dtype=np.uint8)
    arr[0, 0] = (250, 5, 5, 255)
    arr[0, 1] = (5, 250, 5, 128)
    arr[1, 0] = (5, 5, 250, 255)
    arr[1, 1] = (77, 77, 77, 0)
    out = quantize_to_palette(Image.fromarray(arr), PALETTE, "none")
    res = np.asarray(out)
    assert tuple(res[0, 0]) == (255, 0, 0, 255)
    assert tuple(res[0, 1]) == (0, 255, 0, 128)
    assert tuple(res[1, 0]) == (0, 0, 255, 255)
    assert tuple(res[1, 1]) == (0, 0, 0, 0)


def test_quantize_output_colors_are_subset_of_palette():
    rng = np.random.default_rng(11)
    arr = rng.integers(0, 256, (16, 16, 4), dtype=np.uint8)
    arr[..., 3] = 255
    src = Image.fromarray(arr)
    pal_set = {tuple(c) for c in hex_to_palette(PALETTE).tolist()}
    for mode in ("none", "bayer2", "bayer4", "bayer8", "floyd"):
        out = np.asarray(quantize_to_palette(src, PALETTE, mode))
        colors = {tuple(px[:3]) for px in out.reshape(-1, 4)}
        assert colors <= pal_set, mode
        assert (out[..., 3] == 255).all(), mode


def test_quantize_bayer_produces_a_checker_on_a_midtone():
    src = Image.new("RGBA", (4, 4), (128, 128, 128, 255))
    out = np.asarray(quantize_to_palette(src, ["#000000", "#FFFFFF"], "bayer2"))
    assert (out[..., 3] == 255).all()
    assert out[0, 0, 0] != out[0, 1, 0]
    assert out[0, 0, 0] == out[1, 1, 0]
    none = np.asarray(quantize_to_palette(src, ["#000000", "#FFFFFF"], "none"))
    assert (none[..., 0] == none[0, 0, 0]).all()


def test_quantize_floyd_uses_pillow_diffusion():
    src = Image.new("RGBA", (8, 8), (128, 128, 128, 255))
    out = np.asarray(quantize_to_palette(src, ["#000000", "#FFFFFF"], "floyd"))
    values = set(out[..., 0].flatten().tolist())
    assert values == {0, 255}


def test_quantize_floyd_transparent_pixels_do_not_bleed():
    arr = np.zeros((4, 4, 4), dtype=np.uint8)
    arr[:, 2:] = (250, 250, 250, 255)
    out = np.asarray(quantize_to_palette(Image.fromarray(arr), ["#000000", "#FFFFFF"], "floyd"))
    assert (out[:, :2] == 0).all()
    assert (out[:, 2:, :3] == 255).all()


def test_quantize_empty_palette_returns_copy_and_bad_dither_raises():
    src = square_frame((4, 4), (4, 4))
    out = quantize_to_palette(src, [], "none")
    assert np.array_equal(np.asarray(out), np.asarray(src))
    assert out is not src
    with pytest.raises(ValueError):
        quantize_to_palette(src, PALETTE, "ordered")


def test_floyd_warning_names_dither_crawl():
    assert "crawl" in FLOYD_WARNING
    assert "bayer" in FLOYD_WARNING
```

- [x] **Step 2: Run the tests and confirm the failure**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pixelart.py -v
```

Expected: `ImportError: cannot import name 'nearest_palette_indices' from 'core.sprite.pixelart'`.

- [x] **Step 3: Append the implementation**

```python
# --- Task 5: quantize to a fixed palette ---------------------------------------

def nearest_palette_indices(rgb_flat: np.ndarray, palette_rgb: np.ndarray,
                            chunk: int = 65536) -> np.ndarray:
    """Index of the nearest palette color (squared RGB distance) per pixel.

    Exact for integer inputs: every intermediate is an integer below 2**24,
    so float32 holds it without rounding. Ties resolve to the lowest index.
    """
    pal = np.asarray(palette_rgb, dtype=np.float32)
    pal_sq = np.sum(pal * pal, axis=1)
    out = np.empty(len(rgb_flat), dtype=np.int64)
    for start in range(0, len(rgb_flat), chunk):
        block = np.asarray(rgb_flat[start:start + chunk], dtype=np.float32)
        dist = (np.sum(block * block, axis=1)[:, None]
                - 2.0 * (block @ pal.T) + pal_sq[None, :])
        out[start:start + chunk] = np.argmin(dist, axis=1)
    return out


def palette_spread(palette_rgb: np.ndarray) -> float:
    """Mean nearest-neighbor RGB distance inside the palette (dither amplitude)."""
    pal = np.asarray(palette_rgb, dtype=np.float32)
    if len(pal) < 2:
        return 0.0
    diff = pal[:, None, :] - pal[None, :, :]
    dist = np.sqrt(np.sum(diff * diff, axis=-1))
    np.fill_diagonal(dist, np.inf)
    return float(np.mean(np.min(dist, axis=1)))


def quantize_to_palette(image: Image.Image, palette: Sequence[str], dither: str) -> Image.Image:
    """Map every pixel to the nearest color of ``palette``; alpha is carried unchanged.

    ``dither``: none | bayer2 | bayer4 | bayer8 | floyd. Fully transparent
    pixels come back as (0, 0, 0, 0).
    """
    if dither not in DITHER_MODES:
        raise ValueError(f"unknown dither {dither!r}; expected one of {DITHER_MODES}")
    rgba = image if image.mode == "RGBA" else image.convert("RGBA")
    pal = hex_to_palette(palette)
    if len(pal) == 0:
        return rgba.copy()
    arr = np.asarray(rgba)
    rgb = arr[..., :3]
    alpha = arr[..., 3]
    height, width = alpha.shape
    if dither == "floyd":
        # Transparent pixels get an exact palette color so they diffuse no error.
        filled = rgb.copy()
        filled[alpha == 0] = pal[0]
        pal_img = Image.new("P", (1, 1))
        pal_img.putpalette(pal.astype(np.uint8).flatten().tolist())
        quantized = Image.fromarray(np.ascontiguousarray(filled)).quantize(
            palette=pal_img, dither=Image.Dither.FLOYDSTEINBERG)
        out_rgb = np.asarray(quantized.convert("RGB"))
    else:
        work = rgb.astype(np.float32)
        if dither != "none":
            n = int(dither[len("bayer"):])
            tiled = np.tile(bayer_matrix(n), (math.ceil(height / n), math.ceil(width / n)))
            offsets = (tiled[:height, :width] - 0.5) * palette_spread(pal)
            work = np.clip(work + offsets[..., None], 0.0, 255.0)
        idx = nearest_palette_indices(work.reshape(-1, 3), pal)
        out_rgb = pal[idx].reshape(height, width, 3)
    out = np.dstack([out_rgb.astype(np.uint8), alpha]).astype(np.uint8)
    out[alpha == 0] = (0, 0, 0, 0)
    return Image.fromarray(np.ascontiguousarray(out))
```

Notes:
- Pillow 11.3 honors the real palette length in `putpalette`: a 2-color palette maps a near-black pixel to the nearer of the two colors, never to a zero-padded slot (verified). Pillow's palette cache quantizes lookups to 6 bits per channel, which is fine for error diffusion; the exact numpy path handles `none` and Bayer.
- The Bayer offset scales with `palette_spread`, so a dense palette dithers softly and a sparse palette dithers hard. The same offset applies to all three channels (luminance-style ordered dither).
- Memory: `nearest_palette_indices` never allocates more than `chunk × P` float32 (64 MB at 256 colors). A 720×720 frame with 256 colors maps in well under a second.

- [x] **Step 4: Run the tests and confirm they pass**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pixelart.py -v
```

Expected: `39 passed`.

- [x] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/pixelart.py tests/sprite/test_pixelart.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): quantize frames to a fixed palette with none/bayer/floyd dither"
```

---

### Task 6: Palette lock, remap, ensure and rebuild

**Files:**
- Modify: `core/sprite/pixelart.py` (append; finished-file lines 284–316)
- Modify: `tests/sprite/test_pixelart.py` (append; finished-file lines 365–429)

**Interfaces:**
- Consumes: `OutputProfile.palette_size / palette_lock / locked_palette / name` (design §2), `SpriteProject.name / modified` (design §2), `build_shared_palette`, `quantize_to_palette`.
- Produces:
  - `remap_to_locked(image: Image.Image, locked_palette: Sequence[str]) -> Image.Image` — Aseprite "Remap": nearest color, no dither
  - `rebuild_palette(project, profile, frames: Sequence[Image.Image]) -> List[str]` — always rebuilds, stores on `profile.locked_palette` (`None` when empty), stamps `project.modified`
  - `ensure_palette(project, profile, frames: Sequence[Image.Image]) -> List[str]` — `[]` when `palette_size is None`; the stored palette when `palette_lock` and it exists; else `rebuild_palette`

The tests use `SimpleNamespace` stand-ins on purpose: the functions read only the attributes named above, and Task 7 exercises the real dataclasses.

- [x] **Step 1: Write the failing tests**

Add `ensure_palette, rebuild_palette, remap_to_locked` to the import block, then append:

```python
# --- Task 6 -------------------------------------------------------------------------

def make_profile(**kw):
    base = dict(name="pixel", enabled=True, cell_size=(64, 64), binary_alpha=True,
                alpha_threshold=128, defringe_px=0, palette_size=8, dither="none",
                palette_lock=True, locked_palette=None)
    base.update(kw)
    return SimpleNamespace(**base)


def make_project():
    return SimpleNamespace(name="proj", modified="2026-01-01T00:00:00")


def test_remap_to_locked_is_nearest_no_dither():
    src = Image.new("RGBA", (4, 4), (100, 100, 100, 255))
    out = np.asarray(remap_to_locked(src, ["#000000", "#FFFFFF"]))
    assert (out[..., :3] == 0).all()
    assert (out[..., 3] == 255).all()


def test_ensure_palette_builds_and_locks_on_first_run():
    project, profile = make_project(), make_profile()
    frames = [square_frame((8, 8), (8, 8), color=(255, 0, 0, 255))]
    assert ensure_palette(project, profile, frames) == ["#FF0000"]
    assert profile.locked_palette == ["#FF0000"]
    assert project.modified != "2026-01-01T00:00:00"


def test_ensure_palette_reuses_locked_palette_when_locked():
    project, profile = make_project(), make_profile(locked_palette=["#123456"])
    frames = [square_frame((8, 8), (8, 8), color=(255, 0, 0, 255))]
    assert ensure_palette(project, profile, frames) == ["#123456"]
    assert profile.locked_palette == ["#123456"]


def test_ensure_palette_rebuilds_every_run_when_unlocked():
    project, profile = make_project(), make_profile(palette_lock=False, locked_palette=["#123456"])
    frames = [square_frame((8, 8), (8, 8), color=(0, 255, 0, 255))]
    assert ensure_palette(project, profile, frames) == ["#00FF00"]
    assert profile.locked_palette == ["#00FF00"]


def test_ensure_palette_empty_when_no_palette_size():
    project, profile = make_project(), make_profile(palette_size=None, locked_palette=["#123456"])
    assert ensure_palette(project, profile, []) == []
    assert profile.locked_palette == ["#123456"]


def test_rebuild_palette_overrides_lock():
    project, profile = make_project(), make_profile(locked_palette=["#123456"])
    frames = [square_frame((8, 8), (8, 8), color=(0, 0, 255, 255))]
    assert rebuild_palette(project, profile, frames) == ["#0000FF"]
    assert profile.locked_palette == ["#0000FF"]


def test_rebuild_palette_clears_lock_when_frames_are_empty():
    project, profile = make_project(), make_profile(locked_palette=["#123456"])
    assert rebuild_palette(project, profile, [Image.new("RGBA", (4, 4), (0, 0, 0, 0))]) == []
    assert profile.locked_palette is None


def test_rebuild_palette_requires_palette_size():
    with pytest.raises(ValueError):
        rebuild_palette(make_project(), make_profile(palette_size=None), [])
```

- [x] **Step 2: Run the tests and confirm the failure**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pixelart.py -v
```

Expected: `ImportError: cannot import name 'ensure_palette' from 'core.sprite.pixelart'`.

- [x] **Step 3: Append the implementation**

```python
# --- Task 6: lock / remap ---------------------------------------------------------

def remap_to_locked(image: Image.Image, locked_palette: Sequence[str]) -> Image.Image:
    """Aseprite-style "Remap": nearest color, no dither, alpha untouched."""
    return quantize_to_palette(image, locked_palette, "none")


def rebuild_palette(project: Any, profile: Any, frames: Sequence[Image.Image]) -> List[str]:
    """Build a new shared palette from ``frames`` and store it on ``profile``."""
    if profile.palette_size is None:
        raise ValueError(f"profile {profile.name!r} has no palette_size")
    palette = build_shared_palette(frames, profile.palette_size)
    profile.locked_palette = list(palette) if palette else None
    project.modified = datetime.now().isoformat(timespec="seconds")
    logger.info("sprite project %r: rebuilt %s palette with %d colors",
                project.name, profile.name, len(palette))
    return palette


def ensure_palette(project: Any, profile: Any, frames: Sequence[Image.Image]) -> List[str]:
    """Return the palette the pixel stage must use.

    * ``palette_size is None`` -> ``[]`` (no quantization).
    * ``palette_lock`` and a stored ``locked_palette`` -> that palette.
    * otherwise -> :func:`rebuild_palette` (the first run locks it).
    """
    if profile.palette_size is None:
        return []
    if profile.palette_lock and profile.locked_palette:
        return list(profile.locked_palette)
    return rebuild_palette(project, profile, frames)
```

Lock semantics in one sentence each: the first pixel run of a project builds the palette and stores it; every later action maps to the stored palette while `palette_lock` is on; `palette_lock` off rebuilds on every run; only `rebuild_palette` (the GUI "Rebuild palette" action, sub-project 5b) replaces a locked palette. The palette persists because `OutputProfile` is part of `project.iasprite.json`.

- [x] **Step 4: Run the tests and confirm they pass**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pixelart.py -v
```

Expected: `47 passed`.

- [x] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/pixelart.py tests/sprite/test_pixelart.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): palette lock, remap, and rebuild semantics"
```

---

### Task 7: The `pixel` stage runner and its registration

**Files:**
- Modify: `core/sprite/pixelart.py` (append; finished-file lines 317–409: `pixel_stage_settings`, `run_pixel_stage`, the `register_stage` call)
- Modify: `core/sprite/__init__.py` — one import line at the end
- Create: `tests/sprite/test_pipeline_pixel.py` (214 lines)

**Interfaces:**
- Consumes (registry contract shared by sub-projects 1, 3, 4; names verified against sub-project 1's draft on 2026-08-29):
  - `core.sprite.pipeline`: `StageRunner = Callable[[SpriteProject, ActionCard, List[Path], Path, ProgressFn, Optional[CancelToken]], List[Path]]`, `SettingsFn = Callable[[SpriteProject, ActionCard], Dict[str, Any]]`, `STAGE_RUNNERS`, `STAGE_SETTINGS`, `STAGE_CODE_VERSION`, `register_stage(stage, runner, settings_fn=None, code_version=1) -> None` (re-registering replaces all three), `identity_runner` (sub-project 1's placeholder for `pixel`, registered at version 1; its registration test asserts only that every stage has a callable runner, so replacing `pixel` breaks nothing), `STAGES`, `UPSTREAM` (`"pixel" -> "stabilize"`), `stage_dir`, `stage_fingerprint`, `run_pipeline(project, action, *, upto="pixel", progress=no_progress, token=None, force=False)`, `CancelToken`, `Cancelled`, `ProgressFn`, `no_progress`
  - `core.sprite.project`: `OutputProfile` with the two fields sub-project 1 owns — `upscale_small: bool = False`, `upscale_method: str = "lanczos"` — plus `StabilizeSettings.anchor`, `ActionCard(id, name, prompt, ...)`, `SpriteProject(name, project_dir=None, ...)` with defaults for every other field, `SpriteProject.profile(name) -> Optional[OutputProfile]`, `.profiles`, `.stabilize`, `.stage_fingerprints`, `.modified`, `.sheet_meta(profile: str) -> SheetMeta` (passes `palette=list(prof.locked_palette) if prof.locked_palette and prof.palette_size else None`)
  - `core.sprite.keying.apply_profile_alpha(image, profile) -> Image` (returns the image unchanged when `profile.binary_alpha` is False; else re-composes RGBA with `binary_alpha(alpha, profile.alpha_threshold, profile.defringe_px)`, alpha in {0, 255})
  - `core.sprite.pixelart` Tasks 1–6: `FLOYD_WARNING`, `ensure_palette`, `fit_pad_integer`, `integer_fit_scale`, `quantize_to_palette`, `resolution_check`, `upscale_then_fit`
- Produces:
  - `pixelart.pixel_stage_settings(project, action) -> Dict[str, Any]` — `asdict(profile)` of the pixel profile; `{}` when absent or disabled; this dict is the stage's fingerprint input, so `locked_palette`, `upscale_small`, and `upscale_method` all invalidate the cache
  - `pixelart.run_pixel_stage(project, action, input_frames: List[Path], out_dir: Path, progress: ProgressFn, token: Optional[CancelToken]) -> List[Path]` — a `StageRunner`; reads `upscale_small`/`upscale_method` from the profile
  - module-level `register_stage("pixel", run_pixel_stage, settings_fn=pixel_stage_settings, code_version=2)` at the bottom of `pixelart.py`; `core/sprite/__init__.py` imports `pixelart` **after** `.pipeline`, so the call replaces `identity_runner` whenever the package loads and `STAGE_CODE_VERSION["pixel"] == 2`
  - `stages/<action_id>/pixel/pixel.json` manifest: `cell_size, scale, anchor, binary_alpha, palette, dither, upscale_small, upscale_method, warnings`
  - Progress messages the GUI (5b) shows: `"fit NNNN.png (1/k)"`, `"wrote NNNN.png"`, `"warning: <text>"`
  - `SheetMeta.palette` needs no code here: sub-project 1's `sheet_meta` copies `locked_palette`, which `ensure_palette` fills; `test_sheet_meta_pixel_carries_locked_palette` pins that

- [x] **Step 1: Write the failing tests**

```python
# tests/sprite/test_pipeline_pixel.py
import io
import json
import sys
import types

import numpy as np
import pytest
from PIL import Image

from core.sprite import pipeline as pipeline_mod
from core.sprite.pipeline import (
    STAGE_CODE_VERSION, STAGE_RUNNERS, STAGE_SETTINGS, STAGES, Cancelled, CancelToken,
    no_progress, run_pipeline, stage_dir, stage_fingerprint,
)
from core.sprite.pixelart import pixel_stage_settings, run_pixel_stage
from core.sprite.project import ActionCard, OutputProfile, SpriteProject, StabilizeSettings


def make_profile(**kw):
    base = dict(name="pixel", enabled=True, cell_size=(32, 32), binary_alpha=True,
                alpha_threshold=128, defringe_px=0, palette_size=4, dither="none",
                palette_lock=True, locked_palette=None, upscale_small=False,
                upscale_method="lanczos")
    base.update(kw)
    return OutputProfile(**base)


def make_project(tmp_path, profile):
    project = SpriteProject(name="proj", project_dir=tmp_path / "proj")
    project.profiles = [OutputProfile(name="hd", cell_size=(256, 256)), profile]
    project.stabilize = StabilizeSettings(anchor="bottom_center")
    return project


def make_action():
    return ActionCard(id="a1", name="walk", prompt="walk cycle")


def write_frames(tmp_path, count=3, size=(128, 128), square=(64, 128)):
    """Opaque red bar plus a 4 px soft (alpha 90) edge; the bar slides 8 px per frame."""
    src = tmp_path / "stabilized"
    src.mkdir()
    paths = []
    for i in range(count):
        arr = np.zeros((size[1], size[0], 4), dtype=np.uint8)
        x0 = 8 * i
        arr[:square[1], x0:x0 + square[0]] = (200, 40, 40, 255)
        arr[:square[1], x0 + square[0]:x0 + square[0] + 4] = (200, 40, 40, 90)
        path = src / f"{i + 1:04d}.png"
        Image.fromarray(arr).save(path)
        paths.append(path)
    return paths


def test_pixel_stage_writes_fitted_binary_quantized_frames(tmp_path):
    inputs = write_frames(tmp_path)
    profile = make_profile()
    project = make_project(tmp_path, profile)
    out_dir = tmp_path / "pixel"
    outputs = run_pixel_stage(project, make_action(), inputs, out_dir, no_progress, None)
    assert [p.name for p in outputs] == ["0001.png", "0002.png", "0003.png"]
    for path in outputs:
        img = Image.open(path)
        assert img.size == (32, 32) and img.mode == "RGBA"
        arr = np.asarray(img)
        assert set(np.unique(arr[..., 3]).tolist()) <= {0, 255}
        opaque = arr[arr[..., 3] == 255][:, :3]
        assert {tuple(px) for px in opaque} <= {(200, 40, 40)}
    assert profile.locked_palette == ["#C82828"]
    manifest = json.loads((out_dir / "pixel.json").read_text(encoding="utf-8"))
    assert manifest["scale"] == 4
    assert manifest["palette"] == ["#C82828"]
    assert manifest["warnings"] == []


def test_pixel_stage_reuses_locked_palette(tmp_path):
    inputs = write_frames(tmp_path)
    profile = make_profile(locked_palette=["#000000", "#FFFFFF"])
    project = make_project(tmp_path, profile)
    outputs = run_pixel_stage(project, make_action(), inputs, tmp_path / "pixel", no_progress, None)
    arr = np.asarray(Image.open(outputs[0]))
    opaque = arr[arr[..., 3] == 255][:, :3]
    assert {tuple(px) for px in opaque} == {(0, 0, 0)}
    assert profile.locked_palette == ["#000000", "#FFFFFF"]


def test_pixel_stage_warns_on_small_source_and_does_not_upscale(tmp_path):
    inputs = write_frames(tmp_path, count=1, size=(16, 16), square=(8, 16))
    project = make_project(tmp_path, make_profile(palette_size=None))
    messages = []
    outputs = run_pixel_stage(project, make_action(), inputs, tmp_path / "pixel",
                              lambda stage, done, total, msg: messages.append(msg), None)
    arr = np.asarray(Image.open(outputs[0]))
    assert int((arr[..., 3] == 255).sum()) == 8 * 16
    manifest = json.loads((tmp_path / "pixel" / "pixel.json").read_text(encoding="utf-8"))
    assert len(manifest["warnings"]) == 1 and "16x16" in manifest["warnings"][0]
    assert any(msg.startswith("warning: ") for msg in messages)
    assert manifest["palette"] == []


def test_pixel_stage_upscale_small_fills_cell(tmp_path, monkeypatch):
    fake = types.ModuleType("core.upscaling")
    calls = []

    def upscale_image(image_data, target_width, target_height, method="lanczos", **kwargs):
        calls.append(method)
        img = Image.open(io.BytesIO(image_data))
        img.load()
        out = io.BytesIO()
        img.resize((target_width, target_height), Image.Resampling.NEAREST).save(out, format="PNG")
        return out.getvalue()

    fake.upscale_image = upscale_image
    monkeypatch.setitem(sys.modules, "core.upscaling", fake)
    inputs = write_frames(tmp_path, count=1, size=(16, 16), square=(8, 16))
    profile = make_profile(palette_size=None)
    profile.upscale_small = True
    profile.upscale_method = "realesrgan"
    project = make_project(tmp_path, profile)
    outputs = run_pixel_stage(project, make_action(), inputs, tmp_path / "pixel", no_progress, None)
    arr = np.asarray(Image.open(outputs[0]))
    assert int((arr[..., 3] == 255).sum()) == 16 * 32
    assert calls == ["realesrgan"]
    manifest = json.loads((tmp_path / "pixel" / "pixel.json").read_text(encoding="utf-8"))
    assert manifest["warnings"] == []
    assert manifest["upscale_small"] is True and manifest["upscale_method"] == "realesrgan"


def test_pixel_stage_floyd_adds_crawl_warning(tmp_path):
    inputs = write_frames(tmp_path, count=2)
    project = make_project(tmp_path, make_profile(dither="floyd"))
    run_pixel_stage(project, make_action(), inputs, tmp_path / "pixel", no_progress, None)
    manifest = json.loads((tmp_path / "pixel" / "pixel.json").read_text(encoding="utf-8"))
    assert any("crawl" in text for text in manifest["warnings"])


def test_pixel_stage_skips_when_profile_disabled_or_absent(tmp_path):
    inputs = write_frames(tmp_path, count=1)
    project = make_project(tmp_path, make_profile(enabled=False))
    assert run_pixel_stage(project, make_action(), inputs, tmp_path / "pixel", no_progress, None) == []
    assert not (tmp_path / "pixel").exists()
    project.profiles = [OutputProfile(name="hd")]
    assert run_pixel_stage(project, make_action(), inputs, tmp_path / "pixel", no_progress, None) == []
    assert not (tmp_path / "pixel").exists()


def test_pixel_stage_honors_cancel_token(tmp_path):
    inputs = write_frames(tmp_path, count=3)
    project = make_project(tmp_path, make_profile())
    token = CancelToken()

    def cancel_after_first_fit(stage, done, total, msg):
        if msg.startswith("fit ") and done == 1:
            token.cancel()

    with pytest.raises(Cancelled):
        run_pixel_stage(project, make_action(), inputs, tmp_path / "pixel",
                        cancel_after_first_fit, token)
    assert not (tmp_path / "pixel" / "pixel.json").exists()


def test_pixel_stage_is_registered_at_code_version_2():
    assert STAGE_RUNNERS["pixel"] is run_pixel_stage
    assert STAGE_SETTINGS["pixel"] is pixel_stage_settings
    assert STAGE_CODE_VERSION["pixel"] == 2


def test_pixel_settings_drive_the_fingerprint(tmp_path):
    profile = make_profile()
    project = make_project(tmp_path, profile)
    action = make_action()
    settings = pixel_stage_settings(project, action)
    assert settings["upscale_small"] is False and settings["upscale_method"] == "lanczos"
    assert settings["locked_palette"] is None
    base = stage_fingerprint(project, action, "pixel")
    profile.upscale_small = True
    assert stage_fingerprint(project, action, "pixel") != base
    profile.upscale_small = False
    profile.locked_palette = ["#112233"]
    assert stage_fingerprint(project, action, "pixel") != base
    profile.locked_palette = None
    profile.enabled = False
    assert pixel_stage_settings(project, action) == {}
    project.profiles = [OutputProfile(name="hd")]
    assert pixel_stage_settings(project, action) == {}


def test_run_pipeline_dispatches_pixel_runner_with_stabilize_frames(tmp_path, monkeypatch):
    project = make_project(tmp_path, make_profile())
    action = make_action()
    project.actions = [action]
    frame = write_frames(tmp_path, count=1)[0]
    for stage in STAGES[:STAGES.index("pixel")]:
        out_dir = stage_dir(project, action, stage)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / frame.name).write_bytes(frame.read_bytes())
        project.stage_fingerprints.setdefault(action.id, {})[stage] = stage_fingerprint(
            project, action, stage)
    calls = []

    def fake_runner(project, action, input_frames, out_dir, progress, token):
        calls.append(([p.name for p in input_frames], out_dir))
        return []

    monkeypatch.setitem(pipeline_mod.STAGE_RUNNERS, "pixel", fake_runner)
    run_pipeline(project, action, upto="pixel")
    assert calls == [(["0001.png"], stage_dir(project, action, "pixel"))]


def test_sheet_meta_pixel_carries_locked_palette(tmp_path):
    profile = make_profile(locked_palette=["#000000", "#FF00FF"])
    project = make_project(tmp_path, profile)
    assert project.sheet_meta("pixel").palette == ["#000000", "#FF00FF"]
    assert project.sheet_meta("hd").palette is None
```

`test_run_pipeline_dispatches_pixel_runner_with_stabilize_frames` seeds every earlier stage as "cached" through the public contract only (`stage_dir`, `stage_fingerprint`, `stage_fingerprints`), so it needs no ffmpeg and no clip. Sub-project 1's `is_stage_current` requires a recorded fingerprint, at least one PNG in the stage directory, and fingerprint equality; the test writes the PNG **before** it records the fingerprint because the `extract` settings hash the directory listing. The tests build their own profiles, so the enabled/disabled default of `default_profiles()` does not matter to them.

- [x] **Step 2: Run the tests and confirm the failure**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pipeline_pixel.py -v
```

Expected: `ImportError: cannot import name 'pixel_stage_settings' from 'core.sprite.pixelart'`.

- [x] **Step 3: Implement**

3a. Append the stage to `core/sprite/pixelart.py` (the header from Task 1 already imports `json`, `asdict`, `Path`, `Dict`, `apply_profile_alpha`, `CancelToken`, `ProgressFn`, `no_progress`, `register_stage`):

```python
# --- Task 7: pipeline stage ----------------------------------------------------

def pixel_stage_settings(project: Any, action: Any) -> Dict[str, Any]:
    """Settings that feed the ``pixel`` stage fingerprint: the whole pixel profile.

    ``locked_palette``, ``upscale_small`` and ``upscale_method`` are fields of
    the profile, so a rebuilt palette or a toggled upscale re-runs the stage
    by itself. ``{}`` when the profile is absent or disabled.
    """
    profile = project.profile("pixel")
    if profile is None or not profile.enabled:
        return {}
    return asdict(profile)


def run_pixel_stage(project: Any, action: Any, input_frames: List[Path], out_dir: Path,
                    progress: ProgressFn, token: Optional[CancelToken]) -> List[Path]:
    """Stabilized frames -> integer fit -> binary alpha -> shared palette -> PNGs.

    ``StageRunner`` signature (sub-project 1 registry). Writes
    ``out_dir/<input name>`` per frame plus ``out_dir/pixel.json`` (scale,
    palette, warnings). Returns the PNG paths in input order. Returns ``[]``
    without touching disk when the pixel profile is absent or disabled.
    """
    profile = project.profile("pixel")
    if profile is None or not profile.enabled:
        logger.info("pixel stage skipped for %s: profile absent or disabled", action.name)
        return []
    cell = (int(profile.cell_size[0]), int(profile.cell_size[1]))
    anchor = project.stabilize.anchor
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(input_frames)
    warnings: List[str] = []

    frames: List[Image.Image] = []
    for path in input_frames:
        if token is not None:
            token.raise_if_cancelled()
        with Image.open(path) as img:
            frames.append(img.convert("RGBA"))
    scale = max((integer_fit_scale(f.size, cell) for f in frames), default=1)

    fitted: List[Image.Image] = []
    for index, frame in enumerate(frames):
        if token is not None:
            token.raise_if_cancelled()
        warning = resolution_check(frame.size, cell)
        if warning is not None and profile.upscale_small:
            image = upscale_then_fit(frame, cell, anchor, method=profile.upscale_method)
        else:
            if warning is not None and warning not in warnings:
                warnings.append(warning)
            image = fit_pad_integer(frame, cell, anchor, scale=scale)
        image = apply_profile_alpha(image, profile)
        arr = np.array(image.convert("RGBA"))
        arr[arr[..., 3] == 0] = (0, 0, 0, 0)
        fitted.append(Image.fromarray(arr))
        progress("pixel", index + 1, total, f"fit {input_frames[index].name} (1/{scale})")

    palette = ensure_palette(project, profile, fitted)
    if palette and profile.dither == "floyd":
        warnings.append(FLOYD_WARNING)

    outputs: List[Path] = []
    for index, image in enumerate(fitted):
        if token is not None:
            token.raise_if_cancelled()
        if palette:
            image = quantize_to_palette(image, palette, profile.dither)
        target = out_dir / input_frames[index].name
        image.save(target, format="PNG")
        outputs.append(target)
        progress("pixel", index + 1, total, f"wrote {target.name}")

    manifest = {
        "cell_size": list(cell), "scale": scale, "anchor": anchor,
        "binary_alpha": bool(profile.binary_alpha), "palette": list(palette),
        "dither": profile.dither if palette else "none",
        "upscale_small": bool(profile.upscale_small),
        "upscale_method": str(profile.upscale_method), "warnings": warnings,
    }
    (out_dir / "pixel.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for text in warnings:
        logger.warning("pixel stage (%s): %s", action.name, text)
        progress("pixel", total, total, f"warning: {text}")
    return outputs


# Importing this module registers the stage. core/sprite/__init__.py imports it
# after .pipeline, so this call replaces sub-project 1's identity runner.
# code_version=2: the identity runner is version 1, and a real runner at the
# same version with the same settings would reuse a stale identity output.
register_stage("pixel", run_pixel_stage, settings_fn=pixel_stage_settings, code_version=2)
```

3b. `core/sprite/__init__.py`: append this line **after** every other import (the `.pipeline` import must run first, so the placeholder registration happens before this one replaces it):

```python
from . import pixelart  # noqa: E402,F401  registers the "pixel" stage runner
```

Why the order inside `run_pixel_stage` matters: the palette is built from the **fitted, binary-alpha** frames, so it reflects colors at the pixel resolution and never contains fringe blends. One `scale` for the whole action keeps every frame at the same size, which is what stops jitter. The manifest is the GUI's durable record of the resolution warning; the `progress` message is the live one. `run_pipeline` resolves the stage's input through `UPSTREAM["pixel"] == "stabilize"`, so the runner never sees the `hd` outputs. A bad `upscale_method` string raises `ValueError` from `upscale_then_fit`; the pipeline's failure handling logs it with the profile settings.

- [x] **Step 4: Run the tests and confirm they pass**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pipeline_pixel.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pixelart.py -v
```

Expected: `58 passed`.

- [x] **Step 5: Run the whole sprite suite**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite -v
```

Expected: every test passes without an edit to any sub-project 1 test. Sub-project 1's `test_every_stage_has_a_registered_runner` asserts only that every stage has a callable runner, and its `test_pixel_stage_is_skipped_while_disabled_and_runs_when_enabled` asserts only file names and location, so the real runner satisfies both.

- [x] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/pixelart.py core/sprite/__init__.py tests/sprite/test_pipeline_pixel.py && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): pixel stage runner with shared palette and dither"
```

---

### Task 8: Full suite and plan truth-up

**Files:**
- Modify: `Plans/2026-08-29-sprite-pixel-art-plan.md` (this file: tick the boxes; append deviations)

- [x] **Step 1: Run the whole suite**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest -q
```

Expected: everything green (the pre-feature baseline was 1057 tests; add sub-projects 1, 3, and this plan's 58).

- [x] **Step 2: Run the path guard on its own**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py -v
```

Expected: passes. `core/sprite/pixelart.py` writes no path; `run_pixel_stage` writes only under the `out_dir` it receives.

- [x] **Step 3: Confirm the import stays fast**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -c "import time; t = time.time(); import core.sprite.pixelart, core.sprite.pipeline; print('%.2fs' % (time.time() - t))"
```

Expected: a few seconds at most (sub-project 1's `core/sprite/__init__.py` pulls `core.video.ffmpeg_utils`, about 6 s on this machine; that cost is theirs). If the number is 20 s or more, something imported `core.upscaling` at module level; fix it.

- [x] **Step 4: Update this plan**

Tick every completed checkbox. Under "Deviations from the design", record anything the implementer changed while wiring Task 7 (stage callable shape, skip rule, fingerprint input). Commit:

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add Plans/2026-08-29-sprite-pixel-art-plan.md && git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "docs(plans): pixel-art profile plan truth-up"
```

---

## Self-review

- **Spec coverage (design §4.4):** `integer_fit_scale`, `fit_pad_integer`, `resolution_check`, `build_shared_palette`, `quantize_to_palette`, `bayer_matrix` — all present with the design's signatures (Tasks 1–5). Palette lock / Remap / explicit rebuild — Task 6. `SheetMeta.palette` — Task 7. `OutputProfile` fields `cell_size`, `binary_alpha`, `alpha_threshold`, `defringe_px`, `palette_size`, `dither`, `palette_lock`, `locked_palette`, plus sub-project 1's `upscale_small` / `upscale_method`, are all consumed in Task 7; this plan adds no field.
- **Feature list (design §3 row 4):** fit-pad-integer-downscale (+ source-resolution check) — Tasks 1–2; shared-palette-quantization (+ lock/remap) — Tasks 4–6; dither-selector — Task 5 (`none | bayer2 | bayer4 | bayer8 | floyd`, with `FLOYD_WARNING` for the GUI).
- **Risk table (design §6) "Pillow RGBA quantize trap":** `test_pillow_mediancut_raises_on_rgba_but_our_path_does_not` pins it.
- **Hard rules:** never crop or distort (box filter by an integer factor, proportional upscale target, transparent padding); no silent upscale (warning + opt-in keyword); no hand-built paths; every warning is logged **and** surfaced through `progress`.
- **Verification:** every code block in this plan was executed on 2026-08-29 (Pillow 11.3.0, numpy 2.2.6, Python 3.12.3) with `-W error::DeprecationWarning` on, so no deprecated Pillow call remains. Tasks 1–6 ran against a `keying` stub with the sub-project 3 plan's `hex_to_rgb`/`binary_alpha` bodies. Task 7 ran against sub-project 1's current draft (its real `register_stage` registry, `identity_runner` for `pixel` at version 1, lazy ffmpeg import) with the two `OutputProfile` fields added the way sub-project 1 will add them and steps 3a–3b applied exactly as written, plus that draft's own sprite test suite: 58 tests from this plan green and the draft's own tests green with no edit (their registration test asserts only that every stage has a callable runner). `import core.sprite.pixelart` measured 0.85 s.
- **Placeholder scan:** no `TODO`, no `...`, no undefined symbol. Every test imports only names this plan or the design defines.
- **Ordering:** each task's tests depend only on earlier tasks; Task 7 is the only task that touches a sub-project 1 file (one import line in `core/sprite/__init__.py`), and it never edits `pipeline.py`, `project.py`, or a sub-project 1 test.

## Deviations from the design

1. **`OutputProfile.upscale_small: bool = False` and `OutputProfile.upscale_method: str = "lanczos"`** — two fields the design does not list, decided by the orchestrator on 2026-08-29 and **owned by sub-project 1** (field, `to_dict`, `from_dict`). This plan only reads them. The design leaves the upscale as a caller choice and forbids a silent upscale; the fields are that choice, persisted with the project and part of the pixel stage fingerprint through `pixel_stage_settings`. `run_pipeline` keeps its design signature.
2. **Stage hook** — the design's §4.1 said "`pixel` is identity until sub-project 4"; the registry contract (`StageRunner`, `STAGE_RUNNERS`, `STAGE_SETTINGS`, `register_stage`) is how this plan replaces it. `run_pixel_stage` and `pixel_stage_settings` live in `core/sprite/pixelart.py`; the `register_stage("pixel", ..., code_version=2)` call is module-level in that file, and `core/sprite/__init__.py` imports `pixelart` after `.pipeline` so the registration always runs. Version 2 because sub-project 1 registers `identity_runner` for `pixel` at version 1; the same version with the same settings would reuse a stale identity output.
3. **`fit_pad_integer(..., *, scale: Optional[int] = None)`** — one extra keyword on the design signature. The stage computes one factor for the whole action and forces it on every frame, because per-frame factors would jitter the animation.
4. **`upscale_then_fit(image, cell, anchor, *, method="lanczos")`** and **`anchor_offset`, `nearest_palette_indices`, `palette_spread`, `hex_to_palette`, `palette_to_hex`, `remap_to_locked`, `rebuild_palette`, `ensure_palette`** — public helpers the design implies but does not list. If sub-project 1's `stabilize.py` already exposes an anchor-offset helper with the same semantics, reuse it and delete `anchor_offset` here. The stage looks the profile up through sub-project 1's `SpriteProject.profile("pixel")`; no duplicate lookup helper.
5. **`stages/<action_id>/pixel/pixel.json` manifest** — not in the design. It records scale, palette, dither, `upscale_small`, `upscale_method`, and warnings so the GUI can show the resolution warning after a cached run.
6. **Palette build input** — the design says "MEDIANCUT on flattened RGB of the union"; this plan restricts the union to pixels with alpha ≥ 128 (`PALETTE_ALPHA_MIN`) and sub-samples above 1 000 000 pixels with a deterministic stride. Both keep fringe blends and runtime under control.
7. **Palette order** — sorted dark to light and deduplicated, not MEDIANCUT's internal order. Deterministic and readable in the Aseprite palette chunk.
8. **`core.upscaling` is imported lazily** inside `upscale_then_fit` (measured 23.5 s module import via torchvision on this machine). `UPSCALE_METHODS` mirrors `UpscalingMethod` as string literals for the same reason.
9. **`rebuild_palette` stamps `project.modified`** so a palette change marks the project dirty even when no other field changed. `SpriteProject.save()` may overwrite the stamp; that is fine.
10. **Binary alpha through `keying.apply_profile_alpha`** — the stage does not call `binary_alpha` directly. `apply_profile_alpha(image, profile)` honors `binary_alpha`, `alpha_threshold`, and `defringe_px` and returns alpha in {0, 255}; the stage then zeroes the RGB of fully transparent pixels so PNGs stay clean.
11. **`SheetMeta.palette` is sub-project 1's code**: `sheet_meta` passes `list(prof.locked_palette) if prof.locked_palette and prof.palette_size else None`, so a profile with quantization turned off never advertises a stale palette. `ensure_palette` fills `locked_palette`; no code in this plan touches `project.py`.
12. **`run_pixel_stage` cancellation checks** — the Task 7 review flagged the three inline `if token is not None: token.raise_if_cancelled()` blocks as duplicating logic the pipeline module already centralizes. Task 8 replaced all three with `core.sprite.pipeline.check(token)` (imported alongside `_reset_dir`); same semantics, one fewer pattern to keep in sync. Covered by the existing cancel test in `tests/sprite/test_pipeline_pixel.py`, which stayed green with no edit.
