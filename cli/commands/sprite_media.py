"""Headless Sprite imports, processing and exports using the shared core APIs.

The JSON options are intentionally ordinary objects: agents can select actions by
id or exact name, inspect the returned files, and resume saved stage checkpoints.
Importers stage replacements before touching an action's accepted extract output.
"""

from __future__ import annotations

import copy
import json
import math
import shutil
import tempfile
import uuid
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from core.sprite.exporters.aseprite_json import export_aseprite_json
from core.sprite.exporters.aseprite_native import export_aseprite
from core.sprite.exporters.engine_presets import ATLAS_FORMATS, ENGINE_PRESETS, FORMAT_IDS
from core.sprite.exporters.gif import export_gif
from core.sprite.exporters.godot_tres import export_godot_tres
from core.sprite.exporters.grid import GridOptions, export_grid
from core.sprite.exporters.png_sequence import (
    DEFAULT_TEMPLATE, export_png_sequence, export_single_frame, render_frame_name,
)
from core.sprite.exporters.texturepacker_json import export_texturepacker_json
from core.sprite.extract import extract_frames
from core.sprite.models import DIRECTIONS, SheetMeta
from core.sprite.pipeline import (
    PROFILE_STAGES, STAGES, CancelToken, ProgressFn, check, ensure_profile_stages,
    list_frames, record_fingerprint, register_external_frames, run_pipeline, stage_dir,
)
from core.sprite.project import ActionCard, BackgroundSettings, ClipRecord, ExtractionSettings, SpriteProject
from core.sprite.slicing import import_png_sequence, slice_sheet
from core.utils import sanitize_filename, sidecar_path

MEDIA_OPERATIONS = (
    "import-video", "import-frames", "import-sheet", "process", "export", "frame-export", "preview",
)


def _integer(value: Any, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer of at least {minimum}")
    return value


def _object(value: Any, name: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be true or false")
    return value


def _known(data: dict, fields: Any, name: str) -> None:
    unknown = set(data) - set(fields)
    if unknown:
        raise ValueError(f"Unknown {name} field(s): {', '.join(sorted(unknown))}")


def _names(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not value or any(not isinstance(x, str) or not x for x in value):
        raise ValueError(f"{name} must be a nonempty list of strings")
    if len(set(value)) != len(value):
        raise ValueError(f"{name} must not contain duplicates")
    return value


def _actions(project: SpriteProject, data: dict, *, single: bool = False) -> list[ActionCard]:
    selected = list(project.actions)
    if "actions" in data:
        selected = []
        for key in _names(data["actions"], "actions"):
            matches = [a for a in project.actions if a.id == key]
            if not matches:
                matches = [a for a in project.actions if a.name == key]
            if len(matches) != 1:
                raise ValueError(f"Action {key!r} is unknown or ambiguous; use its id")
            if matches[0] in selected:
                raise ValueError(f"Action {key!r} was selected more than once")
            selected.append(matches[0])
    if not selected:
        raise ValueError("The project has no selected actions")
    if single and len(selected) != 1:
        raise ValueError("Select exactly one action using actions: [id or exact name]")
    return selected


def _profiles(project: SpriteProject, data: dict) -> list[str]:
    names = _names(data["profiles"], "profiles") if "profiles" in data else [p.name for p in project.profiles if p.enabled]
    if not names:
        raise ValueError("Enable and select at least one output profile")
    for name in names:
        profile = project.profile(name)
        if name not in PROFILE_STAGES or profile is None or not profile.enabled:
            raise ValueError(f"Profile {name!r} is unknown or disabled")
    return names


def _input_path(value: Any) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("path must be a nonempty file path")
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Input file does not exist: {path}")
    return path


def _validate_image(path: Path) -> None:
    try:
        with Image.open(path) as image:
            image.load()
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot read image {path}: {exc}") from exc


def _sequence_paths(data: dict) -> list[Path]:
    if "paths" in data and "path" in data:
        raise ValueError("Specify paths or path, not both")
    if "paths" in data:
        if not isinstance(data["paths"], list) or not data["paths"]:
            raise ValueError("paths must be a nonempty list of file paths")
        paths = [_input_path(p) for p in data["paths"]]
    elif isinstance(data.get("path"), str) and Path(data["path"]).expanduser().is_dir():
        directory = Path(data["path"]).expanduser().resolve()
        paths = sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in
                       (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"))
    else:
        paths = [_input_path(data.get("path"))]
    if not paths:
        raise ValueError("No source images were found")
    for path in paths:
        _validate_image(path)
    return paths


def _extraction(project: SpriteProject, data: dict) -> ExtractionSettings:
    values = _object(data.get("extraction", {}), "extraction")
    _known(values, ExtractionSettings.__dataclass_fields__, "extraction")
    settings = replace(project.extraction, **values)
    if settings.mode not in ("every_n", "target_fps", "exact_n"):
        raise ValueError("extraction.mode must be every_n, target_fps, or exact_n")
    for name in ("every_n", "target_fps", "exact_n"):
        _integer(getattr(settings, name), f"extraction.{name}", 1)
    for name in ("trim_start_s", "trim_end_s", "duplicate_threshold"):
        value = getattr(settings, name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"extraction.{name} must be a finite nonnegative number")
    _boolean(settings.cull_duplicates, "extraction.cull_duplicates")
    return settings


def _import(operation: str, project: SpriteProject, data: dict, progress: ProgressFn,
            token: CancelToken | None) -> dict:
    action = _actions(project, data, single=True)[0]
    target = stage_dir(project, action, "extract")
    # Source validation happens before creating the temporary replacement directory.
    source = None
    settings = project.extraction
    paths: list[Path] = []
    sheet_args: dict = {}
    if operation == "import-frames":
        paths = _sequence_paths(data)
    else:
        source = _input_path(data.get("path"))
    if operation == "import-video":
        settings = _extraction(project, data)
    if operation == "import-sheet":
        assert source is not None
        _validate_image(source)
        columns = _integer(data.get("columns"), "columns", 1)
        rows = _integer(data.get("rows"), "rows", 1)
        margin = _integer(data.get("margin", 0), "margin")
        spacing = _integer(data.get("spacing", 0), "spacing")
        cell = data.get("cell")
        if cell is not None:
            if not isinstance(cell, list) or len(cell) != 2:
                raise ValueError("cell must contain width and height")
            cell = tuple(_integer(x, "cell size", 1) for x in cell)
        with Image.open(source) as image:
            width, height = image.size
        cw, ch = cell or ((width - 2 * margin - (columns - 1) * spacing) // columns,
                         (height - 2 * margin - (rows - 1) * spacing) // rows)
        if min(cw, ch) < 1 or 2 * margin + columns * cw + (columns - 1) * spacing > width or \
                2 * margin + rows * ch + (rows - 1) * spacing > height:
            raise ValueError("The requested grid does not fit inside the source sheet")
        sheet_args = dict(columns=columns, rows=rows, cell=(cw, ch), margin=margin, spacing=spacing)
    check(token)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".import-", dir=target.parent) as temporary:
        temp = Path(temporary)
        staged = temp / "frames"
        staged_clip = None
        clip_path = None
        if operation == "import-video":
            assert source is not None and project.project_dir is not None
            staged_clip = temp / ("clip" + source.suffix)
            shutil.copy2(source, staged_clip)
            result = extract_frames(staged_clip, staged, settings, progress=progress, token=token)
            paths = result.frames
            clip_path = project.project_dir / "clips" / f"{action.id}_import_{uuid.uuid4().hex}{source.suffix}"
        elif operation == "import-sheet":
            assert source is not None
            paths = slice_sheet(source, staged, **sheet_args)
        else:
            paths = import_png_sequence(paths, staged)
        check(token)
        if not paths:
            raise ValueError("The import produced no frames")
        before_action = copy.deepcopy(action.__dict__)
        before_fingerprints = copy.deepcopy(project.stage_fingerprints)
        before_settings = project.extraction
        before_modified = project.modified
        project_file = project.project_file()
        saved_project = temp / "previous-project.json"
        if project_file.exists():
            shutil.copy2(project_file, saved_project)
        backup = temp / "previous"
        had_output = target.exists()
        try:
            if had_output:
                target.rename(backup)
            staged.rename(target)
            if staged_clip is not None and clip_path is not None:
                clip_path.parent.mkdir(parents=True, exist_ok=True)
                staged_clip.rename(clip_path)
            action.frames = []
            action.status = "draft"
            action.error = None
            # File sizes alone cannot identify an imported image's new content.
            project.stage_fingerprints.pop(action.id, None)
            if clip_path is not None:
                action.clip = ClipRecord(clip_path, "import", "", None, settings.to_dict(), action.prompt,
                                         datetime.now().isoformat(timespec="seconds"), None, None)
                project.extraction = settings
                record_fingerprint(project, action, "extract")
            else:
                register_external_frames(project, action)
            project.save()
        except BaseException:
            # The dispatcher raises KeyboardInterrupt on Ctrl+C; it needs the
            # same rollback as an I/O failure during the short promotion step.
            action.__dict__.clear()
            action.__dict__.update(before_action)
            project.stage_fingerprints = before_fingerprints
            project.extraction = before_settings
            project.modified = before_modified
            if backup.exists():
                if target.exists():
                    shutil.rmtree(target)
                backup.rename(target)
            elif not had_output and target.exists():
                shutil.rmtree(target)
            if clip_path is not None and clip_path.exists():
                clip_path.unlink()
            if saved_project.exists():
                saved_project.replace(project_file)
            raise
    imported = list_frames(target)
    progress("import", len(imported), len(imported), f"Imported {len(imported)} frames for {action.name}")
    return {"action": action.id, "frames": len(imported), "files": [str(p) for p in imported]}


def _process(project: SpriteProject, data: dict, progress: ProgressFn, token: CancelToken | None) -> dict:
    actions = _actions(project, data)
    upto = data.get("upto", "pixel")
    if upto not in STAGES:
        raise ValueError(f"upto must be one of {', '.join(STAGES)}")
    force = _boolean(data.get("force", False), "force")
    profiles = _profiles(project, data) if "profiles" in data else None

    def checkpoint(stage: str, done: int, total: int, message: str) -> None:
        if message == f"{stage}: done":
            project.save()
        progress(stage, done, total, message)

    outputs = {}
    for action in actions:
        check(token)
        result = run_pipeline(project, action, upto=upto, profiles=profiles,
                              force=force, progress=checkpoint, token=token)
        project.save()
        outputs[action.id] = {stage: [str(p) for p in frames] for stage, frames in result.items()}
    return {"actions": [a.id for a in actions], "stages": outputs, "project": str(project.project_file())}


def _grid(values: dict, defaults: GridOptions) -> GridOptions:
    _known(values, GridOptions.__dataclass_fields__, "grid")
    merged = {**asdict(defaults), **values}
    for name in ("columns", "border_px", "shape_px", "inner_px", "extrude_px"):
        _integer(merged[name], f"grid.{name}")
    _boolean(merged["power_of_two"], "grid.power_of_two")
    scales = merged["scales"]
    if not isinstance(scales, (list, tuple)) or not scales:
        raise ValueError("grid.scales must be a nonempty list of positive integers")
    merged["scales"] = tuple(sorted({1, *(_integer(s, "grid scale", 1) for s in scales)}))
    opts = GridOptions(**merged)
    if opts.extrude_px > opts.border_px or 2 * opts.extrude_px > opts.shape_px:
        raise ValueError("Grid extrusion requires border_px >= extrude_px and shape_px >= 2 * extrude_px")
    return opts


def _tag_options(meta: SheetMeta, actions: list[ActionCard], options: dict) -> None:
    consumed = set()
    for tag, action in zip(meta.tags, actions):
        keys = [key for key in (action.id, action.name) if key in options]
        keys = list(dict.fromkeys(keys))
        if len(keys) > 1:
            raise ValueError(f"Specify tag settings once for {action.name!r}, using its id or name")
        if not keys:
            continue
        key = keys[0]
        consumed.add(key)
        values = _object(options[key], f"tags.{key}")
        _known(values, ("direction", "repeat", "fps", "durations_ms"), "tag")
        if "direction" in values:
            if values["direction"] not in DIRECTIONS:
                raise ValueError(f"direction must be one of {', '.join(DIRECTIONS)}")
            tag.direction = values["direction"]
        if "repeat" in values:
            tag.repeat = _integer(values["repeat"], "repeat")
        frames = meta.frames_for(tag)
        if "fps" in values:
            tag.fps_hint = _integer(values["fps"], "fps", 1)
            for frame in frames:
                frame.duration_ms = max(1, round(1000 / tag.fps_hint))
        if "durations_ms" in values:
            durations = values["durations_ms"]
            if not isinstance(durations, list) or len(durations) != len(frames):
                raise ValueError(f"durations_ms for {tag.name!r} needs exactly {len(frames)} entries")
            for frame, duration in zip(frames, durations):
                frame.duration_ms = _integer(duration, "duration_ms", 1)
    if consumed != set(options):
        raise ValueError(f"Unknown or unselected tag(s): {', '.join(sorted(set(options) - consumed))}")


def _prepare(project: SpriteProject, actions: list[ActionCard], profiles: list[str],
             progress: ProgressFn, token: CancelToken | None) -> list[SheetMeta]:
    for action in actions:
        if not action.frames:
            raise ValueError(f"Action {action.name!r} has no processed frames; run process first")
        check(token)
        before = copy.deepcopy(project.stage_fingerprints)
        reasons = ensure_profile_stages(project, action, profiles, progress=progress, token=token)
        if before != project.stage_fingerprints:
            project.save()
        if reasons:
            raise ValueError(f"Cannot export {action.name!r}: {reasons}. Enable the profile and run process first")
        for profile in profiles:
            for frame in action.frames:
                if frame.source_path is None or not (stage_dir(project, action, profile) / frame.source_path.name).is_file():
                    raise ValueError(f"Profile {profile!r} is incomplete for {action.name!r}; run process with force: true")
    selected = copy.copy(project)
    selected.actions = actions
    return [selected.sheet_meta(profile) for profile in profiles]


def _output(value: Any, default: Path) -> Path:
    if value is None:
        return default.resolve()
    if not isinstance(value, str) or not value.strip():
        raise ValueError("output must be a nonempty path")
    return Path(value).expanduser().resolve()


def _export(project: SpriteProject, data: dict, log: Callable, progress: ProgressFn,
            token: CancelToken | None, *, preview: bool = False) -> dict:
    actions = _actions(project, data)
    profiles = _profiles(project, data)
    preset_id = data.get("engine_preset")
    preset = ENGINE_PRESETS.get(preset_id) if isinstance(preset_id, str) else None
    if preset_id is not None and preset is None:
        raise ValueError(f"Unknown engine_preset {preset_id!r}; choose {', '.join(ENGINE_PRESETS)}")
    formats = ["gif"] if preview else _names(data.get("formats", list(preset.formats) if preset else ["grid"]), "formats")
    unknown = set(formats) - set(FORMAT_IDS)
    if unknown:
        raise ValueError(f"Unknown export format(s): {', '.join(sorted(unknown))}")
    grid = _grid(_object(data.get("grid", {}), "grid"), preset.grid if preset else GridOptions())
    template = data.get("template", preset.name_template if preset else DEFAULT_TEMPLATE)
    if not isinstance(template, str) or not template:
        raise ValueError("template must be a nonempty string")
    layout = data.get("json_layout", preset.json_layout if preset else "hash")
    if layout not in ("hash", "array"):
        raise ValueError("json_layout must be hash or array")
    pivot = data.get("pivot", list(preset.pivot) if preset else None)
    if pivot is not None and (not isinstance(pivot, list) or len(pivot) != 2 or any(
            isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not 0 <= x <= 1 for x in pivot)):
        raise ValueError("pivot must be [x,y] with normalized values from 0 to 1")
    bg_values = _object(data.get("background", {}), "background")
    _known(bg_values, BackgroundSettings.__dataclass_fields__, "background")
    background = BackgroundSettings(**{**project.background.to_dict(), **bg_values})
    if (background.mode == "original") != (project.background.mode == "original"):
        raise ValueError("Switch original background through project settings and run process before export")
    assert project.project_dir is not None
    out_dir = _output(data.get("output"), project.project_dir / "exports")
    tags = _object(data.get("tags", {}), "tags")
    metas = _prepare(project, actions, profiles, progress, token)
    for meta in metas:
        _tag_options(meta, actions, tags)
        if pivot is not None:
            for frame in meta.frames:
                frame.pivot = (float(pivot[0]), float(pivot[1]))
        # Catch invalid/colliding template names across the whole selection before writing.
        names = []
        for tag in meta.tags:
            for i, _ in enumerate(meta.frames_for(tag)):
                names.append(render_frame_name(template, title=meta.title, tag=tag.name,
                                               frame=tag.from_index + i, tagframe=i))
        if any("/" in name or "\\" in name or ":" in name for name in names):
            raise ValueError("template must produce filenames without path separators or drive prefixes")
        if "png_sequence" in formats and len(set(n.casefold() for n in names)) != len(names):
            raise ValueError("template produces duplicate filenames; include tag and frame fields")
        gif_names = [sanitize_filename(t.name).casefold() for t in meta.tags]
        if "gif" in formats and len(set(gif_names)) != len(gif_names):
            raise ValueError("Selected action names produce colliding GIF filenames; rename the actions")
    written: list[Path] = []

    def record(path: Path, *, sidecar: bool = False) -> None:
        for p in ([path, sidecar_path(path)] if sidecar else [path]):
            if p not in written:
                written.append(p)
                log(f"Wrote {p}")

    for index, meta in enumerate(metas):
        check(token)
        directory = out_dir / meta.profile
        directory.mkdir(parents=True, exist_ok=True)
        stem = f"{meta.title}_{meta.profile}"
        png = directory / f"{stem}.png"
        if ATLAS_FORMATS.intersection(formats):
            meta = export_grid(meta, png, grid)
            for scale in grid.scales:
                target = png if scale == 1 else png.with_name(f"{png.stem}@{scale}x.png")
                record(target, sidecar=True)
                record(target.with_suffix(".json"))
        for fmt in formats:
            check(token)
            progress("export", index, len(metas), f"{meta.profile}: {fmt}")
            if fmt == "grid":
                continue
            if fmt == "aseprite_json":
                path = directory / f"{stem}.aseprite.json"
                export_aseprite_json(meta, path, image_name=png.name, layout=layout)
                record(path)
            elif fmt == "texturepacker_json":
                path = directory / f"{stem}.atlas.json"
                export_texturepacker_json(meta, path, image_name=png.name, layout=layout)
                record(path)
            elif fmt == "godot_tres":
                record(export_godot_tres(meta, directory / f"{stem}.tres", atlas_res_path=f"res://{png.name}"), sidecar=True)
            elif fmt == "aseprite_native":
                record(export_aseprite(meta, directory / f"{stem}.aseprite"), sidecar=True)
            elif fmt == "png_sequence":
                for path in export_png_sequence(meta, directory / "frames", template):
                    record(path, sidecar=True)
            elif fmt == "gif":
                for tag in meta.tags:
                    check(token)
                    path = directory / f"{meta.title}_{sanitize_filename(tag.name)}.gif"
                    record(export_gif(meta, tag, path, loop=tag.repeat, background_mode=background.mode,
                                      background_color=background.color if background.mode == "solid" else None), sidecar=True)
    manifest = out_dir / "sprite-export.json"
    result = {
        "project": str(project.project_file()), "actions": [a.id for a in actions], "profiles": profiles,
        "formats": formats, "engine_preset": preset_id, "background": background.to_dict(),
        "grid": asdict(grid), "template": template, "json_layout": layout, "pivot": pivot, "tags": tags,
        "files": [str(p) for p in written], "manifest": str(manifest),
    }
    temporary = manifest.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
    temporary.replace(manifest)
    log(f"Wrote {manifest}")
    progress("export", len(metas), len(metas), "done")
    return result


def execute_media(operation: str, project: SpriteProject, data: dict, *, log: Callable,
                  progress: ProgressFn, token: CancelToken | None) -> dict:
    """Execute one media operation. Usage failures raise ValueError for the CLI envelope."""
    _object(data, "sprite data")
    if project.project_dir is None:
        raise ValueError("Save a project before importing, processing or exporting media")
    check(token)
    if operation in ("import-video", "import-frames", "import-sheet"):
        result = _import(operation, project, data, progress, token)
    elif operation == "process":
        result = _process(project, data, progress, token)
    elif operation in ("export", "preview"):
        result = _export(project, data, log, progress, token, preview=operation == "preview")
    elif operation == "frame-export":
        actions = _actions(project, data, single=True)
        profiles = _profiles(project, {"profiles": [data.get("profile", "hd")]})
        index = _integer(data.get("index", 0), "index")
        if index >= len(actions[0].frames):
            raise ValueError(f"index {index} is outside the action's {len(actions[0].frames)} frames")
        meta = _prepare(project, actions, profiles, progress, token)[0]
        path = _output(data.get("output"), project.project_dir / "exports" / profiles[0] /
                       f"{project.slug}_{sanitize_filename(actions[0].name)}_{index + 1:04d}.png")
        if path.suffix.lower() != ".png":
            raise ValueError("frame-export output must have a .png extension")
        check(token)
        export_single_frame(meta.frames[index], path)
        result = {"action": actions[0].id, "profile": profiles[0], "index": index,
                  "files": [str(path), str(sidecar_path(path))]}
    else:
        raise ValueError(f"Unknown media operation: {operation!r}")
    log(f"Sprite {operation} complete")
    return result
