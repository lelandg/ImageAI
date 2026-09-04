"""TexturePacker-style JSON export (hash and array) with pivot and animations.

The ``animations`` block is the top-level map PixiJS and Phaser read:
``{"walk": ["hero_walk_00.png", ...]}``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from ..models import FrameMeta, SheetMeta

LAYOUTS = ("hash", "array")


def frame_key(frame: FrameMeta) -> str:
    return f"{frame.name}.png"


def _frame_entry(frame: FrameMeta) -> Dict[str, Any]:
    x, y, w, h = frame.frame
    sx, sy, sw, sh = frame.sprite_source_size
    return {
        "frame": {"x": x, "y": y, "w": w, "h": h},
        "rotated": frame.rotated,
        "trimmed": frame.trimmed,
        "spriteSourceSize": {"x": sx, "y": sy, "w": sw, "h": sh},
        "sourceSize": {"w": frame.source_size[0], "h": frame.source_size[1]},
        "pivot": {"x": frame.pivot[0], "y": frame.pivot[1]},
    }


def texturepacker_document(meta: SheetMeta, *, image_name: str, layout: str = "hash") -> Dict[str, Any]:
    if layout not in LAYOUTS:
        raise ValueError(f"layout must be one of {LAYOUTS}, got {layout!r}")
    if layout == "hash":
        frames: Any = {frame_key(f): _frame_entry(f) for f in meta.frames}
    else:
        frames = [dict(filename=frame_key(f), **_frame_entry(f)) for f in meta.frames]
    animations = {tag.name: [frame_key(f) for f in meta.frames_for(tag)] for tag in meta.tags}
    scale = int(meta.scale) if float(meta.scale).is_integer() else meta.scale
    return {
        "frames": frames,
        "animations": animations,
        "meta": {
            "app": meta.app,
            "version": meta.version,
            "image": image_name,
            "format": "RGBA8888",
            "size": {"w": meta.sheet_size[0], "h": meta.sheet_size[1]},
            "scale": str(scale),
        },
    }


def export_texturepacker_json(meta: SheetMeta, out_json: Path, *, image_name: str,
                              layout: str = "hash") -> None:
    out_json = Path(out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    document = texturepacker_document(meta, image_name=image_name, layout=layout)
    out_json.write_text(json.dumps(document, indent=1), encoding="utf-8")
