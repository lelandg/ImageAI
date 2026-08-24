"""Single source of truth for every ImageAI data path.

This module resolves the four relocatable data groups — Images, Video, Models,
and Settings — to directories on disk. Each group defaults to the platform user
directory and may be overridden per group in ``config.json``.

IMPORTANT: this module must not import ``core.logging_config`` or
``core.config``. The file logger asks this module where the log directory is,
so this module runs before the logger exists. Errors here go into a deferred
buffer that the logger drains once it starts. See ``drain_warnings``.

``core.config_io`` is the one exception, and it is deliberate. It is standalone
stdlib-only code, and it owns the rules that say what a valid ``config.json``
document and a valid ``data_roots`` entry look like. This module used to parse
the file itself with laxer rules, so a document that ``config_io`` rejected —
a JSON array, a ``null``, a numeric override — reached ``Path()`` here and
raised out of ``setup_logging``. The application then could not start at all,
and the interrupted-move recovery, which builds the same singleton, never ran.
Whatever ``config.json`` holds, this module warns and uses the platform
defaults. It never raises.

The logger starts after the Settings root resolves but before the Images,
Video and Models roots resolve. A warning about one of those three roots would
therefore sit in the buffer for the rest of the run, because only the logger
and the GUI Storage Locations widget ever drain it. To close that gap the
logger installs a warning sink with ``set_warning_sink`` as soon as it attaches
its handlers. Every later warning then goes straight to the log and to stderr.
"""

from __future__ import annotations

import os
import platform
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import config_io

APP_NAME = "ImageAI"  # duplicated from core.constants to avoid the import cycle

WarningSink = Callable[[str], None]

_WARNING_SINK: Optional[WarningSink] = None


def set_warning_sink(sink: Optional[WarningSink]) -> None:
    """Install the process-wide destination for storage warnings.

    ``core.logging_config.setup_logging`` calls this once its handlers exist.
    A warning raised after that point goes to the sink at once, so a CLI run
    prints it to stderr and writes it to the log file. A warning raised before
    that point stays in the per-instance buffer that ``drain_warnings``
    returns, and the logger drains that buffer at startup.

    The sink is one slot, not a list. Two installs replace each other, so one
    warning reaches the sink one time. Pass ``None`` to remove the sink.
    """
    global _WARNING_SINK
    _WARNING_SINK = sink


class Group(str, Enum):
    """A relocatable group of data directories."""

    IMAGES = "images"
    VIDEO = "video"
    MODELS = "models"
    SETTINGS = "settings"


def platform_default_dir() -> Path:
    """Return the platform user data directory. Never changes."""
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        return Path(os.getenv("APPDATA", home / "AppData" / "Roaming")) / APP_NAME
    if system == "Darwin":
        return home / "Library" / "Application Support" / APP_NAME
    return Path(os.getenv("XDG_CONFIG_HOME", home / ".config")) / APP_NAME


def config_file_path() -> Path:
    """Return the path of config.json. This file never moves."""
    return platform_default_dir() / "config.json"


class DataPaths:
    """Resolves data paths for each group, honouring config overrides."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self._config_path = Path(config_path) if config_path else config_file_path()
        self._warnings: List[str] = []
        self._overrides = self._read_overrides()
        self._resolved: Dict[Group, Path] = {}

    # -- configuration -----------------------------------------------------

    def _read_overrides(self) -> Dict[str, str]:
        """Return the per-group overrides config.json records.

        Every failure ends in the same place: a warning and an empty override
        map, which means every group keeps the platform default. A damaged
        config.json must never stop the application from starting, because
        this runs inside ``setup_logging`` before anything can catch it.
        """
        try:
            document = config_io.read_config_document(self._config_path)
        except config_io.ConfigReadError as exc:
            # The message already names the file and the reason.
            self._warn(f"{exc} Using default storage locations.")
            return {}
        except Exception as exc:  # noqa: BLE001 - startup must survive anything
            self._warn(
                f"Could not read config.json at {self._config_path}: "
                f"{type(exc).__name__}: {exc}. Using default storage locations."
            )
            return {}

        if document is None:
            return {}  # fresh install: no file, no overrides, no warning

        overrides, problems = config_io.data_root_overrides(
            document, source=self._config_path,
        )
        for problem in problems:
            self._warn(f"{problem} Using the default location instead.")
        return overrides

    # -- roots -------------------------------------------------------------

    def root(self, group: Group) -> Path:
        """Return the root directory for a group.

        Falls back to the platform default when no override is set, or when the
        configured override is unreachable. An unreachable override is recorded
        as a warning and never rewritten to disk, so the configured path takes
        effect again as soon as the location returns.
        """
        cached = self._resolved.get(group)
        if cached is not None:
            return cached

        default = self._config_path.parent
        configured = self._overrides.get(group.value)

        if not configured:
            resolved = default
        else:
            candidate = Path(str(configured))
            if self._is_reachable(candidate):
                resolved = candidate
            else:
                self._warn(
                    f"Storage location for '{group.value}' is unavailable: "
                    f"{candidate}. Using the default location instead: {default}"
                )
                resolved = default

        self._resolved[group] = resolved
        return resolved

    @staticmethod
    def _is_reachable(path: Path) -> bool:
        """True when the path exists as a writable directory.

        A configured root that no longer exists is unreachable. A removable
        drive that the user unplugged, or a network share that went offline,
        both produce this condition. The resolver then falls back to the
        platform default for that group and records a warning.

        A path the operating system refuses to look at is unreachable too:
        ``os.access`` raises ValueError on an embedded NUL byte, and a broken
        mount raises OSError. Neither may escape into startup.
        """
        try:
            return path.is_dir() and os.access(path, os.W_OK)
        except (OSError, ValueError):
            return False

    def _warn(self, message: str) -> None:
        """Record a warning and deliver it to the sink when one is installed.

        The message always stays in the buffer. The GUI Storage Locations
        widget drains the buffer to mark the affected rows, so the buffer must
        keep the message even when the sink already reported it.
        """
        self._warnings.append(message)
        sink = _WARNING_SINK
        if sink is None:
            return
        try:
            sink(message)
        except Exception:
            # A broken sink must never stop path resolution. The message stays
            # in the buffer, so drain_warnings can still report it.
            pass

    def drain_warnings(self) -> List[str]:
        """Return buffered warnings and clear the buffer."""
        buffered, self._warnings = self._warnings, []
        return buffered

    # -- Images ------------------------------------------------------------

    def generated(self) -> Path:
        return self.root(Group.IMAGES) / "generated"

    def images(self) -> Path:
        return self.root(Group.IMAGES) / "images"

    def composites(self) -> Path:
        return self.root(Group.IMAGES) / "composites"

    def styles(self) -> Path:
        return self.root(Group.IMAGES) / "styles"

    def characters(self) -> Path:
        return self.root(Group.IMAGES) / "Characters"

    def midjourney_cache(self) -> Path:
        return self.root(Group.IMAGES) / "midjourney_web_cache"

    def midjourney_storage(self) -> Path:
        return self.root(Group.IMAGES) / "midjourney_web_storage"

    # -- Video -------------------------------------------------------------

    def video_projects(self) -> Path:
        return self.root(Group.VIDEO) / "video_projects"

    def video_cache(self, name: str) -> Path:
        return self.root(Group.VIDEO) / "cache" / name

    def video_events_db(self) -> Path:
        return self.video_projects() / "events.db"

    # -- Models ------------------------------------------------------------

    def models(self) -> Path:
        return self.root(Group.MODELS)

    def musetalk(self) -> Path:
        return self.root(Group.MODELS) / "musetalk"

    def weights(self) -> Path:
        return self.root(Group.MODELS) / "weights"

    def model_cache(self, name: str) -> Path:
        return self.root(Group.MODELS) / "cache" / name

    def huggingface(self) -> Path:
        return self.root(Group.MODELS) / "huggingface"

    # -- Settings ----------------------------------------------------------

    def settings_root(self) -> Path:
        return self.root(Group.SETTINGS)

    def logs(self) -> Path:
        return self.root(Group.SETTINGS) / "logs"

    def layout(self) -> Path:
        return self.root(Group.SETTINGS) / "layout"

    def template_cache(self) -> Path:
        return self.root(Group.SETTINGS) / "template_cache"

    def history_file(self, name: str) -> Path:
        return self.root(Group.SETTINGS) / f"{name}_history.json"

    def session_file(self, name: str) -> Path:
        return self.root(Group.SETTINGS) / f"{name}_session.json"

    def batch_jobs(self) -> Path:
        return self.root(Group.SETTINGS) / "batch_jobs.json"

    def details(self) -> Path:
        return self.root(Group.SETTINGS) / "details.jsonl"

    # -- Fixed -------------------------------------------------------------

    def config_file(self) -> Path:
        """config.json never moves; it records where everything else lives."""
        return self._config_path

    def ensure(self, path: Path) -> Path:
        """Create a directory and return it."""
        path.mkdir(parents=True, exist_ok=True)
        return path


_INSTANCE: Optional[DataPaths] = None


def get_data_paths() -> DataPaths:
    """Return the process-wide DataPaths singleton."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = DataPaths()
    return _INSTANCE


def reset_data_paths() -> None:
    """Drop the singleton. Used by tests and after a completed move."""
    global _INSTANCE
    _INSTANCE = None
