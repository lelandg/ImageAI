"""Sheet slicing and PNG-sequence import (design section 4.1, gap G9).

External inputs enter the spine after ``extract``: both functions here write
``0001.png``... into an extract directory, and the caller registers them with
``pipeline.register_external_frames``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from .models import Size

logger = logging.getLogger(__name__)

BACKGROUND_TOLERANCE = 12  # per-channel, 0..255
ALPHA_BACKGROUND = 8       # alpha at or below this counts as background


@dataclass
class GridGuess:
    columns: int
    rows: int
    cell: Size
    confidence: float


def _hex_to_rgb(text: str) -> Tuple[int, int, int]:
    text = text.strip().lstrip("#")
    if len(text) != 6:
        raise ValueError(f"Not a #RRGGBB color: {text!r}")
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))


def foreground_mask(sheet: Image.Image, key_color: Optional[str] = None) -> np.ndarray:
    """True where a pixel belongs to a sprite, False where it is background.

    Order of evidence: real transparency, then the key color, then the
    top-left corner color.
    """
    rgba = np.asarray(sheet.convert("RGBA"))
    alpha = rgba[..., 3]
    if np.any(alpha <= ALPHA_BACKGROUND):
        return alpha > ALPHA_BACKGROUND
    rgb = rgba[..., :3].astype(np.int16)
    bg = np.array(_hex_to_rgb(key_color), dtype=np.int16) if key_color else rgb[0, 0]
    diff = np.abs(rgb - bg).max(axis=2)
    return diff > BACKGROUND_TOLERANCE


def _runs(flags: np.ndarray) -> List[Tuple[int, int]]:
    """Start/end (exclusive) of each run of True in a 1-D bool array."""
    runs: List[Tuple[int, int]] = []
    start: Optional[int] = None
    for index, flag in enumerate(flags.tolist()):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            runs.append((start, index))
            start = None
    if start is not None:
        runs.append((start, len(flags)))
    return runs


def _axis_confidence(runs: List[Tuple[int, int]]) -> Optional[float]:
    if len(runs) < 2:
        return None
    if len(runs) == 2:
        return 0.8
    centers = np.array([(a + b) / 2.0 for a, b in runs])
    pitches = np.diff(centers)
    mean = float(pitches.mean())
    if mean <= 0:
        return 0.0
    return float(max(0.0, min(1.0, 1.0 - pitches.std() / mean)))


def guess_grid(sheet: Image.Image, key_color: Optional[str] = None) -> GridGuess:
    """Guess columns, rows and cell size from the gaps between sprites.

    Projects the foreground mask onto both axes; each run of foreground is a
    column (or row) of cells. ``confidence`` below 0.6 means "ask the user".
    """
    mask = foreground_mask(sheet, key_color)
    height, width = mask.shape
    col_runs = _runs(mask.any(axis=0))
    row_runs = _runs(mask.any(axis=1))
    columns = max(1, len(col_runs))
    rows = max(1, len(row_runs))
    scores = [s for s in (_axis_confidence(col_runs), _axis_confidence(row_runs)) if s is not None]
    confidence = min(scores) if scores else 0.3
    cell = (max(1, width // columns), max(1, height // rows))
    return GridGuess(columns=columns, rows=rows, cell=cell, confidence=round(confidence, 3))


def slice_sheet(sheet: Path, out_dir: Path, columns: int, rows: int,
                cell: Optional[Size] = None, margin: int = 0, spacing: int = 0) -> List[Path]:
    """Cut a sheet into ``columns * rows`` RGBA PNG frames, row-major."""
    if columns < 1 or rows < 1:
        raise ValueError("columns and rows must be at least 1")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(sheet) as im:
        image = im.convert("RGBA")
    width, height = image.size
    if cell is None:
        cw = (width - 2 * margin - (columns - 1) * spacing) // columns
        ch = (height - 2 * margin - (rows - 1) * spacing) // rows
        cell = (cw, ch)
    cw, ch = cell
    if cw < 1 or ch < 1:
        raise ValueError(f"Cell size {cell} does not fit a {width}x{height} sheet")
    written: List[Path] = []
    index = 1
    for row in range(rows):
        for col in range(columns):
            x = margin + col * (cw + spacing)
            y = margin + row * (ch + spacing)
            if x + cw > width or y + ch > height:
                raise ValueError(
                    f"Cell ({col},{row}) at {x},{y} size {cw}x{ch} lies outside the {width}x{height} sheet"
                )
            frame = image.crop((x, y, x + cw, y + ch))
            dest = out_dir / f"{index:04d}.png"
            frame.save(dest, format="PNG")
            written.append(dest)
            index += 1
    logger.info(f"Sliced {sheet} into {len(written)} frames ({columns}x{rows}, cell {cw}x{ch})")
    return written


def import_png_sequence(paths: Sequence[Path], out_dir: Path) -> List[Path]:
    """Copy images into ``out_dir`` as RGBA PNGs numbered 0001.png... in the given order."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for index, src in enumerate(paths, start=1):
        with Image.open(src) as im:
            frame = im.convert("RGBA")
        dest = out_dir / f"{index:04d}.png"
        frame.save(dest, format="PNG")
        written.append(dest)
    logger.info(f"Imported {len(written)} frames into {out_dir}")
    return written
