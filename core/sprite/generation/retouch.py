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

from core.sprite.generation._common import emit
from core.sprite.generation.errors import ProviderError
from core.sprite.generation.image_route import (
    call_provider, default_openai_edit_model, first_image, log_request, log_response,
    openai_edit_size, provider_kind,
)
from core.sprite.models import Rect, Size
from core.sprite.pipeline import CancelToken
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
    Image.fromarray(mask).save(buf, "PNG")
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
    token: Optional[CancelToken] = None,
) -> Path:
    """Retouch one frame; write ``NNNN.r<k>.png`` beside it (never overwrite) and return that path.

    ``token`` is checked immediately before and immediately after each attempt's provider call
    (same convention as ``make_chroma_plate``/``generate_action_cards``), so a Cancel request
    during a slow image call is honored as soon as that call returns instead of after the whole
    retry loop.

    The Gemini region path sends one image, because ``edit_image_region`` accepts one image.
    On that path ``neighbors`` are dropped, and the prompt, the request log and the sidecar all
    report zero neighbours. Every other path sends the neighbours as extra references.
    """
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
    # GoogleProvider.edit_image_region takes exactly one image, so the Gemini region path
    # cannot carry the neighbours. The prompt, the request params and the sidecar record
    # what the provider really receives, because core/utils.py defines reference_images as
    # the inputs to the edit.
    sent_neighbors: List[Path] = [] if (kind == "google" and region is not None) else neighbor_paths
    neighbor_bytes = [p.read_bytes() for p in sent_neighbors]
    prompt = retouch_prompt(instruction, neighbors=len(sent_neighbors))
    params: Dict = {"region": list(region) if region else None, "neighbors": [str(p) for p in sent_neighbors]}
    last_reason = ""
    for attempt in range(1, attempts + 1):
        if token is not None:
            token.raise_if_cancelled()
        what = f"retouch {frame.name} attempt {attempt}/{attempts}"
        if kind == "google":
            log_request(log, what=what, provider=kind, model=model, prompt=prompt, params=params, logger=logger)
            if region is not None:
                texts, images = call_provider(provider, "edit_image_region", frame_bytes, tuple(region), prompt,
                                              what=what, log=log, logger=logger, model=model)
            else:
                texts, images = call_provider(provider, "edit_image", [frame_bytes, *neighbor_bytes], prompt,
                                              what=what, log=log, logger=logger, model=model)
        else:
            size_str = openai_edit_size(model, size)
            params["size"] = size_str
            mask = build_region_mask(size, region) if region is not None else None
            log_request(log, what=what, provider=kind, model=model, prompt=prompt, params=params, logger=logger)
            texts, images = call_provider(provider, "edit_image", [frame_bytes, *neighbor_bytes], prompt,
                                          what=what, log=log, logger=logger, model=model, mask=mask,
                                          size=size_str, n=1)
        if token is not None:
            token.raise_if_cancelled()
        log_response(log, what=what, texts=texts, images=images, logger=logger)
        data = first_image(texts, images, what=what)
        with Image.open(BytesIO(data)) as reply:
            edited = fit_to_size(reply, size)
        ok, last_reason = validate_retouch(original, edited, region)
        emit(logger, log, f"[retouch] validation: {last_reason}")
        if ok:
            out.parent.mkdir(parents=True, exist_ok=True)
            edited.save(out, "PNG")
            write_image_sidecar(out, {
                "prompt": prompt, "provider": kind, "model": model, "timestamp": datetime.now().isoformat(timespec="seconds"),
                "route": "retouch", "source_frame": str(frame), "instruction": instruction,
                "region": list(region) if region else None,
                "reference_images": [str(p) for p in sent_neighbors],
                "mask": "region alpha mask" if (kind == "openai" and region is not None) else None,
                "attempt": attempt,
            })
            emit(logger, log, f"[retouch] saved: {out}")
            return out
        emit(logger, log, f"[retouch] {what} rejected: {last_reason}", level="warning")
    message = (f"Retouch produced no visible change after {attempts} attempt(s) ({last_reason}). "
               "Use a more specific instruction or the other provider.")
    emit(logger, log, f"[retouch] {message}", level="error")
    raise ProviderError(message)
