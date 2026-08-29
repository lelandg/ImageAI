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
