### Task 6: Image route — sheet generation and slicing

**Files:**
- Create: `core/sprite/generation/image_route.py`
- Test: `tests/sprite/test_image_route.py`

**Interfaces:**
- Consumes: `GoogleProvider.edit_image(image, prompt, model=None, **kwargs)` (`providers/google.py:1832-1905`; honors `aspect_ratio=` via `image_config`); `OpenAIProvider.edit_image(image, prompt, model=None, mask=None, size="1024x1024", n=1, **kwargs)` (`providers/openai.py:821-940`); `MODEL_CAPS` (`providers/openai.py:46-168`); `validate_custom_size`, `parse_size_string` (`core/image_size.py:12-69`); `inject_chroma` (sub-project 2); `guess_grid`, `slice_sheet` (sub-project 1); `ProviderError`, `classify_provider_error` (sub-project 2); `CancelToken`; `write_image_sidecar`.
- Produces: `provider_kind(provider) -> str`; `call_provider(provider, method, *args, what, **kwargs)`; `first_image(texts, images, *, what) -> bytes`; `save_png(data, out_png) -> Path`; `log_request(...)`, `log_response(...)`; `openai_sheet_size(model) -> str`; `sheet_prompt(action, frames, plate_color) -> str`; `generate_sheet(provider, character, action, out_png, *, frames, plate_color, model=None, log=logger.info, token=None) -> Path`; `slice_generated_sheet(sheet_png, out_dir, frames, plate_color, *, log=logger.info) -> List[Path]`; re-export `generate_pose_instructions`.

- [ ] **Step 1: Write the failing test**

Create `tests/sprite/test_image_route.py`:

```python
# tests/sprite/test_image_route.py
import json
import re
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image

from core.image_size import parse_size_string
from core.sprite.generation import image_route
from core.sprite.generation.errors import ProviderError, SpriteGenerationError
from core.sprite.generation.image_route import (
    generate_sheet, openai_sheet_size, sheet_prompt, slice_generated_sheet,
)
from core.sprite.generation.prompts import FORBIDDEN_WORDS
from core.sprite.pipeline import CancelToken, Cancelled
from core.sprite.project import ActionCard
from core.sprite.slicing import GridGuess
from providers.google import GoogleProvider
from providers.openai import MODEL_CAPS, OpenAIProvider


def png_bytes(w=48, h=16, color=(0, 255, 0, 255), squares=3) -> bytes:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[...] = color
    cell = w // squares
    for i in range(squares):
        x0 = i * cell + 3
        arr[4:12, x0:x0 + 8] = (200, 40 + 40 * i, 60, 255)
    buf = BytesIO()
    Image.fromarray(arr, "RGBA").save(buf, "PNG")
    return buf.getvalue()


def _action() -> ActionCard:
    return ActionCard(id="a1", name="walk", prompt="walks briskly to the right", duration_s=4,
                      loop=True, target_frames=3, fps=12)


def _character(tmp_path: Path) -> Path:
    p = tmp_path / "character.png"
    p.write_bytes(png_bytes(w=16, h=16, squares=1))
    return p


def _google(reply=None):
    provider = MagicMock(spec=GoogleProvider)
    provider.get_default_model.return_value = "default-google-image-model"
    provider.edit_image.return_value = ([], [reply or png_bytes()])
    return provider


def _openai(reply=None):
    provider = MagicMock(spec=OpenAIProvider)
    provider.get_default_model.return_value = next(m for m, c in MODEL_CAPS.items() if c["supports_custom_size"])
    provider.edit_image.return_value = ([], [reply or png_bytes()])
    return provider


def test_sheet_prompt_is_clean():
    text = sheet_prompt(_action(), 6, "#00FF00")
    lowered = text.lower()
    assert "horizontal" in lowered and "6" in text and "#00FF00" in text
    assert not re.search(r"\d+\s*[x×]\s*\d+", text), "no pixel dimensions"
    assert not re.search(r"\b\d+:\d+\b", text), "no aspect ratio"
    for word in FORBIDDEN_WORDS:
        assert word not in lowered
    assert "seamless loop" in lowered


def test_generate_sheet_google_uses_aspect_kwarg_not_prompt(tmp_path):
    provider = _google()
    out = generate_sheet(provider, _character(tmp_path), _action(), tmp_path / "sheet.png",
                         frames=3, plate_color="#00FF00")
    assert out.exists()
    args, kwargs = provider.edit_image.call_args
    assert kwargs["aspect_ratio"] == image_route.SHEET_ASPECT_GEMINI
    assert kwargs["model"] == "default-google-image-model"
    assert image_route.SHEET_ASPECT_GEMINI not in args[1]
    sidecar = json.loads((tmp_path / "sheet.png.json").read_text(encoding="utf-8"))
    assert sidecar["route"] == "image_sheet" and sidecar["frames"] == 3 and sidecar["provider"] == "google"
    assert Image.open(out).mode == "RGBA"


def test_generate_sheet_openai_uses_custom_3to1_size(tmp_path):
    provider = _openai()
    model = provider.get_default_model()
    generate_sheet(provider, _character(tmp_path), _action(), tmp_path / "sheet.png",
                   frames=4, plate_color="#00FF00", model=model)
    args, kwargs = provider.edit_image.call_args
    w, h = parse_size_string(kwargs["size"])
    assert w / h == 3.0 and w % 16 == 0 and h % 16 == 0
    assert kwargs["model"] == model and kwargs["n"] == 1
    assert isinstance(args[0], list) and Path(args[0][0]).name == "character.png"


def test_openai_sheet_size_without_custom_size_picks_widest_preset():
    model = next(m for m, c in MODEL_CAPS.items() if not c["supports_custom_size"] and c["supports_multi_reference"])
    size = openai_sheet_size(model)
    widths = {parse_size_string(s) for s in MODEL_CAPS[model]["valid_sizes"] if s != "auto"}
    assert parse_size_string(size) == max(widths, key=lambda wh: wh[0] / wh[1])


def test_generate_sheet_no_image_raises_provider_error(tmp_path):
    provider = _google()
    provider.edit_image.return_value = (["I cannot draw that."], [])
    with pytest.raises(ProviderError) as info:
        generate_sheet(provider, _character(tmp_path), _action(), tmp_path / "s.png", frames=3, plate_color="#00FF00")
    assert "cannot draw" in str(info.value)


def test_generate_sheet_wraps_provider_exception(tmp_path):
    provider = _google()
    provider.edit_image.side_effect = RuntimeError("Google image editing failed: 429 RESOURCE_EXHAUSTED")
    with pytest.raises(SpriteGenerationError):
        generate_sheet(provider, _character(tmp_path), _action(), tmp_path / "s.png", frames=3, plate_color="#00FF00")


def test_generate_sheet_logs_request_and_response(tmp_path):
    lines = []
    generate_sheet(_google(), _character(tmp_path), _action(), tmp_path / "s.png",
                   frames=3, plate_color="#00FF00", log=lines.append)
    assert any("request" in l and "prompt:" in l for l in lines)
    assert any("response" in l and "1 image" in l for l in lines)


def test_generate_sheet_honors_cancel_token(tmp_path):
    token = CancelToken()
    token.cancel()
    provider = _google()
    with pytest.raises(Cancelled):
        generate_sheet(provider, _character(tmp_path), _action(), tmp_path / "s.png",
                       frames=3, plate_color="#00FF00", token=token)
    provider.edit_image.assert_not_called()


def test_generate_sheet_rejects_fewer_than_two_frames(tmp_path):
    with pytest.raises(ValueError):
        generate_sheet(_google(), _character(tmp_path), _action(), tmp_path / "s.png", frames=1, plate_color="#00FF00")


def test_slice_uses_guess_when_confident(tmp_path, monkeypatch):
    sheet = tmp_path / "sheet.png"
    sheet.write_bytes(png_bytes(w=48, h=16, squares=3))
    monkeypatch.setattr(image_route, "guess_grid", lambda img, key_color=None: GridGuess(columns=3, rows=1, cell=(16, 16), confidence=0.95))
    frames = slice_generated_sheet(sheet, tmp_path / "frames", 3, "#00FF00")
    assert [p.name for p in frames] == ["0001.png", "0002.png", "0003.png"]
    assert all(Image.open(p).size == (16, 16) for p in frames)
    assert (tmp_path / "frames" / "0001.png.json").exists()


def test_slice_falls_back_to_one_row_when_guess_disagrees(tmp_path, monkeypatch):
    sheet = tmp_path / "sheet.png"
    sheet.write_bytes(png_bytes(w=48, h=16, squares=3))
    monkeypatch.setattr(image_route, "guess_grid", lambda img, key_color=None: GridGuess(columns=2, rows=2, cell=(24, 8), confidence=0.9))
    logged = []
    frames = slice_generated_sheet(sheet, tmp_path / "frames", 3, "#00FF00", log=logged.append)
    assert len(frames) == 3 and Image.open(frames[0]).size == (16, 16)
    assert any("rejected" in l for l in logged)
```

- [ ] **Step 2: Run the test to see it fail**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_image_route.py -v` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement the module (sheet half)**

Create `core/sprite/generation/image_route.py`:

```python
"""Route B — image-model sprite generation: one horizontal sheet, or an edit-chain.

Both entry points take an already-built provider (GoogleProvider or
OpenAIProvider), write PNGs with JSON sidecars, log every request and
response in full, and raise ``SpriteGenerationError`` subclasses on failure.
"""
from __future__ import annotations

import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from PIL import Image

from core.sprite.generation.errors import ProviderError, classify_provider_error
from core.sprite.generation.pose_steps import generate_pose_instructions  # noqa: F401 — re-export (design §4.6)
from core.sprite.generation.prompts import inject_chroma
from core.sprite.models import Size
from core.sprite.pipeline import CancelToken
from core.sprite.project import ActionCard
from core.sprite.slicing import guess_grid, slice_sheet
from core.utils import write_image_sidecar

logger = logging.getLogger(__name__)
LogFn = Callable[[str], None]

SHEET_ASPECT_GEMINI = "21:9"      # widest ratio Gemini accepts (AGENTS.md list); kwarg only, never prompt text
SHEET_SIZE_CUSTOM = "3072x1024"   # 3:1 strip for OpenAI models with supports_custom_size
MIN_GRID_CONFIDENCE = 0.6

STEP_PROMPT = (
    "This is the same character. Change only the body pose: {instruction} "
    "Keep the identical character design, art style, scale, and position in the frame."
)


# --------------------------------------------------------------------------- shared helpers

def provider_kind(provider) -> str:
    """'openai' for OpenAIProvider instances, else 'google'."""
    from providers.openai import OpenAIProvider
    return "openai" if isinstance(provider, OpenAIProvider) else "google"


def default_openai_edit_model() -> str:
    """First MODEL_CAPS row that supports multi-reference edits with a mask (capability lookup, no literal)."""
    from providers.openai import MODEL_CAPS
    return next(mid for mid, caps in MODEL_CAPS.items() if caps["supports_multi_reference"] and caps["supports_mask"])


def _timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def first_image(texts: Sequence[str], images: Sequence[bytes], *, what: str) -> bytes:
    if images:
        return images[0]
    detail = " ".join(t.strip() for t in texts if t and t.strip())[:300]
    raise ProviderError(f"{what}: the model returned no image." + (f" Model text: {detail}" if detail else ""))


def save_png(data: bytes, out_png: Path) -> Path:
    """Decode any image bytes the model returned and store them as RGBA PNG."""
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(data)) as img:
        img.convert("RGBA").save(out_png, "PNG")
    return out_png


def log_request(log: LogFn, *, what: str, provider: str, model: Optional[str], prompt: str, params: Dict) -> None:
    message = (f"[image route] {what} request: provider={provider} model={model or 'default'} "
               f"params={params}\nprompt: {prompt}")
    logger.info(message)
    log(message)


def log_response(log: LogFn, *, what: str, texts: Sequence[str], images: Sequence[bytes]) -> None:
    text = " | ".join(t.strip() for t in texts if t and t.strip()) or "(none)"
    message = f"[image route] {what} response: {len(images)} image(s) {[len(b) for b in images]} bytes; text: {text}"
    logger.info(message)
    log(message)


def call_provider(provider, method: str, *args, what: str, **kwargs) -> Tuple[List[str], List[bytes]]:
    """Call ``provider.<method>`` and map any exception to a SpriteGenerationError."""
    try:
        return getattr(provider, method)(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 — classify_provider_error decides the subclass
        logger.error("[image route] %s failed: %s", what, exc)
        raise classify_provider_error(exc) from exc


def openai_sheet_size(model: str) -> str:
    """3:1 custom size when the model allows it, else the widest preset size."""
    from core.image_size import parse_size_string, validate_custom_size
    from providers.openai import MODEL_CAPS
    caps = MODEL_CAPS.get(model) or MODEL_CAPS["gpt-image-1"]
    if caps.get("supports_custom_size"):
        w, h = parse_size_string(SHEET_SIZE_CUSTOM)
        ok, why = validate_custom_size(w, h, caps)
        if ok:
            return SHEET_SIZE_CUSTOM
        logger.warning("custom sheet size %s rejected for %s (%s); using preset sizes", SHEET_SIZE_CUSTOM, model, why)
    presets = [s for s in caps["valid_sizes"] if s != "auto"]
    return max(presets, key=lambda s: (lambda wh: wh[0] / wh[1])(parse_size_string(s)))


def openai_edit_size(model: str, size: Size) -> str:
    """Closest legal edit size for a source of ``size``; custom size when allowed and in range."""
    from core.image_size import parse_size_string, validate_custom_size
    from providers.openai import MODEL_CAPS
    caps = MODEL_CAPS.get(model) or MODEL_CAPS["gpt-image-1"]
    w, h = int(size[0]), int(size[1])
    if caps.get("supports_custom_size"):
        multiple = int(caps.get("custom_size_edge_multiple", 16))
        cw, ch = max(multiple, round(w / multiple) * multiple), max(multiple, round(h / multiple) * multiple)
        ok, _why = validate_custom_size(cw, ch, caps)
        if ok:
            return f"{cw}x{ch}"
    presets = [s for s in caps["valid_sizes"] if s != "auto"]
    target = w / h

    def score(s: str) -> float:
        pw, ph = parse_size_string(s)
        return abs(pw / ph - target)

    return min(presets, key=score)


# --------------------------------------------------------------------------- sheet route

def sheet_prompt(action: ActionCard, frames: int, plate_color: str) -> str:
    """Prompt for one horizontal strip; chroma suffix and loop hint come from inject_chroma."""
    label = action.name.replace("_", " ")
    base = (
        f"A {frames}-frame {label} animation of this exact character as one horizontal sprite sheet: "
        f"{frames} equal cells in a single row from left to right, one key pose per cell, in play order. "
        "Same character, same art style, same scale, and the same position inside every cell. "
        "No labels, no numbers, no cell borders, no text. "
        f"{action.prompt.strip()}"
    )
    return inject_chroma(base, plate_color, loop=action.loop)


def generate_sheet(
    provider,
    character: Path,
    action: ActionCard,
    out_png: Path,
    *,
    frames: int,
    plate_color: str,
    model: Optional[str] = None,
    log: LogFn = logger.info,
    token: Optional[CancelToken] = None,
) -> Path:
    """Generate one horizontal sheet from the character image; returns the sheet PNG path."""
    if frames < 2:
        raise ValueError("frames must be >= 2 for a sheet")
    if token is not None:
        token.raise_if_cancelled()
    character = Path(character)
    if not character.exists():
        raise FileNotFoundError(character)
    kind = provider_kind(provider)
    model = model or provider.get_default_model()
    prompt = sheet_prompt(action, frames, plate_color)
    if kind == "openai":
        size = openai_sheet_size(model)
        params: Dict = {"size": size, "n": 1}
        log_request(log, what="sheet", provider=kind, model=model, prompt=prompt, params=params)
        texts, images = call_provider(provider, "edit_image", [character], prompt, what="sheet",
                                      model=model, size=size, n=1)
    else:
        params = {"aspect_ratio": SHEET_ASPECT_GEMINI}
        log_request(log, what="sheet", provider=kind, model=model, prompt=prompt, params=params)
        texts, images = call_provider(provider, "edit_image", character, prompt, what="sheet",
                                      model=model, aspect_ratio=SHEET_ASPECT_GEMINI)
    log_response(log, what="sheet", texts=texts, images=images)
    out = save_png(first_image(texts, images, what="sheet"), out_png)
    write_image_sidecar(out, {
        "prompt": prompt, "provider": kind, "model": model, "timestamp": _timestamp(),
        "route": "image_sheet", "action": action.name, "action_id": action.id,
        "frames": frames, "plate_color": plate_color, "params": params,
        "reference_images": [str(character)],
    })
    log(f"[image route] sheet saved: {out}")
    return out


def slice_generated_sheet(
    sheet_png: Path,
    out_dir: Path,
    frames: int,
    plate_color: str,
    *,
    log: LogFn = logger.info,
) -> List[Path]:
    """Cut a generated sheet into ``frames`` PNGs (guess the grid; fall back to one row)."""
    sheet_png = Path(sheet_png)
    with Image.open(sheet_png) as img:
        guess = guess_grid(img.convert("RGBA"), key_color=plate_color)
    columns, rows = frames, 1
    if guess.confidence >= MIN_GRID_CONFIDENCE and guess.columns * guess.rows == frames:
        columns, rows = guess.columns, guess.rows
        log(f"[image route] grid detected: {columns}x{rows} (confidence {guess.confidence:.2f})")
    else:
        log(f"[image route] grid guess {guess.columns}x{guess.rows} (confidence {guess.confidence:.2f}) "
            f"rejected; slicing {frames}x1")
    paths = list(slice_sheet(sheet_png, Path(out_dir), columns, rows))
    for index, path in enumerate(paths, start=1):
        write_image_sidecar(path, {
            "route": "image_sheet", "source_sheet": str(sheet_png), "cell_index": index,
            "columns": columns, "rows": rows, "timestamp": _timestamp(),
        })
    return paths
```

- [ ] **Step 4: Run the test to see it pass**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_image_route.py -v` → 12 passed.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/generation/image_route.py tests/sprite/test_image_route.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): image route sheet generation (Gemini aspect kwarg, gpt-image 3:1 custom size) and slicing"
```

---

