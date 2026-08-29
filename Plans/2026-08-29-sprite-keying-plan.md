# Sprite Keying & Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `Plans/2026-08-29-sprite-tab-design.md` — §1.7 (dependencies), §2 (data model: `KeySettings`, `StabilizeSettings`, `OutputProfile`, `FrameMeta.overrides`), §4.3 (keying & cleanup signatures). Read the spec before any task.

**Goal:** Turn the identity `key`, `cleanup`, and `alpha` stages of the sprite pipeline into a real chroma keyer with despill, edge cleanup, binary-alpha support, optional ML background removal, per-frame overrides, and frame de-jitter.

**Architecture:** Two pure-Python modules hold the math: `core/sprite/keying.py` (numpy/OpenCV chroma keying, despill, decontamination, morphology, per-frame settings) and `core/sprite/matting.py` (ML backends behind lazy imports, difference matte). `core/sprite/stabilize.py` gains `dejitter`. `core/sprite/pipeline.py` (sub-project 1) gets its three identity runners replaced and its `stabilize` runner extended. Every long step honors the `ProgressFn` / `CancelToken` contract from §1.1. The GUI (5b) and the CLI (7) call `key_frame`, `ffmpeg_chromakey_preview`, `pick_key_color`, `available_backends`, and `sprite_ml_packages`.

**Tech Stack:** Python 3.12 venv (`.venv_linux`), numpy, OpenCV (`cv2`), Pillow, scikit-image + scipy (new hard deps), ffmpeg via `core/video/ffmpeg_utils.py`, mediapipe + rembg (optional extras), pytest.

**Sub-project:** 3 of 8 — depends on 1 (core spine); independent of 2 (video route); consumed by 4 (pixel profile), 5b (processing panel, install dialog), 7 (CLI).

## Global Constraints

- Never `cd`. Use absolute paths. Git: `git -C /mnt/d/Documents/Code/GitHub/ImageAI …`.
- Python: `PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python`. Tests: `$PY -m pytest <abs path> -v`, run with the shell's working directory at the repo root (the Bash tool default). `python -m` puts the working directory on `sys.path`; the guard test `tests/test_no_hardcoded_paths.py` and the `from tests.sprite…` helper imports both need that.
- Branch: `feat/sprite-tab`. Commit per task with Conventional Commits. No version bump and no changelog entry in this sub-project (sub-project 7 owns the release).
- `core/paths.py` owns every path. The rembg model directory is `get_data_paths().model_cache("rembg")`. `CACHE_OWNERS[Group.MODELS]` in `core/data_migration.py` must gain `"rembg"`; the pin test `tests/migration/test_data_migration.py::test_cache_owners_covers_every_model_cache_and_video_cache_call_site` fails otherwise.
- New hard deps: `scikit-image` and `scipy` in `requirements.txt`, with a `cv2.phaseCorrelate` fallback when the `skimage` import fails. Optional extras go in `requirements-sprite-ml.txt` (`mediapipe`, `rembg[cpu]`; rembg needs Python >=3.11,<3.14).
- **Package age rule:** before any `pip install`, check the release date of the version pip resolves. Never install a version published fewer than 7 days ago. Task 8 and Task 10 carry the exact check command.
- Never make `libimagequant`, `imagequant`, `CorridorKey`, or `bria-rmbg` a dependency. `REMBG_MODELS["bria-rmbg"]["default_ok"]` is `False`.
- Never install system packages. Runtime package installs go through `core/package_installer.py` `PackageInstaller(packages, update_requirements=False, index_url=None)`; this sub-project only supplies the package list (`sprite_ml_packages()`), the dialog is sub-project 5b.
- Every user-facing error is logged with `logger.error(...)` at the raise site. Errors carry a `user_message` attribute.
- Images are never cropped or distorted by this sub-project; `dejitter` translates, and `apply_profile_alpha` only changes alpha.
- Tests use numpy-synthesized images only; no binary fixtures.
- Prose in code comments and docstrings: Simplified Technical English style (short, active, one idea per sentence).

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `core/sprite/keying.py` | Create | Chroma keyer math, despill, decontamination, choke/feather/despeckle, binary alpha, `KeySettings` resolution + per-frame overrides, `key_frame`, ffmpeg preview, key-color picker |
| `core/sprite/matting.py` | Create | `available_backends`, `ml_alpha` (mediapipe / rembg), `REMBG_MODELS`, `rembg_model_dir`, `difference_matte` |
| `core/sprite/ml_install.py` | Create | `sprite_ml_packages`, `python_supports_rembg`, requirements-file parser for the 5b install dialog |
| `core/sprite/stabilize.py` | Modify (sub-project 1 file) | Add `dejitter`, `estimate_shift`, `translate_rgba`, `alpha_centroid` |
| `core/sprite/pipeline.py` | Modify (sub-project 1 file) | Replace `key`/`cleanup`/`alpha` runners; add de-jitter to `stabilize`; `apply_profile_alpha` in `hd`; stage settings for fingerprints; bump `STAGE_CODE_VERSION` |
| `core/data_migration.py` | Modify `:50-54` | `CACHE_OWNERS[Group.MODELS]` gains `"rembg"` |
| `requirements.txt` | Modify (after `:37`) | `scikit-image`, `scipy` hard deps |
| `requirements-sprite-ml.txt` | Create | Optional ML extras |
| `tests/sprite/keying_fixtures.py` | Create | Synthetic disc-on-field images, RGBA helpers, centroid |
| `tests/sprite/test_keying_alpha.py` | Create | Task 1 |
| `tests/sprite/test_keying_despill.py` | Create | Task 2 |
| `tests/sprite/test_keying_cleanup.py` | Create | Task 3 |
| `tests/sprite/test_key_frame.py` | Create | Task 4 |
| `tests/sprite/test_keying_ffmpeg.py` | Create | Task 5 |
| `tests/sprite/test_matting.py` | Create | Task 6 |
| `tests/migration/test_data_migration.py` | Modify (append after `:736`) | Task 6 pin |
| `tests/sprite/test_matting_difference.py` | Create | Task 7 |
| `tests/sprite/test_dejitter.py` | Create | Task 8 |
| `tests/sprite/test_pipeline_keying.py` | Create | Task 9 |
| `tests/sprite/test_ml_install.py` | Create | Task 10 |

Stage file contract (all tasks): every stage reads `NNNN.png` files from the previous stage and writes RGBA `NNNN.png` files with the **same basenames** into its own directory. `key` writes despilled RGB + raw soft alpha. `cleanup` changes alpha only. `alpha` decontaminates edge colors against the key color and writes the final RGBA. Binarization happens only in the profile stages (`hd` when `OutputProfile.binary_alpha`, `pixel` always — sub-project 4).

Pipeline hook contract (accepted by the team lead on 2026-08-29 as the canonical hook; sub-project 1 ships it):

```python
# core/sprite/pipeline.py
StageRunner = Callable[[SpriteProject, ActionCard, List[Path], Path, ProgressFn, Optional[CancelToken]], List[Path]]
STAGE_RUNNERS: Dict[str, StageRunner]                   # (project, action, input_frames, out_dir, progress, token) -> outputs
STAGE_SETTINGS: Dict[str, Callable[[SpriteProject, ActionCard], Dict[str, Any]]]   # hashed by stage_fingerprint
STAGE_CODE_VERSION: Dict[str, int]
def register_stage(stage: str, runner: StageRunner, settings_fn=None, code_version: int = 1) -> None
```

---

### Task 1: Synthetic fixtures, `hex_to_rgb`, `chroma_alpha`

**Files:**
- Create: `core/sprite/keying.py`
- Create: `tests/sprite/keying_fixtures.py`
- Create: `tests/sprite/test_keying_alpha.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces:
  - `keying.hex_to_rgb(hex_color: str) -> Tuple[int, int, int]` — accepts `#RRGGBB`, `RRGGBB`, `#RGB`; raises `ValueError`.
  - `keying.rgb_to_hex(rgb: Sequence[int]) -> str` — `"#RRGGBB"` upper case.
  - `keying.chroma_alpha(rgb: np.ndarray, key_rgb: Tuple[int, int, int], tolerance: float, softness: float) -> np.ndarray` — float32 HxW in 0..1; 0 = keyed out.
  - `keying.KeyingError(RuntimeError)` with `.user_message`.
  - Fixture helpers `disc_on_field`, `disc_rgba`, `centroid`, `write_png` in `tests/sprite/keying_fixtures.py`.

The keyer works in the (Cb, Cr) plane of BT.601 YCbCr. A constant added to all three RGB channels leaves (Cb, Cr) unchanged, so a luminance gradient on the plate keys the same as a flat plate. The test builds that gradient on purpose.

- [ ] **Step 1: Write the fixture helpers**

```python
# tests/sprite/keying_fixtures.py
"""Synthetic images for the sprite keying tests. No binary fixtures."""
from pathlib import Path
from typing import Optional, Sequence, Tuple

import numpy as np
from PIL import Image

FIELD = (0, 200, 0)      # plate green
DISC = (220, 40, 40)     # subject red


def disc_on_field(width: int = 64, height: int = 48, center: Tuple[float, float] = (32.0, 24.0),
                  radius: float = 12.0, disc: Sequence[int] = DISC, field: Sequence[int] = FIELD,
                  gradient: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    """Return (rgb uint8 HxWx3, coverage float32 HxW).

    The disc has an anti-aliased edge (coverage ramps over one pixel). With
    ``gradient`` the field gains +0..55 on every channel from left to right,
    which changes luminance only and keeps (Cb, Cr) constant.
    """
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    dist = np.sqrt((xx - center[0]) ** 2 + (yy - center[1]) ** 2)
    cov = np.clip(radius + 0.5 - dist, 0.0, 1.0).astype(np.float32)
    base = np.empty((height, width, 3), dtype=np.float32)
    base[:] = np.array(field, dtype=np.float32)
    if gradient:
        base = base + np.linspace(0, 55, width, dtype=np.float32)[None, :, None]
    disc_c = np.array(disc, dtype=np.float32)
    rgb = cov[:, :, None] * disc_c + (1.0 - cov[:, :, None]) * base
    return np.clip(np.round(rgb), 0, 255).astype(np.uint8), cov


def disc_rgba(width: int = 64, height: int = 48, center: Tuple[float, float] = (32.0, 24.0),
              radius: float = 10.0, color: Sequence[int] = DISC) -> np.ndarray:
    """Return an RGBA uint8 HxWx4 array: a solid-colour disc with soft alpha on transparent."""
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    dist = np.sqrt((xx - center[0]) ** 2 + (yy - center[1]) ** 2)
    cov = np.clip(radius + 0.5 - dist, 0.0, 1.0)
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[:, :, 0], rgba[:, :, 1], rgba[:, :, 2] = color
    rgba[:, :, 3] = np.round(cov * 255).astype(np.uint8)
    return rgba


def centroid(alpha: np.ndarray) -> Optional[Tuple[float, float]]:
    """Alpha-weighted centroid (y, x) of a float mask, or None when the mask is empty."""
    a = np.asarray(alpha, dtype=np.float32)
    total = float(a.sum())
    if total <= 0.0:
        return None
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]].astype(np.float32)
    return float((yy * a).sum() / total), float((xx * a).sum() / total)


def write_png(path: Path, array: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.ascontiguousarray(array)).save(path)
    return path
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/sprite/test_keying_alpha.py
import numpy as np
import pytest

from core.sprite import keying
from tests.sprite.keying_fixtures import FIELD, disc_on_field


def test_hex_to_rgb_accepts_common_forms():
    assert keying.hex_to_rgb("#00FF00") == (0, 255, 0)
    assert keying.hex_to_rgb("00ff00") == (0, 255, 0)
    assert keying.hex_to_rgb("#0f0") == (0, 255, 0)
    assert keying.rgb_to_hex((0, 200, 0)) == "#00C800"


@pytest.mark.parametrize("bad", ["", "#12345", "#GGGGGG", "green"])
def test_hex_to_rgb_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        keying.hex_to_rgb(bad)


def test_field_with_luminance_gradient_keys_to_zero():
    rgb, cov = disc_on_field(gradient=True)
    alpha = keying.chroma_alpha(rgb, FIELD, tolerance=0.20, softness=0.10)
    assert alpha.dtype == np.float32
    assert alpha.shape == rgb.shape[:2]
    assert alpha[cov == 0].max() == 0.0


def test_disc_interior_is_fully_opaque():
    rgb, cov = disc_on_field()
    alpha = keying.chroma_alpha(rgb, FIELD, tolerance=0.20, softness=0.10)
    assert alpha[cov == 1].min() == 1.0


def test_wide_ramp_yields_partial_alpha_on_the_edge():
    rgb, cov = disc_on_field()
    alpha = keying.chroma_alpha(rgb, FIELD, tolerance=0.05, softness=0.80)
    edge = alpha[(cov > 0) & (cov < 1)]
    assert ((edge > 0.05) & (edge < 0.95)).any()


def test_ramp_midpoint_is_half():
    # The (Cb, Cr) distance from (220,40,40) to (0,200,0) is 0.6957 (normalized by 255).
    red = np.array([[[220, 40, 40]]], dtype=np.uint8)
    alpha = keying.chroma_alpha(red, FIELD, tolerance=0.6957 - 0.05, softness=0.10)
    assert abs(float(alpha[0, 0]) - 0.5) < 0.02


def test_brightness_offset_does_not_change_alpha():
    lifted = np.array([[[50, 250, 50]]], dtype=np.uint8)   # FIELD + 50 on every channel
    assert keying.chroma_alpha(lifted, FIELD, 0.01, 0.0)[0, 0] == 0.0
    assert keying.chroma_alpha(lifted, FIELD, 0.01, 0.05)[0, 0] == 0.0


def test_zero_softness_is_a_hard_step():
    rgb, _ = disc_on_field()
    alpha = keying.chroma_alpha(rgb, FIELD, tolerance=0.20, softness=0.0)
    assert set(np.unique(alpha).tolist()) <= {0.0, 1.0}


def test_rgba_input_ignores_the_alpha_channel():
    rgb, cov = disc_on_field()
    rgba = np.concatenate([rgb, np.full(rgb.shape[:2] + (1,), 255, np.uint8)], axis=2)
    a1 = keying.chroma_alpha(rgb, FIELD, 0.2, 0.1)
    a2 = keying.chroma_alpha(rgba, FIELD, 0.2, 0.1)
    assert (a1 == a2).all()


def test_chroma_alpha_rejects_non_image_arrays():
    with pytest.raises(ValueError):
        keying.chroma_alpha(np.zeros((4, 4), np.uint8), FIELD, 0.2, 0.1)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_keying_alpha.py -v`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'core.sprite.keying'`.

- [ ] **Step 4: Create `core/sprite/keying.py` with the header, errors, and the alpha math**

```python
# core/sprite/keying.py
"""Chroma keying, despill, and alpha cleanup for sprite frames.

Pure numpy / OpenCV / Pillow. No Qt. Every function is stateless. Arrays:
``rgb`` is uint8 HxWx3 (an HxWx4 input is accepted and its alpha ignored),
``alpha`` is float32 HxW in 0..1 where 0 means keyed out.

Design: Plans/2026-08-29-sprite-tab-design.md §4.3.
"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image

from core.sprite.models import FrameMeta
from core.sprite.project import KeySettings, OutputProfile
from core.video.ffmpeg_utils import get_ffmpeg_path

logger = logging.getLogger(__name__)

KEY_METHODS = ("chroma", "ml", "none")
DESPILL_MODES = ("none", "average", "double", "limit")
OVERRIDE_KEYS = ("key_color", "tolerance", "softness")

# BT.601 full-range chroma and luma weights. A constant offset on all three
# RGB channels changes Y only; Cb and Cr stay the same.
_CB = np.array([-0.168736, -0.331264, 0.5], dtype=np.float32)
_CR = np.array([0.5, -0.418688, -0.081312], dtype=np.float32)
_Y = np.array([0.299, 0.587, 0.114], dtype=np.float32)


class KeyingError(RuntimeError):
    """A keying step failed. ``user_message`` is safe to show in the UI or CLI."""

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


# --- colors ------------------------------------------------------------------

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Parse ``#RRGGBB``, ``RRGGBB``, or ``#RGB``. Raise ValueError otherwise."""
    text = str(hex_color).strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in text):
        raise ValueError(f"Not a #RRGGBB color: {hex_color!r}")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def rgb_to_hex(rgb: Sequence[int]) -> str:
    r, g, b = (max(0, min(255, int(round(v)))) for v in rgb[:3])
    return f"#{r:02X}{g:02X}{b:02X}"


# --- array helpers -----------------------------------------------------------

def _as_float_rgb(rgb: np.ndarray) -> np.ndarray:
    arr = np.asarray(rgb)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise ValueError(f"Expected an HxWx3 RGB array, got shape {arr.shape}")
    return arr[:, :, :3].astype(np.float32)


def _chroma(rgb_f: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Return (Cb, Cr) arrays for a float RGB array (any leading shape)."""
    return rgb_f @ _CB, rgb_f @ _CR


# --- keyer -------------------------------------------------------------------

def chroma_alpha(rgb: np.ndarray, key_rgb: Tuple[int, int, int],
                 tolerance: float, softness: float) -> np.ndarray:
    """Soft alpha from the (Cb, Cr) distance to the key color.

    Distance is Euclidean in the Cb/Cr plane, normalized by 255 (0..~0.71).
    Pixels closer than ``tolerance`` get alpha 0. Alpha ramps linearly to 1
    over ``softness``. ``softness == 0`` gives a hard step.
    """
    rgb_f = _as_float_rgb(rgb)
    cb, cr = _chroma(rgb_f)
    key = np.array(key_rgb, dtype=np.float32).reshape(1, 1, 3)
    kcb, kcr = _chroma(key)
    dist = np.sqrt((cb - kcb) ** 2 + (cr - kcr) ** 2) / 255.0
    tol = max(0.0, float(tolerance))
    soft = max(0.0, float(softness))
    if soft <= 0.0:
        return (dist > tol).astype(np.float32)
    return np.clip((dist - tol) / soft, 0.0, 1.0).astype(np.float32)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_keying_alpha.py -v`
Expected: 13 passed. (If `core.sprite.models` or `core.sprite.project` import fails, sub-project 1 is not on this branch — stop and report.)

- [ ] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/keying.py tests/sprite/keying_fixtures.py tests/sprite/test_keying_alpha.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): chroma keyer alpha from (Cb,Cr) distance"
```

---

### Task 2: `despill` and `decontaminate_edges`

**Files:**
- Modify: `core/sprite/keying.py` (append after `chroma_alpha`)
- Create: `tests/sprite/test_keying_despill.py`

**Interfaces:**
- Consumes: `_as_float_rgb`, `_Y`, `DESPILL_MODES` (Task 1).
- Produces:
  - `keying.despill(rgb: np.ndarray, key_rgb: Tuple[int, int, int], mode: str) -> np.ndarray` — uint8 HxWx3; modes `none | average | double | limit`; luminance restored.
  - `keying.decontaminate_edges(rgb: np.ndarray, alpha: np.ndarray, key_rgb: Tuple[int, int, int]) -> np.ndarray` — uint8 HxWx3; F = (C − (1−α)K) / α on 0 < α < 1, clamped.

Despill limits the key's dominant channel (`argmax(key_rgb)`) against the other two: `average` → (a+b)/2, `double` → (2·max(a,b)+min(a,b))/3, `limit` → max(a,b). The luminance the clamp removed is added back as a neutral offset on all channels, which keeps (Cb, Cr) of the result stable.

- [ ] **Step 1: Write the failing tests**

```python
# tests/sprite/test_keying_despill.py
import numpy as np
import pytest

from core.sprite import keying

Y = np.array([0.299, 0.587, 0.114], dtype=np.float32)
KEY = (0, 255, 0)
SPILLED = np.array([[[120, 200, 110]]], dtype=np.uint8)   # green spill on a grey-ish pixel
RED = np.array([[[220, 40, 40]]], dtype=np.uint8)


@pytest.mark.parametrize("mode", ["average", "double", "limit"])
def test_despill_removes_the_green_excess(mode):
    out = keying.despill(SPILLED, KEY, mode)
    assert out.dtype == np.uint8
    r, g, b = (int(v) for v in out[0, 0])
    assert g <= max(r, b) + 1


@pytest.mark.parametrize("mode", ["average", "double", "limit"])
def test_despill_restores_luminance(mode):
    y_before = float(SPILLED[0, 0].astype(np.float32) @ Y)
    out = keying.despill(SPILLED, KEY, mode)
    y_after = float(out[0, 0].astype(np.float32) @ Y)
    assert abs(y_before - y_after) < 1.5


def test_despill_leaves_unspilled_pixels_alone():
    assert (keying.despill(RED, KEY, "average") == RED).all()
    assert (keying.despill(SPILLED, KEY, "none") == SPILLED).all()


def test_despill_rejects_unknown_mode():
    with pytest.raises(ValueError):
        keying.despill(SPILLED, KEY, "bogus")


def test_despill_limit_is_stronger_than_average():
    avg = int(keying.despill(SPILLED, KEY, "average")[0, 0, 1])
    lim = int(keying.despill(SPILLED, KEY, "limit")[0, 0, 1])
    assert lim >= avg


def test_decontaminate_recovers_the_foreground_colour():
    fg = np.array([220, 40, 40], dtype=np.float32)
    key = np.array([0, 200, 0], dtype=np.float32)
    a = 0.4
    mixed = np.round(a * fg + (1 - a) * key).astype(np.uint8).reshape(1, 1, 3)
    alpha = np.array([[a]], dtype=np.float32)
    out = keying.decontaminate_edges(mixed, alpha, (0, 200, 0))
    assert out.dtype == np.uint8
    assert np.abs(out[0, 0].astype(np.float32) - fg).max() <= 3


def test_decontaminate_leaves_opaque_and_transparent_pixels_alone():
    mixed = np.array([[[88, 136, 16]]], dtype=np.uint8)
    for a in (0.0, 1.0):
        alpha = np.array([[a]], dtype=np.float32)
        assert (keying.decontaminate_edges(mixed, alpha, (0, 200, 0)) == mixed).all()


def test_decontaminate_clamps_to_uint8_range():
    dark = np.array([[[0, 0, 0]]], dtype=np.uint8)
    alpha = np.array([[0.1]], dtype=np.float32)
    out = keying.decontaminate_edges(dark, alpha, (0, 255, 0))
    assert out.min() >= 0 and out.max() <= 255
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_keying_despill.py -v`
Expected: FAIL with `AttributeError: module 'core.sprite.keying' has no attribute 'despill'`.

- [ ] **Step 3: Append the implementation to `core/sprite/keying.py`**

```python
# --- despill and edge decontamination ------------------------------------------

def despill(rgb: np.ndarray, key_rgb: Tuple[int, int, int], mode: str) -> np.ndarray:
    """Limit the key's dominant channel and restore the luminance the clamp removed.

    mode: none | average | double | limit (weakest to strongest).
    """
    if mode not in DESPILL_MODES:
        raise ValueError(f"Unknown despill mode {mode!r}; choose one of {DESPILL_MODES}")
    src = _as_float_rgb(rgb)
    if mode == "none":
        return np.clip(src, 0, 255).astype(np.uint8)
    k = int(np.argmax(np.asarray(key_rgb, dtype=np.float32)))
    others = [c for c in range(3) if c != k]
    a = src[:, :, others[0]]
    b = src[:, :, others[1]]
    if mode == "average":
        limit = (a + b) / 2.0
    elif mode == "double":
        limit = (2.0 * np.maximum(a, b) + np.minimum(a, b)) / 3.0
    else:  # limit
        limit = np.maximum(a, b)
    out = src.copy()
    y_before = src @ _Y
    out[:, :, k] = np.minimum(src[:, :, k], limit)
    y_after = out @ _Y
    out += (y_before - y_after)[:, :, None]
    return np.clip(out, 0, 255).astype(np.uint8)


def decontaminate_edges(rgb: np.ndarray, alpha: np.ndarray,
                        key_rgb: Tuple[int, int, int]) -> np.ndarray:
    """Un-mix the key color from semi-transparent pixels: F = (C - (1-a)K) / a.

    Pixels with alpha 0 or 1 are returned unchanged. The result is clamped to 0..255.
    """
    src = _as_float_rgb(rgb)
    a = np.asarray(alpha, dtype=np.float32)
    if a.shape != src.shape[:2]:
        raise ValueError(f"alpha shape {a.shape} does not match image {src.shape[:2]}")
    key = np.array(key_rgb, dtype=np.float32).reshape(1, 1, 3)
    a3 = a[:, :, None]
    fixed = (src - (1.0 - a3) * key) / np.maximum(a3, 1.0 / 255.0)
    edge = (a > (1.0 / 255.0)) & (a < 1.0)
    out = src.copy()
    out[edge] = fixed[edge]
    return np.clip(out, 0, 255).astype(np.uint8)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_keying_despill.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_keying_alpha.py -v`
Expected: 25 passed (12 + 13).

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/keying.py tests/sprite/test_keying_despill.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): despill and edge decontamination"
```

---

### Task 3: `choke_feather`, `binary_alpha`, `apply_profile_alpha`

**Files:**
- Modify: `core/sprite/keying.py` (append)
- Create: `tests/sprite/test_keying_cleanup.py`

**Interfaces:**
- Consumes: `OutputProfile` (design §2: `binary_alpha: bool`, `alpha_threshold: int = 128`, `defringe_px: int = 0`).
- Produces:
  - `keying.choke_feather(alpha, choke_px: int, feather_px: int, despeckle_px: int) -> np.ndarray` — float32; order despeckle (morphological open) → choke (erode; negative = dilate) → feather (Gaussian, sigma = px).
  - `keying.binary_alpha(alpha, threshold: int = 128, defringe_px: int = 0) -> np.ndarray` — float32 with values in {0, 1}; `alpha*255 >= threshold`; `defringe_px` erodes the hard mask.
  - `keying.compose_rgba(rgb: np.ndarray, alpha: np.ndarray) -> Image.Image` and `keying.split_rgba(image: Image.Image) -> Tuple[np.ndarray, np.ndarray]` (rgb uint8, alpha float32).
  - `keying.apply_profile_alpha(image: Image.Image, profile: OutputProfile) -> Image.Image` — binarizes only when `profile.binary_alpha`; the HD soft-alpha guarantee lives here.

- [ ] **Step 1: Write the failing tests**

```python
# tests/sprite/test_keying_cleanup.py
import numpy as np
from PIL import Image

from core.sprite import keying
from core.sprite.project import OutputProfile
from tests.sprite.keying_fixtures import disc_rgba


def _square_with_speck():
    a = np.zeros((32, 32), dtype=np.float32)
    a[8:24, 8:24] = 1.0
    a[2, 2] = 1.0
    return a


def test_choke_erodes_the_mask():
    a = _square_with_speck()
    out = keying.choke_feather(a, choke_px=2, feather_px=0, despeckle_px=0)
    assert out.dtype == np.float32
    assert out.sum() < a.sum()
    assert out[16, 16] == 1.0 and out[8, 8] == 0.0


def test_negative_choke_spreads_the_mask():
    a = _square_with_speck()
    out = keying.choke_feather(a, choke_px=-2, feather_px=0, despeckle_px=0)
    assert out.sum() > a.sum()


def test_feather_softens_the_edge():
    a = _square_with_speck()
    out = keying.choke_feather(a, choke_px=0, feather_px=2, despeckle_px=0)
    assert out.max() <= 1.0 and out.min() >= 0.0
    assert ((out > 0.05) & (out < 0.95)).any()


def test_despeckle_removes_islands_smaller_than_the_kernel():
    a = _square_with_speck()
    out = keying.choke_feather(a, choke_px=0, feather_px=0, despeckle_px=1)
    assert out[2, 2] == 0.0 and out[16, 16] == 1.0


def test_zero_settings_return_the_input_values():
    a = _square_with_speck()
    out = keying.choke_feather(a, 0, 0, 0)
    assert (out == a).all()


def test_binary_alpha_thresholds_on_255_scale():
    a = np.array([[0.0, 0.4, 0.5, 0.6, 1.0]], dtype=np.float32)
    out = keying.binary_alpha(a, threshold=128)
    assert out.dtype == np.float32
    assert out.tolist() == [[0.0, 0.0, 0.0, 1.0, 1.0]]     # 0.5*255 = 127.5 < 128
    assert keying.binary_alpha(a, threshold=100).tolist() == [[0.0, 1.0, 1.0, 1.0, 1.0]]


def test_binary_alpha_accepts_uint8():
    a = np.array([[0, 100, 128, 255]], dtype=np.uint8)
    assert keying.binary_alpha(a, 128).tolist() == [[0.0, 0.0, 1.0, 1.0]]


def test_binary_alpha_defringe_erodes():
    a = np.zeros((16, 16), dtype=np.float32)
    a[4:12, 4:12] = 1.0
    out = keying.binary_alpha(a, 128, defringe_px=1)
    assert out.sum() < a.sum() and out[8, 8] == 1.0
    assert set(np.unique(out).tolist()) <= {0.0, 1.0}


def test_compose_and_split_round_trip():
    rgba = disc_rgba()
    rgb, alpha = keying.split_rgba(Image.fromarray(rgba))
    assert rgb.dtype == np.uint8 and alpha.dtype == np.float32
    back = np.asarray(keying.compose_rgba(rgb, alpha))
    assert (back == rgba).all()


def test_split_rgba_of_an_rgb_image_is_opaque():
    img = Image.new("RGB", (4, 3), (10, 20, 30))
    _rgb, alpha = keying.split_rgba(img)
    assert (alpha == 1.0).all()


def test_hd_profile_keeps_soft_alpha_by_default():
    img = Image.fromarray(disc_rgba())
    hd = OutputProfile(name="hd")
    out = np.asarray(keying.apply_profile_alpha(img, hd))
    values = set(np.unique(out[:, :, 3]).tolist())
    assert values - {0, 255}, "soft edge values must survive"
    assert (out == np.asarray(img)).all()


def test_profile_binary_alpha_binarizes_and_keeps_colour():
    img = Image.fromarray(disc_rgba())
    prof = OutputProfile(name="hd", binary_alpha=True, alpha_threshold=128, defringe_px=0)
    out = np.asarray(keying.apply_profile_alpha(img, prof))
    assert set(np.unique(out[:, :, 3]).tolist()) <= {0, 255}
    assert tuple(out[24, 32, :3]) == (220, 40, 40)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_keying_cleanup.py -v`
Expected: FAIL with `AttributeError: module 'core.sprite.keying' has no attribute 'choke_feather'`.

- [ ] **Step 3: Append the implementation to `core/sprite/keying.py`**

```python
# --- alpha cleanup ---------------------------------------------------------------

def _kernel(px: int) -> np.ndarray:
    size = 2 * int(px) + 1
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))


def choke_feather(alpha: np.ndarray, choke_px: int, feather_px: int,
                  despeckle_px: int) -> np.ndarray:
    """Despeckle (open), then choke (erode; negative spreads), then feather (Gaussian)."""
    a = np.asarray(alpha, dtype=np.float32)
    if despeckle_px > 0:
        a = cv2.morphologyEx(a, cv2.MORPH_OPEN, _kernel(despeckle_px))
    if choke_px > 0:
        a = cv2.erode(a, _kernel(choke_px))
    elif choke_px < 0:
        a = cv2.dilate(a, _kernel(-choke_px))
    if feather_px > 0:
        a = cv2.GaussianBlur(a, (0, 0), sigmaX=float(feather_px))
    return np.clip(a, 0.0, 1.0).astype(np.float32)


def binary_alpha(alpha: np.ndarray, threshold: int = 128, defringe_px: int = 0) -> np.ndarray:
    """Hard 0/1 alpha: ``alpha * 255 >= threshold``. ``defringe_px`` erodes the result."""
    a = np.asarray(alpha)
    a255 = a.astype(np.float32) if a.dtype == np.uint8 else np.asarray(a, dtype=np.float32) * 255.0
    hard = (a255 >= float(threshold)).astype(np.float32)
    if defringe_px > 0:
        hard = cv2.erode(hard, _kernel(defringe_px))
    return hard.astype(np.float32)


# --- RGBA helpers ------------------------------------------------------------------

def compose_rgba(rgb: np.ndarray, alpha: np.ndarray) -> Image.Image:
    """Build an RGBA image from uint8 RGB and float 0..1 alpha."""
    rgb_u8 = np.asarray(rgb)[:, :, :3].astype(np.uint8)
    a_u8 = np.clip(np.round(np.asarray(alpha, dtype=np.float32) * 255.0), 0, 255).astype(np.uint8)
    rgba = np.concatenate([rgb_u8, a_u8[:, :, None]], axis=2)
    return Image.fromarray(np.ascontiguousarray(rgba))


def split_rgba(image: Image.Image) -> Tuple[np.ndarray, np.ndarray]:
    """Return (rgb uint8 HxWx3, alpha float32 HxW). An image without alpha is opaque."""
    rgba = np.asarray(image.convert("RGBA"))
    return rgba[:, :, :3].copy(), rgba[:, :, 3].astype(np.float32) / 255.0


def apply_profile_alpha(image: Image.Image, profile: OutputProfile) -> Image.Image:
    """Binarize alpha only when the profile asks for it. The hd profile keeps soft alpha."""
    if not profile.binary_alpha:
        return image
    rgb, alpha = split_rgba(image)
    hard = binary_alpha(alpha, profile.alpha_threshold, profile.defringe_px)
    return compose_rgba(rgb, hard)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_keying_cleanup.py -v`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/keying.py tests/sprite/test_keying_cleanup.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): alpha choke, feather, despeckle, binary threshold, profile alpha"
```

---

### Task 4: `key_frame`, stage passes, and per-frame overrides

**Files:**
- Modify: `core/sprite/keying.py` (append)
- Create: `tests/sprite/test_key_frame.py`

**Interfaces:**
- Consumes: `KeySettings` (design §2), `FrameMeta.overrides: Dict[str, Any]`, Tasks 1–3.
- Produces:
  - `keying.resolve_key_settings(settings: KeySettings, plate_color: str) -> KeySettings` — `key_color None → plate_color`.
  - `keying.apply_overrides(settings: KeySettings, overrides: Dict[str, Any]) -> KeySettings` — honors `key_color`, `tolerance`, `softness`; ignores other keys with a debug log.
  - `keying.frame_overrides(frames: Sequence[FrameMeta], index: int) -> Dict[str, Any]` — `{}` when out of range.
  - `keying.key_pass(image, settings, overrides) -> Tuple[np.ndarray, np.ndarray, Optional[Tuple[int,int,int]]]` — (despilled rgb uint8, raw alpha float32, key_rgb or None).
  - `keying.cleanup_pass(alpha, settings) -> np.ndarray`.
  - `keying.alpha_pass(rgb, alpha, key_rgb, settings) -> Image.Image` — decontaminates when `settings.edge_decontaminate` and `key_rgb` exists.
  - `keying.key_frame(image: Image.Image, settings: KeySettings, overrides: Dict[str, Any]) -> Image.Image` — RGBA; = `alpha_pass(cleanup_pass(key_pass(...)))`.
  - `keying._ml_alpha(image, backend, model, refine_edges)` — indirection that imports `core.sprite.matting.ml_alpha` lazily (Task 6 creates it); tests patch this name.

- [ ] **Step 1: Write the failing tests**

```python
# tests/sprite/test_key_frame.py
import numpy as np
import pytest
from PIL import Image

from core.sprite import keying
from core.sprite.models import FrameMeta
from core.sprite.project import KeySettings
from tests.sprite.keying_fixtures import disc_on_field, disc_rgba


def _image():
    rgb, cov = disc_on_field()
    return Image.fromarray(rgb), cov


def test_resolve_key_settings_falls_back_to_plate_color():
    s = keying.resolve_key_settings(KeySettings(), "#00C800")
    assert s.key_color == "#00C800"
    s2 = keying.resolve_key_settings(KeySettings(key_color="#FF00FF"), "#00C800")
    assert s2.key_color == "#FF00FF"


def test_apply_overrides_changes_only_known_keys(caplog):
    base = KeySettings(key_color="#00C800", tolerance=0.2, softness=0.1, choke_px=3)
    out = keying.apply_overrides(base, {"tolerance": 0.5, "softness": "0.25", "key_color": "#00FF00",
                                        "choke_px": 9, "mystery": 1})
    assert (out.tolerance, out.softness, out.key_color) == (0.5, 0.25, "#00FF00")
    assert out.choke_px == 3
    assert base.tolerance == 0.2


def test_apply_overrides_ignores_none_values():
    base = KeySettings(key_color="#00C800", tolerance=0.2)
    assert keying.apply_overrides(base, {"tolerance": None}).tolerance == 0.2


def test_frame_overrides_reads_frame_meta():
    frames = [FrameMeta(name="a", source_path=None, frame=(0, 0, 0, 0)),
              FrameMeta(name="b", source_path=None, frame=(0, 0, 0, 0), overrides={"tolerance": 0.9})]
    assert keying.frame_overrides(frames, 0) == {}
    assert keying.frame_overrides(frames, 1) == {"tolerance": 0.9}
    assert keying.frame_overrides(frames, 7) == {}
    assert keying.frame_overrides([], 0) == {}


def test_key_frame_chroma_produces_rgba_with_keyed_field():
    img, cov = _image()
    out = keying.key_frame(img, KeySettings(key_color="#00C800"), {})
    assert out.mode == "RGBA"
    arr = np.asarray(out)
    assert arr[cov == 0][:, 3].max() == 0
    assert arr[cov == 1][:, 3].min() == 255
    assert tuple(arr[24, 32, :3]) == (220, 40, 40)


def test_key_frame_override_tolerance_keys_everything():
    img, cov = _image()
    out = np.asarray(keying.key_frame(img, KeySettings(key_color="#00C800"), {"tolerance": 0.95}))
    assert out[:, :, 3].max() == 0


def test_key_frame_without_key_color_samples_the_corner(caplog):
    img, cov = _image()
    with caplog.at_level("WARNING"):
        out = np.asarray(keying.key_frame(img, KeySettings(), {}))
    assert out[cov == 0][:, 3].max() == 0
    assert "key color" in caplog.text.lower()


def test_key_frame_none_method_keeps_existing_alpha():
    rgba = disc_rgba()
    out = np.asarray(keying.key_frame(Image.fromarray(rgba), KeySettings(method="none"), {}))
    assert (out == rgba).all()


def test_key_frame_none_method_on_rgb_is_opaque():
    img, _ = _image()
    out = np.asarray(keying.key_frame(img, KeySettings(method="none"), {}))
    assert (out[:, :, 3] == 255).all()


def test_key_frame_ml_method_dispatches_to_matting(monkeypatch):
    img, cov = _image()
    calls = []

    def fake_ml(image, backend, model, refine_edges):
        calls.append((backend, model, refine_edges))
        return cov.astype(np.float32)

    monkeypatch.setattr(keying, "_ml_alpha", fake_ml)
    settings = KeySettings(method="ml", ml_backend="rembg", ml_model="u2netp", ml_refine_edges=True)
    out = np.asarray(keying.key_frame(img, settings, {}))
    assert calls == [("rembg", "u2netp", True)]
    assert out[cov == 1][:, 3].min() == 255 and out[cov == 0][:, 3].max() == 0


def test_key_frame_rejects_unknown_method():
    img, _ = _image()
    with pytest.raises(keying.KeyingError):
        keying.key_frame(img, KeySettings(method="magic"), {})


def test_cleanup_and_decontaminate_are_applied():
    img, cov = _image()
    plain = np.asarray(keying.key_frame(img, KeySettings(key_color="#00C800", edge_decontaminate=False), {}))
    choked = np.asarray(keying.key_frame(img, KeySettings(key_color="#00C800", choke_px=2), {}))
    assert choked[:, :, 3].sum() < plain[:, :, 3].sum()
    decon = np.asarray(keying.key_frame(img, KeySettings(key_color="#00C800", tolerance=0.05, softness=0.8,
                                                         edge_decontaminate=True), {}))
    edge = (cov > 0.3) & (cov < 0.7)
    # decontaminated edge pixels lean red, not green
    assert (decon[edge][:, 0].astype(int) > decon[edge][:, 1].astype(int)).mean() > 0.9


def test_key_pass_returns_key_rgb_for_chroma_only():
    img, _ = _image()
    _rgb, _alpha, key = keying.key_pass(img, KeySettings(key_color="#00C800"), {})
    assert key == (0, 200, 0)
    _rgb, _alpha, key = keying.key_pass(img, KeySettings(method="none"), {})
    assert key is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_key_frame.py -v`
Expected: FAIL with `AttributeError: module 'core.sprite.keying' has no attribute 'resolve_key_settings'`.

- [ ] **Step 3: Append the implementation to `core/sprite/keying.py`**

```python
# --- settings, overrides, and the three passes -------------------------------------

def resolve_key_settings(settings: KeySettings, plate_color: str) -> KeySettings:
    """Return settings with ``key_color`` filled from the plate color when it is None."""
    if settings.key_color:
        return settings
    return replace(settings, key_color=plate_color)


def apply_overrides(settings: KeySettings, overrides: Dict[str, Any]) -> KeySettings:
    """Apply per-frame overrides (``key_color``, ``tolerance``, ``softness``)."""
    if not overrides:
        return settings
    changes: Dict[str, Any] = {}
    for key, value in overrides.items():
        if value is None:
            continue
        if key == "key_color":
            changes[key] = str(value)
        elif key in ("tolerance", "softness"):
            changes[key] = float(value)
        else:
            logger.debug("Ignoring unknown per-frame override %r", key)
    return replace(settings, **changes) if changes else settings


def frame_overrides(frames: Sequence[FrameMeta], index: int) -> Dict[str, Any]:
    """Overrides recorded on the frame at ``index``; ``{}`` when there is none."""
    if 0 <= index < len(frames):
        return dict(frames[index].overrides or {})
    return {}


def _ml_alpha(image: Image.Image, backend: str, model: str, refine_edges: bool) -> np.ndarray:
    """Indirection so the ML backends load lazily (Task 6 creates core.sprite.matting)."""
    from core.sprite.matting import ml_alpha
    return ml_alpha(image, backend, model, refine_edges=refine_edges)


def key_pass(image: Image.Image, settings: KeySettings,
             overrides: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray, Optional[Tuple[int, int, int]]]:
    """Stage ``key``: estimate alpha and despill. Returns (rgb uint8, alpha float32, key_rgb)."""
    eff = apply_overrides(settings, overrides)
    if eff.method not in KEY_METHODS:
        msg = f"Unknown key method {eff.method!r}; choose one of {KEY_METHODS}"
        logger.error(msg)
        raise KeyingError(msg)
    if eff.method == "none":
        rgb, alpha = split_rgba(image)
        return rgb, alpha, None
    rgb = np.asarray(image.convert("RGB")).copy()
    if eff.method == "ml":
        alpha = np.asarray(_ml_alpha(image, eff.ml_backend, eff.ml_model, eff.ml_refine_edges),
                           dtype=np.float32)
        return rgb, np.clip(alpha, 0.0, 1.0), None
    if eff.key_color:
        key_rgb = hex_to_rgb(eff.key_color)
    else:
        picked = pick_key_color(image, (0, 0), radius=2)
        logger.warning("No key color set; sampled the top-left corner: %s", picked)
        key_rgb = hex_to_rgb(picked)
    alpha = chroma_alpha(rgb, key_rgb, eff.tolerance, eff.softness)
    rgb = despill(rgb, key_rgb, eff.despill)
    return rgb, alpha, key_rgb


def cleanup_pass(alpha: np.ndarray, settings: KeySettings) -> np.ndarray:
    """Stage ``cleanup``: despeckle, choke, feather."""
    return choke_feather(alpha, settings.choke_px, settings.feather_px, settings.despeckle_px)


def alpha_pass(rgb: np.ndarray, alpha: np.ndarray, key_rgb: Optional[Tuple[int, int, int]],
               settings: KeySettings) -> Image.Image:
    """Stage ``alpha``: decontaminate edge colors against the key, then compose RGBA."""
    if settings.edge_decontaminate and key_rgb is not None:
        rgb = decontaminate_edges(rgb, alpha, key_rgb)
    return compose_rgba(rgb, alpha)


def key_frame(image: Image.Image, settings: KeySettings, overrides: Dict[str, Any]) -> Image.Image:
    """One-shot keyer for previews, the CLI, and tests: key -> cleanup -> alpha."""
    rgb, alpha, key_rgb = key_pass(image, settings, overrides)
    alpha = cleanup_pass(alpha, settings)
    return alpha_pass(rgb, alpha, key_rgb, apply_overrides(settings, overrides))
```

`pick_key_color` is defined in Task 5. Until then, add this minimal version at the end of the file so Task 4 runs; Task 5 replaces it with the final one (same signature):

```python
def pick_key_color(image: Image.Image, xy: Tuple[int, int], radius: int = 2) -> str:
    """Average color in a (2*radius+1)² window around ``xy`` as ``#RRGGBB``."""
    rgb = np.asarray(image.convert("RGB"))
    h, w = rgb.shape[:2]
    x, y = int(xy[0]), int(xy[1])
    if not (0 <= x < w and 0 <= y < h):
        raise ValueError(f"Point {xy} lies outside the {w}x{h} image")
    r = max(0, int(radius))
    patch = rgb[max(0, y - r): y + r + 1, max(0, x - r): x + r + 1]
    return rgb_to_hex(patch.reshape(-1, 3).mean(axis=0))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_key_frame.py -v`
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/keying.py tests/sprite/test_key_frame.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): key_frame with stage passes and per-frame overrides"
```

---

### Task 5: `ffmpeg_chromakey_preview` and `pick_key_color`

**Files:**
- Modify: `core/sprite/keying.py` (append; `pick_key_color` from Task 4 stays as written)
- Create: `tests/sprite/test_keying_ffmpeg.py`

**Interfaces:**
- Consumes: `core.video.ffmpeg_utils.get_ffmpeg_path() -> Optional[str]`, `is_ffmpeg_available() -> bool`.
- Produces:
  - `keying.ffmpeg_chromakey_preview(video: Path, out_mp4: Path, key_color: str, similarity: float, blend: float) -> Path` — runs the ffmpeg `chromakey` filter and composites over neutral grey (`0x7F7F7F`) so an MP4 can show the result; raises `KeyingError` with the stderr tail.
  - `keying.pick_key_color(image, xy, radius=2) -> str` (Task 4 version is final).

Filter graph (verified with the imageio-ffmpeg 7.0.2 binary): `[0:v]split[bg_in][fg_in];[bg_in]drawbox=color=0x7F7F7F:t=fill[bg];[fg_in]chromakey=0xRRGGBB:S:B[fg];[bg][fg]overlay=format=auto,format=yuv420p`. `drawbox … t=fill` fills the whole frame, so the graph needs no size.

- [ ] **Step 1: Write the failing tests**

```python
# tests/sprite/test_keying_ffmpeg.py
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core.sprite import keying
from core.video.ffmpeg_utils import get_ffmpeg_path, is_ffmpeg_available
from tests.sprite.keying_fixtures import disc_on_field

needs_ffmpeg = pytest.mark.skipif(not is_ffmpeg_available(), reason="ffmpeg not available")


def _synthetic_clip(tmp_path: Path) -> Path:
    frames = tmp_path / "frames"
    frames.mkdir()
    for i in range(6):
        rgb = np.zeros((48, 64, 3), dtype=np.uint8)
        rgb[:, :, 1] = 255
        rgb[16:32, 20 + i:36 + i] = (220, 40, 40)
        Image.fromarray(rgb).save(frames / f"{i + 1:04d}.png")
    clip = tmp_path / "src.mp4"
    subprocess.run([get_ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-framerate", "12",
                    "-i", str(frames / "%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)],
                   check=True, capture_output=True, text=True)
    return clip


def _first_frame(video: Path, out_png: Path) -> np.ndarray:
    subprocess.run([get_ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
                    "-frames:v", "1", str(out_png)], check=True, capture_output=True, text=True)
    return np.asarray(Image.open(out_png).convert("RGB"))


@needs_ffmpeg
def test_preview_keys_green_to_grey_and_keeps_the_subject(tmp_path):
    clip = _synthetic_clip(tmp_path)
    out = keying.ffmpeg_chromakey_preview(clip, tmp_path / "preview.mp4", "#00FF00", 0.30, 0.10)
    assert out.exists() and out.stat().st_size > 0
    px = _first_frame(out, tmp_path / "first.png")
    corner = px[2, 2].astype(int)
    center = px[24, 28].astype(int)
    assert abs(corner[0] - corner[1]) < 20 and abs(corner[1] - corner[2]) < 20   # grey
    assert center[0] > 150 and center[1] < 100                                   # red survives


@needs_ffmpeg
def test_preview_failure_raises_keying_error_with_message(tmp_path, caplog):
    with caplog.at_level("ERROR"):
        with pytest.raises(keying.KeyingError) as info:
            keying.ffmpeg_chromakey_preview(tmp_path / "missing.mp4", tmp_path / "out.mp4", "#00FF00", 0.3, 0.1)
    assert info.value.user_message
    assert "chromakey preview" in caplog.text.lower()


def test_preview_without_ffmpeg_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(keying, "get_ffmpeg_path", lambda: None)
    with pytest.raises(keying.KeyingError):
        keying.ffmpeg_chromakey_preview(tmp_path / "a.mp4", tmp_path / "b.mp4", "#00FF00", 0.3, 0.1)


def test_pick_key_color_averages_a_window():
    rgb, _ = disc_on_field(gradient=False)
    img = Image.fromarray(rgb)
    assert keying.pick_key_color(img, (2, 2)) == "#00C800"
    assert keying.pick_key_color(img, (32, 24), radius=0) == "#DC2828"
    assert keying.pick_key_color(img, (0, 0), radius=5) == "#00C800"     # window clipped at the border


def test_pick_key_color_rejects_points_outside_the_image():
    rgb, _ = disc_on_field()
    with pytest.raises(ValueError):
        keying.pick_key_color(Image.fromarray(rgb), (999, 0))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_keying_ffmpeg.py -v`
Expected: the three preview tests FAIL with `AttributeError: … has no attribute 'ffmpeg_chromakey_preview'`; the two `pick_key_color` tests PASS (Task 4 shipped the function).

- [ ] **Step 3: Append the implementation to `core/sprite/keying.py`**

```python
# --- ffmpeg preview --------------------------------------------------------------------

def ffmpeg_chromakey_preview(video: Path, out_mp4: Path, key_color: str,
                             similarity: float, blend: float) -> Path:
    """Render a quick keyed preview MP4: ffmpeg ``chromakey`` composited over neutral grey.

    ``similarity`` (0.01..1) and ``blend`` (0..1) are the ffmpeg filter parameters.
    """
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        msg = "FFmpeg is not available; install it from the Video tab or put ffmpeg on PATH."
        logger.error("Chromakey preview failed: %s", msg)
        raise KeyingError(msg)
    r, g, b = hex_to_rgb(key_color)
    color = f"0x{r:02X}{g:02X}{b:02X}"
    similarity = min(1.0, max(0.01, float(similarity)))
    blend = min(1.0, max(0.0, float(blend)))
    graph = (
        "[0:v]split[bg_in][fg_in];"
        "[bg_in]drawbox=color=0x7F7F7F:t=fill[bg];"
        f"[fg_in]chromakey={color}:{similarity:.3f}:{blend:.3f}[fg];"
        "[bg][fg]overlay=format=auto,format=yuv420p"
    )
    out_mp4 = Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
           "-filter_complex", graph, "-c:v", "libx264", "-preset", "veryfast", "-an", str(out_mp4)]
    logger.info("Chromakey preview: %s", " ".join(cmd))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as exc:
        msg = f"Chromakey preview could not run ffmpeg: {exc}"
        logger.error(msg)
        raise KeyingError(msg) from exc
    if result.returncode != 0:
        tail = (result.stderr or "").strip()[-800:]
        msg = f"Chromakey preview failed (ffmpeg exit {result.returncode}): {tail}"
        logger.error(msg)
        raise KeyingError(msg)
    return out_mp4
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_keying_ffmpeg.py -v`
Expected: 5 passed (or 3 passed + 2 skipped without ffmpeg; the venv has imageio-ffmpeg, so expect 5).

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/keying.py tests/sprite/test_keying_ffmpeg.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): ffmpeg chromakey preview and key-color picker"
```

---

### Task 6: ML matting backends, `REMBG_MODELS`, model cache path, `CACHE_OWNERS` pin

**Files:**
- Create: `core/sprite/matting.py`
- Modify: `core/data_migration.py:51-54` (`CACHE_OWNERS`)
- Modify: `tests/migration/test_data_migration.py` (append a test after line 736)
- Create: `tests/sprite/test_matting.py`

**Interfaces:**
- Consumes: `core.paths.get_data_paths().model_cache(name) -> Path`; `PackageInstaller` is not called here.
- Produces:
  - `matting.ML_BACKENDS = ("mediapipe", "rembg")`
  - `matting.REMBG_MODELS: Dict[str, Dict[str, Any]]` — keys `isnet-anime`, `u2netp`, `bria-rmbg`; values carry `size_mb`, `license`, `default_ok`, `description`.
  - `matting.DEFAULT_REMBG_MODEL = "isnet-anime"`
  - `matting.MattingUnavailable(RuntimeError)` with `.user_message`.
  - `matting.available_backends() -> Dict[str, bool]`
  - `matting.rembg_model_dir() -> Path`
  - `matting.ml_alpha(image: Image.Image, backend: str, model: str, *, refine_edges: bool) -> np.ndarray` — float32 HxW 0..1.
  - `matting.clear_sessions() -> None` — drops cached rembg sessions.

Backend notes: mediapipe uses the legacy `mp.solutions.selfie_segmentation` API (repo pin `mediapipe>=0.10.0,<0.10.15`, see `core/character_animator/installer.py:39`). rembg reads `U2NET_HOME` for its model directory; set it to `rembg_model_dir()` before the first session. Sessions cache per model in `_REMBG_SESSIONS`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/sprite/test_matting.py
import importlib.machinery
import os
import sys
import types

import numpy as np
import pytest
from PIL import Image

from core.paths import get_data_paths
from core.sprite import matting
from tests.sprite.keying_fixtures import disc_on_field


def _fake_module(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    mod.__spec__ = importlib.machinery.ModuleSpec(name, None)
    return mod


@pytest.fixture(autouse=True)
def _fresh_sessions():
    matting.clear_sessions()
    yield
    matting.clear_sessions()


def test_rembg_models_table_marks_bria_non_default():
    assert matting.REMBG_MODELS["isnet-anime"]["default_ok"] is True
    assert matting.REMBG_MODELS["u2netp"]["default_ok"] is True
    assert matting.REMBG_MODELS["bria-rmbg"]["default_ok"] is False
    assert "NC" in matting.REMBG_MODELS["bria-rmbg"]["license"]
    for info in matting.REMBG_MODELS.values():
        assert set(info) >= {"size_mb", "license", "default_ok", "description"}
    assert matting.DEFAULT_REMBG_MODEL == "isnet-anime"
    assert matting.REMBG_MODELS[matting.DEFAULT_REMBG_MODEL]["default_ok"] is True


def test_rembg_model_dir_is_the_models_cache():
    assert matting.rembg_model_dir() == get_data_paths().model_cache("rembg")
    assert matting.rembg_model_dir().is_dir()


def test_available_backends_reports_missing_modules(monkeypatch):
    monkeypatch.delitem(sys.modules, "mediapipe", raising=False)
    monkeypatch.delitem(sys.modules, "rembg", raising=False)
    monkeypatch.setattr(matting, "_installed", lambda name: False)
    assert matting.available_backends() == {"mediapipe": False, "rembg": False}


def test_available_backends_sees_injected_modules(monkeypatch):
    monkeypatch.setitem(sys.modules, "mediapipe", _fake_module("mediapipe"))
    monkeypatch.setitem(sys.modules, "rembg", _fake_module("rembg"))
    assert matting.available_backends() == {"mediapipe": True, "rembg": True}


def test_ml_alpha_unknown_backend_raises_and_logs(caplog):
    with caplog.at_level("ERROR"):
        with pytest.raises(matting.MattingUnavailable) as info:
            matting.ml_alpha(Image.new("RGB", (4, 4)), "magic", "x", refine_edges=False)
    assert info.value.user_message and "magic" in caplog.text


def test_ml_alpha_missing_backend_names_the_install(monkeypatch, caplog):
    monkeypatch.delitem(sys.modules, "rembg", raising=False)
    monkeypatch.setattr(matting, "_installed", lambda name: False)
    with caplog.at_level("ERROR"):
        with pytest.raises(matting.MattingUnavailable) as info:
            matting.ml_alpha(Image.new("RGB", (4, 4)), "rembg", "u2netp", refine_edges=False)
    assert "requirements-sprite-ml.txt" in info.value.user_message


def test_ml_alpha_mediapipe_uses_selfie_segmentation(monkeypatch):
    rgb, cov = disc_on_field()
    seen = {}

    class FakeSeg:
        def __init__(self, model_selection):
            seen["model_selection"] = model_selection

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def process(self, array):
            seen["shape"] = array.shape
            return types.SimpleNamespace(segmentation_mask=cov.astype(np.float32))

    mp = _fake_module("mediapipe")
    mp.solutions = types.SimpleNamespace(selfie_segmentation=types.SimpleNamespace(SelfieSegmentation=FakeSeg))
    monkeypatch.setitem(sys.modules, "mediapipe", mp)
    alpha = matting.ml_alpha(Image.fromarray(rgb), "mediapipe", "", refine_edges=False)
    assert alpha.dtype == np.float32 and alpha.shape == cov.shape
    assert seen["model_selection"] == 1 and seen["shape"] == rgb.shape
    assert np.allclose(alpha, cov)


def test_ml_alpha_mediapipe_refine_edges_tightens_the_mask(monkeypatch):
    rgb, cov = disc_on_field()
    soft = np.clip(cov * 0.6 + 0.2, 0, 1).astype(np.float32)   # blurry mask: 0.2 background, 0.8 subject

    class FakeSeg:
        def __init__(self, model_selection):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def process(self, array):
            return types.SimpleNamespace(segmentation_mask=soft)

    mp = _fake_module("mediapipe")
    mp.solutions = types.SimpleNamespace(selfie_segmentation=types.SimpleNamespace(SelfieSegmentation=FakeSeg))
    monkeypatch.setitem(sys.modules, "mediapipe", mp)
    raw = matting.ml_alpha(Image.fromarray(rgb), "mediapipe", "", refine_edges=False)
    tight = matting.ml_alpha(Image.fromarray(rgb), "mediapipe", "", refine_edges=True)
    # Means, not extremes: the 1 px blur leaves a small halo right next to the edge.
    assert tight[cov == 0].mean() < raw[cov == 0].mean() * 0.5
    assert tight[cov == 1].mean() > raw[cov == 1].mean()
    assert tight.min() >= 0.0 and tight.max() <= 1.0


def test_ml_alpha_rembg_sets_model_dir_and_caches_sessions(monkeypatch):
    rgb, cov = disc_on_field()
    monkeypatch.delenv("U2NET_HOME", raising=False)
    made = []
    removed = []

    def new_session(model_name):
        made.append(model_name)
        return object()

    def remove(img, session=None, only_mask=False, alpha_matting=False, **kw):
        removed.append((only_mask, alpha_matting, os.environ.get("U2NET_HOME")))
        return Image.fromarray((cov * 255).astype(np.uint8))      # 2-D uint8 -> mode "L"

    rembg = _fake_module("rembg")
    rembg.new_session = new_session
    rembg.remove = remove
    monkeypatch.setitem(sys.modules, "rembg", rembg)
    a1 = matting.ml_alpha(Image.fromarray(rgb), "rembg", "u2netp", refine_edges=False)
    a2 = matting.ml_alpha(Image.fromarray(rgb), "rembg", "u2netp", refine_edges=True)
    assert made == ["u2netp"]                              # session cached
    assert removed[0][:2] == (True, False) and removed[1][:2] == (True, True)
    assert removed[0][2] == str(matting.rembg_model_dir())
    assert a1.dtype == np.float32 and np.allclose(a1, cov, atol=1 / 255) and np.allclose(a2, cov, atol=1 / 255)


def test_ml_alpha_rembg_warns_on_non_default_model(monkeypatch, caplog):
    rgb, cov = disc_on_field()
    rembg = _fake_module("rembg")
    rembg.new_session = lambda name: object()
    rembg.remove = lambda img, **kw: Image.fromarray((cov * 255).astype(np.uint8))
    monkeypatch.setitem(sys.modules, "rembg", rembg)
    with caplog.at_level("WARNING"):
        matting.ml_alpha(Image.fromarray(rgb), "rembg", "bria-rmbg", refine_edges=False)
    assert "non-commercial" in caplog.text.lower()


def test_ml_alpha_rembg_unknown_model_raises(monkeypatch):
    rembg = _fake_module("rembg")
    rembg.new_session = lambda name: object()
    rembg.remove = lambda img, **kw: Image.new("L", (4, 4))
    monkeypatch.setitem(sys.modules, "rembg", rembg)
    with pytest.raises(matting.MattingUnavailable):
        matting.ml_alpha(Image.new("RGB", (4, 4)), "rembg", "not-a-model", refine_edges=False)
```

Append to `tests/migration/test_data_migration.py` after line 736 (after `test_moving_video_takes_only_the_video_cache`):

```python
def test_moving_models_takes_the_rembg_cache(tmp_path, paths):
    """The sprite matting models live in cache/rembg and belong to the Models group."""
    _populate(tmp_path / "cache", ["rembg", "video"], size=32)
    _populate(tmp_path, ["weights"], size=32)
    dest = tmp_path / "dest"

    result = move_group(Group.MODELS, dest, paths=paths)

    assert result.ok, result.error
    assert (dest / "cache" / "rembg" / "f.bin").exists()
    assert not (dest / "cache" / "video").exists()
    assert (tmp_path / "cache" / "video" / "f.bin").exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_matting.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/migration/test_data_migration.py -k "matting or rembg" -v`
Expected: `test_matting.py` FAILS at collection (`No module named 'core.sprite.matting'`); `test_moving_models_takes_the_rembg_cache` FAILS on `(dest / "cache" / "rembg" / "f.bin").exists()`.

- [ ] **Step 3: Edit `core/data_migration.py:51-54`**

```python
CACHE_OWNERS: Dict[Group, Tuple[str, ...]] = {
    Group.MODELS: ("ai_visemes", "rembg"),
    Group.VIDEO: ("video", "thumbnails", "veo_videos"),
}
```

- [ ] **Step 4: Create `core/sprite/matting.py`**

```python
# core/sprite/matting.py
"""ML background removal and difference matting for sprite frames.

Both ML backends are optional extras (requirements-sprite-ml.txt) and load
lazily. Nothing here imports Qt.

Design: Plans/2026-08-29-sprite-tab-design.md §1.7, §4.3.
"""
from __future__ import annotations

import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

import cv2
import numpy as np
from PIL import Image

from core.paths import get_data_paths

logger = logging.getLogger(__name__)

ML_BACKENDS = ("mediapipe", "rembg")
DEFAULT_REMBG_MODEL = "isnet-anime"
INSTALL_HINT = ("Install the optional ML extras: "
                "python -m pip install -r requirements-sprite-ml.txt "
                "(or use Sprite > Install ML backends).")

# Never ship weights, never make a model a dependency. ``default_ok`` False means the
# UI must not preselect the model and must show its license.
REMBG_MODELS: Dict[str, Dict[str, Any]] = {
    "isnet-anime": {"size_mb": 168, "license": "MIT", "default_ok": True,
                    "description": "Anime / illustrated characters (default)"},
    "u2netp": {"size_mb": 4.4, "license": "Apache-2.0", "default_ok": True,
               "description": "Small general model, fast download"},
    "bria-rmbg": {"size_mb": 1000, "license": "CC BY-NC (paid commercial)", "default_ok": False,
                  "description": "High quality; non-commercial license, never default"},
}

_REMBG_SESSIONS: Dict[str, Any] = {}


class MattingUnavailable(RuntimeError):
    """A matting backend is missing or refused the request. ``user_message`` is UI-safe."""

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


def _installed(name: str) -> bool:
    """True when ``name`` is importable. Does not import it."""
    if name in sys.modules:
        return True
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def available_backends() -> Dict[str, bool]:
    return {name: _installed(name) for name in ML_BACKENDS}


def rembg_model_dir() -> Path:
    """Where rembg keeps its ONNX models: <Models root>/cache/rembg (moves with the group)."""
    path = get_data_paths().model_cache("rembg")
    path.mkdir(parents=True, exist_ok=True)
    return path


def clear_sessions() -> None:
    _REMBG_SESSIONS.clear()


def _fail(message: str) -> MattingUnavailable:
    logger.error("Matting unavailable: %s", message)
    return MattingUnavailable(message)


def _tighten(mask: np.ndarray) -> np.ndarray:
    """Cheap edge refinement for a blurry segmentation mask: contrast stretch + 1 px blur."""
    stretched = np.clip((mask - 0.5) * 4.0 + 0.5, 0.0, 1.0).astype(np.float32)
    return np.clip(cv2.GaussianBlur(stretched, (0, 0), sigmaX=1.0), 0.0, 1.0).astype(np.float32)


def _mediapipe_alpha(rgb: np.ndarray, refine_edges: bool) -> np.ndarray:
    if not _installed("mediapipe"):
        raise _fail(f"MediaPipe is not installed. {INSTALL_HINT}")
    import mediapipe as mp  # lazy: heavy import
    solutions = getattr(mp, "solutions", None)
    if solutions is None or not hasattr(solutions, "selfie_segmentation"):
        raise _fail("This MediaPipe build has no mp.solutions.selfie_segmentation; "
                    "install mediapipe>=0.10.0,<0.10.15 from requirements-sprite-ml.txt.")
    with solutions.selfie_segmentation.SelfieSegmentation(model_selection=1) as seg:
        result = seg.process(np.ascontiguousarray(rgb))
    mask = getattr(result, "segmentation_mask", None)
    if mask is None:
        raise _fail("MediaPipe returned no segmentation mask for this frame.")
    alpha = np.clip(np.asarray(mask, dtype=np.float32), 0.0, 1.0)
    return _tighten(alpha) if refine_edges else alpha


def _rembg_alpha(image: Image.Image, model: str, refine_edges: bool) -> np.ndarray:
    if not _installed("rembg"):
        raise _fail(f"rembg is not installed (needs Python 3.11-3.13). {INSTALL_HINT}")
    if model not in REMBG_MODELS:
        raise _fail(f"Unknown rembg model {model!r}; choose one of {sorted(REMBG_MODELS)}.")
    info = REMBG_MODELS[model]
    if not info["default_ok"]:
        logger.warning("rembg model %s is %s - non-commercial use only; you chose it explicitly.",
                       model, info["license"])
    os.environ["U2NET_HOME"] = str(rembg_model_dir())
    from rembg import new_session, remove  # lazy: heavy import
    session = _REMBG_SESSIONS.get(model)
    if session is None:
        logger.info("rembg: loading model %s (%s MB) from %s", model, info["size_mb"], rembg_model_dir())
        session = new_session(model)
        _REMBG_SESSIONS[model] = session
    mask = remove(image.convert("RGB"), session=session, only_mask=True, alpha_matting=bool(refine_edges))
    return np.asarray(mask.convert("L"), dtype=np.float32) / 255.0


def ml_alpha(image: Image.Image, backend: str, model: str, *, refine_edges: bool) -> np.ndarray:
    """Foreground alpha (float32 HxW, 0..1) from an ML backend."""
    if backend == "mediapipe":
        return _mediapipe_alpha(np.asarray(image.convert("RGB")), refine_edges)
    if backend == "rembg":
        return _rembg_alpha(image, model or DEFAULT_REMBG_MODEL, refine_edges)
    raise _fail(f"Unknown matting backend {backend!r}; choose one of {ML_BACKENDS}.")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_matting.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/migration/test_data_migration.py -v`
Expected: `test_matting.py` 11 passed; the whole migration module passes, including `test_cache_owners_covers_every_model_cache_and_video_cache_call_site` (it scans `core/sprite/matting.py` for `model_cache("rembg")`) and `test_every_owned_cache_name_is_owned_by_exactly_one_group`.

- [ ] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/matting.py core/data_migration.py tests/sprite/test_matting.py tests/migration/test_data_migration.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): ML matting backends (mediapipe, rembg) with owned model cache"
```

---

### Task 7: `difference_matte`

**Files:**
- Modify: `core/sprite/matting.py` (append)
- Create: `tests/sprite/test_matting_difference.py`

**Interfaces:**
- Produces: `matting.difference_matte(on_white: Image.Image, on_black: Image.Image) -> Image.Image` — RGBA; α = 1 − mean(white − black), color = black / α. Consumed by sub-project 6 (image route).

- [ ] **Step 1: Write the failing tests**

```python
# tests/sprite/test_matting_difference.py
import numpy as np
import pytest
from PIL import Image

from core.sprite import matting


def _pair(fg=(220, 40, 40), size=(32, 24), radius=8.0):
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cov = np.clip(radius + 0.5 - np.sqrt((xx - w / 2) ** 2 + (yy - h / 2) ** 2), 0, 1)
    f = np.array(fg, dtype=np.float32) / 255.0
    a = cov[:, :, None]
    on_white = a * f + (1 - a) * 1.0
    on_black = a * f
    to_img = lambda arr: Image.fromarray(np.round(arr * 255).astype(np.uint8))
    return to_img(on_white), to_img(on_black), cov, f * 255


def test_difference_matte_recovers_alpha_and_colour():
    white, black, cov, fg = _pair()
    out = np.asarray(matting.difference_matte(white, black)).astype(np.float32)
    assert out.shape == cov.shape + (4,)
    assert np.abs(out[:, :, 3] / 255.0 - cov).max() <= 2 / 255
    assert np.abs(out[cov == 1][:, :3] - fg).max() <= 2
    assert (out[cov == 0][:, 3] == 0).all()
    edge = (cov > 0.3) & (cov < 0.7)
    assert np.abs(out[edge][:, :3] - fg).max() <= 6


def test_difference_matte_returns_rgba_mode():
    white, black, _, _ = _pair()
    assert matting.difference_matte(white, black).mode == "RGBA"


def test_difference_matte_rejects_size_mismatch():
    white, black, _, _ = _pair()
    with pytest.raises(ValueError):
        matting.difference_matte(white, black.resize((8, 8)))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_matting_difference.py -v`
Expected: FAIL with `AttributeError: module 'core.sprite.matting' has no attribute 'difference_matte'`.

- [ ] **Step 3: Append to `core/sprite/matting.py`**

```python
# --- difference matte (image route) ---------------------------------------------------

def difference_matte(on_white: Image.Image, on_black: Image.Image) -> Image.Image:
    """Recover RGBA from the same subject rendered on white and on black.

    alpha = 1 - mean(white - black); color = black / alpha (0 where alpha is 0).
    """
    white = np.asarray(on_white.convert("RGB"), dtype=np.float32) / 255.0
    black = np.asarray(on_black.convert("RGB"), dtype=np.float32) / 255.0
    if white.shape != black.shape:
        raise ValueError(f"Size mismatch: on_white {white.shape[:2]} vs on_black {black.shape[:2]}")
    alpha = np.clip(1.0 - (white - black).mean(axis=2), 0.0, 1.0)
    safe = np.maximum(alpha, 1.0 / 255.0)[:, :, None]
    color = np.where(alpha[:, :, None] > 0.0, black / safe, 0.0)
    rgba = np.concatenate([np.clip(color, 0.0, 1.0), alpha[:, :, None]], axis=2)
    return Image.fromarray(np.round(rgba * 255.0).astype(np.uint8))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_matting_difference.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/matting.py tests/sprite/test_matting_difference.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): difference matte from white/black pairs"
```

---

### Task 8: `dejitter` with phase-correlation, OpenCV, and centroid fallbacks (+ hard deps)

**Files:**
- Modify: `core/sprite/stabilize.py` (sub-project 1 file; append after `crop_and_pad`; find it with `grep -n "def crop_and_pad" /mnt/d/Documents/Code/GitHub/ImageAI/core/sprite/stabilize.py`)
- Modify: `requirements.txt` (insert after line 37, `opencv-python>=4.8.0 …`)
- Create: `tests/sprite/test_dejitter.py`

**Interfaces:**
- Consumes: `ProgressFn`, `no_progress`, `CancelToken`, `Cancelled` — import them from the same module `crop_and_pad` already imports them from (sub-project 1 resolved the pipeline↔stabilize import order; do not add a second path).
- Produces:
  - `stabilize.DEJITTER_METHODS = ("phase", "centroid")`
  - `stabilize.alpha_centroid(alpha: np.ndarray) -> Optional[Tuple[float, float]]` — (y, x).
  - `stabilize.estimate_shift(ref_alpha: np.ndarray, mov_alpha: np.ndarray, method: str) -> Tuple[float, float]` — (dy, dx) **to apply to the moving frame** so it registers with the reference. Order: `skimage.registration.phase_cross_correlation(upsample_factor=10)` → `cv2.phaseCorrelate` (sign flipped; `response < MIN_PHASE_RESPONSE` falls through) → centroid.
  - `stabilize.translate_rgba(rgba: np.ndarray, dy: float, dx: float) -> np.ndarray` — sub-pixel translate with premultiplied bilinear sampling (`cv2.warpAffine`), transparent border.
  - `stabilize.dejitter(frames: Sequence[Path], out_dir: Path, method: str = "phase", *, progress: ProgressFn = no_progress, token: Optional[CancelToken] = None) -> List[Path]` — aligns every frame to frame 0's alpha; `out_dir` may equal the input directory (all inputs are read before any output is written); clamps shifts to `MAX_SHIFT_FRACTION` of the frame size.

Sign conventions were verified in the venv: skimage returns the shift to apply to the moving image directly; `cv2.phaseCorrelate(ref, mov)` returns `(dx, dy)` of the motion, so the shift to apply is `(-dy, -dx)`. The tests pin both.

- [ ] **Step 1: Check package ages, then install the hard deps into the venv**

Run:

```bash
$PY - <<'EOF'
import datetime, json, urllib.request
for name in ("scikit-image", "scipy"):
    data = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json"))
    latest = data["info"]["version"]
    uploaded = min(f["upload_time_iso_8601"] for f in data["releases"][latest])
    age = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(uploaded.replace("Z", "+00:00"))
    print(f"{name}: latest {latest} uploaded {uploaded} age_days={age.days}")
EOF
```

Rule: if `age_days < 7` for a package, install with an upper bound that excludes it (`"scikit-image<LATEST"`) and say so in the task report. Then:

```bash
$PY -m pip install "scikit-image>=0.24" "scipy>=1.13"
$PY -c "import skimage, scipy; from skimage.registration import phase_cross_correlation; print(skimage.__version__, scipy.__version__)"
```

Expected: both import; versions print. (scipy 1.16.3 is already present in `.venv_linux`; scikit-image is new.)

- [ ] **Step 2: Add the hard deps to `requirements.txt` after line 37**

```
opencv-python>=4.8.0  # Required for video frame processing and assembly

# Sprite tab de-jitter (core/sprite/stabilize.py); OpenCV phaseCorrelate is the fallback
scikit-image>=0.24  # skimage.registration.phase_cross_correlation (sub-pixel frame alignment)
scipy>=1.13  # required by scikit-image
```

- [ ] **Step 3: Write the failing tests**

```python
# tests/sprite/test_dejitter.py
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core.sprite import stabilize
from core.sprite.pipeline import CancelToken, Cancelled
from tests.sprite.keying_fixtures import centroid, disc_rgba, write_png

REPO = Path(__file__).resolve().parents[2]


def _alpha(rgba: np.ndarray) -> np.ndarray:
    return rgba[:, :, 3].astype(np.float32) / 255.0


def _write_sequence(tmp_path: Path, centers) -> list:
    paths = []
    for i, c in enumerate(centers):
        paths.append(write_png(tmp_path / "in" / f"{i + 1:04d}.png", disc_rgba(center=c)))
    return paths


@pytest.mark.parametrize("method", ["phase", "centroid"])
def test_estimate_shift_recovers_an_integer_offset(method):
    ref = _alpha(disc_rgba(center=(32.0, 24.0)))
    mov = _alpha(disc_rgba(center=(35.0, 22.0)))       # moved +3 x, -2 y
    dy, dx = stabilize.estimate_shift(ref, mov, method)
    assert abs(dy - 2.0) < 0.6 and abs(dx + 3.0) < 0.6


def test_estimate_shift_opencv_fallback_has_the_right_sign(monkeypatch):
    monkeypatch.setattr(stabilize, "_phase_cross_correlation", None)
    ref = _alpha(disc_rgba(center=(32.0, 24.0)))
    mov = _alpha(disc_rgba(center=(35.0, 22.0)))
    dy, dx = stabilize.estimate_shift(ref, mov, "phase")
    assert abs(dy - 2.0) < 0.6 and abs(dx + 3.0) < 0.6


def test_estimate_shift_falls_back_to_centroid_on_weak_response(monkeypatch):
    monkeypatch.setattr(stabilize, "_phase_cross_correlation", None)
    monkeypatch.setattr(stabilize.cv2, "phaseCorrelate", lambda a, b: ((99.0, 99.0), 0.0))
    ref = _alpha(disc_rgba(center=(32.0, 24.0)))
    mov = _alpha(disc_rgba(center=(35.0, 22.0)))
    dy, dx = stabilize.estimate_shift(ref, mov, "phase")
    assert abs(dy - 2.0) < 0.2 and abs(dx + 3.0) < 0.2


def test_estimate_shift_rejects_unknown_method():
    a = _alpha(disc_rgba())
    with pytest.raises(ValueError):
        stabilize.estimate_shift(a, a, "magic")


def test_empty_masks_give_zero_shift():
    empty = np.zeros((48, 64), dtype=np.float32)
    assert stabilize.estimate_shift(empty, empty, "centroid") == (0.0, 0.0)


def test_translate_rgba_keeps_colour_and_moves_subpixel():
    src = disc_rgba(center=(33.5, 24.0))
    out = stabilize.translate_rgba(src, 0.0, -1.5)
    c = centroid(_alpha(out))
    assert abs(c[1] - 32.0) < 0.3 and abs(c[0] - 24.0) < 0.3
    assert tuple(out[24, 32, :3]) == (220, 40, 40)
    assert out.dtype == np.uint8 and out.shape == src.shape


@pytest.mark.parametrize("method", ["phase", "centroid"])
def test_dejitter_aligns_every_frame_to_the_first(tmp_path, method):
    paths = _write_sequence(tmp_path, [(32.0, 24.0), (35.0, 22.0), (30.5, 25.0), (33.0, 26.5)])
    out = stabilize.dejitter(paths, tmp_path / "out", method)
    assert [p.name for p in out] == [p.name for p in paths]
    ref = centroid(_alpha(np.asarray(Image.open(out[0]))))
    for p in out[1:]:
        c = centroid(_alpha(np.asarray(Image.open(p))))
        assert abs(c[0] - ref[0]) < 0.6 and abs(c[1] - ref[1]) < 0.6, p.name


def test_dejitter_in_place_is_safe(tmp_path):
    paths = _write_sequence(tmp_path, [(32.0, 24.0), (36.0, 24.0)])
    out = stabilize.dejitter(paths, tmp_path / "in", "centroid")
    assert out[1] == paths[1]
    c = centroid(_alpha(np.asarray(Image.open(out[1]))))
    assert abs(c[1] - 32.0) < 0.6


def test_dejitter_clamps_wild_shifts(tmp_path, caplog):
    paths = _write_sequence(tmp_path, [(10.0, 24.0), (60.0, 24.0)])   # 50 px on a 64 px frame
    with caplog.at_level("WARNING"):
        out = stabilize.dejitter(paths, tmp_path / "out", "centroid")
    c = centroid(_alpha(np.asarray(Image.open(out[1]))))
    assert c[1] > 40.0                      # moved by at most 25 % of the width (16 px)
    assert "clamp" in caplog.text.lower()


def test_dejitter_reports_progress_and_honours_cancel(tmp_path):
    paths = _write_sequence(tmp_path, [(32.0, 24.0), (33.0, 24.0), (34.0, 24.0)])
    seen = []
    stabilize.dejitter(paths, tmp_path / "out", "centroid",
                       progress=lambda stage, done, total, msg: seen.append((stage, done, total)))
    assert seen[-1] == ("stabilize", 3, 3)
    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        stabilize.dejitter(paths, tmp_path / "out2", "centroid", token=token)


def test_requirements_declare_the_dejitter_deps():
    text = (REPO / "requirements.txt").read_text(encoding="utf-8")
    names = {line.split("#")[0].strip().split(">=")[0].lower() for line in text.splitlines()
             if line.strip() and not line.startswith("#")}
    assert {"scikit-image", "scipy"} <= names
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_dejitter.py -v`
Expected: `test_requirements_declare_the_dejitter_deps` PASSES (Step 2); every other test FAILS with `AttributeError: module 'core.sprite.stabilize' has no attribute …`.

- [ ] **Step 5: Append to `core/sprite/stabilize.py`**

Add these imports at the top of the module if they are not there (`cv2`, `numpy`, `logging`, `Optional`, `Tuple`, `List`, `Sequence`), keep the existing `no_progress` / `CancelToken` import, and add:

```python
try:
    from skimage.registration import phase_cross_correlation as _phase_cross_correlation
except ImportError:  # scikit-image absent or broken: OpenCV fallback (design §1.7)
    _phase_cross_correlation = None

DEJITTER_METHODS = ("phase", "centroid")
MIN_PHASE_RESPONSE = 0.02      # cv2.phaseCorrelate response below this is noise
MAX_SHIFT_FRACTION = 0.25      # never move a frame more than a quarter of its size
```

Then append after `crop_and_pad`:

```python
# --- de-jitter -----------------------------------------------------------------------

def alpha_centroid(alpha: np.ndarray) -> Optional[Tuple[float, float]]:
    """Alpha-weighted centroid (y, x); None when the mask is empty."""
    a = np.asarray(alpha, dtype=np.float32)
    total = float(a.sum())
    if total <= 0.0:
        return None
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]].astype(np.float32)
    return float((yy * a).sum() / total), float((xx * a).sum() / total)


def _centroid_shift(ref: np.ndarray, mov: np.ndarray) -> Tuple[float, float]:
    rc = alpha_centroid(ref)
    mc = alpha_centroid(mov)
    if rc is None or mc is None:
        return 0.0, 0.0
    return rc[0] - mc[0], rc[1] - mc[1]


def estimate_shift(ref_alpha: np.ndarray, mov_alpha: np.ndarray, method: str) -> Tuple[float, float]:
    """Return (dy, dx) to apply to the moving mask so it registers with the reference.

    ``phase``: skimage phase_cross_correlation (upsample_factor=10) -> cv2.phaseCorrelate
    -> centroid. ``centroid``: centroid difference only.
    """
    if method not in DEJITTER_METHODS:
        raise ValueError(f"Unknown dejitter method {method!r}; choose one of {DEJITTER_METHODS}")
    ref = np.asarray(ref_alpha, dtype=np.float32)
    mov = np.asarray(mov_alpha, dtype=np.float32)
    if method == "centroid" or ref.sum() <= 0.0 or mov.sum() <= 0.0:
        return _centroid_shift(ref, mov)
    if _phase_cross_correlation is not None:
        shift, _error, _phase = _phase_cross_correlation(ref, mov, upsample_factor=10)
        return float(shift[0]), float(shift[1])
    (dx, dy), response = cv2.phaseCorrelate(ref, mov)
    if response < MIN_PHASE_RESPONSE:
        logger.debug("phaseCorrelate response %.3f too weak; using centroid", response)
        return _centroid_shift(ref, mov)
    return -float(dy), -float(dx)


def translate_rgba(rgba: np.ndarray, dy: float, dx: float) -> np.ndarray:
    """Sub-pixel translate an RGBA uint8 image. Premultiplied sampling avoids dark fringes."""
    src = np.asarray(rgba).astype(np.float32)
    alpha = src[:, :, 3:4] / 255.0
    pre = np.concatenate([src[:, :, :3] * alpha, src[:, :, 3:4]], axis=2)
    h, w = src.shape[:2]
    matrix = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
    moved = cv2.warpAffine(pre, matrix, (w, h), flags=cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    out_alpha = moved[:, :, 3:4] / 255.0
    rgb = np.where(out_alpha > 0.0, moved[:, :, :3] / np.maximum(out_alpha, 1e-6), 0.0)
    out = np.concatenate([rgb, moved[:, :, 3:4]], axis=2)
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def dejitter(frames: Sequence[Path], out_dir: Path, method: str = "phase", *,
             progress: ProgressFn = no_progress,
             token: Optional[CancelToken] = None) -> List[Path]:
    """Align every frame to the first frame's alpha mask and write the results.

    ``out_dir`` may be the input directory: all inputs are read before any output
    is written. Shifts are clamped to MAX_SHIFT_FRACTION of the frame size.
    """
    if method not in DEJITTER_METHODS:
        raise ValueError(f"Unknown dejitter method {method!r}; choose one of {DEJITTER_METHODS}")
    frames = [Path(p) for p in frames]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    images = []
    for path in frames:
        if token is not None:
            token.raise_if_cancelled()
        images.append(np.asarray(Image.open(path).convert("RGBA")))
    outputs: List[Path] = []
    if not images:
        return outputs
    ref_alpha = images[0][:, :, 3].astype(np.float32) / 255.0
    h, w = ref_alpha.shape
    max_dy, max_dx = MAX_SHIFT_FRACTION * h, MAX_SHIFT_FRACTION * w
    total = len(images)
    for index, (path, rgba) in enumerate(zip(frames, images)):
        if token is not None:
            token.raise_if_cancelled()
        dst = out_dir / path.name
        if index == 0:
            Image.fromarray(rgba).save(dst)
        else:
            mov_alpha = rgba[:, :, 3].astype(np.float32) / 255.0
            dy, dx = estimate_shift(ref_alpha, mov_alpha, method)
            cdy, cdx = max(-max_dy, min(max_dy, dy)), max(-max_dx, min(max_dx, dx))
            if (cdy, cdx) != (dy, dx):
                logger.warning("dejitter %s: clamped shift (%.2f, %.2f) to (%.2f, %.2f)",
                               path.name, dy, dx, cdy, cdx)
            Image.fromarray(translate_rgba(rgba, cdy, cdx)).save(dst)
        outputs.append(dst)
        progress("stabilize", index + 1, total, f"dejitter {path.name}")
    return outputs
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_dejitter.py -v`
Expected: 13 passed. Also run sub-project 1's stabilize tests to confirm nothing regressed: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite -k stabilize -v` → all pass.

- [ ] **Step 7: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/stabilize.py requirements.txt tests/sprite/test_dejitter.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): de-jitter frames by phase correlation with OpenCV and centroid fallbacks"
```

---

### Task 9: Wire `key`, `cleanup`, `alpha`, de-jitter, and the HD alpha guarantee into the pipeline

**Files:**
- Modify: `core/sprite/pipeline.py` (sub-project 1 file). Locate the hooks first:
  `grep -n "register_stage\|_runner\|_stage_settings\|def stage_fingerprint\|def stage_dir\|def run_pipeline\|def _sync_frames\|UPSTREAM" /mnt/d/Documents/Code/GitHub/ImageAI/core/sprite/pipeline.py`
  Sub-project 1 names (confirmed 2026-08-29): runners `extract_runner`, `identity_runner` (registered for `key`, `cleanup`, `alpha`, `pixel`), `stabilize_runner`, `hd_runner`; settings functions `extract_stage_settings`, `key_stage_settings`, `cleanup_stage_settings`, `alpha_stage_settings`, `stabilize_stage_settings`, `hd_stage_settings`, `pixel_stage_settings`; `SettingsFn = Callable[[SpriteProject, ActionCard], Dict[str, Any]]`; `UPSTREAM` maps key←extract, cleanup←key, alpha←cleanup, stabilize←alpha, hd←stabilize, pixel←stabilize; `run_pipeline` rebuilds `action.frames` from the `stabilize` output via `_sync_frames`.
- Create: `tests/sprite/test_pipeline_keying.py`

**Interfaces:**
- Consumes: `register_stage(stage, runner, settings_fn=None, code_version=1)`, `STAGE_RUNNERS`, `STAGE_SETTINGS`, `STAGE_CODE_VERSION`, `stage_fingerprint(project, action, stage) -> str`, `stage_dir(project, action, stage) -> Path`, `run_pipeline(project, action, *, upto, progress, token, force) -> Dict[str, List[Path]]` (design §4.1); `SpriteProject`, `ActionCard`, `FrameMeta`, `OutputProfile` (design §2); Tasks 3, 4, 8.
- Produces:
  - `pipeline.key_stage_settings(project, action) -> Dict[str, Any]`, `pipeline.cleanup_stage_settings(...)`, `pipeline.alpha_stage_settings(...)` — sub-project 1's placeholder bodies replaced; still registered in `STAGE_SETTINGS`.
  - Runners `key_runner`, `cleanup_runner`, `alpha_runner` registered in `STAGE_RUNNERS` (replacing `identity_runner` for those three stages; `pixel` keeps `identity_runner` until sub-project 4); `stabilize_runner` calls `dejitter` when `project.stabilize.dejitter`; `hd_runner` calls `keying.apply_profile_alpha`.
  - `STAGE_CODE_VERSION["key"|"cleanup"|"alpha"|"stabilize"|"hd"]` incremented by 1 each (via the `code_version=` argument of `register_stage`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/sprite/test_pipeline_keying.py
import uuid
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core.sprite import pipeline
from core.sprite.models import FrameMeta
from core.sprite.project import ActionCard, SpriteProject
from tests.sprite.keying_fixtures import disc_on_field, write_png

CENTERS = [(30.0, 24.0), (32.0, 24.0), (34.0, 24.0), (33.0, 23.0)]


def _project(tmp_path: Path) -> SpriteProject:
    project = SpriteProject(name="keytest", project_dir=tmp_path / "proj")
    project.plate_color = "#00C800"
    return project


def _action() -> ActionCard:
    return ActionCard(id=uuid.uuid4().hex, name="walk", prompt="walk cycle")


def _seed_extract(project: SpriteProject, action: ActionCard) -> list:
    """Pretend the extract stage ran: write frames and record its fingerprint (design §1.2)."""
    out = pipeline.stage_dir(project, action, "extract")
    paths = []
    for i, c in enumerate(CENTERS):
        rgb, _cov = disc_on_field(center=c)
        paths.append(write_png(out / f"{i + 1:04d}.png", rgb))
    project.stage_fingerprints.setdefault(action.id, {})["extract"] = \
        pipeline.stage_fingerprint(project, action, "extract")
    action.frames = [FrameMeta(name=f"walk_{i:02d}", source_path=p, frame=(0, 0, 0, 0))
                     for i, p in enumerate(paths)]
    project.actions.append(action)
    return paths


def _rgba(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGBA"))


def test_key_cleanup_alpha_stages_produce_keyed_rgba(tmp_path):
    project = _project(tmp_path)
    action = _action()
    _seed_extract(project, action)
    result = pipeline.run_pipeline(project, action, upto="alpha")
    for stage in ("key", "cleanup", "alpha"):
        assert len(result[stage]) == len(CENTERS)
        assert [p.name for p in result[stage]] == [f"{i + 1:04d}.png" for i in range(len(CENTERS))]
    _rgb, cov = disc_on_field(center=CENTERS[0])
    out = _rgba(result["alpha"][0])
    assert out[cov == 0][:, 3].max() == 0
    assert out[cov == 1][:, 3].min() == 255
    assert tuple(out[24, 30, :3]) == (220, 40, 40)


def test_per_frame_override_changes_only_that_frame(tmp_path):
    project = _project(tmp_path)
    action = _action()
    _seed_extract(project, action)
    action.frames[1].overrides = {"tolerance": 0.95}
    result = pipeline.run_pipeline(project, action, upto="key")
    assert _rgba(result["key"][0])[:, :, 3].max() == 255
    assert _rgba(result["key"][1])[:, :, 3].max() == 0
    assert _rgba(result["key"][2])[:, :, 3].max() == 255


def test_changed_override_changes_the_key_fingerprint(tmp_path):
    project = _project(tmp_path)
    action = _action()
    _seed_extract(project, action)
    before = pipeline.stage_fingerprint(project, action, "key")
    action.frames[1].overrides = {"softness": 0.3}
    assert pipeline.stage_fingerprint(project, action, "key") != before
    settings = pipeline.STAGE_SETTINGS["key"](project, action)
    assert settings["overrides"][1] == {"softness": 0.3}
    assert settings["key_color"] == "#00C800"


def test_cleanup_settings_change_only_cleanup_and_later(tmp_path):
    project = _project(tmp_path)
    action = _action()
    _seed_extract(project, action)
    key_fp = pipeline.stage_fingerprint(project, action, "key")
    cleanup_fp = pipeline.stage_fingerprint(project, action, "cleanup")
    project.key.choke_px = 2
    assert pipeline.stage_fingerprint(project, action, "key") == key_fp
    assert pipeline.stage_fingerprint(project, action, "cleanup") != cleanup_fp


def test_choke_shrinks_the_cleanup_alpha(tmp_path):
    project = _project(tmp_path)
    action = _action()
    _seed_extract(project, action)
    plain = pipeline.run_pipeline(project, action, upto="cleanup")
    plain_sum = int(_rgba(plain["cleanup"][0])[:, :, 3].sum())
    project.key.choke_px = 2
    choked = pipeline.run_pipeline(project, action, upto="cleanup")
    assert int(_rgba(choked["cleanup"][0])[:, :, 3].sum()) < plain_sum


def test_stabilize_settings_include_dejitter_flags(tmp_path):
    project = _project(tmp_path)
    action = _action()
    settings = pipeline.STAGE_SETTINGS["stabilize"](project, action)
    assert settings["dejitter"] is True and settings["dejitter_method"] == "phase"


def test_stabilize_dejitters_when_enabled(tmp_path):
    from tests.sprite.keying_fixtures import centroid
    project = _project(tmp_path)
    action = _action()
    _seed_extract(project, action)
    project.stabilize.dejitter = True
    project.stabilize.dejitter_method = "centroid"
    result = pipeline.run_pipeline(project, action, upto="stabilize")
    cents = [centroid(_rgba(p)[:, :, 3].astype(np.float32) / 255.0) for p in result["stabilize"]]
    for c in cents[1:]:
        assert abs(c[1] - cents[0][1]) < 0.6 and abs(c[0] - cents[0][0]) < 0.6
    project.stabilize.dejitter = False
    result2 = pipeline.run_pipeline(project, action, upto="stabilize")
    cents2 = [centroid(_rgba(p)[:, :, 3].astype(np.float32) / 255.0) for p in result2["stabilize"]]
    assert max(abs(c[1] - cents2[0][1]) for c in cents2[1:]) > 1.0


def test_overrides_survive_the_stabilize_frame_sync(tmp_path):
    """run_pipeline rebuilds action.frames after stabilize (_sync_frames); user edits must survive."""
    project = _project(tmp_path)
    action = _action()
    _seed_extract(project, action)
    action.frames[1].overrides = {"tolerance": 0.95}
    action.frames[2].duration_ms = 250
    first = pipeline.run_pipeline(project, action, upto="stabilize")
    assert action.frames[1].overrides == {"tolerance": 0.95}
    assert action.frames[2].duration_ms == 250
    assert action.frames[1].source_path == first["stabilize"][1]
    # A second run sees the same overrides, so the key stage is still current (no re-run).
    key_fp = project.stage_fingerprints[action.id]["key"]
    pipeline.run_pipeline(project, action, upto="stabilize")
    assert project.stage_fingerprints[action.id]["key"] == key_fp
    assert _rgba(first["key"][1])[:, :, 3].max() == 0


def test_hd_profile_keeps_soft_alpha_unless_binary_requested(tmp_path):
    project = _project(tmp_path)
    action = _action()
    _seed_extract(project, action)
    hd = next(p for p in project.profiles if p.name == "hd")
    assert hd.binary_alpha is False
    soft = pipeline.run_pipeline(project, action, upto="hd")
    values = set(np.unique(_rgba(soft["hd"][0])[:, :, 3]).tolist())
    assert values - {0, 255}, "hd must keep the anti-aliased edge"
    hd.binary_alpha = True
    hard = pipeline.run_pipeline(project, action, upto="hd")
    assert set(np.unique(_rgba(hard["hd"][0])[:, :, 3]).tolist()) <= {0, 255}


def test_stage_code_versions_were_bumped():
    for stage in ("key", "cleanup", "alpha", "stabilize", "hd"):
        assert pipeline.STAGE_CODE_VERSION[stage] >= 2, stage
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pipeline_keying.py -v`
Expected: `test_key_cleanup_alpha_stages_produce_keyed_rgba` FAILS on `out[cov == 0][:, 3].max() == 0` (identity stages keep the green field opaque); `test_stage_code_versions_were_bumped` FAILS; the override and settings tests FAIL with `KeyError: 'overrides'` or on the fingerprint comparison.

- [ ] **Step 3: Edit `core/sprite/pipeline.py`**

Add imports near the top:

```python
from core.sprite import keying
from core.sprite.stabilize import dejitter
```

Replace the bodies of sub-project 1's `key_stage_settings`, `cleanup_stage_settings`, and `alpha_stage_settings` with the versions below (same names, same `SettingsFn` signature), and add the three runners next to `identity_runner`. Keep `identity_runner` itself: `pixel` still uses it until sub-project 4.

```python
def _effective_key_settings(project: SpriteProject):
    return keying.resolve_key_settings(project.key, project.plate_color)


def key_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    s = _effective_key_settings(project)
    return {
        "method": s.method, "key_color": s.key_color, "tolerance": s.tolerance,
        "softness": s.softness, "despill": s.despill, "ml_backend": s.ml_backend,
        "ml_model": s.ml_model, "ml_refine_edges": s.ml_refine_edges,
        "overrides": [keying.frame_overrides(action.frames, i) for i in range(len(action.frames))],
    }


def cleanup_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    s = project.key
    return {"choke_px": s.choke_px, "feather_px": s.feather_px, "despeckle_px": s.despeckle_px}


def alpha_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    s = _effective_key_settings(project)
    return {
        "method": s.method, "key_color": s.key_color, "edge_decontaminate": s.edge_decontaminate,
        "overrides": [keying.frame_overrides(action.frames, i) for i in range(len(action.frames))],
    }


def key_runner(project: SpriteProject, action: ActionCard, inputs: List[Path], out_dir: Path,
               progress: ProgressFn, token: Optional[CancelToken]) -> List[Path]:
    settings = _effective_key_settings(project)
    outputs: List[Path] = []
    total = len(inputs)
    for index, src in enumerate(inputs):
        if token is not None:
            token.raise_if_cancelled()
        overrides = keying.frame_overrides(action.frames, index)
        rgb, alpha, _key = keying.key_pass(Image.open(src), settings, overrides)
        dst = out_dir / src.name
        keying.compose_rgba(rgb, alpha).save(dst)
        outputs.append(dst)
        progress("key", index + 1, total, f"key {src.name}")
    return outputs


def cleanup_runner(project: SpriteProject, action: ActionCard, inputs: List[Path], out_dir: Path,
                   progress: ProgressFn, token: Optional[CancelToken]) -> List[Path]:
    outputs: List[Path] = []
    total = len(inputs)
    for index, src in enumerate(inputs):
        if token is not None:
            token.raise_if_cancelled()
        rgb, alpha = keying.split_rgba(Image.open(src))
        alpha = keying.cleanup_pass(alpha, project.key)
        dst = out_dir / src.name
        keying.compose_rgba(rgb, alpha).save(dst)
        outputs.append(dst)
        progress("cleanup", index + 1, total, f"cleanup {src.name}")
    return outputs


def alpha_runner(project: SpriteProject, action: ActionCard, inputs: List[Path], out_dir: Path,
                 progress: ProgressFn, token: Optional[CancelToken]) -> List[Path]:
    settings = _effective_key_settings(project)
    outputs: List[Path] = []
    total = len(inputs)
    for index, src in enumerate(inputs):
        if token is not None:
            token.raise_if_cancelled()
        eff = keying.apply_overrides(settings, keying.frame_overrides(action.frames, index))
        key_rgb = keying.hex_to_rgb(eff.key_color) if (eff.method == "chroma" and eff.key_color) else None
        rgb, alpha = keying.split_rgba(Image.open(src))
        dst = out_dir / src.name
        keying.alpha_pass(rgb, alpha, key_rgb, eff).save(dst)
        outputs.append(dst)
        progress("alpha", index + 1, total, f"alpha {src.name}")
    return outputs


register_stage("key", key_runner, key_stage_settings, code_version=2)
register_stage("cleanup", cleanup_runner, cleanup_stage_settings, code_version=2)
register_stage("alpha", alpha_runner, alpha_stage_settings, code_version=2)
```

These three calls replace sub-project 1's `register_stage("key", identity_runner, key_stage_settings, …)`, `("cleanup", identity_runner, …)`, and `("alpha", identity_runner, …)` lines. Leave `register_stage("pixel", identity_runner, pixel_stage_settings, …)` alone. `register_stage` writes `STAGE_RUNNERS[stage]`, `STAGE_SETTINGS[stage]`, and `STAGE_CODE_VERSION[stage]` together (re-registering replaces all three), so the tests below can read all three tables.

In `stabilize_runner`, after the existing `crop_and_pad(...)` call that produces `padded: List[Path]` in `out_dir`, add (the runner must still return the final sorted list, because `run_pipeline` feeds it to `_sync_frames`):

```python
    if project.stabilize.dejitter:
        padded = dejitter(padded, out_dir, project.stabilize.dejitter_method,
                          progress=progress, token=token)
    return padded
```

Confirm `STAGE_SETTINGS["stabilize"]` returns `dejitter` and `dejitter_method` (it does when it returns `dataclasses.asdict(project.stabilize)`; if it lists keys by hand, add `"dejitter": project.stabilize.dejitter, "dejitter_method": project.stabilize.dejitter_method`).

In `hd_runner`, where each resized frame `img` is saved, change the save to:

```python
        keying.apply_profile_alpha(img, profile).save(dst)
```

where `profile` is the hd `OutputProfile` the runner already resolved (`next(p for p in project.profiles if p.name == "hd")`).

Bump the code versions of the two runners this task edits in place (`key`/`cleanup`/`alpha` got theirs from `register_stage(..., code_version=2)` above). Edit sub-project 1's existing registration calls; do not add new ones:

```python
register_stage("stabilize", stabilize_runner, stabilize_stage_settings, code_version=2)   # was 1
register_stage("hd", hd_runner, hd_stage_settings, code_version=2)                        # was 1
```

(If sub-project 1 already left either above 1, use that value + 1.)

`_sync_frames` contract (sub-project 1, confirmed 2026-08-29): when it rebuilds `action.frames` from the `stabilize` output it carries over `overrides`, `duration_ms`, and `pivot` from the previous `FrameMeta` at the same index (indices beyond the old list get defaults; old entries beyond the new count are dropped), and sets `frame=(0, 0, w, h)`, `source_size=(w, h)`, `source_path=<stabilize output>`. Sub-project 1's `test_sync_frames_keeps_user_edits_by_index` and this plan's `test_overrides_survive_the_stabilize_frame_sync` both pin it; if either fails, the fix goes in `_sync_frames`, not in the keying stages.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite -v`
Expected: every test in `tests/sprite` passes, including sub-project 1's pipeline and exporter tests (their identity expectations for `key`/`cleanup`/`alpha` — if any test asserted that those stages copy frames byte-for-byte, update that assertion to the keyed behavior and say so in the commit body).

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/pipeline.py tests/sprite/test_pipeline_keying.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): wire key, cleanup, alpha, and de-jitter stages into the pipeline"
```

---

### Task 10: Optional ML extras file and `ml_install` helper

**Files:**
- Create: `requirements-sprite-ml.txt`
- Create: `core/sprite/ml_install.py`
- Create: `tests/sprite/test_ml_install.py`

**Interfaces:**
- Consumes: `core.package_installer.PackageInstaller(packages: List[str], update_requirements: bool = True, index_url: str = None)` — sub-project 5b constructs it with `update_requirements=False` and the tuple below.
- Produces:
  - `ml_install.MEDIAPIPE_SPEC = "mediapipe>=0.10.0,<0.10.15"`, `ml_install.REMBG_SPEC = "rembg[cpu]>=2.0.60"`, `ml_install.REMBG_PYTHON = ((3, 11), (3, 14))`.
  - `ml_install.python_supports_rembg() -> bool`
  - `ml_install.sprite_ml_packages() -> Tuple[List[str], str]` — `(packages, index_url)`; rembg omitted when Python is unsupported; `index_url` is `""` (PyPI).
  - `ml_install.requirements_file() -> Path` and `ml_install.parse_requirements(text: str) -> List[str]`.

- [ ] **Step 1: Check the package ages (same rule as Task 8)**

Run:

```bash
$PY - <<'EOF'
import datetime, json, urllib.request
for name in ("mediapipe", "rembg"):
    data = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json"))
    latest = data["info"]["version"]
    uploaded = min(f["upload_time_iso_8601"] for f in data["releases"][latest])
    age = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(uploaded.replace("Z", "+00:00"))
    print(f"{name}: latest {latest} uploaded {uploaded} age_days={age.days}")
EOF
```

Do **not** install these into `.venv_linux` in this task; they are optional extras and the tests fake the modules. Record the ages in the task report. If the newest `rembg` is younger than 7 days, add `,<LATEST` to `REMBG_SPEC` and the requirements line.

- [ ] **Step 2: Write the failing tests**

```python
# tests/sprite/test_ml_install.py
import sys
from pathlib import Path

from core.sprite import ml_install

REPO = Path(__file__).resolve().parents[2]


def test_python_supports_rembg_window(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 10, 9, "final", 0))
    assert ml_install.python_supports_rembg() is False
    monkeypatch.setattr(sys, "version_info", (3, 11, 0, "final", 0))
    assert ml_install.python_supports_rembg() is True
    monkeypatch.setattr(sys, "version_info", (3, 13, 2, "final", 0))
    assert ml_install.python_supports_rembg() is True
    monkeypatch.setattr(sys, "version_info", (3, 14, 0, "final", 0))
    assert ml_install.python_supports_rembg() is False


def test_sprite_ml_packages_on_supported_python(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 12, 3, "final", 0))
    packages, index_url = ml_install.sprite_ml_packages()
    assert packages == [ml_install.MEDIAPIPE_SPEC, ml_install.REMBG_SPEC]
    assert index_url == ""


def test_sprite_ml_packages_drops_rembg_on_old_python(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 10, 0, "final", 0))
    packages, _ = ml_install.sprite_ml_packages()
    assert packages == [ml_install.MEDIAPIPE_SPEC]


def test_requirements_file_matches_the_constants():
    path = ml_install.requirements_file()
    assert path == REPO / "requirements-sprite-ml.txt"
    specs = ml_install.parse_requirements(path.read_text(encoding="utf-8"))
    assert specs == [ml_install.MEDIAPIPE_SPEC, ml_install.REMBG_SPEC]


def test_parse_requirements_skips_comments_and_blank_lines():
    text = "# c\n\nfoo>=1  # inline\n  bar[cpu]==2.0\n"
    assert ml_install.parse_requirements(text) == ["foo>=1", "bar[cpu]==2.0"]


def test_forbidden_packages_never_appear():
    """Only real requirement lines count; comments may name bria-rmbg to say it is excluded."""
    specs = []
    for name in ("requirements-sprite-ml.txt", "requirements.txt"):
        specs += ml_install.parse_requirements((REPO / name).read_text(encoding="utf-8"))
    joined = " ".join(specs).lower()
    for forbidden in ("imagequant", "corridorkey", "bria"):
        assert forbidden not in joined
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_ml_install.py -v`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'core.sprite.ml_install'`.

- [ ] **Step 4: Create `requirements-sprite-ml.txt`**

```
# Optional ML background-removal backends for the Sprite tab (design §1.7).
# Install: python -m pip install -r requirements-sprite-ml.txt
# Or in the app: Sprite tab > Processing > Install ML backends.
# rembg needs Python >=3.11,<3.14. Models download on first use into
# <Models root>/cache/rembg (core/sprite/matting.py). bria-rmbg is
# non-commercial and is never installed or selected by default.
mediapipe>=0.10.0,<0.10.15  # legacy mp.solutions API (removed in 0.10.15+); no model download
rembg[cpu]>=2.0.60  # isnet-anime (MIT) default, u2netp (Apache-2.0)
```

- [ ] **Step 5: Create `core/sprite/ml_install.py`**

```python
# core/sprite/ml_install.py
"""Package list for the optional sprite ML backends.

The GUI install dialog (gui/sprite, sub-project 5b) passes ``sprite_ml_packages()``
to ``core.package_installer.PackageInstaller(packages, update_requirements=False)``.
The constants here are the source of truth; ``requirements-sprite-ml.txt`` mirrors
them and a test pins the two together.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

MEDIAPIPE_SPEC = "mediapipe>=0.10.0,<0.10.15"   # legacy mp.solutions API, matches core/character_animator
REMBG_SPEC = "rembg[cpu]>=2.0.60"
REMBG_PYTHON = ((3, 11), (3, 14))                # inclusive floor, exclusive ceiling


def python_supports_rembg() -> bool:
    """rembg pins Python >=3.11,<3.14."""
    version = tuple(sys.version_info[:2])
    return REMBG_PYTHON[0] <= version < REMBG_PYTHON[1]


def sprite_ml_packages() -> Tuple[List[str], str]:
    """(packages, index_url) for PackageInstaller. index_url "" means PyPI."""
    packages = [MEDIAPIPE_SPEC]
    if python_supports_rembg():
        packages.append(REMBG_SPEC)
    return packages, ""


def requirements_file() -> Path:
    """The optional-extras file at the repo root (beside requirements.txt)."""
    return Path(__file__).resolve().parents[2] / "requirements-sprite-ml.txt"


def parse_requirements(text: str) -> List[str]:
    """Non-comment, non-blank requirement specs, inline comments stripped."""
    specs: List[str] = []
    for line in text.splitlines():
        spec = line.split("#", 1)[0].strip()
        if spec:
            specs.append(spec)
    return specs
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_ml_install.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py -v`
Expected: 6 + 3 passed (the guard test accepts `Path(__file__)`-relative repo files).

- [ ] **Step 7: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add requirements-sprite-ml.txt core/sprite/ml_install.py tests/sprite/test_ml_install.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): optional ML extras file and install package helper"
```

---

### Task 11: Full-suite run and plan close-out

**Files:**
- Modify: `Plans/2026-08-29-sprite-keying-plan.md` (tick the boxes; add a "Status" line under the header)

- [ ] **Step 1: Run the whole suite**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests -q`
Expected: all green (the pre-feature baseline was 1057 tests at PR #42; sub-project 1 and this plan add to that). Fix any failure in the task that owns the code before moving on; never mark this task done on a red suite.

- [ ] **Step 2: Confirm the guard tests and the CACHE_OWNERS pin once more**

Run: `$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/migration/test_data_migration.py -q`
Expected: all pass.

- [ ] **Step 3: Confirm no forbidden dependency slipped in**

Run: `grep -rniE "imagequant|corridorkey|bria" /mnt/d/Documents/Code/GitHub/ImageAI/requirements*.txt /mnt/d/Documents/Code/GitHub/ImageAI/core/sprite/*.py`
Expected: matches only in `core/sprite/matting.py` (`REMBG_MODELS["bria-rmbg"]` with `default_ok: False`) and in the comment lines of `requirements-sprite-ml.txt`. No `pip install` line and no import references any of them.

- [ ] **Step 4: Tick every checkbox in this plan, add `**Status:** complete <YYYY-MM-DD>` under the header, and commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add Plans/2026-08-29-sprite-keying-plan.md
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "docs(plans): sprite keying plan complete"
```

---

## Self-review

**Spec coverage (design §3 row 3, §4.3, §1.7):**

| Requirement | Task |
|---|---|
| `hex_to_rgb`, `chroma_alpha` from (Cr,Cb) distance with tolerance/softness | 1 |
| `despill` average/double/limit with luminance restore | 2 |
| `decontaminate_edges` F=(C−(1−α)K)/α clamped | 2 |
| `choke_feather` erode / Gaussian / morphological open | 3 |
| `binary_alpha` threshold + defringe; hd never binarizes unless `OutputProfile.binary_alpha` | 3 (`apply_profile_alpha`), 9 (hd runner + test) |
| `key_frame` applying `KeySettings` + per-frame overrides (`key_color`, `tolerance`, `softness`) | 4 |
| `ffmpeg_chromakey_preview` (`chromakey` filter), `pick_key_color` radius average | 5 |
| `available_backends`, `ml_alpha` mediapipe selfie segmentation + rembg, `REMBG_MODELS` (size/license/default_ok), `rembg_model_dir` under `model_cache("rembg")` | 6 |
| `CACHE_OWNERS[Group.MODELS]` gains `"rembg"` + pin test | 6 |
| `difference_matte` α = 1 − (white − black), color = black/α | 7 |
| `dejitter` phase (skimage upsample 10) → cv2.phaseCorrelate → centroid; sub-pixel apply | 8 |
| scikit-image + scipy in `requirements.txt`, fallback on ImportError | 8 |
| Replace identity `key`/`cleanup`/`alpha`; de-jitter inside `stabilize` guarded by `StabilizeSettings.dejitter`; overrides plumbing; fingerprints include overrides | 9 |
| `requirements-sprite-ml.txt` (mediapipe, rembg[cpu], Python ≥3.11 note); `sprite_ml_packages()`, `python_supports_rembg()` | 10 |
| Progress/cancel contract (§1.1) in every long step | 8, 9 |
| Every user-facing error logged | 4 (`KeyingError`), 5, 6 (`MattingUnavailable`) |
| Package-age rule at install time | 8 Step 1, 10 Step 1 |
| No libimagequant / CorridorKey / bria-rmbg dependency | 10 test, 11 Step 3 |

**Placeholder scan:** no TBD/TODO; every step has code or an exact command. The only cross-plan dependencies are named symbols from sub-project 1 (`STAGE_RUNNERS`, `STAGE_SETTINGS`, `STAGE_CODE_VERSION`, `stage_fingerprint`, `stage_dir`, `run_pipeline`, `crop_and_pad`, `SpriteProject`, `ActionCard`, `FrameMeta`, `KeySettings`, `OutputProfile`, `CancelToken`, `Cancelled`, `ProgressFn`, `no_progress`), all with the design's signatures.

**Type consistency:** `chroma_alpha`/`choke_feather`/`binary_alpha`/`ml_alpha`/`estimate_shift` all use float32 HxW alpha in 0..1; `despill`/`decontaminate_edges` return uint8 HxWx3; `compose_rgba`/`split_rgba` convert between them; `key_pass` → `cleanup_pass` → `alpha_pass` types line up with the pipeline runners in Task 9; `dejitter` returns `List[Path]` with input basenames, matching the stage file contract.

## Deviations from the design

1. **Pipeline hook names.** The design fixes `run_pipeline`, `stage_fingerprint`, `stage_dir`, `STAGES`, and `STAGE_CODE_VERSION` but not how sub-project 1 dispatches stages. The team lead accepted this contract on 2026-08-29 and sent it to sub-projects 1 and 4 as canonical: `StageRunner`, `STAGE_RUNNERS`, `STAGE_SETTINGS`, `STAGE_CODE_VERSION`, and `register_stage(stage, runner, settings_fn=None, code_version=1)`. Task 9 registers through `register_stage`; its tests pin behavior, not table names.
2. **Stage split.** `key` = alpha estimation + despill; `cleanup` = despeckle/choke/feather on alpha; `alpha` = edge decontamination + final RGBA. The design lists the stages without saying which math goes where; this split keeps a choke-slider change from re-running the keyer (§1.2).
3. **`binary_alpha` return type.** Returns float32 with values {0, 1} (not uint8) so every alpha in the module shares one representation; `threshold` still applies on the 0..255 scale as the design's `int = 128` implies.
4. **Hard deps land in Task 8, not a separate requirements task.** `scikit-image`/`scipy` go into `requirements.txt` in the task whose deliverable needs them (de-jitter). Task 10 owns only the optional extras file and `ml_install.py`.
5. **`sprite_ml_packages()` source of truth.** Version specs live as constants in `core/sprite/ml_install.py`; `requirements-sprite-ml.txt` mirrors them and a test pins both. The file cannot be the source because a packaged build may not ship it.
6. **Sub-pixel apply uses `cv2.warpAffine`** (already a hard dep, handles 4 channels) rather than `scipy.ndimage.shift`; the shift estimate still comes from scikit-image when available.
7. **`dejitter` reads all frames before writing** so `stabilize` can run it in place on `crop_and_pad`'s output directory (no temp directory, no extra stage).
8. **mediapipe / numpy 2.** `.venv_linux` has numpy 2.2.6. `mediapipe<0.10.15` wheels were built against numpy 1.x; if `import mediapipe` fails with a numpy ABI error at install time, `ml_alpha` raises `MattingUnavailable` with the install hint and rembg remains the working backend. Sub-project 5b's install dialog should surface that message; record the observed behavior in the Task 10 report.
9. **`key_frame` with `key_color=None`** samples the top-left corner and logs a warning instead of raising; the pipeline never hits this path because `resolve_key_settings` fills the plate color first.
