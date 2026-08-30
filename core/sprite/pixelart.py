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
