"""Grid sprite-sheet export (design section 4.1).

Layout: one row per tag by default (``columns=0``), or a fixed column
count. ``border_px`` surrounds the sheet, ``shape_px`` separates cells,
``inner_px`` pads inside each cell, ``extrude_px`` repeats sprite edge pixels
outward into the gap. Always writes an Aseprite JSON sidecar next to the
PNG, plus the ImageAI ``.png.json`` metadata sidecar.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from PIL import Image

from core.utils import write_image_sidecar

from ..models import SheetMeta
from .aseprite_json import export_aseprite_json

logger = logging.getLogger(__name__)


@dataclass
class GridOptions:
    columns: int = 0
    border_px: int = 0
    shape_px: int = 1
    inner_px: int = 0
    extrude_px: int = 0
    power_of_two: bool = False
    scales: Tuple[int, ...] = (1,)


def next_power_of_two(value: int) -> int:
    result = 1
    while result < value:
        result *= 2
    return result


def _grid_shape(meta: SheetMeta, opts: GridOptions) -> Tuple[int, int, List[Tuple[int, int]]]:
    """Return (columns, rows, [(col, row) per frame])."""
    count = len(meta.frames)
    if count == 0:
        return (0, 0, [])
    if opts.columns > 0:
        columns = opts.columns
        cells = [(i % columns, i // columns) for i in range(count)]
        rows = (count + columns - 1) // columns
        return (columns, rows, cells)
    # One row per tag; frames outside every tag go on a final row.
    cells: List[Tuple[int, int]] = [(-1, -1)] * count
    row = 0
    columns = 0
    covered = [False] * count
    for tag in meta.tags:
        span = [i for i in range(tag.from_index, tag.to_index + 1) if 0 <= i < count and not covered[i]]
        if not span:
            continue
        for col, index in enumerate(span):
            cells[index] = (col, row)
            covered[index] = True
        columns = max(columns, len(span))
        row += 1
    leftovers = [i for i in range(count) if not covered[i]]
    if leftovers:
        for col, index in enumerate(leftovers):
            cells[index] = (col, row)
        columns = max(columns, len(leftovers))
        row += 1
    return (columns, row, cells)


def _extrude(sheet: Image.Image, sprite: Image.Image, x: int, y: int, px: int) -> None:
    """Repeat the sprite's edge pixels ``px`` times outward."""
    w, h = sprite.size
    if px <= 0 or w == 0 or h == 0:
        return
    left = sprite.crop((0, 0, 1, h))
    right = sprite.crop((w - 1, 0, w, h))
    top = sprite.crop((0, 0, w, 1))
    bottom = sprite.crop((0, h - 1, w, h))
    for i in range(1, px + 1):
        sheet.paste(left, (x - i, y))
        sheet.paste(right, (x + w - 1 + i, y))
        sheet.paste(top, (x, y - i))
        sheet.paste(bottom, (x, y + h - 1 + i))
    corners = {
        (x - px, y - px): sprite.getpixel((0, 0)),
        (x + w, y - px): sprite.getpixel((w - 1, 0)),
        (x - px, y + h): sprite.getpixel((0, h - 1)),
        (x + w, y + h): sprite.getpixel((w - 1, h - 1)),
    }
    for (cx, cy), color in corners.items():
        sheet.paste(Image.new("RGBA", (px, px), color), (cx, cy))


def _scaled_meta(meta: SheetMeta, scale: int) -> SheetMeta:
    scaled = copy.deepcopy(meta)
    scaled.scale = float(scale)
    scaled.sheet_size = (meta.sheet_size[0] * scale, meta.sheet_size[1] * scale)
    scaled.cell_size = (meta.cell_size[0] * scale, meta.cell_size[1] * scale)
    for frame in scaled.frames:
        fx, fy, fw, fh = frame.frame
        frame.frame = (fx * scale, fy * scale, fw * scale, fh * scale)
        sx, sy, sw, sh = frame.sprite_source_size
        frame.sprite_source_size = (sx * scale, sy * scale, sw * scale, sh * scale)
        frame.source_size = (frame.source_size[0] * scale, frame.source_size[1] * scale)
    return scaled


def export_grid(meta: SheetMeta, out_png: Path, opts: GridOptions) -> SheetMeta:
    """Write the sheet PNG (+ Aseprite JSON + metadata sidecar); return filled meta."""
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    if not meta.frames:
        raise ValueError("SheetMeta has no frames to export")
    if opts.extrude_px < 0 or opts.shape_px < 0 or opts.border_px < 0 or opts.inner_px < 0:
        raise ValueError("padding values must not be negative")
    if opts.extrude_px > 0 and (2 * opts.extrude_px > opts.shape_px or opts.extrude_px > opts.border_px):
        raise ValueError(
            "extrude_px needs room: shape_px must be at least 2*extrude_px and "
            "border_px at least extrude_px"
        )
    if any(s < 1 for s in opts.scales) or 1 not in opts.scales:
        raise ValueError("scales must be positive and include 1")

    images: List[Image.Image] = []
    for frame in meta.frames:
        if frame.source_path is None or not Path(frame.source_path).exists():
            raise FileNotFoundError(f"Frame '{frame.name}' has no source PNG: {frame.source_path}")
        with Image.open(frame.source_path) as im:
            images.append(im.convert("RGBA"))

    cw = max(im.size[0] for im in images) + 2 * opts.inner_px
    ch = max(im.size[1] for im in images) + 2 * opts.inner_px
    columns, rows, cells = _grid_shape(meta, opts)
    width = 2 * opts.border_px + columns * cw + max(0, columns - 1) * opts.shape_px
    height = 2 * opts.border_px + rows * ch + max(0, rows - 1) * opts.shape_px
    if opts.power_of_two:
        width, height = next_power_of_two(width), next_power_of_two(height)

    sheet = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    filled = copy.deepcopy(meta)
    filled.sheet_size = (width, height)
    filled.cell_size = (cw, ch)
    for frame, image, (col, row) in zip(filled.frames, images, cells):
        cell_x = opts.border_px + col * (cw + opts.shape_px)
        cell_y = opts.border_px + row * (ch + opts.shape_px)
        # Centre the sprite inside its (inner-padded) cell.
        sx = cell_x + (cw - image.size[0]) // 2
        sy = cell_y + (ch - image.size[1]) // 2
        if opts.extrude_px:
            _extrude(sheet, image, sx, sy, opts.extrude_px)
        sheet.paste(image, (sx, sy))
        frame.frame = (sx, sy, image.size[0], image.size[1])
        frame.rotated = False
        frame.trimmed = False
        frame.sprite_source_size = (0, 0, image.size[0], image.size[1])
        frame.source_size = (image.size[0], image.size[1])

    for scale in opts.scales:
        if scale == 1:
            target, target_meta = out_png, filled
            image = sheet
        else:
            target = out_png.with_name(f"{out_png.stem}@{scale}x{out_png.suffix}")
            target_meta = _scaled_meta(filled, scale)
            image = sheet.resize((width * scale, height * scale), Image.Resampling.NEAREST)
        image.save(target, format="PNG")
        export_aseprite_json(target_meta, target.with_suffix(".json"), image_name=target.name, layout="hash")
        write_image_sidecar(target, {
            "type": "sprite_sheet",
            "title": meta.title,
            "profile": meta.profile,
            "scale": scale,
            "frames": len(filled.frames),
            "tags": [t.name for t in filled.tags],
            "sheet_size": list(target_meta.sheet_size),
            "cell_size": list(target_meta.cell_size),
            "grid_options": {
                "columns": opts.columns, "border_px": opts.border_px, "shape_px": opts.shape_px,
                "inner_px": opts.inner_px, "extrude_px": opts.extrude_px,
                "power_of_two": opts.power_of_two,
            },
            "app": meta.app,
            "version": meta.version,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        logger.info(f"Wrote sprite sheet {target} ({image.size[0]}x{image.size[1]})")
    return filled
