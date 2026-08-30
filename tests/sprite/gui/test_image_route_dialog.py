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
