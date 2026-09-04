"""Character source import: analysis and aspect normalization (design §4.2).

``normalize_source`` pads the character onto a transparent canvas of the
target aspect ratio through ``providers.google.apply_transparent_canvas_fix``.
It never crops and never distorts (AGENTS.md hard rule).
"""
import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from core.sprite.models import Size
from core.utils import write_image_sidecar
from core.sprite.generation._common import now_iso

logger = logging.getLogger(__name__)

# A border pixel counts as "the same color" when its RGB distance to the
# median border color is at most this value (0..441).
_BORDER_DISTANCE = 24.0
# The border is uniform when at least this fraction of ring pixels match.
_UNIFORM_FRACTION = 0.95


@dataclass
class SourceAnalysis:
    has_alpha: bool
    border_color: Optional[str]
    border_uniform: bool
    size: Size


def _border_ring(rgb: np.ndarray, width: int) -> np.ndarray:
    top = rgb[:width, :, :].reshape(-1, 3)
    bottom = rgb[-width:, :, :].reshape(-1, 3)
    left = rgb[width:-width, :width, :].reshape(-1, 3)
    right = rgb[width:-width, -width:, :].reshape(-1, 3)
    return np.concatenate([top, bottom, left, right], axis=0)


def analyze_source(image: Path) -> SourceAnalysis:
    """Report alpha presence, the dominant border color, and the size."""
    with Image.open(image) as img:
        rgba = np.asarray(img.convert("RGBA"))
    height, width = rgba.shape[:2]
    alpha = rgba[..., 3]
    has_alpha = bool(alpha.min() < 255)

    ring_width = max(1, min(width, height) // 50)
    ring = _border_ring(rgba[..., :3].astype(np.float32), ring_width)
    median = np.median(ring, axis=0)
    distance = np.linalg.norm(ring - median, axis=1)
    fraction = float((distance <= _BORDER_DISTANCE).mean()) if ring.size else 0.0
    uniform = fraction >= _UNIFORM_FRACTION
    color = None
    if uniform:
        r, g, b = (int(round(c)) for c in median)
        color = f"#{r:02X}{g:02X}{b:02X}"
    logger.info("analyze_source %s: size=%dx%d has_alpha=%s border_uniform=%s (%.0f%%) color=%s",
                image, width, height, has_alpha, uniform, fraction * 100, color)
    return SourceAnalysis(has_alpha=has_alpha, border_color=color,
                          border_uniform=uniform, size=(width, height))


def normalize_source(image: Path, out_png: Path, aspect_ratio: str = "16:9") -> Path:
    """Pad the character onto a transparent canvas of ``aspect_ratio``.

    Writes an RGBA PNG to ``out_png`` plus a ``.json`` sidecar. Raises
    ``FileNotFoundError`` when ``image`` is missing.
    """
    from providers.google import apply_transparent_canvas_fix

    image = Path(image)
    if not image.exists():
        raise FileNotFoundError(f"Character image not found: {image}")
    out_png = Path(out_png)
    raw = image.read_bytes()
    fixed = apply_transparent_canvas_fix(raw, aspect_ratio, logger_instance=logger)

    with Image.open(io.BytesIO(fixed)) as img:
        rgba = img.convert("RGBA")
        out_png.parent.mkdir(parents=True, exist_ok=True)
        rgba.save(out_png, format="PNG")
        width, height = rgba.size

    analysis = analyze_source(image)
    write_image_sidecar(out_png, {
        "kind": "character_source",
        "source": str(image),
        "aspect_ratio": aspect_ratio,
        "padded": fixed is not raw,
        "size": [width, height],
        "source_has_alpha": analysis.has_alpha,
        "source_border_color": analysis.border_color,
        "timestamp": now_iso(),
    })
    logger.info("normalize_source: %s -> %s (%dx%d, aspect %s)",
                image, out_png, width, height, aspect_ratio)
    return out_png
