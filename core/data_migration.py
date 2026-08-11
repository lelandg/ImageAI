"""Relocate a group of ImageAI data directories to a new root.

Headless by design: this module imports no Qt. The GUI drives it through
``move_group`` and renders progress from the callback.
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from core.paths import DataPaths, Group, get_data_paths

logger = logging.getLogger(__name__)

# Directory names that belong to each group, relative to the group root.
GROUP_CONTENTS = {
    Group.IMAGES: [
        "generated", "images", "composites", "styles", "Characters",
        "midjourney_web_cache", "midjourney_web_storage",
    ],
    Group.VIDEO: ["video_projects"],
    Group.MODELS: ["musetalk", "weights", "cache", "huggingface"],
    Group.SETTINGS: ["logs", "layout", "template_cache", "templates"],
}

# Loose files that move with the Settings group. config.json is deliberately
# absent: it records where every other group lives, so it can never move.
SETTINGS_FILES = ("details.jsonl", "batch_jobs.json")
SETTINGS_GLOBS = ("*_history.json", "*_session.json", "*_history.backup_*.json")

# Safety margin above the measured source size, in bytes.
FREE_SPACE_MARGIN = 256 * 1024 * 1024


class MoveCancelled(Exception):
    """Raised internally when the caller sets the cancel flag."""


@dataclass
class MoveResult:
    ok: bool
    files_moved: int = 0
    bytes_moved: int = 0
    used_rename: bool = False
    error: Optional[str] = None


def legacy_huggingface_dir() -> Path:
    """The pre-move HuggingFace cache location."""
    return Path.home() / ".cache" / "huggingface"


def legacy_dot_imageai_dir() -> Path:
    """The pre-move ~/.imageai tree."""
    return Path.home() / ".imageai"


def tree_size(path: Path) -> Tuple[int, int]:
    """Return ``(file_count, total_bytes)`` for a directory tree."""
    if not path.exists():
        return (0, 0)
    if path.is_file():
        return (1, path.stat().st_size)
    files = 0
    total = 0
    for entry in path.rglob("*"):
        if entry.is_file():
            files += 1
            try:
                total += entry.stat().st_size
            except OSError:
                pass
    return (files, total)


def sources_for(group: Group, paths: Optional[DataPaths] = None) -> List[Tuple[Path, str]]:
    """List existing source directories for a group.

    Returns ``(absolute_source, name_under_destination)`` pairs. A group may
    span more than one tree: Models spans the app root and the HuggingFace
    cache, Video spans the app root and ~/.imageai.
    """
    paths = paths or get_data_paths()
    root = paths.root(group)
    entries: List[Tuple[Path, str]] = []

    for name in GROUP_CONTENTS[group]:
        candidate = root / name
        if candidate.exists():
            entries.append((candidate, name))

    if group is Group.MODELS:
        hf = legacy_huggingface_dir()
        if hf.exists() and not any(name == "huggingface" for _s, name in entries):
            entries.append((hf, "huggingface"))

    if group is Group.VIDEO:
        legacy = legacy_dot_imageai_dir()
        if legacy.exists():
            for child in sorted(legacy.iterdir()):
                if child.is_dir():
                    entries.append((child, child.name))

    if group is Group.SETTINGS:
        for filename in SETTINGS_FILES:
            candidate = root / filename
            if candidate.exists():
                entries.append((candidate, filename))
        for pattern in SETTINGS_GLOBS:
            for candidate in sorted(root.glob(pattern)):
                if candidate.is_file():
                    entries.append((candidate, candidate.name))

    return entries


def validate_destination(
    group: Group, dest: Path, paths: Optional[DataPaths] = None
) -> Optional[str]:
    """Return an error message, or None when the destination is usable."""
    paths = paths or get_data_paths()
    dest = Path(dest)
    sources = sources_for(group, paths)

    if not sources:
        return f"There is no {group.value} data to move."

    try:
        resolved_dest = dest.resolve()
    except OSError as exc:
        return f"Cannot use {dest}: {exc}"

    # The group root itself is the current location. A destination equal to it
    # is a no-op move.
    try:
        resolved_root = paths.root(group).resolve()
    except OSError:
        resolved_root = paths.root(group)
    if resolved_dest == resolved_root:
        return "The destination is the same as the current location."

    for source, _name in sources:
        resolved_source = source.resolve()
        if resolved_dest == resolved_source:
            return "The destination is the same as the current location."
        if resolved_source in resolved_dest.parents:
            return (
                f"The destination is inside the folder being moved "
                f"({resolved_source}). Choose a folder outside it."
            )

    if not dest.exists():
        parent = dest.parent
        if not parent.is_dir():
            return f"The folder {parent} does not exist."
        if not os.access(parent, os.W_OK):
            return f"The folder {parent} is not writable."
        probe = parent
    else:
        if not os.access(dest, os.W_OK):
            return f"The folder {dest} is not writable."
        probe = dest

    required = sum(tree_size(source)[1] for source, _name in sources)
    try:
        free = shutil.disk_usage(probe).free
    except OSError as exc:
        return f"Cannot check free space at {probe}: {exc}"

    if free < required + FREE_SPACE_MARGIN:
        return (
            f"Not enough free space. The move needs "
            f"{_human(required + FREE_SPACE_MARGIN)} but only "
            f"{_human(free)} is available."
        )

    return None


def _human(num_bytes: int) -> str:
    """Format a byte count for a user-facing message."""
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TB"


def _same_volume(source: Path, dest: Path) -> bool:
    """True when both paths live on the same filesystem volume."""
    probe = dest
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        if os.name == "nt":
            a = os.path.splitdrive(str(source.resolve()))[0].lower()
            b = os.path.splitdrive(str(probe.resolve()))[0].lower()
            return bool(a) and a == b
        return source.stat().st_dev == probe.stat().st_dev
    except OSError:
        return False


def _is_cancelled(cancel) -> bool:
    if cancel is None:
        return False
    if hasattr(cancel, "is_set"):
        return bool(cancel.is_set())
    return bool(cancel())


def _checkpoint_sqlite(db_path: Path) -> None:
    """Fold a SQLite write-ahead log into the main database file.

    A copy of a WAL-mode database without its -wal file loses recent commits.
    Checkpointing first makes the single main file self-contained.
    """
    import sqlite3

    try:
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        logger.warning("Could not checkpoint %s before moving it: %s", db_path, exc)


def _prepare_databases(sources: List[Tuple[Path, str]]) -> None:
    for source, _name in sources:
        if source.is_dir():
            for db in source.rglob("*.db"):
                _checkpoint_sqlite(db)
        elif source.suffix == ".db":
            _checkpoint_sqlite(source)


def _copy_entry(source: Path, target: Path, state: dict, progress_cb, cancel) -> None:
    """Copy one file or directory tree, reporting progress per file."""
    if source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        state["files"] += 1
        state["bytes"] += source.stat().st_size
        if progress_cb:
            progress_cb(state["files"], state["files_total"],
                        state["bytes"], state["bytes_total"], str(source))
        return

    for entry in sorted(source.rglob("*")):
        if _is_cancelled(cancel):
            raise MoveCancelled()
        relative = entry.relative_to(source)
        destination = target / relative
        if entry.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry, destination)
        state["files"] += 1
        try:
            state["bytes"] += entry.stat().st_size
        except OSError:
            pass
        if progress_cb:
            progress_cb(state["files"], state["files_total"],
                        state["bytes"], state["bytes_total"], str(entry))


def _write_root(paths: DataPaths, group: Group, dest: Path) -> None:
    """Persist the new root to config.json and flush it to disk."""
    import json

    config_path = paths.config_file()
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data.setdefault("data_roots", {})[group.value] = str(dest)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())


def move_group(
    group: Group,
    dest: Path,
    paths: Optional[DataPaths] = None,
    progress_cb: Optional[Callable[..., None]] = None,
    cancel=None,
    pre_move: Optional[Callable[[], None]] = None,
) -> MoveResult:
    """Relocate a group's data to ``dest`` and record the new root.

    Order matters: verify the copy, then write the config, then delete the
    source. A crash between the config write and the delete leaves a working
    application plus a stale copy. The reverse order can destroy the only copy.
    """
    paths = paths or get_data_paths()
    dest = Path(dest)

    error = validate_destination(group, dest, paths)
    if error:
        logger.error("Cannot move %s to %s: %s", group.value, dest, error)
        return MoveResult(ok=False, error=error)

    if pre_move is not None:
        try:
            pre_move()
        except Exception as exc:  # noqa: BLE001 - reported to the user
            logger.exception("Pre-move hook failed for %s", group.value)
            return MoveResult(ok=False, error=f"Could not release open files: {exc}")

    sources = sources_for(group, paths)
    _prepare_databases(sources)

    files_total = sum(tree_size(s)[0] for s, _n in sources)
    bytes_total = sum(tree_size(s)[1] for s, _n in sources)
    dest.mkdir(parents=True, exist_ok=True)

    # Fast path: a rename within one volume finishes in milliseconds. This
    # matters most for Models, where a cross-volume copy runs for many minutes.
    if all(_same_volume(source, dest) for source, _n in sources):
        try:
            for source, name in sources:
                os.rename(str(source), str(dest / name))
            _write_root(paths, group, dest)
            _cleanup_empty_legacy_dirs(group)
            logger.info("Moved %s to %s by rename (%d files)", group.value, dest, files_total)
            return MoveResult(ok=True, files_moved=files_total,
                              bytes_moved=bytes_total, used_rename=True)
        except OSError as exc:
            logger.warning("Rename failed for %s, falling back to copy: %s", group.value, exc)

    state = {"files": 0, "bytes": 0, "files_total": files_total, "bytes_total": bytes_total}
    try:
        for source, name in sources:
            if _is_cancelled(cancel):
                raise MoveCancelled()
            _copy_entry(source, dest / name, state, progress_cb, cancel)
    except MoveCancelled:
        _remove_partial(dest)
        logger.info("Move of %s cancelled by the user; source left intact", group.value)
        return MoveResult(ok=False, error="Move cancelled. Nothing was changed.")
    except OSError as exc:
        _remove_partial(dest)
        logger.exception("Copy failed while moving %s", group.value)
        return MoveResult(ok=False, error=f"Copy failed: {exc}. Nothing was changed.")

    copied_files = sum(tree_size(dest / name)[0] for _s, name in sources)
    copied_bytes = sum(tree_size(dest / name)[1] for _s, name in sources)
    if (copied_files, copied_bytes) != (files_total, bytes_total):
        _remove_partial(dest)
        message = (
            f"Verification failed: expected {files_total} files "
            f"({_human(bytes_total)}) but found {copied_files} "
            f"({_human(copied_bytes)}). Your data was left where it was."
        )
        logger.error("Verification failed moving %s: %s", group.value, message)
        return MoveResult(ok=False, error=message)

    _write_root(paths, group, dest)

    for source, _name in sources:
        try:
            if source.is_dir():
                shutil.rmtree(source)
            else:
                source.unlink()
        except OSError as exc:
            logger.warning("Could not remove %s after the move: %s", source, exc)

    _cleanup_empty_legacy_dirs(group)
    logger.info("Moved %s to %s (%d files, %s)", group.value, dest,
                files_total, _human(bytes_total))
    return MoveResult(ok=True, files_moved=files_total, bytes_moved=bytes_total)


def _remove_partial(dest: Path) -> None:
    """Delete a partially written destination after an abort."""
    try:
        if dest.exists():
            shutil.rmtree(dest)
    except OSError as exc:
        logger.warning("Could not clean up the partial copy at %s: %s", dest, exc)


def _cleanup_empty_legacy_dirs(group: Group) -> None:
    """Remove ~/.imageai once the Video move has emptied it."""
    if group is not Group.VIDEO:
        return
    legacy = legacy_dot_imageai_dir()
    try:
        if legacy.is_dir() and not any(legacy.iterdir()):
            legacy.rmdir()
    except OSError as exc:
        logger.debug("Could not remove the empty %s: %s", legacy, exc)
