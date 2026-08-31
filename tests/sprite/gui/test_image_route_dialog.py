# tests/sprite/gui/test_image_route_dialog.py
import threading
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QWidget

from core.sprite.generation.errors import ProviderError
from core.sprite.models import FrameMeta
from core.sprite.pipeline import Cancelled, CancelToken, no_progress
from core.sprite.project import ActionCard, SpriteProject
from gui.sprite import image_route_dialog as ird
from gui.sprite.image_route_dialog import (
    ImageRouteDialog, archive_existing_frames, billed_units, install_image_route,
)
from gui.sprite.workers import SpriteWorker


def _png(path: Path) -> Path:
    Image.fromarray(np.zeros((16, 16, 4), dtype=np.uint8)).save(path)
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


def test_archive_existing_frames_serializes_a_same_second_collision(tmp_path, monkeypatch):
    """Two renders inside one second must not rename onto the same archive name.

    The stamp has one-second resolution. A rename onto an existing non-empty directory
    raises OSError on Linux and always on Windows, so the serial counter is the only thing
    that keeps the second render alive. The clock is frozen to force the collision.
    """
    frozen = datetime(2026, 8, 30, 12, 0, 0)
    monkeypatch.setattr(ird, "datetime", SimpleNamespace(now=lambda: frozen))
    extract = tmp_path / "extracted"
    names = []
    for _ in range(2):
        extract.mkdir()
        _png(extract / "0001.png")
        archived = archive_existing_frames(extract)
        assert archived is not None and (archived / "0001.png").exists()
        names.append(archived.name)
    assert names == ["extracted.prev-20260830-120000", "extracted.prev-20260830-120000-2"]
    assert not extract.exists()


def _chain_dir(tmp_path) -> Path:
    """An extract directory after two finished edit-chain steps, with one matte pair."""
    extract = tmp_path / "chain"
    extract.mkdir()
    for name in ("0001.png", "0002.png", "0002.white.png", "0002.black.png"):
        _png(extract / name)
    return extract


def test_billed_units_sheet_route_bills_only_a_returned_sheet(tmp_path):
    # The sheet route is one provider call, and the user owes it only once generate_sheet returns.
    assert billed_units("sheet", False, tmp_path, sheet_done=False) == 0
    assert billed_units("sheet", False, tmp_path, sheet_done=True) == 1


def test_billed_units_counts_only_finished_steps_after_a_partial_failure(tmp_path):
    # Two NNNN.png files are two billed steps; a matte plate keeps a non-numeric stem.
    assert billed_units("edit_chain", False, _chain_dir(tmp_path), False) == 2
    assert billed_units("edit_chain", False, tmp_path / "never-created", False) == 0


def test_billed_units_doubles_every_step_in_matte_mode(tmp_path):
    # A matte step costs one white plate call and one black plate call.
    assert billed_units("edit_chain", True, _chain_dir(tmp_path), False) == 4


class _FakeConfig:
    """5a's FakeConfig, made key-sensitive: only the "google" key holds the Google credentials.

    The Settings tab stores the Google key and auth mode under "google", while the
    panel's provider id is "gemini". A lookup with the unmapped id must come back empty.
    """

    def __init__(self):
        self.store = {}
        self.key_reads = []

    def get(self, key, default=None):
        return self.store.get(key, default)

    def set(self, key, value):
        self.store[key] = value

    def save(self):
        return True

    def get_api_key(self, provider):
        self.key_reads.append(provider)
        return "test-key" if provider == "google" else None

    def get_auth_mode(self, provider="google"):
        self.key_reads.append(provider)
        return "api-key" if provider == "google" else None


class _IdlePanel:
    """The ProcessingPanel surface the busy guard reads, with no worker of its own."""

    busy_label = None

    @staticmethod
    def is_busy():
        return False


class _FakeTab(QWidget):
    """The SpriteTab surface that image_route_dialog touches (5a/5b names)."""

    def __init__(self, tmp_path, action=None, *, panel=None):
        super().__init__()
        self.actions = {}
        self.provider_reads = 0
        self.action_cards_panel = SimpleNamespace(
            add_card_action=lambda label, cb: self.actions.__setitem__(label, cb),
            llm_provider=self._llm_provider,
            refresh_status=lambda: None)
        self.config = _FakeConfig()
        self.log_calls = []
        self.console = SimpleNamespace(log=self._log)
        self.current_project = _project(tmp_path)
        # _on_rendered mirrors FramesWorkspace._find_action: only a card the project holds
        # may take the destructive pre-render restore.
        self.current_project.actions = [a for a in (action,) if a is not None]
        self._action = action
        self.known = {a.id: a for a in (action,) if a is not None}
        self.applied = []
        self.providers = []
        self.frames_workspace = SimpleNamespace(apply_frames=self._apply_frames,
                                                panel=panel or _IdlePanel())

    def track(self, action):
        """Register a card apply_frames may target while the tab shows another one."""
        self.known[action.id] = action
        self.current_project.actions.append(action)
        return action

    def _log(self, message, level="INFO"):
        self.log_calls.append((message, level))

    def _apply_frames(self, action_id, frames, label):
        # Record what the real FramesWorkspace.apply_frames would snapshot (current list) and install (new list).
        target = self.known.get(action_id)
        if target is None:
            # The real apply_frames logs an ERROR and returns without installing anything.
            self.applied.append((action_id, label, None, len(frames)))
            return
        self.applied.append((action_id, label, len(target.frames), len(frames)))
        target.frames = list(frames)

    def _llm_provider(self):
        # get_all_provider_ids() yields "gemini" for Google (action_cards_panel.py:76-83).
        self.provider_reads += 1
        return "gemini"

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


def test_rendered_for_another_action_still_snapshots_that_action(qapp, tmp_path):
    """M9: "Render (image)" sits on every card row, so an unselected card needs its snapshot.

    Without apply_frames that card's undo stack keeps only older entries, and the next
    Ctrl+Z on it discards the render. The selected card's own frames stay untouched.
    """
    other = ActionCard(id="zz", name="idle", prompt="stands", duration_s=2, loop=True, target_frames=2, fps=12)
    tab = _FakeTab(tmp_path, _action())
    tab.track(other)
    dialog = ird.open_image_route_dialog(tab, other, exec_dialog=False)
    dialog.frames_before = []
    other.frames = [FrameMeta(name="hero_idle_01", source_path=_png(tmp_path / "zz0001.png"),
                              frame=(0, 0, 0, 0))]
    dialog.rendered.emit([])
    assert tab.applied == [("zz", "Render (image)", 0, 1)]   # snapshot sees the pre-render list
    assert len(other.frames) == 1
    assert tab.current_action().frames == []                 # the selected card is untouched


def test_rendered_for_an_action_the_project_does_not_hold_keeps_the_frames(qapp, tmp_path):
    """apply_frames refuses an unknown action id, so the pre-render restore must not run.

    The restore would leave the card holding the old list while the rendered PNGs sit on
    disk, which throws away a render the user paid for. The frames stay, and the missing
    undo snapshot is reported as an ERROR.
    """
    other = ActionCard(id="zz", name="idle", prompt="stands", duration_s=2, loop=True, target_frames=2, fps=12)
    tab = _FakeTab(tmp_path, _action())          # 'other' is never tracked: not in project.actions
    dialog = ird.open_image_route_dialog(tab, other, exec_dialog=False)
    dialog.frames_before = []
    rendered = [FrameMeta(name="hero_idle_01", source_path=_png(tmp_path / "zz0001.png"),
                          frame=(0, 0, 0, 0))]
    other.frames = list(rendered)
    dialog.rendered.emit([])
    assert tab.applied == []                     # apply_frames is never reached
    assert other.frames == rendered              # the paid render is kept on the card
    assert any(level == "ERROR" and "no undo snapshot" in message
               for message, level in tab.log_calls)


def _gated_panel(monkeypatch, gate, entered):
    """A real ProcessingPanel running a real SpriteWorker that blocks until ``gate`` is set."""
    import gui.sprite.processing_panel as pp

    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": False, "rembg": False})
    panel = pp.ProcessingPanel()

    def job(progress, token):
        entered.set()
        assert gate.wait(10), "gate was never released"
        return {}

    worker = panel.start_job(job, label="pipeline", on_finished=lambda _result: None,
                             on_failed=lambda _message: None)
    assert worker is not None
    return panel, worker


def test_image_route_is_refused_while_the_processing_panel_runs(qapp, tmp_path, monkeypatch):
    """Important 7: the render is a second writer against the stage directory and the project.

    It renames the extract directory aside, clears the clip, rewrites action.frames and runs
    a second pipeline while the panel's worker writes the same files. The refusal reaches
    the console as well as the log, and it lifts as soon as the panel goes idle.
    """
    gate, entered = threading.Event(), threading.Event()
    panel, worker = _gated_panel(monkeypatch, gate, entered)
    action = _action()
    tab = _FakeTab(tmp_path, action, panel=panel)
    try:
        assert entered.wait(10), "the gated job never started"
        assert panel.is_busy()
        assert ird.open_image_route_dialog(tab, action, exec_dialog=False) is None
        assert (f"Wait for the running {panel.busy_label} job to finish before rendering",
                "WARNING") in tab.log_calls
    finally:
        gate.set()
        assert worker.wait(10000)
        for _ in range(5):
            qapp.processEvents()
        assert panel.shutdown()
    assert not panel.is_busy()
    assert ird.open_image_route_dialog(tab, action, exec_dialog=False) is not None


def test_pose_fn_maps_the_gemini_id_to_the_google_config_key(qapp, tmp_path, monkeypatch):
    seen = {}

    def fake_generate(action, frames, **kwargs):
        seen.update(kwargs, frames=frames)
        return ["p"] * frames

    monkeypatch.setattr(ird, "generate_pose_instructions", fake_generate)
    tab = _FakeTab(tmp_path, _action())
    steps = ird._make_pose_fn(tab)(_action(), 3, lambda _m: None)
    assert steps == ["p", "p", "p"]
    # The generator gets the panel's own id; both config lookups get the mapped key.
    assert seen["provider"] == "gemini"
    assert seen["api_key"] == "test-key" and seen["auth_mode"] == "api-key"
    assert seen["model"] is None
    assert tab.config.key_reads == ["google", "google"]


def test_pose_fn_snapshots_the_provider_combo_on_the_gui_thread(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(ird, "generate_pose_instructions", lambda action, frames, **k: ["p"] * frames)
    tab = _FakeTab(tmp_path, _action())
    pose_fn = ird._make_pose_fn(tab)
    assert tab.provider_reads == 1 and tab.config.key_reads == ["google", "google"]
    pose_fn(_action(), 2, lambda _m: None)
    pose_fn(_action(), 2, lambda _m: None)
    # The callable runs inside a SpriteWorker; it must never touch the live combo box again.
    assert tab.provider_reads == 1 and tab.config.key_reads == ["google", "google"]


def test_failed_pipeline_restores_frames_and_marks_the_action_failed(qapp, tmp_path, monkeypatch):
    produced = [_png(tmp_path / f"{k:04d}.png") for k in (1, 2, 3)]
    _patch_core(monkeypatch, tmp_path, produced)
    ird.run_pipeline.side_effect = RuntimeError("stabilize blew up")
    dialog = _dialog(tmp_path)
    action = dialog.action
    kept = [FrameMeta(name="old", source_path=_png(tmp_path / "old.png"), frame=(0, 0, 0, 0))]
    action.frames = list(kept)
    with pytest.raises(RuntimeError):
        dialog.build_job()(no_progress, CancelToken())
    assert action.frames == kept                    # the frame swap is rolled back
    assert action.status == "failed"                # the badge never claims "rendered" after a failure
    assert "stabilize blew up" in action.error
    ird.record_actual.assert_called_once()          # the paid edits, recorded before the pipeline ran
    dialog.project.save.assert_called_once()        # the honest state is persisted


def test_partial_edit_chain_failure_records_the_paid_steps(qapp, tmp_path, monkeypatch):
    extract_dir = _patch_core(monkeypatch, tmp_path, [])

    def fail_at_step_3(*a, **k):
        extract_dir.mkdir(parents=True, exist_ok=True)
        _png(extract_dir / "0001.png")
        _png(extract_dir / "0002.png")
        _png(extract_dir / "0002.white.png")        # a matte plate is not a finished step
        raise ProviderError("provider said no at step 3")

    ird.edit_chain.side_effect = fail_at_step_3
    dialog = _dialog(tmp_path)
    dialog.mode_combo.setCurrentIndex(1)
    dialog.steps_edit.setPlainText("one\ntwo\nthree")
    action = dialog.action
    with pytest.raises(ProviderError):
        dialog.build_job()(no_progress, CancelToken())
    assert action.frames == [] and action.status == "failed"
    assert "step 3" in action.error
    ledger = ird.record_actual.call_args.kwargs
    assert ledger["seconds"] == 2.0 and "failed" in ledger["note"]
    assert ledger["provider"] == "google" and ledger["model"] == "default-image-model"
    dialog.project.save.assert_called_once()


def test_cancelled_render_restores_status_and_bills_finished_steps(qapp, tmp_path, monkeypatch):
    extract_dir = _patch_core(monkeypatch, tmp_path, [])

    def cancel_at_step_2(*a, **k):
        extract_dir.mkdir(parents=True, exist_ok=True)
        _png(extract_dir / "0001.png")
        raise Cancelled()

    ird.edit_chain.side_effect = cancel_at_step_2
    dialog = _dialog(tmp_path)
    dialog.mode_combo.setCurrentIndex(1)
    dialog.steps_edit.setPlainText("one\ntwo\nthree")
    action = dialog.action
    with pytest.raises(Cancelled):
        dialog.build_job()(no_progress, CancelToken())
    assert action.status == "draft" and action.error is None    # a cancel is never a failure
    ledger = ird.record_actual.call_args.kwargs
    assert ledger["seconds"] == 1.0 and "cancelled" in ledger["note"]


def _gated_dialog(tmp_path, monkeypatch, gate, entered):
    """A dialog whose sheet call blocks until ``gate`` is released (a provider HTTP call)."""
    produced = [_png(tmp_path / f"{k:04d}.png") for k in (1, 2, 3)]
    _patch_core(monkeypatch, tmp_path, produced)

    def blocking_sheet(*a, **k):
        entered.set()
        assert gate.wait(10), "gate was never released"
        return tmp_path / "sheet.png"

    monkeypatch.setattr(ird, "generate_sheet", blocking_sheet)
    return _dialog(tmp_path)


def test_close_while_a_render_runs_joins_the_worker(qapp, tmp_path, monkeypatch):
    gate, entered = threading.Event(), threading.Event()
    dialog = _gated_dialog(tmp_path, monkeypatch, gate, entered)
    dialog.start_render()
    worker = dialog._worker
    try:
        assert entered.wait(10), "the job never started"
        threading.Timer(0.2, gate.set).start()
        dialog.reject()                     # Escape / Close button -> on_dialog_close
        assert not dialog.is_busy()         # cancelled and joined, never dropped while running
        assert worker.isFinished()
    finally:
        gate.set()
        assert dialog.join_orphans(10000)
        assert worker.wait(10000)
        for _ in range(3):
            qapp.processEvents()


def test_shutdown_timeout_keeps_the_worker_as_an_orphan(qapp, tmp_path, monkeypatch):
    gate, entered = threading.Event(), threading.Event()
    dialog = _gated_dialog(tmp_path, monkeypatch, gate, entered)
    dialog.start_render()
    worker = dialog._worker
    try:
        assert entered.wait(10), "the job never started"
        # The job blocks in a provider call, so it cannot reach a cancel-token poll.
        assert dialog.shutdown(timeout_ms=1) is False
        assert dialog.is_busy()             # kept as an orphan of the host
        assert worker.parent() is None      # detached: destroying the dialog cannot destroy the thread
    finally:
        gate.set()
        assert dialog.join_orphans(10000)
        for _ in range(3):
            qapp.processEvents()
    assert not dialog.is_busy()             # reaped on its own terminal signal
