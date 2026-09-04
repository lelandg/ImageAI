"""Cell, canvas, FPS, and genre presets for the Sprite tab (design section 2)."""

from __future__ import annotations

import re
from typing import Dict, Tuple

from .models import Size

# (label, (w, h)); the label uses the multiplication sign the UI shows.
CELL_PRESETS: Tuple[Tuple[str, Size], ...] = (
    ("8×8", (8, 8)),
    ("16×16", (16, 16)),
    ("16×24", (16, 24)),
    ("24×24", (24, 24)),
    ("16×32", (16, 32)),
    ("32×32", (32, 32)),
    ("48×48 (RPG Maker)", (48, 48)),
    ("64×64", (64, 64)),
    ("96×96", (96, 96)),
    ("128×128", (128, 128)),
    ("256×256", (256, 256)),
    ("512×512", (512, 512)),
    ("720×720", (720, 720)),
    ("1024×1024", (1024, 1024)),
)
DEFAULT_CELL: Size = (64, 64)
CUSTOM_CELL_LABEL = "Custom…"

CANVAS_PRESETS: Tuple[Tuple[str, Size], ...] = (
    ("320×180", (320, 180)),
    ("384×216", (384, 216)),
    ("400×240", (400, 240)),
    ("480×270", (480, 270)),
    ("640×360", (640, 360)),
)
TARGET_RESOLUTIONS: Dict[str, Size] = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "4K": (3840, 2160),
}

# (fps, note)
FPS_PRESETS: Tuple[Tuple[int, str], ...] = (
    (8, "on threes"),
    (12, "on twos"),
    (24, ""),
    (30, ""),
    (60, ""),
)
DEFAULT_FPS = 12

GENRE_PRESETS: Tuple[str, ...] = ("sidescroller", "top_down", "fighting")
DEFAULT_GENRE = "sidescroller"

_SIZE_RE = re.compile(r"^\s*(\d+)\s*(?:[x×X\*]\s*(\d+))?\s*$")


def parse_cell_size(text: str) -> Size:
    """Parse ``"64"``, ``"16x24"``, ``"16×24"`` or ``"16*24"`` into a size.

    A single number means a square cell. Raises ValueError on anything else
    or on a zero dimension.
    """
    match = _SIZE_RE.match(text or "")
    if not match:
        raise ValueError(f"Not a cell size: {text!r} (use W or WxH)")
    w = int(match.group(1))
    h = int(match.group(2)) if match.group(2) else w
    if w < 1 or h < 1:
        raise ValueError(f"Cell size must be at least 1x1: {text!r}")
    return (w, h)


def format_cell_size(size: Size) -> str:
    return f"{size[0]}×{size[1]}"


def integer_scale(canvas: Size, target: Size) -> int:
    """Largest integer k with ``canvas * k`` inside ``target``; 0 when none fits."""
    cw, ch = canvas
    tw, th = target
    if cw < 1 or ch < 1:
        raise ValueError("canvas dimensions must be positive")
    return min(tw // cw, th // ch)


def integer_scale_table(canvas: Size) -> Dict[str, int]:
    """Integer scale of ``canvas`` for every entry in TARGET_RESOLUTIONS."""
    return {name: integer_scale(canvas, size) for name, size in TARGET_RESOLUTIONS.items()}
