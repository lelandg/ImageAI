### Task 9: Retouch dialog + frame-strip wiring

**Files:**
- Create: `gui/sprite/retouch_dialog.py`
- Create: `gui/sprite/retouch_wiring.py`
- Modify: `gui/sprite/sprite_tab.py` (5a) — one call `install_retouch(self)` at the end of `SpriteTab.__init__`
- Test: `tests/sprite/gui/test_retouch_dialog.py`

**Interfaces:**
- Consumes: `retouch_frame` (Task 8); `DialogCleanupMixin`, `bind_primary_action`, `set_default_button` (`gui/common/dialog_conventions.py:77-141`); `DialogStatusConsole` (`gui/llm_utils.py:15-86`); `SpriteWorker(job, *, label="job", parent=None)` with `progress/finished/failed/cancelled` (5a); `SpriteTab.make_provider(name) -> ImageProvider` (5a; raises `ValueError` with a user-facing message when the key is missing — called inside the worker job so it surfaces through `failed(str)`); `ActionCard`; 5b `FrameStrip.retouchRequested(int)`, `PixelView.selection_rect() -> Optional[Rect]`, `FramesWorkspace.apply_frames(action_id, frames, label)` (snapshot + set frames + refresh); tab attributes `frame_strip`, `pixel_view`, `frames_workspace`, `current_action()`, `current_project`, `console`.
- Produces: `RetouchDialog(DialogCleanupMixin, QDialog)` with `retouched = Signal(object)`, `logLine = Signal(str)`, `build_job()`, `start_retouch()`, `cancel_retouch()`, `clear_region()`, `result_path`; `install_retouch(tab) -> None`; `open_retouch_dialog(tab, index, *, exec_dialog=True) -> Optional[RetouchDialog]`; `apply_retouch(tab, action, index, new_path) -> None`.

Mixin order is `(DialogCleanupMixin, QDialog)` — the mixin's `done()`/`closeEvent()` must precede `QDialog` in the MRO (docstring at `gui/common/dialog_conventions.py:103-141`). Console writes from the worker thread go through the `logLine` signal (queued connection), never directly.

- [ ] **Step 1: Write the failing test**

Create `tests/sprite/gui/test_retouch_dialog.py`:

```python
# tests/sprite/gui/test_retouch_dialog.py
import copy
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("PySide6")
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

from core.sprite.models import FrameMeta
from core.sprite.pipeline import CancelToken, no_progress
from core.sprite.project import ActionCard
from gui.sprite import retouch_dialog as rd
from gui.sprite.retouch_dialog import RetouchDialog
from gui.sprite.retouch_wiring import apply_retouch, install_retouch, open_retouch_dialog
from gui.sprite.workers import SpriteWorker


def _png(path: Path, shade=100) -> Path:
    arr = np.full((16, 16, 4), (shade, shade, shade, 255), dtype=np.uint8)
    Image.fromarray(arr, "RGBA").save(path)
    return path


def _frames(tmp_path):
    return [_png(tmp_path / f"{i:04d}.png") for i in range(1, 4)]


def _dialog(tmp_path, region=None):
    f1, f2, f3 = _frames(tmp_path)
    factory_calls = []

    def factory(name):
        factory_calls.append(name)
        return object()

    dialog = RetouchDialog(f2, [f1, f3], provider_factory=factory, region=region)
    return dialog, factory_calls


def test_dialog_builds_with_console_region_and_shortcut(qapp, tmp_path):
    dialog, _ = _dialog(tmp_path, region=(2, 2, 8, 8))
    assert dialog.console is not None and dialog.region == (2, 2, 8, 8)
    assert "x=2" in dialog.region_label.text() and dialog.clear_region_btn.isEnabled()
    assert [dialog.provider_combo.itemData(i) for i in range(dialog.provider_combo.count())] == ["google", "openai"]
    dialog.clear_region()
    assert dialog.region is None and not dialog.clear_region_btn.isEnabled()


def test_build_job_passes_dialog_values_to_retouch_frame(qapp, tmp_path, monkeypatch):
    dialog, factory_calls = _dialog(tmp_path, region=(1, 1, 4, 4))
    seen = {}

    def fake_retouch(provider, frame, instruction, out_png=None, **kwargs):
        seen.update(kwargs, frame=frame, instruction=instruction)
        return tmp_path / "0002.r1.png"

    monkeypatch.setattr(rd, "retouch_frame", fake_retouch)
    dialog.instruction.setPlainText("fix the hand")
    dialog.provider_combo.setCurrentIndex(1)
    dialog.model_edit.setText("some-model")
    result = dialog.build_job()(no_progress, CancelToken())
    assert result == tmp_path / "0002.r1.png"
    assert factory_calls == ["openai"]
    assert seen["frame"].name == "0002.png" and seen["instruction"] == "fix the hand"
    assert [p.name for p in seen["neighbors"]] == ["0001.png", "0003.png"]
    assert seen["region"] == (1, 1, 4, 4) and seen["model"] == "some-model"


def test_start_retouch_runs_worker_and_emits(qapp, tmp_path, monkeypatch):
    dialog, _ = _dialog(tmp_path)
    out = tmp_path / "0002.r1.png"
    monkeypatch.setattr(rd, "retouch_frame", lambda *a, **k: out)
    monkeypatch.setattr(SpriteWorker, "start", SpriteWorker.run)     # synchronous in-test
    got = []
    dialog.retouched.connect(lambda p: got.append(Path(p)))
    dialog.instruction.setPlainText("x")
    dialog.start_retouch()
    assert got == [out] and dialog.result_path == out
    assert dialog.run_btn.isEnabled() and not dialog.cancel_btn.isEnabled()
    assert "saved" in dialog.console.console.toPlainText().lower()


def test_failure_is_logged_to_console(qapp, tmp_path, monkeypatch):
    dialog, _ = _dialog(tmp_path)

    def boom(*a, **k):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(rd, "retouch_frame", boom)
    monkeypatch.setattr(SpriteWorker, "start", SpriteWorker.run)
    dialog.instruction.setPlainText("x")
    dialog.start_retouch()
    assert "exploded" in dialog.console.console.toPlainText()
    assert dialog.run_btn.isEnabled()


def test_empty_instruction_blocks_run(qapp, tmp_path, monkeypatch):
    dialog, _ = _dialog(tmp_path)
    monkeypatch.setattr(rd, "retouch_frame", lambda *a, **k: pytest.fail("must not run"))
    dialog.start_retouch()
    assert "instruction" in dialog.console.console.toPlainText().lower()


class _Strip(QObject):
    retouchRequested = Signal(int)


class _FakeTab(QWidget):
    """The SpriteTab surface that retouch_wiring touches (5a/5b names)."""

    def __init__(self, action, region=None):
        super().__init__()
        self.frame_strip = _Strip()
        self.pixel_view = SimpleNamespace(selection_rect=lambda: region)
        self.frames_workspace = SimpleNamespace(apply_frames=self._apply_frames)
        self._action = action
        self.current_project = SimpleNamespace(project_dir=None, save=lambda: None)
        self.console = SimpleNamespace(log=lambda *a, **k: None)
        self.applied = []
        self.providers = []

    def _apply_frames(self, action_id, frames, label):
        assert action_id == self._action.id
        self._action.frames = list(frames)
        self.applied.append(label)

    def current_action(self):
        return self._action

    def make_provider(self, name="google"):
        self.providers.append(name)
        return object()


def _action(tmp_path):
    frames = [FrameMeta(name=f"hero_walk_{i:02d}", source_path=p, frame=(0, 0, 16, 16))
              for i, p in enumerate(_frames(tmp_path), start=1)]
    return ActionCard(id="a1", name="walk", prompt="walks", frames=frames)


def test_apply_retouch_repoints_a_copy_through_workspace(qapp, tmp_path):
    action = _action(tmp_path)
    tab = _FakeTab(action)
    original_frame = action.frames[1]
    before = copy.deepcopy(original_frame)
    new_path = tmp_path / "0002.r1.png"
    apply_retouch(tab, action, 1, new_path)
    assert action.frames[1].source_path == new_path
    assert original_frame.source_path == before.source_path      # the old list is untouched for the snapshot
    assert tab.applied == ["retouch 2"]


def test_open_retouch_dialog_collects_neighbors_region_and_provider_factory(qapp, tmp_path):
    action = _action(tmp_path)
    tab = _FakeTab(action, region=(3, 3, 5, 5))
    dialog = open_retouch_dialog(tab, 2, exec_dialog=False)
    assert dialog.frame.name == "0003.png"
    assert [p.name for p in dialog.neighbors] == ["0002.png"]
    assert dialog.region == (3, 3, 5, 5)
    dialog._provider_factory("openai")
    assert tab.providers == ["openai"]
    assert open_retouch_dialog(tab, 7, exec_dialog=False) is None


def test_install_retouch_connects_signal(qapp, tmp_path, monkeypatch):
    tab = _FakeTab(_action(tmp_path))
    calls = []
    monkeypatch.setattr("gui.sprite.retouch_wiring.open_retouch_dialog", lambda t, i, **k: calls.append(i))
    install_retouch(tab)
    tab.frame_strip.retouchRequested.emit(1)
    assert calls == [1]
```

- [ ] **Step 2: Run the test to see it fail**

`QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui/test_retouch_dialog.py -v` → `ModuleNotFoundError: gui.sprite.retouch_dialog`.

- [ ] **Step 3: Implement the dialog**

Create `gui/sprite/retouch_dialog.py`:

```python
"""Retouch dialog: one frame, one instruction, one provider call in a SpriteWorker."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, List, Optional, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from core.sprite.generation.retouch import retouch_frame
from core.sprite.models import Rect
from core.sprite.pipeline import CancelToken, ProgressFn
from gui.common.dialog_conventions import DialogCleanupMixin, bind_primary_action, set_default_button
from gui.llm_utils import DialogStatusConsole
from gui.sprite.workers import SpriteWorker

logger = logging.getLogger(__name__)

PROVIDERS = (("google", "Google Gemini"), ("openai", "OpenAI gpt-image"))


class RetouchDialog(DialogCleanupMixin, QDialog):
    """Ctrl+Enter runs the retouch; Escape closes. Never overwrites the source frame."""

    retouched = Signal(object)   # Path of the new frame file
    logLine = Signal(str)        # worker-thread log lines -> console (queued)

    def __init__(self, frame: Path, neighbors: Sequence[Path], *,
                 provider_factory: Callable[[str], object], region: Optional[Rect] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.frame = Path(frame)
        self.neighbors: List[Path] = [Path(n) for n in neighbors]
        self.region: Optional[Rect] = tuple(region) if region else None
        self._provider_factory = provider_factory
        self._worker: Optional[SpriteWorker] = None
        self.result_path: Optional[Path] = None
        self.setWindowTitle(f"Retouch {self.frame.name}")
        self._build_ui()
        self.logLine.connect(self.console.log)

    # ----------------------------------------------------------------- ui
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Vertical, self)
        top = QWidget()
        form = QFormLayout(top)
        self.instruction = QPlainTextEdit()
        self.instruction.setPlaceholderText("What to change in this frame, e.g. 'fix the left hand: five fingers, same glove'")
        form.addRow("Instruction:", self.instruction)
        self.provider_combo = QComboBox()
        for pid, label in PROVIDERS:
            self.provider_combo.addItem(label, pid)
        form.addRow("Provider:", self.provider_combo)
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("provider default")
        form.addRow("Model:", self.model_edit)
        region_row = QHBoxLayout()
        self.region_label = QLabel(self._region_text())
        self.clear_region_btn = QPushButton("Clear region")
        self.clear_region_btn.setEnabled(self.region is not None)
        self.clear_region_btn.clicked.connect(self.clear_region)
        region_row.addWidget(self.region_label, 1)
        region_row.addWidget(self.clear_region_btn)
        form.addRow("Region:", region_row)
        form.addRow("Neighbors:", QLabel(", ".join(p.name for p in self.neighbors) or "(none)"))
        splitter.addWidget(top)
        self.console = DialogStatusConsole("Status Console", self)
        splitter.addWidget(self.console)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.run_btn = QPushButton("Retouch (Ctrl+Enter)")
        self.run_btn.clicked.connect(self.start_retouch)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_retouch)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        for button in (self.run_btn, self.cancel_btn, self.close_btn):
            buttons.addWidget(button)
        root.addLayout(buttons)
        self._primary = bind_primary_action(self, self.start_retouch)
        set_default_button(self, self.run_btn, focus=False)
        self.instruction.setFocus()
        self.resize(560, 480)

    def _region_text(self) -> str:
        if self.region is None:
            return "whole frame"
        x, y, w, h = self.region
        return f"x={x} y={y} w={w} h={h}"

    def clear_region(self) -> None:
        self.region = None
        self.region_label.setText(self._region_text())
        self.clear_region_btn.setEnabled(False)

    # ----------------------------------------------------------------- job
    def build_job(self) -> Callable[[ProgressFn, CancelToken], Path]:
        instruction = self.instruction.toPlainText().strip()
        provider_id = self.provider_combo.currentData()
        model = self.model_edit.text().strip() or None
        frame, neighbors, region = self.frame, list(self.neighbors), self.region
        factory = self._provider_factory
        console_log = self.logLine.emit

        def job(progress: ProgressFn, token: CancelToken) -> Path:
            progress("retouch", 0, 1, f"Retouching {frame.name} with {provider_id}")
            token.raise_if_cancelled()
            provider = factory(provider_id)
            out = retouch_frame(provider, frame, instruction, neighbors=neighbors, region=region,
                                model=model, log=console_log)
            progress("retouch", 1, 1, f"Saved {out.name}")
            return out

        return job

    def start_retouch(self) -> None:
        if self._worker is not None:
            self.console.log("A retouch is already running.", "WARNING")
            return
        if not self.instruction.toPlainText().strip():
            logger.warning("retouch: empty instruction")
            self.console.log("Enter an instruction first.", "WARNING")
            return
        self._worker = SpriteWorker(self.build_job(), parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.console.log(f"Retouch started: {self.frame.name}")
        self._worker.start()

    def cancel_retouch(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.console.log("Cancel requested", "WARNING")

    def _on_progress(self, stage: str, done: int, total: int, message: str) -> None:
        self.console.log(f"[{stage}] {message}")

    def _on_finished(self, result) -> None:
        self.result_path = Path(result)
        self.console.log(f"Retouch saved: {self.result_path}", "SUCCESS")
        self._finish_worker()
        self.retouched.emit(self.result_path)

    def _on_failed(self, message: str) -> None:
        logger.error("retouch failed: %s", message)
        self.console.log(f"Retouch failed: {message}", "ERROR")
        self._finish_worker()

    def _on_cancelled(self) -> None:
        logger.info("retouch cancelled: %s", self.frame.name)
        self.console.log("Retouch cancelled.", "WARNING")
        self._finish_worker()

    def _finish_worker(self) -> None:
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._worker = None

    def on_dialog_close(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait(2000)
            self._worker = None
```

- [ ] **Step 4: Implement the wiring**

Create `gui/sprite/retouch_wiring.py`:

```python
"""Connect FrameStrip.retouchRequested to the RetouchDialog and apply the result with undo."""
from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Optional

from core.sprite.project import ActionCard
from gui.sprite.retouch_dialog import RetouchDialog

logger = logging.getLogger(__name__)


def apply_retouch(tab, action: ActionCard, index: int, new_path: Path) -> None:
    """Repoint one frame in a copied list through FramesWorkspace.apply_frames (snapshot + set + refresh).

    The copy matters: apply_frames snapshots the current list for undo before it installs the new one.
    """
    frames = copy.deepcopy(action.frames)
    frames[index].source_path = Path(new_path)
    tab.frames_workspace.apply_frames(action.id, frames, f"retouch {index + 1}")
    project = tab.current_project
    if project is not None and getattr(project, "project_dir", None) is not None:
        project.save()
    tab.console.log(f"Frame {index + 1} retouched -> {Path(new_path).name}", "SUCCESS")
    logger.info("retouch applied: action=%s frame=%d -> %s", action.name, index + 1, new_path)


def open_retouch_dialog(tab, index: int, *, exec_dialog: bool = True) -> Optional[RetouchDialog]:
    action = tab.current_action()
    if action is None or not (0 <= index < len(action.frames)) or action.frames[index].source_path is None:
        logger.warning("retouch: no frame at index %s", index)
        tab.console.log("Retouch: select a frame first.", "WARNING")
        return None
    frames = action.frames
    neighbors = [frames[i].source_path for i in (index - 1, index + 1)
                 if 0 <= i < len(frames) and frames[i].source_path is not None]
    region = tab.pixel_view.selection_rect()
    dialog = RetouchDialog(frames[index].source_path, neighbors, provider_factory=tab.make_provider,
                           region=region, parent=tab)
    dialog.retouched.connect(lambda path, a=action, i=index: apply_retouch(tab, a, i, Path(path)))
    if exec_dialog:
        dialog.exec()
    return dialog


def install_retouch(tab) -> None:
    """Call once from SpriteTab.__init__."""
    tab.frame_strip.retouchRequested.connect(lambda index: open_retouch_dialog(tab, index))
```

- [ ] **Step 5: Wire the tab (5a file)**

Modify `gui/sprite/sprite_tab.py`: add `from gui.sprite.retouch_wiring import install_retouch` and, as the last statement of `SpriteTab.__init__` (after 5b's `FramesWorkspace` has set `frame_strip` / `pixel_view` / `frames_workspace` on the tab), `install_retouch(self)`. The region comes from 5b's `PixelView.selection_rect()`; sub-project 6 adds no selection UI.

- [ ] **Step 6: Run the tests to see them pass**

`QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/gui -v` → 9 new tests pass; the 5a/5b tab, strip, and pixel-view tests still pass.

- [ ] **Step 7: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add gui/sprite/retouch_dialog.py gui/sprite/retouch_wiring.py gui/sprite/sprite_tab.py tests/sprite/gui/test_retouch_dialog.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): Retouch dialog (status console, Ctrl+Enter, SpriteWorker) wired to the frame strip with undo"
```

---

