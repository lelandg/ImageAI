# tests/sprite/gui/test_retouch_dialog.py
import copy
import threading
import time
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("PySide6")
from PySide6.QtCore import QObject, Signal
from PySide6.QtTest import QTest
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
    Image.fromarray(arr).save(path)
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


def test_close_while_busy_joins_running_worker(qapp, tmp_path, monkeypatch):
    """A running worker must never be dropped when the dialog closes mid-retouch (Task 9 fix).

    Mirrors tests/sprite/gui/test_export_dialog.py::test_close_during_export_joins_running_worker
    exactly, including its two race fixes (see that test's docstring for why both are needed):
    - `entered` blocks the test until the worker thread has genuinely reached the gated mock, so
      `shutdown()`'s `worker.cancel()` cannot race a not-yet-scheduled QThread into finishing
      almost instantly for the wrong reason.
    - `release` fires from a `threading.Timer` scheduled BEFORE the blocking close call, so
      `on_dialog_close()`'s `join_orphans()` fallback (not the gated job's own timing) is what the
      elapsed-time assertion actually measures.
    """
    monkeypatch.setattr(rd, "CLOSE_SHUTDOWN_TIMEOUT_MS", 50)
    entered = threading.Event()
    release = threading.Event()

    def blocked(provider, frame, instruction, out_png=None, **kwargs):
        entered.set()
        release.wait(5)
        return tmp_path / "0002.r1.png"

    monkeypatch.setattr(rd, "retouch_frame", blocked)
    dialog, _ = _dialog(tmp_path)
    dialog.instruction.setPlainText("x")
    dialog.start_retouch()
    worker = dialog._worker
    assert worker is not None and dialog.is_busy()
    assert entered.wait(5), "the gated job never started"
    threading.Timer(0.15, release.set).start()
    started = time.monotonic()
    dialog.reject()  # shutdown(50) times out -> on_dialog_close must join_orphans() before returning
    elapsed_ms = (time.monotonic() - started) * 1000
    assert not worker.isRunning(), "reject() returned before the job actually stopped"
    assert elapsed_ms >= 140, f"reject() returned suspiciously fast ({elapsed_ms:.1f} ms)"
    for _ in range(5):
        QTest.qWait(20)  # let the queued terminal signal deliver so the orphan is fully reaped
    assert not dialog.is_busy()
    assert dialog.run_btn.isEnabled() and not dialog.cancel_btn.isEnabled()   # _on_worker_idle ran


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
