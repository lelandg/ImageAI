"""Sprite project model and persistence (design section 2 and 1.6).

A project lives in ``<Images root>/sprites/<slug>_<timestamp>/`` and is
saved as ``project.iasprite.json``. Media paths are stored absolute; ``load``
re-anchors them under the current project directory after a storage move,
the way ``core.video.project.VideoProject`` does.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.recycle_bin import send_to_recycle_bin
from core.utils import sanitize_filename

from .models import FrameMeta, SheetMeta, Size, TagMeta

logger = logging.getLogger(__name__)

PROJECT_FILE_NAME = "project.iasprite.json"
PROJECT_SUBDIRS = ("source", "clips", "stages", "exports")
SPRITES_DIR_NAME = "sprites"  # the DataPaths.sprite_projects() leaf name

# Interim fix (final-review Minor 4): serializes the tmp-write-and-replace in
# SpriteProject.save() so the queue worker thread and a GUI-thread autosave
# never race on the same project file. One process-wide lock for every
# project is coarser than necessary; the single-writer redesign (the GUI
# owns every save, the worker only requests one) is deferred to sub-project 5b.
_SAVE_LOCK = threading.RLock()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _path_or_none(value: Any) -> Optional[Path]:
    return Path(value) if value else None


def _reanchored(path: Optional[Path], project_dir: Optional[Path]) -> Optional[Path]:
    """Point ``path`` at ``project_dir`` when the stored copy is gone.

    Stored paths are absolute. After a storage move they still name the old
    root. When the stored path is missing, rebuild its tail under the current
    project directory and use that only when the file really exists there.
    A path this cannot resolve comes back unchanged.
    """
    if path is None or project_dir is None:
        return path
    try:
        if path.exists():
            return path
    except OSError:
        return path
    parts = path.parts
    for index, part in enumerate(parts):
        if part == project_dir.name and index + 1 < len(parts):
            candidate = project_dir.joinpath(*parts[index + 1:])
            if candidate.exists():
                return candidate
    for index, part in enumerate(parts):
        if part == SPRITES_DIR_NAME and index + 2 < len(parts):
            candidate = project_dir.joinpath(*parts[index + 2:])
            if candidate.exists():
                return candidate
    return path


# --- settings dataclasses ---------------------------------------------------


@dataclass
class GenerationSettings:
    provider: str = "omni"
    model: str = ""
    resolution: str = "720p"
    aspect_ratio: str = "16:9"
    duration_s: int = 8
    fps: int = 24
    loop_conditioning: bool = True
    plate_color: str = "#00FF00"
    use_turnaround_refs: bool = True
    include_audio: bool = False
    config_name: str = "Default"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GenerationSettings":
        return cls(**{k: v for k, v in (data or {}).items() if k in cls.__dataclass_fields__})


@dataclass
class ExtractionSettings:
    mode: str = "every_n"  # every_n | target_fps | exact_n
    every_n: int = 8
    target_fps: int = 12
    exact_n: int = 8
    trim_start_s: float = 0.0
    trim_end_s: float = 0.0
    cull_duplicates: bool = False
    duplicate_threshold: float = 0.02

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractionSettings":
        return cls(**{k: v for k, v in (data or {}).items() if k in cls.__dataclass_fields__})


@dataclass
class KeySettings:
    method: str = "chroma"  # chroma | ml | none
    key_color: Optional[str] = None
    tolerance: float = 0.20
    softness: float = 0.10
    despill: str = "average"
    edge_decontaminate: bool = True
    choke_px: int = 0
    feather_px: int = 0
    despeckle_px: int = 0
    ml_backend: str = "mediapipe"
    ml_model: str = "isnet-anime"
    ml_refine_edges: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KeySettings":
        return cls(**{k: v for k, v in (data or {}).items() if k in cls.__dataclass_fields__})


@dataclass
class StabilizeSettings:
    anchor: str = "bottom_center"
    dejitter: bool = True
    dejitter_method: str = "phase"
    pad_px: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StabilizeSettings":
        return cls(**{k: v for k, v in (data or {}).items() if k in cls.__dataclass_fields__})


@dataclass
class OutputProfile:
    name: str
    enabled: bool = True
    cell_size: Size = (64, 64)
    binary_alpha: bool = False
    alpha_threshold: int = 128
    defringe_px: int = 0
    palette_size: Optional[int] = None
    dither: str = "none"
    palette_lock: bool = True
    locked_palette: Optional[List[str]] = None
    upscale_small: bool = False        # pixel: upscale a source smaller than the cell (sub-project 4)
    upscale_method: str = "lanczos"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["cell_size"] = list(self.cell_size)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OutputProfile":
        cell = data.get("cell_size", (64, 64))
        locked = data.get("locked_palette")
        return cls(
            name=str(data.get("name", "hd")),
            enabled=bool(data.get("enabled", True)),
            cell_size=(int(cell[0]), int(cell[1])),
            binary_alpha=bool(data.get("binary_alpha", False)),
            alpha_threshold=int(data.get("alpha_threshold", 128)),
            defringe_px=int(data.get("defringe_px", 0)),
            palette_size=int(data["palette_size"]) if data.get("palette_size") is not None else None,
            dither=str(data.get("dither", "none")),
            palette_lock=bool(data.get("palette_lock", True)),
            locked_palette=[str(c) for c in locked] if locked is not None else None,
            upscale_small=bool(data.get("upscale_small", False)),
            upscale_method=str(data.get("upscale_method", "lanczos")),
        )


def default_profiles() -> List[OutputProfile]:
    """The two profiles every new project starts with, both enabled (decision 2)."""
    return [
        OutputProfile(name="hd", enabled=True, cell_size=(256, 256)),
        OutputProfile(
            name="pixel", enabled=True, cell_size=(64, 64), binary_alpha=True,
            palette_size=32, dither="none",
        ),
    ]


# --- records ---------------------------------------------------------------


@dataclass
class ClipRecord:
    path: Path
    provider: str
    model: str
    operation_id: Optional[str]
    params: Dict[str, Any]
    prompt: str
    generated_at: str
    estimated_usd: Optional[float]
    actual_usd: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": str(self.path),
            "provider": self.provider,
            "model": self.model,
            "operation_id": self.operation_id,
            "params": dict(self.params),
            "prompt": self.prompt,
            "generated_at": self.generated_at,
            "estimated_usd": self.estimated_usd,
            "actual_usd": self.actual_usd,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClipRecord":
        return cls(
            path=Path(data["path"]),
            provider=str(data.get("provider", "")),
            model=str(data.get("model", "")),
            operation_id=data.get("operation_id"),
            params=dict(data.get("params") or {}),
            prompt=str(data.get("prompt", "")),
            generated_at=str(data.get("generated_at", "")),
            estimated_usd=data.get("estimated_usd"),
            actual_usd=data.get("actual_usd"),
        )


@dataclass
class ActionCard:
    id: str
    name: str
    prompt: str
    duration_s: int = 8
    loop: bool = True
    target_frames: int = 8
    fps: int = 12
    status: str = "draft"  # draft | queued | rendering | rendered | failed | processed
    error: Optional[str] = None
    clip: Optional[ClipRecord] = None
    frames: List[FrameMeta] = field(default_factory=list)

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "prompt": self.prompt,
            "duration_s": self.duration_s,
            "loop": self.loop,
            "target_frames": self.target_frames,
            "fps": self.fps,
            "status": self.status,
            "error": self.error,
            "clip": self.clip.to_dict() if self.clip else None,
            "frames": [f.to_dict() for f in self.frames],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionCard":
        clip = data.get("clip")
        return cls(
            id=str(data.get("id") or cls.new_id()),
            name=str(data.get("name", "")),
            prompt=str(data.get("prompt", "")),
            duration_s=int(data.get("duration_s", 8)),
            loop=bool(data.get("loop", True)),
            target_frames=int(data.get("target_frames", 8)),
            fps=int(data.get("fps", 12)),
            status=str(data.get("status", "draft")),
            error=data.get("error"),
            clip=ClipRecord.from_dict(clip) if clip else None,
            frames=[FrameMeta.from_dict(f) for f in data.get("frames", [])],
        )


@dataclass
class CostEntry:
    action_id: str
    action_name: str
    provider: str
    model: str
    seconds: float
    estimated_usd: Optional[float]
    actual_usd: Optional[float]
    timestamp: str
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CostEntry":
        return cls(
            action_id=str(data.get("action_id", "")),
            action_name=str(data.get("action_name", "")),
            provider=str(data.get("provider", "")),
            model=str(data.get("model", "")),
            seconds=float(data.get("seconds", 0.0)),
            estimated_usd=data.get("estimated_usd"),
            actual_usd=data.get("actual_usd"),
            timestamp=str(data.get("timestamp", "")),
            note=str(data.get("note", "")),
        )


# --- project ----------------------------------------------------------------


@dataclass
class SpriteProject:
    name: str
    project_dir: Optional[Path] = None
    character_source: Optional[Path] = None
    plate_path: Optional[Path] = None
    plate_color: str = "#00FF00"
    turnaround: Dict[str, Path] = field(default_factory=dict)
    brief: str = ""
    genre_preset: str = "sidescroller"
    actions: List[ActionCard] = field(default_factory=list)
    generation: GenerationSettings = field(default_factory=GenerationSettings)
    extraction: ExtractionSettings = field(default_factory=ExtractionSettings)
    key: KeySettings = field(default_factory=KeySettings)
    stabilize: StabilizeSettings = field(default_factory=StabilizeSettings)
    profiles: List[OutputProfile] = field(default_factory=default_profiles)
    stage_fingerprints: Dict[str, Dict[str, str]] = field(default_factory=dict)
    cost_ledger: List[CostEntry] = field(default_factory=list)
    created: str = field(default_factory=_now)
    modified: str = field(default_factory=_now)

    # -- lookups ---------------------------------------------------------

    @property
    def slug(self) -> str:
        return sanitize_filename(self.name, max_len=60).replace(" ", "_") or "sprite"

    def action_by_id(self, action_id: str) -> Optional[ActionCard]:
        for action in self.actions:
            if action.id == action_id:
                return action
        return None

    def profile(self, name: str) -> Optional[OutputProfile]:
        for prof in self.profiles:
            if prof.name == name:
                return prof
        return None

    # -- serialisation ---------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": "iasprite",
            "format_version": 1,
            "name": self.name,
            "character_source": str(self.character_source) if self.character_source else None,
            "plate_path": str(self.plate_path) if self.plate_path else None,
            "plate_color": self.plate_color,
            "turnaround": {k: str(v) for k, v in self.turnaround.items()},
            "brief": self.brief,
            "genre_preset": self.genre_preset,
            "actions": [a.to_dict() for a in self.actions],
            "generation": self.generation.to_dict(),
            "extraction": self.extraction.to_dict(),
            "key": self.key.to_dict(),
            "stabilize": self.stabilize.to_dict(),
            "profiles": [p.to_dict() for p in self.profiles],
            "stage_fingerprints": {k: dict(v) for k, v in self.stage_fingerprints.items()},
            "cost_ledger": [c.to_dict() for c in self.cost_ledger],
            "created": self.created,
            "modified": self.modified,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpriteProject":
        profiles = data.get("profiles")
        return cls(
            name=str(data.get("name", "Untitled")),
            project_dir=None,
            character_source=_path_or_none(data.get("character_source")),
            plate_path=_path_or_none(data.get("plate_path")),
            plate_color=str(data.get("plate_color", "#00FF00")),
            turnaround={str(k): Path(v) for k, v in (data.get("turnaround") or {}).items() if v},
            brief=str(data.get("brief", "")),
            genre_preset=str(data.get("genre_preset", "sidescroller")),
            actions=[ActionCard.from_dict(a) for a in data.get("actions", [])],
            generation=GenerationSettings.from_dict(data.get("generation") or {}),
            extraction=ExtractionSettings.from_dict(data.get("extraction") or {}),
            key=KeySettings.from_dict(data.get("key") or {}),
            stabilize=StabilizeSettings.from_dict(data.get("stabilize") or {}),
            profiles=[OutputProfile.from_dict(p) for p in profiles] if profiles else default_profiles(),
            stage_fingerprints={
                str(k): {str(s): str(f) for s, f in (v or {}).items()}
                for k, v in (data.get("stage_fingerprints") or {}).items()
            },
            cost_ledger=[CostEntry.from_dict(c) for c in data.get("cost_ledger", [])],
            created=str(data.get("created") or _now()),
            modified=str(data.get("modified") or _now()),
        )

    def project_file(self) -> Path:
        if self.project_dir is None:
            raise ValueError("project_dir is not set")
        return self.project_dir / PROJECT_FILE_NAME

    def save(self, path: Optional[Path] = None) -> Path:
        """Write the project JSON. Returns the path written."""
        if path is None:
            path = self.project_file()
        path = Path(path)
        with _SAVE_LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.modified = _now()
            payload = json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(payload, encoding="utf-8")
            tmp.replace(path)
        return path

    @classmethod
    def load(cls, path: Path) -> "SpriteProject":
        """Read a project JSON and re-anchor its media paths."""
        path = Path(path)
        if path.is_dir():
            path = path / PROJECT_FILE_NAME
        if not path.exists():
            raise FileNotFoundError(f"Sprite project file not found: {path}")
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError(f"Sprite project file is empty: {path}")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            backup = path.with_suffix(".json.corrupted")
            try:
                shutil.copy2(path, backup)
            except OSError:
                pass
            logger.error(f"Invalid JSON in sprite project {path}: {exc}")
            raise ValueError(f"Sprite project file contains invalid JSON: {path}") from exc
        project = cls.from_dict(data)
        project.project_dir = path.parent
        healed = project.reanchor_media_paths()
        if healed:
            logger.info(
                f"Re-anchored {healed} media path(s) in sprite project '{project.name}' "
                f"to {project.project_dir}"
            )
        return project

    # -- media ----------------------------------------------------------

    def reanchor_media_paths(self) -> int:
        """Point stored media paths at the current project directory.

        Returns the number of paths that changed. Paths that still exist, and
        paths with no counterpart under the new directory, are left alone.
        """
        count = 0

        def fix(value: Optional[Path]) -> Optional[Path]:
            nonlocal count
            new = _reanchored(value, self.project_dir)
            if new is not value:
                count += 1
            return new

        self.character_source = fix(self.character_source)
        self.plate_path = fix(self.plate_path)
        self.turnaround = {k: (fix(v) or v) for k, v in self.turnaround.items()}
        for action in self.actions:
            if action.clip is not None:
                action.clip.path = fix(action.clip.path) or action.clip.path
            for frame in action.frames:
                frame.source_path = fix(frame.source_path)
        return count

    def sheet_meta(self, profile: str, *, warn: bool = True) -> SheetMeta:
        """Build the SheetMeta for one output profile.

        ``ActionCard.frames`` is the single frame list (order, timing, pivot).
        Each entry's ``source_path`` names the stabilize-stage PNG. The
        profile stages write a file of the same name under
        ``stages/<action_id>/<profile>/``; when that file exists the sheet
        points at it, otherwise it falls back to the stabilize PNG. The
        fallback logs one warning per action for an enabled profile, because
        the export then carries native-size frames, not the profile cell (T3).
        A frame with no ``source_path`` counts as a fallback too. Pass
        ``warn=False`` from a preview; the export keeps the warning.
        """
        prof = self.profile(profile)
        if prof is None:
            raise ValueError(f"Unknown output profile: {profile!r}")
        frames: List[FrameMeta] = []
        tags: List[TagMeta] = []
        for action in self.actions:
            if not action.frames:
                continue
            start = len(frames)
            fell_back = False
            profile_dir = (self.project_dir / "stages" / action.id / profile
                           if self.project_dir is not None else None)
            for frame in action.frames:
                src = frame.source_path
                if src is None:
                    fell_back = True
                elif profile_dir is not None:
                    candidate = profile_dir / src.name
                    if candidate.exists():
                        src = candidate
                    else:
                        fell_back = True
                frames.append(FrameMeta(
                    name=frame.name,
                    source_path=src,
                    frame=frame.frame,
                    rotated=frame.rotated,
                    trimmed=frame.trimmed,
                    sprite_source_size=frame.sprite_source_size,
                    source_size=frame.source_size,
                    duration_ms=frame.duration_ms,
                    pivot=frame.pivot,
                    overrides=dict(frame.overrides),
                ))
            if warn and fell_back and prof.enabled:
                cell = f"{prof.cell_size[0]}x{prof.cell_size[1]}"
                logger.warning(
                    f"Sprite project '{self.name}': Export of {profile} for '{action.name}' uses "
                    f"the stabilize frames at native size because {profile_dir} is missing or "
                    f"incomplete. Run the pipeline to get {cell} frames."
                )
            tags.append(TagMeta(
                name=action.name,
                from_index=start,
                to_index=len(frames) - 1,
                direction="forward",
                repeat=0 if action.loop else 1,
                fps_hint=action.fps,
            ))
        return SheetMeta(
            title=self.slug,
            frames=frames,
            tags=tags,
            cell_size=prof.cell_size,
            palette=list(prof.locked_palette) if prof.locked_palette and prof.palette_size else None,
            profile=profile,
        )

    def total_cost(self) -> Tuple[float, float]:
        """Return ``(estimated, actual)`` USD sums over the ledger."""
        estimated = sum(c.estimated_usd or 0.0 for c in self.cost_ledger)
        actual = sum(c.actual_usd or 0.0 for c in self.cost_ledger)
        return (round(estimated, 4), round(actual, 4))

    def purge_intermediates(self) -> int:
        """Send ``stages/`` and ``clips/`` to the recycle bin. Returns files removed.

        The sticky preference and the confirmation live in the GUI; this
        method only does the deletion. Frame entries that pointed into the
        purged directories keep their paths, so a later re-run rebuilds them.
        """
        if self.project_dir is None:
            return 0
        removed = 0
        for name in ("stages", "clips"):
            target = self.project_dir / name
            if not target.exists():
                continue
            files = sum(1 for p in target.rglob("*") if p.is_file())
            if send_to_recycle_bin(target):
                removed += files
            else:
                logger.warning(f"Could not recycle {target}; leaving it in place")
        self.stage_fingerprints = {}
        return removed


class SpriteProjectManager:
    """Creates, lists, loads and deletes sprite projects on disk."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        if base_dir is None:
            from core.paths import get_data_paths

            base_dir = get_data_paths().sprite_projects()
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_project(self, name: str) -> SpriteProject:
        project = SpriteProject(name=name)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_dir = self.base_dir / f"{project.slug}_{stamp}"
        counter = 1
        while project_dir.exists():
            project_dir = self.base_dir / f"{project.slug}_{stamp}_{counter}"
            counter += 1
        project_dir.mkdir(parents=True)
        for sub in PROJECT_SUBDIRS:
            (project_dir / sub).mkdir(exist_ok=True)
        project.project_dir = project_dir
        project.save()
        logger.info(f"Created sprite project '{name}' at {project_dir}")
        return project

    def list_projects(self) -> List[Dict[str, Any]]:
        projects: List[Dict[str, Any]] = []
        for project_dir in self.base_dir.iterdir():
            if not project_dir.is_dir():
                continue
            project_file = project_dir / PROJECT_FILE_NAME
            if not project_file.exists():
                continue
            try:
                data = json.loads(project_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning(f"Failed to read sprite project {project_file}: {exc}")
                continue
            projects.append({
                "name": data.get("name", "Untitled"),
                "slug": project_dir.name,
                "path": project_file,
                "created": data.get("created"),
                "modified": data.get("modified"),
                "actions": len(data.get("actions", [])),
            })
        projects.sort(key=lambda p: p.get("modified") or "", reverse=True)
        return projects

    def load_project(self, path: Path) -> SpriteProject:
        """Load from a project directory or its ``project.iasprite.json``."""
        return SpriteProject.load(Path(path))

    def save_project(self, project: SpriteProject) -> Path:
        """Save; give a project with no directory one under ``base_dir`` first."""
        if project.project_dir is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            project.project_dir = self.base_dir / f"{project.slug}_{stamp}"
            project.project_dir.mkdir(parents=True, exist_ok=True)
            for sub in PROJECT_SUBDIRS:
                (project.project_dir / sub).mkdir(exist_ok=True)
        return project.save()

    def find_project(self, name_or_slug: str) -> Optional[Path]:
        """Return the project file whose name or directory name matches.

        A directory name (``Hero_20260829_101500``) matches exactly; a project
        name matches case-insensitively; the newest match wins when two
        projects share a name. Returns ``None`` when nothing matches.
        """
        wanted = name_or_slug.strip()
        for info in self.list_projects():  # newest first
            if info["slug"] == wanted or str(info["name"]).lower() == wanted.lower():
                return info["path"]
        return None

    def delete_project(self, project: SpriteProject) -> bool:
        if not project.project_dir or not project.project_dir.exists():
            logger.warning(f"Sprite project directory not found: {project.project_dir}")
            return False
        try:
            shutil.rmtree(project.project_dir)
        except OSError as exc:
            logger.error(f"Failed to delete sprite project {project.project_dir}: {exc}")
            return False
        logger.info(f"Deleted sprite project '{project.name}' at {project.project_dir}")
        return True
