import gc
import threading
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


@pytest.fixture(autouse=True)
def _isolated_export_settings():
    """Important 7: tests must not see another test's persisted sprite/export/* keys.

    `tests/conftest.py` sandboxes QSettings into one session-scoped ini file with no
    per-test reset, so a value one test's `_save_settings()` writes (e.g. `formats`)
    stays there for every test that runs after it in the same process — order-dependent
    failures like `test_start_export_blocked_by_grid_padding_export_grid_rejects` seeing
    `format_checks["grid"]` unchecked because an earlier test unchecked it and saved.
    Removing the whole `sprite/export` group before each test (not after, so a crashed
    test never leaves the store dirty for the next one) makes every test start from the
    same clean slate. `test_settings_round_trip` is unaffected: it exercises persistence
    across two `ExportDialog`s constructed within itself.
    """
    settings = ed.prefs.sprite_settings()
    settings.remove(ed.SETTINGS_PREFIX.rstrip("/"))
    settings.sync()
    yield


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
    """`export_grid` requires 1 in scales; parse_scales must never omit it (review Important 4)."""
    assert parse_scales("1,2,4") == (1, 2, 4)
    assert parse_scales(" 2 ") == (1, 2)
    assert parse_scales("1,1,2") == (1, 2)
    assert parse_scales("") == (1,)


def test_parse_scales_refuses_bad_tokens():
    """Important 4: a non-integer or non-positive scale raises, naming the offending token,
    instead of silently collapsing the whole list to (1,)."""
    with pytest.raises(ValueError, match="4x"):
        parse_scales("1,2,4x")
    with pytest.raises(ValueError, match="x"):
        parse_scales("x,0,-1")
    with pytest.raises(ValueError, match="0"):
        parse_scales("0")
    with pytest.raises(ValueError, match="-1"):
        parse_scales("-1")


def test_validate_grid_options():
    """Important 4: pre-flight-reject the combinations `export_grid` itself rejects."""
    assert ed.validate_grid_options(GridOptions()) == []
    assert ed.validate_grid_options(GridOptions(scales=(1, 2, 4))) == []
    problems = ed.validate_grid_options(GridOptions(extrude_px=1, shape_px=1, border_px=0))
    assert problems and "extrude" in problems[0].lower()
    problems = ed.validate_grid_options(GridOptions(scales=(2, 4)))
    assert problems and "scale" in problems[0].lower()


def test_builtin_formats_registered_in_order(qapp, project):
    dialog = ExportDialog(project)
    # Sub-project 6 (gui/sprite/export_formats.py) registers its two ids right after the
    # built-ins, before settings restore, so they always appear at the end here.
    assert dialog.formats() == ["grid", "aseprite_json", "texturepacker_json", "png_sequence", "gif",
                                "godot_tres", "aseprite_native"]
    assert set(dialog.profile_checks) == {p.name for p in project.profiles}
    assert dialog.options_layout is not None
    assert dialog.notes_label.wordWrap() and dialog.notes_label.text() == ""
    _close(dialog)


def test_register_format_adds_checkbox_and_id(qapp, project):
    dialog = ExportDialog(project)
    box = dialog.register_format("custom_fmt", "Custom format (.xyz)", lambda meta, out_dir: [])
    assert "custom_fmt" in dialog.formats()
    assert box.text() == "Custom format (.xyz)"
    assert dialog.format_checks["custom_fmt"] is box
    assert "custom_fmt" not in dialog.selected_formats()
    box.setChecked(True)
    assert "custom_fmt" in dialog.selected_formats()
    with pytest.raises(ValueError):
        dialog.register_format("grid", "dup", lambda meta, out_dir: [])
    _close(dialog)


def _on_disk(out_dir) -> list:
    return sorted(p.name for p in Path(out_dir).iterdir() if p.is_file())


def test_run_export_png_sequence_writes_files(project, tmp_path):
    """Important 3: the reported list must match every file actually on disk (PNG + sidecar)."""
    logs = []
    req = _request(project, tmp_path, ["hd"], ["png_sequence"])
    files = run_export(req, _formats("png_sequence"), log=logs.append,
                       progress=no_progress, token=CancelToken())
    assert len(files) == 8  # 4 frame PNGs + 4 ImageAI metadata sidecars
    assert all(Path(p).exists() for p in files)
    assert all(str(p).startswith(str(tmp_path / "out" / "hd")) for p in files)
    assert sorted(Path(p).name for p in files) == _on_disk(tmp_path / "out" / "hd" / "frames")
    assert any("Wrote" in line for line in logs)


def test_run_export_grid_writes_sheet_and_json_sidecar(project, tmp_path):
    """Important 3: the sheet PNG, its Aseprite JSON, and its ImageAI metadata sidecar all report."""
    req = _request(project, tmp_path, ["hd"], ["grid"], grid=GridOptions(columns=2))
    files = run_export(req, _formats("grid"), log=lambda m: None,
                       progress=no_progress, token=CancelToken())
    names = sorted(Path(p).name for p in files)
    assert names == ["walk_hd.json", "walk_hd.png", "walk_hd.png.json"]
    assert names == _on_disk(tmp_path / "out" / "hd")
    assert (tmp_path / "out" / "hd" / "walk_hd.png").stat().st_size > 0


def test_run_export_grid_reports_every_scale(project, tmp_path):
    """Important 3: `scales=(1, 2)` must report the @2x PNG/Aseprite-JSON/metadata trio too."""
    req = _request(project, tmp_path, ["hd"], ["grid"], grid=GridOptions(scales=(1, 2)))
    files = run_export(req, _formats("grid"), log=lambda m: None,
                       progress=no_progress, token=CancelToken())
    names = sorted(Path(p).name for p in files)
    assert names == ["walk_hd.json", "walk_hd.png", "walk_hd.png.json",
                     "walk_hd@2x.json", "walk_hd@2x.png", "walk_hd@2x.png.json"]
    assert names == _on_disk(tmp_path / "out" / "hd")


def test_run_export_sheet_written_once_for_sheet_formats(project, tmp_path):
    req = _request(project, tmp_path, ["hd"], ["grid", "aseprite_json", "texturepacker_json"])
    files = run_export(req, _formats("grid", "aseprite_json", "texturepacker_json"),
                       log=lambda m: None, progress=no_progress, token=CancelToken())
    names = sorted(Path(p).name for p in files)
    assert names == ["walk_hd.json", "walk_hd.png", "walk_hd.png.json", "walk_hd.tp.json"]
    assert names == _on_disk(tmp_path / "out" / "hd")


def test_run_export_gif_per_tag(project, tmp_path):
    req = _request(project, tmp_path, ["pixel"], ["gif"])
    files = run_export(req, _formats("gif"), log=lambda m: None,
                       progress=no_progress, token=CancelToken())
    assert [Path(p).name for p in files] == ["walk_walk.gif", "walk_walk.gif.json"]
    assert sorted(Path(p).name for p in files) == _on_disk(tmp_path / "out" / "pixel")


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
    assert got and len(got[0]) == 8  # 4 frame PNGs + 4 ImageAI metadata sidecars
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


def test_start_export_blocked_by_grid_padding_export_grid_rejects(qapp, project, monkeypatch):
    """Important 4: a padding/extrude combo `export_grid` rejects is caught before the job starts."""
    dialog = ExportDialog(project)
    assert dialog.format_checks["grid"].isChecked()  # needs_sheet, so grid validation applies
    dialog.border.setValue(0)
    dialog.shape.setValue(1)
    dialog.extrude.setValue(1)  # 2*extrude(2) > shape(1) -> export_grid raises ValueError
    shown = []
    monkeypatch.setattr(ed.QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    dialog.start_export()
    assert shown and not dialog.is_running()
    assert "extrude" in shown[0][2].lower()
    _close(dialog)


def test_start_export_blocked_by_bad_scales_text(qapp, project, monkeypatch):
    """Important 4: an invalid scales token blocks Export with a shown+logged message,
    instead of silently exporting the 1x sheet only."""
    dialog = ExportDialog(project)
    assert dialog.format_checks["grid"].isChecked()  # needs_sheet, so scales are parsed
    dialog.scales_edit.setText("1,2,4x")
    shown = []
    monkeypatch.setattr(ed.QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    dialog.start_export()
    assert shown and not dialog.is_running()
    assert "4x" in shown[0][2]
    _close(dialog)


def test_close_during_export_joins_running_worker(qapp, project, tmp_path, monkeypatch):
    """Important 1: Escape/close mid-export cancels + joins, never drops a running thread.

    Discriminating (re-review New 1): capture the worker and assert it has actually stopped
    IMMEDIATELY after done() returns, before any qWait -- a check made only after pumping events
    would pass even with the join_orphans() fallback removed, because the gated job's own
    release fires independently during that pump.

    Two races had to be closed to make this genuinely discriminating (verified out of tree,
    task-7-report.md fix round 2):
    - `entered` (a second Event) blocks the test until the worker thread has actually reached
      `gated()`; without it, `shutdown()`'s `worker.cancel()` can run before the newly-started
      QThread schedules its first line, so `run_export` sees an already-cancelled token and
      never calls the job at all -- the worker then finishes almost instantly regardless of
      which `on_dialog_close` runs, and the test passes for the wrong reason either way.
    - `_save_settings` is stubbed out: its real body does ~11 `QSettings.sync()` calls, which on
      a loaded filesystem took ~400 ms in isolation -- long enough that even the broken
      `on_dialog_close` (shutdown(50) with no join_orphans() fallback) returns *after* the 150 ms
      release fires by sheer I/O coincidence, again passing for the wrong reason. Stubbing it
      keeps this test scoped to the join itself; settings persistence has its own coverage
      (`test_settings_round_trip`).
    With both races closed, the broken variant reliably returns in ~50 ms with the worker still
    running (fails both assertions below); the real fix reliably takes the full ~150 ms and the
    worker has stopped.

    No extra `gc.collect()` here -- the autouse teardown fixture in conftest.py (7077dc7) sweeps
    every GUI test's dead Qt objects; this test only needs to prove the join actually happened.
    """
    monkeypatch.setattr(ed, "CLOSE_SHUTDOWN_TIMEOUT_MS", 50)
    monkeypatch.setattr(ExportDialog, "_save_settings", lambda self: None)
    entered = threading.Event()
    release = threading.Event()

    def gated(meta, out_dir):
        entered.set()
        release.wait(5)
        return []

    dialog = ExportDialog(project)
    dialog.out_dir_edit.setText(str(tmp_path / "exp"))
    for box in dialog.format_checks.values():
        box.setChecked(False)
    dialog.register_format("gated", "Gated", gated, checked=True)
    for name, box in dialog.profile_checks.items():
        box.setChecked(name == "hd")
    dialog.start_export()
    worker = dialog._worker
    assert worker is not None and dialog.is_running()
    assert entered.wait(5), "the gated job never started"
    threading.Timer(0.15, release.set).start()
    started = time.monotonic()
    dialog.done(0)  # shutdown(50) times out -> on_dialog_close must join_orphans() before returning
    elapsed_ms = (time.monotonic() - started) * 1000
    assert not worker.isRunning(), "done() returned before the job actually stopped"
    assert elapsed_ms >= 140, f"done() returned suspiciously fast ({elapsed_ms:.1f} ms)"
    for _ in range(5):
        QTest.qWait(20)  # let the queued terminal signal deliver so the orphan is fully reaped
    assert not dialog.is_busy()


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


def test_purge_skipped_when_export_writes_nothing(qapp, project, tmp_path, monkeypatch):
    """Important 5: purge never runs after a zero-file export (skipped profile, no tags, etc.)."""
    monkeypatch.setattr(ed.prefs, "purge_after_export_enabled", lambda: True)
    from core.sprite.models import SheetMeta
    monkeypatch.setattr(SpriteProject, "sheet_meta",
                        lambda self, profile: SheetMeta(title="empty", frames=[], tags=[], profile=profile))
    purged = []
    monkeypatch.setattr(SpriteProject, "purge_intermediates", lambda self: purged.append(1) or 3)
    dialog = ExportDialog(project)
    assert dialog.purge_check.isChecked()
    dialog.out_dir_edit.setText(str(tmp_path / "exp"))
    for fmt_id, box in dialog.format_checks.items():
        box.setChecked(fmt_id == "png_sequence")
    dialog.start_export()
    _wait_idle(dialog)
    assert purged == []
    text = dialog.console.console.toPlainText()
    assert "Purged" not in text
    assert "Export complete: 0 file(s)" in text
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


def test_persisted_formats_apply_to_a_format_registered_after_construction(qapp, project):
    """T7 fix-now (register_format): `_load_settings` used to apply the persisted `formats`
    set only to checkboxes that existed at `__init__`, so a format a sub-project-6 caller
    `register_format`'d afterward always came up unchecked even when the user last saved it."""
    ed.prefs.set_pref(ed.SETTINGS_PREFIX + "formats", "gif,custom_fmt")
    dialog = ExportDialog(project)
    assert dialog.format_checks["gif"].isChecked()
    assert not dialog.format_checks["grid"].isChecked()
    box = dialog.register_format("custom_fmt", "Custom format (.xyz)", lambda meta, out_dir: [])
    assert box.isChecked()
    _close(dialog)


def test_out_dir_persistence_is_per_project(qapp, tmp_path, monkeypatch):
    """T7 fix-now (out_dir per project): `sprite/export/out_dir` carried no project identity,
    so project A's saved directory became project B's default too; keying by project fixes it."""
    monkeypatch.setattr(ed.prefs, "purge_after_export_enabled", lambda: False)
    monkeypatch.setattr(ed.prefs, "set_purge_after_export", lambda value: None)
    monkeypatch.setattr(ed.prefs, "confirm_purge", lambda parent: True)
    project_a, _ = make_project(tmp_path / "a")
    project_b, _ = make_project(tmp_path / "b")

    dialog_a = ExportDialog(project_a)
    dialog_a.out_dir_edit.setText(str(tmp_path / "custom_export"))
    _close(dialog_a)  # persists under project A's key

    dialog_b = ExportDialog(project_b)
    assert dialog_b.out_dir_edit.text() == str(ed.default_export_dir(project_b))
    _close(dialog_b)

    dialog_a_again = ExportDialog(project_a)
    assert dialog_a_again.out_dir_edit.text() == str(tmp_path / "custom_export")
    _close(dialog_a_again)
