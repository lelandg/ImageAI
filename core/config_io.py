"""Locked, atomic access to ImageAI's ``config.json``.

``config.json`` is the bootstrap file. It holds the API keys and the
``data_roots`` entry that records where every other data directory lives. Two
writers own it: :class:`core.config.ConfigManager` and the storage migrator in
``core.data_migration``. Both run a read-modify-write cycle, and both can run at
the same time — ``ConfigManager`` is built on worker threads by
``providers/google.py``, ``gui/workers.py`` and ``core/video/ffmpeg_utils.py``
while a long move runs. Without one lock held across the whole cycle, a writer's
read is stale by the time it writes, and the other writer's change disappears.

This module is deliberately standalone. It must not import ``core.config``,
``core.paths`` or ``core.logging_config``: both writers depend on it, and
``core/paths.py`` carries a no-dependency guard test.

Public API
----------
``read_config(path)``
    Parse the file. A missing file returns ``{}`` — that is a fresh install.
    Every other failure raises :class:`ConfigReadError`. The caller must never
    treat an unreadable file as an empty one.
``read_config_document(path)``
    The same parse, but a missing file returns ``None``. A caller that merges
    its own document over the disk one needs "there is no document" apart from
    "the document is empty": an empty file is a writer that removed every key,
    while a missing file is no statement about any key at all.
``write_config(path, data)``
    Write the whole document atomically: a temporary file in the same
    directory, flushed, fsynced, then ``os.replace``. Raises
    :class:`ConfigWriteError`.
``config_lock(path, timeout=...)``
    Context manager that holds the exclusive lock. It serialises threads inside
    one process and processes on the host. A lock it cannot take within
    ``timeout`` raises :class:`ConfigLockError` instead of hanging the caller.
``update_config(path, mutate, timeout=...)``
    The whole read-modify-write cycle under the lock. ``mutate`` receives the
    parsed document and returns the document to write (or mutates in place and
    returns ``None``). This is the call every writer should use.
``quarantine_unreadable(path)``
    Copy an unreadable ``config.json`` to a timestamped sidecar beside it, so a
    later write can never be the only copy. Returns the sidecar path, or
    ``None`` when the copy failed — in which case the caller must not write.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

logger = logging.getLogger(__name__)

# A save runs at application shutdown. A wait longer than this means another
# writer is stuck, and a stuck shutdown looks like a hang to the user.
DEFAULT_TIMEOUT = 15.0

_POLL_INTERVAL = 0.02

PathLike = Union[str, "os.PathLike[str]", Path]


class ConfigIOError(Exception):
    """Base class for every config.json access failure."""


class ConfigReadError(ConfigIOError):
    """config.json exists but could not be read or parsed.

    The caller must never fall back to an empty document: the file still holds
    the API keys and the data_roots entry, and a full overwrite destroys them.
    """


class ConfigWriteError(ConfigIOError):
    """config.json could not be replaced. The previous file is unchanged."""


class ConfigLockError(ConfigIOError):
    """The config.json lock could not be taken within the timeout."""


# --- OS-level file lock -----------------------------------------------------
# Import one module per platform. The guard keeps the import off the other OS.

if os.name == "nt":  # pragma: no cover - exercised on Windows only
    import msvcrt

    def _try_lock(fileno: int) -> None:
        """Take the exclusive lock, or raise OSError when another owner holds it."""
        msvcrt.locking(fileno, msvcrt.LK_NBLCK, 1)

    def _release_lock(fileno: int) -> None:
        try:
            msvcrt.locking(fileno, msvcrt.LK_UNLCK, 1)
        except OSError as exc:
            logger.warning("Could not release the config.json lock: %s", exc)

else:
    import fcntl

    def _try_lock(fileno: int) -> None:
        """Take the exclusive lock, or raise OSError when another owner holds it."""
        fcntl.flock(fileno, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _release_lock(fileno: int) -> None:
        try:
            fcntl.flock(fileno, fcntl.LOCK_UN)
        except OSError as exc:
            logger.warning("Could not release the config.json lock: %s", exc)


# --- in-process lock registry ----------------------------------------------
# An OS file lock does not serialise threads of one process: on POSIX the lock
# belongs to the open file description, and on Windows a second handle in the
# same process can take the region again. A per-path threading lock closes that
# hole. The registry is keyed by the absolute path, so two ConfigManager
# instances that point at one file share one lock.

_registry_guard = threading.Lock()
_thread_locks: Dict[str, threading.Lock] = {}
_local = threading.local()


def _lock_key(config_path: PathLike) -> str:
    return os.path.normcase(os.path.abspath(str(config_path)))


def _thread_lock_for(key: str) -> threading.Lock:
    with _registry_guard:
        lock = _thread_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _thread_locks[key] = lock
        return lock


def _held_depths() -> Dict[str, int]:
    depths = getattr(_local, "config_lock_depths", None)
    if depths is None:
        depths = {}
        _local.config_lock_depths = depths
    return depths


def _lock_file_path(config_path: Path) -> Path:
    """The sidecar the lock is taken on.

    The lock never goes on config.json itself. An atomic write replaces that
    file's inode, so a lock held on the old inode would stop protecting the
    name the next writer opens.
    """
    return config_path.with_name(config_path.name + ".lock")


def _acquire_file_lock(config_path: Path, deadline: float):
    """Open the lock file and take the OS lock.

    Returns ``(handle, locked)``. ``handle`` is ``None`` when the lock file
    could not be opened at all — a read-only configuration directory, for
    example. The in-process lock still applies in that case, so the caller
    continues with a warning instead of failing the save.
    """
    lock_path = _lock_file_path(config_path)
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(lock_path, "a+b")
    except OSError as exc:
        logger.warning(
            "Could not open the config lock file %s: %s. "
            "Threads of this process are still serialised.",
            lock_path, exc,
        )
        return (None, False)

    try:
        while True:
            try:
                _try_lock(handle.fileno())
                return (handle, True)
            except OSError as exc:
                if time.monotonic() >= deadline:
                    message = (
                        f"Timed out waiting for the config.json lock at "
                        f"{lock_path}: {exc}. Another ImageAI process or a "
                        f"storage move still holds it."
                    )
                    logger.error(message)
                    raise ConfigLockError(message) from exc
                time.sleep(_POLL_INTERVAL)
    except BaseException:
        handle.close()
        raise


@contextmanager
def config_lock(config_path: PathLike, timeout: float = DEFAULT_TIMEOUT):
    """Hold the exclusive config.json lock for the whole block.

    The lock covers threads of this process and other processes on the host.
    Re-entry from the same thread is allowed and takes no second OS lock,
    because a second flock on a new descriptor would deadlock against the one
    this thread already holds.
    """
    path = Path(config_path)
    key = _lock_key(path)
    depths = _held_depths()

    if depths.get(key):
        depths[key] += 1
        try:
            yield
        finally:
            depths[key] -= 1
            if depths[key] <= 0:
                depths.pop(key, None)
        return

    wait = max(float(timeout), _POLL_INTERVAL)
    deadline = time.monotonic() + wait

    thread_lock = _thread_lock_for(key)
    if not thread_lock.acquire(timeout=wait):
        message = (
            f"Timed out waiting for the config.json lock for {path}. "
            f"Another thread of this process still holds it."
        )
        logger.error(message)
        raise ConfigLockError(message)

    handle = None
    locked = False
    try:
        handle, locked = _acquire_file_lock(path, deadline)
        depths[key] = 1
        try:
            yield
        finally:
            depths.pop(key, None)
    finally:
        if handle is not None:
            if locked:
                _release_lock(handle.fileno())
            handle.close()
        thread_lock.release()


def read_config(config_path: PathLike) -> Dict[str, Any]:
    """Return the parsed config.json.

    A missing file returns ``{}``: that is a fresh install, and it must keep
    working. Every other failure raises :class:`ConfigReadError`, so no caller
    can mistake an unreadable file for an empty one.
    """
    document = read_config_document(config_path)
    if document is None:
        return {}
    return document


def read_config_document(config_path: PathLike) -> Optional[Dict[str, Any]]:
    """Return the parsed config.json, or ``None`` when the file is missing.

    A merging caller must tell two states apart. A file that holds ``{}`` is a
    writer that removed every key, and those deletions must stick. A file that
    is not there says nothing about any key, and the caller keeps what it
    already holds. Every failure other than "not there" raises
    :class:`ConfigReadError`.
    """
    path = Path(config_path)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except UnicodeDecodeError as exc:
        message = f"Could not decode {path} as UTF-8: {exc}"
        logger.error(message)
        raise ConfigReadError(message) from exc
    except OSError as exc:
        message = f"Could not read {path}: {exc}"
        logger.error(message)
        raise ConfigReadError(message) from exc

    try:
        data = json.loads(raw)
    except ValueError as exc:
        message = f"Could not parse {path}: {exc}"
        logger.error(message)
        raise ConfigReadError(message) from exc

    if not isinstance(data, dict):
        message = f"{path} does not hold a JSON object (found {type(data).__name__})."
        logger.error(message)
        raise ConfigReadError(message)

    # An absent entry is valid: no group was ever moved. An entry that is
    # present must be an object. A JSON null is not one — a writer that
    # mutates data_roots in place fails on it, and by then the move has
    # already renamed the directories.
    if "data_roots" in data and not isinstance(data["data_roots"], dict):
        found = type(data["data_roots"]).__name__
        message = (
            f"The 'data_roots' entry in {path} is not a JSON object "
            f"(found {found})."
        )
        logger.error(message)
        raise ConfigReadError(message)

    return data


def _fsync_directory(directory: Path) -> None:
    """Flush the directory entry so the rename survives a power loss."""
    if os.name == "nt":  # pragma: no cover - Windows cannot open a directory
        return
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError as exc:
        logger.debug("Could not open %s to fsync it: %s", directory, exc)
        return
    try:
        os.fsync(fd)
    except OSError as exc:
        logger.debug("Could not fsync %s: %s", directory, exc)
    finally:
        os.close(fd)


def write_config(config_path: PathLike, data: Dict[str, Any]) -> None:
    """Replace config.json atomically.

    The content goes to a temporary file in the same directory, is flushed and
    fsynced, and then replaces config.json in one step. A crash during the
    write therefore cannot truncate the bootstrap file.
    """
    path = Path(config_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        message = f"Could not create {path.parent}: {exc}"
        logger.error(message)
        raise ConfigWriteError(message) from exc

    try:
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        )
    except OSError as exc:
        message = f"Could not create a temporary file beside {path}: {exc}"
        logger.error(message)
        raise ConfigWriteError(message) from exc

    tmp_path = Path(handle.name)
    try:
        with handle:
            json.dump(data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(tmp_path), str(path))
    except Exception as exc:  # noqa: BLE001 - every failure must be reported
        message = f"Could not write {path}: {exc}. The previous file is unchanged."
        logger.error(message)
        try:
            tmp_path.unlink()
        except OSError:
            logger.warning("Could not remove the temporary file %s", tmp_path)
        raise ConfigWriteError(message) from exc

    _fsync_directory(path.parent)


def quarantine_unreadable(config_path: PathLike) -> Optional[Path]:
    """Copy an unreadable config.json to a timestamped sidecar beside it.

    The sidecar keeps the API keys and the data_roots entry recoverable when a
    writer has to replace a file it could not parse. Returns the sidecar path,
    or ``None`` when the copy failed. A caller that gets ``None`` must not
    write, because its write would then be the only copy.
    """
    path = Path(config_path)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.name}.corrupt-{stamp}")
    counter = 1
    while target.exists():
        target = path.with_name(f"{path.name}.corrupt-{stamp}-{counter}")
        counter += 1

    try:
        shutil.copy2(str(path), str(target))
    except OSError as exc:
        logger.error(
            "Could not preserve the unreadable %s as %s: %s. Nothing was overwritten.",
            path, target, exc,
        )
        return None

    logger.error("Preserved the unreadable %s as %s.", path, target)
    return target


def update_config(
    config_path: PathLike,
    mutate: Callable[[Dict[str, Any]], Optional[Dict[str, Any]]],
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Run one read-modify-write cycle on config.json under the lock.

    ``mutate`` receives the parsed document. It returns the document to write,
    or ``None`` to write the document it was given after mutating it in place.
    Raises :class:`ConfigLockError`, :class:`ConfigReadError` or
    :class:`ConfigWriteError`; on any of them config.json is unchanged.
    """
    path = Path(config_path)
    with config_lock(path, timeout=timeout):
        data = read_config(path)
        result = mutate(data)
        if result is None:
            result = data
        write_config(path, result)
        return result
