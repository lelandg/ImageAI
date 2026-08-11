"""Relocate a group of ImageAI data directories to a new root.

Headless by design: this module imports no Qt. The GUI drives it through
``move_group`` and renders progress from the callback.
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from core import config_io
from core.paths import DataPaths, Group, get_data_paths

logger = logging.getLogger(__name__)

# Directory names that belong to each group, relative to the group root.
# "cache" is deliberately absent from both Models and Video: one cache
# directory serves both groups. See CACHE_DIR and CACHE_OWNERS below.
GROUP_CONTENTS = {
    Group.IMAGES: [
        "generated", "images", "composites", "styles", "Characters",
        "midjourney_web_cache", "midjourney_web_storage",
    ],
    Group.VIDEO: ["video_projects"],
    Group.MODELS: ["musetalk", "weights", "huggingface"],
    Group.SETTINGS: ["logs", "layout", "template_cache", "templates"],
}

# The Models root and the Video root default to the same directory, and both
# groups keep their caches in a "cache" subdirectory of their own root. A move
# of one group must not carry the other group's cache away, so each cache
# subdirectory belongs to exactly one group. The names come from
# DataPaths.model_cache() and DataPaths.video_cache() callers.
CACHE_DIR = "cache"
CACHE_OWNERS: Dict[Group, Tuple[str, ...]] = {
    Group.MODELS: ("ai_visemes",),
    Group.VIDEO: ("video", "thumbnails", "veo_videos"),
}

# The destination subdirectory that receives the legacy ~/.imageai tree. That
# tree holds directories with the same names as the current ones — a
# ~/.imageai/video_projects beside the app's own video_projects — so it needs a
# place of its own. A shared name would merge two trees into one silently.
LEGACY_IMAGEAI_NAME = "legacy_imageai"

# Loose files that move with the Settings group. config.json is deliberately
# absent: it records where every other group lives, so it can never move.
SETTINGS_FILES = ("details.jsonl", "batch_jobs.json")
SETTINGS_GLOBS = ("*_history.json", "*_session.json", "*_history.backup_*.json")

# Safety margin above the measured source size, in bytes.
FREE_SPACE_MARGIN = 256 * 1024 * 1024


class MoveCancelled(Exception):
    """Raised internally when the caller sets the cancel flag."""


class _DestinationCollision(Exception):
    """Raised when an entry appears at a destination name during the move.

    Validation runs before the copy starts, and a large copy runs for many
    minutes. Another tool, or a second ImageAI window, can create an entry at
    one of the destination names in that window. The move must abort rather
    than merge into it, because the cleanup would then delete data this move
    did not create.
    """

    def __init__(self, path: Path) -> None:
        super().__init__(str(path))
        self.path = path


# config.json holds the API keys and every other setting. The migrator must
# never overwrite a file it could not read, so a config failure aborts the move
# before any source is deleted. core.config_io owns the locked, atomic
# read-modify-write cycle; this alias keeps the historical name that this
# module's callers already catch, and it covers read, write and lock failures.
ConfigError = config_io.ConfigIOError


@dataclass
class MoveResult:
    ok: bool
    files_moved: int = 0
    bytes_moved: int = 0
    used_rename: bool = False
    error: Optional[str] = None
    # (path_the_data_sits_at_now, path_it_belongs_at) for every directory a
    # failed rollback could not put back. Empty on every other outcome.
    stranded: List[Tuple[str, str]] = field(default_factory=list)


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


def _resolved(path: Path) -> Path:
    """Resolve a path, falling back to the path itself when the OS refuses."""
    try:
        return path.resolve()
    except OSError:
        return path


def _roots_coincide(group: Group, paths: DataPaths) -> bool:
    """True when the Models root and the Video root are one directory.

    That is the default: both groups resolve to the platform user directory
    until the user moves one of them.
    """
    other = Group.VIDEO if group is Group.MODELS else Group.MODELS
    return _resolved(paths.root(group)) == _resolved(paths.root(other))


def _cache_sources(group: Group, paths: DataPaths) -> List[Tuple[Path, str]]:
    """List the cache directories that belong to this group.

    When the Models root and the Video root are the same directory, one
    ``cache`` directory holds both groups' caches. The move then takes only the
    subdirectories this group owns, so a Models move cannot carry the video
    render cache away from the path ``DataPaths.video_cache`` still points at.
    When the two roots differ, the whole ``cache`` directory belongs to this
    group and moves as one entry.
    """
    if group not in CACHE_OWNERS:
        return []
    cache = paths.root(group) / CACHE_DIR
    if not cache.is_dir():
        return []
    if not _roots_coincide(group, paths):
        return [(cache, CACHE_DIR)]
    entries: List[Tuple[Path, str]] = []
    for name in CACHE_OWNERS[group]:
        candidate = cache / name
        if candidate.exists():
            entries.append((candidate, f"{CACHE_DIR}/{name}"))
    return entries


def unclaimed_cache_subdirs(group: Group, paths: DataPaths) -> List[Path]:
    """Cache subdirectories that belong to neither Models nor Video.

    A shared cache directory splits by owner. A subdirectory that no group
    claims stays behind, so the move reports it and the user can act on it.
    """
    if group not in CACHE_OWNERS or not _roots_coincide(group, paths):
        return []
    cache = paths.root(group) / CACHE_DIR
    if not cache.is_dir():
        return []
    claimed = set(CACHE_OWNERS[Group.MODELS]) | set(CACHE_OWNERS[Group.VIDEO])
    try:
        children = sorted(cache.iterdir())
    except OSError as exc:
        logger.warning("Could not list %s: %s", cache, exc)
        return []
    return [child for child in children if child.name not in claimed]


def duplicate_destination_names(
    entries: Sequence[Tuple[Path, str]]
) -> List[str]:
    """Return the destination names that more than one source would claim.

    Two sources that share a name merge into one directory at the destination.
    The verification then counts the merged tree once for each source, and a
    passing count is followed by the deletion of both sources. A name nested
    inside another name (``cache`` and ``cache/video``) has the same effect, so
    it counts as a clash too. A move that finds a clash must stop.
    """
    parts = [(name, PurePosixPath(name).parts) for _source, name in entries]
    clashes = set()
    for index, (name, key) in enumerate(parts):
        for other_name, other_key in parts[index + 1:]:
            if key == other_key or key[:len(other_key)] == other_key \
                    or other_key[:len(key)] == key:
                clashes.add(name)
                clashes.add(other_name)
    return sorted(clashes)


def sources_for(group: Group, paths: Optional[DataPaths] = None) -> List[Tuple[Path, str]]:
    """List existing source directories for a group.

    Returns ``(absolute_source, name_under_destination)`` pairs. A group may
    span more than one tree: Models spans the app root and the HuggingFace
    cache, Video spans the app root and ~/.imageai. Every name in the result is
    unique, because two sources that share one name would merge silently.
    """
    paths = paths or get_data_paths()
    root = paths.root(group)
    entries: List[Tuple[Path, str]] = []

    for name in GROUP_CONTENTS[group]:
        candidate = root / name
        if candidate.exists():
            entries.append((candidate, name))

    entries.extend(_cache_sources(group, paths))

    if group is Group.MODELS:
        hf = legacy_huggingface_dir()
        if hf.exists() and not any(name == "huggingface" for _s, name in entries):
            entries.append((hf, "huggingface"))

    if group is Group.VIDEO:
        legacy = legacy_dot_imageai_dir()
        if legacy.exists():
            for child in sorted(legacy.iterdir()):
                if child.is_dir():
                    entries.append((child, f"{LEGACY_IMAGEAI_NAME}/{child.name}"))

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

    clashes = duplicate_destination_names(sources)
    if clashes:
        message = (
            f"Two folders of the {group.value} data would be moved to the same "
            f"place ({', '.join(clashes)}). Moving them would merge them into "
            f"one folder, so the move stopped. Rename one of them first."
        )
        logger.error("Cannot move %s to %s: %s", group.value, dest, message)
        return message

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
        # The test is link-aware on purpose. Path.exists() follows a symlink
        # and returns False for a link whose target is unreachable — the user's
        # own redirect to an unplugged drive or an offline share. Such a link
        # would pass this guard and then be unlinked by the cleanup.
        collisions = sorted(
            {name for _s, name in sources if os.path.lexists(dest / name)}
        )
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
    ``core.config_io`` owns the parsing and the logging.
    """
    return config_io.read_config(config_path)


def _write_root(paths: DataPaths, group: Group, dest: Path) -> None:
    """Persist the new root to config.json.

    The whole read-modify-write cycle runs under the config.json lock in
    ``core.config_io``. ConfigManager saves the same file from worker threads
    while a long move runs, so a cycle without that lock loses whichever
    writer read first. The write itself is atomic: a temporary file in the same
    directory, flushed, fsynced, then replaced in one step. Raises ConfigError
    on any failure, and config.json is unchanged in that case.
    """
    def mutate(data: dict) -> dict:
        roots = data.setdefault("data_roots", {})
        roots[group.value] = str(dest)
        return data

    config_io.update_config(paths.config_file(), mutate)


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

    # Re-check after the pre-move hook: the hook can close files and change the
    # tree. Two sources that share one destination name merge silently, so the
    # move stops here rather than at the deletion step.
    clashes = duplicate_destination_names(sources)
    if clashes:
        message = (
            f"Two folders of the {group.value} data would be moved to the same "
            f"place ({', '.join(clashes)}). Nothing was changed."
        )
        logger.error("Cannot move %s to %s: %s", group.value, dest, message)
        return MoveResult(ok=False, error=message)

    for leftover in unclaimed_cache_subdirs(group, paths):
        logger.warning(
            "The cache folder %s belongs to no data group, so the %s move "
            "leaves it at %s.", leftover, group.value, leftover.parent,
        )

    _prepare_databases(sources)

    files_total = sum(tree_size(s)[0] for s, _n in sources)
    bytes_total = sum(tree_size(s)[1] for s, _n in sources)

    # Track every directory this move creates under the destination. The
    # cleanup removes only these, so an entry another process put there while
    # the copy ran survives an abort.
    created_dirs: List[Path] = []
    if not os.path.lexists(dest):
        created_dirs.append(dest)
    dest.mkdir(parents=True, exist_ok=True)

    # Fast path: a rename within one volume finishes in milliseconds. This
    # matters most for Models, where a cross-volume copy runs for many minutes.
    if all(_same_volume(source, dest) for source, _n in sources):
        renamed: List[Tuple[Path, Path]] = []
        rename_dirs: List[Path] = []
        rename_error: Optional[OSError] = None
        collision: Optional[Path] = None

        for source, name in sources:
            target = dest / name
            if os.path.lexists(target):
                collision = target
                break
            parents = _missing_parents(dest, target)
            try:
                for parent in parents:
                    parent.mkdir(parents=True, exist_ok=True)
                    rename_dirs.append(parent)
                os.rename(str(source), str(target))
            except OSError as exc:
                rename_error = exc
                logger.warning("Rename failed for %s: %s", group.value, exc)
                break
            renamed.append((source, target))

        if collision is not None:
            stranded = _rollback_renames(renamed)
            _remove_created([], rename_dirs + created_dirs)
            reason = (
                f"Something else created {collision} while the move was "
                f"running, so the move stopped."
            )
            return _failed(group, dest, reason, stranded,
                           " Nothing was changed. Move that folder away and try again.")

        if rename_error is None:
            try:
                _write_root(paths, group, dest)
            except ConfigError as exc:
                logger.error("Could not record the new %s root: %s", group.value, exc)
                stranded = _rollback_renames(renamed)
                _remove_created([], rename_dirs + created_dirs)
                return _failed(group, dest, str(exc), stranded,
                               " Your data was left where it was.")
            _cleanup_empty_legacy_dirs(group)
            logger.info("Moved %s to %s by rename (%d files)", group.value, dest, files_total)
            return MoveResult(ok=True, files_moved=files_total,
                              bytes_moved=bytes_total, used_rename=True)

        # Undo the renames that did succeed. Without the rollback, a source
        # already under the destination would be destroyed by the cleanup that
        # a later cancel or copy failure runs.
        stranded = _rollback_renames(renamed)
        _remove_created([], rename_dirs)
        if stranded:
            return _failed(
                group, dest,
                f"The move failed ({rename_error}) and part of it could not be undone.",
                stranded, "",
            )
        logger.warning("Rolled back the partial rename of %s; falling back to copy",
                       group.value)

    state = {"files": 0, "bytes": 0, "files_total": files_total, "bytes_total": bytes_total}
    created_entries: List[Path] = []
    try:
        for source, name in sources:
            if _is_cancelled(cancel):
                raise MoveCancelled()
            target = dest / name
            if os.path.lexists(target):
                raise _DestinationCollision(target)
            for parent in _missing_parents(dest, target):
                parent.mkdir(parents=True, exist_ok=True)
                created_dirs.append(parent)
            created_entries.append(target)
            _copy_entry(source, target, state, progress_cb, cancel)
    except MoveCancelled:
        _remove_created(created_entries, created_dirs)
        logger.info("Move of %s cancelled by the user; source left intact", group.value)
        return MoveResult(ok=False, error="Move cancelled. Nothing was changed.")
    except _DestinationCollision as exc:
        _remove_created(created_entries, created_dirs)
        message = (
            f"Something else created {exc.path} while the move was running, so "
            f"the move stopped. Nothing was changed. Move that folder away and "
            f"try again."
        )
        logger.error("Aborted the move of %s to %s: %s", group.value, dest, message)
        return MoveResult(ok=False, error=message)
    except OSError as exc:
        _remove_created(created_entries, created_dirs)
        logger.exception("Copy failed while moving %s", group.value)
        return MoveResult(ok=False, error=f"Copy failed: {exc}. Nothing was changed.")

    # Compare the destination against what the copy loop wrote, not against the
    # pre-scan totals. A source that grows during the move — the log file this
    # process writes — must not fail a copy that in fact succeeded. Every name
    # is unique, so each source contributes to the count exactly once.
    copied_files = sum(tree_size(target)[0] for target in created_entries)
    copied_bytes = sum(tree_size(target)[1] for target in created_entries)
    if (copied_files, copied_bytes) != (state["files"], state["bytes"]):
        _remove_created(created_entries, created_dirs)
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
        _remove_created(created_entries, created_dirs)
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


def _rollback_renames(
    renamed: Sequence[Tuple[Path, Path]]
) -> List[Tuple[Path, Path]]:
    """Move every renamed entry back to its original location.

    Returns the ``(where_it_is_now, where_it_belongs)`` pairs that could not be
    put back. The loop never stops at the first failure: each entry is the only
    copy of that data, and an entry left at the destination while config.json
    still points at the old root is data the application reports as missing and
    then downloads over.
    """
    stranded: List[Tuple[Path, Path]] = []
    for source, target in reversed(list(renamed)):
        try:
            os.rename(str(target), str(source))
        except OSError as exc:
            logger.error(
                "Could not move %s back to %s after a failed move: %s. "
                "That folder now holds the only copy of the data.",
                target, source, exc,
            )
            stranded.append((target, source))
    return stranded


def _failed(
    group: Group,
    dest: Path,
    reason: str,
    stranded: Sequence[Tuple[Path, Path]],
    suffix: str,
) -> MoveResult:
    """Build and log the result of a failed move.

    Every stranded directory is named, with the place the data sits now and the
    place it belongs. A message that names only one of them leaves the rest
    invisible to the user.
    """
    if not stranded:
        message = f"{reason}{suffix}"
        logger.error("Could not move %s to %s: %s", group.value, dest, message)
        return MoveResult(ok=False, error=message)

    lines = [
        reason,
        "These folders hold the only copy of your data and are in the wrong "
        "place. Move each one back by hand before you start the application "
        "again:",
    ]
    for target, source in stranded:
        lines.append(f"  {target}  ->  {source}")
    message = "\n".join(lines)
    logger.error("Could not move %s to %s: %s", group.value, dest, message)
    return MoveResult(
        ok=False,
        error=message,
        stranded=[(str(target), str(source)) for target, source in stranded],
    )


def _missing_parents(dest: Path, target: Path) -> List[Path]:
    """Directories between ``dest`` and ``target`` that do not exist yet.

    A destination name may hold a separator — ``cache/video`` — so the move can
    have to create an intermediate directory. Only the directories it creates
    itself may be removed again by the cleanup.
    """
    missing: List[Path] = []
    parent = target.parent
    while parent != dest and dest in parent.parents:
        if not os.path.lexists(parent):
            missing.append(parent)
        parent = parent.parent
    return list(reversed(missing))


def _remove_created(entries: Sequence[Path], dirs: Sequence[Path]) -> None:
    """Delete only what this move created under the destination.

    The destination may be a folder the user already owns, and another program
    can create an entry there while a long copy runs. The cleanup therefore
    works from a recorded list, never from the source names, and it removes an
    intermediate directory only when that directory is empty.
    """
    for entry in sorted(entries, key=lambda p: len(p.parts), reverse=True):
        try:
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry)
            elif os.path.lexists(entry):
                entry.unlink()
        except OSError as exc:
            logger.warning("Could not clean up the partial copy at %s: %s", entry, exc)

    for directory in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
        try:
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        except OSError as exc:
            logger.warning("Could not remove the empty folder %s: %s", directory, exc)


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
