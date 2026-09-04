"""Auto-crop and pad frames into a fixed cell (design section 4.1).

``crop_and_pad`` scales proportionally and never distorts: the crop is
resized with one scale factor for both axes, then placed on a transparent
canvas of the cell size at the requested anchor.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image

from .models import Rect, Size
from .pipeline import CancelToken, ProgressFn, check, no_progress

try:
    from skimage.registration import phase_cross_correlation as _phase_cross_correlation
except ImportError:  # scikit-image absent or broken: OpenCV fallback (design §1.7)
    _phase_cross_correlation = None

logger = logging.getLogger(__name__)

ANCHORS = ("bottom_center", "center", "top_left", "top_center", "bottom_left")
DEJITTER_METHODS = ("phase", "centroid")
MIN_PHASE_RESPONSE = 0.02      # cv2.phaseCorrelate response below this is noise
MAX_SHIFT_FRACTION = 0.25      # never move a frame more than a quarter of its size


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


def fit_size(content: Size, cell: Size, *, allow_upscale: bool = True) -> Size:
    """Largest size with the aspect of ``content`` that fits inside ``cell``.

    ``allow_upscale=False`` caps the scale at 1.0, so content already
    smaller than ``cell`` keeps its native size instead of being enlarged
    (``OutputProfile.upscale_small``, M1).
    """
    w, h = content
    cw, ch = cell
    if w < 1 or h < 1:
        return (0, 0)
    scale = min(cw / w, ch / h)
    if not allow_upscale:
        scale = min(scale, 1.0)
    return (max(1, int(round(w * scale))), max(1, int(round(h * scale))))


RESAMPLE_METHODS = {
    "lanczos": Image.Resampling.LANCZOS,
    "nearest": Image.Resampling.NEAREST,
    "bilinear": Image.Resampling.BILINEAR,
    "bicubic": Image.Resampling.BICUBIC,
}


def _resample_filter(method: str) -> Image.Resampling:
    return RESAMPLE_METHODS.get((method or "lanczos").lower(), Image.Resampling.LANCZOS)


def crop_and_pad(frames: Sequence[Path], out_dir: Path, bbox: Rect, cell: Size,
                 anchor: str = "bottom_center", pad_px: int = 0,
                 *, upscale_small: bool = True, resample_method: str = "lanczos",
                 stage: str = "stabilize", progress: ProgressFn = no_progress,
                 token: Optional[CancelToken] = None) -> List[Path]:
    """Crop every frame to ``bbox`` (+pad), scale proportionally into ``cell``, anchor.

    Output files keep their input names. Frames are never distorted: one
    scale factor for both axes. A crop larger than ``cell`` always shrinks;
    a crop smaller than ``cell`` only grows when ``upscale_small`` is true,
    using ``resample_method`` (``OutputProfile.upscale_small``/
    ``upscale_method``, M1) -- otherwise it keeps its native size, anchored
    inside the cell. ``stage`` names the caller's stage in progress events
    -- ``hd_runner`` passes ``"hd"`` so its per-frame progress does not
    report as ``"stabilize"``.
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
    resample = _resample_filter(resample_method)
    written: List[Path] = []
    total = len(frames)
    for index, path in enumerate(frames, start=1):
        check(token)
        with Image.open(path) as im:
            rgba = im.convert("RGBA")
        # Expand by pad on a transparent canvas so the crop never reads outside the image.
        crop = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
        crop.paste(rgba.crop((x, y, x + w, y + h)), (pad, pad))
        target = fit_size(crop.size, cell, allow_upscale=upscale_small)
        if target != crop.size:
            crop = crop.resize(target, resample)
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        canvas.paste(crop, anchor_offset(anchor, crop.size, cell))
        dest = out_dir / path.name
        canvas.save(dest, format="PNG")
        written.append(dest)
        progress(stage, index, total, f"{stage}: {path.name}")
    return written


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
    -> centroid. ``centroid``: centroid difference only. A mask with no structure
    (empty, or uniformly transparent/opaque -- zero variance) also falls back to
    centroid: skimage's sub-pixel refinement returns a spurious ~0.7 px shift on
    two identical constant masks instead of (0, 0) (I3).
    """
    if method not in DEJITTER_METHODS:
        raise ValueError(f"Unknown dejitter method {method!r}; choose one of {DEJITTER_METHODS}")
    ref = np.asarray(ref_alpha, dtype=np.float32)
    mov = np.asarray(mov_alpha, dtype=np.float32)
    if method == "centroid" or ref.std() < 1e-6 or mov.std() < 1e-6:
        return _centroid_shift(ref, mov)
    if _phase_cross_correlation is not None:
        shift, _error, _phase = _phase_cross_correlation(ref, mov, upsample_factor=10)
        return float(shift[0]), float(shift[1])
    (dx, dy), response = cv2.phaseCorrelate(ref, mov)
    if response < MIN_PHASE_RESPONSE:
        logger.debug("phaseCorrelate response %.3f too weak; using centroid", response)
        return _centroid_shift(ref, mov)
    return -float(dy), -float(dx)


def limit_shift_to_canvas(alpha: np.ndarray, dy: float, dx: float) -> Tuple[float, float]:
    """Reduce ``(dy, dx)`` so the alpha bbox of ``alpha`` stays inside the canvas.

    The stabilize crop is the union alpha bbox with ``pad_px`` 0 by default, so
    subject pixels sit on the canvas edge. A registration shift that pushes
    them off the canvas destroys the frame; on pose animation the estimate is
    wrong anyway (rock_3 frame 7 lost 20 % of the character). Each axis is
    clamped independently to the room left between the bbox and the edge.
    """
    a = np.asarray(alpha)
    rows = np.flatnonzero(a.any(axis=1))
    cols = np.flatnonzero(a.any(axis=0))
    if rows.size == 0 or cols.size == 0:
        return float(dy), float(dx)
    h, w = a.shape[:2]
    top, bottom = int(rows[0]), int(rows[-1]) + 1
    left, right = int(cols[0]), int(cols[-1]) + 1
    ldy = max(-float(top), min(float(h - bottom), float(dy)))
    ldx = max(-float(left), min(float(w - right), float(dx)))
    return ldy, ldx


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

    Every frame registers against frame 0 (never its predecessor), so only
    frame 0's array needs to survive past its own iteration; frames are read
    and written one at a time rather than all loaded up front (I2). ``out_dir``
    may be the input directory: each frame is read before its own output file
    is written, and a frame's own file is never touched before that frame has
    been read, so no frame is overwritten before use. Shifts are clamped to
    MAX_SHIFT_FRACTION of the frame size.
    """
    if method not in DEJITTER_METHODS:
        raise ValueError(f"Unknown dejitter method {method!r}; choose one of {DEJITTER_METHODS}")
    frames = [Path(p) for p in frames]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs: List[Path] = []
    if not frames:
        return outputs
    total = len(frames)

    check(token)
    first_path = frames[0]
    first_rgba = np.asarray(Image.open(first_path).convert("RGBA"))
    ref_alpha = first_rgba[:, :, 3].astype(np.float32) / 255.0
    h, w = ref_alpha.shape
    max_dy, max_dx = MAX_SHIFT_FRACTION * h, MAX_SHIFT_FRACTION * w
    dst0 = out_dir / first_path.name
    Image.fromarray(first_rgba).save(dst0)
    outputs.append(dst0)
    progress("stabilize", 1, total, f"dejitter {first_path.name}")

    for index, path in enumerate(frames[1:], start=2):
        check(token)
        rgba = np.asarray(Image.open(path).convert("RGBA"))
        mov_alpha = rgba[:, :, 3].astype(np.float32) / 255.0
        dy, dx = estimate_shift(ref_alpha, mov_alpha, method)
        cdy, cdx = max(-max_dy, min(max_dy, dy)), max(-max_dx, min(max_dx, dx))
        if (cdy, cdx) != (dy, dx):
            logger.warning("dejitter %s: clamped shift (%.2f, %.2f) to (%.2f, %.2f)",
                           path.name, dy, dx, cdy, cdx)
        fdy, fdx = limit_shift_to_canvas(mov_alpha, cdy, cdx)
        if (fdy, fdx) != (cdy, cdx):
            logger.warning("dejitter %s: shift (%.2f, %.2f) would push the subject off the "
                           "canvas; limited to (%.2f, %.2f)", path.name, cdy, cdx, fdy, fdx)
        cdy, cdx = fdy, fdx
        dst = out_dir / path.name
        Image.fromarray(translate_rgba(rgba, cdy, cdx)).save(dst)
        outputs.append(dst)
        progress("stabilize", index, total, f"dejitter {path.name}")
    return outputs
