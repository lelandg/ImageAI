"""Construction and wiring tests for the Storage Locations widget."""
import json
import logging

import pytest

import core.paths as paths_mod
from core.paths import DataPaths, Group


def _sandbox_sources(monkeypatch):
    """Keep the size workers inside the temporary root.

    The real ``sources_for`` reaches into the developer's home directory —
    ``~/.cache/huggingface`` holds many gigabytes. A test must never walk it.
    """

    def fake_sources(group, paths=None):
        root = (paths or paths_mod.get_data_paths()).root(group)
        return [(root / group.value, group.value)]

    monkeypatch.setattr("gui.storage_settings_widget.sources_for", fake_sources)


def _drain_threads(widget, timeout=10.0):
    """Let every size worker finish before the widget goes away.

    The worker signals the thread to quit through a queued connection, so the
    main event loop must run for the thread to end. A test has no event loop,
    so pump events by hand here.
    """
    import time

    from PySide6.QtWidgets import QApplication

    deadline = time.monotonic() + timeout
    for thread, _worker in list(getattr(widget, "_threads", [])):
        while thread.isRunning() and time.monotonic() < deadline:
            QApplication.processEvents()
            thread.wait(10)
        thread.quit()
        thread.wait(1000)
    QApplication.processEvents()


@pytest.fixture
def widget(tmp_path, monkeypatch, qapp):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))
    _sandbox_sources(monkeypatch)

    from gui.storage_settings_widget import StorageSettingsWidget

    made = StorageSettingsWidget()
    yield made
    _drain_threads(made)


class _FakeConfig:
    """Stand-in for the live ConfigManager the main window holds."""

    def __init__(self, data=None):
        self.config = dict(data or {})
        self.saves = 0

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value

    def save(self):
        self.saves += 1


@pytest.fixture
def hosted_widget(tmp_path, monkeypatch, qapp):
    """A widget inside a window that carries a config, like the real app."""
    from PySide6.QtWidgets import QWidget

    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))
    _sandbox_sources(monkeypatch)

    from gui.storage_settings_widget import StorageSettingsWidget

    host = QWidget()
    host.config = _FakeConfig()
    made = StorageSettingsWidget(host)
    yield made, host
    _drain_threads(made)


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
    _sandbox_sources(monkeypatch)

    from gui.storage_settings_widget import StorageSettingsWidget

    widget = StorageSettingsWidget()
    try:
        assert "Unavailable" in widget.rows[Group.IMAGES].status_label.text()
    finally:
        _drain_threads(widget)


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


def _patch_successful_move(monkeypatch, chosen):
    """Drive _on_move through a successful move without touching the disk."""
    from core.data_migration import MoveResult

    monkeypatch.setattr(
        "gui.storage_settings_widget.QFileDialog.getExistingDirectory",
        lambda *a, **k: str(chosen),
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._confirm", lambda *a, **k: True
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._run_with_progress",
        lambda self, group, dest: MoveResult(ok=True, files_moved=1, bytes_moved=16),
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._offer_restart", lambda *a, **k: None
    )
    monkeypatch.setattr("gui.storage_settings_widget.reset_data_paths", lambda: None)


def test_move_updates_the_live_config_in_memory(hosted_widget, tmp_path, monkeypatch):
    """A later config.save() must not write the pre-move dict back."""
    widget, host = hosted_widget
    _seed_images(tmp_path)
    chosen = tmp_path / "chosen"
    chosen.mkdir()
    _patch_successful_move(monkeypatch, chosen)

    widget._on_move(Group.IMAGES)

    assert host.config.config["data_roots"]["images"] == str(chosen)


def test_move_keeps_the_other_roots_in_the_live_config(hosted_widget, tmp_path, monkeypatch):
    widget, host = hosted_widget
    host.config.set("data_roots", {"models": "/mnt/big/models"})
    _seed_images(tmp_path)
    chosen = tmp_path / "chosen"
    chosen.mkdir()
    _patch_successful_move(monkeypatch, chosen)

    widget._on_move(Group.IMAGES)

    roots = host.config.config["data_roots"]
    assert roots["models"] == "/mnt/big/models"
    assert roots["images"] == str(chosen)


def test_failed_move_leaves_the_live_config_alone(hosted_widget, tmp_path, monkeypatch):
    from core.data_migration import MoveResult

    widget, host = hosted_widget
    _seed_images(tmp_path)
    monkeypatch.setattr(
        "gui.storage_settings_widget.QFileDialog.getExistingDirectory",
        lambda *a, **k: str(tmp_path / "chosen"),
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._confirm", lambda *a, **k: True
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._run_with_progress",
        lambda *a, **k: MoveResult(ok=False, error="Copy failed."),
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.QMessageBox.critical", lambda *a, **k: None
    )

    widget._on_move(Group.IMAGES)

    assert "data_roots" not in host.config.config


def test_pre_move_hook_reaches_the_main_window(hosted_widget):
    widget, host = hosted_widget
    seen = []
    host.close_data_handles = lambda group: seen.append(group)

    widget._close_open_resources(Group.VIDEO)

    assert seen == [Group.VIDEO]


def test_missing_close_hook_is_logged(hosted_widget, caplog):
    """A hook that is not there must be visible in the log, never silent."""
    widget, host = hosted_widget
    assert not hasattr(host, "close_data_handles")

    with caplog.at_level(logging.WARNING, logger="gui.storage_settings_widget"):
        widget._close_open_resources(Group.VIDEO)

    assert any("close_data_handles" in record.message for record in caplog.records)


def test_move_passes_the_group_to_the_pre_move_hook(widget, tmp_path, monkeypatch):
    """move_group must receive a hook, and the hook must know its group."""
    import core.data_migration as migration

    _seed_images(tmp_path)
    seen = []
    widget._close_open_resources = lambda group: seen.append(group)

    captured = {}

    def fake_move_group(group, dest, **kwargs):
        captured["pre_move"] = kwargs.get("pre_move")
        kwargs["pre_move"]()
        return migration.MoveResult(ok=True, files_moved=1, bytes_moved=16)

    monkeypatch.setattr("gui.storage_settings_widget.move_group", fake_move_group)
    widget._run_with_progress(Group.IMAGES, tmp_path / "chosen")

    assert callable(captured["pre_move"])
    assert seen == [Group.IMAGES]


def test_main_window_implements_close_data_handles(qapp):
    """The hook the widget calls must exist on MainWindow and run safely."""
    import types

    from gui.main_window import MainWindow

    assert callable(getattr(MainWindow, "close_data_handles", None))

    stub = types.SimpleNamespace()
    MainWindow.close_data_handles(stub, Group.VIDEO)
    MainWindow.close_data_handles(stub, Group.SETTINGS)
    MainWindow.close_data_handles(stub, Group.IMAGES)
    MainWindow.close_data_handles(stub, Group.MODELS)


def test_unreleasable_resource_is_logged_at_warning(qapp, caplog):
    """A handle this process keeps open must be named in the log."""
    import types

    from gui.main_window import MainWindow

    stub = types.SimpleNamespace()
    with caplog.at_level(logging.WARNING):
        MainWindow.close_data_handles(stub, Group.SETTINGS)

    assert any(record.levelno >= logging.WARNING for record in caplog.records)


def test_status_label_does_not_share_a_cell_with_the_path(widget):
    """The status text must not render on top of the path and buttons."""
    grid = widget.layout()
    for group, row in widget.rows.items():
        path_index = grid.indexOf(row.path_label)
        status_index = grid.indexOf(row.status_label)
        path_row = grid.getItemPosition(path_index)[0]
        status_row = grid.getItemPosition(status_index)[0]
        status_column = grid.getItemPosition(status_index)[1]
        path_column = grid.getItemPosition(path_index)[1]
        assert (path_row, path_column) != (status_row, status_column), group
        assert path_row != status_row or status_column > 4, group


def test_refresh_prunes_finished_size_workers(widget, qapp):
    """The thread list must not grow without bound."""
    _drain_threads(widget)
    before = len(widget._threads)

    widget.refresh_sizes()
    _drain_threads(widget)
    widget.refresh_sizes()
    _drain_threads(widget)

    assert len(widget._threads) <= before


def test_restart_does_not_use_execv(qapp):
    """os.execv skips closeEvent and mis-quotes Windows paths with spaces."""
    import inspect

    from gui.storage_settings_widget import StorageSettingsWidget

    source = inspect.getsource(StorageSettingsWidget._restart_application)
    assert "execv" not in source


def test_main_window_exposes_the_storage_widget(qapp, monkeypatch):
    """The Settings tab must actually contain the widget."""
    import inspect

    from gui.main_window import MainWindow

    source = inspect.getsource(MainWindow._init_settings_tab)
    assert "StorageSettingsWidget" in source
    assert "storage_settings" in source
