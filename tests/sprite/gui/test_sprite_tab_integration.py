"""FramesWorkspace: builds the 5b widgets and wires them into SpriteTab (design §4.5)."""
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from core.sprite.models import FrameMeta
from gui.llm_utils import DialogStatusConsole
from gui.sprite.frames_workspace import FramesWorkspace
from gui_synthetic import make_frames, make_project


class _StubQueue(QObject):
    statusChanged = Signal()


class _StubTab(QWidget):
    """Implements the 5a SpriteTab contract that FramesWorkspace consumes."""

    projectChanged = Signal()
    actionSelected = Signal(str)

    def __init__(self, project=None):
        super().__init__()
        self._project = project
        self.console = DialogStatusConsole("Console")
        self.queue_panel = _StubQueue(self)
        self.placed = {}
        self.toolbar_buttons = []
        self.log_calls = []
        self._layout = QVBoxLayout(self)
        self._layout.addWidget(self.console)

    def add_toolbar_action(self, text, slot):
        button = QPushButton(text, self)
        button.clicked.connect(slot)
        self.toolbar_buttons.append(button)
        return button

    def log(self, message, level="INFO"):
        self.log_calls.append((message, level))
        self.console.log(message, level)

    def set_frame_widget(self, widget):
        self.placed["frame"] = widget
        self._layout.addWidget(widget)

    def set_preview_widget(self, widget):
        self.placed["preview"] = widget
        self._layout.addWidget(widget)

    def set_processing_widget(self, widget):
        self.placed["processing"] = widget
        self._layout.addWidget(widget)

    @property
    def current_project(self):
        return self._project

    def current_action(self):
        if self._project and self._project.actions:
            return self._project.actions[0]
        return None


def _workspace(qapp, tmp_path, monkeypatch):
    import gui.sprite.processing_panel as pp
    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": False, "rembg": False})
    project, action = make_project(tmp_path)
    tab = _StubTab(project)
    workspace = FramesWorkspace(tab)
    tab.projectChanged.emit()
    tab.actionSelected.emit(action.id)
    return tab, workspace, project, action


def _broken_png(tmp_path):
    """A file with a .png name that no image reader can decode."""
    path = tmp_path / "broken.png"
    path.write_bytes(b"not a png at all")
    return path


def _frame_at(path):
    return FrameMeta(name="broken", source_path=path, frame=(0, 0, 8, 8),
                     source_size=(8, 8), sprite_source_size=(0, 0, 8, 8), duration_ms=100)


def test_workspace_places_widgets_and_exposes_attributes(qapp, tmp_path, monkeypatch):
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    assert tab.placed["frame"] is workspace.strip
    assert tab.placed["preview"] is workspace.player
    assert tab.placed["processing"] is workspace.panel
    assert tab.frames_workspace is workspace
    assert tab.frame_strip is workspace.strip
    assert tab.preview_player is workspace.player
    assert tab.pixel_view is workspace.view is workspace.player.view
    assert tab.undo_controller is workspace.undo_controller
    assert tab.undo_stack is workspace.undo_controller.stack(action.id)
    assert tab.refresh_frames == workspace.refresh_frames
    assert [b.text() for b in tab.toolbar_buttons] == ["Export…"]
    assert workspace.export_btn is tab.toolbar_buttons[0]
    assert set(workspace.shortcuts) >= {"Space", "Ctrl+Z"}
    workspace.shutdown()


def test_queue_status_change_rereads_action_frames(qapp, tmp_path, monkeypatch):
    # The queue runs run_pipeline(upto="stabilize") after a clip lands, which rebuilds
    # action.frames; the strip must re-read the list instead of keeping a stale copy.
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    action.frames = make_frames(tmp_path / "rendered", 5)
    tab.queue_panel.statusChanged.emit()
    assert workspace.strip.count() == 5
    assert len(workspace.player.frames()) == 5
    workspace.shutdown()


def test_apply_frames_snapshots_reloads_and_emits_project_changed(qapp, tmp_path, monkeypatch):
    import copy
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    changed = []
    tab.projectChanged.connect(lambda: changed.append(1))
    old_path = action.frames[1].source_path
    # The sub-project 6 retouch pattern: a NEW list, never an in-place edit of the current frames.
    new_frames = copy.deepcopy(action.frames)
    new_frames[1].source_path = tmp_path / "stages" / "act1" / "stabilize" / "0001.r1.png"
    workspace.apply_frames(action.id, new_frames, "retouch 2")
    assert action.frames[1].source_path.name == "0001.r1.png"
    assert workspace.strip.count() == 4
    assert workspace.player.frames()[1].source_path.name == "0001.r1.png"
    assert changed == [1]
    assert "retouch 2" in tab.console.console.toPlainText()
    assert workspace.undo_controller.can_undo(action.id)
    assert workspace.undo() is True                      # the snapshot holds the old path
    assert action.frames[1].source_path == old_path
    workspace.apply_frames("no-such-action", new_frames, "ignored")  # logged, no raise
    assert ("ignored: action 'no-such-action' not found", "ERROR") in tab.log_calls
    workspace.shutdown()


def test_action_selected_loads_strip_player_and_panel(qapp, tmp_path, monkeypatch):
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    assert workspace.strip.count() == 4
    assert len(workspace.player.frames()) == 4
    assert workspace.player.tag_combo.count() == 2  # All frames + walk
    assert workspace.panel.action() is action
    assert workspace.panel.project() is project
    assert workspace.undo_controller.active_action == action.id
    assert workspace.strip.action_id() == action.id
    workspace.shutdown()


def test_strip_edit_updates_action_and_undo_restores(qapp, tmp_path, monkeypatch):
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    workspace.strip.select_index(1)
    workspace.strip.delete_selected()
    assert [f.name for f in action.frames] == ["frame_00", "frame_02", "frame_03"]
    assert len(workspace.player.frames()) == 3
    assert workspace.undo() is True
    assert len(action.frames) == 4
    assert workspace.strip.count() == 4
    assert len(workspace.player.frames()) == 4
    assert workspace.redo() is True
    assert len(action.frames) == 3
    assert workspace.strip.count() == 3
    workspace.shutdown()


def test_selection_sync_between_strip_and_player(qapp, tmp_path, monkeypatch):
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    workspace.strip.select_index(2)
    assert workspace.player.current_index() == 2
    workspace.player.set_current_index(3)
    assert workspace.strip.current_index() == 3
    workspace.shutdown()


def test_pipeline_finished_reloads_from_action(qapp, tmp_path, monkeypatch):
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    action.frames = make_frames(tmp_path / "again", 6)
    workspace.panel.pipelineFinished.emit(action.id)
    assert workspace.strip.count() == 6
    assert len(workspace.player.frames()) == 6
    action.frames = make_frames(tmp_path / "retouched", 2)
    tab.refresh_frames()  # the sub-project 6 entry point
    assert workspace.strip.count() == 2
    assert len(workspace.player.frames()) == 2
    workspace.shutdown()


def test_player_source_switch_uses_sheet_meta(qapp, tmp_path, monkeypatch):
    from core.sprite.project import SpriteProject
    from gui_synthetic import sheet_from_action
    seen = []

    def fake_sheet(self, profile):
        seen.append(profile)
        return sheet_from_action(self.actions[0], profile)

    monkeypatch.setattr(SpriteProject, "sheet_meta", fake_sheet)
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    workspace.player.source_combo.setCurrentIndex(1)  # "hd"
    assert seen == ["hd"]
    assert len(workspace.player.frames()) == 4
    workspace.shutdown()


def test_player_source_switch_reports_a_failing_profile(qapp, tmp_path, monkeypatch):
    from core.sprite.project import SpriteProject

    def broken_sheet(self, profile):
        raise RuntimeError("no pixel stage")

    monkeypatch.setattr(SpriteProject, "sheet_meta", broken_sheet)
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    workspace.player.source_combo.setCurrentIndex(2)  # "pixel"
    assert workspace.player.frames() == []
    assert ("Cannot load profile 'pixel': no pixel stage", "ERROR") in tab.log_calls
    workspace.shutdown()


class _FakeDialog(QObject):
    """Stands in for ExportDialog: the workspace only needs finished/logMessage/exec."""

    finished = Signal(int)
    logMessage = Signal(str, str)

    def __init__(self, proj, parent):
        super().__init__(parent)
        self.project = proj
        self.deleted = []
        self.shutdown_calls = []

    def exec(self):
        self.finished.emit(0)
        return 0

    def deleteLater(self):
        self.deleted.append(1)
        super().deleteLater()

    def shutdown(self, timeout_ms=5000):
        self.shutdown_calls.append(timeout_ms)
        return True

    def join_orphans(self, timeout_ms=None):
        return True


def test_export_request_opens_dialog_with_project(qapp, tmp_path, monkeypatch):
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    opened = []

    def factory(proj, parent):
        dialog = _FakeDialog(proj, parent)
        opened.append((proj, parent))
        return dialog

    monkeypatch.setattr(workspace, "export_dialog_factory", factory)
    workspace.panel.exportRequested.emit()
    assert opened == [(project, tab)]
    workspace.shutdown()


def test_export_dialog_is_parented_and_released_when_it_finishes(qapp, tmp_path, monkeypatch):
    # A parentless dialog that holds worker plumbing is freed by the cyclic collector at an
    # arbitrary time (5b Task 7 finding), so the dialog is a child of the tab and the
    # workspace holds it only while it is open.
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    made = []

    def factory(proj, parent):
        dialog = _FakeDialog(proj, parent)
        made.append(dialog)
        return dialog

    monkeypatch.setattr(workspace, "export_dialog_factory", factory)
    dialog = workspace.open_export_dialog()
    assert dialog is made[0]
    assert dialog.parent() is tab
    assert dialog.deleted == [1]                 # scheduled for deletion on finished
    assert workspace._export_dialog is None      # the reference is dropped again
    dialog.logMessage.emit("late line", "INFO")  # disconnected with the dialog; no crash
    workspace.shutdown()


def test_shutdown_stops_an_open_export_dialog(qapp, tmp_path, monkeypatch):
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    dialog = _FakeDialog(project, tab)
    workspace._export_dialog = dialog
    assert workspace.shutdown() is True
    assert dialog.shutdown_calls == [5000]
    assert workspace.join_orphans() is True


def test_export_without_a_project_is_logged_and_shown(qapp, tmp_path, monkeypatch):
    import gui.sprite.frames_workspace as fw
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    shown = []
    monkeypatch.setattr(fw.QMessageBox, "warning",
                        lambda *args, **kwargs: shown.append(args[1:3]))
    tab._project = None
    tab.projectChanged.emit()
    assert workspace.open_export_dialog() is None
    assert ("Export: open or create a sprite project first.", "WARNING") in tab.log_calls
    assert shown == [("Export", "Open or create a sprite project first.")]
    workspace.shutdown()


def test_decode_failures_are_logged_and_shown(qapp, tmp_path, monkeypatch):
    # Task 2 / Task 3 carry-forward: a frame that cannot be decoded must reach the console,
    # not only the file log, or the preview goes blank with no explanation.
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    broken = _broken_png(tmp_path)
    action.frames = [_frame_at(broken)]
    workspace.refresh_frames()
    assert [level for message, level in tab.log_calls if "broken.png" in message] == ["WARNING"]

    tab.log_calls.clear()
    assert workspace.set_view_image(broken) is False
    assert [level for message, level in tab.log_calls if "broken.png" in message] == ["WARNING"]
    assert workspace.set_view_image(None) is True
    workspace.shutdown()


def test_no_project_clears_everything(qapp, tmp_path, monkeypatch):
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    tab._project = None
    tab.projectChanged.emit()
    assert workspace.strip.count() == 0
    assert workspace.player.frames() == []
    assert workspace.panel.action() is None
    assert workspace.undo() is False
    assert workspace.redo() is False
    workspace.shutdown()


class _FakeConfig:
    """The config surface the 5a panels read (mirrors tests in the 5a plan)."""

    def __init__(self):
        self.store = {}

    def get(self, key, default=None):
        return self.store.get(key, default)

    def set(self, key, value):
        self.store[key] = value

    def save(self):
        pass

    def get_api_key(self, provider):
        return "test-key"

    def get_auth_mode(self, provider="google"):
        return "api-key"


def test_real_sprite_tab_constructs_workspace(qapp, monkeypatch):
    import gui.sprite.processing_panel as pp
    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": False, "rembg": False})
    from gui.sprite.sprite_tab import SpriteTab
    tab = SpriteTab(_FakeConfig())
    assert isinstance(tab.frames_workspace, FramesWorkspace)
    assert tab.frame_strip is tab.frames_workspace.strip
    assert tab.frame_area.layout().itemAt(0).widget() is tab.frames_workspace.strip
    assert tab.preview_area.layout().itemAt(0).widget() is tab.frames_workspace.player
    assert tab.processing_area.layout().itemAt(0).widget() is tab.frames_workspace.panel
    tab.frames_workspace.shutdown()


def test_real_sprite_tab_shutdown_covers_the_workspace(qapp, monkeypatch):
    import gui.sprite.processing_panel as pp
    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": False, "rembg": False})
    from gui.sprite.sprite_tab import SpriteTab
    tab = SpriteTab(_FakeConfig())
    calls = []
    monkeypatch.setattr(tab.frames_workspace, "shutdown", lambda: calls.append("shutdown") or True)
    monkeypatch.setattr(tab.frames_workspace, "join_orphans",
                        lambda timeout_ms=None: calls.append(("join", timeout_ms)) or True)
    assert tab.shutdown() is True
    assert tab.join_orphans(100) is True
    assert calls == ["shutdown", ("join", 100)]


def test_real_sprite_tab_shutdown_reports_a_workspace_orphan(qapp, monkeypatch):
    import gui.sprite.processing_panel as pp
    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": False, "rembg": False})
    from gui.sprite.sprite_tab import SpriteTab
    tab = SpriteTab(_FakeConfig())
    monkeypatch.setattr(tab.frames_workspace, "shutdown", lambda: False)
    assert tab.shutdown() is False          # the caller must join_orphans() before teardown
    monkeypatch.setattr(tab.frames_workspace, "shutdown", lambda: True)
    assert tab.shutdown() is True
