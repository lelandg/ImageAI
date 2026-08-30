"""Processing spine: stage registry, cache, cancel and progress contract.

Design sections 1.1 and 1.2. Every stage reads the previous stage's PNGs
from ``stages/<action_id>/<upstream>/`` and writes ``stages/<action_id>/<stage>/``.
A stage whose recorded fingerprint equals the computed one, and whose output
directory holds frames, is skipped. Raw clips and extracted frames are never
overwritten by a later stage.

Stages are pluggable. ``register_stage`` binds a stage name to a runner, a
settings function (what the fingerprint hashes) and a code version. Sub-project
1 registers ``extract``, ``stabilize`` and ``hd`` with real runners and
``key``, ``cleanup``, ``alpha``, ``pixel`` with ``identity_runner``.
Sub-project 3 re-registers the keying stages; sub-project 4 re-registers
``pixel``. ``run_pipeline`` never needs to change for that.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PIL import Image

from .models import FrameMeta
from .project import ActionCard, SpriteProject
from core.sprite import keying

logger = logging.getLogger(__name__)


class Cancelled(Exception):
    """Raised by ``CancelToken.raise_if_cancelled`` when the user cancels."""


class CancelToken:
    """Thread-safe cancel flag. Stages poll it between frames and stages."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise Cancelled()


ProgressFn = Callable[[str, int, int, str], None]
# (stage_name, done, total, message) — done/total may be 0, 0 for indeterminate.


def no_progress(stage: str, done: int, total: int, message: str) -> None:
    """Default progress sink: does nothing."""


def check(token: Optional[CancelToken]) -> None:
    """Raise Cancelled when ``token`` is set. Safe to call with None."""
    if token is not None:
        token.raise_if_cancelled()


class PipelineError(Exception):
    """A stage cannot run. ``user_message`` is safe to show in the UI."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


# ``stabilize`` imports ``CancelToken``/``ProgressFn``/``check``/``no_progress`` from
# this module, so this import must come after those names are defined above (not at
# the very top of the file) to avoid a circular-import failure on first package load.
from .stabilize import dejitter  # noqa: E402


# --- stage registry ---------------------------------------------------------

STAGES = ("extract", "key", "cleanup", "alpha", "stabilize", "hd", "pixel")
UPSTREAM: Dict[str, Optional[str]] = {
    "extract": None,
    "key": "extract",
    "cleanup": "key",
    "alpha": "cleanup",
    "stabilize": "alpha",
    "hd": "stabilize",
    "pixel": "stabilize",
}
PROFILE_STAGES = ("hd", "pixel")

StageRunner = Callable[
    [SpriteProject, ActionCard, List[Path], Path, ProgressFn, Optional[CancelToken]], List[Path]
]
# (project, action, input_frames, out_dir, progress, token) -> output frames,
# written into out_dir as NNNN.png and returned sorted.
SettingsFn = Callable[[SpriteProject, ActionCard], Dict[str, Any]]
# Returns the JSON-able settings that decide a stage's output; the
# fingerprint hashes it, so per-frame overrides belong in it too.

STAGE_RUNNERS: Dict[str, StageRunner] = {}
STAGE_SETTINGS: Dict[str, SettingsFn] = {}
STAGE_CODE_VERSION: Dict[str, int] = {}


def _no_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    return {}


def register_stage(stage: str, runner: StageRunner, settings_fn: Optional[SettingsFn] = None,
                   code_version: int = 1) -> None:
    """Bind a stage name to its runner, settings function and code version.

    Re-registering a stage replaces all three. Bump ``code_version`` when the
    runner's output changes for the same settings, so cached frames rebuild.
    """
    if stage not in STAGES:
        raise ValueError(f"Unknown stage: {stage!r}; use one of {STAGES}")
    STAGE_RUNNERS[stage] = runner
    STAGE_SETTINGS[stage] = settings_fn or _no_settings
    STAGE_CODE_VERSION[stage] = int(code_version)


def stage_dir(project: SpriteProject, action: ActionCard, stage: str) -> Path:
    if project.project_dir is None:
        raise ValueError("project_dir is not set")
    if stage not in STAGES:
        raise ValueError(f"Unknown stage: {stage!r}")
    return project.project_dir / "stages" / action.id / stage


def list_frames(directory: Path) -> List[Path]:
    """PNG frames in a stage directory, in numeric name order."""
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.glob("*.png") if p.is_file())


# --- default settings functions (sub-project 1) -----------------------------


def _clip_info(action: ActionCard) -> Optional[Dict[str, object]]:
    if action.clip is None:
        return None
    path = Path(action.clip.path)
    info: Dict[str, object] = {"path": str(path)}
    try:
        st = path.stat()
        info["size"] = st.st_size
        info["mtime"] = int(st.st_mtime)
    except OSError:
        info["missing"] = True
    return info


def _frame_identity(path: Path) -> List[Any]:
    """``[name, size]`` for a frame, or ``[name, "missing"]`` if it's gone (M5).

    A frame removed between runs must invalidate the stage's fingerprint
    (its identity changed) rather than raise a bare ``FileNotFoundError``
    out of ``is_stage_current``/``run_pipeline``.
    """
    try:
        return [path.name, path.stat().st_size]
    except OSError:
        return [path.name, "missing"]


def extract_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    """Extraction settings plus the clip identity, or the imported file list (G9)."""
    clip = _clip_info(action)
    settings: Dict[str, Any] = {"extraction": asdict(project.extraction), "clip": clip}
    if clip is None and project.project_dir is not None:
        frames = list_frames(stage_dir(project, action, "extract"))
        settings["external"] = [_frame_identity(p) for p in frames]
    return settings


def _effective_key_settings(project: SpriteProject):
    return keying.resolve_key_settings(project.key, project.plate_color)


def _frame_override_list(project: SpriteProject, action: ActionCard) -> List[Dict[str, Any]]:
    """Per-frame overrides, one entry per *extracted* frame (design §4.1/§1.2).

    Sized off the ``extract`` stage's own output, not ``len(action.frames)``:
    ``run_pipeline`` rewrites ``action.frames`` from the ``stabilize`` output
    mid-run (``_sync_frames``), so a settings function keyed on its length
    would read a different frame count before and after that stage runs in
    the same pass -- destabilizing the ``key``/``alpha`` fingerprint on every
    run even when nothing the user controls changed.
    """
    total = len(list_frames(stage_dir(project, action, "extract"))) if project.project_dir else 0
    return [keying.frame_overrides(action.frames, i) for i in range(total)]


def key_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    s = _effective_key_settings(project)
    return {
        "method": s.method, "key_color": s.key_color, "tolerance": s.tolerance,
        "softness": s.softness, "despill": s.despill, "ml_backend": s.ml_backend,
        "ml_model": s.ml_model, "ml_refine_edges": s.ml_refine_edges,
        "overrides": _frame_override_list(project, action),
    }


def cleanup_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    s = project.key
    return {"choke_px": s.choke_px, "feather_px": s.feather_px, "despeckle_px": s.despeckle_px}


def alpha_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    s = _effective_key_settings(project)
    return {
        "method": s.method, "key_color": s.key_color, "edge_decontaminate": s.edge_decontaminate,
        "overrides": _frame_override_list(project, action),
    }


def stabilize_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    return {"stabilize": asdict(project.stabilize)}


def _profile_settings(project: SpriteProject, name: str) -> Dict[str, Any]:
    prof = project.profile(name)
    return {"profile": prof.to_dict() if prof else None, "anchor": project.stabilize.anchor}


def hd_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    return _profile_settings(project, "hd")


def pixel_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    return _profile_settings(project, "pixel")


DEFAULT_STAGE_SETTINGS: Dict[str, SettingsFn] = {
    "extract": extract_stage_settings,
    "key": key_stage_settings,
    "cleanup": cleanup_stage_settings,
    "alpha": alpha_stage_settings,
    "stabilize": stabilize_stage_settings,
    "hd": hd_stage_settings,
    "pixel": pixel_stage_settings,
}
for _stage, _settings_fn in DEFAULT_STAGE_SETTINGS.items():
    STAGE_SETTINGS[_stage] = _settings_fn
    STAGE_CODE_VERSION[_stage] = 1


# --- fingerprints ------------------------------------------------------------


def stage_settings(project: SpriteProject, action: ActionCard, stage: str) -> Dict[str, Any]:
    """The registered settings for a stage (empty dict when none is registered)."""
    if stage not in STAGES:
        raise ValueError(f"Unknown stage: {stage!r}")
    return STAGE_SETTINGS.get(stage, _no_settings)(project, action)


def stage_fingerprint(project: SpriteProject, action: ActionCard, stage: str) -> str:
    """SHA-1 of (upstream fingerprint + stage settings JSON + stage code version)."""
    upstream = UPSTREAM[stage]
    parent = stage_fingerprint(project, action, upstream) if upstream else ""
    payload = json.dumps(
        {"parent": parent, "settings": stage_settings(project, action, stage),
         "code": STAGE_CODE_VERSION.get(stage, 1)},
        sort_keys=True, default=str,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def is_stage_current(project: SpriteProject, action: ActionCard, stage: str) -> bool:
    recorded = project.stage_fingerprints.get(action.id, {}).get(stage)
    if recorded is None:
        return False
    if not list_frames(stage_dir(project, action, stage)):
        return False
    return recorded == stage_fingerprint(project, action, stage)


def record_fingerprint(project: SpriteProject, action: ActionCard, stage: str) -> str:
    fp = stage_fingerprint(project, action, stage)
    project.stage_fingerprints.setdefault(action.id, {})[stage] = fp
    return fp


def register_external_frames(project: SpriteProject, action: ActionCard) -> List[Path]:
    """Mark frames placed in the extract directory by an import as current (G9).

    ``slicing.import_png_sequence`` and ``slicing.slice_sheet`` write into
    ``stage_dir(project, action, "extract")``. Calling this afterwards is
    optional: ``run_pipeline`` also accepts a populated extract directory
    with ``action.clip is None`` and treats extraction as done. This helper
    records the fingerprint up front and clears a stale clip reference.
    """
    frames = list_frames(stage_dir(project, action, "extract"))
    if not frames:
        raise PipelineError("No frames were imported for this action")
    action.clip = None
    record_fingerprint(project, action, "extract")
    return frames


def _reset_dir(directory: Path) -> Path:
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True)
    return directory


# --- default runners (sub-project 1) ------------------------------------------


def identity_runner(project: SpriteProject, action: ActionCard, input_frames: List[Path],
                    out_dir: Path, progress: ProgressFn, token: Optional[CancelToken]) -> List[Path]:
    """Copy every input frame unchanged. The placeholder for stages later sub-projects fill."""
    stage = out_dir.name
    _reset_dir(out_dir)
    written: List[Path] = []
    total = len(input_frames)
    for index, path in enumerate(input_frames, start=1):
        check(token)
        dest = out_dir / path.name
        shutil.copy2(path, dest)
        written.append(dest)
        progress(stage, index, total, f"{stage}: {path.name}")
    return written


def extract_runner(project: SpriteProject, action: ActionCard, input_frames: List[Path],
                   out_dir: Path, progress: ProgressFn, token: Optional[CancelToken]) -> List[Path]:
    """Extract from ``action.clip``; or accept frames an importer placed in ``out_dir``."""
    from .extract import extract_frames

    if action.clip is not None:
        clip = Path(action.clip.path)
        if not clip.exists():
            raise PipelineError(f"Clip not found: {clip}")
        result = extract_frames(clip, out_dir, project.extraction, progress=progress, token=token)
        return result.frames
    frames = list_frames(out_dir)
    if not frames:
        raise PipelineError(
            f"Action '{action.name}' has no clip and no imported frames; "
            "render it or import a video, PNG sequence, or sheet first"
        )
    return frames


def key_runner(project: SpriteProject, action: ActionCard, input_frames: List[Path],
               out_dir: Path, progress: ProgressFn, token: Optional[CancelToken]) -> List[Path]:
    """Estimate alpha and despill every frame (chroma, ml, or none; per-frame overrides apply)."""
    settings = _effective_key_settings(project)
    _reset_dir(out_dir)
    outputs: List[Path] = []
    total = len(input_frames)
    for index, src in enumerate(input_frames):
        check(token)
        overrides = keying.frame_overrides(action.frames, index)
        rgb, alpha, _key = keying.key_pass(Image.open(src), settings, overrides, frame_name=src.name)
        dst = out_dir / src.name
        keying.compose_rgba(rgb, alpha).save(dst)
        outputs.append(dst)
        progress("key", index + 1, total, f"key {src.name}")
    return outputs


def cleanup_runner(project: SpriteProject, action: ActionCard, input_frames: List[Path],
                   out_dir: Path, progress: ProgressFn, token: Optional[CancelToken]) -> List[Path]:
    """Choke/feather/despeckle the alpha the ``key`` stage produced."""
    _reset_dir(out_dir)
    outputs: List[Path] = []
    total = len(input_frames)
    for index, src in enumerate(input_frames):
        check(token)
        rgb, alpha = keying.split_rgba(Image.open(src))
        alpha = keying.cleanup_pass(alpha, project.key)
        dst = out_dir / src.name
        keying.compose_rgba(rgb, alpha).save(dst)
        outputs.append(dst)
        progress("cleanup", index + 1, total, f"cleanup {src.name}")
    return outputs


def alpha_runner(project: SpriteProject, action: ActionCard, input_frames: List[Path],
                 out_dir: Path, progress: ProgressFn, token: Optional[CancelToken]) -> List[Path]:
    """Decontaminate spill on the keyed edges (chroma only) and finalize the RGBA."""
    settings = _effective_key_settings(project)
    _reset_dir(out_dir)
    outputs: List[Path] = []
    total = len(input_frames)
    for index, src in enumerate(input_frames):
        check(token)
        eff = keying.apply_overrides(settings, keying.frame_overrides(action.frames, index), frame_name=src.name)
        key_rgb = (keying.parse_key_color(eff.key_color, context=src.name)
                  if (eff.method == "chroma" and eff.key_color) else None)
        rgb, alpha = keying.split_rgba(Image.open(src))
        dst = out_dir / src.name
        keying.alpha_pass(rgb, alpha, key_rgb, eff).save(dst)
        outputs.append(dst)
        progress("alpha", index + 1, total, f"alpha {src.name}")
    return outputs


def stabilize_runner(project: SpriteProject, action: ActionCard, input_frames: List[Path],
                     out_dir: Path, progress: ProgressFn, token: Optional[CancelToken]) -> List[Path]:
    """Crop every frame to the union bbox plus ``pad_px``; no resampling. Then de-jitter."""
    from .stabilize import crop_and_pad, has_transparency, solid_border_bbox, union_alpha_bbox

    if not input_frames:
        raise PipelineError("No frames to stabilize")
    if has_transparency(input_frames[0]):
        bbox = union_alpha_bbox(input_frames)
    else:
        bbox = solid_border_bbox(input_frames)
    pad = max(0, project.stabilize.pad_px)
    cell = (bbox[2] + 2 * pad, bbox[3] + 2 * pad)
    _reset_dir(out_dir)
    padded = crop_and_pad(input_frames, out_dir, bbox, cell, anchor=project.stabilize.anchor,
                          pad_px=pad, stage=out_dir.name, progress=progress, token=token)
    if project.stabilize.dejitter:
        padded = dejitter(padded, out_dir, project.stabilize.dejitter_method,
                          progress=progress, token=token)
    return padded


def hd_runner(project: SpriteProject, action: ActionCard, input_frames: List[Path],
              out_dir: Path, progress: ProgressFn, token: Optional[CancelToken]) -> List[Path]:
    """Scale the stabilised frames proportionally into the hd profile cell.

    The ``hd`` profile keeps the anti-aliased alpha the keying stages produced
    unless ``binary_alpha`` is set, in which case ``apply_profile_alpha``
    thresholds it (the HD alpha guarantee).
    """
    from .stabilize import crop_and_pad

    prof = project.profile("hd")
    if prof is None or not input_frames:
        raise PipelineError("hd profile is missing")
    with Image.open(input_frames[0]) as first:
        w, h = first.size
    _reset_dir(out_dir)
    written = crop_and_pad(input_frames, out_dir, (0, 0, w, h), prof.cell_size,
                           anchor=project.stabilize.anchor, pad_px=0,
                           upscale_small=prof.upscale_small, resample_method=prof.upscale_method,
                           stage=out_dir.name, progress=progress, token=token)
    for dst in written:
        with Image.open(dst) as img:
            keying.apply_profile_alpha(img, prof).save(dst)
    return written


register_stage("extract", extract_runner, extract_stage_settings)
register_stage("key", key_runner, key_stage_settings, code_version=2)
register_stage("cleanup", cleanup_runner, cleanup_stage_settings, code_version=2)
register_stage("alpha", alpha_runner, alpha_stage_settings, code_version=2)
register_stage("stabilize", stabilize_runner, stabilize_stage_settings, code_version=2)
register_stage("hd", hd_runner, hd_stage_settings, code_version=2)
register_stage("pixel", identity_runner, pixel_stage_settings)


# --- the runner loop ----------------------------------------------------------


def _sync_frames(action: ActionCard, frames: List[Path]) -> None:
    """Rebuild ``action.frames`` after a stabilize run, keeping user edits.

    The entry at each index carries over ``duration_ms``, ``pivot`` and
    ``overrides`` from the previous ``FrameMeta`` at the same index, so a
    per-frame keying override or an edited duration survives a re-run and
    the key fingerprint stays stable. Indices beyond the old list get
    defaults; old entries beyond the new count are dropped.
    """
    rebuilt: List[FrameMeta] = []
    for index, path in enumerate(frames):
        with Image.open(path) as im:
            w, h = im.size
        prev = action.frames[index] if index < len(action.frames) else None
        rebuilt.append(FrameMeta(
            name=f"{action.name}_{index:02d}",
            source_path=path,
            frame=(0, 0, w, h),
            sprite_source_size=(0, 0, w, h),
            source_size=(w, h),
            duration_ms=prev.duration_ms if prev else round(1000 / max(1, action.fps)),
            pivot=prev.pivot if prev else (0.5, 1.0),
            overrides=dict(prev.overrides) if prev else {},
        ))
    action.frames = rebuilt


def run_pipeline(project: SpriteProject, action: ActionCard, *, upto: str = "pixel",
                 progress: ProgressFn = no_progress, token: Optional[CancelToken] = None,
                 force: bool = False) -> Dict[str, List[Path]]:
    """Run every registered stage up to and including ``upto``; return stage -> frames.

    Each stage's runner receives the previous stage's output list (``[]`` for
    ``extract``). Cached stages are skipped unless ``force`` is set. A disabled
    profile stage is skipped and absent from the result. After ``stabilize``
    runs, ``action.frames`` is rebuilt from its output. ``project.stage_fingerprints``
    is updated in place; the caller saves the project.
    """
    if upto not in STAGES:
        raise ValueError(f"Unknown stage: {upto!r}")
    if project.project_dir is None:
        raise ValueError("project_dir is not set")
    outputs: Dict[str, List[Path]] = {}
    stop = STAGES.index(upto)
    for stage in STAGES[:stop + 1]:
        check(token)
        if stage in PROFILE_STAGES:
            prof = project.profile(stage)
            if prof is None or not prof.enabled:
                continue
        runner = STAGE_RUNNERS.get(stage)
        if runner is None:
            raise PipelineError(f"No runner is registered for stage {stage!r}")
        out_dir = stage_dir(project, action, stage)
        if not force and is_stage_current(project, action, stage):
            outputs[stage] = list_frames(out_dir)
            if stage == "stabilize" and not action.frames:
                # A project whose frames list was cleared (or hand-edited)
                # would otherwise stay frameless forever, since a cached
                # stage never reaches the _sync_frames call below (M6).
                # Only the empty case rebuilds -- a non-empty list is left
                # alone so user deletions are never undone by a cache hit.
                _sync_frames(action, outputs[stage])
            progress(stage, 0, 0, f"{stage}: cached")
            continue
        upstream = UPSTREAM[stage]
        input_frames = outputs.get(upstream, []) if upstream else []
        progress(stage, 0, 0, f"{stage}: running")
        frames = runner(project, action, input_frames, out_dir, progress, token)
        if stage == "stabilize":
            _sync_frames(action, frames)
        outputs[stage] = frames
        record_fingerprint(project, action, stage)
        progress(stage, len(frames), len(frames), f"{stage}: done")
    if action.frames and action.status in ("rendered", "draft"):
        action.status = "processed"
    return outputs
