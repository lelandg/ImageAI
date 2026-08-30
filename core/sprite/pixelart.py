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

from core.sprite import stabilize
from core.sprite.keying import apply_profile_alpha, hex_to_rgb, rgb_to_hex
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
    """Top-left paste position of ``content`` inside ``cell`` for ``anchor``.

    Thin wrapper over ``stabilize.anchor_offset`` (same five anchor names,
    different argument order) so the arithmetic lives in one place.
    """
    if int(content[0]) > int(cell[0]) or int(content[1]) > int(cell[1]):
        raise ValueError(f"content {content} does not fit in cell {cell}")
    return stabilize.anchor_offset(anchor, content, cell)


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


# --- Task 4: shared palette ----------------------------------------------------

def hex_to_palette(palette: Sequence[str]) -> np.ndarray:
    """``["#RRGGBB", ...]`` -> int32 array of shape (P, 3)."""
    if len(palette) == 0:
        return np.zeros((0, 3), dtype=np.int32)
    return np.array([hex_to_rgb(c) for c in palette], dtype=np.int32)


def palette_to_hex(colors: Sequence[Sequence[int]]) -> List[str]:
    """Rows of (r, g, b) -> ``["#RRGGBB", ...]`` (uppercase)."""
    return [rgb_to_hex(c) for c in colors]


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
