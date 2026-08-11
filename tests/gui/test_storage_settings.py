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


def test_unreleasable_settings_log_file_is_named(qapp, caplog):
    """The Settings branch must name the log file it cannot close."""
    import types

    from gui.main_window import MainWindow

    with caplog.at_level(logging.WARNING):
        MainWindow.close_data_handles(types.SimpleNamespace(), Group.SETTINGS)

    warnings = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("log file" in message for message in warnings), warnings


def test_unreleasable_torch_weights_are_named(qapp, caplog, monkeypatch):
    """A loaded PyTorch keeps weight files mapped; the log must say so."""
    import sys
    import types

    from gui.main_window import MainWindow

    fake_torch = types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=lambda: False)
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    with caplog.at_level(logging.WARNING):
        MainWindow.close_data_handles(types.SimpleNamespace(), Group.MODELS)

    warnings = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("PyTorch" in message for message in warnings), warnings


def test_watcher_that_refuses_to_pause_is_named(qapp, caplog):
    """A handle this process cannot release must name the owner."""
    import types

    from gui.main_window import MainWindow

    class _StubbornWatcher:
        enabled = True

        def set_enabled(self, value):
            raise RuntimeError("watcher busy")

    stub = types.SimpleNamespace(midjourney_watcher=_StubbornWatcher())
    with caplog.at_level(logging.WARNING):
        MainWindow.close_data_handles(stub, Group.IMAGES)

    warnings = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("Midjourney watcher" in message for message in warnings), warnings


def test_unreleasable_video_event_store_is_named(qapp, caplog):
    """An event store that refuses to drop must be named in the log."""
    import types

    from gui.main_window import MainWindow

    class _StuckOwner:
        def __init__(self):
            object.__setattr__(self, "event_store", object())

        def __setattr__(self, name, value):
            raise RuntimeError("attribute is read only")

    stub = types.SimpleNamespace(
        _video_tab_loaded=True,
        tab_video=types.SimpleNamespace(
            event_store=None, history_tab=_StuckOwner(), workspace=None
        ),
    )
    with caplog.at_level(logging.WARNING):
        MainWindow.close_data_handles(stub, Group.VIDEO)

    warnings = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("event store" in message for message in warnings), warnings


# --- releasing handles must be reversible ---------------------------------


class _FakeWatcher:
    """Stand-in for the Midjourney download watcher."""

    def __init__(self, enabled=True):
        self.enabled = bool(enabled)

    def set_enabled(self, value):
        self.enabled = bool(value)


class _FakeHistoryTab:
    """Stand-in for gui.video.history_tab.HistoryTab."""

    def __init__(self):
        self.event_store = object()
        self.rebuilds = 0

    def init_event_store(self):
        self.rebuilds += 1
        self.event_store = object()


def _window_stub():
    """A main-window stand-in that owns every releasable resource."""
    import types

    history_tab = _FakeHistoryTab()
    workspace = types.SimpleNamespace(current_project=None)
    video_tab = types.SimpleNamespace(
        event_store=None, history_tab=history_tab, workspace=workspace
    )
    return types.SimpleNamespace(
        midjourney_watcher=_FakeWatcher(),
        tab_video=video_tab,
        _video_tab_loaded=True,
    )


def test_main_window_implements_restore_data_handles(qapp):
    from gui.main_window import MainWindow

    assert callable(getattr(MainWindow, "restore_data_handles", None))


def test_restore_re_enables_the_midjourney_watcher(qapp):
    """A failed move must not leave the watcher off for the session."""
    from gui.main_window import MainWindow

    stub = _window_stub()
    MainWindow.close_data_handles(stub, Group.IMAGES)
    assert stub.midjourney_watcher.enabled is False

    MainWindow.restore_data_handles(stub, Group.IMAGES)

    assert stub.midjourney_watcher.enabled is True
    assert getattr(stub, "_midjourney_watch_paused", False) is False


def test_restore_rebuilds_the_video_event_store(qapp):
    """The History tab must load events again after a failed move."""
    from gui.main_window import MainWindow

    stub = _window_stub()
    MainWindow.close_data_handles(stub, Group.VIDEO)
    assert stub.tab_video.history_tab.event_store is None

    MainWindow.restore_data_handles(stub, Group.VIDEO)

    assert stub.tab_video.history_tab.event_store is not None
    assert stub.tab_video.history_tab.rebuilds == 1


def test_restore_of_an_unknown_group_is_logged(qapp, caplog):
    from gui.main_window import MainWindow

    with caplog.at_level(logging.ERROR):
        MainWindow.restore_data_handles(_window_stub(), "not-a-group")

    assert any(r.levelno >= logging.ERROR for r in caplog.records)


def test_failed_move_restores_the_released_handles(hosted_widget, tmp_path, monkeypatch):
    """A move that fails must leave the app as usable as it was."""
    from core.data_migration import MoveResult

    widget, host = hosted_widget
    _seed_images(tmp_path)
    released, restored = [], []
    host.close_data_handles = released.append
    host.restore_data_handles = restored.append

    monkeypatch.setattr(
        "gui.storage_settings_widget.QFileDialog.getExistingDirectory",
        lambda *a, **k: str(tmp_path / "chosen"),
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._confirm", lambda *a, **k: True
    )

    def fake_run(self, group, dest):
        self._close_open_resources(group)
        return MoveResult(ok=False, error="Copy failed: No space left on device.")

    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._run_with_progress", fake_run
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.QMessageBox.critical", lambda *a, **k: None
    )

    widget._on_move(Group.IMAGES)

    assert released == [Group.IMAGES]
    assert restored == [Group.IMAGES]


def test_cancelled_move_restores_the_released_handles(hosted_widget, tmp_path, monkeypatch):
    """"Nothing was changed" must also be true for in-process state."""
    from core.data_migration import MoveResult

    widget, host = hosted_widget
    _seed_images(tmp_path)
    released, restored = [], []
    host.close_data_handles = released.append
    host.restore_data_handles = restored.append

    monkeypatch.setattr(
        "gui.storage_settings_widget.QFileDialog.getExistingDirectory",
        lambda *a, **k: str(tmp_path / "chosen"),
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._confirm", lambda *a, **k: True
    )

    def fake_run(self, group, dest):
        self._close_open_resources(group)
        return MoveResult(ok=False, error="Move cancelled. Nothing was changed.")

    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._run_with_progress", fake_run
    )
    monkeypatch.setattr(
        "gui.storage_settings_widget.QMessageBox.critical", lambda *a, **k: None
    )

    widget._on_move(Group.IMAGES)

    assert released == [Group.IMAGES]
    assert restored == [Group.IMAGES]


def _click_restart_button(monkeypatch, label):
    """Drive the restart prompt as if the user pressed one named button."""
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(
        QMessageBox,
        "clickedButton",
        lambda self: next(
            (b for b in self.buttons() if b.text().replace("&", "") == label), None
        ),
    )


def test_later_choice_restores_the_released_handles(hosted_widget, monkeypatch):
    """A successful move the user does not restart after must still recover."""
    from core.data_migration import MoveResult

    widget, host = hosted_widget
    restored = []
    host.restore_data_handles = restored.append
    _click_restart_button(monkeypatch, "Later")

    widget._offer_restart(Group.VIDEO, MoveResult(ok=True, files_moved=1, bytes_moved=16))

    assert restored == [Group.VIDEO]


def test_restart_choice_does_not_restore_the_handles(hosted_widget, monkeypatch):
    """A restart rebuilds everything, so no restore runs before it."""
    from core.data_migration import MoveResult

    widget, host = hosted_widget
    restored, restarts = [], []
    host.restore_data_handles = restored.append
    monkeypatch.setattr(
        "gui.storage_settings_widget.StorageSettingsWidget._restart_application",
        lambda self: restarts.append(1),
    )
    _click_restart_button(monkeypatch, "Restart Now")

    widget._offer_restart(Group.VIDEO, MoveResult(ok=True, files_moved=1, bytes_moved=16))

    assert restarts == [1]
    assert restored == []


def test_missing_restore_hook_is_logged(hosted_widget, caplog):
    """A window without the hook must say so; silence hides the defect."""
    widget, host = hosted_widget
    assert not hasattr(host, "restore_data_handles")

    with caplog.at_level(logging.WARNING, logger="gui.storage_settings_widget"):
        widget._restore_open_resources(Group.VIDEO)

    assert any("restore_data_handles" in r.message for r in caplog.records)


def test_restore_hook_failure_is_logged(hosted_widget, caplog):
    widget, host = hosted_widget

    def boom(group):
        raise RuntimeError("restore failed")

    host.restore_data_handles = boom

    with caplog.at_level(logging.ERROR, logger="gui.storage_settings_widget"):
        widget._restore_open_resources(Group.VIDEO)

    assert any(r.levelno >= logging.ERROR for r in caplog.records)


def test_history_tab_reopens_a_released_event_store(qapp, tmp_path, monkeypatch):
    """The History tab must rebuild its store on the next access."""
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))

    from gui.video.history_tab import HistoryTab

    tab = HistoryTab()
    try:
        assert tab.event_store is not None
        tab.event_store = None  # what close_data_handles does before a move

        assert tab.ensure_event_store() is not None
        assert tab.event_store is not None
    finally:
        tab.deleteLater()


# --- unreachable-root reporting -------------------------------------------


def test_unreachable_root_warning_is_not_logged_twice(tmp_path, monkeypatch, qapp, caplog):
    """The logging sink already wrote it; the widget must not repeat it."""
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps({"data_roots": {"images": str(tmp_path / "gone")}}), encoding="utf-8"
    )
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))
    _sandbox_sources(monkeypatch)

    delivered = []
    monkeypatch.setattr(paths_mod, "_WARNING_SINK", delivered.append)

    from gui.storage_settings_widget import StorageSettingsWidget

    with caplog.at_level(logging.WARNING, logger="gui.storage_settings_widget"):
        widget = StorageSettingsWidget()
    try:
        assert sum("images" in m for m in delivered) == 1, delivered
        repeats = [r.message for r in caplog.records if "unavailable" in r.message.lower()]
        assert repeats == [], repeats
        assert "Unavailable" in widget.rows[Group.IMAGES].status_label.text()
    finally:
        _drain_threads(widget)


def test_unreachable_root_is_logged_when_no_sink_listens(tmp_path, monkeypatch, qapp, caplog):
    """Without a sink the widget is the only reader; it must log."""
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps({"data_roots": {"images": str(tmp_path / "gone")}}), encoding="utf-8"
    )
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))
    _sandbox_sources(monkeypatch)
    monkeypatch.setattr(paths_mod, "_WARNING_SINK", None)

    from gui.storage_settings_widget import StorageSettingsWidget

    with caplog.at_level(logging.WARNING, logger="gui.storage_settings_widget"):
        widget = StorageSettingsWidget()
    try:
        assert any("unavailable" in r.message.lower() for r in caplog.records)
    finally:
        _drain_threads(widget)


def test_unreachable_settings_root_flags_its_row(tmp_path, monkeypatch, qapp):
    """The Settings root resolves before the widget exists; the row must know."""
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps({"data_roots": {"settings": str(tmp_path / "offline")}}),
        encoding="utf-8",
    )
    paths = DataPaths(config_path=cfg)
    monkeypatch.setattr(paths_mod, "_INSTANCE", paths)
    _sandbox_sources(monkeypatch)

    # setup_logging resolves the Settings root and empties the buffer long
    # before the Settings tab is built. Reproduce that here.
    paths.root(Group.SETTINGS)
    assert paths.drain_warnings()

    from gui.storage_settings_widget import StorageSettingsWidget

    widget = StorageSettingsWidget()
    try:
        assert "Unavailable" in widget.rows[Group.SETTINGS].status_label.text()
    finally:
        _drain_threads(widget)


def test_reachable_roots_carry_no_marker(tmp_path, monkeypatch, qapp):
    good = tmp_path / "good"
    good.mkdir()
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps({"data_roots": {"images": str(good)}}), encoding="utf-8"
    )
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))
    _sandbox_sources(monkeypatch)

    from gui.storage_settings_widget import StorageSettingsWidget

    widget = StorageSettingsWidget()
    try:
        for group, row in widget.rows.items():
            assert row.status_label.text() == "", group
            assert row.status_label.isVisible() is False, group
    finally:
        _drain_threads(widget)


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
