# Configurable Storage Locations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user relocate ImageAI's four data groups — Images, Video, Models, Settings — to directories of their choosing from the Settings tab.

**Architecture:** A new `core/paths.py` module owns every data path in the application. It reads optional per-group root overrides from `config.json` and falls back to today's platform defaults, so an existing installation sees no change. Every current path source — 36 resolver calls, 10 inline platform-directory builders, 7 `~/.imageai` call sites, and 4 HuggingFace download sites — is rewired to call it. A headless `core/data_migration.py` then physically relocates a group and updates the config, and a Settings-tab UI drives it.

**Tech Stack:** Python 3.12, PySide6, pytest. No new dependencies.

**Design doc:** `Plans/2026-08-10-storage-locations-design.md` (read this first).

## Global Constraints

- Python 3.12. On WSL/Linux use `.venv_linux`; never mix it with `.venv`.
- Run `python3 -m pytest` before every commit. Never commit on a broken build.
- Conventional Commits, subject under 72 characters.
- Every error must reach the file logger, including every error shown to a user.
- `config.json` NEVER moves. It is the bootstrap anchor that records where the other groups live.
- `core/paths.py` must not import `core/logging_config.py` or `core/config.py`. The logger depends on it, so it must have no logging dependency of its own.
- No new third-party dependencies. Standard library only for paths and migration.
- Do NOT touch these paths — they belong to other software: gcloud (`core/gcloud_utils.py:46`, `core/gcloud_utils.py:75`, `providers/google.py:408`, `providers/google.py:1511`), system fonts (`core/layout/font_manager.py:85-98`), ffmpeg (`core/video/audio_segmenter.py:40`), and the shared HuggingFace hub read at `core/character_animator/installer.py:254`.
- Platform defaults do not change. A fresh install writes exactly where it writes today.

## Deviation from the design doc

The design doc's section 6 says `move_group` must "refuse to move the Video group while a database connection is open". Detecting a foreign process's SQLite connection is not reliably possible. This plan implements the practical equivalent instead: `move_group` accepts a `pre_move` callback that the GUI uses to close its own connections, and the migrator runs `PRAGMA wal_checkpoint(TRUNCATE)` to fold the write-ahead log into the main database before copying. Task 13 updates the design doc to match.

---

## File Structure

**Created:**

| File | Responsibility |
|---|---|
| `core/paths.py` | The single path resolver. `Group` enum, `DataPaths` class, module-level singleton. No I/O beyond reading `config.json`. |
| `core/data_migration.py` | Headless group relocation: validate, copy or rename, verify, commit, delete. No Qt imports. |
| `gui/storage_settings_widget.py` | The Storage Locations group box, the size worker, and the move flow. |
| `tests/test_paths.py` | `DataPaths` unit tests. |
| `tests/migration/test_data_migration.py` | Migrator unit tests. |
| `tests/test_no_hardcoded_paths.py` | Guard test: no straggler path sources remain. |
| `tests/gui/test_storage_settings.py` | Construction smoke test. |

**Modified:** `core/logging_config.py`, `core/constants.py`, `core/config.py`, `core/utils.py`, `core/musetalk_installer.py`, `core/styles/store.py`, `core/layout/template_manager.py`, `core/character_animator/{installer,ai_face_editor,face_generator,segmenter}.py`, `core/video/{config,project_manager,project_enhancements,veo_client,image_generator,thumbnail_manager}.py`, `providers/{google,local_sd}.py`, `gui/{history_widget,midjourney_dialog,main_window,prompt_builder,prompt_generation_dialog,prompt_question_dialog_old,install_dialog,local_sd_widget,model_browser}.py`, `gui/video/{history_tab,video_project_tab}.py`, `gui/character_animator/{install_dialog,puppet_wizard}.py`, `gui/font_generator/font_wizard.py`, `gui/layout/layout_tab.py`, `CHANGELOG.md`, `core/constants.py` (version).

---

## Task 1: The `DataPaths` resolver

**Files:**
- Create: `core/paths.py`
- Test: `tests/test_paths.py`

**Interfaces:**
- Consumes: nothing. This is the foundation task.
- Produces:
  - `class Group(str, Enum)` with members `IMAGES`, `VIDEO`, `MODELS`, `SETTINGS` and values `"images"`, `"video"`, `"models"`, `"settings"`.
  - `platform_default_dir() -> Path`
  - `config_file_path() -> Path`
  - `class DataPaths` with `root(group: Group) -> Path`, `drain_warnings() -> list[str]`, and the accessors listed in Step 3.
  - `get_data_paths() -> DataPaths` (module singleton), `reset_data_paths() -> None` (test hook).

- [x] **Step 1: Write the failing tests**

Create `tests/test_paths.py`:

```python
"""Unit tests for the DataPaths resolver."""
import json

import pytest

from core.paths import (
    DataPaths,
    Group,
    get_data_paths,
    reset_data_paths,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_data_paths()
    yield
    reset_data_paths()


def _write_config(tmp_path, payload):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(payload), encoding="utf-8")
    return cfg


def test_default_root_is_config_dir_when_no_override(tmp_path):
    cfg = _write_config(tmp_path, {})
    dp = DataPaths(config_path=cfg)
    assert dp.root(Group.IMAGES) == tmp_path


def test_override_is_used_when_reachable(tmp_path):
    dest = tmp_path / "elsewhere"
    dest.mkdir()
    cfg = _write_config(tmp_path, {"data_roots": {"images": str(dest)}})
    dp = DataPaths(config_path=cfg)
    assert dp.root(Group.IMAGES) == dest


def test_override_applies_only_to_its_own_group(tmp_path):
    dest = tmp_path / "elsewhere"
    dest.mkdir()
    cfg = _write_config(tmp_path, {"data_roots": {"images": str(dest)}})
    dp = DataPaths(config_path=cfg)
    assert dp.root(Group.IMAGES) == dest
    assert dp.root(Group.VIDEO) == tmp_path
    assert dp.root(Group.MODELS) == tmp_path
    assert dp.root(Group.SETTINGS) == tmp_path


def test_null_override_falls_back_to_default(tmp_path):
    cfg = _write_config(tmp_path, {"data_roots": {"images": None}})
    dp = DataPaths(config_path=cfg)
    assert dp.root(Group.IMAGES) == tmp_path


def test_unreachable_override_falls_back_and_warns(tmp_path):
    missing = tmp_path / "no" / "such" / "drive"
    cfg = _write_config(tmp_path, {"data_roots": {"images": str(missing)}})
    dp = DataPaths(config_path=cfg)

    assert dp.root(Group.IMAGES) == tmp_path
    warnings = dp.drain_warnings()
    assert len(warnings) == 1
    assert str(missing) in warnings[0]
    assert "images" in warnings[0].lower()


def test_unreachable_override_does_not_rewrite_config(tmp_path):
    missing = tmp_path / "gone"
    cfg = _write_config(tmp_path, {"data_roots": {"images": str(missing)}})
    dp = DataPaths(config_path=cfg)
    dp.root(Group.IMAGES)

    on_disk = json.loads(cfg.read_text(encoding="utf-8"))
    assert on_disk["data_roots"]["images"] == str(missing)


def test_drain_warnings_empties_the_buffer(tmp_path):
    missing = tmp_path / "gone"
    cfg = _write_config(tmp_path, {"data_roots": {"images": str(missing)}})
    dp = DataPaths(config_path=cfg)
    dp.root(Group.IMAGES)

    assert dp.drain_warnings()
    assert dp.drain_warnings() == []


def test_missing_config_file_uses_defaults(tmp_path):
    dp = DataPaths(config_path=tmp_path / "absent.json")
    assert dp.root(Group.IMAGES) == tmp_path
    assert dp.drain_warnings() == []


def test_corrupt_config_uses_defaults_and_warns(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("{not json", encoding="utf-8")
    dp = DataPaths(config_path=cfg)

    assert dp.root(Group.IMAGES) == tmp_path
    assert any("config.json" in w for w in dp.drain_warnings())


def test_accessors_sit_under_the_right_roots(tmp_path):
    images = tmp_path / "I"
    video = tmp_path / "V"
    models = tmp_path / "M"
    for d in (images, video, models):
        d.mkdir()
    cfg = _write_config(tmp_path, {"data_roots": {
        "images": str(images), "video": str(video), "models": str(models),
    }})
    dp = DataPaths(config_path=cfg)

    assert dp.generated() == images / "generated"
    assert dp.composites() == images / "composites"
    assert dp.styles() == images / "styles"
    assert dp.characters() == images / "Characters"
    assert dp.midjourney_cache() == images / "midjourney_web_cache"

    assert dp.video_projects() == video / "video_projects"
    assert dp.video_cache("thumbnails") == video / "cache" / "thumbnails"
    assert dp.video_events_db() == video / "video_projects" / "events.db"

    assert dp.musetalk() == models / "musetalk"
    assert dp.weights() == models / "weights"
    assert dp.huggingface() == models / "huggingface"

    assert dp.logs() == tmp_path / "logs"
    assert dp.history_file("prompt") == tmp_path / "prompt_history.json"


def test_config_file_never_moves(tmp_path):
    dest = tmp_path / "elsewhere"
    dest.mkdir()
    cfg = _write_config(tmp_path, {"data_roots": {"settings": str(dest)}})
    dp = DataPaths(config_path=cfg)

    assert dp.root(Group.SETTINGS) == dest
    assert dp.config_file() == cfg
    assert dp.config_file().parent == tmp_path


def test_get_data_paths_returns_a_singleton():
    assert get_data_paths() is get_data_paths()


def test_reset_data_paths_clears_the_singleton():
    first = get_data_paths()
    reset_data_paths()
    assert get_data_paths() is not first


def test_paths_module_imports_no_logging_or_config():
    """core/paths.py must stay importable before the logger exists."""
    import ast
    import pathlib

    source = pathlib.Path("core/paths.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert not any("logging_config" in name for name in imported)
    assert not any(name in ("core.config", ".config") for name in imported)
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_paths.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.paths'`

- [x] **Step 3: Write the implementation**

Create `core/paths.py`:

```python
"""Single source of truth for every ImageAI data path.

This module resolves the four relocatable data groups — Images, Video, Models,
and Settings — to directories on disk. Each group defaults to the platform user
directory and may be overridden per group in ``config.json``.

IMPORTANT: this module must not import ``core.logging_config`` or
``core.config``. The file logger asks this module where the log directory is,
so this module runs before the logger exists. Errors here go into a deferred
buffer that the logger drains once it starts. See ``drain_warnings``.
"""

from __future__ import annotations

import json
import os
import platform
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

APP_NAME = "ImageAI"  # duplicated from core.constants to avoid the import cycle


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

    def _read_overrides(self) -> Dict[str, Any]:
        if not self._config_path.exists():
            return {}
        try:
            data = json.loads(self._config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self._warnings.append(
                f"Could not read config.json at {self._config_path}: {exc}. "
                f"Using default storage locations."
            )
            return {}
        roots = data.get("data_roots")
        return roots if isinstance(roots, dict) else {}

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
            candidate = Path(configured)
            if self._is_reachable(candidate):
                resolved = candidate
            else:
                self._warnings.append(
                    f"Storage location for '{group.value}' is unavailable: "
                    f"{candidate}. Using the default location instead: {default}"
                )
                resolved = default

        self._resolved[group] = resolved
        return resolved

    @staticmethod
    def _is_reachable(path: Path) -> bool:
        """True when the path exists, or when its parent exists and is writable."""
        if path.is_dir():
            return os.access(path, os.W_OK)
        parent = path.parent
        return parent.is_dir() and os.access(parent, os.W_OK)

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
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_paths.py -v`
Expected: PASS, 15 tests.

- [x] **Step 5: Run the full suite**

Run: `python3 -m pytest`
Expected: PASS. Nothing imports `core/paths.py` yet, so the count rises by 15 with no failures.

- [x] **Step 6: Commit**

```bash
git add core/paths.py tests/test_paths.py
git commit -m "feat(paths): add DataPaths resolver for relocatable data groups"
```

---

## Task 2: Remove the hardcoded developer username

**Files:**
- Modify: `providers/google.py:1083`, `providers/google.py:1292`
- Test: `tests/test_no_hardcoded_paths.py`

**Interfaces:**
- Consumes: `core.paths.get_data_paths` from Task 1.
- Produces: `tests/test_no_hardcoded_paths.py`, which Task 12 extends with the straggler sweep.

This ships a real bug fix independent of the Move feature: released code writes to `C:/Users/aboog/...`, the author's own machine.

- [x] **Step 1: Write the failing test**

Create `tests/test_no_hardcoded_paths.py`:

```python
"""Guard tests: no source file may hardcode a developer-specific path."""
import pathlib

SOURCE_DIRS = ("core", "gui", "cli", "providers")


def _python_files():
    for directory in SOURCE_DIRS:
        yield from pathlib.Path(directory).rglob("*.py")


def test_no_hardcoded_user_profile_paths():
    offenders = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            lowered = line.lower()
            if "c:/users/" in lowered or "c:\\\\users\\\\" in lowered:
                offenders.append(f"{path}:{lineno}: {line.strip()}")
    assert not offenders, "Hardcoded user-profile paths found:\n" + "\n".join(offenders)
```

- [x] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_no_hardcoded_paths.py -v`
Expected: FAIL, listing `providers/google.py:1083` and `providers/google.py:1292`.

- [x] **Step 3: Fix both call sites**

In `providers/google.py`, both blocks currently read:

```python
                                    if platform.system() == "Windows":
                                        debug_dir = Path("C:/Users/aboog/AppData/Roaming/ImageAI/generated")
                                    else:
                                        debug_dir = Path.home() / ".config" / "ImageAI" / "generated"
```

Replace each with:

```python
                                    from core.paths import get_data_paths
                                    debug_dir = get_data_paths().generated()
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_no_hardcoded_paths.py -v`
Expected: PASS.

- [x] **Step 5: Run the full suite**

Run: `python3 -m pytest`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add providers/google.py tests/test_no_hardcoded_paths.py
git commit -m "fix(google): remove hardcoded developer path from debug dumps"
```

---

## Task 3: Route the logger through `DataPaths`

**Files:**
- Modify: `core/logging_config.py:27-37`, `core/logging_config.py:141-151`
- Modify: `main.py:120-121`
- Test: `tests/test_paths.py` (extend)

**Interfaces:**
- Consumes: `core.paths.get_data_paths`, `DataPaths.logs()`, `DataPaths.drain_warnings()` from Task 1.
- Produces: `setup_logging()` keeps its existing signature `(log_level=logging.INFO, log_to_file=True) -> Path | None`.

The logger is the first consumer and the ordering constraint that shaped Task 1. It must drain the deferred warning buffer as soon as handlers exist.

- [x] **Step 1: Write the failing test**

Append to `tests/test_paths.py`:

```python
def test_logger_uses_the_settings_root(tmp_path, monkeypatch):
    """setup_logging must write under DataPaths.logs(), not a hardcoded dir."""
    import logging

    import core.paths as paths_mod
    from core.logging_config import setup_logging

    dest = tmp_path / "settings_root"
    dest.mkdir()
    cfg = _write_config(tmp_path, {"data_roots": {"settings": str(dest)}})

    monkeypatch.setattr(paths_mod, "_INSTANCE", paths_mod.DataPaths(config_path=cfg))
    try:
        log_file = setup_logging(log_level=logging.INFO, log_to_file=True)
        assert log_file is not None
        assert Path(log_file).parent == dest / "logs"
    finally:
        logging.getLogger().handlers.clear()
```

Add `from pathlib import Path` to the imports at the top of `tests/test_paths.py`.

- [x] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_paths.py::test_logger_uses_the_settings_root -v`
Expected: FAIL — the log file lands under the real `%APPDATA%`/`~/.config` directory, not `dest`.

- [x] **Step 3: Rewrite both log-directory blocks**

In `core/logging_config.py`, replace the block at lines 27-37:

```python
    # Determine log directory based on platform
    system = platform.system()
    if system == "Windows":
        import os
        log_dir = Path(os.environ.get('APPDATA', '')) / 'ImageAI' / 'logs'
    elif system == "Darwin":  # macOS
        log_dir = Path.home() / 'Library' / 'Application Support' / 'ImageAI' / 'logs'
    else:  # Linux
        log_dir = Path.home() / '.config' / 'ImageAI' / 'logs'

    log_dir.mkdir(parents=True, exist_ok=True)
```

with:

```python
    # Resolve the log directory through the single path resolver. This import
    # is safe here: core.paths deliberately has no logging dependency.
    from core.paths import get_data_paths

    data_paths = get_data_paths()
    log_dir = data_paths.logs()
    log_dir.mkdir(parents=True, exist_ok=True)
```

Apply the identical replacement to the second block at lines 141-151.

- [x] **Step 4: Drain the deferred warnings**

In `setup_logging`, immediately after the file handler is attached to
`root_logger` and before the function returns, add:

```python
    # core.paths runs before the logger exists, so it buffers its own warnings.
    # Emit them now that handlers are attached.
    for message in data_paths.drain_warnings():
        root_logger.warning(message)
```

- [x] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_paths.py -v`
Expected: PASS, 16 tests.

- [x] **Step 6: Verify the app still starts and logs**

Run: `python3 main.py --help`
Expected: the CLI help prints, and a fresh `imageai_*.log` appears under the settings root's `logs/` directory.

- [x] **Step 7: Run the full suite and commit**

```bash
python3 -m pytest
git add core/logging_config.py tests/test_paths.py
git commit -m "refactor(logging): resolve log directory through DataPaths"
```

---

## Task 4: Rewire the `core/` call sites

**Files:**
- Modify: `core/constants.py:140-158`, `core/config.py:21-46`, `core/config.py:234-238`, `core/config.py:268-270`, `core/utils.py:180-186`, `core/musetalk_installer.py:59-75`, `core/styles/store.py:50-51`, `core/layout/template_manager.py:188`, `core/character_animator/installer.py:248`, `core/character_animator/ai_face_editor.py:111`, `core/character_animator/face_generator.py:58`, `core/character_animator/segmenter.py:108`
- Test: `tests/test_paths.py` (extend)

**Interfaces:**
- Consumes: `core.paths.get_data_paths`, all accessors from Task 1.
- Produces: `get_user_data_dir()` in `core/constants.py` becomes a thin deprecated shim delegating to `DataPaths.settings_root()`; `ConfigManager.config_dir` stays a property so its ~30 existing readers keep working.

Apply this exact mapping:

| File:line | Old expression | New expression |
|---|---|---|
| `core/constants.py:140` | body of `get_user_data_dir()` | `return get_data_paths().settings_root()` |
| `core/constants.py:161` | `BATCH_JOBS_PATH = get_user_data_dir() / "batch_jobs.json"` | delete the constant; see Step 3 |
| `core/config.py:32` | `_get_config_dir()` body | `return get_data_paths().config_file().parent` |
| `core/config.py:23` | `self.details_path = self.config_dir / "details.jsonl"` | `self.details_path = get_data_paths().details()` |
| `core/config.py:234` | `images_dir = self.config_dir / "images"` | `images_dir = get_data_paths().images()` |
| `core/config.py:268` | `templates_dir = self.config_dir / "templates" / "layouts"` | `templates_dir = get_data_paths().settings_root() / "templates" / "layouts"` |
| `core/utils.py:184` | `d = config.config_dir / "generated"` | `d = get_data_paths().generated()` (and drop the now-unused `ConfigManager` import in that function) |
| `core/musetalk_installer.py:71-75` | the three-branch platform block | `base = get_data_paths().musetalk()`; see Step 4 for the Linux legacy check |
| `core/styles/store.py:51` | `base_dir = get_user_data_dir() / "styles"` | `base_dir = get_data_paths().styles()` |
| `core/layout/template_manager.py:188` | `cache_dir = config.config_dir / "template_cache"` | `cache_dir = get_data_paths().template_cache()` |
| `core/character_animator/installer.py:248` | `get_user_data_dir() / "weights" / "character_animator"` | `get_data_paths().weights() / "character_animator"` |
| `core/character_animator/ai_face_editor.py:111` | `get_user_data_dir() / "cache" / "ai_visemes"` | `get_data_paths().model_cache("ai_visemes")` |
| `core/character_animator/face_generator.py:58` | `get_user_data_dir() / "cache" / "ai_visemes"` | `get_data_paths().model_cache("ai_visemes")` |
| `core/character_animator/segmenter.py:108` | `get_user_data_dir() / "weights" / "character_animator" / "sam2_hiera_large.pt"` | `get_data_paths().weights() / "character_animator" / "sam2_hiera_large.pt"` |

Leave `core/character_animator/installer.py:254` (`~/.cache/huggingface/hub`) exactly as it is — it reads a cache that other tools own.

- [x] **Step 1: Write the failing tests**

Append to `tests/test_paths.py`:

```python
def test_musetalk_keeps_legacy_linux_cache(tmp_path, monkeypatch):
    """An existing ~/.cache/imageai/musetalk must not trigger a 4 GB re-download."""
    import core.paths as paths_mod
    from core.musetalk_installer import get_musetalk_model_path

    legacy = tmp_path / ".cache" / "imageai" / "musetalk"
    legacy.mkdir(parents=True)
    (legacy / "musetalk").mkdir()

    cfg = _write_config(tmp_path, {})
    monkeypatch.setattr(paths_mod, "_INSTANCE", paths_mod.DataPaths(config_path=cfg))
    monkeypatch.setattr(paths_mod.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setattr("core.musetalk_installer.Path.home", staticmethod(lambda: tmp_path))

    assert get_musetalk_model_path() == legacy


def test_musetalk_uses_models_root_when_no_legacy_dir(tmp_path, monkeypatch):
    import core.paths as paths_mod
    from core.musetalk_installer import get_musetalk_model_path

    models = tmp_path / "M"
    models.mkdir()
    cfg = _write_config(tmp_path, {"data_roots": {"models": str(models)}})
    monkeypatch.setattr(paths_mod, "_INSTANCE", paths_mod.DataPaths(config_path=cfg))
    monkeypatch.setattr("core.musetalk_installer.Path.home", staticmethod(lambda: tmp_path))

    assert get_musetalk_model_path() == models / "musetalk"


def test_styles_store_uses_the_images_root(tmp_path, monkeypatch):
    import core.paths as paths_mod

    images = tmp_path / "I"
    images.mkdir()
    cfg = _write_config(tmp_path, {"data_roots": {"images": str(images)}})
    monkeypatch.setattr(paths_mod, "_INSTANCE", paths_mod.DataPaths(config_path=cfg))

    from core.styles.store import StyleStore

    assert StyleStore().base_dir == images / "styles"
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_paths.py -k "musetalk or styles_store" -v`
Expected: FAIL — the legacy check does not exist and the store still uses `get_user_data_dir()`.

- [x] **Step 3: Apply the mapping table**

Work through every row above. For `core/constants.py`, replace the whole body of `get_user_data_dir` and delete the module-level constant:

```python
def get_user_data_dir() -> Path:
    """Deprecated. Use ``core.paths.get_data_paths()`` directly.

    Retained so external scripts keep working. Returns the Settings root.
    """
    from core.paths import get_data_paths

    return get_data_paths().settings_root()
```

`BATCH_JOBS_PATH` is a module-level constant, so it freezes the path at import
time and would ignore any later move. Delete it and give callers a function:

```python
def batch_jobs_path() -> Path:
    """Path of the OpenAI Batch API job ledger."""
    from core.paths import get_data_paths

    return get_data_paths().batch_jobs()
```

Then update every importer. Find them with:

```bash
grep -rn "BATCH_JOBS_PATH" --include=*.py .
```

Replace each `BATCH_JOBS_PATH` reference with a `batch_jobs_path()` call and fix
the import on the same line.

- [x] **Step 4: Add the MuseTalk legacy-directory check**

Replace the body of `get_musetalk_model_path` in `core/musetalk_installer.py`:

```python
def get_musetalk_model_path() -> Path:
    """Return the MuseTalk weights directory.

    Older Linux installs kept weights in ~/.cache/imageai/musetalk. Keep using
    that directory when it already holds data, so no user re-downloads 4 GB.
    """
    from core.paths import get_data_paths

    legacy = Path.home() / ".cache" / "imageai" / "musetalk"
    if legacy.is_dir() and any(legacy.iterdir()):
        return legacy
    return get_data_paths().musetalk()
```

- [x] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_paths.py -v`
Expected: PASS, 19 tests.

- [x] **Step 6: Verify no `core/` straggler remains**

Run:

```bash
grep -rn "get_user_data_dir()\|config_dir /" --include=*.py core/ | grep -v "core/paths.py\|core/constants.py"
```

Expected: no output.

- [x] **Step 7: Run the full suite and commit**

```bash
python3 -m pytest
git add core/ tests/test_paths.py
git commit -m "refactor(core): resolve core data paths through DataPaths"
```

---

## Task 5: Rewire the video subsystem and the `~/.imageai` tree

**Files:**
- Modify: `core/video/config.py:105-113`, `core/video/project_manager.py:33-39`, `core/video/project_enhancements.py:323-329`, `core/video/veo_client.py:461`, `core/video/veo_client.py:917`, `core/video/veo_client.py:987`, `core/video/image_generator.py:54`, `core/video/thumbnail_manager.py:30`, `gui/video/history_tab.py:195`, `gui/video/video_project_tab.py:1827`, `gui/video/video_project_tab.py:2013`
- Test: `tests/video/test_video_paths.py`

**Interfaces:**
- Consumes: `DataPaths.video_projects()`, `DataPaths.video_cache(name)`, `DataPaths.video_events_db()`, `DataPaths.generated()` from Task 1.
- Produces: nothing new. All eleven call sites resolve through the Video root afterwards.

Apply this exact mapping:

| File:line | Old expression | New expression |
|---|---|---|
| `core/video/config.py:107-111` | three-branch platform block building `config_dir` | `config_dir = get_data_paths().settings_root()` — this is the `video_config.json` settings file, so it belongs to Settings, not Video |
| `core/video/project_manager.py:35-39` | three-branch block building `base_dir` | `base_dir = get_data_paths().video_projects()` |
| `core/video/project_enhancements.py:325-329` | three-branch block building `base_dir` | `base_dir = get_data_paths().video_projects()` |
| `core/video/veo_client.py:461` | `Path(config_mgr.get('output_dir', Path.home() / 'AppData' / ...))` | `Path(config_mgr.get('output_dir') or get_data_paths().generated())` |
| `core/video/veo_client.py:917` | `Path.home() / ".imageai" / "cache" / "veo_videos"` | `get_data_paths().video_cache("veo_videos")` |
| `core/video/veo_client.py:987` | `Path.home() / ".imageai" / "cache" / "veo_videos"` | `get_data_paths().video_cache("veo_videos")` |
| `core/video/image_generator.py:54` | `cache_dir or Path.home() / ".imageai" / "cache" / "video"` | `cache_dir or get_data_paths().video_cache("video")` |
| `core/video/thumbnail_manager.py:30` | `cache_dir or Path.home() / ".imageai" / "cache" / "thumbnails"` | `cache_dir or get_data_paths().video_cache("thumbnails")` |
| `gui/video/history_tab.py:195` | `Path.home() / ".imageai" / "video_projects" / "events.db"` | `get_data_paths().video_events_db()` |
| `gui/video/video_project_tab.py:1827` | same | `get_data_paths().video_events_db()` |
| `gui/video/video_project_tab.py:2013` | same | `get_data_paths().video_events_db()` |

- [x] **Step 1: Write the failing tests**

Create `tests/video/test_video_paths.py`:

```python
"""Video subsystem paths must resolve through the Video root."""
import json

import pytest

import core.paths as paths_mod
from core.paths import DataPaths


@pytest.fixture
def video_root(tmp_path, monkeypatch):
    dest = tmp_path / "V"
    dest.mkdir()
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"data_roots": {"video": str(dest)}}), encoding="utf-8")
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))
    return dest


def test_project_manager_uses_video_root(video_root):
    from core.video.project_manager import VideoProjectManager

    assert VideoProjectManager().base_dir == video_root / "video_projects"


def test_thumbnail_cache_uses_video_root(video_root):
    from core.video.thumbnail_manager import ThumbnailManager

    assert ThumbnailManager().cache_dir == video_root / "cache" / "thumbnails"


def test_image_generator_cache_uses_video_root(video_root):
    from core.video.image_generator import VideoImageGenerator

    assert VideoImageGenerator().cache_dir == video_root / "cache" / "video"


def test_events_db_uses_video_root(video_root):
    assert paths_mod.get_data_paths().video_events_db() == (
        video_root / "video_projects" / "events.db"
    )


def test_no_dot_imageai_references_remain():
    """Nothing may build a path under ~/.imageai any more."""
    import pathlib

    offenders = []
    for directory in ("core", "gui", "cli", "providers"):
        for path in pathlib.Path(directory).rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if '".imageai"' in line or "'.imageai'" in line:
                    offenders.append(f"{path}:{lineno}: {line.strip()}")
    assert not offenders, "Stale ~/.imageai paths:\n" + "\n".join(offenders)
```

Adjust the constructor calls if `VideoProjectManager`, `ThumbnailManager`, or
`VideoImageGenerator` require arguments — read each `__init__` first and pass
the minimum needed.

- [x] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/video/test_video_paths.py -v`
Expected: FAIL — paths still resolve to the real home directory, and the
straggler test lists seven `~/.imageai` sites.

- [x] **Step 3: Apply the mapping table**

Work through all eleven rows. Each replacement follows the same shape — delete
the platform branch or the `Path.home()` expression and call the resolver:

```python
from core.paths import get_data_paths

base_dir = get_data_paths().video_projects()
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/video/test_video_paths.py -v`
Expected: PASS, 5 tests.

- [x] **Step 5: Run the full suite and commit**

```bash
python3 -m pytest
git add core/video/ gui/video/ tests/video/test_video_paths.py
git commit -m "refactor(video): resolve video paths through DataPaths"
```

---

## Task 6: Rewire the GUI call sites

**Files:**
- Modify: `gui/history_widget.py:236-260`, `gui/midjourney_dialog.py:143-145`, `gui/main_window.py:5610`, `gui/main_window.py:6987`, `gui/main_window.py:8238`, `gui/prompt_builder.py:192`, `gui/prompt_generation_dialog.py:1462`, `gui/prompt_generation_dialog.py:1472`, `gui/prompt_question_dialog_old.py:937`, `gui/prompt_question_dialog_old.py:949`, `gui/prompt_question_dialog_old.py:1027`, `gui/prompt_question_dialog_old.py:1039`, `gui/install_dialog.py:325`, `gui/character_animator/install_dialog.py:416`, `gui/character_animator/puppet_wizard.py:930`, `gui/font_generator/font_wizard.py`, `gui/layout/layout_tab.py`
- Test: `tests/gui/test_gui_paths.py`

**Interfaces:**
- Consumes: every `DataPaths` accessor from Task 1.
- Produces: nothing new.

Apply this exact mapping:

| File:line | Old expression | New expression |
|---|---|---|
| `gui/history_widget.py:238-242` | three-branch block building `history_file` | `history_file = get_data_paths().history_file(self.dialog_name)` |
| `gui/history_widget.py:255-259` | identical block in the save path | same replacement |
| `gui/midjourney_dialog.py:143-145` | `app_data = QStandardPaths.writableLocation(...)` then two `os.path.join` calls | `cache_path = str(get_data_paths().midjourney_cache())` and `storage_path = str(get_data_paths().midjourney_storage())`; delete the `app_data` line |
| `gui/main_window.py:5610` | `get_user_data_dir() / "composites"` | `get_data_paths().composites()` |
| `gui/main_window.py:6987` | `self.config.config_dir / "generated" / "ImageAI Logo 01.png"` | `get_data_paths().generated() / "ImageAI Logo 01.png"` |
| `gui/main_window.py:8238` | `str(images_output_dir())` | leave as is — `images_output_dir()` was rewired in Task 4 |
| `gui/prompt_builder.py:192` | `self.config.config_dir / "prompt_builder_history.json"` | `get_data_paths().history_file("prompt_builder")` |
| `gui/prompt_generation_dialog.py:1462`, `:1472` | `Path(self.config.config_dir) / "prompt_gen_session.json"` | `get_data_paths().session_file("prompt_gen")` |
| `gui/prompt_question_dialog_old.py:937`, `:949` | `Path(self.config.config_dir) / "prompt_question_session.json"` | `get_data_paths().session_file("prompt_question")` |
| `gui/prompt_question_dialog_old.py:1027`, `:1039` | `Path(self.config.config_dir) / "prompt_question_history.json"` | `get_data_paths().history_file("prompt_question")` |
| `gui/install_dialog.py:325` | `get_user_data_dir() / "weights"` | `get_data_paths().weights()` |
| `gui/character_animator/install_dialog.py:416` | `get_user_data_dir() / "weights" / "character_animator"` | `get_data_paths().weights() / "character_animator"` |
| `gui/character_animator/puppet_wizard.py:930` | `get_user_data_dir() / "Characters"` | `get_data_paths().characters()` |

For `gui/font_generator/font_wizard.py` and `gui/layout/layout_tab.py`, first locate the references:

```bash
grep -n "config_dir\|get_user_data_dir()" gui/font_generator/font_wizard.py gui/layout/layout_tab.py
```

Then map each to the accessor matching its group: font output and layout output are user artifacts under Images; caches and history files are under Settings.

- [x] **Step 1: Write the failing test**

Create `tests/gui/test_gui_paths.py`:

```python
"""GUI modules must resolve data paths through DataPaths."""
import json
import pathlib

import pytest

import core.paths as paths_mod
from core.paths import DataPaths


@pytest.fixture
def roots(tmp_path, monkeypatch):
    images = tmp_path / "I"
    settings = tmp_path / "S"
    for d in (images, settings):
        d.mkdir()
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"data_roots": {
        "images": str(images), "settings": str(settings),
    }}), encoding="utf-8")
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))
    return images, settings


def test_history_widget_uses_the_settings_root(roots, qapp):
    _images, settings = roots
    from gui.history_widget import HistoryWidget

    widget = HistoryWidget(dialog_name="unit_test")
    assert widget._history_path() == settings / "unit_test_history.json"


def test_no_gui_module_builds_a_platform_dir():
    """No GUI file may compute the platform data directory itself."""
    needles = ("AppData", "Application Support", "XDG_CONFIG_HOME", "APPDATA")
    allowed = {"gui/gcloud_help.py"}  # gcloud paths are not ours

    offenders = []
    for path in pathlib.Path("gui").rglob("*.py"):
        if str(path).replace("\\\\", "/") in allowed:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(n in line for n in needles) and "gcloud" not in line.lower():
                offenders.append(f"{path}:{lineno}: {line.strip()}")
    assert not offenders, "GUI files building platform dirs:\n" + "\n".join(offenders)
```

`HistoryWidget` has no `_history_path` helper today — the path is built inline
twice. Extract it as part of Step 3 so both the load path and the save path
share one implementation.

- [x] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/gui/test_gui_paths.py -v`
Expected: FAIL — `HistoryWidget` has no `_history_path`, and the sweep lists the
`gui/history_widget.py` and `gui/midjourney_dialog.py` sites.

- [x] **Step 3: Extract `HistoryWidget._history_path` and apply the mapping**

In `gui/history_widget.py`, add:

```python
    def _history_path(self) -> Path:
        """Path of this dialog's history file."""
        from core.paths import get_data_paths

        return get_data_paths().history_file(self.dialog_name)
```

Replace both inline blocks (the load at line 236 and the save at line 253) with
a call to `self._history_path()`. Then work through the rest of the mapping
table.

- [x] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/gui/test_gui_paths.py -v`
Expected: PASS, 2 tests.

- [x] **Step 5: Run the full suite and commit**

```bash
python3 -m pytest
git add gui/ tests/gui/test_gui_paths.py
git commit -m "refactor(gui): resolve GUI data paths through DataPaths"
```

---

## Task 7: Route the HuggingFace cache through the Models root

**Files:**
- Modify: `providers/local_sd.py:122`, `gui/local_sd_widget.py:68`, `gui/model_browser.py:100`
- Test: `tests/test_paths.py` (extend)

**Interfaces:**
- Consumes: `DataPaths.huggingface()` from Task 1.
- Produces: nothing new.

This is the largest win in the feature: 67 GB of Stable Diffusion weights.
All three sites already pass an explicit `cache_dir=` to `snapshot_download`
and `from_pretrained`, so no environment variable is involved. Do NOT set
`HF_HOME` or `HF_HUB_CACHE` — those affect every HuggingFace tool on the machine.

Leave `core/character_animator/installer.py:254` alone. It reads
`~/.cache/huggingface/hub` to detect models other tools downloaded.

- [x] **Step 1: Write the failing test**

Append to `tests/test_paths.py`:

```python
def test_local_sd_cache_uses_the_models_root(tmp_path, monkeypatch):
    import core.paths as paths_mod

    models = tmp_path / "M"
    models.mkdir()
    cfg = _write_config(tmp_path, {"data_roots": {"models": str(models)}})
    monkeypatch.setattr(paths_mod, "_INSTANCE", paths_mod.DataPaths(config_path=cfg))

    from providers.local_sd import LocalSDProvider

    provider = LocalSDProvider({})
    assert provider.cache_dir == models / "huggingface"


def test_explicit_cache_dir_config_still_wins(tmp_path, monkeypatch):
    """The pre-existing config key keeps working for anyone who set it."""
    import core.paths as paths_mod

    models = tmp_path / "M"
    custom = tmp_path / "custom"
    for d in (models, custom):
        d.mkdir()
    cfg = _write_config(tmp_path, {"data_roots": {"models": str(models)}})
    monkeypatch.setattr(paths_mod, "_INSTANCE", paths_mod.DataPaths(config_path=cfg))

    from providers.local_sd import LocalSDProvider

    provider = LocalSDProvider({"cache_dir": str(custom)})
    assert provider.cache_dir == custom


def test_character_animator_keeps_the_shared_hub_path():
    """The shared HuggingFace hub belongs to other tools and must not move."""
    import pathlib

    text = pathlib.Path("core/character_animator/installer.py").read_text(encoding="utf-8")
    assert '".cache" / "huggingface"' in text or '.cache/huggingface' in text
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_paths.py -k "cache" -v`
Expected: FAIL — all three sites still default to `~/.cache/huggingface`.

- [x] **Step 3: Rewrite the three defaults**

`providers/local_sd.py:122`:

```python
        from core.paths import get_data_paths

        configured = config.get("cache_dir")
        self.cache_dir = Path(configured) if configured else get_data_paths().huggingface()
```

`gui/local_sd_widget.py:68`:

```python
        from core.paths import get_data_paths

        self.cache_dir = get_data_paths().huggingface()
```

`gui/model_browser.py:100`:

```python
        from core.paths import get_data_paths

        self.cache_dir = cache_dir or get_data_paths().huggingface()
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_paths.py -v`
Expected: PASS, 22 tests.

- [x] **Step 5: Run the full suite and commit**

```bash
python3 -m pytest
git add providers/local_sd.py gui/local_sd_widget.py gui/model_browser.py tests/test_paths.py
git commit -m "refactor(models): route HuggingFace cache through the Models root"
```

---

## Task 8: Migration — sources and validation

**Files:**
- Create: `core/data_migration.py`
- Test: `tests/migration/test_data_migration.py`

**Interfaces:**
- Consumes: `Group`, `DataPaths`, `get_data_paths`, `platform_default_dir` from Task 1.
- Produces:
  - `@dataclass MoveResult` with fields `ok: bool`, `files_moved: int`, `bytes_moved: int`, `used_rename: bool`, `error: Optional[str]`.
  - `class MoveCancelled(Exception)`
  - `sources_for(group: Group, paths: DataPaths) -> list[tuple[Path, str]]` — absolute source directory paired with its name under the destination root.
  - `validate_destination(group: Group, dest: Path, paths: DataPaths) -> Optional[str]` — returns an error message, or `None` when valid.
  - `tree_size(path: Path) -> tuple[int, int]` — `(file_count, total_bytes)`.

- [x] **Step 1: Write the failing tests**

Create `tests/migration/test_data_migration.py`:

```python
"""Unit tests for group relocation."""
import json

import pytest

from core.data_migration import (
    sources_for,
    tree_size,
    validate_destination,
)
from core.paths import DataPaths, Group


@pytest.fixture
def paths(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({}), encoding="utf-8")
    return DataPaths(config_path=cfg)


def _populate(root, names, size=1024):
    for name in names:
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "f.bin").write_bytes(b"x" * size)


def test_tree_size_counts_files_and_bytes(tmp_path):
    _populate(tmp_path, ["a", "b"], size=100)
    assert tree_size(tmp_path) == (2, 200)


def test_tree_size_of_missing_dir_is_zero(tmp_path):
    assert tree_size(tmp_path / "nope") == (0, 0)


def test_sources_for_images_lists_only_existing_dirs(tmp_path, paths):
    _populate(tmp_path, ["generated", "styles"])
    names = [name for _src, name in sources_for(Group.IMAGES, paths)]
    assert sorted(names) == ["generated", "styles"]


def test_sources_for_models_includes_the_huggingface_cache(tmp_path, paths, monkeypatch):
    _populate(tmp_path, ["musetalk"])
    hf = tmp_path / "hf"
    _populate(hf, ["models--x"])
    monkeypatch.setattr("core.data_migration.legacy_huggingface_dir", lambda: hf)

    entries = dict((name, src) for src, name in sources_for(Group.MODELS, paths))
    assert "musetalk" in entries
    assert entries["huggingface"] == hf


def test_sources_for_video_includes_the_dot_imageai_tree(tmp_path, paths, monkeypatch):
    _populate(tmp_path, ["video_projects"])
    legacy = tmp_path / "dot"
    _populate(legacy, ["cache"])
    monkeypatch.setattr("core.data_migration.legacy_dot_imageai_dir", lambda: legacy)

    names = [name for _src, name in sources_for(Group.VIDEO, paths)]
    assert "video_projects" in names
    assert "cache" in names


def test_validate_rejects_a_destination_equal_to_the_source(tmp_path, paths):
    _populate(tmp_path, ["generated"])
    error = validate_destination(Group.IMAGES, tmp_path, paths)
    assert error and "same" in error.lower()


def test_validate_rejects_a_destination_inside_the_source(tmp_path, paths):
    _populate(tmp_path, ["generated"])
    inside = tmp_path / "generated" / "sub"
    error = validate_destination(Group.IMAGES, inside, paths)
    assert error and "inside" in error.lower()


def test_validate_rejects_an_unwritable_parent(tmp_path, paths):
    _populate(tmp_path, ["generated"])
    error = validate_destination(Group.IMAGES, tmp_path / "no" / "such" / "parent", paths)
    assert error and ("does not exist" in error.lower() or "writable" in error.lower())


def test_validate_rejects_insufficient_free_space(tmp_path, paths, monkeypatch):
    import collections

    _populate(tmp_path, ["generated"], size=4096)
    dest = tmp_path / "dest"
    dest.mkdir()

    Usage = collections.namedtuple("Usage", "total used free")
    monkeypatch.setattr("core.data_migration.shutil.disk_usage",
                        lambda _p: Usage(total=100, used=99, free=1))

    error = validate_destination(Group.IMAGES, dest, paths)
    assert error and "space" in error.lower()


def test_validate_accepts_a_good_destination(tmp_path, paths):
    _populate(tmp_path, ["generated"])
    dest = tmp_path / "dest"
    dest.mkdir()
    assert validate_destination(Group.IMAGES, dest, paths) is None
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/migration/test_data_migration.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.data_migration'`

- [x] **Step 3: Write the implementation**

Create `core/data_migration.py`:

```python
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
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/migration/test_data_migration.py -v`
Expected: PASS, 10 tests.

- [x] **Step 5: Run the full suite and commit**

```bash
python3 -m pytest
git add core/data_migration.py tests/migration/test_data_migration.py
git commit -m "feat(migration): add source discovery and destination validation"
```

---

## Task 9: Migration — the move itself

**Files:**
- Modify: `core/data_migration.py`
- Test: `tests/migration/test_data_migration.py` (extend)

**Interfaces:**
- Consumes: everything from Task 8.
- Produces: `move_group(group, dest, paths=None, progress_cb=None, cancel=None, pre_move=None) -> MoveResult`, where `progress_cb` has signature `(files_done: int, files_total: int, bytes_done: int, bytes_total: int, current: str) -> None` and `cancel` is any object with a truthy `.is_set()` method or a plain callable returning bool.

This task implements the ordering rule from the design doc: verify, then write
the config, then delete. A crash between the config write and the delete leaves
a working application with a stale copy — recoverable. The reverse order can
destroy the only copy.

- [x] **Step 1: Write the failing tests**

Append to `tests/migration/test_data_migration.py`:

```python
import sqlite3
import threading

from core.data_migration import MoveResult, move_group


def _read_roots(paths):
    return json.loads(paths.config_file().read_text(encoding="utf-8")).get("data_roots", {})


def test_move_relocates_files_and_updates_config(tmp_path, paths):
    _populate(tmp_path, ["generated", "styles"], size=64)
    dest = tmp_path / "dest"

    result = move_group(Group.IMAGES, dest, paths=paths)

    assert result.ok, result.error
    assert (dest / "generated" / "f.bin").read_bytes() == b"x" * 64
    assert (dest / "styles" / "f.bin").exists()
    assert not (tmp_path / "generated").exists()
    assert _read_roots(paths)["images"] == str(dest)


def test_move_reports_counts(tmp_path, paths):
    _populate(tmp_path, ["generated", "styles"], size=64)
    result = move_group(Group.IMAGES, tmp_path / "dest", paths=paths)
    assert result.files_moved == 2
    assert result.bytes_moved == 128


def test_move_uses_rename_on_the_same_volume(tmp_path, paths):
    _populate(tmp_path, ["generated"], size=64)
    result = move_group(Group.IMAGES, tmp_path / "dest", paths=paths)
    assert result.ok
    assert result.used_rename is True


def test_move_reports_progress(tmp_path, paths, monkeypatch):
    monkeypatch.setattr("core.data_migration._same_volume", lambda _a, _b: False)
    _populate(tmp_path, ["generated", "styles"], size=64)

    seen = []
    move_group(Group.IMAGES, tmp_path / "dest", paths=paths,
               progress_cb=lambda *a: seen.append(a))

    assert seen
    assert seen[-1][0] == seen[-1][1]  # files_done reached files_total


def test_cancel_aborts_and_leaves_the_source_intact(tmp_path, paths, monkeypatch):
    monkeypatch.setattr("core.data_migration._same_volume", lambda _a, _b: False)
    _populate(tmp_path, ["generated", "styles", "images"], size=64)
    dest = tmp_path / "dest"

    flag = threading.Event()

    def cb(files_done, *_rest):
        if files_done >= 1:
            flag.set()

    result = move_group(Group.IMAGES, dest, paths=paths, progress_cb=cb, cancel=flag)

    assert not result.ok
    assert "cancel" in result.error.lower()
    assert (tmp_path / "generated" / "f.bin").exists()
    assert not dest.exists()
    assert "images" not in _read_roots(paths)


def test_verify_mismatch_aborts_and_keeps_the_source(tmp_path, paths, monkeypatch):
    monkeypatch.setattr("core.data_migration._same_volume", lambda _a, _b: False)
    _populate(tmp_path, ["generated"], size=64)
    monkeypatch.setattr("core.data_migration.tree_size",
                        lambda p: (99, 99) if "dest" in str(p) else (1, 64))

    result = move_group(Group.IMAGES, tmp_path / "dest", paths=paths)

    assert not result.ok
    assert "verif" in result.error.lower()
    assert (tmp_path / "generated" / "f.bin").exists()


def test_move_refuses_an_invalid_destination(tmp_path, paths):
    _populate(tmp_path, ["generated"])
    result = move_group(Group.IMAGES, tmp_path, paths=paths)
    assert not result.ok
    assert "same" in result.error.lower()


def test_move_copies_sqlite_sidecars(tmp_path, paths, monkeypatch):
    monkeypatch.setattr("core.data_migration._same_volume", lambda _a, _b: False)
    monkeypatch.setattr("core.data_migration.legacy_dot_imageai_dir",
                        lambda: tmp_path / "absent")

    projects = tmp_path / "video_projects"
    projects.mkdir()
    db = projects / "events.db"
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE t (a INTEGER)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()

    dest = tmp_path / "dest"
    result = move_group(Group.VIDEO, dest, paths=paths)

    assert result.ok, result.error
    moved = sqlite3.connect(dest / "video_projects" / "events.db")
    assert moved.execute("SELECT a FROM t").fetchone() == (1,)
    moved.close()


def test_pre_move_hook_runs_before_any_copy(tmp_path, paths):
    _populate(tmp_path, ["generated"], size=64)
    calls = []
    move_group(Group.IMAGES, tmp_path / "dest", paths=paths,
               pre_move=lambda: calls.append("closed"))
    assert calls == ["closed"]
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/migration/test_data_migration.py -v`
Expected: FAIL — `ImportError: cannot import name 'move_group'`

- [x] **Step 3: Write the implementation**

Append to `core/data_migration.py`:

```python
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
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/migration/test_data_migration.py -v`
Expected: PASS, 19 tests.

- [x] **Step 5: Run the full suite and commit**

```bash
python3 -m pytest
git add core/data_migration.py tests/migration/test_data_migration.py
git commit -m "feat(migration): relocate groups with verify-before-delete ordering"
```

---

## Task 10: The Storage Locations widget

**Files:**
- Create: `gui/storage_settings_widget.py`
- Test: `tests/gui/test_storage_settings.py`

**Interfaces:**
- Consumes: `Group`, `get_data_paths`, `reset_data_paths` from Task 1; `sources_for`, `tree_size`, `validate_destination`, `move_group`, `MoveResult` from Tasks 8-9.
- Produces: `class StorageSettingsWidget(QGroupBox)` with `rows: dict[Group, StorageRow]`, method `refresh_sizes()`, and signal `move_completed = Signal(str)` carrying the group value.

- [x] **Step 1: Write the failing test**

Create `tests/gui/test_storage_settings.py`:

```python
"""Construction and wiring tests for the Storage Locations widget."""
import json

import pytest

import core.paths as paths_mod
from core.paths import DataPaths, Group


@pytest.fixture
def widget(tmp_path, monkeypatch, qapp):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))

    from gui.storage_settings_widget import StorageSettingsWidget

    return StorageSettingsWidget()


def test_widget_has_one_row_per_group(widget):
    assert set(widget.rows) == set(Group)


def test_each_row_has_move_and_open_buttons(widget):
    for group, row in widget.rows.items():
        assert row.move_button is not None, group
        assert row.open_button is not None, group


def test_rows_start_in_a_calculating_state(widget):
    for row in widget.rows.values():
        assert row.size_label.text() == "Calculating…"


def test_multi_tree_groups_are_labelled(widget, monkeypatch):
    """Models and Video can span two source trees before the first move."""
    assert widget.rows[Group.MODELS].path_label.toolTip()
    assert widget.rows[Group.VIDEO].path_label.toolTip()


def test_unreachable_root_shows_a_warning(tmp_path, monkeypatch, qapp):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"data_roots": {"images": str(tmp_path / "gone" / "x")}}),
                   encoding="utf-8")
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))

    from gui.storage_settings_widget import StorageSettingsWidget

    widget = StorageSettingsWidget()
    assert "Unavailable" in widget.rows[Group.IMAGES].status_label.text()
```

- [x] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/gui/test_storage_settings.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gui.storage_settings_widget'`

- [x] **Step 3: Write the implementation**

Create `gui/storage_settings_widget.py`:

```python
"""Settings-tab UI for relocating ImageAI's data groups."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QObject, QStandardPaths, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
)

from core.data_migration import sources_for, tree_size
from core.paths import Group, get_data_paths

logger = logging.getLogger(__name__)

GROUP_LABELS = {
    Group.IMAGES: "Images",
    Group.VIDEO: "Video",
    Group.MODELS: "Models",
    Group.SETTINGS: "Settings",
}

GROUP_HINTS = {
    Group.IMAGES: "Generated images, composites, styles, Midjourney cache",
    Group.VIDEO: "Video projects, render caches, the events database",
    Group.MODELS: "MuseTalk, Character Animator weights, Stable Diffusion models",
    Group.SETTINGS: "Logs, history, layout templates (config.json always stays put)",
}

PICKER_ROOTS = {
    Group.IMAGES: QStandardPaths.PicturesLocation,
    Group.VIDEO: QStandardPaths.MoviesLocation,
    Group.MODELS: QStandardPaths.AppDataLocation,
    Group.SETTINGS: QStandardPaths.AppDataLocation,
}


def human_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{int(value)} B" if unit == "B" else f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} TB"


@dataclass
class StorageRow:
    name_label: QLabel
    path_label: QLabel
    size_label: QLabel
    status_label: QLabel
    move_button: QPushButton
    open_button: QPushButton


class _SizeWorker(QObject):
    """Walks the trees for one group off the UI thread."""

    finished = Signal(str, int)  # group value, total bytes

    def __init__(self, group: Group) -> None:
        super().__init__()
        self._group = group

    def run(self) -> None:
        try:
            total = sum(tree_size(source)[1] for source, _name in sources_for(self._group))
        except Exception:  # noqa: BLE001 - a size probe must never crash the UI
            logger.exception("Could not measure the %s storage group", self._group.value)
            total = -1
        self.finished.emit(self._group.value, total)


class StorageSettingsWidget(QGroupBox):
    """Shows where each data group lives and lets the user move it."""

    move_completed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__("Storage Locations", parent)
        self.rows: Dict[Group, StorageRow] = {}
        self._threads = []
        self._build_ui()
        self.refresh_sizes()

    def _build_ui(self) -> None:
        grid = QGridLayout(self)
        grid.setColumnStretch(1, 1)

        header = QLabel(
            "Move large data off your system drive. "
            "config.json always stays in the default location."
        )
        header.setWordWrap(True)
        grid.addWidget(header, 0, 0, 1, 5)

        paths = get_data_paths()
        for index, group in enumerate(Group, start=1):
            name_label = QLabel(GROUP_LABELS[group])
            name_label.setToolTip(GROUP_HINTS[group])

            path_label = QLabel(self._path_text(group))
            path_label.setToolTip(self._path_tooltip(group))
            path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

            size_label = QLabel("Calculating…")
            size_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            status_label = QLabel("")

            move_button = QPushButton("&Move…")
            move_button.setToolTip(f"Relocate {GROUP_LABELS[group]} data")
            move_button.clicked.connect(lambda _c=False, g=group: self._on_move(g))

            open_button = QPushButton("&Open")
            open_button.setToolTip("Show this folder in the file manager")
            open_button.clicked.connect(lambda _c=False, g=group: self._on_open(g))

            grid.addWidget(name_label, index, 0)
            grid.addWidget(path_label, index, 1)
            grid.addWidget(size_label, index, 2)
            grid.addWidget(move_button, index, 3)
            grid.addWidget(open_button, index, 4)

            self.rows[group] = StorageRow(
                name_label, path_label, size_label, status_label,
                move_button, open_button,
            )

            grid.addWidget(status_label, index, 1, 1, 4)
            status_label.setVisible(False)

        # Surface any root that could not be reached at startup.
        for message in paths.drain_warnings():
            logger.warning(message)
            for group in Group:
                if f"'{group.value}'" in message:
                    row = self.rows[group]
                    row.status_label.setText("⚠ Unavailable — using default location")
                    row.status_label.setVisible(True)

    def _path_text(self, group: Group) -> str:
        return str(get_data_paths().root(group))

    def _path_tooltip(self, group: Group) -> str:
        sources = sources_for(group)
        if not sources:
            return "No data yet."
        return "\n".join(str(source) for source, _name in sources)

    def refresh_sizes(self) -> None:
        """Measure every group off the UI thread."""
        for group in Group:
            thread = QThread(self)
            worker = _SizeWorker(group)
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.finished.connect(self._on_size_ready)
            worker.finished.connect(thread.quit)
            thread.finished.connect(worker.deleteLater)
            self._threads.append((thread, worker))
            thread.start()

    def _on_size_ready(self, group_value: str, total: int) -> None:
        row = self.rows[Group(group_value)]
        row.size_label.setText("unknown" if total < 0 else human_size(total))

    def _on_open(self, group: Group) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        target = get_data_paths().root(group)
        target.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _on_move(self, group: Group) -> None:
        """Filled in by Task 11."""
        raise NotImplementedError
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/gui/test_storage_settings.py -v`
Expected: PASS, 5 tests.

- [x] **Step 5: Run the full suite and commit**

```bash
python3 -m pytest
git add gui/storage_settings_widget.py tests/gui/test_storage_settings.py
git commit -m "feat(gui): add Storage Locations widget with async size probes"
```

---

## Task 11: The move flow and Settings-tab wiring

**Files:**
- Modify: `gui/storage_settings_widget.py`
- Modify: `gui/main_window.py:1606` (`_init_settings_tab`)
- Test: `tests/gui/test_storage_settings.py` (extend)

**Interfaces:**
- Consumes: `move_group`, `validate_destination`, `MoveResult` from Tasks 8-9; `StorageSettingsWidget` from Task 10.
- Produces: `StorageSettingsWidget._on_move` implemented; `MainWindow.storage_settings` attribute.

- [x] **Step 1: Write the failing tests**

Append to `tests/gui/test_storage_settings.py`:

```python
def test_move_calls_the_migrator_with_the_chosen_directory(widget, tmp_path, monkeypatch):
    from core.data_migration import MoveResult

    chosen = tmp_path / "chosen"
    chosen.mkdir()
    calls = {}

    monkeypatch.setattr(
        "gui.storage_settings_widget.QFileDialog.getExistingDirectory",
        lambda *a, **k: str(chosen),
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._confirm", lambda *a, **k: True
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._run_with_progress",
        lambda self, group, dest: calls.setdefault("args", (group, dest))
        or MoveResult(ok=True, files_moved=1, bytes_moved=10),
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._offer_restart", lambda *a, **k: None
    )

    widget._on_move(Group.IMAGES)
    assert calls["args"] == (Group.IMAGES, chosen)


def test_cancelled_picker_does_nothing(widget, monkeypatch):
    monkeypatch.setattr(
        "gui.storage_settings_widget.QFileDialog.getExistingDirectory",
        lambda *a, **k: "",
    )
    called = []
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._run_with_progress",
        lambda *a, **k: called.append(1),
    )
    widget._on_move(Group.IMAGES)
    assert not called


def test_failed_move_shows_the_error(widget, tmp_path, monkeypatch):
    from core.data_migration import MoveResult

    shown = []
    monkeypatch.setattr(
        "gui.storage_settings_widget.QFileDialog.getExistingDirectory",
        lambda *a, **k: str(tmp_path / "chosen"),
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._confirm", lambda *a, **k: True
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._run_with_progress",
        lambda *a, **k: MoveResult(ok=False, error="Not enough free space."),
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.QMessageBox.critical",
        lambda *a, **k: shown.append(a[2]),
    )

    widget._on_move(Group.IMAGES)
    assert shown and "free space" in shown[0]


def test_main_window_exposes_the_storage_widget(qapp, monkeypatch):
    """The Settings tab must actually contain the widget."""
    import inspect

    from gui.main_window import MainWindow

    source = inspect.getsource(MainWindow._init_settings_tab)
    assert "StorageSettingsWidget" in source
    assert "storage_settings" in source
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/gui/test_storage_settings.py -v`
Expected: FAIL — `_on_move` raises `NotImplementedError` and `_init_settings_tab` has no reference.

- [x] **Step 3: Implement the move flow**

Add these imports to the top of `gui/storage_settings_widget.py`:

```python
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
)

from core.data_migration import move_group, validate_destination
from core.paths import Group, get_data_paths, reset_data_paths
```

Replace the `_on_move` stub with:

```python
    def _suggested_dir(self, group: Group) -> str:
        base = QStandardPaths.writableLocation(PICKER_ROOTS[group])
        return str(Path(base) / "ImageAI" / GROUP_LABELS[group])

    def _confirm(self, group: Group, dest: Path, total: int) -> bool:
        import shutil

        probe = dest if dest.exists() else dest.parent
        try:
            free = shutil.disk_usage(probe).free
        except OSError:
            free = 0

        box = QMessageBox(self)
        box.setWindowTitle(f"Move {GROUP_LABELS[group]} data")
        box.setIcon(QMessageBox.Question)
        box.setText(f"Move {GROUP_LABELS[group]} data to a new location?")
        box.setInformativeText(
            f"From:  {get_data_paths().root(group)}\n"
            f"To:    {dest}\n\n"
            f"Size to move:      {human_size(total)}\n"
            f"Free at destination: {human_size(free)}\n\n"
            f"ImageAI copies the data, verifies it, then removes the original."
        )
        box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        box.setDefaultButton(QMessageBox.Cancel)
        return box.exec() == QMessageBox.Ok

    def _run_with_progress(self, group: Group, dest: Path):
        dialog = QProgressDialog(
            f"Moving {GROUP_LABELS[group]} data…", "Cancel", 0, 100, self
        )
        dialog.setWindowModality(Qt.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setValue(0)

        def progress(files_done, files_total, bytes_done, bytes_total, current):
            percent = int(bytes_done * 100 / bytes_total) if bytes_total else 0
            dialog.setValue(min(percent, 100))
            dialog.setLabelText(
                f"Moving {GROUP_LABELS[group]} data…\n"
                f"{files_done} of {files_total} files "
                f"({human_size(bytes_done)} of {human_size(bytes_total)})\n"
                f"{Path(current).name}"
            )
            QApplication.processEvents()

        try:
            return move_group(
                group, dest,
                progress_cb=progress,
                cancel=dialog.wasCanceled,
                pre_move=self._close_open_resources,
            )
        finally:
            dialog.close()

    def _close_open_resources(self) -> None:
        """Ask the main window to release file handles before a move."""
        window = self.window()
        closer = getattr(window, "close_data_handles", None)
        if callable(closer):
            closer()

    def _offer_restart(self, group: Group, result) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("Move complete")
        box.setIcon(QMessageBox.Information)
        box.setText(
            f"Moved {human_size(result.bytes_moved)} of "
            f"{GROUP_LABELS[group]} data."
        )
        box.setInformativeText(
            "Restart ImageAI to use the new location."
        )
        restart = box.addButton("Restart Now", QMessageBox.AcceptRole)
        box.addButton("Later", QMessageBox.RejectRole)
        box.exec()

        if box.clickedButton() is restart:
            self._restart_application()

    @staticmethod
    def _restart_application() -> None:
        import os
        import sys

        logger.info("Restarting ImageAI after a storage move")
        QApplication.quit()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _on_move(self, group: Group) -> None:
        start = self._suggested_dir(group)
        chosen = QFileDialog.getExistingDirectory(
            self, f"Choose a folder for {GROUP_LABELS[group]} data", start
        )
        if not chosen:
            return

        dest = Path(chosen)
        error = validate_destination(group, dest)
        if error:
            logger.error("Rejected destination %s for %s: %s", dest, group.value, error)
            QMessageBox.critical(self, "Cannot use that folder", error)
            return

        total = sum(tree_size(source)[1] for source, _name in sources_for(group))
        if not self._confirm(group, dest, total):
            return

        result = self._run_with_progress(group, dest)

        if not result.ok:
            logger.error("Move of %s failed: %s", group.value, result.error)
            QMessageBox.critical(self, "Move failed", result.error)
            self.refresh_sizes()
            return

        reset_data_paths()
        self.rows[group].path_label.setText(str(dest))
        self.rows[group].path_label.setToolTip(str(dest))
        self.refresh_sizes()
        self.move_completed.emit(group.value)
        self._offer_restart(group, result)
```

- [x] **Step 4: Wire the widget into the Settings tab**

In `gui/main_window.py`, inside `_init_settings_tab`, immediately before the
`# === MIDJOURNEY SETTINGS ===` block at line 1781, insert:

```python
        # === STORAGE LOCATIONS ===
        from gui.storage_settings_widget import StorageSettingsWidget

        self.storage_settings = StorageSettingsWidget(self.tab_settings)
        v.addWidget(self.storage_settings)
```

- [x] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/gui/test_storage_settings.py -v`
Expected: PASS, 9 tests.

- [x] **Step 6: Verify by hand**

Leland runs this from PowerShell with `.venv`, because the move dialogs need a
real display:

```powershell
python main.py
```

Confirm: the Settings tab shows a Storage Locations box with four rows; sizes
resolve from `Calculating…` to real values; `Open` opens the folder; `Move…`
starts at `Pictures\ImageAI\Images` for the Images row; picking the current
location is rejected with a clear message.

- [x] **Step 7: Run the full suite and commit**

```bash
python3 -m pytest
git add gui/storage_settings_widget.py gui/main_window.py tests/gui/test_storage_settings.py
git commit -m "feat(gui): wire Storage Locations move flow into the Settings tab"
```

---

## Task 12: The straggler guard

**Files:**
- Modify: `tests/test_no_hardcoded_paths.py`
- Modify: any file the guard catches

**Interfaces:**
- Consumes: the completed rewire from Tasks 2-7.
- Produces: a permanent regression guard.

The design doc's top risk is a missed call site that keeps writing to the old
location. This task turns that risk into a test.

- [x] **Step 1: Write the failing test**

Append to `tests/test_no_hardcoded_paths.py`:

```python
import re

# Paths that belong to other software and must keep their own resolution.
ALLOWED_PATTERNS = (
    r"gcloud",
    r"Cloud SDK",
    r"application_default_credentials",
    r"font",           # system font directories
    r"ffmpeg",
    r"\.cache.\s*.\s*.huggingface",  # shared hub read by character_animator
)

FORBIDDEN = (
    "AppData",
    "Application Support",
    "XDG_CONFIG_HOME",
    "APPDATA",
    ".imageai",
)


def _is_allowed(line: str) -> bool:
    return any(re.search(p, line, re.IGNORECASE) for p in ALLOWED_PATTERNS)


def test_no_module_builds_its_own_platform_data_dir():
    """core/paths.py is the only place allowed to compute the data directory."""
    offenders = []
    for path in _python_files():
        rel = str(path).replace("\\\\", "/")
        if rel == "core/paths.py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            if any(token in line for token in FORBIDDEN) and not _is_allowed(line):
                offenders.append(f"{rel}:{lineno}: {line.strip()}")

    assert not offenders, (
        "These lines build a data path without DataPaths:\n" + "\n".join(offenders)
    )


def test_get_user_data_dir_has_no_remaining_callers():
    """The shim exists for external scripts only; nothing in-tree may call it."""
    offenders = []
    for path in _python_files():
        rel = str(path).replace("\\\\", "/")
        if rel == "core/constants.py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "get_user_data_dir(" in line:
                offenders.append(f"{rel}:{lineno}: {line.strip()}")

    assert not offenders, (
        "Replace these with core.paths.get_data_paths():\n" + "\n".join(offenders)
    )
```

- [x] **Step 2: Run the tests to see what remains**

Run: `python3 -m pytest tests/test_no_hardcoded_paths.py -v`
Expected: FAIL or PASS depending on what Tasks 4-7 missed. Treat every reported
line as work to finish.

- [x] **Step 3: Fix each offender**

For each reported line, either route it through `DataPaths`, or — if it truly
belongs to other software — add a precise pattern to `ALLOWED_PATTERNS` with a
comment saying why. Do not broaden a pattern to silence an unrelated line.

- [x] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_no_hardcoded_paths.py -v`
Expected: PASS, 3 tests.

- [x] **Step 5: Run the full suite and commit**

```bash
python3 -m pytest
git add tests/test_no_hardcoded_paths.py core/ gui/ providers/ cli/
git commit -m "test(paths): guard against straggler data-path call sites"
```

---

## Task 13: Documentation, CodeMap, and release

**Files:**
- Modify: `Plans/2026-08-10-storage-locations-design.md`
- Modify: `AGENTS.md`
- Modify: `Docs/CodeMap.md`
- Modify: `CHANGELOG.md`, `core/constants.py` (version), plus every path in `.claude/VERSION_LOCATIONS.md`

**Interfaces:**
- Consumes: the completed feature.
- Produces: a released v0.45.0.

- [x] **Step 1: Correct the design doc's SQLite requirement**

In `Plans/2026-08-10-storage-locations-design.md`, replace this testing bullet:

```markdown
- `move_group` refuses to move the Video group while a database connection is
  open.
```

with:

```markdown
- `move_group` runs `PRAGMA wal_checkpoint(TRUNCATE)` on every database before
  it copies, and it calls the `pre_move` hook so the GUI can close its own
  connections first.
```

Then in section 2.7, replace "The migrator must confirm that no connection is
open before it copies the file" with:

```markdown
The migrator checkpoints every database with `PRAGMA wal_checkpoint(TRUNCATE)`
before it copies, which folds the write-ahead log into the main file. The GUI
closes its own connections through the `pre_move` hook. Detecting a foreign
process's connection is not reliably possible, so the design does not attempt it.
```

- [x] **Step 2: Update AGENTS.md**

The "Navigation & debugging" section tells agents where the log lives. Append to
that bullet:

```markdown
  The log directory follows the Settings storage root, which the user can move
  from the Settings tab. Resolve it with `core.paths.get_data_paths().logs()`
  rather than assuming a platform directory.
```

Add to "Hard project rules":

```markdown
- Never build a data path by hand. `core/paths.py` owns every location; call
  `get_data_paths()` and its accessors. A guard test
  (`tests/test_no_hardcoded_paths.py`) fails the build on new inline paths.
```

- [x] **Step 3: Regenerate the CodeMap**

Run the `update-code-map` skill, or:

```bash
python3 tools/generate_code_map.py
```

Confirm `Docs/CodeMap.md` now lists `core/paths.py`, `core/data_migration.py`,
and `gui/storage_settings_widget.py` with accurate line numbers.

- [x] **Step 4: Run the full suite one last time**

Run: `python3 -m pytest`
Expected: PASS. Record the total count for the changelog.

- [x] **Step 5: Cut the release**

This is a feature, so it is a minor bump: 0.44.1 → 0.45.0. Dry-run first:

```bash
python3 ~/.claude/skills/version-manager/version_tool.py \
  --repo /mnt/d/Documents/Code/GitHub/ImageAI release minor
```

Review the generated notes, curate them into prose in a file, then apply:

```bash
python3 ~/.claude/skills/version-manager/version_tool.py \
  --repo /mnt/d/Documents/Code/GitHub/ImageAI release minor --notes NOTES.md --apply
```

Never hand-edit the version number or a changelog heading — the tool owns both.
The changelog entry should lead with the user-visible change and name the two
bug fixes:

> Four Move buttons in Settings relocate Images, Video, Models, and Settings
> data to any folder. Fixes a hardcoded developer path in the Google provider's
> debug dumps, and MuseTalk's platform paths, which ignored `%APPDATA%` on
> Windows and disagreed with every other subsystem on Linux.

- [x] **Step 6: Review before pushing**

Per the house rule, the local review runs before `git push`, not after. Run the
`code-reviewer` agent over the branch, then reconcile its findings.

- [ ] **Step 7: Commit and open the PR** — committed; the push and the PR wait
      on the maintainer. See `Docs/Storage-Locations-Known-Issues.md` for what
      five adversarial rounds left open.

```bash
git add -A
git commit -m "docs: document configurable storage locations"
git push -u origin feat/storage-locations
gh pr create --title "feat: configurable storage locations" --body "..."
```

---

## Self-Review

**Spec coverage.** Every design-doc section maps to a task: groups and mapping → Tasks 1, 8; resolver and config schema → Task 1; `config.json` pinned → Task 1 (`test_config_file_never_moves`); init order → Tasks 1, 3; the four call-site classes → Tasks 4, 5, 6, 7; paths that must not move → Tasks 4, 7, 12; HuggingFace → Task 7; `~/.imageai` → Task 5; both audit bugs → Tasks 2, 4; move steps and ordering → Task 9; same-volume fast path → Task 9; restart → Task 11; UI and defaults → Tasks 10, 11; errors and logging → Tasks 9, 11; testing → every task; unreachable root → Tasks 1, 10.

**Known deviation.** The "refuse while a connection is open" requirement is replaced by checkpoint-plus-`pre_move`, and Task 13 amends the design doc rather than leaving the two documents in conflict.

**Type consistency.** `Group` members and their string values are fixed in Task 1 and used unchanged everywhere. `MoveResult` fields (`ok`, `files_moved`, `bytes_moved`, `used_rename`, `error`) are defined in Task 8 and read in Tasks 9 and 11. `move_group`'s signature is fixed in Task 9 and called with exactly those keywords in Task 11. `progress_cb` takes the same five positional arguments in Tasks 9, 10, and 11. `DataPaths` accessor names are asserted in Task 1's tests and used verbatim in the Task 4-7 mapping tables.

**Line numbers.** Every `file:line` reference was verified against the working tree on 2026-08-11. They shift as tasks land — after Task 4, re-grep before trusting a line number in Tasks 5 and 6.
