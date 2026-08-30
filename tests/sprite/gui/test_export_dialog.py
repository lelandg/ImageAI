import gc
import time
from pathlib import Path

import pytest
from PySide6.QtTest import QTest

import gui.sprite.export_dialog as ed
from core.sprite.exporters.grid import GridOptions
from core.sprite.pipeline import CancelToken, no_progress
from core.sprite.project import SpriteProject
from gui.sprite.export_dialog import (BUILTIN_FORMATS, DEFAULT_TEMPLATE, ExportDialog,
                                      ExportRequest, parse_scales, run_export, sheet_png_path)
from gui_synthetic import make_project, sheet_from_action


def _close(dialog) -> None:
    """Close a dialog and sweep it immediately.

    ExportDialog/SpriteWorker hold Qt reference cycles that Python's
    refcounting cannot free, so a closed dialog waits for the next cyclic GC
    pass. Left alone, several tests' worth of dead dialogs pile up and get
    swept by an automatic GC pass that lands while a *later* test's
    SpriteWorker thread is mid-job — segfault, reproduced 4/5 runs of this
    file before this fix. Collecting right here, only when no worker is
    running, keeps every GC pass at a safe point instead.
    """
    dialog.done(0)
    gc.collect()


def _wait_idle(dialog, timeout_s=10.0):
    deadline = time.monotonic() + timeout_s
    while dialog.is_running() and time.monotonic() < deadline:
        QTest.qWait(20)
    QTest.qWait(20)
    assert not dialog.is_running(), "export worker did not finish"


@pytest.fixture
def project(tmp_path, monkeypatch):
    project, _action = make_project(tmp_path)
    monkeypatch.setattr(SpriteProject, "sheet_meta",
                        lambda self, profile: sheet_from_action(self.actions[0], profile))
    monkeypatch.setattr(ed.prefs, "purge_after_export_enabled", lambda: False)
    monkeypatch.setattr(ed.prefs, "set_purge_after_export", lambda value: None)
    monkeypatch.setattr(ed.prefs, "confirm_purge", lambda parent: True)
    return project


def _formats(*ids):
    return [f for f in BUILTIN_FORMATS if f.id in ids]


def _request(project, tmp_path, profiles, formats, **kw):
    base = dict(project=project, profiles=profiles, formats=formats, out_dir=tmp_path / "out",
                template=DEFAULT_TEMPLATE, grid=GridOptions(), pivot=None, purge=False)
    base.update(kw)
    return ExportRequest(**base)


def test_parse_scales():
    assert parse_scales("1,2,4") == (1, 2, 4)
    assert parse_scales(" 2 ") == (2,)
    assert parse_scales("") == (1,)
    assert parse_scales("x,0,-1") == (1,)


def test_builtin_formats_registered_in_order(qapp, project):
    dialog = ExportDialog(project)
    assert dialog.formats() == ["grid", "aseprite_json", "texturepacker_json", "png_sequence", "gif"]
    assert set(dialog.profile_checks) == {p.name for p in project.profiles}
    assert dialog.options_layout is not None
    assert dialog.notes_label.wordWrap() and dialog.notes_label.text() == ""
    _close(dialog)


def test_register_format_adds_checkbox_and_id(qapp, project):
    dialog = ExportDialog(project)
    box = dialog.register_format("godot_tres", "Godot 4 SpriteFrames (.tres)", lambda meta, out_dir: [])
    assert "godot_tres" in dialog.formats()
    assert box.text() == "Godot 4 SpriteFrames (.tres)"
    assert dialog.format_checks["godot_tres"] is box
    assert "godot_tres" not in dialog.selected_formats()
    box.setChecked(True)
    assert "godot_tres" in dialog.selected_formats()
    with pytest.raises(ValueError):
        dialog.register_format("grid", "dup", lambda meta, out_dir: [])
    _close(dialog)


def test_run_export_png_sequence_writes_files(project, tmp_path):
    logs = []
    req = _request(project, tmp_path, ["hd"], ["png_sequence"])
    files = run_export(req, _formats("png_sequence"), log=logs.append,
                       progress=no_progress, token=CancelToken())
    assert len(files) == 4
    assert all(Path(p).exists() for p in files)
    assert all(str(p).startswith(str(tmp_path / "out" / "hd")) for p in files)
    assert any("Wrote" in line for line in logs)


def test_run_export_grid_writes_sheet_and_json_sidecar(project, tmp_path):
    req = _request(project, tmp_path, ["hd"], ["grid"], grid=GridOptions(columns=2))
    files = run_export(req, _formats("grid"), log=lambda m: None,
                       progress=no_progress, token=CancelToken())
    names = sorted(Path(p).name for p in files)
    assert names == ["walk_hd.json", "walk_hd.png"]
    assert (tmp_path / "out" / "hd" / "walk_hd.png").stat().st_size > 0


def test_run_export_sheet_written_once_for_sheet_formats(project, tmp_path):
    req = _request(project, tmp_path, ["hd"], ["grid", "aseprite_json", "texturepacker_json"])
    files = run_export(req, _formats("grid", "aseprite_json", "texturepacker_json"),
                       log=lambda m: None, progress=no_progress, token=CancelToken())
    names = sorted(Path(p).name for p in files)
    assert names == ["walk_hd.json", "walk_hd.png", "walk_hd.tp.json"]


def test_run_export_gif_per_tag(project, tmp_path):
    req = _request(project, tmp_path, ["pixel"], ["gif"])
    files = run_export(req, _formats("gif"), log=lambda m: None,
                       progress=no_progress, token=CancelToken())
    assert [Path(p).name for p in files] == ["walk_walk.gif"]


def test_run_export_applies_pivot_and_passes_filled_meta_to_plugins(project, tmp_path):
    seen = []

    def plugin(meta, out_dir):
        seen.append((meta.sheet_size, [f.pivot for f in meta.frames], out_dir))
        return []

    plugin_format = ed.ExportFormat("plugin", "Plugin", plugin, needs_sheet=True)
    req = _request(project, tmp_path, ["hd"], ["plugin"], pivot=(0.25, 0.75))
    run_export(req, [plugin_format], log=lambda m: None, progress=no_progress, token=CancelToken())
    sheet_size, pivots, out_dir = seen[0]
    assert sheet_size != (0, 0)
    assert pivots == [(0.25, 0.75)] * 4
    assert out_dir == tmp_path / "out" / "hd"
    assert sheet_png_path(project.sheet_meta("hd"), out_dir).exists()


def test_run_export_skips_profile_without_frames(project, tmp_path, monkeypatch):
    from core.sprite.models import SheetMeta
    monkeypatch.setattr(SpriteProject, "sheet_meta",
                        lambda self, profile: SheetMeta(title="empty", frames=[], tags=[], profile=profile))
    logs = []
    req = _request(project, tmp_path, ["hd"], ["png_sequence"])
    assert run_export(req, _formats("png_sequence"), log=logs.append,
                      progress=no_progress, token=CancelToken()) == []
    assert any("no frames" in line for line in logs)


def test_dialog_export_runs_worker_and_emits(qapp, project, tmp_path):
    dialog = ExportDialog(project)
    dialog.out_dir_edit.setText(str(tmp_path / "exp"))
    for fmt_id, box in dialog.format_checks.items():
        box.setChecked(fmt_id == "png_sequence")
    for name, box in dialog.profile_checks.items():
        box.setChecked(name == "hd")
    got = []
    dialog.exported.connect(got.append)
    dialog.start_export()
    _wait_idle(dialog)
    assert got and len(got[0]) == 4
    assert all(Path(p).exists() for p in got[0])
    assert "Export complete" in dialog.console.console.toPlainText()
    _close(dialog)


def test_dialog_validates_selection(qapp, project, monkeypatch):
    dialog = ExportDialog(project)
    for box in dialog.format_checks.values():
        box.setChecked(False)
    shown = []
    monkeypatch.setattr(ed.QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    dialog.start_export()
    assert shown and not dialog.is_running()
    _close(dialog)


def test_set_grid_options_and_current_meta(qapp, project):
    dialog = ExportDialog(project)
    dialog.set_grid_options(GridOptions(columns=4, border_px=2, shape_px=3, inner_px=1,
                                        extrude_px=1, power_of_two=True, scales=(1, 2)))
    opts = dialog.grid_options()
    assert (opts.columns, opts.border_px, opts.shape_px, opts.inner_px, opts.extrude_px) == (4, 2, 3, 1, 1)
    assert opts.power_of_two is True and opts.scales == (1, 2)
    for name, box in dialog.profile_checks.items():
        box.setChecked(name == "pixel")
    meta = dialog.current_meta()
    assert meta is not None and meta.profile == "pixel" and len(meta.frames) == 4
    for box in dialog.profile_checks.values():
        box.setChecked(False)
    assert dialog.current_meta() is None
    dialog.pivot_x_spin.setValue(0.4)
    dialog.pivot_y_spin.setValue(0.9)
    assert dialog.request().pivot == (0.4, 0.9)
    _close(dialog)


def test_purge_checkbox_requires_confirmation(qapp, project, monkeypatch):
    calls = []
    monkeypatch.setattr(ed.prefs, "set_purge_after_export", calls.append)
    monkeypatch.setattr(ed.prefs, "confirm_purge", lambda parent: False)
    dialog = ExportDialog(project)
    assert not dialog.purge_check.isChecked()
    dialog.purge_check.setChecked(True)
    assert not dialog.purge_check.isChecked()
    assert calls == []
    monkeypatch.setattr(ed.prefs, "confirm_purge", lambda parent: True)
    dialog.purge_check.setChecked(True)
    assert dialog.purge_check.isChecked()
    assert calls == [True]
    dialog.purge_check.setChecked(False)
    assert calls == [True, False]
    _close(dialog)


def test_purge_runs_after_export_when_enabled(qapp, project, tmp_path, monkeypatch):
    monkeypatch.setattr(ed.prefs, "purge_after_export_enabled", lambda: True)
    purged = []
    monkeypatch.setattr(SpriteProject, "purge_intermediates", lambda self: purged.append(1) or 3)
    dialog = ExportDialog(project)
    assert dialog.purge_check.isChecked()
    dialog.out_dir_edit.setText(str(tmp_path / "exp"))
    for fmt_id, box in dialog.format_checks.items():
        box.setChecked(fmt_id == "png_sequence")
    dialog.start_export()
    _wait_idle(dialog)
    assert purged == [1]
    assert "Purged 3" in dialog.console.console.toPlainText()
    _close(dialog)


def test_failed_export_is_logged_and_shown(qapp, project, tmp_path, monkeypatch):
    dialog = ExportDialog(project)
    dialog.out_dir_edit.setText(str(tmp_path / "exp"))
    for box in dialog.format_checks.values():
        box.setChecked(False)

    def boom(meta, out_dir):
        raise RuntimeError("disk full")

    dialog.register_format("boom", "Boom", boom, checked=True)
    shown = []
    monkeypatch.setattr(ed.QMessageBox, "critical", staticmethod(lambda *a, **k: shown.append(a)))
    dialog.start_export()
    _wait_idle(dialog)
    assert shown
    assert "disk full" in dialog.console.console.toPlainText()
    _close(dialog)


def test_settings_round_trip(qapp, project, tmp_path):
    dialog = ExportDialog(project)
    dialog.out_dir_edit.setText(str(tmp_path / "keep"))
    dialog.name_template_edit.setText("{title}-{frame01}.png")
    dialog.columns.setValue(6)
    dialog.scales_edit.setText("1,2")
    dialog.format_checks["gif"].setChecked(True)
    _close(dialog)  # persists
    again = ExportDialog(project)
    assert again.out_dir_edit.text() == str(tmp_path / "keep")
    assert again.name_template_edit.text() == "{title}-{frame01}.png"
    assert again.columns.value() == 6
    assert again.grid_options().scales == (1, 2)
    assert again.format_checks["gif"].isChecked()
    _close(again)
