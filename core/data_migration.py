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
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

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


class ConfigError(Exception):
    """Raised when config.json cannot be read, parsed, or replaced.

    config.json holds the API keys and every other setting. The migrator must
    never overwrite a file it could not read, so this error aborts the move
    before any source is deleted.
    """


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
        # A pre-existing entry with a source name would be merged into by the
        # copy. Its files then inflate the verification counts, and the abort
        # cleanup would delete data the move did not create.
        collisions = sorted({name for _s, name in sources if (dest / name).exists()})
        if collisions:
            listed = ", ".join(collisions[:3])
            if len(collisions) > 3:
                listed += f", and {len(collisions) - 3} more"
            return (
                f"The folder {dest} already contains {listed}. "
                f"Choose an empty folder or a new one."
            )
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
    """Copy one file or directory tree, reporting progress per file.

    The counters measure the bytes that landed in the destination, not the
    bytes the source holds now. A live file — the log file this process writes
    — can grow between the copy and the measurement, and a source-side count
    would then disagree with the destination for a copy that in fact succeeded.
    """
    if source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        state["files"] += 1
        state["bytes"] += target.stat().st_size
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
        state["bytes"] += destination.stat().st_size
        if progress_cb:
            progress_cb(state["files"], state["files_total"],
                        state["bytes"], state["bytes_total"], str(entry))


def _read_config(config_path: Path) -> dict:
    """Return the parsed config.json, ready to be updated.

    A missing file is a fresh install, so it yields an empty document. Every
    other failure raises ConfigError. config.json holds the API keys, and a
    rewrite based on a document the migrator could not read would erase them.
    """
    import json

    if not config_path.exists():
        return {}
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Could not read {config_path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ConfigError(f"Could not parse {config_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{config_path} does not hold a JSON object.")
    roots = data.get("data_roots")
    if roots is not None and not isinstance(roots, dict):
        raise ConfigError(f"The 'data_roots' entry in {config_path} is not a JSON object.")
    return data


def _write_root(paths: DataPaths, group: Group, dest: Path) -> None:
    """Persist the new root to config.json.

    The write goes to a temporary file in the same directory, is flushed and
    fsynced, and then replaces config.json in one atomic step. A crash during
    the write therefore cannot truncate the bootstrap file. Raises ConfigError
    on any failure.
    """
    import json

    config_path = paths.config_file()
    data = _read_config(config_path)
    data.setdefault("data_roots", {})[group.value] = str(dest)

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigError(f"Could not create {config_path.parent}: {exc}") from exc

    temp_path = config_path.with_name(f"{config_path.name}.{os.getpid()}.tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temp_path), str(config_path))
    except OSError as exc:
        try:
            temp_path.unlink()
        except OSError:
            logger.warning("Could not remove the temporary file %s", temp_path)
        raise ConfigError(f"Could not write {config_path}: {exc}") from exc


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

    # Read config.json before any work starts. The move ends with a rewrite of
    # this file, and a file that cannot be read now cannot be rewritten later
    # without losing the API keys it holds.
    try:
        _read_config(paths.config_file())
    except ConfigError as exc:
        logger.error("Cannot move %s to %s: %s", group.value, dest, exc)
        return MoveResult(
            ok=False,
            error=f"{exc} Repair that file first. Nothing was changed.",
        )

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

    names = [name for _s, name in sources]

    # Fast path: a rename within one volume finishes in milliseconds. This
    # matters most for Models, where a cross-volume copy runs for many minutes.
    if all(_same_volume(source, dest) for source, _n in sources):
        renamed: List[Tuple[Path, Path]] = []
        rename_failed = True
        try:
            for source, name in sources:
                target = dest / name
                os.rename(str(source), str(target))
                renamed.append((source, target))
            rename_failed = False
        except OSError as exc:
            logger.warning("Rename failed for %s: %s", group.value, exc)

        if not rename_failed:
            try:
                _write_root(paths, group, dest)
            except ConfigError as exc:
                logger.error("Could not record the new %s root: %s", group.value, exc)
                rollback_error = _rollback_renames(renamed)
                if rollback_error:
                    return MoveResult(ok=False, error=rollback_error)
                return MoveResult(
                    ok=False,
                    error=f"{exc} Your data was left where it was.",
                )
            _cleanup_empty_legacy_dirs(group)
            logger.info("Moved %s to %s by rename (%d files)", group.value, dest, files_total)
            return MoveResult(ok=True, files_moved=files_total,
                              bytes_moved=bytes_total, used_rename=True)

        # Undo the renames that did succeed. Without the rollback, a source
        # already under the destination would be destroyed by the cleanup that
        # a later cancel or copy failure runs.
        rollback_error = _rollback_renames(renamed)
        if rollback_error:
            return MoveResult(ok=False, error=rollback_error)
        logger.warning("Rolled back the partial rename of %s; falling back to copy",
                       group.value)

    state = {"files": 0, "bytes": 0, "files_total": files_total, "bytes_total": bytes_total}
    try:
        for source, name in sources:
            if _is_cancelled(cancel):
                raise MoveCancelled()
            _copy_entry(source, dest / name, state, progress_cb, cancel)
    except MoveCancelled:
        _remove_partial(dest, names)
        logger.info("Move of %s cancelled by the user; source left intact", group.value)
        return MoveResult(ok=False, error="Move cancelled. Nothing was changed.")
    except OSError as exc:
        _remove_partial(dest, names)
        logger.exception("Copy failed while moving %s", group.value)
        return MoveResult(ok=False, error=f"Copy failed: {exc}. Nothing was changed.")

    # Compare the destination against what the copy loop wrote, not against the
    # pre-scan totals. A source that grows during the move — the log file this
    # process writes — must not fail a copy that in fact succeeded.
    copied_files = sum(tree_size(dest / name)[0] for name in names)
    copied_bytes = sum(tree_size(dest / name)[1] for name in names)
    if (copied_files, copied_bytes) != (state["files"], state["bytes"]):
        _remove_partial(dest, names)
        message = (
            f"Verification failed: the copy wrote {state['files']} files "
            f"({_human(state['bytes'])}) but the destination holds "
            f"{copied_files} ({_human(copied_bytes)}). "
            f"Your data was left where it was."
        )
        logger.error("Verification failed moving %s: %s", group.value, message)
        return MoveResult(ok=False, error=message)

    try:
        _write_root(paths, group, dest)
    except ConfigError as exc:
        _remove_partial(dest, names)
        logger.error("Could not record the new %s root: %s", group.value, exc)
        return MoveResult(ok=False, error=f"{exc} Your data was left where it was.")

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
                state["files"], _human(state["bytes"]))
    return MoveResult(ok=True, files_moved=state["files"], bytes_moved=state["bytes"])


def _rollback_renames(renamed: Sequence[Tuple[Path, Path]]) -> Optional[str]:
    """Move renamed entries back to their original locations.

    Returns None on success, or a user-facing error message that names the
    directory that still holds the data. The caller must abort on an error:
    the data has only one copy, and it is not where the application expects it.
    """
    for source, target in reversed(list(renamed)):
        try:
            os.rename(str(target), str(source))
        except OSError as exc:
            logger.exception("Could not move %s back to %s after a failed rename",
                             target, source)
            return (
                f"The move failed and part of it could not be undone ({exc}). "
                f"Your data is now in {target}. Move it back to {source} by "
                f"hand before you start the application again."
            )
    return None


def _remove_partial(dest: Path, names: Iterable[str]) -> None:
    """Delete only the entries this move created under the destination.

    The destination may be a folder the user already owns. Deleting the folder
    itself, or anything the move did not put there, would destroy unrelated
    data, so the cleanup removes ``dest / name`` and never ``dest``.
    """
    for name in names:
        entry = dest / name
        try:
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry)
            elif entry.exists() or entry.is_symlink():
                entry.unlink()
        except OSError as exc:
            logger.warning("Could not clean up the partial copy at %s: %s", entry, exc)


def _cleanup_empty_legacy_dirs(group: Group) -> None:
    """Remove ~/.imageai once the Video move has emptied it."""
    if group is not Group.VIDEO:
        return
    legacy = legacy_dot_imageai_dir()
    try:
        if legacy.is_dir() and not any(legacy.iterdir()):
            legacy.rmdir()
    except OSError as exc:
        logger.warning("Could not remove the empty %s: %s", legacy, exc)
