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
        self.saved = []
        self._layout = QVBoxLayout(self)
        self._layout.addWidget(self.console)

    def save_current_project(self):
        self.saved.append(self._project)

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


def test_apply_frames_saves_the_project_and_does_not_rebuild_the_panel(qapp, tmp_path, monkeypatch):
    # Review Important 3: the retouch path must persist, and the projectChanged it emits must
    # not re-enter _on_project_changed and rebuild every profile editor.
    import copy
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    editors = list(workspace.panel.profile_editors.values())
    assert editors, "the fixture project must have output profiles for this test to mean anything"
    tab.saved.clear()
    workspace.apply_frames(action.id, copy.deepcopy(action.frames), "retouch")
    assert tab.saved == [project]                                       # autosaved once
    assert list(workspace.panel.profile_editors.values()) == editors    # same widgets, no rebuild
    assert workspace.panel.project() is project
    workspace.shutdown()


def test_apply_frames_on_another_action_does_not_touch_the_shown_widgets(qapp, tmp_path, monkeypatch):
    # Review Minor 4: the strip and the player always show the SELECTED action.
    from core.sprite.project import ActionCard
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    other = ActionCard(id="act2", name="jump", prompt="jump")
    other.frames = make_frames(tmp_path / "jump", 2)
    project.actions.append(other)
    replacement = make_frames(tmp_path / "jump_v2", 7)

    # Minor 11: the end-state assertions below cannot fail on their own. apply_frames emits
    # projectChanged, whose same-project fast path calls refresh_frames() and heals the strip
    # from the SELECTED action, so a reload=True regression is invisible afterwards. Record
    # every widget write instead, and assert the other card's list never reached the widgets.
    set_frames_calls = []
    reload_calls = []
    real_set_frames = workspace.strip.set_frames
    real_reload_player = workspace._reload_player

    def record_set_frames(frames):
        set_frames_calls.append([f.name for f in frames])
        real_set_frames(frames)

    def record_reload_player():
        reload_calls.append(workspace.strip.count())
        real_reload_player()

    monkeypatch.setattr(workspace.strip, "set_frames", record_set_frames)
    monkeypatch.setattr(workspace, "_reload_player", record_reload_player)

    workspace.apply_frames(other.id, replacement, "retouch jump")

    replacement_names = [f.name for f in replacement]
    assert replacement_names not in set_frames_calls     # the strip never held the other card
    assert set_frames_calls == [[f.name for f in action.frames]]  # one write: the selected card
    assert reload_calls == [len(action.frames)]          # one reload, over the healed strip

    assert [f.name for f in other.frames] == replacement_names              # written
    assert workspace.undo_controller.can_undo(other.id)                     # snapshot pushed
    assert workspace.strip.action_id() == action.id                         # still the selected card
    assert workspace.strip.count() == len(action.frames) == 4               # not the other 7 frames
    assert len(workspace.player.frames()) == 4
    assert tab.saved == [project]                                           # still persisted
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


def test_real_export_dialog_is_alive_on_return_and_deleted_afterwards(qapp, tmp_path, monkeypatch):
    # Final review Minor 2: the workspace releases its reference in `finally` and calls
    # deleteLater() only after exec() returns, so the caller still receives a readable
    # dialog — sub-project 6 registers its export formats on it — and the object goes away
    # once the event loop delivers the deferred delete. A fake dialog runs no event loop, so
    # only the real ExportDialog shows that a real modal loop leaves the object valid.
    import shiboken6
    from PySide6.QtCore import QEvent, QTimer
    from gui.sprite.export_dialog import ExportDialog

    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)

    def factory(proj, parent):
        # The REAL QDialog.exec() runs a nested event loop; a zero-timer closes it from
        # inside. A stubbed exec() would run no loop at all and could not show the bug.
        built = ExportDialog(proj, parent)
        QTimer.singleShot(0, lambda: built.done(0))
        return built

    monkeypatch.setattr(workspace, "export_dialog_factory", factory)

    dialog = workspace.open_export_dialog()
    assert isinstance(dialog, ExportDialog)
    assert shiboken6.isValid(dialog)             # the caller receives a live object
    assert dialog.parent() is tab
    assert dialog.formats()                      # readable: sub-project 6 registers formats here
    assert workspace._export_dialog is None      # the reference is dropped again

    qapp.sendPostedEvents(None, QEvent.DeferredDelete)
    qapp.processEvents()
    assert not shiboken6.isValid(dialog)         # and the dialog is gone once the loop runs
    workspace.shutdown()


def test_export_dialog_reference_is_released_even_without_a_finished_signal(qapp, tmp_path,
                                                                           monkeypatch):
    # Releasing after exec() instead of on `finished` does not depend on the dialog emitting
    # anything: a dialog closed without a finished signal must not stay held forever, or the
    # workspace refuses every later export and shutdown() keeps poking a closed dialog.
    class _SilentDialog(QObject):
        finished = Signal(int)
        logMessage = Signal(str, str)

        def __init__(self, proj, parent):
            super().__init__(parent)

        def exec(self):
            return 0        # closed without emitting finished

        def shutdown(self, timeout_ms=5000):
            return True

        def join_orphans(self, timeout_ms=None):
            return True

    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    monkeypatch.setattr(workspace, "export_dialog_factory", _SilentDialog)
    dialog = workspace.open_export_dialog()
    assert dialog is not None
    assert workspace._export_dialog is None                # released by open_export_dialog
    assert workspace.open_export_dialog() is not dialog    # a later export is not blocked
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


def test_export_is_refused_while_the_panel_runs(qapp, tmp_path, monkeypatch):
    # Final review Important 3: the pipeline rewrites action.frames, the locked palette and
    # the stage directories the export reads, and no lock guards SpriteProject. The toolbar
    # Export button follows the panel's own Export button, and open_export_dialog refuses
    # even when the caller bypasses the button (a shortcut, sub-project 6).
    import threading
    import gui.sprite.processing_panel as pp

    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    release = threading.Event()

    def blocked_pipeline(*args, **kwargs):
        release.wait(20)
        return {"pixel": []}

    monkeypatch.setattr(pp, "run_pipeline", blocked_pipeline)
    opened = []

    def factory(proj, parent):
        opened.append(proj)
        return _FakeDialog(proj, parent)

    monkeypatch.setattr(workspace, "export_dialog_factory", factory)
    assert workspace.export_btn.isEnabled()          # idle: the toolbar button is live

    workspace.panel.run_pipeline()
    worker = workspace.panel._worker
    assert worker is not None and workspace.panel.is_busy()
    assert not workspace.export_btn.isEnabled()      # gated with the panel's own button
    assert workspace.open_export_dialog() is None
    assert opened == []                              # no dialog was built
    assert (f"Wait for the running {workspace.panel.busy_label} job to finish before "
            f"exporting", "WARNING") in tab.log_calls

    release.set()
    assert worker.wait(5000)
    for _ in range(5):
        qapp.processEvents()
    assert not workspace.panel.is_busy()
    assert workspace.export_btn.isEnabled()          # re-enabled once the panel is idle
    assert workspace.open_export_dialog() is not None
    assert opened == [project]
    workspace.shutdown()


def test_decode_failures_are_logged_and_shown(qapp, tmp_path, monkeypatch):
    # Task 2 / Task 3 carry-forward: a frame that cannot be decoded must reach the console,
    # not only the file log, or the preview goes blank with no explanation.
    tab, workspace, project, action = _workspace(qapp, tmp_path, monkeypatch)
    broken = _broken_png(tmp_path)
    action.frames = [_frame_at(broken)]
    workspace.refresh_frames()
    # Every console line about the file is a WARNING, and the player's own decode failure is
    # one of them. The count is not pinned: the strip reports an unreadable thumbnail on the
    # same console, and that is a second warning about the same file.
    levels = [level for message, level in tab.log_calls if "broken.png" in message]
    assert levels and set(levels) == {"WARNING"}
    assert any(message.startswith("Cannot decode frame image:") for message, _ in tab.log_calls)

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


def test_apply_frames_persists_through_the_real_tab(qapp, monkeypatch):
    # Review Important 3: SpriteTab.save_current_project() is the public autosave path, and
    # apply_frames must go through it — a retouch has to survive a crash.
    from pathlib import Path
    import gui.sprite.processing_panel as pp
    monkeypatch.setattr(pp, "available_backends", lambda: {"mediapipe": False, "rembg": False})
    from gui.sprite.sprite_tab import SpriteTab
    tab = SpriteTab(_FakeConfig())
    project = tab.new_project_named("persist")
    card = tab.action_cards_panel.add_card()
    tab.action_cards_panel.table.selectRow(0)
    assert tab.current_action() is card
    assert tab.frames_workspace.current_action() is card

    saved = tab.save_project()
    assert saved is not None and Path(saved).exists()
    Path(saved).unlink()

    frames = make_frames(Path(project.project_dir) / "stages" / card.id / "stabilize", 3)
    tab.frames_workspace.apply_frames(card.id, frames, "retouch")
    assert Path(saved).exists()                      # written again by the autosave path
    assert len(card.frames) == 3
    tab.shutdown()


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
