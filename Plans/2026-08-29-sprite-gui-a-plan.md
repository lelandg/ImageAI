# Sprite GUI (A): Tab, Intake, Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Last Updated:** 2026-08-30 08:56

**Spec:** `Plans/2026-08-29-sprite-tab-design.md` — §1.1 (worker contract), §1.5 (shortcuts: Ctrl+Enter / Escape), §1.6 (storage, purge preference, named configs), §2 (data model), §4.5 (GUI module list), decision 8 (cost labels), decision 9 (Generation Settings dialog + named configurations).

**Goal:** Ship the left half of the Sprite tab: a lazily loaded `SpriteTab` in the main window, the character intake panel (drop / browse → normalize → chroma plate → turnaround), the action-cards panel (LLM brief → editable cards → per-card Render / Re-render / Refine), the Generation Settings dialog with named configurations and a live cost line, and the queue panel that drives `ActionQueue` with per-action and per-sheet cost labels. Every long call runs in a `SpriteWorker` thread. "Send to Sprite" reaches the tab from the Image tab, the History tab, and the Video reference library. The right half (frame strip, preview, pixel view, processing, export) is sub-project 5b, which fills three placeholder slots this plan exposes.

**Architecture:** `gui/sprite/` holds one widget per file (`sprite_tab.py`, `character_panel.py`, `action_cards_panel.py`, `queue_panel.py`, `generation_settings_dialog.py`, `workers.py`, `prefs.py`). Every panel is a `WorkerHost` (one `SpriteWorker` at a time) and talks to the tab through Qt signals only — no panel imports the tab. All provider, LLM, PIL and ffmpeg calls happen inside the worker's `job(progress, token)` callable; the UI thread paints at most one thumbnail. The tab owns the `DialogStatusConsole` and routes every panel's `logMessage(str, str)` into it. Named configurations are pure Python (`core/sprite/configs.py`) so the CLI (sub-project 7) reads the same file.

**Tech Stack:** Python 3.12 (`.venv_linux`), PySide6 (offscreen in tests), pytest, Pillow (thumbnails, test fixtures). Core contracts from sub-projects 1–2 (`core/sprite/…`) are consumed as-is.

**Sub-project:** 5a of 8 — depends on 1 (core spine: models, project, paths, pipeline contract) and 2 (video route: action cards, plate, turnaround, queue, cost, timing). Sub-project 5b extends `SpriteTab` through the three `set_*_widget` hooks and never edits the files this plan creates except `sprite_tab.py` (adding shortcuts/undo wiring).

## Global Constraints

- Repo root: `/mnt/d/Documents/Code/GitHub/ImageAI`. Branch `feat/sprite-tab`. Never `cd`; absolute paths only; `git -C /mnt/d/Documents/Code/GitHub/ImageAI …`.
- `PY=/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python`. GUI tests: `QT_QPA_PLATFORM=offscreen $PY -m pytest <path> -v`. The session `qapp` fixture and the QSettings / data-path sandboxes come from `tests/conftest.py`.
- Design names, signatures and paths are the contract. Consume these exactly as the design writes them: `core.sprite.pipeline.CancelToken / Cancelled / ProgressFn / no_progress / run_pipeline`, `core.sprite.project.SpriteProject / GenerationSettings / ActionCard / ClipRecord`, `core.sprite.generation.action_cards.generate_action_cards / ActionCardDraft / GENRE_CHECKLISTS`, `core.sprite.generation.plate.make_chroma_plate`, `core.sprite.generation.turnaround.generate_turnaround`, `core.sprite.generation.video_route.refine_action`, `core.sprite.generation.queue.ActionQueue`, `core.sprite.generation.cost.estimate_action / estimate_project`, `core.sprite.generation.errors.SpriteGenerationError`, `core.sprite.source.normalize_source / analyze_source`, `core.sprite.timing.suggest_clip_duration`, `core.paths.get_data_paths().sprite_configs() / .sprite_projects()`.
- `SpriteProjectManager` (sub-project 1, reconciled 2026-08-29) lives in `core/sprite/project.py`: `SpriteProjectManager(base_dir: Optional[Path] = None)` (default `get_data_paths().sprite_projects()`), `create_project(name) -> SpriteProject` (creates `<base>/<slug>_<YYYYmmdd_HHMMSS>/` with `source/ clips/ stages/ exports/`, sets `project_dir`, saves `project.iasprite.json`), `load_project(path) -> SpriteProject` (dir or `.json`), `save_project(project) -> Path`, plus `list_projects()`, `delete_project(project)`, `find_project(name_or_slug)`. Import: `from core.sprite.project import SpriteProject, SpriteProjectManager`. `SpriteProject.default_profiles()` returns both profiles enabled (hd 256×256, pixel 64×64); no 5a test inspects profiles.
- UI thread never blocks: every provider / LLM / pipeline call runs inside `SpriteWorker`. Worker signals connect **only to bound methods of QObjects** (queued to the GUI thread). A lambda connected to a worker signal runs on the worker thread — allowed in tests only.
- Every user-facing error is logged **and** shown: use `gui.dialog_utils.show_error` / `show_warning` (they call `logger.error` / `logger.warning` before the QMessageBox). Console lines go through `logMessage(str, str)` → `DialogStatusConsole.log(message, level)`.
- API keys: `config.get_api_key(provider)` and `config.get_auth_mode(provider)` only. Never read the config dict.
- No hand-built data paths: project-relative subfolders (`project_dir / "source"`) are fine; user-dir roots come from `get_data_paths()`. `tests/test_no_hardcoded_paths.py` must stay green.
- QSettings: one object `QSettings("ImageAI", "Sprite")` (`gui/sprite/prefs.py:sprite_settings()`), every key under `sprite/`.
- Dialogs: `class X(DialogCleanupMixin, QDialog)` (mixin first — `gui/common/dialog_conventions.py:110-146`), `bind_primary_action` for Ctrl+Enter, `set_default_button` for exactly one default, `standard_splitter` + `persist_splitter` / `restore_splitter` for splitters.
- Conventional Commits, one commit per task, no version bump (sub-project 7 owns the bump). Prose in Simplified Technical English style.
- Gate per task: `$PY -m py_compile <touched files>` + that task's tests. The full suite runs once, in Task 10.

## File Structure

| Path | Role | Task |
|---|---|---|
| `gui/sprite/__init__.py` | package; exports `SpriteTab` (added in Task 8) | 1, 8 |
| `gui/sprite/workers.py` | `SpriteWorker(QThread)`, `WorkerHost` mixin | 1 |
| `core/sprite/configs.py` | `NamedConfigStore` (JSON, no Qt) | 2 |
| `gui/sprite/prefs.py` | `sprite_settings()`, purge preference, `confirm_purge`, generic `get_pref/set_pref` | 3 |
| `gui/sprite/character_panel.py` | `CharacterPanel` | 4 |
| `gui/sprite/generation_settings_dialog.py` | `GenerationSettingsDialog` | 5 |
| `gui/sprite/action_cards_panel.py` | `ActionCardsPanel` | 6 |
| `gui/sprite/queue_panel.py` | `QueuePanel` | 7 |
| `gui/sprite/sprite_tab.py` | `SpriteTab` | 8 |
| `gui/main_window.py` | placeholder tab, `_load_sprite_tab`, `_on_send_to_sprite`, context menus, closeEvent | 9 |
| `gui/video/reference_library_widget.py` | "Send to Sprite" on `ReferenceCard`; `sendToSpriteRequested` on the library | 9 |
| `gui/video/video_project_tab.py` | forwards `sendToSpriteRequested` | 9 |
| `tests/sprite/gui/conftest.py` | `FakeConfig`, `fake_project`, `png`, `wait_for_worker` fixtures | 1 |
| `tests/sprite/gui/test_sprite_worker.py` | worker + host contract | 1 |
| `tests/sprite/test_named_configs.py` | store (no Qt) | 2 |
| `tests/sprite/gui/test_sprite_prefs.py` | purge preference | 3 |
| `tests/sprite/gui/test_character_panel.py` | | 4 |
| `tests/sprite/gui/test_generation_settings_dialog.py` | | 5 |
| `tests/sprite/gui/test_action_cards_panel.py` | | 6 |
| `tests/sprite/gui/test_queue_panel.py` | | 7 |
| `tests/sprite/gui/test_sprite_tab_smoke.py` | | 8 |
| `tests/sprite/gui/test_main_window_sprite_wiring.py` | | 9 |

Test basenames are unique across `tests/` (no `__init__.py` packages there; verified with `find` on 2026-08-29).

Consumed, not created here (sub-project 1): `core/sprite/project.py` — `SpriteProject`, `SpriteProjectManager`, `ActionCard`, `GenerationSettings`, `ClipRecord`; `core/sprite/pipeline.py`; `core/sprite/generation/*`; `core/sprite/source.py`; `core/sprite/timing.py`; `DataPaths.sprite_configs()` / `.sprite_projects()`.

---

### Task 1: `SpriteWorker` and `WorkerHost` (`gui/sprite/workers.py`)

**Files:**
- Create: `gui/sprite/__init__.py`, `gui/sprite/workers.py`
- Create: `tests/sprite/gui/conftest.py`, `tests/sprite/gui/test_sprite_worker.py`
- Reference: `gui/layout/prompt_worker.py:1-36` (QThread worker pattern), `gui/workers.py:12-74`, design §1.1

**Interfaces:**
- Consumes: `core.sprite.pipeline.CancelToken` (`cancel()`, `.cancelled`, `raise_if_cancelled()`), `core.sprite.pipeline.Cancelled`, `core.sprite.pipeline.ProgressFn`, `core.sprite.generation.errors.SpriteGenerationError` (`.user_message`).
- Produces: `gui.sprite.workers.SpriteWorker(QThread)` — `__init__(self, job: Callable[[ProgressFn, CancelToken], Any], *, label: str = "job", parent=None)`; Signals `progress(str, int, int, str)`, `finished(object)`, `failed(str)`, `cancelled()`; `token -> CancelToken` property; `label -> str` property; `cancel() -> None`.
- Produces: `gui.sprite.workers.WorkerHost` mixin — `start_job(job, *, label, on_finished, on_failed, on_cancelled=None, on_progress=None) -> Optional[SpriteWorker]` (returns `None` when busy), `is_busy() -> bool`, `cancel_running() -> None`, `shutdown(timeout_ms: int = 5000) -> None`.
- Cancellation mapping (decision): `Cancelled` raised by the job → `cancelled()` signal (no `failed`). The UI shows no error dialog on cancel. A job that returns normally after `token.cancel()` also reports `cancelled()`.

- [x] **Step 1: Test fixtures** — create `tests/sprite/gui/conftest.py`:

```python
# tests/sprite/gui/conftest.py
"""Shared fixtures for the Sprite GUI tests (offscreen, sandboxed QSettings)."""
import types

import pytest
from PySide6.QtWidgets import QApplication

from core.sprite.project import ActionCard, GenerationSettings


class FakeConfig:
    """Minimal ConfigManager stand-in: get/set/save/get_api_key/get_auth_mode."""

    def __init__(self, api_key="test-key"):
        self.store = {}
        self.api_key = api_key

    def get(self, key, default=None):
        return self.store.get(key, default)

    def set(self, key, value):
        self.store[key] = value

    def save(self):
        return True

    def get_api_key(self, provider):
        return self.api_key

    def get_auth_mode(self, provider="google"):
        return "api-key"


@pytest.fixture
def fake_config():
    return FakeConfig()


@pytest.fixture
def fake_project(tmp_path):
    """A SpriteProject-shaped namespace with the fields the panels read/write.

    A namespace (not the real dataclass) keeps these tests independent of the
    constructor defaults sub-project 1 chose; the tab smoke tests use the real
    class through SpriteProjectManager.
    """
    project_dir = tmp_path / "hero"
    project_dir.mkdir()
    return types.SimpleNamespace(
        name="hero",
        project_dir=project_dir,
        character_source=None,
        plate_path=None,
        plate_color="#00FF00",
        turnaround={},
        brief="",
        genre_preset="sidescroller",
        actions=[
            ActionCard(id="a1", name="idle", prompt="idle pose"),
            ActionCard(id="a2", name="walk", prompt="walk cycle", target_frames=8, fps=12),
        ],
        generation=GenerationSettings(),
        cost_ledger=[],
        stage_fingerprints={},
    )


@pytest.fixture
def png(tmp_path):
    from PIL import Image

    path = tmp_path / "char.png"
    Image.new("RGBA", (64, 48), (255, 0, 0, 255)).save(path)
    return path


@pytest.fixture
def wait_for_worker():
    """Return a helper that joins a WorkerHost's current worker and pumps events.

    Worker signals reach the panel's bound-method slots through the GUI event
    loop; a test has no running loop, so pump it by hand after the join.
    """

    def _wait(host, timeout_ms=10000):
        worker = host._worker
        assert worker is not None, "no worker was started"
        assert worker.wait(timeout_ms), "worker did not finish in time"
        for _ in range(3):
            QApplication.processEvents()
        return worker

    return _wait
```

- [x] **Step 2: Failing tests** — create `tests/sprite/gui/test_sprite_worker.py`:

```python
# tests/sprite/gui/test_sprite_worker.py
"""SpriteWorker contract (design §1.1): progress, finished(object), failed, cancelled."""
import time

from PySide6.QtWidgets import QWidget

from core.sprite.generation.errors import SpriteGenerationError
from gui.sprite.workers import SpriteWorker, WorkerHost


class _UserError(SpriteGenerationError):
    """Independent of the real constructor: sets the two documented attributes."""

    def __init__(self, message):
        Exception.__init__(self, message)
        self.user_message = message
        self.retryable = False


def _run(worker, timeout_ms=5000):
    worker.start()
    assert worker.wait(timeout_ms)


def test_finished_carries_job_result(qapp):
    seen = []
    worker = SpriteWorker(lambda progress, token: 42, label="answer")
    worker.finished.connect(lambda result: seen.append(result))
    _run(worker)
    assert seen == [42]
    assert worker.label == "answer"


def test_progress_forwards_stage_tuple(qapp):
    seen = []

    def job(progress, token):
        progress("extract", 1, 4, "frame 1")
        return None

    worker = SpriteWorker(job)
    worker.progress.connect(lambda *args: seen.append(args))
    _run(worker)
    assert seen == [("extract", 1, 4, "frame 1")]


def test_failed_uses_user_message(qapp):
    seen = []

    def job(progress, token):
        raise _UserError("Quota exceeded - try again later")

    worker = SpriteWorker(job)
    worker.failed.connect(lambda message: seen.append(message))
    _run(worker)
    assert seen == ["Quota exceeded - try again later"]


def test_unexpected_exception_is_reported_not_raised(qapp, caplog):
    seen = []

    def job(progress, token):
        raise RuntimeError("boom")

    worker = SpriteWorker(job)
    worker.failed.connect(lambda message: seen.append(message))
    with caplog.at_level("ERROR"):
        _run(worker)
    assert seen == ["boom"]
    assert any("boom" in record.message for record in caplog.records)


def test_cancel_sets_token_and_emits_cancelled(qapp):
    outcome = []

    def job(progress, token):
        while True:
            token.raise_if_cancelled()
            time.sleep(0.005)

    worker = SpriteWorker(job)
    worker.cancelled.connect(lambda: outcome.append("cancelled"))
    worker.failed.connect(lambda message: outcome.append(("failed", message)))
    worker.start()
    worker.cancel()
    assert worker.wait(5000)
    assert worker.token.cancelled
    assert outcome == ["cancelled"]


class _Host(WorkerHost, QWidget):
    pass


def test_worker_host_runs_one_job_at_a_time(qapp):
    host = _Host()
    results = []

    def slow(progress, token):
        time.sleep(0.05)
        return "done"

    first = host.start_job(slow, label="a",
                           on_finished=lambda r: results.append(r),
                           on_failed=lambda m: results.append(("failed", m)))
    assert first is not None and host.is_busy()
    second = host.start_job(slow, label="b",
                            on_finished=lambda r: None, on_failed=lambda m: None)
    assert second is None  # busy: refused, not queued
    assert first.wait(5000)
    for _ in range(3):
        qapp.processEvents()
    assert results == ["done"]
    assert not host.is_busy()


def test_worker_host_shutdown_cancels_and_joins(qapp):
    host = _Host()

    def forever(progress, token):
        while True:
            token.raise_if_cancelled()
            time.sleep(0.005)

    worker = host.start_job(forever, label="loop",
                            on_finished=lambda r: None, on_failed=lambda m: None)
    assert worker is not None
    host.shutdown(timeout_ms=5000)
    assert not worker.isRunning()
    assert worker.token.cancelled
```

- [x] **Step 3: Run — expect failure**

```bash
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_sprite_worker.py -v
```
Expected: collection error `ModuleNotFoundError: No module named 'gui.sprite'`.

- [x] **Step 4: Implement** — create `gui/sprite/__init__.py`:

```python
"""Sprite tab GUI package (design §4.5). ``SpriteTab`` is exported in Task 8."""
```

Create `gui/sprite/workers.py`:

```python
"""SpriteWorker: one QThread per long-running sprite job (design §1.1).

The job is a callable ``job(progress, token) -> object``. ``progress`` has the
``ProgressFn`` shape ``(stage, done, total, message)``; ``token`` is the
worker's own ``CancelToken``. Signals:

- ``progress(str, int, int, str)`` — forwarded from the job.
- ``finished(object)`` — the job's return value. This name shadows
  ``QThread.finished()``; use ``wait()`` / ``isRunning()`` for lifecycle.
- ``failed(str)`` — ``SpriteGenerationError.user_message`` or ``str(exc)``.
- ``cancelled()`` — the job raised ``Cancelled`` (or returned after cancel).

Connect these to bound methods of QObjects so the slot runs on the GUI thread.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from PySide6.QtCore import QThread, Signal

from core.sprite.generation.errors import SpriteGenerationError
from core.sprite.pipeline import Cancelled, CancelToken, ProgressFn

logger = logging.getLogger(__name__)

Job = Callable[[ProgressFn, CancelToken], Any]


class SpriteWorker(QThread):
    progress = Signal(str, int, int, str)
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, job: Job, *, label: str = "job", parent=None):
        super().__init__(parent)
        self._job = job
        self._label = label
        self._token = CancelToken()

    @property
    def token(self) -> CancelToken:
        return self._token

    @property
    def label(self) -> str:
        return self._label

    def cancel(self) -> None:
        """Ask the job to stop. The job polls the token between frames/stages."""
        self._token.cancel()

    def _report(self, stage: str, done: int, total: int, message: str) -> None:
        self.progress.emit(str(stage), int(done), int(total), str(message))

    def run(self) -> None:
        try:
            result = self._job(self._report, self._token)
        except Cancelled:
            logger.info("Sprite worker %r cancelled", self._label)
            self.cancelled.emit()
            return
        except SpriteGenerationError as exc:
            message = getattr(exc, "user_message", None) or str(exc)
            logger.error("Sprite worker %r failed: %s", self._label, message, exc_info=True)
            self.failed.emit(message)
            return
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI and the log
            logger.error("Sprite worker %r failed: %s", self._label, exc, exc_info=True)
            self.failed.emit(str(exc))
            return
        if self._token.cancelled:
            logger.info("Sprite worker %r finished after cancel; result dropped", self._label)
            self.cancelled.emit()
            return
        self.finished.emit(result)


class WorkerHost:
    """Mixin for a QObject that runs at most one SpriteWorker at a time.

    ``start_job`` refuses (returns ``None``) while a worker runs; callers log a
    warning. The worker is parented to the host so Qt keeps it alive; the
    host must call ``shutdown()`` before it is destroyed.
    """

    _worker: Optional[SpriteWorker] = None

    def start_job(self, job: Job, *, label: str, on_finished, on_failed,
                  on_cancelled=None, on_progress=None) -> Optional[SpriteWorker]:
        if self.is_busy():
            logger.warning("Sprite job %r refused: %r is still running", label, self._worker.label)
            return None
        worker = SpriteWorker(job, label=label, parent=self)
        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        if on_cancelled is not None:
            worker.cancelled.connect(on_cancelled)
        if on_progress is not None:
            worker.progress.connect(on_progress)
        # Release AFTER the caller's slots (same connection type keeps order).
        worker.finished.connect(self._release_worker)
        worker.failed.connect(self._release_worker)
        worker.cancelled.connect(self._release_worker)
        self._worker = worker
        worker.start()
        return worker

    def is_busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def cancel_running(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def shutdown(self, timeout_ms: int = 5000) -> None:
        """Cancel and join the running worker (call from closeEvent / tab shutdown)."""
        worker = self._worker
        if worker is None:
            return
        worker.cancel()
        if worker.isRunning() and not worker.wait(timeout_ms):
            logger.error("Sprite worker %r did not stop within %d ms", worker.label, timeout_ms)
        self._worker = None

    def _release_worker(self, *_args) -> None:
        self._worker = None
```

- [x] **Step 5: Run — expect pass**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m py_compile /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/workers.py
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_sprite_worker.py -v
```
Expected: 7 passed.

- [x] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/__init__.py gui/sprite/workers.py tests/sprite/gui/conftest.py tests/sprite/gui/test_sprite_worker.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite-gui): SpriteWorker QThread with cancel token and progress signals"
```

---

### Task 2: `NamedConfigStore` (`core/sprite/configs.py`)

**Files:**
- Create: `core/sprite/configs.py`
- Create: `tests/sprite/test_named_configs.py`
- Reference: design decision 9 and §1.6 (`<Settings root>/sprite_configs.json` via `DataPaths.sprite_configs()`), `core/sprite/project.py` `GenerationSettings`

**Interfaces:**
- Consumes: `core.sprite.project.GenerationSettings` (dataclass, all fields defaulted), `core.paths.get_data_paths().sprite_configs() -> Path`.
- Produces: `core.sprite.configs.DEFAULT_NAME = "Default"`, `FORMAT_VERSION = 1`, `settings_to_dict(settings) -> dict`, `settings_from_dict(data, *, name=None) -> GenerationSettings`, `NamedConfigStore(path: Optional[Path] = None)` with `path -> Path`, `list_names() -> List[str]` ("Default" always first), `get(name) -> GenerationSettings` (`KeyError` when missing; "Default" always resolves), `save(name, settings) -> None` (`ValueError` on empty name), `delete(name) -> None` (`ValueError` for "Default", `KeyError` when missing).
- File format: `{"version": 1, "configs": {name: {GenerationSettings fields…}}}`, written atomically (tmp + `os.replace`).

- [x] **Step 1: Failing tests** — create `tests/sprite/test_named_configs.py`:

```python
# tests/sprite/test_named_configs.py
"""NamedConfigStore: named GenerationSettings in one JSON file (decision 9)."""
import json

import pytest

from core.paths import get_data_paths
from core.sprite.configs import DEFAULT_NAME, NamedConfigStore, settings_from_dict
from core.sprite.project import GenerationSettings


def _store(tmp_path):
    return NamedConfigStore(tmp_path / "sprite_configs.json")


def test_default_path_comes_from_data_paths():
    assert NamedConfigStore().path == get_data_paths().sprite_configs()


def test_fresh_store_lists_only_default(tmp_path):
    store = _store(tmp_path)
    assert store.list_names() == [DEFAULT_NAME]
    assert not store.path.exists()  # nothing written until a save


def test_default_resolves_to_dataclass_defaults(tmp_path):
    settings = _store(tmp_path).get(DEFAULT_NAME)
    assert settings == GenerationSettings(config_name=DEFAULT_NAME)


def test_save_get_roundtrip_and_ordering(tmp_path):
    store = _store(tmp_path)
    custom = GenerationSettings(provider="veo", model="veo-3.1-fast-generate-001",
                                duration_s=6, include_audio=True, plate_color="#0000FF")
    store.save("Zed", custom)
    store.save("Alpha", GenerationSettings())
    assert store.list_names() == [DEFAULT_NAME, "Alpha", "Zed"]
    loaded = store.get("Zed")
    assert loaded.config_name == "Zed"
    assert loaded.provider == "veo" and loaded.duration_s == 6 and loaded.include_audio
    doc = json.loads(store.path.read_text(encoding="utf-8"))
    assert doc["version"] == 1 and set(doc["configs"]) == {"Zed", "Alpha"}


def test_default_can_be_overwritten_but_not_deleted(tmp_path):
    store = _store(tmp_path)
    store.save(DEFAULT_NAME, GenerationSettings(duration_s=4))
    assert store.get(DEFAULT_NAME).duration_s == 4
    with pytest.raises(ValueError):
        store.delete(DEFAULT_NAME)
    assert store.list_names() == [DEFAULT_NAME]


def test_delete_removes_and_unknown_raises(tmp_path):
    store = _store(tmp_path)
    store.save("Temp", GenerationSettings())
    store.delete("Temp")
    assert store.list_names() == [DEFAULT_NAME]
    with pytest.raises(KeyError):
        store.delete("Temp")
    with pytest.raises(KeyError):
        store.get("Nope")


def test_empty_name_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        _store(tmp_path).save("   ", GenerationSettings())


def test_unknown_keys_are_dropped_and_missing_keys_default():
    settings = settings_from_dict({"provider": "veo", "future_field": 1}, name="X")
    assert settings.provider == "veo" and settings.config_name == "X"
    assert settings.fps == GenerationSettings().fps


def test_corrupt_file_is_logged_and_treated_as_empty(tmp_path, caplog):
    store = _store(tmp_path)
    store.path.write_text("{ not json", encoding="utf-8")
    with caplog.at_level("ERROR"):
        assert store.list_names() == [DEFAULT_NAME]
    assert any("unreadable" in record.message for record in caplog.records)
```

- [x] **Step 2: Run — expect failure**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_named_configs.py -v
```
Expected: `ModuleNotFoundError: No module named 'core.sprite.configs'`.

- [x] **Step 3: Implement** — create `core/sprite/configs.py`:

```python
"""Named generation configurations for the Sprite tab (design decision 9, §1.6).

One JSON file under the Settings root — ``get_data_paths().sprite_configs()`` —
holds every named ``GenerationSettings``. The "Default" entry always exists:
the user may overwrite it, never delete it. Pure Python (no Qt) so the CLI
reads the same file.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from core.paths import get_data_paths
from core.sprite.project import GenerationSettings

logger = logging.getLogger(__name__)

FORMAT_VERSION = 1
DEFAULT_NAME = "Default"


def settings_to_dict(settings: GenerationSettings) -> dict:
    return dataclasses.asdict(settings)


def settings_from_dict(data: Optional[dict], *, name: Optional[str] = None) -> GenerationSettings:
    """Build settings from a dict. Unknown keys are dropped; missing keys keep defaults."""
    known = {f.name for f in dataclasses.fields(GenerationSettings)}
    kwargs = {k: v for k, v in (data or {}).items() if k in known}
    if name is not None:
        kwargs["config_name"] = name
    return GenerationSettings(**kwargs)


class NamedConfigStore:
    """Read/write named GenerationSettings in one JSON document."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = Path(path) if path is not None else get_data_paths().sprite_configs()

    @property
    def path(self) -> Path:
        return self._path

    # -- persistence -------------------------------------------------------

    def _read(self) -> Dict[str, dict]:
        if not self._path.exists():
            return {}
        try:
            document = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.error("Sprite config store unreadable (%s): %s", self._path, exc)
            return {}
        configs = document.get("configs") if isinstance(document, dict) else None
        return {str(k): dict(v) for k, v in configs.items() if isinstance(v, dict)} \
            if isinstance(configs, dict) else {}

    def _write(self, configs: Dict[str, dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(json.dumps({"version": FORMAT_VERSION, "configs": configs}, indent=2),
                       encoding="utf-8")
        os.replace(tmp, self._path)

    # -- API ---------------------------------------------------------------

    def list_names(self) -> List[str]:
        names = set(self._read().keys())
        names.discard(DEFAULT_NAME)
        return [DEFAULT_NAME] + sorted(names)

    def get(self, name: str) -> GenerationSettings:
        configs = self._read()
        if name in configs:
            return settings_from_dict(configs[name], name=name)
        if name == DEFAULT_NAME:
            return GenerationSettings(config_name=DEFAULT_NAME)
        raise KeyError(name)

    def save(self, name: str, settings: GenerationSettings) -> None:
        name = (name or "").strip()
        if not name:
            raise ValueError("A configuration needs a name.")
        configs = self._read()
        data = settings_to_dict(settings)
        data["config_name"] = name
        configs[name] = data
        self._write(configs)
        logger.info("Saved sprite generation configuration %r", name)

    def delete(self, name: str) -> None:
        if name == DEFAULT_NAME:
            raise ValueError('The "Default" configuration cannot be deleted.')
        configs = self._read()
        if name not in configs:
            raise KeyError(name)
        del configs[name]
        self._write(configs)
        logger.info("Deleted sprite generation configuration %r", name)
```

- [x] **Step 4: Run — expect pass**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_named_configs.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py -v
```
Expected: 9 passed in the configs file; the path guard stays green.

- [x] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/configs.py tests/sprite/test_named_configs.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): NamedConfigStore for saved generation configurations"
```

---

### Task 3: Sprite preferences and the purge confirmation (`gui/sprite/prefs.py`)

**Files:**
- Create: `gui/sprite/prefs.py`
- Create: `tests/sprite/gui/test_sprite_prefs.py`
- Reference: design §1.6 (`sprite/purge_after_export`, default False, sticky, confirmed when enabled; deletions go through `core/recycle_bin.py` — the deletion itself is `SpriteProject.purge_intermediates()`, sub-project 1; the checkbox UI is 5b's export dialog)

**Interfaces:**
- Produces: `gui.sprite.prefs.sprite_settings() -> QSettings` (`QSettings("ImageAI", "Sprite")`), `PURGE_KEY = "sprite/purge_after_export"`, `LLM_PROVIDER_KEY = "sprite/llm_provider"`, `purge_after_export_enabled() -> bool`, `set_purge_after_export(enabled: bool) -> None`, `confirm_purge(parent: Optional[QWidget]) -> bool`, `PURGE_MESSAGE: str`, `get_pref(key: str, default=None)`, `set_pref(key: str, value) -> None`.

- [x] **Step 1: Failing tests** — create `tests/sprite/gui/test_sprite_prefs.py`:

```python
# tests/sprite/gui/test_sprite_prefs.py
"""Sticky purge-after-export preference (design §1.6)."""
from PySide6.QtWidgets import QMessageBox

import gui.sprite.prefs as prefs


def test_purge_defaults_to_off(qapp):
    prefs.sprite_settings().remove(prefs.PURGE_KEY)
    assert prefs.purge_after_export_enabled() is False


def test_purge_setting_is_sticky(qapp):
    prefs.set_purge_after_export(True)
    assert prefs.purge_after_export_enabled() is True
    prefs.set_purge_after_export(False)
    assert prefs.purge_after_export_enabled() is False


def test_purge_reads_ini_string_booleans(qapp):
    # QSettings' INI backend hands strings back; "true"/"false" must round-trip.
    settings = prefs.sprite_settings()
    settings.setValue(prefs.PURGE_KEY, "true")
    assert prefs.purge_after_export_enabled() is True
    settings.setValue(prefs.PURGE_KEY, "false")
    assert prefs.purge_after_export_enabled() is False
    settings.remove(prefs.PURGE_KEY)


def test_confirm_purge_names_deleted_folders(qapp, monkeypatch):
    asked = {}

    def fake_question(parent, title, text, buttons, default):
        asked.update(title=title, text=text, default=default)
        return QMessageBox.Yes

    monkeypatch.setattr(prefs.QMessageBox, "question", staticmethod(fake_question))
    assert prefs.confirm_purge(None) is True
    assert "clips/" in asked["text"] and "stages/" in asked["text"]
    assert "recycle bin" in asked["text"].lower()
    assert asked["default"] == QMessageBox.No  # Enter never enables the purge


def test_confirm_purge_no_returns_false(qapp, monkeypatch):
    monkeypatch.setattr(prefs.QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.No))
    assert prefs.confirm_purge(None) is False


def test_generic_pref_roundtrip(qapp):
    prefs.set_pref(prefs.LLM_PROVIDER_KEY, "openai")
    assert prefs.get_pref(prefs.LLM_PROVIDER_KEY, "google") == "openai"
    prefs.sprite_settings().remove(prefs.LLM_PROVIDER_KEY)
    assert prefs.get_pref(prefs.LLM_PROVIDER_KEY, "google") == "google"
```

- [x] **Step 2: Run — expect failure**

```bash
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_sprite_prefs.py -v
```
Expected: `ModuleNotFoundError: No module named 'gui.sprite.prefs'`.

- [x] **Step 3: Implement** — create `gui/sprite/prefs.py`:

```python
"""Sticky Sprite-tab preferences (QSettings) and the purge confirmation.

Every Sprite GUI module reads QSettings through ``sprite_settings()`` so all
keys live under one ``sprite/`` namespace in ``QSettings("ImageAI", "Sprite")``.
"""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox, QWidget

ORGANIZATION = "ImageAI"
APPLICATION = "Sprite"

PURGE_KEY = "sprite/purge_after_export"
LLM_PROVIDER_KEY = "sprite/llm_provider"

PURGE_MESSAGE = (
    "After every export, ImageAI deletes these folders of the current sprite project:\n\n"
    "  • clips/   — the generated video clips and their sidecars\n"
    "  • stages/  — every extracted, keyed, cleaned and resized frame\n\n"
    "The source image, the plate, the turnaround pack, the project file and the "
    "exports stay.\nDeleted files go to the system recycle bin.\n\n"
    "Turn on auto-purge after export?"
)


def sprite_settings() -> QSettings:
    return QSettings(ORGANIZATION, APPLICATION)


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return bool(value)


def get_pref(key: str, default: Any = None) -> Any:
    value = sprite_settings().value(key, default)
    return default if value is None else value


def set_pref(key: str, value: Any) -> None:
    settings = sprite_settings()
    settings.setValue(key, value)
    settings.sync()


def purge_after_export_enabled() -> bool:
    return _as_bool(get_pref(PURGE_KEY, False))


def set_purge_after_export(enabled: bool) -> None:
    set_pref(PURGE_KEY, bool(enabled))


def confirm_purge(parent: Optional[QWidget]) -> bool:
    """Ask before the purge preference turns on. Names what gets deleted."""
    reply = QMessageBox.question(
        parent, "Purge intermediates after export?", PURGE_MESSAGE,
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
    )
    return reply == QMessageBox.Yes
```

- [x] **Step 4: Run — expect pass**

```bash
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_sprite_prefs.py -v
```
Expected: 6 passed.

- [x] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/prefs.py tests/sprite/gui/test_sprite_prefs.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite-gui): sticky purge-after-export preference and confirmation"
```

---

### Task 4: `CharacterPanel` (`gui/sprite/character_panel.py`)

**Files:**
- Create: `gui/sprite/character_panel.py`
- Create: `tests/sprite/gui/test_character_panel.py`
- Reference: design §4.2 (`normalize_source`, `analyze_source`, `make_chroma_plate`, `generate_turnaround`), §1.6 (`source/character.png`, `source/plate.png`, `source/turnaround/<view>.png`), `gui/workers.py:35-55` (provider construction: `get_provider(name, {"api_key", "auth_mode"})`), `gui/dialog_utils.py:15-29` (`show_error`)

**Interfaces:**
- Consumes: `core.sprite.source.normalize_source(image: Path, out_png: Path, aspect_ratio: str) -> Path`, `core.sprite.source.analyze_source(image: Path) -> SourceAnalysis(has_alpha, border_color, border_uniform, size)`, `core.sprite.generation.plate.make_chroma_plate(provider, character, out_png, plate_color, *, model=None, log)`, `core.sprite.generation.turnaround.generate_turnaround(provider, character, out_dir, *, plate_color, log, token) -> Dict[str, Path]`, `providers.get_provider(name, config_dict)`, `config.get_api_key("google")`, `config.get_auth_mode("google")`.
- Produces: `gui.sprite.character_panel.CharacterPanel(WorkerHost, QGroupBox)` — `__init__(self, config, parent=None)`; Signals `sourceChanged(object)` (Path of the normalized PNG), `plateReady(object)` (Path), `turnaroundReady(object)` (dict view → Path), `plateColorChanged(str)`, `historyEntry(dict)`, `logMessage(str, str)`; methods `set_project(project) -> None`, `set_source(path: Path) -> None` (validates, then normalizes in a worker), `plate_color -> str` property, `make_plate() -> None`, `generate_turnaround() -> None`, `cancel() -> None`, plus the `WorkerHost` API. Helper `paths_from_mime(mime: QMimeData) -> List[Path]` (module-level, image suffixes only).
- Widget names (5b/tests rely on them): `drop_label`, `browse_btn`, `analysis_label`, `plate_color_btn`, `plate_btn`, `turnaround_btn`, `cancel_btn`, `progress`, `status_label`.

- [x] **Step 1: Failing tests** — create `tests/sprite/gui/test_character_panel.py`:

```python
# tests/sprite/gui/test_character_panel.py
"""CharacterPanel: intake, normalize, chroma plate, turnaround (offscreen)."""
import shutil
import types
from pathlib import Path

from PySide6.QtCore import QMimeData, QUrl

import gui.sprite.character_panel as cp
from gui.sprite.character_panel import CharacterPanel, paths_from_mime


def _analysis(size=(64, 48)):
    return types.SimpleNamespace(has_alpha=False, border_color="#FFFFFF",
                                 border_uniform=True, size=size)


def _patch_source(monkeypatch):
    def fake_normalize(image, out_png, aspect_ratio="16:9"):
        Path(out_png).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(image, out_png)
        return Path(out_png)

    monkeypatch.setattr(cp, "normalize_source", fake_normalize)
    monkeypatch.setattr(cp, "analyze_source", lambda image: _analysis())


def _capture_errors(monkeypatch):
    seen = []
    monkeypatch.setattr(cp, "show_error",
                        lambda parent, title, message, exception=None: seen.append(message))
    return seen


def test_construction_without_project_disables_actions(qapp, fake_config):
    panel = CharacterPanel(fake_config)
    assert not panel.browse_btn.isEnabled()
    assert not panel.plate_btn.isEnabled()
    assert not panel.turnaround_btn.isEnabled()
    assert panel.plate_color == "#00FF00"


def test_set_project_enables_browse_only(qapp, fake_config, fake_project):
    panel = CharacterPanel(fake_config)
    panel.set_project(fake_project)
    assert panel.browse_btn.isEnabled()
    assert not panel.plate_btn.isEnabled()  # no character yet


def test_set_source_normalizes_into_project_and_emits(qapp, fake_config, fake_project, png,
                                                      monkeypatch, wait_for_worker):
    _patch_source(monkeypatch)
    panel = CharacterPanel(fake_config)
    panel.set_project(fake_project)
    got = []
    panel.sourceChanged.connect(lambda p: got.append(p))
    panel.set_source(png)
    wait_for_worker(panel)
    expected = fake_project.project_dir / "source" / "character.png"
    assert expected.exists()
    assert fake_project.character_source == expected
    assert got == [expected]
    assert "64×48" in panel.analysis_label.text()
    assert panel.plate_btn.isEnabled() and panel.turnaround_btn.isEnabled()


def test_set_source_missing_file_reports_error_without_worker(qapp, fake_config, fake_project,
                                                              monkeypatch, tmp_path):
    seen = _capture_errors(monkeypatch)
    panel = CharacterPanel(fake_config)
    panel.set_project(fake_project)
    panel.set_source(tmp_path / "nope.png")
    assert seen and "nope.png" in seen[0]
    assert panel._worker is None


def test_set_source_without_project_reports_error(qapp, fake_config, png, monkeypatch):
    seen = _capture_errors(monkeypatch)
    panel = CharacterPanel(fake_config)
    panel.set_source(png)
    assert seen and "project" in seen[0].lower()


def test_make_plate_requires_api_key(qapp, fake_project, png, monkeypatch):
    seen = _capture_errors(monkeypatch)
    config = types.SimpleNamespace(get_api_key=lambda p: None, get_auth_mode=lambda p="google": "api-key")
    panel = CharacterPanel(config)
    fake_project.character_source = png
    panel.set_project(fake_project)
    panel.make_plate()
    assert seen and "api key" in seen[0].lower()
    assert panel._worker is None


def test_make_plate_runs_in_worker_and_records_plate(qapp, fake_config, fake_project, png,
                                                     monkeypatch, wait_for_worker):
    calls = {}

    def fake_make_plate(provider, character, out_png, plate_color="#00FF00", *, model=None, log=None):
        calls.update(character=character, out=out_png, color=plate_color)
        Path(out_png).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(character, out_png)
        log("plate done")
        return Path(out_png)

    monkeypatch.setattr(cp, "make_chroma_plate", fake_make_plate)
    monkeypatch.setattr(cp, "get_provider", lambda name, cfg: object())
    panel = CharacterPanel(fake_config)
    fake_project.character_source = png
    panel.set_project(fake_project)
    ready, history, lines = [], [], []
    panel.plateReady.connect(lambda p: ready.append(p))
    panel.historyEntry.connect(lambda e: history.append(e))
    panel.logMessage.connect(lambda m, level: lines.append(m))
    panel.make_plate()
    wait_for_worker(panel)
    expected = fake_project.project_dir / "source" / "plate.png"
    assert calls["out"] == expected and calls["color"] == "#00FF00"
    assert fake_project.plate_path == expected
    assert ready == [expected]
    assert history and history[0]["path"] == expected and history[0]["source_tab"] == "sprite"
    assert any("plate done" in line for line in lines)


def test_worker_failure_is_shown_and_logged(qapp, fake_config, fake_project, png,
                                            monkeypatch, wait_for_worker):
    def boom(*a, **k):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(cp, "make_chroma_plate", boom)
    monkeypatch.setattr(cp, "get_provider", lambda name, cfg: object())
    seen = _capture_errors(monkeypatch)
    panel = CharacterPanel(fake_config)
    fake_project.character_source = png
    panel.set_project(fake_project)
    panel.make_plate()
    wait_for_worker(panel)
    assert seen == ["provider exploded"]
    assert not panel.progress.isVisible()


def test_generate_turnaround_stores_views(qapp, fake_config, fake_project, png,
                                          monkeypatch, wait_for_worker):
    def fake_turnaround(provider, character, out_dir, views=("front", "side"), *, plate_color,
                        do_not_change=(), model=None, log=None, token=None):
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        result = {}
        for view in ("front", "side"):
            target = Path(out_dir) / f"{view}.png"
            shutil.copy(character, target)
            result[view] = target
        return result

    monkeypatch.setattr(cp, "generate_turnaround", fake_turnaround)
    monkeypatch.setattr(cp, "get_provider", lambda name, cfg: object())
    panel = CharacterPanel(fake_config)
    fake_project.character_source = png
    panel.set_project(fake_project)
    got = []
    panel.turnaroundReady.connect(lambda d: got.append(d))
    panel.generate_turnaround()
    wait_for_worker(panel)
    assert set(fake_project.turnaround) == {"front", "side"}
    assert got and set(got[0]) == {"front", "side"}


def test_plate_color_change_updates_project_and_emits(qapp, fake_config, fake_project, monkeypatch):
    from PySide6.QtGui import QColor
    monkeypatch.setattr(cp.QColorDialog, "getColor",
                        staticmethod(lambda *a, **k: QColor("#ff00ff")))
    panel = CharacterPanel(fake_config)
    panel.set_project(fake_project)
    got = []
    panel.plateColorChanged.connect(lambda c: got.append(c))
    panel.plate_color_btn.click()
    assert panel.plate_color == "#FF00FF"
    assert fake_project.plate_color == "#FF00FF"
    assert got == ["#FF00FF"]


def test_paths_from_mime_filters_images(qapp, tmp_path):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(tmp_path / "a.png")),
                  QUrl.fromLocalFile(str(tmp_path / "b.txt"))])
    assert paths_from_mime(mime) == [tmp_path / "a.png"]
```

- [x] **Step 2: Run — expect failure**

```bash
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_character_panel.py -v
```
Expected: `ModuleNotFoundError: No module named 'gui.sprite.character_panel'`.

- [x] **Step 3: Implement** — create `gui/sprite/character_panel.py`:

```python
"""Character intake panel: drop/browse → normalize → chroma plate → turnaround.

All PIL and provider work runs inside a SpriteWorker; the GUI thread only
paints one thumbnail. Output layout (design §1.6):
``<project_dir>/source/character.png``, ``source/plate.png``,
``source/turnaround/<view>.png``.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QColorDialog, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QVBoxLayout,
)

from core.sprite.generation.plate import make_chroma_plate
from core.sprite.generation.turnaround import generate_turnaround
from core.sprite.source import analyze_source, normalize_source
from gui.dialog_utils import show_error
from gui.sprite.workers import WorkerHost
from providers import get_provider

logger = logging.getLogger(__name__)

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")
THUMB_SIZE = 200
DROP_HINT = "Drop a character image here\nor click Browse…"


def paths_from_mime(mime: QMimeData) -> List[Path]:
    """Local image files carried by a drag; other files are ignored."""
    paths: List[Path] = []
    if not mime.hasUrls():
        return paths
    for url in mime.urls():
        local = url.toLocalFile()
        if local and Path(local).suffix.lower() in IMAGE_SUFFIXES:
            paths.append(Path(local))
    return paths


class CharacterPanel(WorkerHost, QGroupBox):
    sourceChanged = Signal(object)      # Path — normalized character PNG
    plateReady = Signal(object)         # Path
    turnaroundReady = Signal(object)    # Dict[str, Path]
    plateColorChanged = Signal(str)
    historyEntry = Signal(dict)
    logMessage = Signal(str, str)

    def __init__(self, config, parent=None):
        super().__init__("Character", parent)
        self.config = config
        self.project = None
        self._plate_color = "#00FF00"
        self._build()
        self.setAcceptDrops(True)
        self._sync_enabled()

    # -- UI ----------------------------------------------------------------

    def _build(self) -> None:
        root = QVBoxLayout(self)

        self.drop_label = QLabel(DROP_HINT)
        self.drop_label.setAlignment(Qt.AlignCenter)
        self.drop_label.setMinimumHeight(THUMB_SIZE)
        self.drop_label.setStyleSheet("border: 2px dashed #888; padding: 8px;")
        root.addWidget(self.drop_label)

        row = QHBoxLayout()
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.clicked.connect(self._browse)
        row.addWidget(self.browse_btn)
        self.analysis_label = QLabel("No character loaded.")
        self.analysis_label.setWordWrap(True)
        row.addWidget(self.analysis_label, 1)
        root.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Plate color:"))
        self.plate_color_btn = QPushButton()
        self.plate_color_btn.setToolTip("Chroma key color used for the plate and every clip")
        self.plate_color_btn.clicked.connect(self._pick_plate_color)
        row2.addWidget(self.plate_color_btn)
        self.plate_btn = QPushButton("Make chroma plate")
        self.plate_btn.clicked.connect(self.make_plate)
        row2.addWidget(self.plate_btn)
        self.turnaround_btn = QPushButton("Generate turnaround")
        self.turnaround_btn.clicked.connect(self.generate_turnaround)
        row2.addWidget(self.turnaround_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel)
        row2.addWidget(self.cancel_btn)
        root.addLayout(row2)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)
        self.status_label = QLabel("")
        root.addWidget(self.status_label)
        self._set_plate_color_ui(self._plate_color)

    def _sync_enabled(self) -> None:
        busy = self.is_busy()
        has_project = self.project is not None
        has_source = has_project and bool(getattr(self.project, "character_source", None))
        self.browse_btn.setEnabled(has_project and not busy)
        self.plate_btn.setEnabled(has_source and not busy)
        self.turnaround_btn.setEnabled(has_source and not busy)
        self.cancel_btn.setEnabled(busy)
        self.setAcceptDrops(has_project and not busy)

    def _set_plate_color_ui(self, hex_color: str) -> None:
        self._plate_color = hex_color.upper()
        self.plate_color_btn.setText(self._plate_color)
        self.plate_color_btn.setStyleSheet(f"background-color: {self._plate_color};")

    def _show_thumbnail(self, path: Optional[Path]) -> None:
        if path and Path(path).exists():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.drop_label.setPixmap(pixmap.scaled(
                    THUMB_SIZE, THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return
        self.drop_label.setPixmap(QPixmap())
        self.drop_label.setText(DROP_HINT)

    def _describe(self, analysis) -> str:
        w, h = analysis.size
        parts = [f"{w}×{h}", "has alpha" if analysis.has_alpha else "no alpha"]
        if analysis.border_color:
            uniform = "uniform" if analysis.border_uniform else "mixed"
            parts.append(f"border {analysis.border_color} ({uniform})")
        return ", ".join(parts)

    # -- public API --------------------------------------------------------

    @property
    def plate_color(self) -> str:
        return self._plate_color

    def set_project(self, project) -> None:
        self.project = project
        if project is not None:
            self._set_plate_color_ui(getattr(project, "plate_color", None) or "#00FF00")
            self._show_thumbnail(getattr(project, "character_source", None))
            source = getattr(project, "character_source", None)
            if source and Path(source).exists():
                try:
                    self.analysis_label.setText(self._describe(analyze_source(Path(source))))
                except Exception as exc:  # noqa: BLE001 - readout only
                    logger.warning("Source analysis failed: %s", exc)
                    self.analysis_label.setText(Path(source).name)
            else:
                self.analysis_label.setText("No character loaded.")
        else:
            self._show_thumbnail(None)
            self.analysis_label.setText("No character loaded.")
        self._sync_enabled()

    def set_source(self, path: Path) -> None:
        """Normalize ``path`` into the project (worker) and record it as the character."""
        path = Path(path)
        if self.project is None:
            show_error(self, "Sprite", "Create or open a sprite project before adding a character.")
            return
        if not path.exists() or path.suffix.lower() not in IMAGE_SUFFIXES:
            show_error(self, "Sprite", f"Not an image file: {path.name}")
            return
        out_png = Path(self.project.project_dir) / "source" / "character.png"
        aspect = getattr(self.project.generation, "aspect_ratio", "16:9")

        def job(progress, token):
            progress("source", 0, 0, f"Normalizing {path.name}")
            out_png.parent.mkdir(parents=True, exist_ok=True)
            out = normalize_source(path, out_png, aspect_ratio=aspect)
            token.raise_if_cancelled()
            return Path(out), analyze_source(Path(out))

        self.logMessage.emit(f"Importing character from {path}", "INFO")
        self._begin("normalize", job, self._on_source_done)

    def make_plate(self) -> None:
        if not self._ready_for_provider("chroma plate"):
            return
        character = Path(self.project.character_source)
        out_png = Path(self.project.project_dir) / "source" / "plate.png"
        color = self._plate_color
        provider_cfg = self._provider_config()
        if provider_cfg is None:
            return

        def job(progress, token):
            progress("plate", 0, 0, f"Placing character on {color} plate")
            out_png.parent.mkdir(parents=True, exist_ok=True)
            provider = get_provider("google", provider_cfg)
            return Path(make_chroma_plate(provider, character, out_png, color,
                                          log=lambda m: progress("plate", 0, 0, m)))

        self.logMessage.emit(f"Chroma plate requested ({color}) for {character.name}", "INFO")
        self._begin("plate", job, self._on_plate_done)

    def generate_turnaround(self) -> None:
        if not self._ready_for_provider("turnaround"):
            return
        character = Path(self.project.character_source)
        out_dir = Path(self.project.project_dir) / "source" / "turnaround"
        color = self._plate_color
        provider_cfg = self._provider_config()
        if provider_cfg is None:
            return

        def job(progress, token):
            progress("turnaround", 0, 0, "Generating front / side / back / ¾ views")
            provider = get_provider("google", provider_cfg)
            views = generate_turnaround(provider, character, out_dir, plate_color=color,
                                        log=lambda m: progress("turnaround", 0, 0, m),
                                        token=token)
            return {str(k): Path(v) for k, v in dict(views).items()}

        self.logMessage.emit(f"Turnaround pack requested for {character.name}", "INFO")
        self._begin("turnaround", job, self._on_turnaround_done)

    def cancel(self) -> None:
        if self.is_busy():
            self.logMessage.emit("Cancelling…", "WARNING")
            self.cancel_running()

    # -- worker plumbing ---------------------------------------------------

    def _ready_for_provider(self, what: str) -> bool:
        if self.project is None:
            show_error(self, "Sprite", f"Open a sprite project before making a {what}.")
            return False
        source = getattr(self.project, "character_source", None)
        if not source or not Path(source).exists():
            show_error(self, "Sprite", f"Load a character image before making a {what}.")
            return False
        return True

    def _provider_config(self) -> Optional[dict]:
        api_key = self.config.get_api_key("google")
        auth_mode = self.config.get_auth_mode("google")
        if not api_key:
            show_error(self, "Sprite", "No Google API key is configured. Add one in Settings.")
            return None
        return {"api_key": api_key, "auth_mode": auth_mode}

    def _begin(self, label: str, job, on_finished) -> None:
        worker = self.start_job(job, label=label, on_finished=on_finished,
                                on_failed=self._on_failed, on_cancelled=self._on_cancelled,
                                on_progress=self._on_progress)
        if worker is None:
            self.logMessage.emit("Another character job is still running.", "WARNING")
            return
        self.progress.setRange(0, 0)
        self.progress.setVisible(True)
        self._sync_enabled()

    def _finish(self) -> None:
        self.progress.setVisible(False)
        self.status_label.setText("")
        self._sync_enabled()

    def _history_entry(self, path: Path, prompt: str) -> dict:
        return {"path": path, "prompt": prompt, "provider": "google", "model": "",
                "timestamp": time.time(), "cost": 0.0, "source_tab": "sprite"}

    def _on_progress(self, stage: str, done: int, total: int, message: str) -> None:
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
        else:
            self.progress.setRange(0, 0)
        self.status_label.setText(f"{stage}: {message}")
        self.logMessage.emit(f"[{stage}] {message}", "INFO")

    def _on_failed(self, message: str) -> None:
        self._finish()
        self.logMessage.emit(message, "ERROR")
        show_error(self, "Sprite", message)

    def _on_cancelled(self) -> None:
        self._finish()
        self.logMessage.emit("Cancelled.", "WARNING")

    def _on_source_done(self, result) -> None:
        out, analysis = result
        self.project.character_source = out
        self._show_thumbnail(out)
        self.analysis_label.setText(self._describe(analysis))
        self._finish()
        self.logMessage.emit(f"Character normalized → {out}", "SUCCESS")
        self.sourceChanged.emit(out)

    def _on_plate_done(self, out) -> None:
        out = Path(out)
        self.project.plate_path = out
        self.project.plate_color = self._plate_color
        self._finish()
        self.logMessage.emit(f"Chroma plate saved → {out}", "SUCCESS")
        self.historyEntry.emit(self._history_entry(out, f"chroma plate {self._plate_color}"))
        self.plateReady.emit(out)

    def _on_turnaround_done(self, views: Dict[str, Path]) -> None:
        self.project.turnaround = dict(views)
        self._finish()
        self.logMessage.emit(f"Turnaround pack saved: {', '.join(sorted(views))}", "SUCCESS")
        for view, path in views.items():
            self.historyEntry.emit(self._history_entry(path, f"turnaround {view}"))
        self.turnaroundReady.emit(dict(views))

    # -- user actions ------------------------------------------------------

    def _browse(self) -> None:
        filters = "Images (" + " ".join(f"*{s}" for s in IMAGE_SUFFIXES) + ")"
        path, _ = QFileDialog.getOpenFileName(self, "Choose a character image", "", filters)
        if path:
            self.set_source(Path(path))

    def _pick_plate_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._plate_color), self, "Chroma plate color")
        if not color.isValid():
            return
        self._set_plate_color_ui(color.name())
        if self.project is not None:
            self.project.plate_color = self._plate_color
        self.logMessage.emit(f"Plate color set to {self._plate_color}", "INFO")
        self.plateColorChanged.emit(self._plate_color)

    # -- drag & drop -------------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        if paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        paths = paths_from_mime(event.mimeData())
        if paths:
            event.acceptProposedAction()
            self.set_source(paths[0])
```

- [x] **Step 4: Run — expect pass**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m py_compile /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/character_panel.py
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_character_panel.py -v
```
Expected: 11 passed.

- [x] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/character_panel.py tests/sprite/gui/test_character_panel.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite-gui): CharacterPanel with source intake, chroma plate, turnaround"
```

---

### Task 5: `GenerationSettingsDialog` (`gui/sprite/generation_settings_dialog.py`)

**Files:**
- Create: `gui/sprite/generation_settings_dialog.py`
- Create: `tests/sprite/gui/test_generation_settings_dialog.py`
- Reference: design decision 9, §2 `GenerationSettings`, §4.2 `estimate_action`; `core/video/omni_client.py:64-77` (`OmniModel.default_id()`), `core/video/veo_client.py:45-62` (`VeoModel` members), `gui/common/dialog_conventions.py` (`DialogCleanupMixin`, `bind_primary_action`, `set_default_button`), `tests/gui/test_dialog_conventions.py:78-112` (primary-action test idiom)

**Interfaces:**
- Consumes: `core.sprite.project.GenerationSettings / ActionCard`, `core.sprite.configs.NamedConfigStore / DEFAULT_NAME`, `core.sprite.generation.cost.estimate_action(settings, action) -> Optional[float]`, `core.video.omni_client.OmniModel.default_id()`, `core.video.veo_client.VeoModel`.
- Produces: `gui.sprite.generation_settings_dialog.GenerationSettingsDialog(DialogCleanupMixin, QDialog)` — `__init__(self, settings: GenerationSettings, store: NamedConfigStore, parent=None)`; `set_settings(settings) -> None`; `settings() -> GenerationSettings`; module constants `PROVIDERS = ("omni", "veo")`, `RESOLUTIONS = ("720p", "1080p")`, `ASPECT_RATIOS = ("16:9", "9:16", "1:1")`, `PROVIDER_DEFAULT_LABEL = "(provider default)"`, `GEOMETRY_KEY = "sprite/gen_settings_geometry"`; `model_choices(provider: str) -> List[str]`. Ctrl+Enter = OK (`self._primary`), Escape = reject (QDialog default), geometry saved on every exit path.
- Widget names: `config_combo`, `load_btn`, `save_as_btn`, `delete_btn`, `provider_combo`, `model_combo` (editable), `resolution_combo`, `aspect_combo`, `duration_spin`, `fps_spin`, `loop_check`, `plate_color_btn`, `turnaround_check`, `audio_check`, `cost_label`, `ok_btn`, `cancel_btn`.

- [x] **Step 1: Failing tests** — create `tests/sprite/gui/test_generation_settings_dialog.py`:

```python
# tests/sprite/gui/test_generation_settings_dialog.py
"""GenerationSettingsDialog: every field editable, named configs, cost line, Ctrl+Enter."""
from PySide6.QtWidgets import QDialog

import gui.sprite.generation_settings_dialog as gsd
from core.sprite.configs import DEFAULT_NAME, NamedConfigStore
from core.sprite.project import GenerationSettings
from gui.sprite.generation_settings_dialog import (
    PROVIDER_DEFAULT_LABEL, GenerationSettingsDialog, model_choices,
)


def _dialog(tmp_path, settings=None):
    store = NamedConfigStore(tmp_path / "configs.json")
    return GenerationSettingsDialog(settings or GenerationSettings(), store), store


def test_defaults_roundtrip_with_provider_default_model(qapp, tmp_path):
    dialog, _ = _dialog(tmp_path)
    assert dialog.provider_combo.currentText() == "omni"
    assert dialog.model_combo.currentText() == PROVIDER_DEFAULT_LABEL
    assert dialog.settings() == GenerationSettings()


def test_every_field_roundtrips(qapp, tmp_path):
    custom = GenerationSettings(provider="veo", model="veo-3.1-fast-generate-001",
                                resolution="1080p", aspect_ratio="9:16", duration_s=6, fps=30,
                                loop_conditioning=False, plate_color="#0000FF",
                                use_turnaround_refs=False, include_audio=True,
                                config_name=DEFAULT_NAME)
    dialog, _ = _dialog(tmp_path)
    dialog.set_settings(custom)
    assert dialog.settings() == custom


def test_provider_switch_repopulates_models(qapp, tmp_path):
    dialog, _ = _dialog(tmp_path)
    dialog.provider_combo.setCurrentText("veo")
    items = [dialog.model_combo.itemText(i) for i in range(dialog.model_combo.count())]
    assert items[0] == PROVIDER_DEFAULT_LABEL
    assert "veo-3.1-generate-001" in items
    assert dialog.audio_check.isEnabled()
    dialog.provider_combo.setCurrentText("omni")
    items = [dialog.model_combo.itemText(i) for i in range(dialog.model_combo.count())]
    assert items == [PROVIDER_DEFAULT_LABEL] + model_choices("omni")
    assert not dialog.audio_check.isEnabled()


def test_custom_model_text_is_kept(qapp, tmp_path):
    dialog, _ = _dialog(tmp_path)
    dialog.model_combo.setEditText("my-custom-model")
    assert dialog.settings().model == "my-custom-model"


def test_save_as_adds_named_config(qapp, tmp_path, monkeypatch):
    dialog, store = _dialog(tmp_path)
    monkeypatch.setattr(gsd.QInputDialog, "getText", staticmethod(lambda *a, **k: ("Fast", True)))
    dialog.duration_spin.setValue(4)
    dialog.save_as_btn.click()
    assert "Fast" in store.list_names()
    assert store.get("Fast").duration_s == 4
    assert dialog.config_combo.currentText() == "Fast"
    assert dialog.settings().config_name == "Fast"


def test_load_applies_named_config(qapp, tmp_path):
    dialog, store = _dialog(tmp_path)
    store.save("Tall", GenerationSettings(aspect_ratio="9:16", fps=12))
    dialog._reload_names(select="Tall")
    dialog.load_btn.click()
    assert dialog.aspect_combo.currentText() == "9:16"
    assert dialog.fps_spin.value() == 12


def test_delete_default_is_refused_and_reported(qapp, tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(gsd, "show_error",
                        lambda parent, title, message, exception=None: seen.append(message))
    dialog, store = _dialog(tmp_path)
    dialog.delete_btn.click()
    assert seen and "Default" in seen[0]
    assert store.list_names() == [DEFAULT_NAME]


def test_delete_named_config_after_confirmation(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    dialog, store = _dialog(tmp_path)
    store.save("Temp", GenerationSettings())
    dialog._reload_names(select="Temp")
    monkeypatch.setattr(gsd.QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    dialog.delete_btn.click()
    assert store.list_names() == [DEFAULT_NAME]
    assert dialog.config_combo.currentText() == DEFAULT_NAME


def test_cost_line_shows_estimate_or_unknown(qapp, tmp_path, monkeypatch):
    dialog, _ = _dialog(tmp_path)
    monkeypatch.setattr(gsd, "estimate_action", lambda settings, action: 0.5)
    dialog._update_cost()
    assert "$0.50" in dialog.cost_label.text()
    monkeypatch.setattr(gsd, "estimate_action", lambda settings, action: None)
    dialog._update_cost()
    assert "unknown" in dialog.cost_label.text()


def test_cost_estimator_error_is_logged_not_raised(qapp, tmp_path, monkeypatch, caplog):
    dialog, _ = _dialog(tmp_path)

    def broken(settings, action):
        raise RuntimeError("no price table")

    monkeypatch.setattr(gsd, "estimate_action", broken)
    with caplog.at_level("WARNING"):
        dialog._update_cost()
    assert "unknown" in dialog.cost_label.text()
    assert any("no price table" in record.message for record in caplog.records)


def test_ctrl_enter_accepts(qapp, tmp_path):
    dialog, _ = _dialog(tmp_path)
    dialog.show()
    dialog._primary._activated()
    assert dialog.result() == QDialog.Accepted


def test_geometry_saved_on_close(qapp, tmp_path):
    from gui.sprite.prefs import sprite_settings
    dialog, _ = _dialog(tmp_path)
    dialog.show()
    dialog.reject()
    assert sprite_settings().value(gsd.GEOMETRY_KEY) is not None
```

- [x] **Step 2: Run — expect failure**

```bash
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_generation_settings_dialog.py -v
```
Expected: `ModuleNotFoundError: No module named 'gui.sprite.generation_settings_dialog'`.

- [x] **Step 3: Implement** — create `gui/sprite/generation_settings_dialog.py`:

```python
"""Generation Settings dialog: every GenerationSettings field + named configurations.

Decision 9: defaults live here, every field is editable, and the user keeps
several named configurations (``NamedConfigStore``). A live cost line shows
``estimate_action`` for one clip of the chosen duration — "unknown" when the
estimator has no verified rate (decision 8: never a guess).
"""
from __future__ import annotations

import logging
from typing import List, Optional

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QFormLayout, QHBoxLayout,
    QInputDialog, QLabel, QMessageBox, QPushButton, QSpinBox, QVBoxLayout,
)

from core.sprite.configs import DEFAULT_NAME, NamedConfigStore
from core.sprite.generation.cost import estimate_action
from core.sprite.project import ActionCard, GenerationSettings
from core.video.omni_client import OmniModel
from core.video.veo_client import VeoModel
from gui.common.dialog_conventions import DialogCleanupMixin, bind_primary_action, set_default_button
from gui.dialog_utils import show_error
from gui.sprite.prefs import sprite_settings

logger = logging.getLogger(__name__)

PROVIDERS = ("omni", "veo")
RESOLUTIONS = ("720p", "1080p")
ASPECT_RATIOS = ("16:9", "9:16", "1:1")
PROVIDER_DEFAULT_LABEL = "(provider default)"
GEOMETRY_KEY = "sprite/gen_settings_geometry"


def model_choices(provider: str) -> List[str]:
    """Model IDs offered for a provider. Omni resolves through the registry."""
    if provider == "veo":
        return [model.value for model in VeoModel]
    return [OmniModel.default_id()]


class GenerationSettingsDialog(DialogCleanupMixin, QDialog):
    def __init__(self, settings: GenerationSettings, store: NamedConfigStore, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generation Settings")
        self.setMinimumWidth(480)
        self._store = store
        self._plate_color = settings.plate_color
        self._build()
        self._reload_names(select=settings.config_name)
        self.set_settings(settings)
        self._primary = bind_primary_action(self, self.accept)
        set_default_button(self, self.ok_btn, focus=False)
        self.provider_combo.setFocus()
        geometry = sprite_settings().value(GEOMETRY_KEY)
        if geometry is not None:
            self.restoreGeometry(geometry)

    # -- build -------------------------------------------------------------

    def _build(self) -> None:
        root = QVBoxLayout(self)

        config_row = QHBoxLayout()
        config_row.addWidget(QLabel("Configuration:"))
        self.config_combo = QComboBox()
        self.config_combo.currentTextChanged.connect(self._on_config_selected)
        config_row.addWidget(self.config_combo, 1)
        self.load_btn = QPushButton("Load")
        self.load_btn.clicked.connect(self._on_load)
        self.save_as_btn = QPushButton("Save as…")
        self.save_as_btn.clicked.connect(self._on_save_as)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._on_delete)
        for button in (self.load_btn, self.save_as_btn, self.delete_btn):
            config_row.addWidget(button)
        root.addLayout(config_row)

        form = QFormLayout()
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(PROVIDERS)
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        form.addRow("Provider:", self.provider_combo)
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        form.addRow("Model:", self.model_combo)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(RESOLUTIONS)
        form.addRow("Resolution:", self.resolution_combo)
        self.aspect_combo = QComboBox()
        self.aspect_combo.addItems(ASPECT_RATIOS)
        form.addRow("Aspect ratio:", self.aspect_combo)
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 15)
        self.duration_spin.setSuffix(" s")
        form.addRow("Clip duration:", self.duration_spin)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setToolTip("Clip frame rate. Presets: 8, 12, 24, 30, 60.")
        form.addRow("Clip FPS:", self.fps_spin)
        self.loop_check = QCheckBox("Loop conditioning (Veo first+last frame; forces 8 s)")
        form.addRow("", self.loop_check)
        self.plate_color_btn = QPushButton()
        self.plate_color_btn.clicked.connect(self._pick_plate_color)
        form.addRow("Plate color:", self.plate_color_btn)
        self.turnaround_check = QCheckBox("Attach turnaround views as references")
        form.addRow("", self.turnaround_check)
        self.audio_check = QCheckBox("Include audio (Veo only; changes the price)")
        form.addRow("", self.audio_check)
        root.addLayout(form)

        self.cost_label = QLabel("Estimated cost per action: unknown")
        root.addWidget(self.cost_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self.ok_btn)
        buttons.addWidget(self.cancel_btn)
        root.addLayout(buttons)

        for signal in (self.model_combo.currentTextChanged, self.model_combo.editTextChanged,
                       self.resolution_combo.currentTextChanged, self.duration_spin.valueChanged,
                       self.audio_check.toggled):
            signal.connect(self._update_cost)

    # -- models ------------------------------------------------------------

    def _on_provider_changed(self, provider: str) -> None:
        current = self._model_text()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItem(PROVIDER_DEFAULT_LABEL)
        for model_id in model_choices(provider):
            self.model_combo.addItem(model_id)
        self.model_combo.blockSignals(False)
        self._select_model(current)
        is_veo = provider == "veo"
        self.audio_check.setEnabled(is_veo)
        self.loop_check.setEnabled(is_veo)
        self._update_cost()

    def _select_model(self, model: str) -> None:
        if not model:
            self.model_combo.setCurrentIndex(0)
            return
        index = self.model_combo.findText(model)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)
        else:
            self.model_combo.setEditText(model)

    def _model_text(self) -> str:
        text = self.model_combo.currentText().strip()
        return "" if text == PROVIDER_DEFAULT_LABEL else text

    # -- settings <-> widgets ---------------------------------------------

    def set_settings(self, settings: GenerationSettings) -> None:
        provider = settings.provider if settings.provider in PROVIDERS else "omni"
        self.provider_combo.setCurrentText(provider)
        self._on_provider_changed(provider)  # populate even when the text did not change
        self._select_model(settings.model)
        self.resolution_combo.setCurrentText(settings.resolution)
        self.aspect_combo.setCurrentText(settings.aspect_ratio)
        self.duration_spin.setValue(int(settings.duration_s))
        self.fps_spin.setValue(int(settings.fps))
        self.loop_check.setChecked(bool(settings.loop_conditioning))
        self._set_plate_color(settings.plate_color)
        self.turnaround_check.setChecked(bool(settings.use_turnaround_refs))
        self.audio_check.setChecked(bool(settings.include_audio))
        index = self.config_combo.findText(settings.config_name)
        if index >= 0:
            self.config_combo.setCurrentIndex(index)
        self._update_cost()

    def settings(self) -> GenerationSettings:
        return GenerationSettings(
            provider=self.provider_combo.currentText(),
            model=self._model_text(),
            resolution=self.resolution_combo.currentText(),
            aspect_ratio=self.aspect_combo.currentText(),
            duration_s=self.duration_spin.value(),
            fps=self.fps_spin.value(),
            loop_conditioning=self.loop_check.isChecked(),
            plate_color=self._plate_color,
            use_turnaround_refs=self.turnaround_check.isChecked(),
            include_audio=self.audio_check.isChecked(),
            config_name=self.config_combo.currentText() or DEFAULT_NAME,
        )

    def _update_cost(self, *_args) -> None:
        try:
            current = self.settings()
            sample = ActionCard(id="preview", name="preview", prompt="",
                                duration_s=current.duration_s)
            usd = estimate_action(current, sample)
        except Exception as exc:  # noqa: BLE001 - a broken estimator must not break the dialog
            logger.warning("Cost estimate failed: %s", exc)
            usd = None
        if usd is None:
            self.cost_label.setText("Estimated cost per action: unknown")
        else:
            self.cost_label.setText(f"Estimated cost per action: ${usd:.2f}")

    # -- plate color -------------------------------------------------------

    def _set_plate_color(self, hex_color: str) -> None:
        self._plate_color = (hex_color or "#00FF00").upper()
        self.plate_color_btn.setText(self._plate_color)
        self.plate_color_btn.setStyleSheet(f"background-color: {self._plate_color};")

    def _pick_plate_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._plate_color), self, "Chroma plate color")
        if color.isValid():
            self._set_plate_color(color.name())

    # -- named configurations ---------------------------------------------

    def _reload_names(self, select: Optional[str] = None) -> None:
        self.config_combo.blockSignals(True)
        self.config_combo.clear()
        self.config_combo.addItems(self._store.list_names())
        self.config_combo.blockSignals(False)
        index = self.config_combo.findText(select) if select else -1
        self.config_combo.setCurrentIndex(index if index >= 0 else 0)
        self._on_config_selected(self.config_combo.currentText())

    def _on_config_selected(self, name: str) -> None:
        self.delete_btn.setEnabled(bool(name) and name != DEFAULT_NAME)

    def _on_load(self) -> None:
        name = self.config_combo.currentText()
        try:
            loaded = self._store.get(name)
        except KeyError:
            show_error(self, "Generation Settings", f"Configuration not found: {name}")
            self._reload_names()
            return
        self.set_settings(loaded)
        logger.info("Loaded sprite generation configuration %r", name)

    def _on_save_as(self) -> None:
        name, ok = QInputDialog.getText(self, "Save configuration", "Configuration name:",
                                        text=self.config_combo.currentText())
        if not ok or not name.strip():
            return
        name = name.strip()
        try:
            self._store.save(name, self.settings())
        except (OSError, ValueError) as exc:
            show_error(self, "Generation Settings", f"Could not save configuration: {exc}",
                       exception=exc)
            return
        self._reload_names(select=name)

    def _on_delete(self) -> None:
        name = self.config_combo.currentText()
        if name == DEFAULT_NAME:
            show_error(self, "Generation Settings", 'The "Default" configuration cannot be deleted.')
            return
        reply = QMessageBox.question(self, "Delete configuration", f'Delete "{name}"?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            self._store.delete(name)
        except (KeyError, ValueError, OSError) as exc:
            show_error(self, "Generation Settings", f"Could not delete configuration: {exc}",
                       exception=exc)
            return
        self._reload_names(select=DEFAULT_NAME)

    # -- cleanup -----------------------------------------------------------

    def on_dialog_close(self) -> None:
        settings = sprite_settings()
        settings.setValue(GEOMETRY_KEY, self.saveGeometry())
        settings.sync()
```

- [x] **Step 4: Run — expect pass**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m py_compile /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/generation_settings_dialog.py
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_generation_settings_dialog.py -v
```
Expected: 12 passed.

- [x] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/generation_settings_dialog.py tests/sprite/gui/test_generation_settings_dialog.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite-gui): GenerationSettingsDialog with named configs and cost preview"
```

---

### Task 6: `ActionCardsPanel` (`gui/sprite/action_cards_panel.py`)

**Files:**
- Create: `gui/sprite/action_cards_panel.py`
- Create: `tests/sprite/gui/test_action_cards_panel.py`
- Reference: design §4.2 (`generate_action_cards`, `ActionCardDraft`, `GENRE_CHECKLISTS`, `suggest_clip_duration`), §2 `ActionCard`; `core/llm_models.py:63-75` (`resolve_model(provider, "chat")`), `:200-218` (`get_all_provider_ids`, `get_provider_display_name`)

**Interfaces:**
- Consumes: `core.sprite.generation.action_cards.generate_action_cards(brief, genre, *, provider, model, api_key, plate_color, completion_fn=None, log) -> List[ActionCardDraft]`, `ActionCardDraft(name, prompt, duration_s, loop, target_frames, fps)`, `GENRE_CHECKLISTS: Dict[str, List[str]]`, `core.sprite.timing.suggest_clip_duration(target_frames, fps, provider, model) -> int`, `core.sprite.project.ActionCard`, `core.llm_models.resolve_model / get_all_provider_ids / get_provider_display_name`, `gui.sprite.prefs.get_pref / set_pref / LLM_PROVIDER_KEY`.
- Produces: `gui.sprite.action_cards_panel.ActionCardsPanel(WorkerHost, QGroupBox)` — `__init__(self, config, parent=None)`; Signals `renderRequested(list)` (action ids), `refineRequested(str, str)` (action id, instruction), `cardsChanged()`, `actionSelected(str)` (selected card id, `""` when none — 5b/6 consume it), `logMessage(str, str)`; methods `add_card_action(label: str, callback: Callable[[ActionCard], None]) -> None` (adds one button to every card row, existing and future; the button calls `callback(card)`; attribute `extra_row_actions: List[Tuple[str, Callable]]`), `set_project(project)`, `refresh()` (rebuild rows), `refresh_status()` (status column + row buttons only), `refresh_hint()`, `generate_cards()`, `add_card() -> ActionCard`, `remove_selected() -> int`, `selected_ids() -> List[str]`, `request_render(action_id)`, `request_rerender(action_id)`, `request_refine(action_id)`, `card_by_id(action_id) -> Optional[ActionCard]`, `llm_provider() -> str`. Column constants `COL_NAME … COL_ACTIONS`, `NAME_RE`.
- Widget names: `brief_edit`, `genre_combo`, `llm_combo`, `generate_btn`, `add_btn`, `remove_btn`, `render_all_btn`, `table`, `hint_label`, `progress`, `status_label`. Ctrl+Enter inside the panel = Generate cards (`self._primary`, `Qt.WidgetWithChildrenShortcut`).

- [x] **Step 1: Failing tests** — create `tests/sprite/gui/test_action_cards_panel.py`:

```python
# tests/sprite/gui/test_action_cards_panel.py
"""ActionCardsPanel: brief → cards, editable table, per-card render/refine."""
from PySide6.QtCore import Qt

import gui.sprite.action_cards_panel as acp
from core.sprite.generation.action_cards import ActionCardDraft
from gui.sprite.action_cards_panel import (
    COL_ACTIONS, COL_FPS, COL_LOOP, COL_NAME, COL_SECONDS, COL_STATUS, ActionCardsPanel,
)


def _panel(fake_config, fake_project):
    panel = ActionCardsPanel(fake_config)
    panel.set_project(fake_project)
    return panel


def test_genres_come_from_the_llm_contract(qapp, fake_config):
    panel = ActionCardsPanel(fake_config)
    genres = [panel.genre_combo.itemText(i) for i in range(panel.genre_combo.count())]
    assert "sidescroller" in genres and genres == sorted(genres)
    assert not panel.generate_btn.isEnabled()  # no project yet


def test_set_project_fills_rows_and_brief(qapp, fake_config, fake_project):
    fake_project.brief = "a knight"
    panel = _panel(fake_config, fake_project)
    assert panel.table.rowCount() == 2
    assert panel.table.item(0, COL_NAME).text() == "idle"
    assert panel.table.item(1, COL_STATUS).text() == "draft"
    assert panel.brief_edit.text() == "a knight"
    assert panel.generate_btn.isEnabled()


def test_editing_cells_writes_back_to_cards(qapp, fake_config, fake_project):
    panel = _panel(fake_config, fake_project)
    changed = []
    panel.cardsChanged.connect(lambda: changed.append(1))
    panel.table.item(0, COL_SECONDS).setText("6")
    panel.table.item(0, COL_FPS).setText("24")
    panel.table.item(0, COL_LOOP).setCheckState(Qt.Unchecked)
    panel.table.item(0, COL_NAME).setText("idle_stand")
    card = fake_project.actions[0]
    assert card.duration_s == 6 and card.fps == 24 and card.loop is False
    assert card.name == "idle_stand"
    assert len(changed) == 4


def test_invalid_edits_are_reverted_and_logged(qapp, fake_config, fake_project):
    panel = _panel(fake_config, fake_project)
    lines = []
    panel.logMessage.connect(lambda m, level: lines.append((level, m)))
    panel.table.item(0, COL_SECONDS).setText("forty")
    assert fake_project.actions[0].duration_s == 8
    assert panel.table.item(0, COL_SECONDS).text() == "8"
    panel.table.item(1, COL_NAME).setText("idle")  # duplicate of row 0
    assert fake_project.actions[1].name == "walk"
    panel.table.item(1, COL_NAME).setText("Bad Name")  # not snake_case
    assert fake_project.actions[1].name == "walk"
    assert [level for level, _ in lines].count("WARNING") == 3


def test_add_and_remove_cards(qapp, fake_config, fake_project):
    panel = _panel(fake_config, fake_project)
    card = panel.add_card()
    assert card in fake_project.actions and panel.table.rowCount() == 3
    assert card.name not in ("idle", "walk")
    panel.table.selectRow(2)
    assert panel.remove_selected() == 1
    assert card not in fake_project.actions and panel.table.rowCount() == 2


def test_render_requests_emit_ids(qapp, fake_config, fake_project):
    panel = _panel(fake_config, fake_project)
    got = []
    panel.renderRequested.connect(lambda ids: got.append(list(ids)))
    panel.request_render("a1")
    fake_project.actions[1].status = "rendered"
    panel.request_rerender("a2")
    assert got == [["a1"], ["a2"]]
    assert fake_project.actions[1].status == "draft"  # re-render resets the card
    panel.render_all_btn.click()
    assert got[-1] == ["a1", "a2"]


def test_refine_asks_for_instruction(qapp, fake_config, fake_project, monkeypatch):
    panel = _panel(fake_config, fake_project)
    got = []
    panel.refineRequested.connect(lambda cid, text: got.append((cid, text)))
    monkeypatch.setattr(acp.QInputDialog, "getMultiLineText",
                        staticmethod(lambda *a, **k: ("make the cape swing", True)))
    panel.request_refine("a1")
    assert got == [("a1", "make the cape swing")]
    monkeypatch.setattr(acp.QInputDialog, "getMultiLineText",
                        staticmethod(lambda *a, **k: ("", False)))
    panel.request_refine("a1")
    assert len(got) == 1


def test_generate_cards_appends_unique_names(qapp, fake_config, fake_project, monkeypatch,
                                             wait_for_worker):
    captured = {}

    def fake_generate(brief, genre, *, provider, model, api_key, plate_color,
                      completion_fn=None, log=None):
        captured.update(brief=brief, genre=genre, provider=provider, model=model,
                        api_key=api_key, plate_color=plate_color)
        log("contract ok")
        return [ActionCardDraft(name="idle", prompt="stands still", duration_s=4, loop=True,
                                target_frames=6, fps=12),
                ActionCardDraft(name="jump", prompt="jumps", duration_s=6, loop=False,
                                target_frames=10, fps=12)]

    monkeypatch.setattr(acp, "generate_action_cards", fake_generate)
    monkeypatch.setattr(acp, "resolve_model", lambda provider, family: "chat-model")
    panel = _panel(fake_config, fake_project)
    panel.brief_edit.setText("a brave knight")
    panel.genre_combo.setCurrentText("sidescroller")
    changed = []
    panel.cardsChanged.connect(lambda: changed.append(1))
    panel.generate_cards()
    wait_for_worker(panel)
    names = [card.name for card in fake_project.actions]
    assert names == ["idle", "walk", "idle_2", "jump"]
    assert fake_project.brief == "a brave knight" and fake_project.genre_preset == "sidescroller"
    assert captured["model"] == "chat-model" and captured["api_key"] == "test-key"
    assert captured["plate_color"] == "#00FF00"
    assert panel.table.rowCount() == 4 and changed


def test_generate_cards_requires_brief(qapp, fake_config, fake_project, monkeypatch):
    seen = []
    monkeypatch.setattr(acp, "show_warning",
                        lambda parent, title, message, log_level=None: seen.append(message))
    panel = _panel(fake_config, fake_project)
    panel.brief_edit.setText("   ")
    panel.generate_cards()
    assert seen and panel._worker is None


def test_hint_uses_timing_helper(qapp, fake_config, fake_project, monkeypatch):
    monkeypatch.setattr(acp, "suggest_clip_duration",
                        lambda frames, fps, provider, model: 8)
    panel = _panel(fake_config, fake_project)
    panel.table.selectRow(1)
    panel.refresh_hint()
    assert "8 s" in panel.hint_label.text() and "walk" in panel.hint_label.text()


def test_llm_provider_choice_is_sticky(qapp, fake_config, fake_project):
    from gui.sprite.prefs import LLM_PROVIDER_KEY, sprite_settings
    panel = _panel(fake_config, fake_project)
    assert panel.llm_combo.count() > 0
    panel.llm_combo.setCurrentIndex(panel.llm_combo.count() - 1)
    panel._on_llm_changed(panel.llm_combo.currentIndex())  # explicit: a 1-item combo emits nothing
    chosen = panel.llm_provider()
    assert sprite_settings().value(LLM_PROVIDER_KEY) == chosen
    other = ActionCardsPanel(fake_config)
    assert other.llm_provider() == chosen


def test_selection_emits_action_id(qapp, fake_config, fake_project):
    panel = _panel(fake_config, fake_project)
    got = []
    panel.actionSelected.connect(lambda cid: got.append(cid))
    panel.table.selectRow(1)
    assert got[-1] == "a2"
    panel.table.clearSelection()
    assert got[-1] == ""


def test_add_card_action_adds_button_to_every_row(qapp, fake_config, fake_project):
    from PySide6.QtWidgets import QPushButton
    panel = _panel(fake_config, fake_project)
    clicked = []
    panel.add_card_action("Render (image)", lambda card: clicked.append(card.id))
    for row in range(panel.table.rowCount()):
        buttons = panel.table.cellWidget(row, COL_ACTIONS).findChildren(QPushButton)
        assert [b.text() for b in buttons] == ["Render", "Re-render", "Refine…", "Render (image)"]
    panel.table.cellWidget(1, COL_ACTIONS).findChildren(QPushButton)[-1].click()
    assert clicked == ["a2"]
    panel.add_card()  # future rows get the button too
    last = panel.table.rowCount() - 1
    last_buttons = panel.table.cellWidget(last, COL_ACTIONS).findChildren(QPushButton)
    assert last_buttons[-1].text() == "Render (image)"
```

- [x] **Step 2: Run — expect failure**

```bash
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_action_cards_panel.py -v
```
Expected: `ModuleNotFoundError: No module named 'gui.sprite.action_cards_panel'`.

- [x] **Step 3: Implement** — create `gui/sprite/action_cards_panel.py`:

```python
"""Action cards panel: brief + genre → LLM action cards → editable table.

Per-card buttons emit ``renderRequested([id])`` / ``refineRequested(id, text)``;
the tab routes them to the queue panel. The LLM call runs in a SpriteWorker
with full request/response logging inside ``generate_action_cards``.
"""
from __future__ import annotations

import logging
import re
from typing import Callable, List, Optional, Tuple
from uuid import uuid4

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QLineEdit, QProgressBar, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from core.llm_models import get_all_provider_ids, get_provider_display_name, resolve_model
from core.sprite.generation.action_cards import GENRE_CHECKLISTS, generate_action_cards
from core.sprite.project import ActionCard
from core.sprite.timing import suggest_clip_duration
from gui.common.dialog_conventions import bind_primary_action
from gui.dialog_utils import show_error, show_warning
from gui.sprite.prefs import LLM_PROVIDER_KEY, get_pref, set_pref
from gui.sprite.workers import WorkerHost

logger = logging.getLogger(__name__)

COL_NAME, COL_PROMPT, COL_SECONDS, COL_LOOP, COL_FRAMES, COL_FPS, COL_STATUS, COL_ACTIONS = range(8)
HEADERS = ("Name", "Prompt", "Seconds", "Loop", "Frames", "FPS", "Status", "")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
INT_LIMITS = {COL_SECONDS: (1, 15), COL_FRAMES: (1, 64), COL_FPS: (1, 60)}
RERENDER_STATES = ("rendered", "processed", "failed")


class ActionCardsPanel(WorkerHost, QGroupBox):
    renderRequested = Signal(list)       # [action_id, ...]
    refineRequested = Signal(str, str)   # action_id, instruction
    cardsChanged = Signal()
    actionSelected = Signal(str)         # selected card id, "" when nothing is selected
    logMessage = Signal(str, str)

    def __init__(self, config, parent=None):
        super().__init__("Action cards", parent)
        self.config = config
        self.project = None
        self._loading = False
        # (label, callback) pairs rendered as extra buttons on every row (5b/6 hooks)
        self.extra_row_actions: List[Tuple[str, Callable[[ActionCard], None]]] = []
        self._build()
        self._primary = bind_primary_action(self, self.generate_cards,
                                            context=Qt.WidgetWithChildrenShortcut)
        self._sync_enabled()

    # -- build -------------------------------------------------------------

    def _build(self) -> None:
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("Brief:"))
        self.brief_edit = QLineEdit()
        self.brief_edit.setPlaceholderText("e.g. a small armored knight with a red cape")
        top.addWidget(self.brief_edit, 1)
        self.genre_combo = QComboBox()
        self.genre_combo.addItems(sorted(GENRE_CHECKLISTS))
        top.addWidget(self.genre_combo)
        self.llm_combo = QComboBox()
        for provider_id in get_all_provider_ids():
            self.llm_combo.addItem(get_provider_display_name(provider_id), provider_id)
        saved = get_pref(LLM_PROVIDER_KEY, "google")
        index = self.llm_combo.findData(saved)
        self.llm_combo.setCurrentIndex(index if index >= 0 else 0)
        self.llm_combo.currentIndexChanged.connect(self._on_llm_changed)
        top.addWidget(self.llm_combo)
        self.generate_btn = QPushButton("Generate cards")
        self.generate_btn.setToolTip("Ctrl+Enter")
        self.generate_btn.clicked.connect(self.generate_cards)
        top.addWidget(self.generate_btn)
        root.addLayout(top)

        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_PROMPT, QHeaderView.Stretch)
        for column in (COL_NAME, COL_SECONDS, COL_LOOP, COL_FRAMES, COL_FPS, COL_STATUS, COL_ACTIONS):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        root.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.add_btn = QPushButton("Add card")
        self.add_btn.clicked.connect(self.add_card)
        self.remove_btn = QPushButton("Remove selected")
        self.remove_btn.clicked.connect(self.remove_selected)
        self.render_all_btn = QPushButton("Render all")
        self.render_all_btn.clicked.connect(self._render_all)
        for button in (self.add_btn, self.remove_btn, self.render_all_btn):
            bottom.addWidget(button)
        bottom.addStretch(1)
        self.hint_label = QLabel("")
        bottom.addWidget(self.hint_label)
        root.addLayout(bottom)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)
        self.status_label = QLabel("")
        root.addWidget(self.status_label)

    def _sync_enabled(self) -> None:
        has_project = self.project is not None
        busy = self.is_busy()
        for widget in (self.generate_btn, self.add_btn, self.remove_btn, self.render_all_btn,
                       self.brief_edit, self.genre_combo, self.table):
            widget.setEnabled(has_project and not busy)
        if hasattr(self, "_primary"):
            self._primary.set_enabled(has_project and not busy)

    # -- project / cards ---------------------------------------------------

    def _cards(self) -> List[ActionCard]:
        return list(self.project.actions) if self.project is not None else []

    def card_by_id(self, action_id: str) -> Optional[ActionCard]:
        for card in self._cards():
            if card.id == action_id:
                return card
        return None

    def set_project(self, project) -> None:
        self.project = project
        if project is not None:
            self.brief_edit.setText(getattr(project, "brief", "") or "")
            genre = getattr(project, "genre_preset", "") or ""
            if self.genre_combo.findText(genre) >= 0:
                self.genre_combo.setCurrentText(genre)
        self.refresh()
        self._sync_enabled()

    def refresh(self) -> None:
        self._loading = True
        try:
            self.table.setRowCount(0)
            for card in self._cards():
                row = self.table.rowCount()
                self.table.insertRow(row)
                self._set_text(row, COL_NAME, card.name, card.id)
                self._set_text(row, COL_PROMPT, card.prompt, card.id)
                self._set_text(row, COL_SECONDS, str(card.duration_s), card.id)
                loop_item = QTableWidgetItem()
                loop_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                loop_item.setCheckState(Qt.Checked if card.loop else Qt.Unchecked)
                loop_item.setData(Qt.UserRole, card.id)
                self.table.setItem(row, COL_LOOP, loop_item)
                self._set_text(row, COL_FRAMES, str(card.target_frames), card.id)
                self._set_text(row, COL_FPS, str(card.fps), card.id)
                status = self._set_text(row, COL_STATUS, card.status, card.id)
                status.setFlags(status.flags() & ~Qt.ItemIsEditable)
                self.table.setCellWidget(row, COL_ACTIONS, self._row_buttons(card))
        finally:
            self._loading = False
        self.refresh_hint()

    def refresh_status(self) -> None:
        """Update the status column and row buttons without rebuilding the rows."""
        self._loading = True
        try:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, COL_NAME)
                card = self.card_by_id(item.data(Qt.UserRole)) if item else None
                if card is None:
                    continue
                self.table.item(row, COL_STATUS).setText(card.status)
                self.table.setCellWidget(row, COL_ACTIONS, self._row_buttons(card))
        finally:
            self._loading = False

    def _set_text(self, row: int, column: int, text: str, action_id: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setData(Qt.UserRole, action_id)
        self.table.setItem(row, column, item)
        return item

    def _row_buttons(self, card: ActionCard) -> QWidget:
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        render = QPushButton("Render")
        render.clicked.connect(lambda _checked=False, cid=card.id: self.request_render(cid))
        rerender = QPushButton("Re-render")
        rerender.setEnabled(card.status in RERENDER_STATES)
        rerender.clicked.connect(lambda _checked=False, cid=card.id: self.request_rerender(cid))
        refine = QPushButton("Refine…")
        refine.setEnabled(card.clip is not None and self._provider() == "omni")
        refine.setToolTip("Conversational refine (Omni only)")
        refine.clicked.connect(lambda _checked=False, cid=card.id: self.request_refine(cid))
        for button in (render, rerender, refine):
            layout.addWidget(button)
        for label, callback in self.extra_row_actions:
            extra = QPushButton(label)
            extra.clicked.connect(
                lambda _checked=False, cid=card.id, cb=callback: self._run_card_action(cid, cb))
            layout.addWidget(extra)
        return box

    def add_card_action(self, label: str, callback: Callable[[ActionCard], None]) -> None:
        """Add a button to every card row (existing and future); it calls ``callback(card)``."""
        self.extra_row_actions.append((label, callback))
        self.refresh_status()

    def _run_card_action(self, action_id: str, callback: Callable[[ActionCard], None]) -> None:
        card = self.card_by_id(action_id)
        if card is not None:
            callback(card)

    def _provider(self) -> str:
        generation = getattr(self.project, "generation", None)
        return getattr(generation, "provider", "omni") if generation is not None else "omni"

    def _model(self) -> str:
        generation = getattr(self.project, "generation", None)
        return getattr(generation, "model", "") if generation is not None else ""

    def _unique_name(self, base: str) -> str:
        base = base if NAME_RE.match(base or "") else "action"
        taken = {card.name for card in self._cards()}
        if base not in taken:
            return base
        index = 2
        while f"{base}_{index}" in taken:
            index += 1
        return f"{base}_{index}"

    # -- editing -----------------------------------------------------------

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading:
            return
        card = self.card_by_id(item.data(Qt.UserRole))
        if card is None:
            return
        column = item.column()
        text = item.text().strip()
        if column == COL_NAME:
            others = {c.name for c in self._cards() if c is not card}
            if not NAME_RE.match(text) or text in others:
                self._revert(item, card.name, f"Card name must be unique snake_case: {text!r}")
                return
            card.name = text
        elif column == COL_PROMPT:
            card.prompt = text
        elif column in INT_LIMITS:
            low, high = INT_LIMITS[column]
            current = {COL_SECONDS: card.duration_s, COL_FRAMES: card.target_frames,
                       COL_FPS: card.fps}[column]
            try:
                value = int(text)
                if not low <= value <= high:
                    raise ValueError(text)
            except ValueError:
                self._revert(item, str(current), f"Value must be an integer {low}-{high}: {text!r}")
                return
            if column == COL_SECONDS:
                card.duration_s = value
            elif column == COL_FRAMES:
                card.target_frames = value
            else:
                card.fps = value
        elif column == COL_LOOP:
            card.loop = item.checkState() == Qt.Checked
        else:
            return
        self.cardsChanged.emit()
        self.refresh_hint()

    def _revert(self, item: QTableWidgetItem, text: str, message: str) -> None:
        logger.warning(message)
        self.logMessage.emit(message, "WARNING")
        self._loading = True
        try:
            item.setText(text)
        finally:
            self._loading = False

    # -- public actions ----------------------------------------------------

    def add_card(self) -> Optional[ActionCard]:
        if self.project is None:
            return None
        card = ActionCard(id=uuid4().hex, name=self._unique_name("action"), prompt="")
        self.project.actions.append(card)
        self.refresh()
        self.cardsChanged.emit()
        return card

    def selected_ids(self) -> List[str]:
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        ids = []
        for row in rows:
            item = self.table.item(row, COL_NAME)
            if item is not None:
                ids.append(item.data(Qt.UserRole))
        return ids

    def remove_selected(self) -> int:
        ids = set(self.selected_ids())
        if not ids or self.project is None:
            return 0
        before = len(self.project.actions)
        self.project.actions[:] = [c for c in self.project.actions if c.id not in ids]
        removed = before - len(self.project.actions)
        self.refresh()
        self.cardsChanged.emit()
        self.logMessage.emit(f"Removed {removed} card(s)", "INFO")
        return removed

    def request_render(self, action_id: str) -> None:
        if self.card_by_id(action_id) is None:
            return
        self.renderRequested.emit([action_id])

    def request_rerender(self, action_id: str) -> None:
        card = self.card_by_id(action_id)
        if card is None:
            return
        card.status = "draft"
        card.error = None
        self.refresh_status()
        self.renderRequested.emit([action_id])

    def request_refine(self, action_id: str) -> None:
        card = self.card_by_id(action_id)
        if card is None:
            return
        text, ok = QInputDialog.getMultiLineText(
            self, "Refine clip", f"Instruction for the model ({card.name}):")
        if not ok or not text.strip():
            return
        self.refineRequested.emit(action_id, text.strip())

    def _render_all(self) -> None:
        ids = [card.id for card in self._cards() if card.status in ("draft", "failed")]
        if not ids:
            self.logMessage.emit("No draft or failed cards to render.", "WARNING")
            return
        self.renderRequested.emit(ids)

    def llm_provider(self) -> str:
        data = self.llm_combo.currentData()
        return str(data) if data else "google"

    def _on_llm_changed(self, _index: int) -> None:
        set_pref(LLM_PROVIDER_KEY, self.llm_provider())

    def refresh_hint(self) -> None:
        ids = self.selected_ids()
        card = self.card_by_id(ids[0]) if ids else None
        if card is None:
            self.hint_label.setText("")
            return
        try:
            seconds = suggest_clip_duration(card.target_frames, card.fps,
                                            self._provider(), self._model())
            self.hint_label.setText(
                f"{card.name}: {card.target_frames} frames @ {card.fps} fps → "
                f"suggested clip {seconds} s on {self._provider()}")
        except Exception as exc:  # noqa: BLE001 - hint only
            logger.warning("Timing hint failed: %s", exc)
            self.hint_label.setText("")

    def _on_selection_changed(self) -> None:
        ids = self.selected_ids()
        self.actionSelected.emit(ids[0] if ids else "")
        self.refresh_hint()

    # -- LLM generation ----------------------------------------------------

    def generate_cards(self) -> None:
        if self.project is None:
            show_error(self, "Sprite", "Open a sprite project before generating cards.")
            return
        brief = self.brief_edit.text().strip()
        if not brief:
            show_warning(self, "Sprite", "Write a one-line brief for the character first.")
            return
        if self.is_busy():
            self.logMessage.emit("Card generation is already running.", "WARNING")
            return
        genre = self.genre_combo.currentText()
        provider = self.llm_provider()
        model = resolve_model(provider, "chat")
        api_key = self.config.get_api_key(provider)
        plate_color = getattr(self.project, "plate_color", "#00FF00")
        self.project.brief = brief
        self.project.genre_preset = genre

        def job(progress, token):
            progress("cards", 0, 0, f"Asking {provider}/{model} for {genre} action cards")
            drafts = generate_action_cards(brief, genre, provider=provider, model=model,
                                           api_key=api_key, plate_color=plate_color,
                                           log=lambda m: progress("cards", 0, 0, m))
            token.raise_if_cancelled()
            return list(drafts)

        self.logMessage.emit(f"Generating action cards ({genre}) via {provider}/{model}", "INFO")
        worker = self.start_job(job, label="action cards", on_finished=self._on_cards_done,
                                on_failed=self._on_failed, on_cancelled=self._on_cancelled,
                                on_progress=self._on_progress)
        if worker is not None:
            self.progress.setRange(0, 0)
            self.progress.setVisible(True)
            self._sync_enabled()

    def _on_progress(self, stage: str, done: int, total: int, message: str) -> None:
        self.status_label.setText(f"{stage}: {message}")
        self.logMessage.emit(f"[{stage}] {message}", "INFO")

    def _finish(self) -> None:
        self.progress.setVisible(False)
        self.status_label.setText("")
        self._sync_enabled()

    def _on_cards_done(self, drafts) -> None:
        added = 0
        for draft in drafts:
            card = ActionCard(id=uuid4().hex, name=self._unique_name(draft.name),
                              prompt=draft.prompt, duration_s=int(draft.duration_s),
                              loop=bool(draft.loop), target_frames=int(draft.target_frames),
                              fps=int(draft.fps))
            self.project.actions.append(card)
            added += 1
        self._finish()
        self.refresh()
        self.logMessage.emit(f"Added {added} action card(s)", "SUCCESS")
        self.cardsChanged.emit()

    def _on_failed(self, message: str) -> None:
        self._finish()
        self.logMessage.emit(message, "ERROR")
        show_error(self, "Sprite", message)

    def _on_cancelled(self) -> None:
        self._finish()
        self.logMessage.emit("Card generation cancelled.", "WARNING")
```

- [x] **Step 4: Run — expect pass**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m py_compile /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/action_cards_panel.py
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_action_cards_panel.py -v
```
Expected: 13 passed.

- [x] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/action_cards_panel.py tests/sprite/gui/test_action_cards_panel.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite-gui): ActionCardsPanel with LLM card generation and per-card render"
```

---

### Task 7: `QueuePanel` (`gui/sprite/queue_panel.py`)

**Files:**
- Create: `gui/sprite/queue_panel.py`
- Create: `tests/sprite/gui/test_queue_panel.py`
- Reference: design §4.2 (`ActionQueue`, `refine_action`, `estimate_action`, `estimate_project`), §1.3 (retry policy lives inside the queue; the panel only shows `user_message`), decision 8 (per-action estimate + sheet total; actual cost from the ledger), `core/sprite/pipeline.py` `run_pipeline`

**Interfaces:**
- Consumes: `core.sprite.generation.queue.ActionQueue(project, *, api_key, auth_mode, progress, token, log, max_concurrent=1)` with `enqueue(ids)`, `run() -> Dict[str, ClipRecord | SpriteGenerationError]`; `core.sprite.generation.video_route.refine_action(clip, instruction, out_mp4, *, api_key, log) -> ClipRecord`; `core.sprite.pipeline.run_pipeline(project, action, *, upto, progress, token, force)`; `core.sprite.generation.cost.estimate_action(settings, action) -> Optional[float]`, `estimate_project(project) -> Tuple[Optional[float], int]`; `core.sprite.generation.errors.SpriteGenerationError`.
- Produces: `gui.sprite.queue_panel.QueuePanel(WorkerHost, QGroupBox)` — `__init__(self, config, parent=None)`; Signals `queueFinished(object)` (the `run()` dict), `statusChanged()`, `logMessage(str, str)`; methods `set_project(project)`, `refresh()`, `enqueue(ids: Sequence[str])`, `start(ids: Optional[Sequence[str]] = None)`, `cancel()`, `retry()`, `refine(action_id: str, instruction: str)`, `selected_ids() -> List[str]`; module helper `fmt_usd(value: Optional[float]) -> str` ("unknown" for `None`). Column constants `COL_ACTION, COL_STATUS, COL_ESTIMATE, COL_ACTUAL`.
- Widget names: `table`, `total_label`, `progress`, `status_label`, `start_btn`, `cancel_btn`, `retry_btn`. Ctrl+Enter inside the panel = Start (`self._primary`).

- [x] **Step 1: Failing tests** — create `tests/sprite/gui/test_queue_panel.py`:

```python
# tests/sprite/gui/test_queue_panel.py
"""QueuePanel: drives ActionQueue in a worker; cost labels; cancel/retry/refine."""
import time
import types
from pathlib import Path

import gui.sprite.queue_panel as qp
from core.sprite.pipeline import Cancelled
from gui.sprite.queue_panel import COL_ACTUAL, COL_ESTIMATE, COL_STATUS, QueuePanel, fmt_usd


class _FakeQueue:
    instances = []

    def __init__(self, project, *, api_key, auth_mode, progress, token, log, max_concurrent=1):
        self.project = project
        self.api_key = api_key
        self.auth_mode = auth_mode
        self.progress = progress
        self.token = token
        self.log = log
        self.ids = []
        _FakeQueue.instances.append(self)

    def enqueue(self, ids):
        self.ids.extend(ids)

    def run(self):
        results = {}
        for cid in self.ids:
            self.log(f"rendering {cid}")
            self.progress("render", 1, 1, cid)
            card = next(c for c in self.project.actions if c.id == cid)
            card.status = "rendered"
            card.clip = types.SimpleNamespace(path=Path(f"{cid}.mp4"), actual_usd=0.12,
                                              provider="omni", model="m")
            results[cid] = card.clip
        return results


class _BlockingQueue(_FakeQueue):
    def run(self):
        while not self.token.cancelled:
            time.sleep(0.005)
        raise Cancelled()


def _panel(fake_config, fake_project, monkeypatch, queue_cls=_FakeQueue):
    monkeypatch.setattr(qp, "ActionQueue", queue_cls)
    monkeypatch.setattr(qp, "estimate_action", lambda settings, card: 0.25)
    monkeypatch.setattr(qp, "estimate_project", lambda project: (0.5, 0))
    panel = QueuePanel(fake_config)
    panel.set_project(fake_project)
    return panel


def test_fmt_usd():
    assert fmt_usd(None) == "unknown" and fmt_usd(0.5) == "$0.50"


def test_rows_show_estimates_and_sheet_total(qapp, fake_config, fake_project, monkeypatch):
    panel = _panel(fake_config, fake_project, monkeypatch)
    assert panel.table.rowCount() == 2
    assert panel.table.item(0, COL_ESTIMATE).text() == "$0.25"
    assert panel.table.item(0, COL_ACTUAL).text() == "-"
    assert panel.total_label.text() == "Sheet estimate: $0.50"
    monkeypatch.setattr(qp, "estimate_project", lambda project: (None, 2))
    panel.refresh()
    assert panel.total_label.text() == "Sheet estimate: unknown (2 actions without a verified rate)"


def test_estimator_failure_shows_unknown(qapp, fake_config, fake_project, monkeypatch, caplog):
    def broken(*a, **k):
        raise RuntimeError("no rate")

    panel = _panel(fake_config, fake_project, monkeypatch)
    monkeypatch.setattr(qp, "estimate_action", broken)
    monkeypatch.setattr(qp, "estimate_project", broken)
    with caplog.at_level("WARNING"):
        panel.refresh()
    assert panel.table.item(0, COL_ESTIMATE).text() == "unknown"
    assert "unknown" in panel.total_label.text()


def test_enqueue_marks_cards_queued(qapp, fake_config, fake_project, monkeypatch):
    panel = _panel(fake_config, fake_project, monkeypatch)
    panel.enqueue(["a2"])
    assert fake_project.actions[1].status == "queued"
    assert panel.table.item(1, COL_STATUS).text() == "queued"


def test_start_runs_queue_in_worker_and_reports(qapp, fake_config, fake_project, monkeypatch,
                                                wait_for_worker):
    _FakeQueue.instances.clear()
    panel = _panel(fake_config, fake_project, monkeypatch)
    done, lines = [], []
    panel.queueFinished.connect(lambda r: done.append(r))
    panel.logMessage.connect(lambda m, level: lines.append((level, m)))
    panel.enqueue(["a1"])
    panel.start()
    wait_for_worker(panel)
    queue = _FakeQueue.instances[-1]
    assert queue.ids == ["a1"] and queue.api_key == "test-key" and queue.auth_mode == "api-key"
    assert done and set(done[0]) == {"a1"}
    assert fake_project.actions[0].status == "rendered"
    assert panel.table.item(0, COL_ACTUAL).text() == "$0.12"
    assert any(level == "SUCCESS" for level, _ in lines)
    assert any("rendering a1" in m for _, m in lines)
    assert not panel.progress.isVisible()


def test_start_with_nothing_queued_warns(qapp, fake_config, fake_project, monkeypatch):
    panel = _panel(fake_config, fake_project, monkeypatch)
    lines = []
    panel.logMessage.connect(lambda m, level: lines.append(level))
    panel.start()
    assert "WARNING" in lines and panel._worker is None


def test_start_requires_api_key(qapp, fake_project, monkeypatch):
    seen = []
    monkeypatch.setattr(qp, "show_error",
                        lambda parent, title, message, exception=None: seen.append(message))
    config = types.SimpleNamespace(get_api_key=lambda p: None,
                                   get_auth_mode=lambda p="google": "api-key")
    panel = _panel(config, fake_project, monkeypatch)
    panel.enqueue(["a1"])
    panel.start()
    assert seen and "api key" in seen[0].lower() and panel._worker is None


def test_cancel_stops_queue_without_error_dialog(qapp, fake_config, fake_project, monkeypatch,
                                                 wait_for_worker):
    seen = []
    monkeypatch.setattr(qp, "show_error",
                        lambda parent, title, message, exception=None: seen.append(message))
    panel = _panel(fake_config, fake_project, monkeypatch, queue_cls=_BlockingQueue)
    panel.enqueue(["a1"])
    panel.start()
    assert panel.is_busy()
    panel.cancel()
    wait_for_worker(panel)
    assert seen == []
    assert "cancel" in panel.status_label.text().lower()


def test_retry_requeues_failed_cards(qapp, fake_config, fake_project, monkeypatch):
    panel = _panel(fake_config, fake_project, monkeypatch)
    fake_project.actions[0].status = "failed"
    fake_project.actions[0].error = "boom"
    panel.refresh()
    started = []
    monkeypatch.setattr(panel, "start", lambda ids=None: started.append(list(ids or [])))
    panel.table.selectRow(0)
    panel.retry()
    assert fake_project.actions[0].status == "queued" and fake_project.actions[0].error is None
    assert started == [["a1"]]


def test_queue_errors_are_logged_per_card(qapp, fake_config, fake_project, monkeypatch,
                                          wait_for_worker):
    from core.sprite.generation.errors import SpriteGenerationError

    class _Err(SpriteGenerationError):
        def __init__(self, message):
            Exception.__init__(self, message)
            self.user_message = message
            self.retryable = False

    class _ErrQueue(_FakeQueue):
        def run(self):
            card = self.project.actions[0]
            card.status = "failed"
            card.error = "safety refusal"
            return {"a1": _Err("safety refusal")}

    panel = _panel(fake_config, fake_project, monkeypatch, queue_cls=_ErrQueue)
    lines = []
    panel.logMessage.connect(lambda m, level: lines.append((level, m)))
    panel.enqueue(["a1"])
    panel.start()
    wait_for_worker(panel)
    assert any(level == "ERROR" and "safety refusal" in m for level, m in lines)
    assert panel.table.item(0, COL_STATUS).text() == "failed"


def test_refine_replaces_clip_and_reruns_pipeline(qapp, fake_config, fake_project, monkeypatch,
                                                  wait_for_worker):
    calls = {}
    fake_project.actions[0].clip = types.SimpleNamespace(path=Path("a1.mp4"), actual_usd=0.1)
    new_clip = types.SimpleNamespace(path=Path("a1.r1.mp4"), actual_usd=0.2)

    def fake_refine(clip, instruction, out_mp4, *, api_key, log):
        calls.update(instruction=instruction, out=out_mp4, api_key=api_key)
        return new_clip

    def fake_pipeline(project, action, *, upto, progress, token, force):
        calls.update(upto=upto, force=force, action=action.id)
        return {}

    monkeypatch.setattr(qp, "refine_action", fake_refine)
    monkeypatch.setattr(qp, "run_pipeline", fake_pipeline)
    panel = _panel(fake_config, fake_project, monkeypatch)
    changed = []
    panel.statusChanged.connect(lambda: changed.append(1))
    panel.refine("a1", "make the cape swing")
    wait_for_worker(panel)
    assert calls["instruction"] == "make the cape swing"
    assert calls["out"] == fake_project.project_dir / "clips" / "a1.r1.mp4"
    assert calls["upto"] == "stabilize" and calls["force"] is True and calls["action"] == "a1"
    assert fake_project.actions[0].clip is new_clip
    assert fake_project.actions[0].status == "rendered"
    assert changed
```

- [x] **Step 2: Run — expect failure**

```bash
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_queue_panel.py -v
```
Expected: `ModuleNotFoundError: No module named 'gui.sprite.queue_panel'`.

- [x] **Step 3: Implement** — create `gui/sprite/queue_panel.py`:

```python
"""Queue panel: one row per action card, cost estimate + actual, Start/Cancel/Retry.

The panel runs ``ActionQueue`` inside a SpriteWorker; the queue owns retries
with backoff (design §1.3) and writes ``CostEntry`` rows. The panel only
reflects card status and logs ``user_message`` for failures.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QProgressBar,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from core.sprite.generation.cost import estimate_action, estimate_project
from core.sprite.generation.errors import SpriteGenerationError
from core.sprite.generation.queue import ActionQueue
from core.sprite.generation.video_route import refine_action
from core.sprite.pipeline import run_pipeline
from gui.common.dialog_conventions import bind_primary_action
from gui.dialog_utils import show_error, show_warning
from gui.sprite.workers import WorkerHost

logger = logging.getLogger(__name__)

COL_ACTION, COL_STATUS, COL_ESTIMATE, COL_ACTUAL = range(4)
HEADERS = ("Action", "Status", "Est. cost", "Actual cost")


def fmt_usd(value: Optional[float]) -> str:
    return "unknown" if value is None else f"${value:.2f}"


class QueuePanel(WorkerHost, QGroupBox):
    queueFinished = Signal(object)   # Dict[action_id, ClipRecord | SpriteGenerationError]
    statusChanged = Signal()
    logMessage = Signal(str, str)

    def __init__(self, config, parent=None):
        super().__init__("Render queue", parent)
        self.config = config
        self.project = None
        self._build()
        self._primary = bind_primary_action(self, self.start, context=Qt.WidgetWithChildrenShortcut)
        self._set_running(False)

    # -- build -------------------------------------------------------------

    def _build(self) -> None:
        root = QVBoxLayout(self)
        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_ACTION, QHeaderView.Stretch)
        for column in (COL_STATUS, COL_ESTIMATE, COL_ACTUAL):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        root.addWidget(self.table, 1)

        self.total_label = QLabel("Sheet estimate: unknown")
        root.addWidget(self.total_label)

        row = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.setToolTip("Render every queued card (Ctrl+Enter)")
        self.start_btn.clicked.connect(self.start)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel)
        self.retry_btn = QPushButton("Retry selected")
        self.retry_btn.clicked.connect(self.retry)
        for button in (self.start_btn, self.cancel_btn, self.retry_btn):
            row.addWidget(button)
        row.addStretch(1)
        root.addLayout(row)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)
        self.status_label = QLabel("")
        root.addWidget(self.status_label)

    def _set_running(self, running: bool) -> None:
        has_project = self.project is not None
        self.start_btn.setEnabled(has_project and not running)
        self.retry_btn.setEnabled(has_project and not running)
        self.cancel_btn.setEnabled(running)
        self.progress.setVisible(running)
        if running:
            self.progress.setRange(0, 0)
        if hasattr(self, "_primary"):
            self._primary.set_enabled(has_project and not running)

    # -- project / rows ----------------------------------------------------

    def _cards(self) -> list:
        return list(self.project.actions) if self.project is not None else []

    def _card(self, action_id: str):
        for card in self._cards():
            if card.id == action_id:
                return card
        return None

    def set_project(self, project) -> None:
        self.project = project
        self.refresh()
        self._set_running(self.is_busy())

    def _estimate(self, card) -> Optional[float]:
        try:
            return estimate_action(self.project.generation, card)
        except Exception as exc:  # noqa: BLE001 - label only, never blocks rendering
            logger.warning("Cost estimate failed for %s: %s", card.name, exc)
            return None

    def refresh(self) -> None:
        self.table.setRowCount(0)
        for card in self._cards():
            row = self.table.rowCount()
            self.table.insertRow(row)
            actual = getattr(card.clip, "actual_usd", None) if card.clip is not None else None
            values = (card.name, card.status, fmt_usd(self._estimate(card)),
                      "-" if actual is None else fmt_usd(actual))
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setData(Qt.UserRole, card.id)
                if column == COL_STATUS and card.error:
                    item.setToolTip(str(card.error))
                self.table.setItem(row, column, item)
        self._refresh_total()

    def _refresh_total(self) -> None:
        if self.project is None:
            self.total_label.setText("Sheet estimate: unknown")
            return
        try:
            usd, unknown = estimate_project(self.project)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Sheet estimate failed: %s", exc)
            usd, unknown = None, len(self._cards())
        if usd is None:
            suffix = f" ({unknown} actions without a verified rate)" if unknown else ""
            self.total_label.setText(f"Sheet estimate: unknown{suffix}")
        elif unknown:
            self.total_label.setText(f"Sheet estimate: {fmt_usd(usd)} + {unknown} unknown")
        else:
            self.total_label.setText(f"Sheet estimate: {fmt_usd(usd)}")

    def selected_ids(self) -> List[str]:
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        return [self.table.item(row, COL_ACTION).data(Qt.UserRole) for row in rows
                if self.table.item(row, COL_ACTION) is not None]

    # -- queue control -----------------------------------------------------

    def enqueue(self, ids: Sequence[str]) -> None:
        for action_id in ids:
            card = self._card(action_id)
            if card is not None:
                card.status = "queued"
                card.error = None
        self.refresh()
        self.statusChanged.emit()

    def _google_credentials(self) -> Optional[dict]:
        api_key = self.config.get_api_key("google")
        if not api_key:
            show_error(self, "Sprite queue", "No Google API key is configured. Add one in Settings.")
            return None
        return {"api_key": api_key, "auth_mode": self.config.get_auth_mode("google")}

    def start(self, ids: Optional[Sequence[str]] = None) -> None:
        if self.project is None:
            show_warning(self, "Sprite queue", "Open a sprite project first.")
            return
        if self.is_busy():
            self.logMessage.emit("The queue is already running.", "WARNING")
            return
        ids = [i for i in (ids or []) if self._card(i) is not None] or \
              [card.id for card in self._cards() if card.status == "queued"]
        if not ids:
            self.logMessage.emit("Nothing queued — press Render on a card first.", "WARNING")
            return
        credentials = self._google_credentials()
        if credentials is None:
            return
        project = self.project
        for action_id in ids:
            self._card(action_id).status = "queued"

        def job(progress, token):
            queue = ActionQueue(project, api_key=credentials["api_key"],
                                auth_mode=credentials["auth_mode"], progress=progress,
                                token=token, log=lambda m: progress("queue", 0, 0, m))
            queue.enqueue(ids)
            return queue.run()

        names = ", ".join(self._card(i).name for i in ids)
        self.logMessage.emit(f"Rendering {len(ids)} card(s): {names}", "INFO")
        worker = self.start_job(job, label="render queue", on_finished=self._on_queue_done,
                                on_failed=self._on_failed, on_cancelled=self._on_cancelled,
                                on_progress=self._on_progress)
        if worker is not None:
            self.refresh()
            self._set_running(True)

    def cancel(self) -> None:
        if self.is_busy():
            self.logMessage.emit("Cancelling the queue… (a running provider job keeps its "
                                 "operation id for recovery)", "WARNING")
            self.cancel_running()

    def retry(self) -> None:
        ids = [i for i in self.selected_ids() if getattr(self._card(i), "status", "") == "failed"]
        if not ids:
            self.logMessage.emit("Select a failed card to retry.", "WARNING")
            return
        self.enqueue(ids)
        self.start(ids)

    def refine(self, action_id: str, instruction: str) -> None:
        card = self._card(action_id)
        if card is None or self.project is None:
            return
        if card.clip is None:
            show_warning(self, "Sprite queue", f"Render {card.name} before refining it.")
            return
        if self.is_busy():
            self.logMessage.emit("The queue is already running.", "WARNING")
            return
        credentials = self._google_credentials()
        if credentials is None:
            return
        clips_dir = Path(self.project.project_dir) / "clips"
        revision = 1
        while (clips_dir / f"{action_id}.r{revision}.mp4").exists():
            revision += 1
        out_mp4 = clips_dir / f"{action_id}.r{revision}.mp4"
        project, clip = self.project, card.clip

        def job(progress, token):
            progress("refine", 0, 0, f"Refining {card.name}: {instruction}")
            clips_dir.mkdir(parents=True, exist_ok=True)
            record = refine_action(clip, instruction, out_mp4, api_key=credentials["api_key"],
                                   log=lambda m: progress("refine", 0, 0, m))
            token.raise_if_cancelled()
            card.clip = record
            card.status = "rendered"
            card.error = None
            run_pipeline(project, card, upto="stabilize", progress=progress, token=token, force=True)
            return record

        self.logMessage.emit(f"Refine requested for {card.name}: {instruction}", "INFO")
        worker = self.start_job(job, label="refine", on_finished=self._on_refine_done,
                                on_failed=self._on_failed, on_cancelled=self._on_cancelled,
                                on_progress=self._on_progress)
        if worker is not None:
            self._set_running(True)

    # -- worker slots ------------------------------------------------------

    def _on_progress(self, stage: str, done: int, total: int, message: str) -> None:
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
        else:
            self.progress.setRange(0, 0)
        self.status_label.setText(f"{stage}: {message}")
        self.logMessage.emit(f"[{stage}] {message}", "INFO")
        if stage in ("render", "extract", "stabilize", "key", "cleanup", "alpha"):
            self.refresh()

    def _on_queue_done(self, results) -> None:
        self._set_running(False)
        self.status_label.setText("")
        results = dict(results or {})
        for action_id, outcome in results.items():
            card = self._card(action_id)
            name = card.name if card is not None else action_id
            if isinstance(outcome, SpriteGenerationError):
                message = getattr(outcome, "user_message", None) or str(outcome)
                self.logMessage.emit(f"{name}: {message}", "ERROR")
            else:
                cost = fmt_usd(getattr(outcome, "actual_usd", None))
                self.logMessage.emit(f"{name}: clip ready ({cost}) → {getattr(outcome, 'path', '')}",
                                     "SUCCESS")
        self.refresh()
        self.statusChanged.emit()
        self.queueFinished.emit(results)

    def _on_refine_done(self, record) -> None:
        self._set_running(False)
        self.status_label.setText("")
        self.logMessage.emit(f"Refined clip ready → {getattr(record, 'path', '')}", "SUCCESS")
        self.refresh()
        self.statusChanged.emit()

    def _on_failed(self, message: str) -> None:
        self._set_running(False)
        self.status_label.setText("")
        self.logMessage.emit(message, "ERROR")
        self.refresh()
        self.statusChanged.emit()
        show_error(self, "Sprite queue", message)

    def _on_cancelled(self) -> None:
        self._set_running(False)
        self.status_label.setText("Cancelled.")
        self.logMessage.emit("Queue cancelled.", "WARNING")
        self.refresh()
        self.statusChanged.emit()
```

- [x] **Step 4: Run — expect pass**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m py_compile /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/queue_panel.py
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_queue_panel.py -v
```
Expected: 11 passed.

- [x] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/queue_panel.py tests/sprite/gui/test_queue_panel.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite-gui): QueuePanel driving ActionQueue with cost labels"
```

---

### Task 8: `SpriteTab` assembly (`gui/sprite/sprite_tab.py`)

**Files:**
- Create: `gui/sprite/sprite_tab.py`
- Modify: `gui/sprite/__init__.py` (export `SpriteTab`)
- Create: `tests/sprite/gui/test_sprite_tab_smoke.py`
- Reference: `gui/layout/layout_tab.py:31-63` (signals, `__init__(config, parent)`, toolbar loop), `gui/layout/__init__.py`, `gui/history_widget.py:37-45` (`standard_splitter` + persist pattern), `gui/llm_utils.py:15-83` (`DialogStatusConsole.log/clear/separator`), `tests/layout/test_layout_tab.py` (non-dialog `*_to`/`*_from` methods for tests), design §4.5 and §1.6

**Interfaces:**
- Consumes: `core.sprite.project.SpriteProjectManager` (`create_project`, `load_project`, `save_project`), `core.sprite.project.SpriteProject` (`.save(path)`, `.name`, `.project_dir`, `.generation`, `.actions`), `core.paths.get_data_paths().sprite_projects()`, `core.sprite.configs.NamedConfigStore`, the four widgets from Tasks 4–7, `gui.llm_utils.DialogStatusConsole`.
- Produces: `gui.sprite.SpriteTab` / `gui.sprite.sprite_tab.SpriteTab(QWidget)` — `__init__(self, config, parent=None)` (`config` is the `ConfigManager`; the tab and every panel read API keys through `config.get_api_key` / `get_auth_mode`); Signals `addToHistoryRequested(dict)`, `projectChanged()`, `actionSelected(str)` (forwarded from the action-cards table; `""` when nothing is selected); properties `current_project -> Optional[SpriteProject]`; `current_action() -> Optional[ActionCard]` (the selected card); `add_toolbar_action(text: str, slot) -> QPushButton` (inserted before the toolbar stretch — 5b adds "Export…" here); `make_provider(name: str = "google") -> ImageProvider` (`get_provider` with this tab's credentials; raises `ValueError` with a user-facing message when the key is missing — call it inside a worker job so `failed(str)` shows it); attribute `toolbar_layout: QHBoxLayout`. **Reserved for 5b** (set by `FramesWorkspace(self)`, appended as the last two lines of `__init__` in sub-project 5b — this plan never defines them): `frames_workspace`, `frame_strip`, `preview_player`, `pixel_view`, `processing_panel`, `undo_controller`, `undo_stack`, `refresh_frames`; project API `new_project()`, `new_project_named(name) -> Optional[SpriteProject]`, `open_project()`, `open_project_from(path) -> Optional[SpriteProject]`, `save_project() -> Optional[Path]`, `save_project_as()`, `save_project_to(path) -> Optional[Path]`, `open_generation_settings()`; routing `set_character_source(path: Path)`; **5b hooks** `set_frame_widget(w: QWidget)`, `set_preview_widget(w)`, `set_processing_widget(w)` (replace the placeholder inside `frame_area` / `preview_area` / `processing_area`; the widget is kept as `frame_widget` / `preview_widget` / `processing_widget`); `log(message, level="INFO")`; `shutdown()`; `closeEvent`. Attributes 5b uses: `console: DialogStatusConsole`, `character_panel`, `action_cards_panel`, `queue_panel`, `left_splitter`, `right_splitter`, `main_splitter`, `console_splitter`, `config_store: NamedConfigStore`, `project_manager`.
- Module constants: `PROJECT_FILTER = "Sprite projects (*.iasprite.json)"`, `SPLITTER_KEYS` (`sprite/splitter_main|left|right|console`).

- [x] **Step 1: Failing tests** — create `tests/sprite/gui/test_sprite_tab_smoke.py`:

```python
# tests/sprite/gui/test_sprite_tab_smoke.py
"""SpriteTab: construction, project toolbar, 5b slots, routing, console."""
from pathlib import Path

from PySide6.QtWidgets import QDialog, QLabel, QPushButton

import gui.sprite.sprite_tab as st
from core.sprite.project import GenerationSettings
from gui.sprite import SpriteTab
from gui.sprite.character_panel import CharacterPanel
from gui.sprite.prefs import sprite_settings


def test_construction_has_console_slots_and_no_project(qapp, fake_config):
    tab = SpriteTab(config=fake_config)
    assert tab.current_project is None
    assert tab.console.console.isReadOnly()
    for area in (tab.frame_area, tab.preview_area, tab.processing_area):
        assert area.layout().count() == 1  # placeholder label
    assert tab.main_splitter.count() == 2 and tab.left_splitter.count() == 3
    assert not tab.save_btn.isEnabled()


def test_new_project_named_creates_and_broadcasts(qapp, fake_config):
    tab = SpriteTab(config=fake_config)
    changed = []
    tab.projectChanged.connect(lambda: changed.append(1))
    project = tab.new_project_named("hero")
    assert project is tab.current_project and project.name == "hero"
    assert Path(project.project_dir).exists()
    assert tab.character_panel.project is project
    assert tab.action_cards_panel.project is project
    assert tab.queue_panel.project is project
    assert changed and "hero" in tab.title_label.text()
    assert tab.save_btn.isEnabled()


def test_save_then_open_roundtrip(qapp, fake_config):
    tab = SpriteTab(config=fake_config)
    tab.new_project_named("roundtrip")
    saved = tab.save_project()
    assert saved is not None and Path(saved).exists()
    other = SpriteTab(config=fake_config)
    loaded = other.open_project_from(saved)
    assert loaded is not None and loaded.name == "roundtrip"
    assert other.current_project is loaded


def test_open_malformed_file_is_reported(qapp, fake_config, tmp_path, monkeypatch):
    bad = tmp_path / "bad.iasprite.json"
    bad.write_text("{ not json", encoding="utf-8")
    reported = {}
    monkeypatch.setattr(SpriteTab, "_report_error",
                        lambda self, what, exc: reported.update(what=what, exc=exc))
    tab = SpriteTab(config=fake_config)
    assert tab.open_project_from(bad) is None
    assert reported.get("what") == "open project"
    assert isinstance(reported.get("exc"), Exception)


def test_5b_slots_replace_placeholders(qapp, fake_config):
    tab = SpriteTab(config=fake_config)
    first, second = QLabel("strip"), QLabel("strip v2")
    tab.set_frame_widget(first)
    assert tab.frame_widget is first
    assert tab.frame_area.layout().count() == 1
    assert tab.frame_area.layout().itemAt(0).widget() is first
    tab.set_frame_widget(second)
    assert tab.frame_widget is second and tab.frame_area.layout().count() == 1
    preview, processing = QLabel("preview"), QLabel("processing")
    tab.set_preview_widget(preview)
    tab.set_processing_widget(processing)
    assert tab.preview_widget is preview and tab.processing_widget is processing


def test_set_character_source_auto_creates_project(qapp, fake_config, png, monkeypatch):
    calls = []
    monkeypatch.setattr(CharacterPanel, "set_source", lambda self, path: calls.append(Path(path)))
    tab = SpriteTab(config=fake_config)
    tab.set_character_source(png)
    assert tab.current_project is not None and tab.current_project.name == png.stem
    assert calls == [png]
    tab.set_character_source(png)  # second call keeps the existing project
    assert len(calls) == 2


def test_panel_signals_are_routed(qapp, fake_config, monkeypatch):
    tab = SpriteTab(config=fake_config)
    tab.new_project_named("route")
    log = {"enqueue": [], "start": [], "refine": []}
    monkeypatch.setattr(tab.queue_panel, "enqueue", lambda ids: log["enqueue"].append(list(ids)))
    monkeypatch.setattr(tab.queue_panel, "start", lambda ids=None: log["start"].append(list(ids or [])))
    monkeypatch.setattr(tab.queue_panel, "refine", lambda cid, text: log["refine"].append((cid, text)))
    tab.action_cards_panel.renderRequested.emit(["a1"])
    tab.action_cards_panel.refineRequested.emit("a1", "swing")
    assert log == {"enqueue": [["a1"]], "start": [["a1"]], "refine": [("a1", "swing")]}


def test_console_and_history_forwarding(qapp, fake_config):
    tab = SpriteTab(config=fake_config)
    got = []
    tab.addToHistoryRequested.connect(lambda entry: got.append(entry))
    tab.character_panel.logMessage.emit("plate started", "INFO")
    tab.queue_panel.logMessage.emit("queue failed", "ERROR")
    assert "plate started" in tab.console.console.toPlainText()
    assert "queue failed" in tab.console.console.toPlainText()
    tab.character_panel.historyEntry.emit({"path": Path("x.png"), "source_tab": "sprite"})
    assert got == [{"path": Path("x.png"), "source_tab": "sprite"}]


def test_generation_settings_dialog_updates_project(qapp, fake_config, monkeypatch):
    class _FakeDialog:
        def __init__(self, settings, store, parent=None):
            self.initial = settings

        def exec(self):
            return QDialog.Accepted

        def settings(self):
            return GenerationSettings(duration_s=5, provider="veo")

    monkeypatch.setattr(st, "GenerationSettingsDialog", _FakeDialog)
    tab = SpriteTab(config=fake_config)
    tab.new_project_named("cfg")
    tab.open_generation_settings()
    assert tab.current_project.generation.duration_s == 5
    assert tab.current_project.generation.provider == "veo"


def test_shutdown_persists_splitters_and_is_safe_without_project(qapp, fake_config):
    tab = SpriteTab(config=fake_config)
    tab.shutdown()
    settings = sprite_settings()
    for key in st.SPLITTER_KEYS.values():
        assert settings.value(key) is not None


def test_current_action_follows_card_selection(qapp, fake_config):
    tab = SpriteTab(config=fake_config)
    tab.new_project_named("sel")
    card = tab.action_cards_panel.add_card()
    got = []
    tab.actionSelected.connect(lambda cid: got.append(cid))
    tab.action_cards_panel.table.selectRow(0)
    assert tab.current_action() is card
    assert got[-1] == card.id
    tab.action_cards_panel.table.clearSelection()
    assert tab.current_action() is None and got[-1] == ""


def test_add_toolbar_action_inserts_before_stretch(qapp, fake_config):
    tab = SpriteTab(config=fake_config)
    hits = []
    button = tab.add_toolbar_action("Export…", lambda: hits.append(1))
    assert isinstance(button, QPushButton)
    layout = tab.toolbar_layout
    index = next(i for i in range(layout.count()) if layout.itemAt(i).widget() is button)
    stretch = next(i for i in range(layout.count()) if layout.itemAt(i).spacerItem() is not None)
    assert index < stretch
    button.click()
    assert hits == [1]


def test_make_provider_uses_config_keys(qapp, fake_config, monkeypatch):
    import pytest
    seen = {}

    def fake_get_provider(name, cfg):
        seen.update(name=name, cfg=cfg)
        return "provider"

    monkeypatch.setattr(st, "get_provider", fake_get_provider)
    tab = SpriteTab(config=fake_config)
    assert tab.make_provider("google") == "provider"
    assert seen == {"name": "google", "cfg": {"api_key": "test-key", "auth_mode": "api-key"}}
    fake_config.api_key = None
    with pytest.raises(ValueError, match="API key"):
        tab.make_provider("google")
```

- [x] **Step 2: Run — expect failure**

```bash
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_sprite_tab_smoke.py -v
```
Expected: `ImportError: cannot import name 'SpriteTab' from 'gui.sprite'`.

- [x] **Step 3: Implement** — create `gui/sprite/sprite_tab.py`:

```python
"""Sprite tab: project toolbar, intake / action-card / queue panels, 5b slots, console.

Layout (design §4.5): a horizontal splitter with the left column
[CharacterPanel, ActionCardsPanel, QueuePanel] and the right column
[frame_area, preview_area, processing_area] — three containers sub-project 5b
fills through ``set_frame_widget`` / ``set_preview_widget`` /
``set_processing_widget`` — above a ``DialogStatusConsole``.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from core.paths import get_data_paths
from core.sprite.configs import NamedConfigStore
from core.sprite.project import ActionCard, SpriteProject, SpriteProjectManager
from gui.common.dialog_conventions import persist_splitter, restore_splitter, standard_splitter
from gui.dialog_utils import show_error, show_warning
from gui.llm_utils import DialogStatusConsole
from gui.sprite.action_cards_panel import ActionCardsPanel
from gui.sprite.character_panel import CharacterPanel
from gui.sprite.generation_settings_dialog import GenerationSettingsDialog
from gui.sprite.prefs import sprite_settings
from gui.sprite.queue_panel import QueuePanel
from providers import get_provider

logger = logging.getLogger(__name__)

PROJECT_FILTER = "Sprite projects (*.iasprite.json)"
SPLITTER_KEYS = {
    "main": "sprite/splitter_main",
    "left": "sprite/splitter_left",
    "right": "sprite/splitter_right",
    "console": "sprite/splitter_console",
}
LEVELS = {"INFO": logging.INFO, "SUCCESS": logging.INFO,
          "WARNING": logging.WARNING, "ERROR": logging.ERROR}
NO_PROJECT_TEXT = "No project — click New… or send a character image here"


class SpriteTab(QWidget):
    addToHistoryRequested = Signal(dict)
    projectChanged = Signal()
    actionSelected = Signal(str)   # selected card id from the action-cards table, "" when none

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.project_manager = SpriteProjectManager()
        self.config_store = NamedConfigStore()
        self._project: Optional[SpriteProject] = None
        self.frame_widget: Optional[QWidget] = None
        self.preview_widget: Optional[QWidget] = None
        self.processing_widget: Optional[QWidget] = None
        self._build()
        self._wire()
        self._restore_splitters()
        self._sync_title()

    # -- build -------------------------------------------------------------

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        self.toolbar_layout = QHBoxLayout()
        toolbar = self.toolbar_layout
        self.new_btn = QPushButton("New…")
        self.new_btn.clicked.connect(self.new_project)
        self.open_btn = QPushButton("Open…")
        self.open_btn.clicked.connect(self.open_project)
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_project)
        self.save_as_btn = QPushButton("Save As…")
        self.save_as_btn.clicked.connect(self.save_project_as)
        self.settings_btn = QPushButton("Generation Settings…")
        self.settings_btn.clicked.connect(self.open_generation_settings)
        for button in (self.new_btn, self.open_btn, self.save_btn, self.save_as_btn, self.settings_btn):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        self.title_label = QLabel()
        toolbar.addWidget(self.title_label)
        root.addLayout(toolbar)

        self.character_panel = CharacterPanel(self.config)
        self.action_cards_panel = ActionCardsPanel(self.config)
        self.queue_panel = QueuePanel(self.config)
        self.left_splitter = standard_splitter(Qt.Vertical)
        for panel in (self.character_panel, self.action_cards_panel, self.queue_panel):
            self.left_splitter.addWidget(panel)

        self.frame_area = self._make_area("Frame strip (sub-project 5b)")
        self.preview_area = self._make_area("Preview player (sub-project 5b)")
        self.processing_area = self._make_area("Processing (sub-project 5b)")
        self.right_splitter = standard_splitter(Qt.Vertical)
        for area in (self.frame_area, self.preview_area, self.processing_area):
            self.right_splitter.addWidget(area)

        self.main_splitter = standard_splitter(Qt.Horizontal)
        self.main_splitter.addWidget(self.left_splitter)
        self.main_splitter.addWidget(self.right_splitter)

        self.console = DialogStatusConsole("Sprite console")
        self.console_splitter = standard_splitter(Qt.Vertical)
        self.console_splitter.addWidget(self.main_splitter)
        self.console_splitter.addWidget(self.console)
        root.addWidget(self.console_splitter, 1)

    @staticmethod
    def _make_area(text: str) -> QWidget:
        area = QWidget()
        layout = QVBoxLayout(area)
        layout.setContentsMargins(0, 0, 0, 0)
        hint = QLabel(text)
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: gray; border: 1px dashed gray;")
        layout.addWidget(hint)
        return area

    @staticmethod
    def _fill_area(area: QWidget, widget: QWidget) -> None:
        layout = area.layout()
        while layout.count():
            item = layout.takeAt(0)
            old = item.widget()
            if old is not None:
                old.setParent(None)
                old.deleteLater()
        layout.addWidget(widget)

    def set_frame_widget(self, widget: QWidget) -> None:
        self._fill_area(self.frame_area, widget)
        self.frame_widget = widget

    def set_preview_widget(self, widget: QWidget) -> None:
        self._fill_area(self.preview_area, widget)
        self.preview_widget = widget

    def set_processing_widget(self, widget: QWidget) -> None:
        self._fill_area(self.processing_area, widget)
        self.processing_widget = widget

    def add_toolbar_action(self, text: str, slot) -> QPushButton:
        """Add a toolbar button before the stretch (sub-project 5b adds Export… here)."""
        button = QPushButton(text)
        button.clicked.connect(slot)
        index = self.toolbar_layout.count()
        for i in range(self.toolbar_layout.count()):
            if self.toolbar_layout.itemAt(i).spacerItem() is not None:
                index = i
                break
        self.toolbar_layout.insertWidget(index, button)
        return button

    # -- wiring ------------------------------------------------------------

    def _wire(self) -> None:
        for panel in (self.character_panel, self.action_cards_panel, self.queue_panel):
            panel.logMessage.connect(self.log)
        self.character_panel.historyEntry.connect(self.addToHistoryRequested)
        self.character_panel.sourceChanged.connect(self._on_character_changed)
        self.character_panel.plateReady.connect(self._on_character_changed)
        self.character_panel.turnaroundReady.connect(self._on_character_changed)
        self.character_panel.plateColorChanged.connect(self._on_character_changed)
        self.action_cards_panel.cardsChanged.connect(self._on_cards_changed)
        self.action_cards_panel.renderRequested.connect(self._on_render_requested)
        self.action_cards_panel.refineRequested.connect(self._on_refine_requested)
        self.action_cards_panel.actionSelected.connect(self.actionSelected)
        self.queue_panel.statusChanged.connect(self._on_queue_status_changed)

    def _on_character_changed(self, *_args) -> None:
        self._autosave()
        self.projectChanged.emit()

    def _on_cards_changed(self) -> None:
        self.queue_panel.refresh()
        self._autosave()
        self.projectChanged.emit()

    def _on_render_requested(self, ids) -> None:
        ids = list(ids)
        self.queue_panel.enqueue(ids)
        self.queue_panel.start(ids)

    def _on_refine_requested(self, action_id: str, instruction: str) -> None:
        self.queue_panel.refine(action_id, instruction)

    def _on_queue_status_changed(self) -> None:
        self.action_cards_panel.refresh_status()
        self._autosave()
        self.projectChanged.emit()

    # -- splitters ---------------------------------------------------------

    def _restore_splitters(self) -> None:
        settings = sprite_settings()
        if not restore_splitter(settings, SPLITTER_KEYS["main"], self.main_splitter):
            self.main_splitter.setSizes([480, 820])
        if not restore_splitter(settings, SPLITTER_KEYS["left"], self.left_splitter):
            self.left_splitter.setSizes([260, 320, 220])
        if not restore_splitter(settings, SPLITTER_KEYS["right"], self.right_splitter):
            self.right_splitter.setSizes([220, 360, 220])
        if not restore_splitter(settings, SPLITTER_KEYS["console"], self.console_splitter):
            self.console_splitter.setSizes([640, 160])

    def _persist_splitters(self) -> None:
        settings = sprite_settings()
        persist_splitter(settings, SPLITTER_KEYS["main"], self.main_splitter)
        persist_splitter(settings, SPLITTER_KEYS["left"], self.left_splitter)
        persist_splitter(settings, SPLITTER_KEYS["right"], self.right_splitter)
        persist_splitter(settings, SPLITTER_KEYS["console"], self.console_splitter)
        settings.sync()

    # -- console -----------------------------------------------------------

    def log(self, message: str, level: str = "INFO") -> None:
        self.console.log(message, level)
        logger.log(LEVELS.get(level, logging.INFO), "sprite: %s", message)

    def _report_error(self, what: str, exc: Exception) -> None:
        message = f"Could not {what}: {exc}"
        self.console.log(message, "ERROR")
        show_error(self, "Sprite", message, exception=exc)

    # -- project -----------------------------------------------------------

    @property
    def current_project(self) -> Optional[SpriteProject]:
        return self._project

    def current_action(self) -> Optional[ActionCard]:
        """The card selected in the action-cards table, or None."""
        ids = self.action_cards_panel.selected_ids()
        return self.action_cards_panel.card_by_id(ids[0]) if ids else None

    def make_provider(self, name: str = "google"):
        """Build an image provider with this tab's credentials.

        Raises ValueError with a user-facing message when no key is configured;
        call it inside a worker job so the message reaches ``failed(str)``.
        """
        api_key = self.config.get_api_key(name)
        if not api_key:
            raise ValueError(f"No {name} API key is configured. Add one in Settings.")
        return get_provider(name, {"api_key": api_key, "auth_mode": self.config.get_auth_mode(name)})

    def _apply_project(self, project: SpriteProject) -> None:
        self._project = project
        self.character_panel.set_project(project)
        self.action_cards_panel.set_project(project)
        self.queue_panel.set_project(project)
        self._sync_title()
        self.log(f"Project: {project.name} ({project.project_dir})", "INFO")
        self.projectChanged.emit()

    def _sync_title(self) -> None:
        has_project = self._project is not None
        if has_project:
            self.title_label.setText(f"{self._project.name} — {self._project.project_dir}")
        else:
            self.title_label.setText(NO_PROJECT_TEXT)
        for button in (self.save_btn, self.save_as_btn, self.settings_btn):
            button.setEnabled(has_project)

    def _autosave(self) -> None:
        if self._project is None:
            return
        try:
            self.project_manager.save_project(self._project)
        except Exception as exc:  # noqa: BLE001 - reported, never raised out of a slot
            self._report_error("save project", exc)

    def new_project(self) -> None:
        name, ok = QInputDialog.getText(self, "New sprite project", "Project name:", text="sprite")
        if ok and name.strip():
            self.new_project_named(name.strip())

    def new_project_named(self, name: str) -> Optional[SpriteProject]:
        try:
            project = self.project_manager.create_project(name)
        except Exception as exc:  # noqa: BLE001
            self._report_error("create project", exc)
            return None
        self._apply_project(project)
        return project

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open sprite project", str(get_data_paths().sprite_projects()), PROJECT_FILTER)
        if path:
            self.open_project_from(path)

    def open_project_from(self, path) -> Optional[SpriteProject]:
        try:
            project = self.project_manager.load_project(Path(path))
        except Exception as exc:  # noqa: BLE001
            self._report_error("open project", exc)
            return None
        self._apply_project(project)
        return project

    def save_project(self) -> Optional[Path]:
        if self._project is None:
            show_warning(self, "Sprite", "There is no project to save.")
            return None
        try:
            saved = self.project_manager.save_project(self._project)
        except Exception as exc:  # noqa: BLE001
            self._report_error("save project", exc)
            return None
        self.log(f"Saved → {saved}", "SUCCESS")
        self._sync_title()
        return Path(saved)

    def save_project_as(self) -> None:
        if self._project is None:
            show_warning(self, "Sprite", "There is no project to save.")
            return
        start = str(self._project.project_dir or get_data_paths().sprite_projects())
        path, _ = QFileDialog.getSaveFileName(self, "Save sprite project as", start, PROJECT_FILTER)
        if path:
            self.save_project_to(path)

    def save_project_to(self, path) -> Optional[Path]:
        if self._project is None:
            return None
        try:
            saved = self._project.save(Path(path))
        except Exception as exc:  # noqa: BLE001
            self._report_error("save project", exc)
            return None
        self.log(f"Saved → {saved}", "SUCCESS")
        self._sync_title()
        return Path(saved)

    def open_generation_settings(self) -> None:
        if self._project is None:
            show_warning(self, "Sprite", "Open a sprite project first.")
            return
        dialog = GenerationSettingsDialog(self._project.generation, self.config_store, self)
        if dialog.exec() != QDialog.Accepted:
            return
        settings = dialog.settings()
        self._project.generation = settings
        self.log(f"Generation settings [{settings.config_name}]: {settings.provider}/"
                 f"{settings.model or 'default'} {settings.resolution} {settings.aspect_ratio} "
                 f"{settings.duration_s}s @ {settings.fps} fps, plate {settings.plate_color}", "INFO")
        self.queue_panel.refresh()
        self.action_cards_panel.refresh_hint()
        self._autosave()
        self.projectChanged.emit()

    # -- cross-tab entry ---------------------------------------------------

    def set_character_source(self, path: Path) -> None:
        """Entry point for "Send to Sprite": creates a project when none is open."""
        path = Path(path)
        if self._project is None and self.new_project_named(path.stem or "sprite") is None:
            return
        self.log(f"Character source: {path}", "INFO")
        self.character_panel.set_source(path)

    # -- lifecycle ---------------------------------------------------------

    def shutdown(self) -> None:
        """Cancel every running worker and persist layout. MainWindow calls this on close."""
        for panel in (self.character_panel, self.action_cards_panel, self.queue_panel):
            panel.shutdown()
        self._persist_splitters()

    def closeEvent(self, event) -> None:
        self.shutdown()
        super().closeEvent(event)
```

Replace `gui/sprite/__init__.py` with:

```python
"""Sprite tab GUI package (design §4.5)."""

from .sprite_tab import SpriteTab

__all__ = ["SpriteTab"]
```

- [x] **Step 4: Run — expect pass**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m py_compile /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/sprite_tab.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/__init__.py
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui -v
```
Expected: `test_sprite_tab_smoke.py` 13 passed; every earlier `tests/sprite/gui` file still green.

- [x] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/__init__.py gui/sprite/sprite_tab.py tests/sprite/gui/test_sprite_tab_smoke.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite-gui): SpriteTab assembly with project toolbar and 5b hook slots"
```

---

### Task 9: Main-window wiring and "Send to Sprite" (three surfaces)

**Files:**
- Modify: `gui/main_window.py` — `_init_ui` (`:667-727`; placeholder tab at `:686-688`, `addTab` block `:708-714`), output image label (`:1470-1475`), history view (`:3401-3465`), `closeEvent` (`:7795-7825`), `_on_tab_changed` (`:8084-8114`), `_load_video_tab` STEP 5 (`:8145-8156`), new methods after `_load_video_tab` (`:8208`). Line numbers verified on `25788d3` (2026-08-29); re-grep before editing.
- Modify: `gui/video/reference_library_widget.py` — `ReferenceCard` signals (`:27-28`), `contextMenuEvent` (`:180-192`), `ReferenceLibraryWidget` signals (`:265-266`), card creation loop (`:463-468`).
- Modify: `gui/video/video_project_tab.py` — `VideoProjectTab` signals (`:1575-1578`), reference-library wiring (`:1682-1684`).
- Create: `tests/sprite/gui/test_main_window_sprite_wiring.py`
- Reference: `tests/gui/test_storage_settings.py:364-388` (unbound `MainWindow.method(stub, …)` test idiom), `gui/video/workspace_widget.py:2131-2154` (`QMenu` action pattern)

**Interfaces:**
- Produces (MainWindow): attributes `tab_sprite: QWidget`, `_sprite_tab_loaded: bool`; methods `_load_sprite_tab() -> None` (idempotent; swaps the placeholder in place; connects `addToHistoryRequested → add_to_history`; on failure logs + `QMessageBox.warning`), `_on_send_to_sprite(path) -> None` (loads the tab if needed, switches to it, calls `set_character_source`), `_build_send_to_sprite_menu(path, parent=None) -> QMenu` (one action "Send to Sprite", enabled only when `path` exists), `_show_output_image_context_menu(pos)`, `_history_path_at(pos) -> Optional[Path]`, `_show_history_context_menu(pos)`.
- Produces (video): `ReferenceCard.send_to_sprite_clicked = Signal(object)` + `_build_context_menu() -> QMenu`; `ReferenceLibraryWidget.sendToSpriteRequested = Signal(object)` + `_connect_card(card)`; `VideoProjectTab.sendToSpriteRequested = Signal(object)` (forwarded from the library); `_load_video_tab` connects it to `_on_send_to_sprite`.
- Design §4.5 names the signal `sendToSpriteRequested(Path)`; payload is a `Path` carried by `Signal(object)`.

- [x] **Step 1: Failing tests** — create `tests/sprite/gui/test_main_window_sprite_wiring.py`:

```python
# tests/sprite/gui/test_main_window_sprite_wiring.py
"""MainWindow ↔ SpriteTab wiring: lazy placeholder swap and Send to Sprite (3 surfaces).

MainWindow is never constructed here (it scans history and builds every tab);
the methods run unbound against a SimpleNamespace stub, as
tests/gui/test_storage_settings.py does for close_data_handles.
"""
import inspect
import types
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget, QWidget

from core.video.project import ReferenceImage
from gui.video.reference_library_widget import ReferenceCard, ReferenceLibraryWidget


class _FakeSpriteTab(QWidget):
    addToHistoryRequested = Signal(dict)

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.sources = []

    def set_character_source(self, path):
        self.sources.append(Path(path))

    def shutdown(self):
        pass


class _Logger:
    def __init__(self):
        self.errors, self.infos = [], []

    def info(self, message, *a, **k):
        self.infos.append(message)

    def error(self, message, *a, **k):
        self.errors.append(message)

    debug = warning = info


def _stub(monkeypatch, tab_cls=_FakeSpriteTab):
    from gui.main_window import MainWindow

    monkeypatch.setattr("gui.sprite.SpriteTab", tab_cls)
    tabs = QTabWidget()
    placeholder = QWidget()
    tabs.addTab(QWidget(), "🎨 Image")
    tabs.addTab(placeholder, "🎮 Sprite")
    tabs.addTab(QWidget(), "⚙️ Settings")
    history = []

    def add_to_history(entry):  # plain function: signals connect to it cleanly
        history.append(entry)

    stub = types.SimpleNamespace(tabs=tabs, tab_sprite=placeholder, _sprite_tab_loaded=False,
                                 config=object(), logger=_Logger(),
                                 add_to_history=add_to_history, history_entries=history)
    stub._load_sprite_tab = lambda: MainWindow._load_sprite_tab(stub)
    stub._on_send_to_sprite = lambda path: MainWindow._on_send_to_sprite(stub, path)
    return MainWindow, stub


def test_init_ui_adds_sprite_placeholder_after_layout(qapp):
    from gui.main_window import MainWindow

    source = inspect.getsource(MainWindow._init_ui)
    assert "self._sprite_tab_loaded = False" in source
    assert source.index('"📖 Layout"') < source.index('"🎮 Sprite"') < source.index('"⚙️ Settings"')
    changed = inspect.getsource(MainWindow._on_tab_changed)
    assert "self.tab_sprite" in changed and "_load_sprite_tab" in changed
    close = inspect.getsource(MainWindow.closeEvent)
    assert "tab_sprite" in close and "shutdown" in close


def test_load_sprite_tab_swaps_placeholder_in_place(qapp, monkeypatch):
    MainWindow, stub = _stub(monkeypatch)
    MainWindow._load_sprite_tab(stub)
    assert stub._sprite_tab_loaded is True
    assert isinstance(stub.tab_sprite, _FakeSpriteTab)
    assert stub.tab_sprite.config is stub.config
    assert stub.tabs.count() == 3
    assert stub.tabs.widget(1) is stub.tab_sprite
    assert stub.tabs.tabText(1) == "🎮 Sprite"
    assert stub.tabs.currentIndex() == 1
    stub.tab_sprite.addToHistoryRequested.emit({"path": Path("p.png")})
    assert stub.history_entries == [{"path": Path("p.png")}]


def test_load_sprite_tab_is_idempotent(qapp, monkeypatch):
    MainWindow, stub = _stub(monkeypatch)
    MainWindow._load_sprite_tab(stub)
    first = stub.tab_sprite
    MainWindow._load_sprite_tab(stub)
    assert stub.tab_sprite is first and stub.tabs.count() == 3


def test_load_sprite_tab_failure_is_logged_and_shown(qapp, monkeypatch):
    class _Broken(QWidget):
        def __init__(self, config=None, parent=None):
            raise RuntimeError("sprite import exploded")

    import gui.main_window as mw
    warnings = []
    monkeypatch.setattr(mw.QMessageBox, "warning",
                        staticmethod(lambda parent, title, text: warnings.append((title, text))))
    MainWindow, stub = _stub(monkeypatch, tab_cls=_Broken)
    MainWindow._load_sprite_tab(stub)
    assert stub._sprite_tab_loaded is False
    assert stub.tabs.widget(1) is stub.tab_sprite  # placeholder kept
    assert any("sprite import exploded" in message for message in stub.logger.errors)
    assert warnings and "sprite import exploded" in warnings[0][1]


def test_send_to_sprite_loads_tab_and_routes_path(qapp, monkeypatch, png):
    MainWindow, stub = _stub(monkeypatch)
    MainWindow._on_send_to_sprite(stub, str(png))
    assert stub._sprite_tab_loaded is True
    assert stub.tabs.currentWidget() is stub.tab_sprite
    assert stub.tab_sprite.sources == [png]


def test_send_to_sprite_missing_file_is_reported_not_routed(qapp, monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr("gui.dialog_utils.show_error",
                        lambda parent, title, message, exception=None: seen.append(message))
    MainWindow, stub = _stub(monkeypatch)
    MainWindow._on_send_to_sprite(stub, tmp_path / "gone.png")
    assert seen and "gone.png" in seen[0]
    assert stub._sprite_tab_loaded is False


def test_send_to_sprite_menu_action_enabled_only_when_path_exists(qapp, monkeypatch, png, tmp_path):
    MainWindow, stub = _stub(monkeypatch)
    menu = MainWindow._build_send_to_sprite_menu(stub, png)
    actions = menu.actions()
    assert [a.text() for a in actions] == ["Send to Sprite"]
    assert actions[0].isEnabled()
    actions[0].trigger()
    assert stub.tab_sprite.sources == [png]
    disabled = MainWindow._build_send_to_sprite_menu(stub, tmp_path / "missing.png")
    assert not disabled.actions()[0].isEnabled()
    none_menu = MainWindow._build_send_to_sprite_menu(stub, None)
    assert not none_menu.actions()[0].isEnabled()


def test_reference_card_context_menu_sends_to_sprite(qapp, png):
    card = ReferenceCard(ReferenceImage(path=png))
    got = []
    card.send_to_sprite_clicked.connect(lambda p: got.append(p))
    menu = card._build_context_menu()
    texts = [action.text() for action in menu.actions()]
    assert texts == ["Edit Info", "Send to Sprite", "Remove"]
    menu.actions()[1].trigger()
    assert got == [png]


def test_reference_library_forwards_send_to_sprite(qapp, png):
    library = ReferenceLibraryWidget(None, None)
    got = []
    library.sendToSpriteRequested.connect(lambda p: got.append(p))
    card = ReferenceCard(ReferenceImage(path=png))
    library._connect_card(card)
    card.send_to_sprite_clicked.emit(png)
    assert got == [png]


def test_video_tab_declares_and_main_window_connects_the_signal(qapp):
    from gui.main_window import MainWindow
    from gui.video.video_project_tab import VideoProjectTab

    assert hasattr(VideoProjectTab, "sendToSpriteRequested")
    source = inspect.getsource(MainWindow._load_video_tab)
    assert "sendToSpriteRequested" in source and "_on_send_to_sprite" in source
```

- [x] **Step 2: Run — expect failure**

```bash
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_main_window_sprite_wiring.py -v
```
Expected: `AttributeError: type object 'MainWindow' has no attribute '_load_sprite_tab'` (and `ReferenceCard has no attribute 'send_to_sprite_clicked'`).

- [x] **Step 3: Implement — `gui/main_window.py`**

3a. In `_init_ui`, directly after the video placeholder block (`self._video_tab_loaded = False  # Track if real video tab is loaded`):

```python
        # Placeholder for the Sprite tab — loaded lazily like the Video tab
        self.tab_sprite = QWidget()
        self._sprite_tab_loaded = False
```

3b. In the `# Add tabs` block, insert after `self.tabs.addTab(self.tab_layout, "📖 Layout")`:

```python
        self.tabs.addTab(self.tab_sprite, "🎮 Sprite")
```

3c. In `_init_generate_tab`, directly after `self.output_image_label.setScaledContents(False)  # We handle scaling manually`:

```python
        # Right-click: Send to Sprite (the label had no context menu before)
        self.output_image_label.setContextMenuPolicy(Qt.CustomContextMenu)
        self.output_image_label.customContextMenuRequested.connect(
            self._show_output_image_context_menu)
```

3d. In `_init_history_tab`, directly after `self.history_view.doubleClicked.connect(self._on_history_item_double_clicked)`:

```python
        self.history_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_view.customContextMenuRequested.connect(self._show_history_context_menu)
```

3e. In `_on_tab_changed`, after the video lazy-load block:

```python
        # Lazy load sprite tab on first access
        if current_widget == self.tab_sprite and not self._sprite_tab_loaded:
            self.logger.info("Triggering sprite tab lazy load...")
            self._load_sprite_tab()
```

3f. In `_load_video_tab` STEP 5, after the `add_to_history_signal` connection:

```python
            if hasattr(real_video_tab, 'sendToSpriteRequested'):
                real_video_tab.sendToSpriteRequested.connect(self._on_send_to_sprite)
                self.logger.info("STEP 5: Connected sendToSpriteRequested signal")
```

3g. In `closeEvent`, before `# Save window geometry`:

```python
            # Stop sprite workers and persist the sprite tab layout
            if getattr(self, "_sprite_tab_loaded", False) and hasattr(self.tab_sprite, "shutdown"):
                try:
                    self.tab_sprite.shutdown()
                except Exception as e:
                    logger.error(f"Error shutting down sprite tab: {e}")
```

3h. New methods, inserted directly after `_load_video_tab` (before `_trigger_help_render`):

```python
    def _load_sprite_tab(self):
        """Lazy-load the Sprite tab on first activation (mirrors _load_video_tab)."""
        if getattr(self, "_sprite_tab_loaded", False):
            return
        try:
            from gui.sprite import SpriteTab
            real_tab = SpriteTab(config=self.config)
            real_tab.addToHistoryRequested.connect(self.add_to_history)
            index = self.tabs.indexOf(self.tab_sprite)
            self.tabs.removeTab(index)
            self.tabs.insertTab(index, real_tab, "🎮 Sprite")
            self.tabs.setCurrentIndex(index)
            self.tab_sprite = real_tab
            self._sprite_tab_loaded = True
            self.logger.info("Sprite tab loaded")
        except Exception as e:
            import traceback
            error_msg = f"Failed to load sprite tab: {str(e)}\n\n{traceback.format_exc()}"
            self.logger.error(f"SPRITE TAB LOAD ERROR:\n{error_msg}")
            QMessageBox.warning(self, "Sprite Tab Error", error_msg)

    def _on_send_to_sprite(self, path):
        """Route an image path into the Sprite tab as its character source."""
        try:
            path = Path(path)
        except TypeError:
            self.logger.error(f"Send to Sprite: invalid path {path!r}")
            return
        if not path.exists():
            from gui.dialog_utils import show_error
            show_error(self, "Send to Sprite", f"Image not found: {path}")
            return
        if not self._sprite_tab_loaded:
            self._load_sprite_tab()
        if not self._sprite_tab_loaded:
            return  # load failed; already logged and shown
        self.tabs.setCurrentWidget(self.tab_sprite)
        self.tab_sprite.set_character_source(path)

    def _build_send_to_sprite_menu(self, path, parent=None):
        """One-action context menu shared by the Image result and the History table."""
        from PySide6.QtWidgets import QMenu
        menu = QMenu(parent)
        action = menu.addAction("Send to Sprite")
        exists = False
        if path:
            try:
                exists = Path(path).exists()
            except (TypeError, OSError):
                exists = False
        action.setEnabled(exists)
        action.triggered.connect(lambda _checked=False, p=path: self._on_send_to_sprite(p))
        return menu

    def _show_output_image_context_menu(self, pos):
        path = getattr(self, "_last_displayed_image_path", None)
        menu = self._build_send_to_sprite_menu(path, self.output_image_label)
        menu.exec(self.output_image_label.mapToGlobal(pos))

    def _history_path_at(self, pos):
        index = self.history_view.indexAt(pos)
        if not index.isValid():
            return None
        source_index = self.history_proxy.mapToSource(index)
        entry = self.history_model.get_entry(source_index.row())
        return entry.get("path") if isinstance(entry, dict) else None

    def _show_history_context_menu(self, pos):
        path = self._history_path_at(pos)
        if not path:
            return
        menu = self._build_send_to_sprite_menu(path, self.history_view)
        menu.exec(self.history_view.viewport().mapToGlobal(pos))
```

`Qt`, `Path`, `QMessageBox` and `QWidget` are already imported at the top of `gui/main_window.py` (`:6`, `:17`, `:19-22`).

- [x] **Step 4: Implement — `gui/video/reference_library_widget.py`**

4a. `ReferenceCard` signals become:

```python
    remove_clicked = Signal(object)  # ReferenceImage
    edit_clicked = Signal(object)  # ReferenceImage
    send_to_sprite_clicked = Signal(object)  # Path — "Send to Sprite" (design §4.5)
```

4b. Replace `contextMenuEvent` with:

```python
    def _build_context_menu(self) -> QMenu:
        """Edit / Send to Sprite / Remove. Built separately so tests can inspect it."""
        menu = QMenu(self)

        edit_action = QAction("Edit Info", self)
        edit_action.triggered.connect(lambda: self.edit_clicked.emit(self.reference))
        menu.addAction(edit_action)

        sprite_action = QAction("Send to Sprite", self)
        sprite_action.setEnabled(self.reference.path.exists())
        sprite_action.triggered.connect(
            lambda: self.send_to_sprite_clicked.emit(Path(self.reference.path)))
        menu.addAction(sprite_action)

        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(lambda: self.remove_clicked.emit(self.reference))
        menu.addAction(remove_action)
        return menu

    def contextMenuEvent(self, event):
        """Show context menu"""
        self._build_context_menu().exec_(event.globalPos())
```

4c. `ReferenceLibraryWidget` signals become:

```python
    references_changed = Signal()  # Emitted when references are added/removed
    frame_selected = Signal(Path)  # Emitted when an extracted frame is selected to add as reference
    sendToSpriteRequested = Signal(object)  # Path — forwarded from a card's context menu
```

4d. Add to `ReferenceLibraryWidget` (after `__init__`):

```python
    def _connect_card(self, card: ReferenceCard) -> None:
        card.remove_clicked.connect(self.on_remove_reference)
        card.edit_clicked.connect(self.on_edit_reference)
        card.send_to_sprite_clicked.connect(self.sendToSpriteRequested)
```

and in the card creation loop replace the two `card.*.connect(...)` lines with `self._connect_card(card)`:

```python
        for ref in refs:
            card = ReferenceCard(ref, self)
            self._connect_card(card)
            self.cards_layout.addWidget(card)
            self.reference_cards.append(card)
```

- [x] **Step 5: Implement — `gui/video/video_project_tab.py`**

5a. `VideoProjectTab` signals become:

```python
    # Signals
    image_provider_changed = Signal(str)  # provider name
    llm_provider_changed = Signal(str, str)  # provider name, model name
    add_to_history_signal = Signal(dict)  # history entry
    sendToSpriteRequested = Signal(object)  # Path — from the reference library (design §4.5)
```

5b. After `self.reference_library_widget.references_changed.connect(self.on_references_changed)`:

```python
        self.reference_library_widget.sendToSpriteRequested.connect(self.sendToSpriteRequested)
```

- [x] **Step 6: Run — expect pass**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m py_compile /mnt/d/Documents/Code/GitHub/ImageAI/gui/main_window.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/video/reference_library_widget.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/video/video_project_tab.py
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_main_window_sprite_wiring.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/gui -v
```
Expected: 10 passed in the wiring file; `tests/gui` unchanged and green.

- [ ] **Step 7: Manual check (PowerShell, `.venv`, per AGENTS.md)** — `python main.py`: the "🎮 Sprite" tab sits after "📖 Layout"; clicking it replaces the placeholder; right-click on the Image-tab result and on a History row shows "Send to Sprite"; the Video → References card menu shows it; each lands on the Sprite tab with a new project named after the file. Record the outcome in the commit body.
  **Deferred to Leland** — headless CI/agent dispatch has no interactive display for a manual PowerShell click-through; this step still needs a human run before the sub-project is fully verified end-to-end.

- [x] **Step 8: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/main_window.py gui/video/reference_library_widget.py gui/video/video_project_tab.py tests/sprite/gui/test_main_window_sprite_wiring.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite-gui): lazy Sprite tab in MainWindow and Send to Sprite actions"
```

---

### Task 10: Full-suite run and plan close-out

**Files:**
- Modify (only if a fix is needed): any file from Tasks 1–9
- Modify: `Plans/2026-08-29-sprite-gui-a-plan.md` (tick the checkboxes, update **Last Updated**)

**Interfaces:** none new.

- [x] **Step 1: Compile every touched module**

```bash
/mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m py_compile /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/__init__.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/workers.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/prefs.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/character_panel.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/generation_settings_dialog.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/action_cards_panel.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/queue_panel.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/sprite/sprite_tab.py /mnt/d/Documents/Code/GitHub/ImageAI/core/sprite/configs.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/main_window.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/video/reference_library_widget.py /mnt/d/Documents/Code/GitHub/ImageAI/gui/video/video_project_tab.py
```
Expected: no output.

- [x] **Step 2: Sprite suite + path guard + dialog conventions**

```bash
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/gui -v
```
Expected: all green — 5a adds 7 + 9 + 6 + 11 + 12 + 13 + 11 + 13 + 10 = 92 tests on top of sub-projects 1–4.

- [x] **Step 3: Full suite (the single full run for this sub-project)**

```bash
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest -q
```
Expected: 0 failures. If a failure is in a 5a file, fix it and re-run this step; if it is in another sub-project's file, report it to the team lead and do not patch it here.

- [x] **Step 4: Commit any fix**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI status --short
git -C /mnt/d/Documents/Code/GitHub/ImageAI add -A gui/sprite core/sprite/configs.py tests/sprite
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "test(sprite-gui): stabilize sprite GUI suite after full run"
```
Skip the commit when `status --short` is empty.

- [x] **Step 5: Close the plan** — tick every `- [ ]` above to `- [x]`, set **Last Updated** with `date '+%Y-%m-%d %H:%M'`, and commit:

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add Plans/2026-08-29-sprite-gui-a-plan.md
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "docs(plans): sprite GUI (A) plan complete"
```

No version bump and no changelog entry in this sub-project (sub-project 7 owns the release).

---

## Self-review

Checked against the design and the repo on 2026-08-29:

- **Contract names.** Every `core.sprite.*` symbol the plan consumes appears verbatim in design §1.1, §1.3, §2, §4.2 (`CancelToken`, `Cancelled`, `ProgressFn`, `run_pipeline`, `GenerationSettings`, `ActionCard`, `SpriteProject.save`, `generate_action_cards`, `ActionCardDraft`, `GENRE_CHECKLISTS`, `make_chroma_plate`, `generate_turnaround`, `refine_action`, `ActionQueue`, `estimate_action`, `estimate_project`, `SpriteGenerationError.user_message`, `normalize_source`, `analyze_source`, `suggest_clip_duration`, `DataPaths.sprite_configs / sprite_projects`). The one symbol the design does not define — `SpriteProjectManager` — was reconciled with sub-project 1 on 2026-08-29 (`core/sprite/project.py`; see Global Constraints).
- **Repo APIs verified by reading.** `DialogStatusConsole.log(message, level)` / `clear()` / `separator()` (`gui/llm_utils.py:15-83`); `standard_splitter` / `persist_splitter` / `restore_splitter` / `bind_primary_action(widget, slot, *, context)` / `PrimaryAction.set_enabled` / `set_default_button(dialog, button, *, focus)` / `DialogCleanupMixin.on_dialog_close` (`gui/common/dialog_conventions.py`); `show_error(parent, title, message, exception=None)` and `show_warning(parent, title, message, log_level=…)` (`gui/dialog_utils.py:15-40`); `ConfigManager.get/set/get_api_key/get_auth_mode` (`core/config.py:394-470`); `get_provider(name, config_dict)` (`gui/workers.py:60`); `resolve_model(provider, family, static_default=None)`, `get_all_provider_ids()`, `get_provider_display_name(id)` (`core/llm_models.py:63-218`); `OmniModel.default_id()` (`core/video/omni_client.py:74-77`); `VeoModel` members (`core/video/veo_client.py:60-62`); `MainWindow._last_displayed_image_path` (`gui/main_window.py:6604,7247,7970`), `history_proxy` / `history_model.get_entry` (`:8049-8051`), `add_to_history(entry)` (`:9167`); `ReferenceImage(path=…)` (`core/video/project.py:198-205`); `ReferenceLibraryWidget(parent, project)` (`reference_library_widget.py:268`).
- **Threading.** Every provider / LLM / pipeline / PIL call is inside a `job(progress, token)`; worker signals connect to bound methods of the panel (queued to the GUI thread); the GUI thread paints one thumbnail (`CharacterPanel._show_thumbnail`). `SpriteTab.shutdown()` joins every worker; `MainWindow.closeEvent` calls it (a child widget never receives the parent's `closeEvent`).
- **Errors.** Every user-facing failure path goes through `show_error` / `show_warning` (which log first) or `logMessage(…, "ERROR")` into the console plus `logger.error` in the worker. Cancels never open a dialog.
- **Keys and paths.** API keys only via `config.get_api_key` / `get_auth_mode`. No literal user-dir path anywhere; `tests/test_no_hardcoded_paths.py` runs in Tasks 2 and 10.
- **Tests.** Every test symbol is defined in the plan or in the design; provider and LLM calls are monkeypatched at the panel module namespace; workers are joined with `wait_for_worker`. Test basenames are unique under `tests/`. No test constructs `MainWindow`.
- **Task order** matches the brief: workers → configs → prefs → character panel → settings dialog → action cards → queue → tab → main-window wiring → full run.
- **Known risk to watch in Task 1:** `SpriteWorker.finished = Signal(object)` shadows `QThread.finished()`. PySide6 treats it as an overload; `test_finished_carries_job_result` asserts exactly `[42]` so any stray no-arg emission surfaces immediately. If it fails, keep the design name and connect through `worker.finished[object]`.

## Deviations from the design

1. **`SpriteProjectManager`** is not in the design. Sub-project 1 ships it in `core/sprite/project.py` (`create_project` / `load_project` / `save_project` / `list_projects` / `delete_project` / `find_project`); this plan imports it from there (reconciled 2026-08-29).
2. **`cancelled()` signal** added to `SpriteWorker` beyond the three signals in §1.1. A `Cancelled` exception maps to `cancelled()`, never to `failed("cancelled")`, so the UI can skip the error dialog.
3. **Mixin order** is `class GenerationSettingsDialog(DialogCleanupMixin, QDialog)` (the mixin must precede `QDialog` for `done()`/`closeEvent` interception), not the `(QDialog, DialogCleanupMixin)` order in the brief.
4. **Panels subclass `QGroupBox`** (a `QWidget`) for a titled frame; the brief says `QWidget`. The public API is unchanged.
5. **Path payloads** use `Signal(object)` (documented as `Path`) instead of `Signal(Path)`; `ReferenceLibraryWidget.frame_selected` keeps its existing `Signal(Path)`.
6. **No pre-existing context menus.** The Image-tab result label and the History table have no context menu today (verified: no `QMenu` / `customContextMenuRequested` in `gui/main_window.py`). Task 9 creates both with "Send to Sprite" as the only action. The Video library's only context menu is `ReferenceCard`; `ExtractedFrameCard` has none and is untouched.
7. **Genre list** comes from `GENRE_CHECKLISTS` in `core/sprite/generation/action_cards.py` (design §4.2) rather than an unnamed symbol in `core/sprite/presets.py`; FPS presets are shown as a tooltip on the FPS spin box.
8. **LLM provider for action cards** is chosen in the panel (`llm_combo`, sticky under `sprite/llm_provider`) because the design does not name which chat provider writes the cards. The model is always `resolve_model(provider, "chat")`.
9. **Refine** runs `run_pipeline(upto="stabilize", force=True)` after `refine_action`, mirroring what `ActionQueue` does after `render_action`, so refined frames appear without a separate step.
10. **Retry** in the panel re-enqueues the selected failed cards and starts a new `ActionQueue` run; the queue's own `retry(action_id)` only exists while a run is in progress.
11. **QSettings object** is `QSettings("ImageAI", "Sprite")` with every key under `sprite/` (the repo uses one application name per feature: `"VideoProjects"`, `"CharacterAnimator"`, …).
12. **Extra tests**: `tests/sprite/test_named_configs.py` sits in `tests/sprite/` (no Qt); `test_sprite_worker.py` and `test_sprite_prefs.py` are additions to the brief's list.
13. **`MainWindow.closeEvent`** gains a `tab_sprite.shutdown()` call (not in the design) so a running render is cancelled and joined before the window is destroyed.
14. **Hooks added for sub-projects 5b and 6** (agreed 2026-08-29): `ActionCardsPanel.actionSelected(str)` and `add_card_action(label, callback)`; `SpriteTab.actionSelected(str)`, `current_action()`, `add_toolbar_action(text, slot)`, `make_provider(name)`. `install_shortcuts` (`gui/sprite/shortcuts.py`) belongs to 5b; `install_retouch` / `install_image_route` to 6 — this plan does not ship them.
