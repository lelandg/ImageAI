"""Engine presets: one call exports everything an engine needs from a SheetMeta."""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from core.sprite.exporters.aseprite_json import export_aseprite_json
from core.sprite.exporters.gif import export_gif
from core.sprite.exporters.godot_tres import export_godot_tres, ordered_frame_indices
from core.sprite.exporters.grid import GridOptions, export_grid
from core.sprite.exporters.png_sequence import export_png_sequence
from core.sprite.exporters.texturepacker_json import export_texturepacker_json
from core.sprite.models import SheetMeta
from core.sprite.timing import ms_to_fps
from core.utils import read_image_sidecar, sanitize_filename, sidecar_path, write_image_sidecar

logger = logging.getLogger(__name__)

FORMAT_IDS: Tuple[str, ...] = (
    "grid", "aseprite_json", "texturepacker_json", "png_sequence", "gif", "godot_tres", "aseprite_native",
)
# Formats that need frame rects from export_grid before they can run.
ATLAS_FORMATS = {"grid", "aseprite_json", "texturepacker_json", "godot_tres"}
GIF_MIN_MS = 20


@dataclass(frozen=True)
class EnginePreset:
    id: str
    label: str
    formats: Tuple[str, ...]
    grid: GridOptions
    pivot: Tuple[float, float]          # normalized, y down; (0.5, 1.0) = bottom-center
    name_template: str                  # png_sequence template
    how_to_import: str
    json_layout: str = "hash"           # aseprite_json / texturepacker_json layout


_DEFAULT_TEMPLATE = "{title}_{tag}_{frame01}.png"

ENGINE_PRESETS: Dict[str, EnginePreset] = {p.id: p for p in (
    EnginePreset(
        id="unity", label="Unity (Sprite Editor / TexturePacker JSON)",
        formats=("grid", "texturepacker_json"),
        grid=GridOptions(columns=0, border_px=1, shape_px=2, inner_px=0, extrude_px=1, power_of_two=False),
        pivot=(0.5, 1.0), name_template=_DEFAULT_TEMPLATE,
        how_to_import=(
            "Import the PNG with Texture Type = Sprite (2D and UI), Sprite Mode = Multiple, and Filter Mode = Point for pixel art. "
            "Open the Sprite Editor and slice with Grid By Cell Size using the cell size from the JSON, or install the TexturePacker Importer package and let it read the .atlas.json. "
            "Set the pivot to Bottom so the feet stay planted."
        ),
    ),
    EnginePreset(
        id="godot4", label="Godot 4 (SpriteFrames .tres)",
        formats=("grid", "godot_tres"),
        grid=GridOptions(columns=0, border_px=0, shape_px=1, inner_px=0, extrude_px=0, power_of_two=False),
        pivot=(0.5, 1.0), name_template=_DEFAULT_TEMPLATE,
        how_to_import=(
            "Copy the PNG and the .tres into the same folder of the Godot project. "
            "Select the PNG, set Filter to Nearest in the Import dock for pixel art, and click Reimport. "
            "Add an AnimatedSprite2D node and assign the .tres as its Sprite Frames. "
            "The .tres references the PNG as res://<png name>, so keep the two files together."
        ),
    ),
    EnginePreset(
        id="phaser3", label="Phaser 3 (atlas JSON hash)",
        formats=("grid", "texturepacker_json"),
        grid=GridOptions(columns=0, border_px=1, shape_px=2, inner_px=0, extrude_px=1, power_of_two=False),
        pivot=(0.5, 1.0), name_template=_DEFAULT_TEMPLATE,
        how_to_import=(
            "Load the atlas in preload() with this.load.atlas('hero', 'hero.png', 'hero.atlas.json'). "
            "Create each animation with this.anims.create({ key: 'walk', frames: this.anims.generateFrameNames('hero', { prefix: 'hero_walk_', start: 1, end: N, zeroPad: 2 }), frameRate: fps, repeat: -1 }). "
            "Set pixelArt: true in the game config for crisp scaling."
        ),
    ),
    EnginePreset(
        id="pixijs", label="PixiJS (spritesheet JSON hash)",
        formats=("grid", "texturepacker_json"),
        grid=GridOptions(columns=0, border_px=1, shape_px=2, inner_px=0, extrude_px=1, power_of_two=False),
        pivot=(0.5, 1.0), name_template=_DEFAULT_TEMPLATE,
        how_to_import=(
            "Load the sheet with const sheet = await Assets.load('hero.atlas.json'); PixiJS resolves the PNG from meta.image. "
            "Build an AnimatedSprite with new AnimatedSprite(sheet.animations['walk']) and set animationSpeed to fps / 60. "
            "Set the texture scale mode to nearest for pixel art."
        ),
    ),
    EnginePreset(
        id="unreal", label="Unreal Engine 5 (Paper2D)",
        formats=("grid", "texturepacker_json"),
        grid=GridOptions(columns=0, border_px=1, shape_px=2, inner_px=0, extrude_px=1, power_of_two=False),
        pivot=(0.5, 1.0), name_template=_DEFAULT_TEMPLATE, json_layout="array",
        how_to_import=(
            "Import the PNG into the Content Browser, then import the .atlas.json; Paper2D reads TexturePacker array JSON and creates one Paper Sprite per frame. "
            "Right-click the texture and choose Sprite Actions > Apply Paper2D Texture Settings for nearest filtering. "
            "Create a Flipbook from the sprites and set Frames Per Second to the fps value."
        ),
    ),
    EnginePreset(
        id="libgdx", label="libGDX (grid + TextureRegion.split)",
        formats=("grid", "aseprite_json"),
        grid=GridOptions(columns=0, border_px=0, shape_px=0, inner_px=0, extrude_px=0, power_of_two=True),
        pivot=(0.5, 1.0), name_template=_DEFAULT_TEMPLATE,
        how_to_import=(
            "Load the PNG as a Texture and call TextureRegion.split(texture, cellWidth, cellHeight); the cell size and the per-tag rows are in the JSON. "
            "Build one Animation<TextureRegion> per tag with frameDuration = 1f / fps. "
            "Set the texture filter to Nearest for pixel art."
        ),
    ),
    EnginePreset(
        id="rpgmaker_mz", label="RPG Maker MZ (character sheet)",
        formats=("grid",),
        grid=GridOptions(columns=3, border_px=0, shape_px=0, inner_px=0, extrude_px=0, power_of_two=False),
        pivot=(0.5, 1.0), name_template=_DEFAULT_TEMPLATE,
        how_to_import=(
            "RPG Maker MZ expects 3 columns per walk cycle and 48x48 cells, so export the pixel profile with a 48x48 cell. "
            "Copy the PNG into img/characters and prefix the file name with $ so MZ reads it as a single-character sheet. "
            "Rows map to down, left, right, and up in that order."
        ),
    ),
    EnginePreset(
        id="web_preview", label="Web preview (GIF + PNG frames)",
        formats=("gif", "png_sequence"),
        grid=GridOptions(),
        pivot=(0.5, 1.0), name_template=_DEFAULT_TEMPLATE,
        how_to_import=(
            "Open a GIF in any browser or image viewer to check the loop. "
            "Use the PNG frames for hand-placed HTML or CSS sprite animations."
        ),
    ),
)}


def _title(meta: SheetMeta) -> str:
    return sanitize_filename(meta.title) or "sprite"


def with_pivot(meta: SheetMeta, pivot: Tuple[float, float]) -> SheetMeta:
    """Deep copy of ``meta`` with every frame pivot set to ``pivot`` (engine presets own the pivot)."""
    copied = copy.deepcopy(meta)
    for frame in copied.frames:
        frame.pivot = (float(pivot[0]), float(pivot[1]))
    return copied


Writer = Callable[[SheetMeta, Path, str, EnginePreset], List[Path]]


def _write_aseprite_json(meta: SheetMeta, out_dir: Path, title: str, preset: EnginePreset) -> List[Path]:
    out = out_dir / f"{title}.aseprite.json"
    export_aseprite_json(meta, out, image_name=f"{title}.png", layout=preset.json_layout)
    return [out]


def _write_texturepacker_json(meta: SheetMeta, out_dir: Path, title: str, preset: EnginePreset) -> List[Path]:
    out = out_dir / f"{title}.atlas.json"
    export_texturepacker_json(meta, out, image_name=f"{title}.png", layout=preset.json_layout)
    return [out]


def _write_godot_tres(meta: SheetMeta, out_dir: Path, title: str, preset: EnginePreset) -> List[Path]:
    out = export_godot_tres(meta, out_dir / f"{title}.tres", atlas_res_path=f"res://{title}.png")
    return [out, sidecar_path(out)]


def _write_png_sequence(meta: SheetMeta, out_dir: Path, title: str, preset: EnginePreset) -> List[Path]:
    pngs = list(export_png_sequence(meta, out_dir / "frames", template=preset.name_template))
    return [p for png in pngs for p in (png, sidecar_path(png))]


def _write_gif(meta: SheetMeta, out_dir: Path, title: str, preset: EnginePreset) -> List[Path]:
    paths: List[Path] = []
    for tag in meta.tags:
        # The title is sanitised by the caller; the tag name is user text and
        # must not carry a path separator into the file name (PR #45 review).
        out = export_gif(meta, tag, out_dir / f"{title}_{sanitize_filename(tag.name)}.gif")
        # export_gif already wrote a sidecar with the correct unrolled frame
        # count plus durations_ms/loop/warnings/timestamp -- merge the preset
        # fields into it instead of overwriting, and derive "frames" the same
        # way the exporter did (ordered_frame_indices), so a pingpong/reverse
        # tag's sidecar never disagrees with the GIF it describes.
        sidecar = read_image_sidecar(out) or {}
        sidecar.update({
            "format": "gif", "title": meta.title, "tag": tag.name, "profile": meta.profile,
            "frames": len(ordered_frame_indices(tag)), "direction": tag.direction,
            "app": meta.app, "version": meta.version,
        })
        write_image_sidecar(out, sidecar)
        paths.extend([out, sidecar_path(out)])
    return paths


def _write_aseprite_native(meta: SheetMeta, out_dir: Path, title: str, preset: EnginePreset) -> List[Path]:
    from core.sprite.exporters.aseprite_native import export_aseprite  # Task 3
    out = export_aseprite(meta, out_dir / f"{title}.aseprite")
    return [out, sidecar_path(out)]


FORMAT_WRITERS: Dict[str, Writer] = {
    "aseprite_json": _write_aseprite_json,
    "texturepacker_json": _write_texturepacker_json,
    "godot_tres": _write_godot_tres,
    "png_sequence": _write_png_sequence,
    "gif": _write_gif,
    "aseprite_native": _write_aseprite_native,
}


def _grid_output_paths(png: Path, scales: Tuple[int, ...]) -> List[Path]:
    """Every file ``export_grid`` writes for ``png``, across every scale in ``scales``.

    ``export_grid`` (``core/sprite/exporters/grid.py``) writes, for each entry
    in ``opts.scales``: the sheet PNG itself (``<stem>.png``, or
    ``<stem>@Nx.png`` for ``scale != 1``), its Aseprite JSON sidecar
    (``target.with_suffix(".json")``), and the ImageAI metadata sidecar
    (``sidecar_path(target)``, e.g. ``hero.png.json``) -- unconditionally,
    for every scale. The manifest must list all three per scale, not just
    the first sidecar found, or a consumer copying/zipping from this list
    silently drops real files.
    """
    paths: List[Path] = []
    for scale in scales:
        target = png if scale == 1 else png.with_name(f"{png.stem}@{scale}x{png.suffix}")
        paths.extend([target, target.with_suffix(".json"), sidecar_path(target)])
    return paths


def export_with_preset(meta: SheetMeta, preset_id: str, out_dir: Path) -> List[Path]:
    """Run every exporter of ``preset_id`` into ``out_dir``; return the written paths."""
    preset = ENGINE_PRESETS.get(preset_id)
    if preset is None:
        raise ValueError(f"Unknown engine preset {preset_id!r}; known: {', '.join(sorted(ENGINE_PRESETS))}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    title = _title(meta)
    meta = with_pivot(meta, preset.pivot)
    written: List[Path] = []
    laid = meta
    if ATLAS_FORMATS.intersection(preset.formats):
        png = out_dir / f"{title}.png"
        laid = export_grid(meta, png, preset.grid)
        written.extend(_grid_output_paths(png, preset.grid.scales))
    for fmt in preset.formats:
        if fmt == "grid":
            continue
        writer = FORMAT_WRITERS.get(fmt)
        if writer is None:
            raise ValueError(f"Preset {preset_id!r} names unknown format {fmt!r}")
        written.extend(writer(laid, out_dir, title, preset))
    logger.info("Engine preset %s exported %d file(s) to %s", preset_id, len(written), out_dir)
    return written


def fps_reconciliation(meta: SheetMeta, target: str) -> List[str]:
    """Human-readable notes about timing that the target cannot represent exactly."""
    notes: List[str] = []
    if target == "godot":
        for tag in meta.tags:
            indices = ordered_frame_indices(tag)
            durations = [meta.frames[i].duration_ms for i in indices]
            if not durations:
                continue
            fps, multipliers = ms_to_fps(durations)
            base_ms = 1000.0 / fps
            for i, (orig, mult) in enumerate(zip(durations, multipliers), start=1):
                # mult is defined as orig*fps/1000, so mult*base_ms always reproduces orig
                # exactly (SpriteFrames stores mult verbatim as a float "duration" field) --
                # that path never drifts. The real reconciliation risk is a *fractional*
                # multiplier: an importer or hand-edit that only honours whole-frame
                # durations rounds it, and that rounding is what actually drifts.
                if abs(mult - round(mult)) > 1e-6:
                    played = round(mult) * base_ms
                    drift = played - orig
                    notes.append(
                        f"Godot: tag '{tag.name}' frame {i} needs a fractional duration "
                        f"({mult:.2f} at {fps} fps) to reproduce {orig} ms exactly; a tool that "
                        f"rounds to whole frames plays {played:.1f} ms instead (drift {drift:+.1f} ms)."
                    )
            if tag.direction != "forward":
                notes.append(
                    f"Godot: tag '{tag.name}' direction '{tag.direction}' is unrolled into "
                    f"{len(indices)} frames because SpriteFrames has no direction field."
                )
            if tag.repeat > 1:
                notes.append(f"Godot: tag '{tag.name}' repeat={tag.repeat} becomes loop=false; Godot loops forever or plays once.")
        return notes
    if target == "gif":
        for i, frame in enumerate(meta.frames, start=1):
            ms = frame.duration_ms
            if ms < GIF_MIN_MS:
                notes.append(f"GIF: frame {i} duration {ms} ms is below {GIF_MIN_MS} ms; the exporter writes 20 ms and browsers may clamp it to 100 ms.")
            elif ms % 10:
                notes.append(f"GIF: frame {i} duration {ms} ms rounds to {round(ms / 10) * 10} ms because GIF stores centiseconds.")
        return notes
    raise ValueError(f"Unknown reconciliation target {target!r}; use 'godot' or 'gif'")
