"""Synthetic frames and projects for the sprite GUI tests (no binary fixtures)."""
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtGui import QColor, QImage

from core.sprite.models import FrameMeta, SheetMeta, TagMeta
from core.sprite.project import ActionCard, SpriteProject


def write_frame_png(path: Path, size: Tuple[int, int] = (8, 8),
                    color: Tuple[int, int, int, int] = (255, 0, 0, 255),
                    dot: Optional[Tuple[int, int]] = None) -> Path:
    """Write a flat RGBA PNG; `dot` marks one blue pixel so frames differ."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image = QImage(size[0], size[1], QImage.Format_RGBA8888)
    image.fill(QColor(*color))
    if dot is not None:
        image.setPixelColor(dot[0], dot[1], QColor(0, 0, 255, 255))
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"cannot write {path}")
    return path


def make_frames(root: Path, n: int = 4, size: Tuple[int, int] = (8, 8),
                duration_ms: int = 100) -> List[FrameMeta]:
    frames: List[FrameMeta] = []
    for i in range(n):
        path = write_frame_png(root / f"{i:04d}.png", size=size, dot=(i % size[0], 0))
        frames.append(FrameMeta(
            name=f"frame_{i:02d}",
            source_path=path,
            frame=(0, 0, size[0], size[1]),
            source_size=size,
            sprite_source_size=(0, 0, size[0], size[1]),
            duration_ms=duration_ms,
        ))
    return frames


def make_project(root: Path, n_frames: int = 4) -> Tuple[SpriteProject, ActionCard]:
    project = SpriteProject(name="test_sprite", project_dir=root,
                            character_source=None, plate_path=None)
    action = ActionCard(id="act1", name="walk", prompt="walk cycle")
    action.frames = make_frames(root / "stages" / action.id / "stabilize", n_frames)
    project.actions.append(action)
    return project, action


def sheet_from_action(action: ActionCard, profile: str = "hd") -> SheetMeta:
    n = len(action.frames)
    return SheetMeta(
        title=action.name,
        frames=list(action.frames),
        tags=[TagMeta(name=action.name, from_index=0, to_index=max(0, n - 1))],
        cell_size=(8, 8),
        profile=profile,
    )
