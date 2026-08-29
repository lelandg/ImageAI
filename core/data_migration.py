"""Relocate a group of ImageAI data directories to a new root.

Headless by design: this module imports no Qt. The GUI drives it through
``move_group`` and renders progress from the callback.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from core import config_io
from core.paths import DataPaths, Group, get_data_paths, reset_data_paths

logger = logging.getLogger(__name__)

# Directory names that belong to each group, relative to the group root.
# "cache" is deliberately absent from both Models and Video: one cache
# directory serves both groups. See CACHE_DIR and CACHE_OWNERS below.
GROUP_CONTENTS = {
    Group.IMAGES: [
        "generated", "images", "composites", "styles", "Characters",
        "Fonts", "midjourney_web_cache", "midjourney_web_storage", "sprites",
    ],
    Group.VIDEO: ["video_projects"],
    Group.MODELS: ["musetalk", "weights", "huggingface"],
    Group.SETTINGS: ["logs", "layout", "template_cache", "templates"],
}

# The Models root and the Video root default to the same directory, and both
# groups keep their caches in a "cache" subdirectory of their own root. A move
# of one group must not carry the other group's cache away, so each cache
# subdirectory belongs to exactly one group and a move takes only the
# subdirectories its group owns. The rule holds whether or not the two roots
# coincide: a rule that changed with the roots let a subdirectory that the
# first move reported as left behind travel silently with the second move.
#
# Every name here is a literal argument of DataPaths.model_cache() or
# DataPaths.video_cache() somewhere in the tree, and
# tests/migration/test_data_migration.py pins that correspondence. A new cache
# name that no group owns is data that every move leaves behind.
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
SETTINGS_FILES = (
    "details.jsonl", "batch_jobs.json", "video_config.json", "sprite_configs.json",
)
SETTINGS_GLOBS = ("*_history.json", "*_session.json", "*_history.backup_*.json")

# Safety margin above the measured source size, in bytes.
FREE_SPACE_MARGIN = 256 * 1024 * 1024

# The journal that covers the window between the first rename and the config
# write. It sits beside config.json, which never moves, so a move cannot carry
# its own journal away. The name matches no SETTINGS_GLOBS pattern, so a later
# Settings move never picks it up as a source.
MOVE_INTENT_SUFFIX = ".move-intent"
INTENT_VERSION = 1

# A journal whose owning process is still alive describes a move that is still
# running, so the recovery leaves it alone. A process identifier is reused after
# a reboot, and an unrelated process that inherits the recorded number would
# block the repair for ever, so a journal older than this age is repaired
# whatever the identifier says.
INTENT_STALE_SECONDS = 7 * 24 * 60 * 60


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
    # Every path this move left in a place the user has to act on, as
    # (path_on_disk_now, the_path_it_relates_to). Two outcomes fill it.
    #
    # * ``ok=False``: a rollback could not put a directory back, so the pair is
    #   (where the data sits now, where it belongs). The data is in the wrong
    #   place and the application cannot see it.
    # * ``ok=True``: the copy succeeded and config.json names the destination,
    #   but the old copy could not be deleted, so the pair is (the leftover
    #   source, the destination copy that is now in use). This is the normal
    #   Windows outcome for a file this process still holds open. The data is
    #   safe; a full duplicate tree stays behind until the user removes it.
    stranded: List[Tuple[str, str]] = field(default_factory=list)


def legacy_dot_imageai_dir() -> Path:
    """The pre-move ~/.imageai tree."""
    return Path.home() / ".imageai"


def tree_size(path: Path) -> Tuple[int, int]:
    """Return ``(file_count, total_bytes)`` for a directory tree.

    Symbolic links count for nothing, on either side of a move. The move copies
    a link as a link, so the link's target contributes no bytes to the
    destination; counting the target here would make the free-space estimate
    and the post-copy verification disagree with what the copy actually wrote.
    """
    if path.is_symlink():
        return (0, 0)
    if not path.exists():
        return (0, 0)
    if path.is_file():
        return (1, path.stat().st_size)
    files = 0
    total = 0
    for entry in path.rglob("*"):
        if entry.is_symlink():
            continue
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


def _cache_sources(group: Group, paths: DataPaths) -> List[Tuple[Path, str]]:
    """List the cache directories that belong to this group.

    A move takes only the cache subdirectories its group owns, always. The
    Models root and the Video root coincide by default, and one ``cache``
    directory then holds both groups' caches, so a Models move must not carry
    the video render cache away from the path ``DataPaths.video_cache`` still
    points at. The same rule applies once the two roots differ: a rule that
    handed the whole directory to one group as soon as the roots differed let a
    subdirectory that the first move had reported as left behind travel
    silently with the second move.
    """
    if group not in CACHE_OWNERS:
        return []
    cache = paths.root(group) / CACHE_DIR
    if not cache.is_dir():
        return []
    entries: List[Tuple[Path, str]] = []
    for name in CACHE_OWNERS[group]:
        candidate = cache / name
        if os.path.lexists(candidate):
            entries.append((candidate, f"{CACHE_DIR}/{name}"))
    return entries


def unclaimed_cache_subdirs(group: Group, paths: DataPaths) -> List[Path]:
    """Cache subdirectories that belong to neither Models nor Video.

    The cache directory splits by owner. A subdirectory that no group claims
    stays behind, so every move that touches the directory reports it and the
    user can act on it.
    """
    if group not in CACHE_OWNERS:
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


def _configured_roots(group: Group, paths: DataPaths) -> Dict[str, Path]:
    """The roots the user has moved, for every group except this one.

    Only a root that config.json names counts. Every group defaults to the
    directory that holds config.json, so a rule based on the resolved roots
    would reject any destination under that directory and block the first move
    of every group. A configured root is different: the user put data there on
    purpose, and a destination that nests inside it, or that contains it, makes
    one group's move carry another group's data away.
    """
    try:
        data = config_io.read_config(paths.config_file())
    except config_io.ConfigIOError:
        # move_group reports an unreadable config.json with its own message and
        # stops before it touches anything.
        return {}
    roots = data.get("data_roots")
    if not isinstance(roots, dict):
        return {}
    configured: Dict[str, Path] = {}
    for name, value in roots.items():
        if name == group.value or not isinstance(value, str) or not value:
            continue
        configured[name] = Path(value)
    return configured


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
    span more than one tree: Video spans the app root and ~/.imageai. Every
    name in the result is unique, because two sources that share one name would
    merge silently.

    ``~/.cache/huggingface`` is deliberately absent from the Models group. That
    directory is the machine-wide HuggingFace hub cache, shared with every
    other transformers or diffusers tool on the machine, and ImageAI sets
    neither HF_HOME nor HUGGINGFACE_HUB_CACHE, so moving it would make those
    tools re-download their models. ImageAI passes an explicit ``cache_dir`` at
    each of its own download sites, and that directory is
    ``DataPaths.huggingface()`` under the Models root, so ImageAI's own weights
    still travel with the group.
    """
    paths = paths or get_data_paths()
    root = paths.root(group)
    entries: List[Tuple[Path, str]] = []

    for name in GROUP_CONTENTS[group]:
        candidate = root / name
        if os.path.lexists(candidate):
            entries.append((candidate, name))

    entries.extend(_cache_sources(group, paths))

    if group is Group.VIDEO:
        legacy = legacy_dot_imageai_dir()
        if legacy.exists():
            for child in sorted(legacy.iterdir()):
                if child.is_dir() or child.is_symlink():
                    entries.append((child, f"{LEGACY_IMAGEAI_NAME}/{child.name}"))

    if group is Group.SETTINGS:
        for filename in SETTINGS_FILES:
            candidate = root / filename
            if os.path.lexists(candidate):
                entries.append((candidate, filename))
        for pattern in SETTINGS_GLOBS:
            for candidate in sorted(root.glob(pattern)):
                if candidate.is_file():
                    entries.append((candidate, candidate.name))

    return entries


def unreachable_configured_root(
    group: Group, paths: Optional[DataPaths] = None
) -> Optional[Path]:
    """The root config.json names for a group when the group is not using it.

    ``core.paths`` falls back to the default directory when a configured root
    is unreachable — an unplugged drive, an offline share — and deliberately
    leaves config.json alone, so the configured path takes effect again as soon
    as the location returns. config.json is then the only record of where that
    data lives. Returns the configured path in that state, and None when the
    group runs on the root config.json names.
    """
    paths = paths or get_data_paths()
    try:
        data = config_io.read_config(paths.config_file())
    except config_io.ConfigIOError:
        # move_group reports an unreadable config.json with its own message.
        return None
    roots = data.get("data_roots")
    if not isinstance(roots, dict):
        return None
    configured = roots.get(group.value)
    if not isinstance(configured, str) or not configured:
        return None
    candidate = Path(configured)
    if _resolved(candidate) == _resolved(paths.root(group)):
        return None
    return candidate


def validate_destination(
    group: Group, dest: Path, paths: Optional[DataPaths] = None
) -> Optional[str]:
    """Return an error message, or None when the destination is usable."""
    paths = paths or get_data_paths()
    dest = Path(dest)

    # The offline-root test comes first. Every later test resolves through the
    # fallback root, and the move would end by writing the destination into
    # data_roots — over the only record of the offline location, which would
    # leave that data unreferenced when the drive comes back.
    offline = unreachable_configured_root(group, paths)
    if offline is not None:
        message = (
            f"The {group.value} data is recorded at {offline}, and that "
            f"location is not available now, so the application is using "
            f"{paths.root(group)} instead. Moving the {group.value} data now "
            f"would replace the recorded location and leave the data at "
            f"{offline} with nothing pointing at it. Reconnect that location, "
            f"or clear it in config.json, and try again."
        )
        logger.error("Cannot move %s to %s: %s", group.value, dest, message)
        return message

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
        resolved_source = _resolved(source)
        if resolved_dest == resolved_source:
            return "The destination is the same as the current location."
        if resolved_source in resolved_dest.parents:
            return (
                f"The destination is inside the folder being moved "
                f"({resolved_source}). Choose a folder outside it."
            )

    # No group's data may nest inside another group's root. A Video root under
    # the Images root travels away inside the Images tree at the next Images
    # move, and config.json still names the old path afterwards. Two groups
    # that share one root are fine: that is the default arrangement.
    for other, other_root in _configured_roots(group, paths).items():
        resolved_other = _resolved(other_root)
        if resolved_other == resolved_dest:
            continue
        if resolved_other in resolved_dest.parents:
            return (
                f"The destination is inside the folder that holds the {other} "
                f"data ({resolved_other}). A later {other} move would carry "
                f"the {group.value} data away with it. Choose a folder outside "
                f"it."
            )
        if resolved_dest in resolved_other.parents:
            return (
                f"The destination folder holds the {other} data "
                f"({resolved_other}). A later {group.value} move would carry "
                f"the {other} data away with it. Choose a folder outside it."
            )

    # The destination has to be a directory. An existing file, and a symlink
    # whose target is unreachable, both reach mkdir() as a FileExistsError, so
    # they are reported here instead.
    if os.path.lexists(dest) and not dest.is_dir():
        if dest.is_symlink():
            try:
                target = os.readlink(str(dest))
            except OSError:
                target = "an unreadable target"
            return (
                f"{dest} is a link that points nowhere ({target}). "
                f"Choose a folder that exists."
            )
        return f"{dest} is a file, not a folder. Choose a folder."

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
    """True when both paths live on the same filesystem volume.

    The source is measured without following a link. A rename moves the link
    itself, so the volume that matters is the one the link sits on, not the one
    its target sits on.
    """
    probe = dest
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        if os.name == "nt":
            a = os.path.splitdrive(os.path.abspath(str(source)))[0].lower()
            b = os.path.splitdrive(str(probe.resolve()))[0].lower()
            return bool(a) and a == b
        return os.lstat(str(source)).st_dev == probe.stat().st_dev
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


def _copy_link(source: Path, target: Path, state: dict, progress_cb) -> None:
    """Recreate a symbolic link at the destination.

    The link is the data, not the bytes it points at. Following it would copy a
    file the user deliberately kept outside the group into the group's tree,
    and a link whose target is unreachable would raise FileNotFoundError and
    abort the whole move — one dead link in a Models tree would then block
    every cross-volume move of that group, permanently.

    ``tree_size`` skips links on both sides, so a recreated link adds nothing
    to either counter and the verification still balances.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        link_target = os.readlink(str(source))
    except OSError as exc:
        logger.warning("Could not read the link %s: %s. It was skipped.", source, exc)
        return

    try:
        os.symlink(link_target, str(target),
                   target_is_directory=os.path.isdir(str(source)))
        return
    except OSError as exc:
        logger.warning(
            "Could not recreate the link %s -> %s at %s: %s",
            source, link_target, target, exc,
        )

    # Windows refuses to create a link without the privilege. Copy what the
    # link points at instead, and count those bytes, so the verification still
    # balances. A link that points nowhere holds no data at all.
    if not os.path.exists(str(source)):
        logger.warning(
            "Skipped the link %s -> %s: it points nowhere, so it holds no data.",
            source, link_target,
        )
        return
    if os.path.isdir(str(source)):
        shutil.copytree(str(source), str(target), symlinks=True, dirs_exist_ok=True)
        files, size = tree_size(target)
        _record_written_tree(state, target)
    else:
        shutil.copy2(str(source), str(target))
        files, size = (1, target.stat().st_size)
        _record_written(state, target, size)
    state["files"] += files
    state["bytes"] += size
    if progress_cb:
        progress_cb(state["files"], state["files_total"],
                    state["bytes"], state["bytes_total"], str(source))


def _record_written(state: dict, target: Path, size: int) -> None:
    """Remember the size the copy wrote for one destination file.

    The post-copy verification compares each of these against the file on disk.
    An aggregate byte total measured at the destination alone can only catch a
    miscounting loop; a per-file record catches a file that another writer
    truncated or replaced after the copy wrote it, and it catches a file the
    copy never wrote at all. It cannot catch a rewrite that keeps the length —
    that needs a hash of every byte, and the Models group is tens of gigabytes.
    """
    state.setdefault("written", []).append((target, size))


def _record_written_tree(state: dict, target: Path) -> None:
    """Record every regular file of a tree the copy wrote in one call."""
    try:
        entries = sorted(target.rglob("*"))
    except OSError as exc:
        logger.warning("Could not list the copied tree %s to verify it: %s", target, exc)
        return
    for entry in entries:
        if entry.is_symlink() or not entry.is_file():
            continue
        try:
            _record_written(state, entry, entry.stat().st_size)
        except OSError as exc:
            logger.warning("Could not measure the copied file %s: %s", entry, exc)


def _copy_file(source: Path, target: Path) -> int:
    """Copy one regular file and return the number of bytes that landed.

    A copy that wrote fewer bytes than the source held when it started is a
    short write — a full disk that reported no error, a network share that
    dropped the tail. The move must not delete the source after one of those,
    so the failure is raised here and the caller aborts the whole move. A
    source that grew during the copy is not a failure: the copy read to the end
    of the file as it stood, and the destination is then larger than the size
    measured first.
    """
    try:
        before = source.stat().st_size
    except OSError:
        before = None
    shutil.copy2(source, target)
    written = target.stat().st_size
    if before is not None and written < before:
        raise OSError(
            f"the copy of {source} wrote {written} bytes, but the file held "
            f"{before} bytes when the copy started"
        )
    return written


def _copy_entry(source: Path, target: Path, state: dict, progress_cb, cancel) -> None:
    """Copy one file, directory tree, or symbolic link, reporting per file.

    The counters measure the bytes that landed in the destination, not the
    bytes the source holds now. A live file — the log file this process writes
    — can grow between the copy and the measurement, and a source-side count
    would then disagree with the destination for a copy that in fact succeeded.
    """
    if source.is_symlink():
        _copy_link(source, target, state, progress_cb)
        return

    if source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        written = _copy_file(source, target)
        _record_written(state, target, written)
        state["files"] += 1
        state["bytes"] += written
        if progress_cb:
            progress_cb(state["files"], state["files_total"],
                        state["bytes"], state["bytes_total"], str(source))
        return

    for entry in sorted(source.rglob("*")):
        if _is_cancelled(cancel):
            raise MoveCancelled()
        relative = entry.relative_to(source)
        destination = target / relative
        # The link test comes first: a link to a directory answers is_dir()
        # with True, and mkdir() would replace it with an empty real folder.
        if entry.is_symlink():
            _copy_link(entry, destination, state, progress_cb)
            continue
        if entry.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        written = _copy_file(entry, destination)
        _record_written(state, destination, written)
        state["files"] += 1
        state["bytes"] += written
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


def intent_file_path(paths: Optional[DataPaths] = None) -> Path:
    """The journal that records a rename move in progress.

    It sits beside config.json. config.json never moves — it records where
    every other directory lives — so the journal cannot be carried away by the
    move it describes. A journal inside a group's own tree would travel to the
    destination with that tree and the next start would never find it.
    """
    paths = paths or get_data_paths()
    config = paths.config_file()
    return config.with_name(config.name + MOVE_INTENT_SUFFIX)


def _process_is_alive(pid) -> bool:
    """True when a process with this identifier is running on this host.

    The recovery uses it to leave a move that is still running alone. This
    process itself never counts: a startup recovery runs before any move of
    this process starts, and treating our own identifier as alive would make a
    recycled identifier block the repair.
    """
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    if pid == os.getpid():
        return False

    if os.name == "nt":  # pragma: no cover - exercised on Windows only
        # os.kill(pid, 0) terminates the process on Windows, so the query goes
        # through the API that only reads.
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Another user owns it, so it exists.
        return True
    except OSError:
        return False
    return True


def _journal_is_stale(path: Path) -> bool:
    """True when the journal is too old for its recorded owner to be believed."""
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return False
    return age > INTENT_STALE_SECONDS


def _write_intent(
    paths: DataPaths,
    group: Group,
    dest: Path,
    entries: Sequence[Tuple[Path, Path]],
) -> Tuple[Path, str]:
    """Record a rename move before the first rename runs.

    ``os.rename`` commits each directory one at a time, and config.json is
    written only after the last one. A power loss in that window leaves every
    directory at the destination and config.json naming the old root, and
    without this record nothing on disk says so: the next start resolves the
    group to an empty default and reports no warning. The record closes that
    window, and ``recover_interrupted_move`` acts on it at the next start.

    Raises ConfigError when the record cannot be written. A move that cannot be
    journalled must not start, because an interruption would then be
    undetectable — and a configuration directory that refuses this write would
    refuse the config.json update at the end of the move anyway.

    Returns ``(path, token)``. The token names this move, and ``_clear_intent``
    removes the journal only when the record still carries it: two moves must
    never delete each other's record.
    """
    token = uuid.uuid4().hex
    record = {
        "version": INTENT_VERSION,
        "group": group.value,
        "dest": str(dest),
        "config_file": str(paths.config_file()),
        "entries": [[str(source), str(target)] for source, target in entries],
        # The indices of the entries whose rename has committed. See
        # _mark_moved: without it, a source directory that startup re-created
        # makes a completed rename look as if it never ran.
        "moved": [],
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pid": os.getpid(),
        "host": platform.node(),
        "token": token,
    }
    path = intent_file_path(paths)
    config_io.write_config(path, record)
    logger.info("Recorded the %s move to %s in %s", group.value, dest, path)
    return (path, token)


def _mark_moved(path: Path, index: int) -> None:
    """Record that one entry's rename has committed.

    The journal records paths, and the recovery used to read the state of the
    move off those paths alone: an entry counted as moved only when the target
    existed and the source did not. Startup re-creates directories — the file
    logger creates the log directory under the root config.json still names —
    so a re-created source made a committed rename look as if it never ran, and
    the recovery then "put back" the entries that really had moved and reported
    that the data was unchanged. This mark states the fact directly, at the
    moment the rename makes it true.

    A failure here is logged and the move continues. The recovery still falls
    back to the shape on disk, which is correct in every case except a source
    that something re-created.
    """
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("the journal does not hold a JSON object")
        moved = record.get("moved")
        if not isinstance(moved, list):
            moved = []
        if index not in moved:
            moved.append(index)
        record["moved"] = moved
        config_io.write_config(path, record)
    except (OSError, ValueError, config_io.ConfigIOError) as exc:
        logger.error(
            "Could not record the completed rename of entry %d in the move "
            "journal %s: %s", index, path, exc,
        )


def _clear_intent(path: Path, token: Optional[str] = None) -> None:
    """Remove the journal once config.json names the new root.

    ``token`` is the identifier ``_write_intent`` returned for this move. The
    journal is removed only when the record still carries it, so a move that
    overlapped another one cannot delete the only description of that other
    move. Pass None only from the recovery, which has already established that
    no other process owns the record.

    A journal left behind is not dangerous: the next recovery finds every
    directory at the destination and config.json already naming it, and clears
    the record without touching anything. Every failure is logged.
    """
    if token is not None:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError) as exc:
            logger.error(
                "Could not read the move journal %s before removing it: %s. "
                "It was left in place.", path, exc,
            )
            return
        found = record.get("token") if isinstance(record, dict) else None
        if found != token:
            logger.error(
                "The move journal %s describes another move, so this move left "
                "it in place. Restart the application to repair that move.",
                path,
            )
            return

    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        logger.warning("Could not remove the completed move journal %s: %s", path, exc)


def _read_intent(path: Path) -> Optional[dict]:
    """Parse the journal, or return None when it holds nothing usable."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        # Not the same as a corrupt record. A sharing violation, an antivirus
        # scan or a dropped mount is transient, and the journal is the only
        # record that the move happened at all, so it must survive. The caller
        # tells these apart: a corrupt record is removed, this one is kept.
        logger.error("Could not read the move journal %s: %s", path, exc)
        raise
    try:
        record = json.loads(raw)
    except ValueError as exc:
        logger.error("Could not parse the move journal %s: %s", path, exc)
        return None
    if not isinstance(record, dict):
        logger.error("The move journal %s does not hold a JSON object.", path)
        return None
    try:
        Group(record["group"])
        if not isinstance(record["dest"], str) or not record["dest"]:
            raise ValueError("dest is not a path")
        entries = record["entries"]
        if not isinstance(entries, list):
            raise TypeError("entries is not a list")
        for pair in entries:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError("an entry is not a (source, target) pair")
            if not all(isinstance(item, str) and item for item in pair):
                raise ValueError("an entry names something that is not a path")
    except (KeyError, TypeError, ValueError) as exc:
        logger.error("The move journal %s is incomplete: %s", path, exc)
        return None

    # "moved" arrived after the first version of the journal, so a record
    # without it is valid and states nothing. A malformed one is dropped rather
    # than trusted: the recovery then reads the state off the disk, which is
    # what it did before the mark existed.
    moved = record.get("moved", [])
    if not isinstance(moved, list) or not all(
        isinstance(item, int) and not isinstance(item, bool)
        and 0 <= item < len(record["entries"]) for item in moved
    ):
        logger.error(
            "The move journal %s records an unusable list of completed "
            "renames (%r); the recovery reads the folders instead.", path, moved,
        )
        moved = []
    record["moved"] = moved
    return record


def _is_empty_dir(path: Path) -> bool:
    """True when the path is a real directory that holds nothing."""
    try:
        if path.is_symlink() or not path.is_dir():
            return False
        return not any(path.iterdir())
    except OSError:
        return False


def _entry_location(source: Path, target: Path, marked_moved: bool) -> str:
    """Say where one journal entry's data sits: "dest", "source" or "missing".

    The rename mark decides it whenever the move recorded one. Without a mark
    the shape on disk decides, and an empty source directory beside a target
    that holds data counts as moved: a rename never leaves the source behind,
    so an empty directory at the source is something that re-created it —
    ``setup_logging`` creates the log directory from the root config.json still
    names. Treating that empty directory as "the data is still home" made the
    recovery undo a move that had in fact succeeded.
    """
    if not os.path.lexists(target):
        return "source" if os.path.lexists(source) else "missing"
    if marked_moved or not os.path.lexists(source):
        return "dest"
    if _is_empty_dir(source) and not _is_empty_dir(target):
        return "dest"
    return "source"


def _owner_is_running(record: dict, path: Path) -> bool:
    """True when the process that wrote this journal is still running.

    A second ImageAI window starts while the first one runs a move. Its
    recovery would find the journal of that running move, see the directories
    that have already been renamed, write config.json for a move that has not
    finished, and delete the record. The owner test stops it: the journal stays
    on disk, and the move that owns it finishes or is repaired at a later
    start.

    A process identifier is only meaningful on the host that issued it, and it
    is reused after a reboot, so the test applies only to a record written on
    this host and only while the record is recent.
    """
    host = record.get("host")
    if isinstance(host, str) and host and host != platform.node():
        return False
    if _journal_is_stale(path):
        return False
    return _process_is_alive(record.get("pid"))


def recover_interrupted_move(paths: Optional[DataPaths] = None) -> Optional[str]:
    """Finish or undo a rename move that a crash interrupted. Startup calls it.

    Returns a one-line summary when it acted, or None when there was nothing to
    do. The check costs one ``lexists`` call on the usual path, so it never
    delays a normal start, and every failure is logged rather than raised: a
    recovery problem must not stop the application.

    Two outcomes are possible.

    * Every directory sits at the destination. The move finished on disk, and
      only the config.json write was lost, so the recovery writes the new root
      and the user keeps the move.
    * Some directories sit at the destination and some at the source. The move
      is half done, so the recovery renames the moved ones back and leaves
      config.json alone. A journal it could not act on stays on disk, so the
      next start tries again and the user has the evidence.
    """
    paths = paths or get_data_paths()
    path = intent_file_path(paths)
    if not os.path.lexists(path):
        return None

    logger.warning("Found an interrupted storage move recorded in %s", path)
    try:
        record = _read_intent(path)
    except OSError as exc:
        # The record is there and may be perfectly good; this start could not
        # read it. Keep it, so the next start can. Removing it here would
        # destroy the only evidence of the move the journal exists to record.
        message = (
            f"An interrupted storage move is recorded in {path}, but this "
            f"start could not read the record: {exc}. It was left in place for "
            f"the next start. Your data was not touched."
        )
        logger.error(message)
        return message
    if record is not None and _owner_is_running(record, path):
        logger.warning(
            "The move recorded in %s belongs to process %s on %s, and that "
            "process is still running, so this start left the move alone.",
            path, record.get("pid"), record.get("host"),
        )
        return None
    if record is None:
        _clear_intent(path)
        message = (
            f"An interrupted storage move was recorded in {path}, but the "
            f"record could not be read. Check your data folders by hand. The "
            f"unreadable record was removed."
        )
        logger.error(message)
        return message

    group = Group(record["group"])
    dest = Path(record["dest"])
    entries = [(Path(source), Path(target)) for source, target in record["entries"]]

    moved = set(record.get("moved") or [])
    located = [
        (source, target, _entry_location(source, target, index in moved))
        for index, (source, target) in enumerate(entries)
    ]
    at_dest = [(s, t) for s, t, where in located if where == "dest"]
    still_home = [(s, t) for s, t, where in located if where == "source"]

    if not at_dest:
        _clear_intent(path)
        if still_home:
            message = (
                f"A {group.value} storage move to {dest} was interrupted before "
                f"it moved anything. Your data is unchanged."
            )
            logger.warning(message)
        else:
            message = (
                f"A {group.value} storage move to {dest} was interrupted, and "
                f"none of its folders are at either location. Check {dest} and "
                f"{paths.root(group)} by hand."
            )
            logger.error(message)
        return message

    if len(at_dest) == len(entries):
        try:
            current = config_io.read_config(paths.config_file())
        except config_io.ConfigIOError as exc:
            message = (
                f"A {group.value} storage move to {dest} finished, but "
                f"config.json could not be read to record it: {exc} The data "
                f"is at {dest}. Repair config.json and start again."
            )
            logger.error(message)
            return message

        already = (current.get("data_roots") or {}).get(group.value)
        if already == str(dest):
            _clear_intent(path)
            message = (
                f"A {group.value} storage move to {dest} had already been "
                f"recorded. Nothing needed repair."
            )
            logger.info(message)
            return message

        try:
            _write_root(paths, group, dest)
        except ConfigError as exc:
            message = (
                f"A {group.value} storage move to {dest} finished, but the new "
                f"location could not be recorded: {exc} The data is at {dest}. "
                f"The record was kept at {path} for the next start."
            )
            logger.error(message)
            return message

        _clear_intent(path)
        reset_data_paths()
        message = (
            f"Finished an interrupted {group.value} storage move: the data is "
            f"at {dest}, and that location is now recorded. Restart the "
            f"application if anything still reads the old location."
        )
        logger.warning(message)
        return message

    # A half-done move. Put back what crossed, and leave config.json alone.
    failed: List[Tuple[Path, Path]] = []
    for source, target in reversed(at_dest):
        # Startup can re-create the source as an empty directory before the
        # recovery runs. os.rename refuses to replace an existing directory on
        # Windows, and the empty directory holds nothing, so it goes first.
        if _is_empty_dir(source):
            try:
                source.rmdir()
                logger.warning(
                    "Removed the empty %s that startup re-created, so the "
                    "interrupted move can put the data back.", source,
                )
            except OSError as exc:
                logger.error(
                    "Could not remove the empty %s before putting %s back: %s",
                    source, target, exc,
                )
        try:
            os.rename(str(target), str(source))
            logger.warning("Moved %s back to %s after an interrupted move.",
                           target, source)
        except OSError as exc:
            logger.error(
                "Could not move %s back to %s after an interrupted move: %s. "
                "That folder holds the only copy of the data.",
                target, source, exc,
            )
            failed.append((target, source))

    if failed:
        listed = "; ".join(f"{target} -> {source}" for target, source in failed)
        message = (
            f"A {group.value} storage move to {dest} was interrupted. These "
            f"folders could not be put back and hold the only copy of your "
            f"data: {listed}. Move each one back by hand. The record was kept "
            f"at {path}."
        )
        logger.error(message)
        return message

    _clear_intent(path)
    message = (
        f"A {group.value} storage move to {dest} was interrupted part way, so "
        f"the {len(at_dest)} folder(s) that had moved were put back. Your data "
        f"is where it was."
    )
    logger.warning(message)
    return message


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
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        # validate_destination rejects a destination that is a file or a dead
        # link. This guard catches the same shapes when another program creates
        # one between the check and here, and it reports them as a result
        # rather than as an exception out of move_group.
        message = f"Could not create the folder {dest}: {exc}. Nothing was changed."
        logger.error("Cannot move %s to %s: %s", group.value, dest, message)
        return MoveResult(ok=False, error=message)

    # Fast path: a rename within one volume finishes in milliseconds. This
    # matters most for Models, where a cross-volume copy runs for many minutes.
    if all(_same_volume(source, dest) for source, _n in sources):
        renamed: List[Tuple[Path, Path]] = []
        rename_dirs: List[Path] = []
        rename_error: Optional[OSError] = None
        collision: Optional[Path] = None
        cancelled = False

        # One journal covers one move. A second move that overwrote the record
        # would destroy the only description of the first one, so a record that
        # is still on disk stops this move instead.
        #
        # The test and the write share one critical section, under the
        # config.json lock. Without it, two windows both find no journal, both
        # write one, and the second record replaces the first — the first
        # move's data is then unreferenced with nothing on disk to describe it.
        # The lock covers threads of this process and other processes on the
        # host, and it is held only for the test and the write, never for the
        # renames.
        existing = intent_file_path(paths)
        try:
            with config_io.config_lock(paths.config_file()):
                if os.path.lexists(existing):
                    message = (
                        f"An earlier storage move was interrupted and has not "
                        f"been repaired yet ({existing}). Restart the "
                        f"application to repair it, then try again. Nothing "
                        f"was changed."
                    )
                    logger.error("Cannot move %s to %s: %s",
                                 group.value, dest, message)
                    _remove_created([], created_dirs)
                    return MoveResult(ok=False, error=message)

                # Journal the move before the first rename commits. See
                # _write_intent: without the record, a crash before the
                # config.json write leaves the data at the destination with
                # nothing on disk to say so.
                intent, intent_token = _write_intent(
                    paths, group, dest,
                    [(source, dest / name) for source, name in sources],
                )
        except ConfigError as exc:
            message = (
                f"Could not record the move before starting it: {exc} "
                f"Nothing was changed."
            )
            logger.error("Cannot move %s to %s: %s", group.value, dest, message)
            _remove_created([], created_dirs)
            return MoveResult(ok=False, error=message)

        for index, (source, name) in enumerate(sources):
            # Cancel is checked per entry. A same-volume move used to run to
            # completion after the user pressed Cancel, and the dialog then
            # reported "Move complete".
            if _is_cancelled(cancel):
                cancelled = True
                break
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
            # The rename has committed, so the journal must say so before the
            # next one starts. See _mark_moved.
            _mark_moved(intent, index)

        # A rollback that stranded a directory leaves the group split across
        # two places. The journal describes exactly that split, so it stays on
        # disk and the recovery at the next start retries the rename that
        # failed here. A rollback that put everything back needs no record.
        def _undo(reason: str, suffix: str) -> MoveResult:
            stranded = _rollback_renames(renamed)
            if not stranded:
                _clear_intent(intent, intent_token)
            else:
                logger.error(
                    "Kept the move journal %s: %d folder(s) could not be put "
                    "back, and the next start retries them.", intent, len(stranded),
                )
            _remove_created([], rename_dirs + created_dirs)
            return _failed(group, dest, reason, stranded, suffix)

        if cancelled:
            if not renamed:
                _clear_intent(intent, intent_token)
                _remove_created([], rename_dirs + created_dirs)
                logger.info("Move of %s cancelled by the user; source left intact",
                            group.value)
                return MoveResult(ok=False,
                                  error="Move cancelled. Nothing was changed.")
            result = _undo("The move was cancelled.",
                           " Nothing was changed.")
            if not result.stranded:
                logger.info("Move of %s cancelled by the user; source left intact",
                            group.value)
                return MoveResult(ok=False,
                                  error="Move cancelled. Nothing was changed.")
            return result

        if collision is not None:
            return _undo(
                f"Something else created {collision} while the move was "
                f"running, so the move stopped.",
                " Nothing was changed. Move that folder away and try again.",
            )

        if rename_error is None:
            try:
                _write_root(paths, group, dest)
            except ConfigError as exc:
                logger.error("Could not record the new %s root: %s", group.value, exc)
                return _undo(str(exc), " Your data was left where it was.")
            _clear_intent(intent, intent_token)
            _cleanup_empty_legacy_dirs(group)
            logger.info("Moved %s to %s by rename (%d files)", group.value, dest, files_total)
            return MoveResult(ok=True, files_moved=files_total,
                              bytes_moved=bytes_total, used_rename=True)

        # Undo the renames that did succeed. Without the rollback, a source
        # already under the destination would be destroyed by the cleanup that
        # a later cancel or copy failure runs.
        stranded = _rollback_renames(renamed)
        if stranded:
            logger.error(
                "Kept the move journal %s: %d folder(s) could not be put back, "
                "and the next start retries them.", intent, len(stranded),
            )
            _remove_created([], rename_dirs + created_dirs)
            return _failed(
                group, dest,
                f"The move failed ({rename_error}) and part of it could not be undone.",
                stranded, "",
            )
        # The copy path takes over. It never renames, so the journal has
        # nothing left to describe, and the destination directory stays because
        # the copy reuses it.
        _clear_intent(intent, intent_token)
        _remove_created([], rename_dirs)
        logger.warning("Rolled back the partial rename of %s; falling back to copy",
                       group.value)

    state = {"files": 0, "bytes": 0, "files_total": files_total,
             "bytes_total": bytes_total, "written": []}
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

    # Verify twice, and only then delete a source.
    #
    # Per file: every file the copy wrote must still be at the destination with
    # exactly the length the copy wrote, and each of those files was at least as
    # long as its source when the copy read it (_copy_file raises otherwise).
    # This catches a short write, a file another writer truncated or replaced
    # after the copy, and a file that vanished. It does not compare contents: a
    # rewrite that keeps the length is not detected, because hashing tens of
    # gigabytes of model weights would take longer than the move.
    #
    # In total: the destination must hold no more than the copy wrote. The
    # counters come from the copy loop, not from the pre-scan totals, because a
    # source that grows during the move — the log file this process writes —
    # must not fail a copy that in fact succeeded. Every name is unique, so each
    # source contributes to the count exactly once.
    problems = _verify_written(state["written"])
    copied_files = sum(tree_size(target)[0] for target in created_entries)
    copied_bytes = sum(tree_size(target)[1] for target in created_entries)
    if problems or (copied_files, copied_bytes) != (state["files"], state["bytes"]):
        _remove_created(created_entries, created_dirs)
        if problems:
            listed = "; ".join(problems[:5])
            if len(problems) > 5:
                listed += f", and {len(problems) - 5} more"
            message = (
                f"Verification failed: {len(problems)} file(s) at the "
                f"destination do not match what the copy wrote ({listed}). "
                f"Your data was left where it was."
            )
        else:
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

    # A source the delete step could not remove is a full duplicate tree that
    # nothing points at. Windows refuses to delete a file this process still
    # holds open — close_data_handles cannot release the active log file or
    # PyTorch-mapped weights — so this is the normal outcome there, not an edge
    # case. The move did succeed, and the result says where every leftover is.
    leftovers: List[Tuple[str, str]] = []
    for source, name in sources:
        try:
            # The link test comes first. shutil.rmtree refuses to remove a link
            # to a directory, so a source that was a symlink used to survive
            # the move: the copy reported success and the old location stayed
            # in place, invisible, holding a second copy of the data.
            if source.is_symlink():
                source.unlink()
            elif source.is_dir():
                shutil.rmtree(source)
            else:
                source.unlink()
        except OSError as exc:
            logger.error(
                "Could not remove %s after the move to %s: %s. That copy stays "
                "on disk and nothing points at it; remove it by hand.",
                source, dest / name, exc,
            )
            leftovers.append((str(source), str(dest / name)))

    _cleanup_empty_legacy_dirs(group)
    logger.info("Moved %s to %s (%d files, %s)", group.value, dest,
                state["files"], _human(state["bytes"]))
    return MoveResult(ok=True, files_moved=state["files"],
                      bytes_moved=state["bytes"], stranded=leftovers)


def _verify_written(written: Sequence[Tuple[Path, int]]) -> List[str]:
    """Name every destination file that no longer matches what the copy wrote.

    Each entry is one file and the length the copy gave it. The check re-reads
    the length now, so it catches a file that disappeared, a file another writer
    truncated, and a file another writer replaced with one of a different
    length. It says nothing about the bytes inside a file of the right length.
    """
    problems: List[str] = []
    for target, size in written:
        try:
            actual = target.stat().st_size
        except OSError as exc:
            problems.append(f"{target} could not be read back ({exc})")
            continue
        if actual != size:
            problems.append(
                f"{target} holds {actual} bytes, but the copy wrote {size}"
            )
    return problems


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
