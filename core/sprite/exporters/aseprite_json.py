"""Aseprite JSON export (hash and array layouts).

Key names match Aseprite's own ``--data`` output so engine importers
(Phaser ``createFromAseprite``, Unity/Godot community importers) read it
without changes. ``meta.app`` and ``meta.version`` name ImageAI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from ..models import FrameMeta, SheetMeta

LAYOUTS = ("hash", "array")
DEFAULT_TAG_COLOR = "#000000ff"


def frame_key(frame: FrameMeta) -> str:
    return frame.name


def _frame_entry(frame: FrameMeta) -> Dict[str, Any]:
    x, y, w, h = frame.frame
    sx, sy, sw, sh = frame.sprite_source_size
    return {
        "frame": {"x": x, "y": y, "w": w, "h": h},
        "rotated": frame.rotated,
        "trimmed": frame.trimmed,
        "spriteSourceSize": {"x": sx, "y": sy, "w": sw, "h": sh},
        "sourceSize": {"w": frame.source_size[0], "h": frame.source_size[1]},
        "duration": frame.duration_ms,
    }


def aseprite_document(meta: SheetMeta, *, image_name: str, layout: str = "hash") -> Dict[str, Any]:
    if layout not in LAYOUTS:
        raise ValueError(f"layout must be one of {LAYOUTS}, got {layout!r}")
    if layout == "hash":
        frames: Any = {frame_key(f): _frame_entry(f) for f in meta.frames}
    else:
        frames = [dict(filename=frame_key(f), **_frame_entry(f)) for f in meta.frames]
    frame_tags: List[Dict[str, Any]] = []
    for tag in meta.tags:
        entry: Dict[str, Any] = {
            "name": tag.name,
            "from": tag.from_index,
            "to": tag.to_index,
            "direction": tag.direction,
            "color": DEFAULT_TAG_COLOR,
        }
        if tag.repeat > 0:
            entry["repeat"] = str(tag.repeat)
        frame_tags.append(entry)
    scale = int(meta.scale) if float(meta.scale).is_integer() else meta.scale
    return {
        "frames": frames,
        "meta": {
            "app": meta.app,
            "version": meta.version,
            "image": image_name,
            "format": "RGBA8888",
            "size": {"w": meta.sheet_size[0], "h": meta.sheet_size[1]},
            "scale": str(scale),
            "frameTags": frame_tags,
            "layers": [{"name": "Layer 1", "opacity": 255, "blendMode": "normal"}],
            "slices": [],
        },
    }


def export_aseprite_json(meta: SheetMeta, out_json: Path, *, image_name: str,
                         layout: str = "hash") -> None:
    out_json = Path(out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    document = aseprite_document(meta, image_name=image_name, layout=layout)
    out_json.write_text(json.dumps(document, indent=1), encoding="utf-8")
