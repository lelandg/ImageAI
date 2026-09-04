from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton, QTableWidget, QWidget

from gui.sprite.shortcuts import SHORTCUT_TABLE, install_shortcuts, resolve_target


class _Owner(QWidget):
    """A real child widget standing in for frame_strip / preview_player.

    A real QWidget (not a SimpleNamespace) so `install_shortcuts` can parent
    a QShortcut on it and QTest.keyClick focus scoping applies correctly.
    """

    def __init__(self, parent, **methods):
        super().__init__(parent)
        for name, fn in methods.items():
            setattr(self, name, fn)


class _FakeTab(QWidget):
    def __init__(self):
        super().__init__()
        self.calls = []
        record = lambda name: (lambda: self.calls.append(name))
        self.frame_strip = _Owner(self, delete_selected=record("delete"),
                                   duplicate_selected=record("duplicate"))
        self.preview_player = _Owner(self, toggle_play=record("play"), step_back=record("prev"),
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
    # design §1.5's "Where" column: strip rows on frame_strip, player + view
    # rows on preview_player (the view lives inside the player, deviation 2),
    # undo/redo tab-wide on the tab itself.
    expected_parent = {
        "Space": tab.preview_player, ",": tab.preview_player, ".": tab.preview_player,
        "Home": tab.preview_player, "End": tab.preview_player, "L": tab.preview_player,
        "Delete": tab.frame_strip, "Ctrl+D": tab.frame_strip,
        "Ctrl+Z": tab, "Ctrl+Y": tab, "Ctrl+Shift+Z": tab,
        "+": tab.preview_player, "=": tab.preview_player, "-": tab.preview_player,
        "Ctrl+0": tab.preview_player, "G": tab.preview_player,
    }
    assert set(expected_parent) == EXPECTED_KEYS
    for key, shortcut in shortcuts.items():
        assert shortcut.context() == Qt.WidgetWithChildrenShortcut
        assert shortcut.parent() is expected_parent[key], key
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


# ----- real focus/keyClick scoping probes (final review, Important 1) -----

def _activate(tab, widget):
    tab.show()
    tab.activateWindow()
    widget.setFocus(Qt.OtherFocusReason)
    for _ in range(3):
        QTest.qWait(10)


def test_focused_button_receives_space_not_toggle_play(qapp):
    """A button elsewhere in the tab keeps Space; the player shortcut stays out of scope."""
    tab = _FakeTab()
    install_shortcuts(tab)
    button = QPushButton("Run pipeline", tab)
    clicked = []
    button.clicked.connect(lambda: clicked.append(True))
    try:
        _activate(tab, button)
        assert button.hasFocus()
        QTest.keyClick(button, Qt.Key_Space)
        QTest.qWait(10)
        assert clicked == [True]
        assert "play" not in tab.calls
    finally:
        tab.hide()


def test_delete_on_table_outside_strip_does_not_delete(qapp):
    """Delete on a focused table that is NOT the strip must not touch the frame list."""
    tab = _FakeTab()
    install_shortcuts(tab)
    table = QTableWidget(2, 1, tab)  # e.g. the action-cards table, a sibling of frame_strip
    try:
        _activate(tab, table)
        assert table.hasFocus()
        QTest.keyClick(table, Qt.Key_Delete)
        QTest.qWait(10)
        assert "delete" not in tab.calls
    finally:
        tab.hide()


def test_delete_on_table_inside_strip_deletes(qapp):
    """Delete on a focused widget inside the strip still calls delete_selected."""
    tab = _FakeTab()
    install_shortcuts(tab)
    table = QTableWidget(2, 1, tab.frame_strip)  # a child of the strip owner widget
    try:
        _activate(tab, table)
        assert table.hasFocus()
        QTest.keyClick(table, Qt.Key_Delete)
        QTest.qWait(10)
        assert tab.calls == ["delete"]
    finally:
        tab.hide()
