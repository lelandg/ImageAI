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
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .project import ActionCard, SpriteProject

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


def extract_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    """Extraction settings plus the clip identity, or the imported file list (G9)."""
    clip = _clip_info(action)
    settings: Dict[str, Any] = {"extraction": asdict(project.extraction), "clip": clip}
    if clip is None and project.project_dir is not None:
        frames = list_frames(stage_dir(project, action, "extract"))
        settings["external"] = [[p.name, p.stat().st_size] for p in frames]
    return settings


def key_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    return {"key": asdict(project.key), "plate_color": project.plate_color}


def cleanup_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    key = asdict(project.key)
    return {k: key[k] for k in ("despill", "edge_decontaminate", "choke_px", "feather_px", "despeckle_px")}


def alpha_stage_settings(project: SpriteProject, action: ActionCard) -> Dict[str, Any]:
    return {"method": project.key.method, "ml_refine_edges": project.key.ml_refine_edges}


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
