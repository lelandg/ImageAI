"""Per-tag PNG sequence export and single-frame export.

Template fields: ``{title}``, ``{tag}``, ``{frame}`` (0-based index on the
sheet), ``{frame01}`` (1-based index inside the tag, 2 digits),
``{tagframe}`` (0-based index inside the tag).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import List

from PIL import Image

from core.utils import sanitize_filename, write_image_sidecar

from ..models import FrameMeta, SheetMeta

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE = "{title}_{tag}_{frame01}.png"
UNTAGGED = "untagged"
TEMPLATE_FIELDS = ("title", "tag", "frame", "tagframe", "frame01")


def render_frame_name(template: str, *, title: str, tag: str, frame: int, tagframe: int) -> str:
    """Render a user-typed filename template.

    Raises ``ValueError`` naming the offending field and the supported
    field list for an unknown field (``KeyError``), a positional field
    like ``{0}`` (``IndexError``), or an unbalanced brace (``ValueError``)
    -- the ExportDialog (5b) feeds this a user string and needs a
    user-readable message, not a bare formatting exception (M2).
    """
    try:
        name = template.format(title=title, tag=tag, frame=frame, tagframe=tagframe,
                               frame01=f"{tagframe + 1:02d}")
    except (KeyError, IndexError, ValueError) as exc:
        raise ValueError(
            f"Template {template!r} is invalid ({exc}). "
            f"Supported fields: {', '.join('{' + f + '}' for f in TEMPLATE_FIELDS)}"
        ) from exc
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, "png"
    return f"{sanitize_filename(stem)}.{ext}"


def _write_frame(frame: FrameMeta, dest: Path, extra: dict) -> Path:
    if frame.source_path is None or not Path(frame.source_path).exists():
        raise FileNotFoundError(f"Frame '{frame.name}' has no source PNG: {frame.source_path}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(frame.source_path) as im:
        im.convert("RGBA").save(dest, format="PNG")
    meta = {
        "type": "sprite_frame",
        "name": frame.name,
        "duration_ms": frame.duration_ms,
        "pivot": list(frame.pivot),
        "source": str(frame.source_path),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    meta.update(extra)
    write_image_sidecar(dest, meta)
    return dest


def export_png_sequence(meta: SheetMeta, out_dir: Path,
                        template: str = DEFAULT_TEMPLATE) -> List[Path]:
    """Write every frame as its own PNG, named per tag. Returns the paths."""
    out_dir = Path(out_dir)

    # First pass: render all names and detect collisions before writing any file.
    frame_infos: List[tuple[str, FrameMeta, str, int]] = []  # (name, frame, tag_name, index)
    covered = set()
    for tag in meta.tags:
        for tagframe, frame in enumerate(meta.frames_for(tag)):
            index = tag.from_index + tagframe
            covered.add(index)
            name = render_frame_name(template, title=meta.title, tag=tag.name,
                                     frame=index, tagframe=tagframe)
            frame_infos.append((name, frame, tag.name, index))

    leftovers = [i for i in range(len(meta.frames)) if i not in covered]
    for tagframe, index in enumerate(leftovers):
        name = render_frame_name(template, title=meta.title, tag=UNTAGGED,
                                 frame=index, tagframe=tagframe)
        frame_infos.append((name, meta.frames[index], UNTAGGED, index))

    # Check for name collisions.
    names_seen = {}
    for name, _, _, _ in frame_infos:
        if name in names_seen:
            raise ValueError(f"Template '{template}' produces duplicate filename '{name}'")
        names_seen[name] = True

    # Second pass: write all frames.
    written: List[Path] = []
    for name, frame, tag_name, index in frame_infos:
        written.append(_write_frame(frame, out_dir / name, {"tag": tag_name, "index": index}))

    logger.info(f"Wrote {len(written)} PNG frames to {out_dir}")
    return written


def export_single_frame(frame: FrameMeta, out_png: Path) -> Path:
    """Write one frame as a PNG with its sidecar."""
    return _write_frame(frame, Path(out_png), {})
