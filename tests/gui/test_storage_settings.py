"""Construction and wiring tests for the Storage Locations widget."""
import json

import pytest

import core.paths as paths_mod
from core.paths import DataPaths, Group


@pytest.fixture
def widget(tmp_path, monkeypatch, qapp):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))

    from gui.storage_settings_widget import StorageSettingsWidget

    return StorageSettingsWidget()


def test_widget_has_one_row_per_group(widget):
    assert set(widget.rows) == set(Group)


def test_each_row_has_move_and_open_buttons(widget):
    for group, row in widget.rows.items():
        assert row.move_button is not None, group
        assert row.open_button is not None, group


def test_rows_start_in_a_calculating_state(widget):
    for row in widget.rows.values():
        assert row.size_label.text() == "Calculating…"


def test_multi_tree_groups_are_labelled(widget, monkeypatch):
    """Models and Video can span two source trees before the first move."""
    assert widget.rows[Group.MODELS].path_label.toolTip()
    assert widget.rows[Group.VIDEO].path_label.toolTip()


def test_large_group_sizes_survive_the_signal(widget):
    """A group larger than 2 GB must not overflow the size signal."""
    from gui.storage_settings_widget import _SizeWorker

    received = []
    worker = _SizeWorker(Group.MODELS)
    worker.finished.connect(lambda name, total: received.append((name, total)))
    worker.finished.emit(Group.MODELS.value, 28_391_171_187)

    assert received == [("models", 28_391_171_187)]


def test_unreachable_root_shows_a_warning(tmp_path, monkeypatch, qapp):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"data_roots": {"images": str(tmp_path / "gone" / "x")}}),
                   encoding="utf-8")
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))

    from gui.storage_settings_widget import StorageSettingsWidget

    widget = StorageSettingsWidget()
    assert "Unavailable" in widget.rows[Group.IMAGES].status_label.text()


def _seed_images(tmp_path):
    """Give the Images group one real source tree so validation can pass."""
    source = tmp_path / "generated"
    source.mkdir(exist_ok=True)
    (source / "one.png").write_bytes(b"x" * 16)
    return source


def test_move_calls_the_migrator_with_the_chosen_directory(widget, tmp_path, monkeypatch):
    from core.data_migration import MoveResult

    _seed_images(tmp_path)
    chosen = tmp_path / "chosen"
    chosen.mkdir()
    calls = {}

    monkeypatch.setattr(
        "gui.storage_settings_widget.QFileDialog.getExistingDirectory",
        lambda *a, **k: str(chosen),
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._confirm", lambda *a, **k: True
    )
    def fake_run(self, group, dest):
        calls["args"] = (group, dest)
        return MoveResult(ok=True, files_moved=1, bytes_moved=10)

    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._run_with_progress", fake_run
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._offer_restart", lambda *a, **k: None
    )
    # Keep the temporary DataPaths in place: a real reset would point the
    # refresh at the developer's own data directories.
    monkeypatch.setattr(
        "gui.storage_settings_widget.reset_data_paths", lambda: None
    )

    widget._on_move(Group.IMAGES)
    assert calls["args"] == (Group.IMAGES, chosen)


def test_cancelled_picker_does_nothing(widget, monkeypatch):
    monkeypatch.setattr(
        "gui.storage_settings_widget.QFileDialog.getExistingDirectory",
        lambda *a, **k: "",
    )
    called = []
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._run_with_progress",
        lambda *a, **k: called.append(1),
    )
    widget._on_move(Group.IMAGES)
    assert not called


def test_failed_move_shows_the_error(widget, tmp_path, monkeypatch):
    from core.data_migration import MoveResult

    _seed_images(tmp_path)
    shown = []
    monkeypatch.setattr(
        "gui.storage_settings_widget.QFileDialog.getExistingDirectory",
        lambda *a, **k: str(tmp_path / "chosen"),
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._confirm", lambda *a, **k: True
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._run_with_progress",
        lambda *a, **k: MoveResult(ok=False, error="Not enough free space."),
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.QMessageBox.critical",
        lambda *a, **k: shown.append(a[2]),
    )

    widget._on_move(Group.IMAGES)
    assert shown and "free space" in shown[0]


def test_rejected_destination_is_reported(widget, tmp_path, monkeypatch):
    """A destination the migrator refuses never reaches the move step."""
    shown = []
    called = []
    monkeypatch.setattr(
        "gui.storage_settings_widget.QFileDialog.getExistingDirectory",
        lambda *a, **k: str(tmp_path),
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._run_with_progress",
        lambda *a, **k: called.append(1),
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.QMessageBox.critical",
        lambda *a, **k: shown.append(a[2]),
    )

    widget._on_move(Group.IMAGES)
    assert shown and not called


def test_main_window_exposes_the_storage_widget(qapp, monkeypatch):
    """The Settings tab must actually contain the widget."""
    import inspect

    from gui.main_window import MainWindow

    source = inspect.getsource(MainWindow._init_settings_tab)
    assert "StorageSettingsWidget" in source
    assert "storage_settings" in source
