### Task 8: Retouch core

**Files:**
- Create: `core/sprite/generation/retouch.py`
- Test: `tests/sprite/test_retouch.py`

**Interfaces:**
- Consumes: `GoogleProvider.edit_image_region(image: bytes, region_bbox, prompt, model=None, ...)` (`providers/google.py:1907-2014`); `GoogleProvider.edit_image` list input; `OpenAIProvider.edit_image(..., mask=bytes, size=...)` (`providers/openai.py:821-940`, mask semantics: alpha 0 = editable, per `_create_alpha_mask` `:1070-1122`); validation pattern from `core/character_animator/ai_face_editor.py:561-617`; helpers from Task 6/7 (`provider_kind`, `call_provider`, `first_image`, `log_request`, `log_response`, `openai_edit_size`, `default_openai_edit_model`); `ProviderError`; `write_image_sidecar`.
- Produces: `next_retouch_path(frame: Path) -> Path`; `build_region_mask(size: Size, region: Rect, feather: int = 5) -> bytes`; `fit_to_size(image, size) -> Image`; `validate_retouch(original, edited, region) -> Tuple[bool, str]`; `retouch_prompt(instruction, *, neighbors: int) -> str`; `retouch_frame(provider, frame: Path, instruction: str, out_png: Optional[Path] = None, *, neighbors: Sequence[Path] = (), region: Optional[Rect] = None, model=None, log=logger.info, attempts: int = 2) -> Path`.

- [ ] **Step 1: Write the failing test**

Create `tests/sprite/test_retouch.py`:

```python
# tests/sprite/test_retouch.py
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image

from core.sprite.generation.errors import ProviderError
from core.sprite.generation.retouch import (
    build_region_mask, fit_to_size, next_retouch_path, retouch_frame, validate_retouch,
)
from providers.google import GoogleProvider
from providers.openai import MODEL_CAPS, OpenAIProvider


def _png(w=32, h=32, shade=100) -> bytes:
    arr = np.full((h, w, 4), (shade, shade, shade, 255), dtype=np.uint8)
    arr[8:24, 8:24] = (255, 0, 0, 255)
    buf = BytesIO()
    Image.fromarray(arr, "RGBA").save(buf, "PNG")
    return buf.getvalue()


def _frames(tmp_path: Path):
    paths = []
    for i in range(1, 4):
        p = tmp_path / f"{i:04d}.png"
        p.write_bytes(_png(shade=100))
        paths.append(p)
    return paths


def _google(reply: bytes):
    provider = MagicMock(spec=GoogleProvider)
    provider.get_default_model.return_value = "default-google-image-model"
    provider.edit_image.return_value = ([], [reply])
    provider.edit_image_region.return_value = ([], [reply])
    return provider


def _openai(reply: bytes):
    provider = MagicMock(spec=OpenAIProvider)
    provider.edit_image.return_value = ([], [reply])
    return provider


def test_next_retouch_path_never_collides(tmp_path):
    frame = tmp_path / "0003.png"
    frame.write_bytes(_png())
    first = next_retouch_path(frame)
    assert first.name == "0003.r1.png"
    first.write_bytes(_png())
    assert next_retouch_path(frame).name == "0003.r2.png"
    assert next_retouch_path(first).name == "0003.r2.png"     # retouch of a retouch keeps the base name


def test_google_whole_frame_uses_neighbors_as_references(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    provider = _google(_png(shade=180))
    out = retouch_frame(provider, f2, "fix the left hand", neighbors=[f1, f3])
    assert out == tmp_path / "0002.r1.png" and out.exists()
    assert f2.read_bytes() == _png(shade=100)                   # original untouched
    args, kwargs = provider.edit_image.call_args
    assert args[0] == [f2.read_bytes(), f1.read_bytes(), f3.read_bytes()]
    assert "fix the left hand" in args[1] and "neighboring" in args[1]
    assert kwargs["model"] == "default-google-image-model"
    provider.edit_image_region.assert_not_called()
    sidecar = json.loads((tmp_path / "0002.r1.png.json").read_text(encoding="utf-8"))
    assert sidecar["route"] == "retouch" and sidecar["source_frame"].endswith("0002.png")
    assert len(sidecar["reference_images"]) == 2 and sidecar["region"] is None


def test_google_region_uses_edit_image_region(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    provider = _google(_png(shade=180))
    retouch_frame(provider, f2, "add a glove", neighbors=[f1, f3], region=(8, 8, 16, 16))
    args, kwargs = provider.edit_image_region.call_args
    assert args[0] == f2.read_bytes() and args[1] == (8, 8, 16, 16) and "add a glove" in args[2]
    provider.edit_image.assert_not_called()


def test_openai_region_builds_alpha_mask(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    provider = _openai(_png(shade=180))
    model = next(m for m, c in MODEL_CAPS.items() if c["supports_mask"] and c["supports_multi_reference"])
    retouch_frame(provider, f2, "add a glove", neighbors=[f1], region=(8, 8, 16, 16), model=model)
    args, kwargs = provider.edit_image.call_args
    assert kwargs["model"] == model and kwargs["n"] == 1 and "size" in kwargs
    mask = Image.open(BytesIO(kwargs["mask"]))
    assert mask.size == (32, 32) and mask.mode == "RGBA"
    assert mask.getpixel((16, 16))[3] == 0            # inside region: editable
    assert mask.getpixel((0, 0))[3] == 255            # far outside: protected
    assert args[0] == [f2.read_bytes(), f1.read_bytes()]


def test_openai_without_region_sends_no_mask(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    provider = _openai(_png(shade=180))
    retouch_frame(provider, f2, "brighten the cape", neighbors=[])
    assert provider.edit_image.call_args.kwargs["mask"] is None


def test_build_region_mask_feathers_edge():
    mask = Image.open(BytesIO(build_region_mask((32, 32), (8, 8, 16, 16), feather=4)))
    assert mask.getpixel((7, 16))[3] < 255 and mask.getpixel((7, 16))[3] > 0
    assert mask.getpixel((2, 16))[3] == 255


def test_result_is_repadded_proportionally_when_size_differs(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    provider = _google(_png(w=64, h=32, shade=180))   # 2:1 reply for a 1:1 frame
    out = retouch_frame(provider, f2, "x")
    img = Image.open(out)
    assert img.size == (32, 32)
    alpha = np.asarray(img.getchannel("A"))
    assert alpha[0, 16] == 0 and alpha[31, 16] == 0 and alpha[16, 16] == 255   # letterboxed, not stretched


def test_fit_to_size_upscales_small_result():
    small = Image.new("RGBA", (16, 8), (1, 2, 3, 255))
    fitted = fit_to_size(small, (64, 64))
    assert fitted.size == (64, 64)
    assert fitted.getpixel((32, 32))[3] == 255 and fitted.getpixel((32, 2))[3] == 0


def test_validate_retouch_detects_unchanged():
    a = Image.open(BytesIO(_png(shade=100)))
    assert validate_retouch(a, a.copy(), None)[0] is False
    assert validate_retouch(a, Image.open(BytesIO(_png(shade=180))), (0, 0, 8, 8))[0] is True


def test_unchanged_result_retries_then_raises(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    provider = _google(_png(shade=100))               # identical to the source
    with pytest.raises(ProviderError):
        retouch_frame(provider, f2, "x", attempts=2)
    assert provider.edit_image.call_count == 2
    assert not (tmp_path / "0002.r1.png").exists()


def test_never_overwrites_existing_output(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    (tmp_path / "custom.png").write_bytes(_png())
    with pytest.raises(FileExistsError):
        retouch_frame(_google(_png(shade=180)), f2, "x", tmp_path / "custom.png")


def test_logs_request_and_response(tmp_path):
    f1, f2, f3 = _frames(tmp_path)
    lines = []
    retouch_frame(_google(_png(shade=180)), f2, "x", log=lines.append)
    assert any("request" in l and "prompt:" in l for l in lines)
    assert any("response" in l for l in lines) and any("validation" in l for l in lines)
```

- [ ] **Step 2: Run the test to see it fail**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_retouch.py -v` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement the module**

Create `core/sprite/generation/retouch.py`:

```python
"""AI retouch of one sprite frame (Gemini or gpt-image) — non-destructive.

The output is a new file ``NNNN.r<k>.png`` beside the original; the original
is never overwritten, so undo is a pointer swap (design §1.4).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from core.sprite.generation.errors import ProviderError
from core.sprite.generation.image_route import (
    call_provider, default_openai_edit_model, first_image, log_request, log_response,
    openai_edit_size, provider_kind,
)
from core.sprite.models import Rect, Size
from core.utils import write_image_sidecar

logger = logging.getLogger(__name__)
LogFn = Callable[[str], None]

_RETOUCH_SUFFIX = re.compile(r"\.r(\d+)$")
MIN_CHANGE_MEAN_DIFF = 1.0     # same threshold as ai_face_editor._validate_edit


def next_retouch_path(frame: Path) -> Path:
    """``0003.png`` -> ``0003.r1.png`` (or the next free k); a retouch of a retouch keeps the base name."""
    frame = Path(frame)
    base = _RETOUCH_SUFFIX.sub("", frame.stem)
    k = 1
    while True:
        candidate = frame.with_name(f"{base}.r{k}{frame.suffix}")
        if not candidate.exists():
            return candidate
        k += 1


def build_region_mask(size: Size, region: Rect, feather: int = 5) -> bytes:
    """OpenAI edit mask: alpha 0 inside ``region`` (editable), 255 outside, feathered edge."""
    w, h = int(size[0]), int(size[1])
    x, y, rw, rh = region
    ys, xs = np.mgrid[0:h, 0:w]
    dx = np.maximum(0, np.maximum(x - xs, xs - (x + rw - 1)))
    dy = np.maximum(0, np.maximum(y - ys, ys - (y + rh - 1)))
    dist = np.sqrt(dx.astype(np.float32) ** 2 + dy.astype(np.float32) ** 2)
    if feather > 0:
        alpha = np.clip(dist / float(feather), 0.0, 1.0) * 255.0
    else:
        alpha = (dist > 0).astype(np.float32) * 255.0
    mask = np.zeros((h, w, 4), dtype=np.uint8)
    mask[..., 3] = alpha.astype(np.uint8)
    buf = BytesIO()
    Image.fromarray(mask, "RGBA").save(buf, "PNG")
    return buf.getvalue()


def fit_to_size(image: Image.Image, size: Size) -> Image.Image:
    """Return ``image`` at exactly ``size``: scaled proportionally and padded on a transparent canvas."""
    target = (int(size[0]), int(size[1]))
    image = image.convert("RGBA")
    if image.size == target:
        return image
    scale = min(target[0] / image.width, target[1] / image.height)
    new_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    resized = image.resize(new_size, Image.LANCZOS)
    canvas = Image.new("RGBA", target, (0, 0, 0, 0))
    canvas.paste(resized, ((target[0] - new_size[0]) // 2, (target[1] - new_size[1]) // 2))
    return canvas


def validate_retouch(original: Image.Image, edited: Image.Image, region: Optional[Rect]) -> Tuple[bool, str]:
    """The edited area must differ from the original (pattern: ai_face_editor._validate_edit)."""
    if region is None:
        box = (0, 0, original.width, original.height)
    else:
        x, y, w, h = region
        box = (x, y, x + w, y + h)
    a = np.asarray(original.convert("RGB").crop(box), dtype=np.float32)
    b = np.asarray(edited.convert("RGB").crop(box), dtype=np.float32)
    if a.shape != b.shape:
        return False, f"size mismatch {a.shape} vs {b.shape}"
    mean = float(np.mean(np.abs(a - b)))
    if mean < MIN_CHANGE_MEAN_DIFF:
        return False, f"edit region unchanged (mean diff {mean:.2f})"
    return True, f"mean diff {mean:.2f}"


def retouch_prompt(instruction: str, *, neighbors: int) -> str:
    parts = [instruction.strip().rstrip(".") + "."]
    if neighbors:
        parts.append(f"The other {neighbors} image(s) are the neighboring animation frames; "
                     "keep the character identical to them.")
    parts.append("Keep the same background color, framing, scale, and character position. Do not change anything else.")
    return " ".join(parts)


def retouch_frame(
    provider,
    frame: Path,
    instruction: str,
    out_png: Optional[Path] = None,
    *,
    neighbors: Sequence[Path] = (),
    region: Optional[Rect] = None,
    model: Optional[str] = None,
    log: LogFn = logger.info,
    attempts: int = 2,
) -> Path:
    """Retouch one frame; write ``NNNN.r<k>.png`` beside it (never overwrite) and return that path."""
    frame = Path(frame)
    if not frame.exists():
        raise FileNotFoundError(frame)
    if not instruction.strip():
        raise ValueError("instruction is empty")
    out = Path(out_png) if out_png else next_retouch_path(frame)
    if out.exists():
        raise FileExistsError(f"retouch output exists; never overwrite: {out}")
    kind = provider_kind(provider)
    model = model or (default_openai_edit_model() if kind == "openai" else provider.get_default_model())
    with Image.open(frame) as src:
        original = src.convert("RGBA")
    size: Size = original.size
    frame_bytes = frame.read_bytes()
    neighbor_paths = [Path(n) for n in neighbors if Path(n).exists()]
    neighbor_bytes = [p.read_bytes() for p in neighbor_paths]
    prompt = retouch_prompt(instruction, neighbors=len(neighbor_paths))
    params: Dict = {"region": list(region) if region else None, "neighbors": [str(p) for p in neighbor_paths]}
    last_reason = ""
    for attempt in range(1, attempts + 1):
        what = f"retouch {frame.name} attempt {attempt}/{attempts}"
        if kind == "google":
            log_request(log, what=what, provider=kind, model=model, prompt=prompt, params=params)
            if region is not None:
                texts, images = call_provider(provider, "edit_image_region", frame_bytes, tuple(region), prompt,
                                              what=what, model=model)
            else:
                texts, images = call_provider(provider, "edit_image", [frame_bytes, *neighbor_bytes], prompt,
                                              what=what, model=model)
        else:
            size_str = openai_edit_size(model, size)
            params["size"] = size_str
            mask = build_region_mask(size, region) if region is not None else None
            log_request(log, what=what, provider=kind, model=model, prompt=prompt, params=params)
            texts, images = call_provider(provider, "edit_image", [frame_bytes, *neighbor_bytes], prompt,
                                          what=what, model=model, mask=mask, size=size_str, n=1)
        log_response(log, what=what, texts=texts, images=images)
        data = first_image(texts, images, what=what)
        with Image.open(BytesIO(data)) as reply:
            edited = fit_to_size(reply, size)
        ok, last_reason = validate_retouch(original, edited, region)
        log(f"[retouch] validation: {last_reason}")
        if ok:
            out.parent.mkdir(parents=True, exist_ok=True)
            edited.save(out, "PNG")
            write_image_sidecar(out, {
                "prompt": prompt, "provider": kind, "model": model, "timestamp": datetime.now().isoformat(timespec="seconds"),
                "route": "retouch", "source_frame": str(frame), "instruction": instruction,
                "region": list(region) if region else None,
                "reference_images": [str(p) for p in neighbor_paths],
                "mask": "region alpha mask" if (kind == "openai" and region is not None) else None,
                "attempt": attempt,
            })
            log(f"[retouch] saved: {out}")
            return out
        logger.warning("[retouch] %s rejected: %s", what, last_reason)
    message = (f"Retouch produced no visible change after {attempts} attempt(s) ({last_reason}). "
               "Use a more specific instruction or the other provider.")
    logger.error("[retouch] %s", message)
    log(f"[retouch] {message}")
    raise ProviderError(message)
```

- [ ] **Step 4: Run the test to see it pass**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_retouch.py -v` → 12 passed.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/generation/retouch.py tests/sprite/test_retouch.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): non-destructive AI frame retouch (region or whole frame, Gemini/gpt-image)"
```

---

