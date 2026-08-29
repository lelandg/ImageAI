"""Auto-crop and pad frames into a fixed cell (design section 4.1).

``crop_and_pad`` scales proportionally and never distorts: the crop is
resized with one scale factor for both axes, then placed on a transparent
canvas of the cell size at the requested anchor.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from .models import Rect, Size
from .pipeline import CancelToken, ProgressFn, check, no_progress

logger = logging.getLogger(__name__)

ANCHORS = ("bottom_center", "center", "top_left", "top_center", "bottom_left")


def has_transparency(frame: Path) -> bool:
    with Image.open(frame) as im:
        if im.mode not in ("RGBA", "LA", "P"):
            return False
        alpha = np.asarray(im.convert("RGBA"))[..., 3]
    return bool(np.any(alpha < 255))


def union_alpha_bbox(frames: Sequence[Path]) -> Rect:
    """Smallest rect covering every non-transparent pixel of every frame."""
    x0 = y0 = None
    x1 = y1 = None
    size: Optional[Tuple[int, int]] = None
    for path in frames:
        with Image.open(path) as im:
            size = size or im.size
            box = im.convert("RGBA").getchannel("A").getbbox()
        if box is None:
            continue
        x0 = box[0] if x0 is None else min(x0, box[0])
        y0 = box[1] if y0 is None else min(y0, box[1])
        x1 = box[2] if x1 is None else max(x1, box[2])
        y1 = box[3] if y1 is None else max(y1, box[3])
    if x0 is None or size is None:
        w, h = size or (0, 0)
        return (0, 0, w, h)
    return (x0, y0, x1 - x0, y1 - y0)


def solid_border_bbox(frames: Sequence[Path], variance: float = 5.0) -> Rect:
    """Union bbox of pixels that differ from each frame's top-left color.

    Pre-key path: the frames still carry the chroma plate, so alpha is
    useless. ``variance`` is the per-channel tolerance (0..255).
    """
    x0 = y0 = None
    x1 = y1 = None
    size: Optional[Tuple[int, int]] = None
    for path in frames:
        with Image.open(path) as im:
            rgb = np.asarray(im.convert("RGB"), dtype=np.int16)
        size = size or (rgb.shape[1], rgb.shape[0])
        diff = np.abs(rgb - rgb[0, 0]).max(axis=2)
        ys, xs = np.nonzero(diff > variance)
        if xs.size == 0:
            continue
        bx0, bx1 = int(xs.min()), int(xs.max()) + 1
        by0, by1 = int(ys.min()), int(ys.max()) + 1
        x0 = bx0 if x0 is None else min(x0, bx0)
        y0 = by0 if y0 is None else min(y0, by0)
        x1 = bx1 if x1 is None else max(x1, bx1)
        y1 = by1 if y1 is None else max(y1, by1)
    if x0 is None or size is None:
        w, h = size or (0, 0)
        return (0, 0, w, h)
    return (x0, y0, x1 - x0, y1 - y0)


def anchor_offset(anchor: str, content: Size, cell: Size) -> Tuple[int, int]:
    """Top-left position of ``content`` inside ``cell`` for an anchor name."""
    if anchor not in ANCHORS:
        raise ValueError(f"Unknown anchor {anchor!r}; use one of {ANCHORS}")
    cw, ch = cell
    w, h = content
    vertical, _, horizontal = anchor.partition("_")
    if anchor == "center":
        vertical, horizontal = "center", "center"
    x = {"left": 0, "center": (cw - w) // 2}[horizontal]
    y = {"top": 0, "center": (ch - h) // 2, "bottom": ch - h}[vertical]
    return (x, y)


def fit_size(content: Size, cell: Size) -> Size:
    """Largest size with the aspect of ``content`` that fits inside ``cell``."""
    w, h = content
    cw, ch = cell
    if w < 1 or h < 1:
        return (0, 0)
    scale = min(cw / w, ch / h)
    return (max(1, int(round(w * scale))), max(1, int(round(h * scale))))


def crop_and_pad(frames: Sequence[Path], out_dir: Path, bbox: Rect, cell: Size,
                 anchor: str = "bottom_center", pad_px: int = 0,
                 *, progress: ProgressFn = no_progress,
                 token: Optional[CancelToken] = None) -> List[Path]:
    """Crop every frame to ``bbox`` (+pad), scale proportionally into ``cell``, anchor.

    Output files keep their input names. Frames are never distorted; a
    crop larger than the cell shrinks, a smaller one grows, both with
    ``Image.LANCZOS`` and one scale factor for both axes.
    """
    if anchor not in ANCHORS:
        raise ValueError(f"Unknown anchor {anchor!r}; use one of {ANCHORS}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    x, y, w, h = bbox
    pad = max(0, int(pad_px))
    cw, ch = cell
    if cw < 1 or ch < 1:
        raise ValueError(f"cell must be positive, got {cell}")
    written: List[Path] = []
    total = len(frames)
    for index, path in enumerate(frames, start=1):
        check(token)
        with Image.open(path) as im:
            rgba = im.convert("RGBA")
        # Expand by pad on a transparent canvas so the crop never reads outside the image.
        crop = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
        crop.paste(rgba.crop((x, y, x + w, y + h)), (pad, pad))
        target = fit_size(crop.size, cell)
        if target != crop.size:
            crop = crop.resize(target, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        canvas.paste(crop, anchor_offset(anchor, crop.size, cell))
        dest = out_dir / path.name
        canvas.save(dest, format="PNG")
        written.append(dest)
        progress("stabilize", index, total, f"stabilize: {path.name}")
    return written
