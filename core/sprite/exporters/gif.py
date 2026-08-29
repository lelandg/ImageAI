"""Transparent GIF export with the safe Pillow recipe (design section 4.1).

Recipe, regression-tested: every frame is quantized to 255 colours, index
255 is reserved for transparency, ``disposal=2`` clears each frame before
the next, ``optimize=False`` keeps Pillow from merging palettes, and every
duration is clamped to at least 20 ms because browsers treat shorter delays
as 100 ms.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image

from core.utils import sidecar_path

from ..models import FrameMeta, SheetMeta, TagMeta

logger = logging.getLogger(__name__)

TRANSPARENT_INDEX = 255
MIN_DURATION_MS = 20
GIF_UNIT_MS = 10  # the GIF delay field counts hundredths of a second
ALPHA_CUTOFF = 128


def gif_durations(frames: List[FrameMeta]) -> Tuple[List[int], List[str]]:
    """Round durations to the GIF 10 ms unit and clamp to >= 20 ms.

    Returns ``(durations, warnings)``. Each clamp gets its own warning; all
    roundings share one summary warning, because a 12 fps sheet (83 ms)
    rounds on every frame and a warning per frame would only be noise.
    """
    durations: List[int] = []
    warnings: List[str] = []
    rounded = 0
    for frame in frames:
        ms = int(frame.duration_ms)
        if ms < MIN_DURATION_MS:
            warnings.append(
                f"Frame '{frame.name}' duration {ms} ms raised to {MIN_DURATION_MS} ms "
                "(GIF viewers ignore shorter delays)"
            )
            durations.append(MIN_DURATION_MS)
            continue
        unit = int(round(ms / GIF_UNIT_MS)) * GIF_UNIT_MS
        if unit != ms:
            rounded += 1
        durations.append(unit)
    if rounded:
        warnings.append(f"{rounded} frame duration(s) rounded to the GIF {GIF_UNIT_MS} ms unit")
    return durations, warnings


def ordered_frames(meta: SheetMeta, tag: TagMeta) -> List[FrameMeta]:
    """Apply the tag direction to its frame range."""
    frames = meta.frames_for(tag)
    if tag.direction == "reverse":
        return list(reversed(frames))
    if tag.direction == "pingpong" and len(frames) > 2:
        return frames + list(reversed(frames[1:-1]))
    if tag.direction == "pingpong_reverse" and len(frames) > 2:
        back = list(reversed(frames))
        return back + frames[1:-1]
    return list(frames)


def to_palette_frame(image: Image.Image) -> Image.Image:
    """RGBA -> P with index 255 reserved for fully transparent pixels."""
    rgba = image.convert("RGBA")
    rgb = rgba.convert("RGB")
    alpha = rgba.getchannel("A")
    quantized = rgb.quantize(colors=TRANSPARENT_INDEX, method=Image.Quantize.MEDIANCUT,
                             dither=Image.Dither.NONE)
    palette = (quantized.getpalette() or [])[:TRANSPARENT_INDEX * 3]
    palette += [0] * (TRANSPARENT_INDEX * 3 - len(palette)) + [0, 0, 0]
    quantized.putpalette(palette)
    mask = alpha.point(lambda v: 255 if v < ALPHA_CUTOFF else 0)
    quantized.paste(TRANSPARENT_INDEX, mask=mask)
    return quantized


def export_gif(meta: SheetMeta, tag: TagMeta, out_gif: Path, *, loop: int = 0,
               warnings: Optional[List[str]] = None) -> Path:
    """Write one tag as a looping transparent GIF. Collects warnings when a list is given."""
    out_gif = Path(out_gif)
    out_gif.parent.mkdir(parents=True, exist_ok=True)
    frames = ordered_frames(meta, tag)
    if not frames:
        raise ValueError(f"Tag '{tag.name}' covers no frames")
    durations, notes = gif_durations(frames)
    for note in notes:
        logger.warning(note)
    if warnings is not None:
        warnings.extend(notes)
    palette_frames: List[Image.Image] = []
    for frame in frames:
        if frame.source_path is None or not Path(frame.source_path).exists():
            raise FileNotFoundError(f"Frame '{frame.name}' has no source PNG: {frame.source_path}")
        with Image.open(frame.source_path) as im:
            palette_frames.append(to_palette_frame(im))
    first, rest = palette_frames[0], palette_frames[1:]
    first.save(
        out_gif, format="GIF", save_all=True, append_images=rest,
        duration=durations, loop=loop, disposal=2, optimize=False,
        transparency=TRANSPARENT_INDEX,
    )
    sidecar_path(out_gif).write_text(json.dumps({
        "type": "sprite_gif",
        "title": meta.title,
        "tag": tag.name,
        "direction": tag.direction,
        "frames": len(frames),
        "durations_ms": durations,
        "loop": loop,
        "warnings": notes,
        "app": meta.app,
        "version": meta.version,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }, indent=2), encoding="utf-8")
    logger.info(f"Wrote GIF {out_gif} ({len(frames)} frames, tag '{tag.name}')")
    return out_gif
