"""GIF export with preserved, transparent, or solid backgrounds.

Recipe, regression-tested: every frame is quantized to 255 colours, index
255 is reserved for transparency (or the exact solid background), ``disposal=2`` clears each frame before
the next, ``optimize=False`` keeps Pillow from merging palettes, and every
duration is clamped to at least 20 ms because browsers treat shorter delays
as 100 ms.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageChops

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


def normalize_background_color(color: str) -> str:
    """Validate the portable RGB color accepted by the GIF export API."""
    if not isinstance(color, str) or re.fullmatch(r"#[0-9a-fA-F]{6}", color) is None:
        logger.error("Invalid GIF background color: %r", color)
        raise ValueError("Background color must be a hex RGB color such as #FFFFFF")
    return color.upper()


def to_solid_palette_frame(image: Image.Image, color: str) -> Image.Image:
    """Composite before quantization and reserve index 255 for the exact background."""
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, color)
    rgb = Image.alpha_composite(background, rgba).convert("RGB")
    quantized = rgb.quantize(colors=255, method=Image.Quantize.MEDIANCUT,
                             dither=Image.Dither.NONE)
    palette = (quantized.getpalette() or [])[:255 * 3]
    palette += [0] * (255 * 3 - len(palette)) + list(background.getpixel((0, 0))[:3])
    quantized.putpalette(palette)
    difference = ImageChops.difference(rgb, background.convert("RGB"))
    red, green, blue = difference.split()
    exact = ImageChops.lighter(ImageChops.lighter(red, green), blue).point(
        lambda value: 255 if value == 0 else 0)
    quantized.paste(255, mask=exact)
    return quantized


def export_gif(meta: SheetMeta, tag: TagMeta, out_gif: Path, *, loop: int = 0,
               warnings: Optional[List[str]] = None,
               background_color: Optional[str] = None,
               background_mode: str = "transparent") -> Path:
    """Write one tag as GIF, optionally composited onto an exact solid RGB color.

    Original mode preserves source alpha when present, and omits transparency
    altogether for opaque inputs. Default calls retain the transparent recipe.
    """
    if background_mode not in ("transparent", "original", "solid"):
        logger.error("Unknown GIF background mode: %r", background_mode)
        raise ValueError(f"Unknown background mode: {background_mode!r}")
    if background_color is not None:
        background_color = normalize_background_color(background_color)
        background_mode = "solid"
    elif background_mode == "solid":
        logger.error("Solid GIF background mode requires background_color")
        raise ValueError("Solid background mode requires background_color")
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
    has_alpha = False
    for frame in frames:
        if frame.source_path is None or not Path(frame.source_path).exists():
            raise FileNotFoundError(f"Frame '{frame.name}' has no source PNG: {frame.source_path}")
        with Image.open(frame.source_path) as im:
            has_alpha = has_alpha or im.convert("RGBA").getchannel("A").getextrema()[0] < ALPHA_CUTOFF
            palette_frames.append(to_solid_palette_frame(im, background_color)
                                  if background_color else to_palette_frame(im))
    first, rest = palette_frames[0], palette_frames[1:]
    options = {"background": 255} if background_color else {}
    if background_mode == "transparent" or (background_mode == "original" and has_alpha):
        options["transparency"] = TRANSPARENT_INDEX
    first.save(
        out_gif, format="GIF", save_all=True, append_images=rest,
        duration=durations, loop=loop, disposal=2, optimize=False,
        **options,
    )
    sidecar_path(out_gif).write_text(json.dumps({
        "type": "sprite_gif",
        "title": meta.title,
        "tag": tag.name,
        "direction": tag.direction,
        "frames": len(frames),
        "durations_ms": durations,
        "loop": loop,
        "background_mode": background_mode,
        "background_color": background_color,
        "warnings": notes,
        "app": meta.app,
        "version": meta.version,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }, indent=2), encoding="utf-8")
    logger.info("Wrote GIF %s (%d frames, tag '%s', background=%s, color=%s)",
                out_gif, len(frames), tag.name, background_mode, background_color)
    return out_gif
