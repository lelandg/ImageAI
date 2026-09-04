import threading
import time

import pytest
from PySide6.QtTest import QTest

import gui.sprite.processing_panel as pp
from core.sprite.project import ActionCard
from gui.sprite.pixel_view import PixelView
from gui.sprite.processing_panel import CUSTOM_PRESET, ProcessingPanel
from gui_synthetic import make_project


def _make_clip(root, name):
    """An action-shaped clip stub whose `path` points at a real (empty) file."""
    path = root / "clips" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00")
    return type("Clip", (), {"path": path})()


def _pump(times=5):
    """Deliver the queued cross-thread worker signals."""
    for _ in range(times):
        QTest.qWait(20)


def _wait_idle(panel, timeout_s=10.0):
    deadline = time.monotonic() + timeout_s
    while panel.is_busy() and time.monotonic() < deadline:
        QTest.qWait(20)
    QTest.qWait(20)
    assert not panel.is_busy(), "worker did not finish"


@pytest.fixture
def panel(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": False, "rembg": False})
    project, action = make_project(tmp_path)
    widget = ProcessingPanel()
    widget.set_project(project)
    widget.set_action(action)
    yield widget, project, action
    widget.shutdown()


def test_loads_project_settings(panel):
    widget, project, action = panel
    assert widget.key_method.currentData() == project.key.method
    assert widget.extract_mode.currentData() == project.extraction.mode
    assert set(widget.profile_editors) == {p.name for p in project.profiles}
    assert widget.run_btn.isEnabled()


def test_tolerance_slider_writes_back(panel):
    widget, project, _ = panel
    changed = []
    widget.settingsChanged.connect(lambda: changed.append(1))
    widget.tolerance.setValue(35)
    assert abs(project.key.tolerance - 0.35) < 1e-9
    assert changed


def test_extract_mode_and_stabilize_write_back(panel):
    widget, project, _ = panel
    widget.extract_mode.setCurrentIndex(widget.extract_mode.findData("target_fps"))
    assert project.extraction.mode == "target_fps"
    widget.target_fps.setValue(15)
    assert project.extraction.target_fps == 15
    # De-jitter is off by default, so toggle on first: the write-back must run.
    widget.dejitter.setChecked(True)
    assert project.stabilize.dejitter is True
    widget.dejitter.setChecked(False)
    assert project.stabilize.dejitter is False
    widget.anchor.setCurrentIndex(widget.anchor.findData("center"))
    assert project.stabilize.anchor == "center"


def test_key_color_edit_writes_back_and_validates(panel):
    widget, project, _ = panel
    widget.key_color_edit.setText("#12ab34")
    assert project.key.key_color == "#12AB34"
    widget.key_color_edit.setText("nope")
    assert project.key.key_color is None


def test_estimate_readout_uses_probe(panel):
    widget, project, _ = panel
    assert "?" in widget.estimate_text()
    widget.set_probe({"fps": 24.0, "nb_frames": 48, "duration": 2.0, "width": 64, "height": 64})
    text = widget.estimate_text()
    assert "?" not in text and any(ch.isdigit() for ch in text)
    assert widget.estimate_label.text() == text


def test_profile_editor_floyd_warning_and_custom_size(panel):
    widget, project, _ = panel
    editor = widget.profile_editors["pixel"]
    profile = next(p for p in project.profiles if p.name == "pixel")
    assert editor.dither_warning.isHidden()
    editor.dither.setCurrentIndex(editor.dither.findData("floyd"))
    assert not editor.dither_warning.isHidden()
    assert profile.dither == "floyd"
    editor.preset.setCurrentText(CUSTOM_PRESET)
    editor.width.setValue(72)
    editor.height.setValue(80)
    assert profile.cell_size == (72, 80)
    editor.palette_size.setValue(0)
    assert profile.palette_size is None
    editor.palette_size.setValue(16)
    assert profile.palette_size == 16
    editor.upscale_small.setChecked(True)
    assert getattr(profile, "upscale_small", None) is True


def test_run_pipeline_uses_worker_and_emits(panel, monkeypatch):
    widget, project, action = panel
    calls = []

    def fake_run(proj, act, *, upto, progress, token, force):
        calls.append((proj, act, upto, force))
        progress("key", 1, 2, "keying")
        return {"key": [], "stabilize": []}

    monkeypatch.setattr(pp, "run_pipeline", fake_run)
    done = []
    widget.pipelineFinished.connect(done.append)
    logs = []
    widget.logMessage.connect(lambda m, l: logs.append((m, l)))
    widget.force_check.setChecked(True)
    widget.run_pipeline()
    assert widget.is_busy()
    _wait_idle(widget)
    assert calls == [(project, action, "pixel", True)]
    assert done == [action.id]
    assert any(l == "SUCCESS" for _, l in logs)


def test_run_pipeline_blocked_by_invalid_key_color(panel, monkeypatch):
    """Important 6: a typed key colour that does not parse must never silently key on
    the plate colour — Run pipeline refuses (logged + shown) instead of starting."""
    widget, project, _ = panel
    called = []
    monkeypatch.setattr(pp, "run_pipeline", lambda *a, **k: called.append(1))
    shown = []
    monkeypatch.setattr(pp.QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    widget.key_color_edit.setText("1E90FF")  # missing '#', HEX_RE rejects it
    widget.run_pipeline()
    assert not called
    assert not widget.is_busy()
    assert shown and "1E90FF" in shown[0][2]
    assert project.key.key_color is None  # _write_back already dropped the bad value


def test_failed_pipeline_is_logged_and_shown(panel, monkeypatch):
    widget, _, _ = panel

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(pp, "run_pipeline", boom)
    shown = []
    monkeypatch.setattr(pp.QMessageBox, "critical", staticmethod(lambda *a, **k: shown.append(a)))
    logs = []
    widget.logMessage.connect(lambda m, l: logs.append((m, l)))
    widget.run_pipeline()
    _wait_idle(widget)
    assert shown
    assert any(l == "ERROR" and "boom" in m for m, l in logs)


def test_preview_key_requires_clip(panel, monkeypatch):
    widget, _, action = panel
    action.clip = None
    shown = []
    monkeypatch.setattr(pp.QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    widget.preview_key_on_clip()
    assert shown and not widget.is_busy()


def test_preview_key_runs_ffmpeg_helper(panel, monkeypatch, tmp_path):
    widget, project, action = panel
    clip = tmp_path / "clips" / "act1.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"\x00")
    action.clip = type("Clip", (), {"path": clip})()
    calls = []

    def fake_preview(video, out_mp4, key_color, similarity, blend):
        calls.append((video, out_mp4, key_color, similarity, blend))
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        out_mp4.write_bytes(b"\x00")
        return out_mp4

    monkeypatch.setattr(pp, "ffmpeg_chromakey_preview", fake_preview)
    opened = []
    monkeypatch.setattr(pp.QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url) or True))
    widget.preview_key_on_clip()
    _wait_idle(widget)
    assert len(calls) == 1 and calls[0][0] == clip
    assert calls[0][2] == (project.key.key_color or project.plate_color)
    assert opened


def test_preview_key_blocked_by_invalid_key_color(panel, monkeypatch, tmp_path):
    """Important 6: same refusal at the Preview key commit point."""
    widget, project, action = panel
    clip = tmp_path / "clips" / "act1.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"\x00")
    action.clip = type("Clip", (), {"path": clip})()
    calls = []
    monkeypatch.setattr(pp, "ffmpeg_chromakey_preview", lambda *a, **k: calls.append(1))
    shown = []
    monkeypatch.setattr(pp.QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    widget.key_color_edit.setText("green")
    widget.preview_key_on_clip()
    assert not calls
    assert not widget.is_busy()
    assert shown and "green" in shown[0][2]


def test_preview_done_warns_when_openurl_fails(panel, monkeypatch, tmp_path):
    """Minor 8: `_preview_done` must log a WARNING with the path when no handler opens it,
    instead of only the SUCCESS "written" line (silent failure otherwise)."""
    widget, _, _ = panel
    monkeypatch.setattr(pp.QDesktopServices, "openUrl", staticmethod(lambda url: False))
    logs = []
    widget.logMessage.connect(lambda m, l: logs.append((m, l)))
    path = tmp_path / "preview_chromakey.mp4"
    widget._preview_done(path)
    assert any(l == "WARNING" and str(path) in m for m, l in logs)


def test_key_color_pick_roundtrip(panel):
    widget, project, _ = panel
    view = PixelView()
    widget.attach_pixel_view(view)
    widget.pick_key_color()
    assert view.pick_mode()
    view.colorPicked.emit("#00FF00")
    assert widget.key_color_edit.text() == "#00FF00"
    assert project.key.key_color == "#00FF00"


def test_install_button_hidden_when_backends_present(panel, monkeypatch):
    widget, _, _ = panel
    assert not widget.install_btn.isHidden()
    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": True, "rembg": True})
    widget.refresh_backends()
    assert widget.install_btn.isHidden()
    assert "installed" in widget.ml_status.text()


def test_rebuild_palette_clears_lock_and_reruns_pipeline(panel, monkeypatch):
    widget, project, action = panel
    profile = next(p for p in project.profiles if p.name == "pixel")
    profile.locked_palette = ["#000000", "#FFFFFF"]
    calls = []

    def fake_run(proj, act, *, upto, progress, token, force):
        calls.append((upto, force, profile.locked_palette))
        profile.locked_palette = ["#101010", "#808080", "#F0F0F0"]  # what ensure_palette would store
        return {"pixel": []}

    monkeypatch.setattr(pp, "run_pipeline", fake_run)
    logs = []
    widget.logMessage.connect(lambda m, l: logs.append(m))
    done = []
    widget.pipelineFinished.connect(done.append)
    widget.rebuild_palette_for("pixel")
    _wait_idle(widget)
    assert calls == [("pixel", False, None)]  # the lock was cleared before the run
    assert any("3 colors" in m for m in logs)
    assert done == [action.id]


def test_pixel_warnings_are_logged_after_run(panel, monkeypatch, tmp_path):
    widget, project, action = panel
    monkeypatch.setattr(pp, "stage_dir", lambda proj, act, stage: tmp_path / "stages" / stage)
    report = tmp_path / "stages" / "pixel" / "pixel.json"
    report.parent.mkdir(parents=True)
    report.write_text('{"warnings": ["source 40x40 is smaller than cell 64x64"]}', encoding="utf-8")
    monkeypatch.setattr(pp, "run_pipeline", lambda *a, **k: {"pixel": []})
    logs = []
    widget.logMessage.connect(lambda m, l: logs.append((m, l)))
    widget.run_pipeline()
    _wait_idle(widget)
    assert any(l == "WARNING" and "smaller than cell" in m for m, l in logs)


def test_export_button_emits(panel):
    widget, _, _ = panel
    got = []
    widget.exportRequested.connect(lambda: got.append(1))
    widget.export_btn.click()
    assert got == [1]


def test_no_project_disables_run(qapp, monkeypatch):
    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": False, "rembg": False})
    widget = ProcessingPanel()
    widget.set_project(None)
    assert not widget.run_btn.isEnabled()
    widget.set_probe({"fps": 24.0, "nb_frames": 48, "duration": 2.0})
    assert "?" in widget.estimate_text()


def test_probe_failure_is_logged_and_shown(qapp, tmp_path, monkeypatch):
    """A failed ffprobe reaches the status console, not only the file log."""
    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": False, "rembg": False})
    project, action = make_project(tmp_path)
    clip = tmp_path / "clips" / "act1.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"\x00")
    action.clip = type("Clip", (), {"path": clip})()

    def boom(path):
        raise RuntimeError("ffprobe exploded")

    monkeypatch.setattr(pp, "probe_video", boom)
    widget = ProcessingPanel()
    widget.set_project(project)
    logs = []
    widget.logMessage.connect(lambda m, l: logs.append((m, l)))
    try:
        widget.set_action(action)
        probe = widget._probe_worker
        assert probe is not None, "no probe worker was started"
        assert probe.wait(10000), "the probe worker did not finish in time"
        for _ in range(5):
            QTest.qWait(20)   # the failed signal reaches the panel through the event loop
    finally:
        widget.shutdown()
    assert any(level == "WARNING" and "ffprobe failed for act1.mp4" in message
               for message, level in logs)
    assert widget._probe_worker is None


def test_probe_worker_timeout_becomes_orphan(qapp, tmp_path, monkeypatch):
    """A probe worker that outlives shutdown's bounded wait is adopted, never destroyed."""
    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": False, "rembg": False})
    project, action = make_project(tmp_path)
    clip = tmp_path / "clips" / "act1.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"\x00")
    action.clip = type("Clip", (), {"path": clip})()
    release = threading.Event()

    def slow_probe(path):
        release.wait(30.0)
        return {"fps": 24.0, "nb_frames": 48, "duration": 2.0}

    monkeypatch.setattr(pp, "probe_video", slow_probe)
    widget = ProcessingPanel()
    widget.set_project(project)
    widget.set_action(action)
    try:
        assert widget.shutdown(timeout_ms=50) is False
        assert widget.is_busy(), "an orphaned probe worker must keep the host busy"
    finally:
        release.set()
        assert widget.join_orphans(10000)
    _wait_idle(widget)
    assert widget._probe_worker is None


def test_orphaned_worker_resets_the_run_ui(qapp, tmp_path, monkeypatch):
    """A timed-out shutdown orphans the worker; the idle hook must reset the run UI.

    WorkerHost._guarded drops the orphan's terminal signal, so _on_done/_on_failed
    never run — without _on_worker_idle the progress bar and Cancel button would
    stay live for a job that already stopped (review, Minor 1).
    """
    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": False, "rembg": False})
    project, action = make_project(tmp_path)
    release = threading.Event()

    def slow_run(proj, act, *, upto, progress, token, force):
        release.wait(30.0)
        return {"pixel": []}

    monkeypatch.setattr(pp, "run_pipeline", slow_run)
    widget = ProcessingPanel()
    widget.set_project(project)
    widget.set_action(action)
    try:
        widget.run_pipeline()
        assert widget.is_busy()
        assert not widget.progress_bar.isHidden(), "the run UI should be live"
        assert widget.cancel_btn.isEnabled()
        assert widget.shutdown(timeout_ms=50) is False, "the worker should be orphaned"
    finally:
        release.set()
        assert widget.join_orphans(10000)
    _wait_idle(widget)          # pumps until _reap_orphan runs _on_worker_idle
    assert widget.progress_bar.isHidden(), "the progress bar stayed live after the orphan stopped"
    assert widget.progress_label.isHidden()
    assert not widget.cancel_btn.isEnabled(), "Cancel stayed enabled after the orphan stopped"


def test_orphaned_probe_result_is_dropped_after_shutdown(qapp, tmp_path, monkeypatch):
    """A probe orphaned by a timed-out shutdown must never write the panel's estimate."""
    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": False, "rembg": False})
    project, action = make_project(tmp_path)
    action.clip = _make_clip(tmp_path, "act1.mp4")
    release = threading.Event()

    def slow_probe(path):
        release.wait(30.0)
        return {"fps": 24.0, "duration": 10.0}

    monkeypatch.setattr(pp, "probe_video", slow_probe)
    widget = ProcessingPanel()
    widget.set_project(project)
    widget.set_action(action)
    try:
        assert widget._probe_worker is not None
        probe_id = widget._probe_id
        before = widget.estimate_text()
        assert widget.shutdown(timeout_ms=50) is False
        # The guard, not the worker, is what drops the result: deliver it by hand.
        widget._probe_done(probe_id, action.id, {"fps": 24.0, "duration": 10.0})
        assert widget.estimate_text() == before
    finally:
        release.set()
        assert widget.join_orphans(10000)
    _pump()
    assert widget.estimate_text() == before
    assert "?" in widget.estimate_text()


def test_action_switch_supersedes_probe_and_drops_the_late_result(qapp, tmp_path, monkeypatch):
    """A -> B mid-probe: B is probed, and A's late result never reaches the estimate."""
    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": False, "rembg": False})
    project, action_a = make_project(tmp_path)
    action_b = ActionCard(id="act2", name="run", prompt="run cycle")
    project.actions.append(action_b)
    action_a.clip = _make_clip(tmp_path, "a.mp4")
    action_b.clip = _make_clip(tmp_path, "b.mp4")
    gate = threading.Event()

    def fake_probe(path):
        if path.name == "a.mp4":
            gate.wait(30.0)
            return {"fps": 24.0, "duration": 10.0}   # every_n=8 -> ~30 frames
        return {"fps": 24.0, "duration": 1.0}        # every_n=8 -> ~3 frames

    monkeypatch.setattr(pp, "probe_video", fake_probe)
    widget = ProcessingPanel()
    widget.set_project(project)
    try:
        widget.set_action(action_a)
        worker_a = widget._probe_worker
        assert worker_a is not None and worker_a.isRunning()

        widget.set_action(action_b)                   # supersedes A's probe
        worker_b = widget._probe_worker
        assert worker_b is not None and worker_b is not worker_a, "B must be probed too"
        assert worker_b.wait(10000)
        _pump()
        assert widget.estimate_text() == "yields ~3 frames"
    finally:
        # Release A and join it before returning: a worker still blocked on the
        # Event at test exit crashes the whole-directory run.
        gate.set()
        assert widget.join_orphans(10000)
        widget.shutdown()
    _pump()
    assert widget.estimate_text() == "yields ~3 frames", "A's stale probe overwrote B"


def test_queued_probe_release_never_waits_on_the_new_worker(qapp, tmp_path, monkeypatch):
    """A's queued `finished`, delivered after B started, must not join B's thread."""
    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": False, "rembg": False})
    project, action_a = make_project(tmp_path)
    action_b = ActionCard(id="act2", name="run", prompt="run cycle")
    project.actions.append(action_b)
    action_a.clip = _make_clip(tmp_path, "a.mp4")
    action_b.clip = _make_clip(tmp_path, "b.mp4")
    gate = threading.Event()

    def fake_probe(path):
        if path.name == "a.mp4":
            return {"fps": 24.0, "duration": 10.0}    # ~30 frames
        gate.wait(30.0)
        return {"fps": 24.0, "duration": 1.0}

    monkeypatch.setattr(pp, "probe_video", fake_probe)
    widget = ProcessingPanel()
    widget.set_project(project)
    widget.set_action(action_a)
    worker_a = widget._probe_worker
    assert worker_a is not None
    # Join A's thread WITHOUT pumping: its `finished` is now posted, not delivered.
    assert worker_a.wait(10000)

    widget.set_action(action_b)                       # B's probe blocks on the gate
    worker_b = widget._probe_worker
    assert worker_b is not None and worker_b.isRunning()

    start = time.monotonic()
    _pump()                                           # A's queued event lands here
    elapsed = time.monotonic() - start
    try:
        assert elapsed < 2.0, f"a stale probe event joined the running worker ({elapsed:.1f}s)"
        assert worker_b.isRunning(), "B's probe was released by A's stale event"
        assert "?" in widget.estimate_text(), "A's stale probe overwrote the estimate"
    finally:
        # Release B and join it before returning; shutdown() may orphan it.
        gate.set()
        widget.shutdown()
        assert widget.join_orphans(10000)
