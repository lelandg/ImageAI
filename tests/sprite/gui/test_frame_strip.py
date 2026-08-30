import logging
from pathlib import Path

from PySide6.QtWidgets import QDialog

import gui.sprite.frame_strip as fs
from gui.sprite.frame_strip import FrameOverridesDialog, FrameStrip, sanitize_frame_name, unique_name
from gui.sprite.undo_controller import UndoController
from gui_synthetic import make_frames, write_frame_png


def _strip(tmp_path, n=4):
    undo = UndoController()
    strip = FrameStrip(undo)
    strip.set_action_id("act1")
    strip.set_frames(make_frames(tmp_path, n))
    return strip, undo


def test_helpers():
    assert sanitize_frame_name("Hero Walk 03.png") == "Hero_Walk_03_png"
    assert sanitize_frame_name("***") == "frame"
    assert unique_name("a", ["a", "a_2"]) == "a_3"
    assert unique_name("b", ["a"]) == "b"


def test_set_frames_builds_items_without_snapshot(qapp, tmp_path):
    strip, undo = _strip(tmp_path)
    assert strip.count() == 4
    assert strip.list.count() == 4
    assert [f.name for f in strip.frames()] == [f"frame_{i:02d}" for i in range(4)]
    assert not undo.can_undo("act1")


def test_delete_pushes_snapshot_and_undo_restores(qapp, tmp_path):
    strip, undo = _strip(tmp_path)
    changed = []
    strip.framesChanged.connect(lambda: changed.append(1))
    strip.select_index(1)
    assert strip.delete_selected() == 1
    assert [f.name for f in strip.frames()] == ["frame_00", "frame_02", "frame_03"]
    assert changed == [1]
    assert undo.can_undo("act1")
    restored = undo.undo("act1", strip.frames())
    strip.set_frames(restored)
    assert strip.count() == 4


def test_duplicate_inserts_unique_name_after_source(qapp, tmp_path):
    strip, undo = _strip(tmp_path)
    strip.select_index(0)
    assert strip.duplicate_selected() == 1
    names = [f.name for f in strip.frames()]
    assert names[:2] == ["frame_00", "frame_00_copy"]
    assert strip.frames()[1].source_path == strip.frames()[0].source_path
    assert undo.can_undo("act1")
    strip.select_index(0)
    strip.duplicate_selected()
    assert [f.name for f in strip.frames()][1] == "frame_00_copy_2"


def test_move_frame_reorders(qapp, tmp_path):
    strip, undo = _strip(tmp_path)
    strip.move_frame(3, 0)
    assert [f.name for f in strip.frames()] == ["frame_03", "frame_00", "frame_01", "frame_02"]
    assert strip.list.item(0).data(fs.Qt.UserRole) == 0
    assert undo.can_undo("act1")


def test_insert_from_file_reads_size(qapp, tmp_path):
    strip, undo = _strip(tmp_path, 2)
    extra = write_frame_png(tmp_path / "extra" / "Wide Frame.png", size=(12, 6))
    strip.select_index(0)
    assert strip.insert_from_file([extra]) == 1
    inserted = strip.frames()[1]
    assert inserted.name == "Wide_Frame"
    assert inserted.source_size == (12, 6)
    assert inserted.frame == (0, 0, 12, 6)
    assert inserted.duration_ms == 100
    assert undo.can_undo("act1")
    anchor_dir = strip.frames()[0].source_path.parent
    assert inserted.source_path.parent == anchor_dir / "inserted"
    assert inserted.source_path.exists()
    assert inserted.source_path != extra
    assert extra.exists()  # the original external file is untouched


def test_insert_from_file_refuses_on_empty_strip(qapp, tmp_path, monkeypatch):
    undo = UndoController()
    strip = FrameStrip(undo)
    strip.set_action_id("act1")
    strip.set_frames([])
    extra = write_frame_png(tmp_path / "extra" / "Wide Frame.png", size=(12, 6))
    shown = []
    monkeypatch.setattr(fs.QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    assert strip.insert_from_file([extra]) == 0
    assert shown
    assert strip.count() == 0
    assert not undo.can_undo("act1")


def test_insert_from_file_reports_bad_image(qapp, tmp_path, monkeypatch):
    strip, undo = _strip(tmp_path, 1)
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not a png")
    shown = []
    monkeypatch.setattr(fs.QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    assert strip.insert_from_file([bad]) == 0
    assert shown and strip.count() == 1
    assert not undo.can_undo("act1")


def test_apply_duration_to_selection(qapp, tmp_path):
    strip, undo = _strip(tmp_path)
    strip.select_index(2)
    strip.duration_spin.setValue(250)
    strip.apply_duration()
    assert strip.frames()[2].duration_ms == 250
    assert strip.frames()[0].duration_ms == 100
    assert undo.can_undo("act1")


def test_apply_overrides(qapp, tmp_path):
    strip, undo = _strip(tmp_path)
    strip.apply_overrides([1, 2], {"tolerance": 0.3})
    assert strip.frames()[1].overrides == {"tolerance": 0.3}
    assert strip.frames()[2].overrides == {"tolerance": 0.3}
    assert strip.frames()[0].overrides == {}
    assert undo.can_undo("act1")


def test_overrides_dialog_values_only_enabled_fields(qapp):
    dialog = FrameOverridesDialog({"tolerance": 0.25})
    assert dialog.tolerance_on.isChecked()
    assert abs(dialog.tolerance.value() - 0.25) < 1e-9
    dialog.key_color_on.setChecked(True)
    dialog.key_color.setText("#00ff00")
    dialog.softness_on.setChecked(False)
    assert dialog.values() == {"tolerance": 0.25, "key_color": "#00FF00"}
    dialog.key_color.setText("garbage")
    assert "key_color" not in dialog.values()
    dialog.done(QDialog.Rejected)


def test_selection_emits_frame_selected_and_updates_spin(qapp, tmp_path):
    strip, _ = _strip(tmp_path)
    strip.frames()[3].duration_ms = 400
    strip.set_frames(strip.frames())
    got = []
    strip.frameSelected.connect(got.append)
    strip.select_index(3)
    assert got == [3]
    assert strip.duration_spin.value() == 400


def test_export_selected_frame_writes_png(qapp, tmp_path):
    strip, _ = _strip(tmp_path)
    strip.select_index(1)
    exported = []
    strip.frameExported.connect(exported.append)
    out = tmp_path / "out" / "single.png"
    assert strip.export_selected_frame(out) == out
    assert out.exists() and out.stat().st_size > 0
    assert exported == [out]


def test_request_retouch_emits_current_index(qapp, tmp_path):
    strip, _ = _strip(tmp_path)
    got = []
    strip.retouchRequested.connect(got.append)
    strip.select_index(2)
    strip.request_retouch()
    assert got == [2]


def test_refresh_rereads_thumbnails_after_source_repoint(qapp, tmp_path):
    strip, _ = _strip(tmp_path, 2)
    frame = strip.frames()[0]  # same FrameMeta object the strip holds
    before = strip.list.item(0).icon().pixmap(8, 8).toImage()
    frame.source_path = write_frame_png(tmp_path / "r" / "0000.r1.png", color=(0, 0, 255, 255))
    strip.select_index(1)
    strip.refresh()
    after = strip.list.item(0).icon().pixmap(8, 8).toImage()
    assert after != before
    assert strip.count() == 2
    assert strip.current_index() == 1  # selection survives a refresh


# ----- final review fixes -----

def test_edit_overrides_refuses_invalid_key_color(qapp, tmp_path, monkeypatch):
    """B2 / Important 5: an invalid key colour must not close the dialog or write an override."""
    strip, undo = _strip(tmp_path)
    shown = []
    monkeypatch.setattr(fs.QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))

    def fake_exec(self):
        # Stand in for the user checking Key color, typing "green", and
        # clicking OK: drive the dialog's real accept() (not QDialog's),
        # so the fix under test actually runs.
        self.key_color_on.setChecked(True)
        self.key_color.setText("green")
        self.accept()
        return self.result()

    monkeypatch.setattr(fs.FrameOverridesDialog, "exec", fake_exec)
    strip.select_index(0)
    strip.edit_overrides_for_selected()

    assert shown, "QMessageBox.warning was not shown for an invalid key colour"
    assert strip.frames()[0].overrides == {}
    assert not undo.can_undo("act1")


def test_frame_overrides_dialog_accept_rejects_bad_hex_directly(qapp, monkeypatch):
    """The dialog itself refuses OK on invalid input, independent of the caller."""
    dialog = FrameOverridesDialog({})
    shown = []
    monkeypatch.setattr(fs.QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    dialog.key_color_on.setChecked(True)
    dialog.key_color.setText("green")
    dialog.accept()
    assert dialog.result() != QDialog.Accepted
    assert shown
    dialog.done(QDialog.Rejected)


def test_missing_frame_file_warns_once_across_two_refreshes(qapp, tmp_path, caplog):
    """B4 / Minor 7: a missing source file shows a grey cell and warns exactly once."""
    strip, _ = _strip(tmp_path, 1)
    frame = strip.frames()[0]
    missing_path = frame.source_path
    missing_path.unlink()
    messages = []
    strip.logMessage.connect(lambda msg, level: messages.append((msg, level)))

    with caplog.at_level(logging.WARNING, logger="gui.sprite.frame_strip"):
        strip.refresh()
        strip.refresh()

    pixmap = strip.list.item(0).icon().pixmap(fs.THUMB_PX, fs.THUMB_PX)
    assert not pixmap.isNull()  # grey placeholder, not a failure to render at all

    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 1, [r.getMessage() for r in warning_records]
    assert messages == [(f"Thumbnail unavailable: {missing_path}", "WARNING")]


def test_insert_from_file_reports_mkdir_failure(qapp, tmp_path, monkeypatch):
    """B5 / Minor 9: a mkdir failure for inserted/ goes through the same error pattern as copy2."""
    strip, undo = _strip(tmp_path, 1)
    extra = write_frame_png(tmp_path / "extra" / "Wide Frame.png", size=(4, 4))
    shown = []
    monkeypatch.setattr(fs.QMessageBox, "critical", staticmethod(lambda *a, **k: shown.append(a)))

    real_mkdir = Path.mkdir

    def fake_mkdir(self, *args, **kwargs):
        if self.name == "inserted":
            raise OSError("permission denied")
        return real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(fs.Path, "mkdir", fake_mkdir)
    strip.select_index(0)

    assert strip.insert_from_file([extra]) == 0
    assert shown
    assert strip.count() == 1
    assert not undo.can_undo("act1")
