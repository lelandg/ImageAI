"""Godot 4 ``SpriteFrames`` (.tres) exporter — a pure projection of SheetMeta.

Godot 4 has no JSON atlas importer. A text resource with one ``AtlasTexture``
sub-resource per frame is the engine-ready path: copy the PNG and the .tres
into the project and assign the .tres to an ``AnimatedSprite2D``.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from core.sprite.models import FrameMeta, SheetMeta, TagMeta
from core.sprite.timing import ms_to_fps
from core.utils import write_image_sidecar

logger = logging.getLogger(__name__)

GODOT_FORMAT = 3


def _fmt_float(value: float) -> str:
    """Godot text floats always carry a decimal point ("12.0", "1.5")."""
    text = f"{float(value):.4f}".rstrip("0")
    if text.endswith("."):
        text += "0"
    return text


def ordered_frame_indices(tag: TagMeta) -> List[int]:
    """Unroll a tag direction into the explicit frame order Godot plays.

    ``SpriteFrames`` has no direction field, so reverse and ping-pong tags
    become a plain sequence.
    """
    forward = list(range(tag.from_index, tag.to_index + 1))
    if tag.direction == "reverse":
        return forward[::-1]
    if tag.direction == "pingpong":
        return forward + forward[-2:0:-1]
    if tag.direction == "pingpong_reverse":
        back = forward[::-1]
        return back + back[-2:0:-1]
    return forward


def _atlas_block(index: int, frame: FrameMeta) -> str:
    x, y, w, h = frame.frame
    lines = [
        f'[sub_resource type="AtlasTexture" id="AtlasTexture_{index}"]',
        'atlas = ExtResource("1")',
        f"region = Rect2({x}, {y}, {w}, {h})",
    ]
    ox, oy, _, _ = frame.sprite_source_size
    sw, sh = frame.source_size
    if frame.trimmed and sw > 0 and sh > 0:
        margin = (ox, oy, sw - w, sh - h)
        if any(margin):
            lines.append(f"margin = Rect2({margin[0]}, {margin[1]}, {margin[2]}, {margin[3]})")
    return "\n".join(lines)


def _animation_block(meta: SheetMeta, tag: TagMeta) -> str:
    indices = ordered_frame_indices(tag)
    durations = [meta.frames[i].duration_ms for i in indices]
    fps, multipliers = ms_to_fps(durations)
    entries = []
    for i, mult in zip(indices, multipliers):
        entries.append(
            "{\n"
            f'"duration": {_fmt_float(mult)},\n'
            f'"texture": SubResource("AtlasTexture_{i + 1}")\n'
            "}"
        )
    loop = "true" if tag.repeat == 0 else "false"
    return (
        "{\n"
        '"frames": [' + ", ".join(entries) + "],\n"
        f'"loop": {loop},\n'
        f'"name": &"{tag.name}",\n'
        f'"speed": {_fmt_float(fps)}\n'
        "}"
    )


def render_godot_tres(meta: SheetMeta, *, atlas_res_path: str) -> str:
    """Return the .tres text for ``meta``. Frame rects must be filled by export_grid."""
    if not meta.frames:
        raise ValueError("SheetMeta has no frames")
    if tuple(meta.sheet_size) == (0, 0):
        raise ValueError("SheetMeta.sheet_size is (0, 0): run export_grid before export_godot_tres")
    load_steps = 1 + len(meta.frames) + 1
    parts = [
        f'[gd_resource type="SpriteFrames" load_steps={load_steps} format={GODOT_FORMAT}]',
        "",
        f'[ext_resource type="Texture2D" path="{atlas_res_path}" id="1"]',
        "",
    ]
    for index, frame in enumerate(meta.frames, start=1):
        parts.append(_atlas_block(index, frame))
        parts.append("")
    parts.append("[resource]")
    animations = ", ".join(_animation_block(meta, tag) for tag in meta.tags)
    parts.append(f"animations = [{animations}]")
    return "\n".join(parts) + "\n"


def export_godot_tres(meta: SheetMeta, out_tres: Path, *, atlas_res_path: str) -> Path:
    """Write ``meta`` as a Godot 4 SpriteFrames text resource plus a JSON sidecar."""
    out_tres = Path(out_tres)
    out_tres.parent.mkdir(parents=True, exist_ok=True)
    text = render_godot_tres(meta, atlas_res_path=atlas_res_path)
    out_tres.write_text(text, encoding="utf-8")
    write_image_sidecar(out_tres, {
        "format": "godot_tres",
        "atlas": atlas_res_path,
        "title": meta.title,
        "profile": meta.profile,
        "frames": len(meta.frames),
        "tags": [t.name for t in meta.tags],
        "app": meta.app,
        "version": meta.version,
    })
    logger.info("Godot SpriteFrames written: %s (%d frames, %d animations)",
                out_tres, len(meta.frames), len(meta.tags))
    return out_tres
