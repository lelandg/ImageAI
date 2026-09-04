"""Sprite sheet metadata: the one source of truth every exporter projects.

Stdlib dataclasses only. No Qt, no PIL. ``SheetMeta`` describes a set of
frames on disk plus the tags (animations) that group them. Exporters read a
``SheetMeta`` and write files; they never mutate the project.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.constants import VERSION

Rect = Tuple[int, int, int, int]  # x, y, w, h
Size = Tuple[int, int]  # w, h

DIRECTIONS = ("forward", "reverse", "pingpong", "pingpong_reverse")


def _rect(value: Any) -> Rect:
    x, y, w, h = (int(v) for v in value)
    return (x, y, w, h)


def _size(value: Any) -> Size:
    w, h = (int(v) for v in value)
    return (w, h)


@dataclass
class FrameMeta:
    """One frame of a sprite sheet."""

    name: str
    source_path: Optional[Path]
    frame: Rect
    rotated: bool = False
    trimmed: bool = False
    sprite_source_size: Rect = (0, 0, 0, 0)
    source_size: Size = (0, 0)
    duration_ms: int = 100
    pivot: Tuple[float, float] = (0.5, 1.0)
    overrides: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "source_path": str(self.source_path) if self.source_path else None,
            "frame": list(self.frame),
            "rotated": self.rotated,
            "trimmed": self.trimmed,
            "sprite_source_size": list(self.sprite_source_size),
            "source_size": list(self.source_size),
            "duration_ms": self.duration_ms,
            "pivot": list(self.pivot),
            "overrides": dict(self.overrides),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FrameMeta":
        source = data.get("source_path")
        pivot = data.get("pivot", [0.5, 1.0])
        return cls(
            name=str(data.get("name", "")),
            source_path=Path(source) if source else None,
            frame=_rect(data.get("frame", (0, 0, 0, 0))),
            rotated=bool(data.get("rotated", False)),
            trimmed=bool(data.get("trimmed", False)),
            sprite_source_size=_rect(data.get("sprite_source_size", (0, 0, 0, 0))),
            source_size=_size(data.get("source_size", (0, 0))),
            duration_ms=int(data.get("duration_ms", 100)),
            pivot=(float(pivot[0]), float(pivot[1])),
            overrides=dict(data.get("overrides") or {}),
        )


@dataclass
class TagMeta:
    """A named, contiguous range of frames (one animation)."""

    name: str
    from_index: int
    to_index: int
    direction: str = "forward"
    repeat: int = 0
    fps_hint: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "from_index": self.from_index,
            "to_index": self.to_index,
            "direction": self.direction,
            "repeat": self.repeat,
            "fps_hint": self.fps_hint,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TagMeta":
        fps_hint = data.get("fps_hint")
        return cls(
            name=str(data.get("name", "")),
            from_index=int(data.get("from_index", 0)),
            to_index=int(data.get("to_index", 0)),
            direction=str(data.get("direction", "forward")),
            repeat=int(data.get("repeat", 0)),
            fps_hint=int(fps_hint) if fps_hint is not None else None,
        )


@dataclass
class SheetMeta:
    """Everything an exporter needs to know about one sprite sheet."""

    title: str
    frames: List[FrameMeta]
    tags: List[TagMeta]
    sheet_size: Size = (0, 0)
    cell_size: Size = (64, 64)
    scale: float = 1.0
    palette: Optional[List[str]] = None
    profile: str = "hd"
    app: str = "ImageAI"
    version: str = VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "frames": [f.to_dict() for f in self.frames],
            "tags": [t.to_dict() for t in self.tags],
            "sheet_size": list(self.sheet_size),
            "cell_size": list(self.cell_size),
            "scale": self.scale,
            "palette": list(self.palette) if self.palette is not None else None,
            "profile": self.profile,
            "app": self.app,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SheetMeta":
        palette = data.get("palette")
        return cls(
            title=str(data.get("title", "")),
            frames=[FrameMeta.from_dict(f) for f in data.get("frames", [])],
            tags=[TagMeta.from_dict(t) for t in data.get("tags", [])],
            sheet_size=_size(data.get("sheet_size", (0, 0))),
            cell_size=_size(data.get("cell_size", (64, 64))),
            scale=float(data.get("scale", 1.0)),
            palette=[str(c) for c in palette] if palette is not None else None,
            profile=str(data.get("profile", "hd")),
            app=str(data.get("app", "ImageAI")),
            version=str(data.get("version", VERSION)),
        )

    def frames_for(self, tag: TagMeta) -> List[FrameMeta]:
        """Return the frames a tag covers, in sheet order."""
        if tag.to_index < tag.from_index:
            return []
        return self.frames[tag.from_index:tag.to_index + 1]
