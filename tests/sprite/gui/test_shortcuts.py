from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from gui.sprite.shortcuts import SHORTCUT_TABLE, install_shortcuts, resolve_target


class _FakeTab(QWidget):
    def __init__(self):
        super().__init__()
        self.calls = []
        record = lambda name: (lambda: self.calls.append(name))
        self.frame_strip = SimpleNamespace(delete_selected=record("delete"),
                                           duplicate_selected=record("duplicate"))
        self.preview_player = SimpleNamespace(toggle_play=record("play"), step_back=record("prev"),
                                              step_forward=record("next"), first=record("first"),
                                              last=record("last"), cycle_mode=record("mode"))
        self.pixel_view = SimpleNamespace(zoom_in=record("zoom_in"), zoom_out=record("zoom_out"),
                                          zoom_reset=record("zoom_reset"), toggle_grid=record("grid"))
        self.frames_workspace = SimpleNamespace(undo=record("undo"), redo=record("redo"))


EXPECTED_KEYS = {"Space", ",", ".", "Home", "End", "Delete", "Ctrl+D", "Ctrl+Z", "Ctrl+Y",
                 "Ctrl+Shift+Z", "+", "=", "-", "Ctrl+0", "G", "L"}


def test_table_covers_design_1_5():
    assert {row[0] for row in SHORTCUT_TABLE} == EXPECTED_KEYS


def test_install_creates_widget_scoped_shortcuts(qapp):
    tab = _FakeTab()
    shortcuts = install_shortcuts(tab)
    assert set(shortcuts) == EXPECTED_KEYS
    for shortcut in shortcuts.values():
        assert shortcut.context() == Qt.WidgetWithChildrenShortcut
        assert shortcut.parent() is tab
        assert shortcut.isEnabled()


def test_activation_routes_to_targets(qapp):
    tab = _FakeTab()
    shortcuts = install_shortcuts(tab)
    routing = {"Space": "play", ",": "prev", ".": "next", "Home": "first", "End": "last",
               "Delete": "delete", "Ctrl+D": "duplicate", "Ctrl+Z": "undo", "Ctrl+Y": "redo",
               "Ctrl+Shift+Z": "redo", "+": "zoom_in", "=": "zoom_in", "-": "zoom_out",
               "Ctrl+0": "zoom_reset", "G": "grid", "L": "mode"}
    for key, expected in routing.items():
        tab.calls.clear()
        shortcuts[key].activated.emit()
        assert tab.calls == [expected], key


def test_resolve_target_rejects_unknown_owner(qapp):
    tab = _FakeTab()
    assert resolve_target(tab, "view.zoom_in") is tab.pixel_view.zoom_in
    try:
        resolve_target(tab, "nowhere.zoom_in")
    except KeyError:
        pass
    else:
        raise AssertionError("unknown owner must raise KeyError")


def test_reinstall_replaces_previous_shortcuts(qapp):
    tab = _FakeTab()
    first = install_shortcuts(tab)
    second = install_shortcuts(tab)
    assert all(not s.isEnabled() for s in first.values())
    assert all(s.isEnabled() for s in second.values())
