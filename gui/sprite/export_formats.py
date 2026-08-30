"""Extra export formats registered into the sprite ExportDialog (sub-project 6).

``gui.sprite.export_dialog`` imports this module at load time, so the
``sheet_png_path`` import below stays inside the function.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from core.sprite.exporters.aseprite_native import export_aseprite
from core.sprite.exporters.godot_tres import export_godot_tres
from core.sprite.models import SheetMeta

logger = logging.getLogger(__name__)

FORMAT_GODOT = "godot_tres"
FORMAT_ASEPRITE = "aseprite_native"


def _stem(meta: SheetMeta) -> str:
    return f"{meta.title}_{meta.profile}"


def write_godot_tres(meta: SheetMeta, out_dir: Path) -> List[Path]:
    """``<title>_<profile>.tres`` beside the sheet PNG the export runner wrote (needs_sheet=True)."""
    from gui.sprite.export_dialog import sheet_png_path
    out_dir = Path(out_dir)
    png = sheet_png_path(meta, out_dir)
    if tuple(meta.sheet_size) == (0, 0) or not png.exists():
        raise ValueError(f"godot_tres needs the sheet PNG at {png}; register it with needs_sheet=True")
    out = export_godot_tres(meta, out_dir / f"{_stem(meta)}.tres", atlas_res_path=f"res://{png.name}")
    logger.info("Godot SpriteFrames: %s", out)
    return [out]


def write_aseprite_native(meta: SheetMeta, out_dir: Path) -> List[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = export_aseprite(meta, out_dir / f"{_stem(meta)}.aseprite")
    logger.info("Aseprite file: %s", out)
    return [out]


def register_extra_formats(dialog) -> None:
    """Register the sub-project 6 formats on an ExportDialog (5b ``register_format`` contract)."""
    dialog.register_format(FORMAT_GODOT, "Godot 4 SpriteFrames (.tres + sheet PNG)", write_godot_tres,
                           needs_sheet=True)
    dialog.register_format(FORMAT_ASEPRITE, "Aseprite file (.aseprite)", write_aseprite_native)
