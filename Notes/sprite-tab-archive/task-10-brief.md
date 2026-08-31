### Task 10: Action-cards "Render (image)" button + ImageRouteDialog

**Files:**
- Create: `gui/sprite/image_route_dialog.py`
- Modify: `gui/sprite/sprite_tab.py` — one call `install_image_route(self)` at the end of `SpriteTab.__init__`
- Test: `tests/sprite/gui/test_image_route_dialog.py`

**Interfaces:**
- Consumes: `generate_sheet`, `slice_generated_sheet`, `edit_chain`, `generate_pose_instructions`, `default_openai_edit_model` (Tasks 5-7); `run_pipeline(project, action, *, upto, progress, token)`, `stage_dir(project, action, stage)`, `CancelToken`, `ProgressFn`; `record_actual(project, action, usd, note="", *, provider, model, seconds, estimated_usd)` (sub-project 2); `FrameMeta`, `ActionCard`, `SpriteProject`; `SpriteWorker` (+ `cancelled`); 5a `ActionCardsPanel.add_card_action(label, callback)`, `ActionCardsPanel.llm_provider() -> str`, `ActionCardsPanel.refresh_status()`; `SpriteTab.{make_provider(name), config, console, action_cards_panel, current_project, current_action()}`; 5b `FramesWorkspace.apply_frames(action_id, frames, label)` via `tab.frames_workspace`; `config.get_api_key(provider)`, `config.get_auth_mode(provider)`.
- Produces: `ImageRouteDialog(DialogCleanupMixin, QDialog)` with `rendered = Signal(object)`, `logLine = Signal(str)`, `build_job()`, `start_render()`, `cancel_render()`, `generate_steps()`; `archive_existing_frames(extract_dir: Path) -> Optional[Path]`; `install_image_route(tab) -> None`; `open_image_route_dialog(tab, action, *, exec_dialog=True) -> Optional[ImageRouteDialog]`.

The dialog calls providers and an LLM, so it carries a `DialogStatusConsole` at the bottom (splitter), Ctrl+Enter = Render, Escape = close. The job writes frames into `stage_dir(project, action, "extract")` with `action.clip = None` (the G9 pre-extracted entry point), records a ledger row, then runs `run_pipeline(upto="stabilize")` like the video queue.

- [ ] **Step 1: Write the failing test**

Create `tests/sprite/gui/test_image_route_dialog.py`:

```python
# tests/sprite/gui/test_image_route_dialog.py
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QWidget

from core.sprite.models import FrameMeta
from core.sprite.pipeline import CancelToken, no_progress
from core.sprite.project import ActionCard, SpriteProject
from gui.sprite import image_route_dialog as ird
from gui.sprite.image_route_dialog import ImageRouteDialog, archive_existing_frames, install_image_route
from gui.sprite.workers import SpriteWorker


def _png(path: Path) -> Path:
    Image.fromarray(np.zeros((16, 16, 4), dtype=np.uint8), "RGBA").save(path)
    return path


def _project(tmp_path):
    project = MagicMock(spec=SpriteProject)
    project.name = "hero"
    project.project_dir = tmp_path
    project.plate_path = None
    project.character_source = _png(tmp_path / "character.png")
    project.plate_color = "#00FF00"
    return project


def _action():
    return ActionCard(id="a1", name="walk", prompt="walks", duration_s=4, loop=True, target_frames=3, fps=12)


def _patch_core(monkeypatch, tmp_path, produced):
    extract_dir = tmp_path / "stages" / "a1" / "extracted"
    monkeypatch.setattr(ird, "stage_dir", lambda project, action, stage: extract_dir)
    monkeypatch.setattr(ird, "generate_sheet", lambda *a, **k: tmp_path / "sheet.png")
    monkeypatch.setattr(ird, "slice_generated_sheet", lambda *a, **k: produced)
    monkeypatch.setattr(ird, "edit_chain", MagicMock(return_value=produced))
    monkeypatch.setattr(ird, "run_pipeline", MagicMock(return_value={}))
    monkeypatch.setattr(ird, "record_actual", MagicMock())
    return extract_dir


def _fake_provider(name="google"):
    return SimpleNamespace(get_default_model=lambda: "default-image-model")


def _dialog(tmp_path, pose_fn=None):
    return ImageRouteDialog(_project(tmp_path), _action(), provider_factory=_fake_provider,
                            pose_fn=pose_fn or (lambda action, frames, log: [f"pose {k}" for k in range(1, frames + 1)]))


def test_dialog_defaults_and_mode_toggle(qapp, tmp_path):
    dialog = _dialog(tmp_path)
    assert dialog.frames_spin.value() == 3
    assert [dialog.mode_combo.itemData(i) for i in range(dialog.mode_combo.count())] == ["sheet", "edit_chain"]
    assert not dialog.matte_check.isEnabled() and not dialog.steps_edit.isEnabled()
    dialog.mode_combo.setCurrentIndex(1)
    assert dialog.matte_check.isEnabled() and dialog.steps_edit.isEnabled()
    assert dialog.console is not None


def test_sheet_job_fills_frames_and_runs_pipeline(qapp, tmp_path, monkeypatch):
    produced = [_png(tmp_path / f"{k:04d}.png") for k in (1, 2, 3)]
    _patch_core(monkeypatch, tmp_path, produced)
    dialog = _dialog(tmp_path)
    result = dialog.build_job()(no_progress, CancelToken())
    action = dialog.action
    assert result == produced
    assert [f.source_path for f in action.frames] == produced
    assert action.frames[0].duration_ms == round(1000 / 12)
    assert action.clip is None and action.status == "processed"
    ird.run_pipeline.assert_called_once()
    assert ird.run_pipeline.call_args.kwargs["upto"] == "stabilize"
    ird.record_actual.assert_called_once()
    ledger_kwargs = ird.record_actual.call_args.kwargs
    assert "image route sheet" in ledger_kwargs["note"]
    assert ledger_kwargs["provider"] == "google" and ledger_kwargs["model"] == "default-image-model"
    assert ledger_kwargs["seconds"] == 3.0                     # unit count = frames for the sheet route
    dialog.project.save.assert_called_once()


def test_edit_chain_job_uses_typed_steps_when_count_matches(qapp, tmp_path, monkeypatch):
    produced = [_png(tmp_path / f"{k:04d}.png") for k in (1, 2, 3)]
    _patch_core(monkeypatch, tmp_path, produced)
    pose_calls = []
    dialog = _dialog(tmp_path, pose_fn=lambda a, n, log: pose_calls.append(n) or ["x"] * n)
    dialog.mode_combo.setCurrentIndex(1)
    dialog.matte_check.setChecked(True)
    dialog.steps_edit.setPlainText("one\ntwo\nthree")
    dialog.build_job()(no_progress, CancelToken())
    assert pose_calls == []
    kwargs = ird.edit_chain.call_args.kwargs
    assert kwargs["pose_instructions"] == ["one", "two", "three"] and kwargs["matte_pairs"] is True
    assert kwargs["frames"] == 3 and kwargs["plate_color"] == "#00FF00"


def test_edit_chain_job_asks_llm_when_steps_missing(qapp, tmp_path, monkeypatch):
    produced = [_png(tmp_path / f"{k:04d}.png") for k in (1, 2, 3)]
    _patch_core(monkeypatch, tmp_path, produced)
    pose_calls = []
    dialog = _dialog(tmp_path, pose_fn=lambda a, n, log: pose_calls.append(n) or [f"p{k}" for k in range(n)])
    dialog.mode_combo.setCurrentIndex(1)
    dialog.build_job()(no_progress, CancelToken())
    assert pose_calls == [3]
    assert ird.edit_chain.call_args.kwargs["pose_instructions"] == ["p0", "p1", "p2"]


def test_generate_steps_button_fills_editor(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(SpriteWorker, "start", SpriteWorker.run)
    dialog = _dialog(tmp_path)
    dialog.mode_combo.setCurrentIndex(1)
    dialog.generate_steps()
    assert dialog.steps_edit.toPlainText().splitlines() == ["pose 1", "pose 2", "pose 3"]


def test_start_render_emits_rendered(qapp, tmp_path, monkeypatch):
    produced = [_png(tmp_path / f"{k:04d}.png") for k in (1, 2, 3)]
    _patch_core(monkeypatch, tmp_path, produced)
    monkeypatch.setattr(SpriteWorker, "start", SpriteWorker.run)
    dialog = _dialog(tmp_path)
    got = []
    dialog.rendered.connect(lambda paths: got.append(list(paths)))
    dialog.start_render()
    assert got == [produced] and dialog.render_btn.isEnabled()
    assert "3 frame" in dialog.console.console.toPlainText()


def test_missing_character_fails_cleanly(qapp, tmp_path, monkeypatch):
    produced = []
    _patch_core(monkeypatch, tmp_path, produced)
    monkeypatch.setattr(SpriteWorker, "start", SpriteWorker.run)
    dialog = _dialog(tmp_path)
    dialog.project.character_source = tmp_path / "missing.png"
    dialog.start_render()
    assert "character" in dialog.console.console.toPlainText().lower()
    assert dialog.render_btn.isEnabled()


def test_archive_existing_frames_moves_aside(tmp_path):
    extract = tmp_path / "extracted"
    extract.mkdir()
    _png(extract / "0001.png")
    archived = archive_existing_frames(extract)
    assert archived is not None and archived.parent == tmp_path and (archived / "0001.png").exists()
    assert not extract.exists()
    assert archive_existing_frames(tmp_path / "nope") is None


class _FakeConfig:
    """Mirror of 5a's FakeConfig: get/set/save/get_api_key/get_auth_mode."""

    def __init__(self):
        self.store = {}

    def get(self, key, default=None):
        return self.store.get(key, default)

    def set(self, key, value):
        self.store[key] = value

    def save(self):
        return True

    def get_api_key(self, provider):
        return "test-key"

    def get_auth_mode(self, provider="google"):
        return "api-key"


class _FakeTab(QWidget):
    """The SpriteTab surface that image_route_dialog touches (5a/5b names)."""

    def __init__(self, tmp_path, action=None):
        super().__init__()
        self.actions = {}
        self.action_cards_panel = SimpleNamespace(
            add_card_action=lambda label, cb: self.actions.__setitem__(label, cb),
            llm_provider=lambda: "google",
            refresh_status=lambda: None)
        self.config = _FakeConfig()
        self.console = SimpleNamespace(log=lambda *a, **k: None)
        self.current_project = _project(tmp_path)
        self._action = action
        self.applied = []
        self.providers = []
        self.frames_workspace = SimpleNamespace(apply_frames=self._apply_frames)

    def _apply_frames(self, action_id, frames, label):
        # Record what the real FramesWorkspace.apply_frames would snapshot (current list) and install (new list).
        self.applied.append((action_id, label, len(self._action.frames), len(frames)))
        self._action.frames = list(frames)

    def current_action(self):
        return self._action

    def make_provider(self, name="google"):
        self.providers.append(name)
        return _fake_provider(name)


def test_install_image_route_registers_button_and_builds_dialog(qapp, tmp_path):
    action = _action()
    tab = _FakeTab(tmp_path, action)
    install_image_route(tab)
    assert "Render (image)" in tab.actions
    dialog = ird.open_image_route_dialog(tab, action, exec_dialog=False)
    assert isinstance(dialog, ImageRouteDialog)
    assert dialog._provider_factory == tab.make_provider
    # Simulate a finished job: the worker wrote the new frames onto the action; the dialog kept the old list.
    dialog.frames_before = []
    action.frames = [FrameMeta(name="hero_walk_01", source_path=_png(tmp_path / "0001.png"), frame=(0, 0, 0, 0))]
    dialog.rendered.emit([])
    assert tab.applied == [("a1", "Render (image)", 0, 1)]   # snapshot sees the pre-render list, new list installed
    assert len(action.frames) == 1


def test_rendered_for_another_action_only_refreshes_status(qapp, tmp_path):
    other = ActionCard(id="zz", name="idle", prompt="stands", duration_s=2, loop=True, target_frames=2, fps=12)
    tab = _FakeTab(tmp_path, _action())
    dialog = ird.open_image_route_dialog(tab, other, exec_dialog=False)
    dialog.rendered.emit([])
    assert tab.applied == []


def test_pose_fn_uses_panel_provider_and_config(qapp, tmp_path, monkeypatch):
    seen = {}

    def fake_generate(action, frames, **kwargs):
        seen.update(kwargs, frames=frames)
        return ["p"] * frames

    monkeypatch.setattr(ird, "generate_pose_instructions", fake_generate)
    tab = _FakeTab(tmp_path, _action())
    steps = ird._make_pose_fn(tab)(_action(), 3, lambda _m: None)
    assert steps == ["p", "p", "p"]
    assert seen["provider"] == "google" and seen["api_key"] == "test-key" and seen["auth_mode"] == "api-key"
    assert seen["model"] is None


```

- [ ] **Step 2: Run the test to see it fail**

`QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_image_route_dialog.py -v` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement the dialog and install hook**

Create `gui/sprite/image_route_dialog.py`:

```python
"""Render one action card through the image route (sheet or edit-chain) in a SpriteWorker."""
from __future__ import annotations

import copy
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLineEdit, QPlainTextEdit,
    QPushButton, QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

from core.sprite.generation.cost import record_actual
from core.sprite.generation.errors import ProviderError
from core.sprite.generation.image_route import (
    default_openai_edit_model, edit_chain, generate_pose_instructions, generate_sheet,
    slice_generated_sheet,
)
from core.sprite.models import FrameMeta
from core.sprite.pipeline import CancelToken, ProgressFn, run_pipeline, stage_dir
from core.sprite.project import ActionCard, SpriteProject
from gui.common.dialog_conventions import DialogCleanupMixin, bind_primary_action, set_default_button
from gui.llm_utils import DialogStatusConsole
from gui.sprite.workers import SpriteWorker

logger = logging.getLogger(__name__)

PROVIDERS = (("google", "Google Gemini"), ("openai", "OpenAI gpt-image"))
MODES = (("sheet", "Sheet (one image, sliced)"), ("edit_chain", "Edit chain (one edit per frame)"))
PoseFn = Callable[[ActionCard, int, Callable[[str], None]], List[str]]


def archive_existing_frames(extract_dir: Path) -> Optional[Path]:
    """Move a populated extract directory aside instead of deleting it; return the archive path."""
    extract_dir = Path(extract_dir)
    if not extract_dir.exists() or not any(extract_dir.iterdir()):
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive = extract_dir.with_name(f"{extract_dir.name}.prev-{stamp}")
    extract_dir.rename(archive)
    logger.info("archived previous frames: %s -> %s", extract_dir, archive)
    return archive


class ImageRouteDialog(DialogCleanupMixin, QDialog):
    rendered = Signal(object)   # List[Path]
    logLine = Signal(str)

    def __init__(self, project: SpriteProject, action: ActionCard, *,
                 provider_factory: Callable[[str], object], pose_fn: PoseFn,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.project = project
        self.action = action
        self._provider_factory = provider_factory
        self._pose_fn = pose_fn
        self._worker: Optional[SpriteWorker] = None
        self.frames_before: List[FrameMeta] = []     # pre-render frame list; restored before apply_frames snapshots
        self.setWindowTitle(f"Render (image) — {action.name}")
        self._build_ui()
        self.logLine.connect(self.console.log)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Vertical, self)
        top = QWidget()
        form = QFormLayout(top)
        self.mode_combo = QComboBox()
        for mid, label in MODES:
            self.mode_combo.addItem(label, mid)
        form.addRow("Mode:", self.mode_combo)
        self.provider_combo = QComboBox()
        for pid, label in PROVIDERS:
            self.provider_combo.addItem(label, pid)
        form.addRow("Provider:", self.provider_combo)
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("provider default")
        form.addRow("Model:", self.model_edit)
        self.frames_spin = QSpinBox()
        self.frames_spin.setRange(2, 24)
        self.frames_spin.setValue(max(2, min(24, self.action.target_frames)))
        form.addRow("Frames:", self.frames_spin)
        self.matte_check = QCheckBox("Render white + black plates and difference-matte (2x cost)")
        form.addRow("", self.matte_check)
        steps_row = QHBoxLayout()
        self.steps_edit = QPlainTextEdit()
        self.steps_edit.setPlaceholderText("One pose per line (edit-chain). Leave empty to ask the LLM.")
        self.steps_btn = QPushButton("Generate pose steps")
        self.steps_btn.clicked.connect(self.generate_steps)
        steps_row.addWidget(self.steps_edit, 1)
        steps_row.addWidget(self.steps_btn)
        form.addRow("Pose steps:", steps_row)
        splitter.addWidget(top)
        self.console = DialogStatusConsole("Status Console", self)
        splitter.addWidget(self.console)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.render_btn = QPushButton("Render (Ctrl+Enter)")
        self.render_btn.clicked.connect(self.start_render)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_render)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        for button in (self.render_btn, self.cancel_btn, self.close_btn):
            buttons.addWidget(button)
        root.addLayout(buttons)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._on_mode_changed(0)
        self._primary = bind_primary_action(self, self.start_render)
        set_default_button(self, self.render_btn)
        self.resize(640, 560)

    def _on_mode_changed(self, _index: int) -> None:
        chain = self.mode_combo.currentData() == "edit_chain"
        self.matte_check.setEnabled(chain)
        self.steps_edit.setEnabled(chain)
        self.steps_btn.setEnabled(chain)

    # ----------------------------------------------------------------- jobs
    def _typed_steps(self) -> List[str]:
        return [line.strip() for line in self.steps_edit.toPlainText().splitlines() if line.strip()]

    def generate_steps(self) -> None:
        """Fill the pose-step editor from the LLM contract (runs in a worker)."""
        if self._worker is not None:
            self.console.log("A job is already running.", "WARNING")
            return
        action, frames, pose_fn, log = self.action, self.frames_spin.value(), self._pose_fn, self.logLine.emit

        def job(progress: ProgressFn, token: CancelToken) -> List[str]:
            progress("pose_steps", 0, 1, f"Asking the LLM for {frames} pose steps")
            token.raise_if_cancelled()
            return pose_fn(action, frames, log)

        self._worker = SpriteWorker(job, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_steps_ready)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._set_running(True)
        self._worker.start()

    def _on_steps_ready(self, steps) -> None:
        self.steps_edit.setPlainText("\n".join(steps))
        self.console.log(f"{len(steps)} pose steps ready; edit them, then Render.", "SUCCESS")
        self._set_running(False)

    def build_job(self) -> Callable[[ProgressFn, CancelToken], List[Path]]:
        mode = self.mode_combo.currentData()
        provider_id = self.provider_combo.currentData()
        model = self.model_edit.text().strip() or None
        frames = self.frames_spin.value()
        matte = self.matte_check.isChecked() and mode == "edit_chain"
        typed_steps = self._typed_steps()
        project, action = self.project, self.action
        factory, pose_fn, log = self._provider_factory, self._pose_fn, self.logLine.emit

        def job(progress: ProgressFn, token: CancelToken) -> List[Path]:
            character = project.plate_path or project.character_source
            if character is None or not Path(character).exists():
                raise ProviderError("Import a character image first (Character panel).")
            provider = factory(provider_id)
            model_used = model or (default_openai_edit_model() if provider_id == "openai"
                                   else provider.get_default_model())
            extract_dir = stage_dir(project, action, "extract")
            archived = archive_existing_frames(extract_dir)
            if archived is not None:
                log(f"[image route] previous frames kept at {archived}")
            if mode == "sheet":
                progress("image_route", 0, 3, "Generating sheet")
                sheet_png = Path(project.project_dir) / "clips" / f"{action.id}_sheet.png"
                sheet = generate_sheet(provider, Path(character), action, sheet_png, frames=frames,
                                       plate_color=project.plate_color, model=model, log=log, token=token)
                progress("image_route", 1, 3, "Slicing sheet")
                paths = slice_generated_sheet(sheet, extract_dir, frames, project.plate_color, log=log)
            else:
                steps = typed_steps
                if len(steps) != frames:
                    progress("image_route", 0, 3, f"Generating {frames} pose steps")
                    steps = pose_fn(action, frames, log)
                progress("image_route", 1, 3, f"Edit chain: {frames} steps")
                paths = edit_chain(provider, Path(character), action, extract_dir, frames=frames,
                                   pose_instructions=steps, plate_color=project.plate_color, model=model,
                                   log=log, token=token, matte_pairs=matte)
            progress("image_route", 2, 3, "Running pipeline to stabilize")
            duration_ms = round(1000 / max(1, action.fps))
            action.frames = [
                FrameMeta(name=f"{project.name}_{action.name}_{i:02d}", source_path=p, frame=(0, 0, 0, 0),
                          duration_ms=duration_ms)
                for i, p in enumerate(paths, start=1)
            ]
            action.clip = None
            action.status = "rendered"
            action.error = None
            edits = len(paths) * (2 if matte else 1)
            record_actual(project, action, None,
                          note=f"image route {mode}: {len(paths)} frame(s), {edits} edit(s)",
                          provider=provider_id, model=model_used, seconds=float(edits))
            run_pipeline(project, action, upto="stabilize", progress=progress, token=token)
            action.status = "processed"
            project.save()
            progress("image_route", 3, 3, f"{len(paths)} frame(s) ready")
            return paths

        return job

    def start_render(self) -> None:
        if self._worker is not None:
            self.console.log("A job is already running.", "WARNING")
            return
        self.frames_before = copy.deepcopy(self.action.frames)
        self._worker = SpriteWorker(self.build_job(), parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_rendered)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._set_running(True)
        self.console.log(f"Image route started: {self.action.name} ({self.mode_combo.currentData()})")
        self._worker.start()

    def cancel_render(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.console.log("Cancel requested", "WARNING")

    def _on_progress(self, stage: str, done: int, total: int, message: str) -> None:
        self.console.log(f"[{stage}] {done}/{total} {message}")

    def _on_rendered(self, paths) -> None:
        paths = list(paths)
        self.console.log(f"Rendered {len(paths)} frame(s) for {self.action.name}", "SUCCESS")
        self._set_running(False)
        self.rendered.emit(paths)

    def _on_failed(self, message: str) -> None:
        logger.error("image route failed: %s", message)
        self.console.log(f"Failed: {message}", "ERROR")
        self._set_running(False)

    def _on_cancelled(self) -> None:
        logger.info("image route cancelled: %s", self.action.name)
        self.console.log("Cancelled.", "WARNING")
        self._set_running(False)

    def _set_running(self, running: bool) -> None:
        self.render_btn.setEnabled(not running)
        self.steps_btn.setEnabled(not running and self.mode_combo.currentData() == "edit_chain")
        self.cancel_btn.setEnabled(running)
        if not running:
            self._worker = None

    def on_dialog_close(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait(2000)
            self._worker = None


# --------------------------------------------------------------------- tab wiring

def _make_pose_fn(tab) -> PoseFn:
    """Pose steps use the chat provider chosen in the action-cards panel; the model comes from the registry."""
    def pose_fn(action: ActionCard, frames: int, log: Callable[[str], None]) -> List[str]:
        provider = tab.action_cards_panel.llm_provider()
        auth_mode = tab.config.get_auth_mode(provider) if provider in ("google", "gemini") else None
        return generate_pose_instructions(action, frames, provider=provider, model=None,
                                          api_key=tab.config.get_api_key(provider), auth_mode=auth_mode, log=log)
    return pose_fn


def _on_rendered(tab, action: ActionCard, dialog: ImageRouteDialog) -> None:
    """Refresh the card status; reload strip + player when the rendered action is the current one.

    The job already wrote ``action.frames``. ``apply_frames`` snapshots the current list for
    undo before it installs the new one, so restore the pre-render list first and hand the
    rendered list over as the new one.
    """
    tab.action_cards_panel.refresh_status()
    current = tab.current_action()
    if current is not None and current.id == action.id:
        rendered = list(action.frames)
        action.frames = list(dialog.frames_before)
        tab.frames_workspace.apply_frames(action.id, rendered, "Render (image)")
    tab.console.log(f"Image route: '{action.name}' has {len(action.frames)} frame(s)", "SUCCESS")


def open_image_route_dialog(tab, action: ActionCard, *, exec_dialog: bool = True) -> Optional[ImageRouteDialog]:
    project = tab.current_project
    if project is None:
        logger.warning("image route: no project open")
        tab.console.log("Open or create a sprite project first.", "WARNING")
        return None
    dialog = ImageRouteDialog(project, action, provider_factory=tab.make_provider,
                              pose_fn=_make_pose_fn(tab), parent=tab)
    dialog.rendered.connect(lambda _paths, a=action, d=dialog: _on_rendered(tab, a, d))
    if exec_dialog:
        dialog.exec()
    return dialog


def install_image_route(tab) -> None:
    """Call once from SpriteTab.__init__: adds "Render (image)" to every action card row."""
    tab.action_cards_panel.add_card_action("Render (image)", lambda action: open_image_route_dialog(tab, action))
```

- [ ] **Step 4: Wire the tab (5a file)**

Modify `gui/sprite/sprite_tab.py`: add `from gui.sprite.image_route_dialog import install_image_route` and `install_image_route(self)` right after `install_retouch(self)` at the end of `SpriteTab.__init__`. 5a's `ActionCardsPanel.add_card_action` renders the button on existing and future rows.

- [ ] **Step 5: Run the tests to see them pass**

`QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui -v` → 11 new tests pass; `tests/sprite/gui/test_action_cards_panel.py` (5a) still passes.

- [ ] **Step 6: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/image_route_dialog.py gui/sprite/sprite_tab.py tests/sprite/gui/test_image_route_dialog.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): Render (image) card action with sheet/edit-chain dialog, pose steps, and pipeline hand-off"
```

---

