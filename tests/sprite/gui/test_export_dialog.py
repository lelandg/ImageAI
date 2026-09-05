import gc
import json
import threading
import time
from pathlib import Path

import pytest
from PySide6.QtTest import QTest
from PySide6.QtCore import QSettings

import gui.sprite.export_dialog as ed
from core.sprite.exporters.grid import GridOptions
from core.sprite.pipeline import STALE_STABILIZE_REASON, CancelToken, no_progress
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
def _isolated_export_settings(tmp_path, monkeypatch):
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
    # NativeFormat is the Windows registry: setPath cannot redirect it.
    # Use an explicit INI file to exercise persistence without touching user preferences.
    settings_file = str(tmp_path / "sprite-settings.ini")
    monkeypatch.setattr(ed.prefs, "sprite_settings",
                        lambda: QSettings(settings_file, QSettings.Format.IniFormat))
    settings = ed.prefs.sprite_settings()
    settings.remove(ed.SETTINGS_PREFIX.rstrip("/"))
    settings.sync()
    yield


@pytest.fixture
def project(tmp_path, monkeypatch):
    project, _action = make_project(tmp_path)
    monkeypatch.setattr(SpriteProject, "sheet_meta",
                        lambda self, profile, warn=True: sheet_from_action(self.actions[0], profile))
    # Unit tests provide their own sheet metadata; pipeline integration tests
    # below use real stages or replace this helper with a recorder.
    monkeypatch.setattr(ed, "ensure_profile_stages", lambda *args, **kwargs: {})
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


@pytest.mark.parametrize("mode", ["solid", "original"])
def test_run_export_gif_background_metadata_and_pixels(project, tmp_path, mode):
    import json

    project.background.mode = mode
    project.background.color = "#123456"
    for index, frame in enumerate(project.actions[0].frames):
        source = Image.new("RGBA", (8, 8), (0, 255, 0, 255 if mode == "original" else 0))
        source.putpixel((index + 2, 5), (240, 80, 20, 255))
        source.save(frame.source_path)
    request = _request(project, tmp_path, ["pixel"], ["gif"])
    files = run_export(request, _formats("gif"), log=lambda m: None,
                       progress=no_progress, token=CancelToken())
    with Image.open(files[0]) as gif:
        assert "transparency" not in gif.info
        assert gif.convert("RGB").getpixel((0, 0)) == ((18, 52, 86) if mode == "solid" else (0, 255, 0))
    metadata = json.loads(Path(files[1]).read_text())
    assert metadata["background_mode"] == mode
    assert metadata["background_color"] == ("#123456" if mode == "solid" else None)


def test_export_dialog_displays_project_background(qapp, project):
    project.background.mode = "solid"
    project.background.color = "#123456"
    dialog = ExportDialog(project)
    assert "#123456" in dialog.background_label.text()
    assert "GIF only" in dialog.background_label.text()
    assert "Processing" in dialog.background_label.text()
    _close(dialog)


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


# --- T4: the options pane scrolls; the format rows never get squeezed ----------------
def _settle(dialog, width: int, height: int) -> None:
    """Show `dialog` at the given size and pump the layout until it settles."""
    from PySide6.QtWidgets import QApplication
    dialog.show()
    dialog.resize(width, height)
    for _ in range(5):
        QApplication.processEvents()


def _format_rows_keep_their_hint(dialog) -> None:
    for fmt_id, box in dialog.format_checks.items():
        assert box.height() >= box.sizeHint().height(), (
            f"format row '{fmt_id}' squeezed to {box.height()} px "
            f"(hint {box.sizeHint().height()} px)")


def test_format_rows_keep_their_height_at_the_old_opening_size(qapp, project):
    """Problem 2: at the old 660x680 opening size the splitter squeezed the format
    checkboxes below their size hint (3-4 px clipped) until the window grew."""
    dialog = ExportDialog(project)
    _settle(dialog, 660, 680)
    _format_rows_keep_their_hint(dialog)
    _close(dialog)


def test_options_pane_scrolls_instead_of_squeezing(qapp, project):
    """When the dialog is too short for the options, the pane scrolls; rows keep their hint."""
    dialog = ExportDialog(project)
    _settle(dialog, 660, 480)
    assert dialog.options_scroll.verticalScrollBar().maximum() > 0
    _format_rows_keep_their_hint(dialog)
    _close(dialog)


def test_dialog_minimum_fits_a_laptop_screen(qapp, project):
    dialog = ExportDialog(project)
    _settle(dialog, 660, 720)  # the layout's minimum is only known once it is shown
    assert dialog.minimumSize().height() <= 600
    assert dialog.minimumWidth() == 660
    _close(dialog)


def test_unreadable_saved_geometry_falls_back_to_the_default_size(qapp, project, caplog):
    """A foreign value under the geometry key must not break the dialog."""
    settings = ed.prefs.sprite_settings()
    settings.setValue(ed.GEOMETRY_KEY, "not a QByteArray")
    settings.sync()
    with caplog.at_level("WARNING", logger="gui.sprite.export_dialog"):
        dialog = ExportDialog(project)
    assert dialog.width() >= 660 and dialog.height() > 0
    assert any("geometry" in r.message for r in caplog.records)
    _close(dialog)


def test_first_open_size_fits_the_screen(qapp, project):
    from PySide6.QtGui import QGuiApplication
    dialog = ExportDialog(project)
    available = QGuiApplication.primaryScreen().availableGeometry()
    assert dialog.height() <= available.height()
    assert dialog.width() >= 660
    _close(dialog)


def test_geometry_round_trip(qapp, project):
    """Mirror of test_settings_round_trip for the window geometry."""
    dialog = ExportDialog(project)
    _settle(dialog, 700, 750)
    _close(dialog)  # persists the geometry
    again = ExportDialog(project)
    assert again.settings.value(ed.SETTINGS_PREFIX + "geometry") is not None
    assert (again.width(), again.height()) == (700, 750)
    _close(again)


def test_late_registered_format_row_is_not_clipped(qapp, project):
    """A format registered after construction (sub-project 6) gets its full row height too."""
    dialog = ExportDialog(project)
    box = dialog.register_format("late_fmt", "Late format (.late)", lambda meta, out_dir: [])
    _settle(dialog, 660, 680)
    assert box.height() >= box.sizeHint().height()
    _format_rows_keep_their_hint(dialog)
    _close(dialog)


# --- T3: run_export guarantees the profile stages before it reads sheet_meta -------
from PIL import Image  # noqa: E402

from core.sprite.pipeline import register_external_frames, run_pipeline, stage_dir  # noqa: E402
from core.sprite.project import ActionCard  # noqa: E402
from core.sprite.slicing import import_png_sequence  # noqa: E402


def _install_recorder(monkeypatch, events, reasons=None, ran=False):
    """Stand in for ensure_profile_stages. ``ran`` marks the fingerprints as changed,
    the way a real stage run does, so the export saves the project."""
    def recorder(project, action, profiles, *, progress=no_progress, token=None):
        events.append(("ensure", action.id, list(profiles)))
        if ran:
            for name in profiles:
                project.stage_fingerprints.setdefault(action.id, {})[name] = "ran"
        return dict(reasons or {})

    monkeypatch.setattr(ed, "ensure_profile_stages", recorder)
    return recorder


def test_run_export_ensures_profile_stages_per_action_before_sheet_meta(project, tmp_path, monkeypatch):
    project.actions.append(ActionCard(id="act2", name="idle", prompt="idle"))  # no frames
    events = []
    _install_recorder(monkeypatch, events)
    real_sheet_meta = SpriteProject.sheet_meta

    def sheet_meta(self, profile, warn=True):
        events.append(("sheet_meta", profile))
        return real_sheet_meta(self, profile)

    monkeypatch.setattr(SpriteProject, "sheet_meta", sheet_meta)
    req = _request(project, tmp_path, ["hd", "pixel"], ["png_sequence"])
    run_export(req, _formats("png_sequence"), log=lambda m: None, progress=no_progress, token=CancelToken())
    assert events == [("ensure", "act1", ["hd"]), ("sheet_meta", "hd"),
                      ("ensure", "act1", ["pixel"]), ("sheet_meta", "pixel")]


def test_run_export_blocks_stale_processing_before_writing(project, tmp_path, monkeypatch, caplog):
    events = []
    _install_recorder(monkeypatch, events, reasons={"hd": STALE_STABILIZE_REASON})
    logs = []
    req = _request(project, tmp_path, ["hd"], ["png_sequence"])
    with caplog.at_level("WARNING", logger="gui.sprite.export_dialog"):
        with pytest.raises(ValueError, match="Run the pipeline"):
            run_export(req, _formats("png_sequence"), log=logs.append,
                       progress=no_progress, token=CancelToken())
    assert not req.out_dir.exists()
    assert any("stabilize output is stale" in line and "walk" in line for line in logs)
    assert any("stabilize output is stale" in r.message for r in caplog.records)


def test_run_export_sends_reasons_at_warning_level(project, tmp_path, monkeypatch):
    """A two-argument log callback (the dialog's) gets WARNING for a reason; the
    ordinary lines stay INFO."""
    _install_recorder(monkeypatch, [], reasons={"hd": "profile is disabled"})
    logs = []
    req = _request(project, tmp_path, ["hd"], ["png_sequence"])
    with pytest.raises(ValueError, match="profile is disabled"):
        run_export(req, _formats("png_sequence"), log=lambda m, level="INFO": logs.append((level, m)),
                   progress=no_progress, token=CancelToken())
    levels = {level for level, line in logs if "profile is disabled" in line}
    assert levels == {"WARNING"}
    assert not any(line.startswith("Wrote ") for _level, line in logs)


def test_run_export_saves_the_project_after_the_helper(project, tmp_path, monkeypatch):
    events = []
    _install_recorder(monkeypatch, events, ran=True)
    monkeypatch.setattr(SpriteProject, "save", lambda self, path=None: events.append(("save",)))
    req = _request(project, tmp_path, ["hd"], ["png_sequence"])
    run_export(req, _formats("png_sequence"), log=lambda m: None, progress=no_progress, token=CancelToken())
    assert events[:2] == [("ensure", "act1", ["hd"]), ("save",)]


def test_run_export_does_not_save_when_no_stage_ran(project, tmp_path, monkeypatch):
    """Every profile output is current: the fingerprints did not change, so no save."""
    events = []
    _install_recorder(monkeypatch, events)
    monkeypatch.setattr(SpriteProject, "save", lambda self, path=None: events.append(("save",)))
    req = _request(project, tmp_path, ["hd", "pixel"], ["png_sequence"])
    run_export(req, _formats("png_sequence"), log=lambda m: None, progress=no_progress, token=CancelToken())
    assert ("save",) not in events
    assert [e for e in events if e[0] == "ensure"] == [("ensure", "act1", ["hd"]),
                                                       ("ensure", "act1", ["pixel"])]


def test_run_export_skips_the_helper_for_a_project_without_a_directory(project, tmp_path, monkeypatch):
    events = []
    _install_recorder(monkeypatch, events, ran=True)
    monkeypatch.setattr(SpriteProject, "save", lambda self, path=None: events.append(("save",)))
    project.project_dir = None
    req = _request(project, tmp_path, ["hd"], ["png_sequence"])
    files = run_export(req, _formats("png_sequence"), log=lambda m: None,
                       progress=no_progress, token=CancelToken())
    assert len(files) == 8
    assert events == []


def test_run_export_save_failure_is_logged_not_raised(project, tmp_path, monkeypatch, caplog):
    _install_recorder(monkeypatch, [], ran=True)

    def broken(self, path=None):
        raise OSError("disk full")

    monkeypatch.setattr(SpriteProject, "save", broken)
    logs = []
    req = _request(project, tmp_path, ["hd"], ["png_sequence"])
    with caplog.at_level("WARNING", logger="gui.sprite.export_dialog"):
        files = run_export(req, _formats("png_sequence"), log=lambda m, level="INFO": logs.append((level, m)),
                           progress=no_progress, token=CancelToken())
    assert len(files) == 8
    assert any(level == "WARNING" and "Could not save the project" in line and "disk full" in line
               for level, line in logs)
    assert any("disk full" in r.message for r in caplog.records)


def test_run_export_end_to_end_writes_hd_cell_sized_frames(tmp_path, alpha_frames):
    """Regression for problem 1: an export must carry the profile cell size (256x256 hd)
    even when the user never ran the hd stage from the Processing panel."""
    project = SpriteProject(name="e2e")
    project.project_dir = tmp_path / "proj"
    project.project_dir.mkdir()
    action = ActionCard(id="a1", name="walk", prompt="walk")
    project.actions = [action]
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    run_pipeline(project, action, upto="stabilize")
    assert not stage_dir(project, action, "hd").exists()
    with Image.open(action.frames[0].source_path) as im:
        assert im.size != (256, 256)  # the stabilize frames are native size

    req = _request(project, tmp_path, ["hd"], ["png_sequence"])
    files = run_export(req, _formats("png_sequence"), log=lambda m: None,
                       progress=no_progress, token=CancelToken())
    pngs = [Path(p) for p in files if Path(p).suffix == ".png"]
    assert len(pngs) == 12
    for png in pngs:
        with Image.open(png) as im:
            assert im.size == (256, 256), png.name
    assert (project.project_dir / "project.iasprite.json").exists()


def test_export_rejects_disabled_profile_with_old_background_outputs(tmp_path, alpha_frames):
    project = SpriteProject(name="background")
    project.project_dir = tmp_path / "project"
    project.project_dir.mkdir()
    action = ActionCard(id="a1", name="walk", prompt="walk")
    project.actions = [action]
    import_png_sequence(alpha_frames, stage_dir(project, action, "extract"))
    register_external_frames(project, action)
    run_pipeline(project, action, upto="hd")
    assert list(stage_dir(project, action, "hd").glob("*.png"))
    project.profile("hd").enabled = False
    project.background.mode = "original"
    run_pipeline(project, action, upto="stabilize")
    request = _request(project, tmp_path, ["hd"], ["gif"])
    with pytest.raises(ValueError, match="disabled"):
        run_export(request, _formats("gif"), log=lambda m: None,
                   progress=no_progress, token=CancelToken())
    assert not request.out_dir.exists()


def test_export_validates_mutated_background_settings(project, tmp_path, caplog):
    project.background.mode = "solid"
    project.background.color = "not a color"
    request = _request(project, tmp_path, ["hd"], ["gif"])
    with pytest.raises(ValueError, match="#RRGGBB"):
        run_export(request, _formats("gif"), log=lambda m: None,
                   progress=no_progress, token=CancelToken())
    assert "not a color" in caplog.text
    assert not request.out_dir.exists()


@pytest.mark.parametrize("background_mode", ["transparent", "original", "solid"])
@pytest.mark.parametrize("upscale_small", [False, True])
@pytest.mark.parametrize("cells", [((256, 256), (64, 64)), ((120, 80), (48, 72))])
def test_background_modes_export_exact_profile_canvases(
        tmp_path, background_mode, upscale_small, cells):
    """Background choice must not turn profile dimensions into resize bounds."""
    project = SpriteProject(name="background_geometry", project_dir=tmp_path / "project")
    project.background.mode = background_mode
    project.background.color = "#123456"
    project.key.method = "chroma"
    project.key.key_color = "#00FF00"
    project.stabilize.pad_px = 4
    project.stabilize.anchor = "center"
    action = ActionCard(id="a1", name="walk", prompt="walk")
    project.actions = [action]
    extracted = stage_dir(project, action, "extract")
    extracted.mkdir(parents=True)
    for index in range(2):
        image = Image.new("RGBA", (160, 90), "#00FF00")
        image.paste((220, 30 + index * 50, 40, 255), (30 + index, 20, 120 + index, 70))
        image.save(extracted / f"{index + 1:04d}.png")
    register_external_frames(project, action)
    for name, cell in zip(("hd", "pixel"), cells):
        profile = project.profile(name)
        profile.cell_size = cell
        profile.upscale_small = upscale_small
        profile.upscale_method = "lanczos"

    # Export must build both profile stages from current stabilization output.
    run_pipeline(project, action, upto="stabilize")
    formats = ["grid", "png_sequence", "gif"]
    request = _request(project, tmp_path, ["hd", "pixel"], formats,
                       grid=GridOptions(columns=2, shape_px=0))
    files = run_export(request, _formats(*formats), log=lambda message: None,
                       progress=no_progress, token=CancelToken())

    for name, cell in zip(("hd", "pixel"), cells):
        profile_dir = request.out_dir / name
        meta = project.sheet_meta(name)
        sheet_path = sheet_png_path(meta, profile_dir)
        png_frames = [path for path in files
                      if path.parent == profile_dir / "frames" and path.suffix == ".png"]
        gifs = [path for path in files if path.parent == profile_dir and path.suffix == ".gif"]
        assert len(png_frames) == 2
        assert len(gifs) == 1
        for path in png_frames + gifs:
            with Image.open(path) as image:
                assert image.size == cell, (background_mode, name, path.name)
                if path.suffix == ".gif":
                    assert image.n_frames == 2
                    for frame_index in range(image.n_frames):
                        image.seek(frame_index)
                        assert image.size == cell
        with Image.open(sheet_path) as sheet:
            assert sheet.size == (2 * cell[0], cell[1])
        sheet_json = json.loads(sheet_path.with_suffix(".json").read_text(encoding="utf-8"))
        assert sheet_json["meta"]["size"] == {"w": 2 * cell[0], "h": cell[1]}
        assert len(sheet_json["frames"]) == 2
        for frame in sheet_json["frames"].values():
            assert frame["sourceSize"] == {"w": cell[0], "h": cell[1]}
            assert (frame["frame"]["w"], frame["frame"]["h"]) == cell
