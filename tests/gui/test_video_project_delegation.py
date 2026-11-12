"""File > Save / Save As / Open delegate to the Video tab by widget, not index (#41).

The handlers used to compare the current index to 3 (the Layout tab) and look
up a nonexistent ``self.video_tab``, so on the Video tab nothing happened and
on the Layout tab the image-project dialogs were skipped.
"""
import logging

import pytest
from PySide6.QtWidgets import QMainWindow, QWidget


class _Workspace:
    def __init__(self, calls):
        self._calls = calls

    def save_project(self):
        self._calls.append("save")

    def save_project_as(self):
        self._calls.append("save_as")

    def open_project(self):
        self._calls.append("open")


class _FakeVideoTab(QWidget):
    def __init__(self, calls):
        super().__init__()
        self.workspace_widget = _Workspace(calls)


@pytest.fixture
def window(qapp, monkeypatch):
    """A MainWindow with real tabs, a loaded fake Video tab, and stub dialogs."""
    from gui.main_window import MainWindow
    import gui.layout
    import gui.main_window as main_window

    class Layout(QWidget):
        def __init__(self, config=None):
            super().__init__()

    monkeypatch.setattr(gui.layout, "LayoutTab", Layout)

    class Window(MainWindow):
        def __init__(self):
            QMainWindow.__init__(self)
            self.config = type("Config", (), {"get": lambda self, key, default=None: default})()
            self.logger = logging.getLogger(__name__)
            self.current_image_data = None

        def _init_generate_tab(self):
            pass

        def _init_settings_tab(self):
            pass

        def _init_history_tab(self):
            pass

        def _init_help_tab(self):
            pass

        def _init_templates_tab(self):
            pass

        def _trigger_help_render(self):
            pass

    win = Window()
    win._init_ui()

    # Swap the placeholder for a loaded Video tab, as _load_video_tab does.
    win.video_calls = []
    index = win.tabs.indexOf(win.tab_video)
    real = _FakeVideoTab(win.video_calls)
    win.tabs.blockSignals(True)
    win.tabs.removeTab(index)
    win.tabs.insertTab(index, real, "Video")
    win.tabs.blockSignals(False)
    win.tab_video = real
    win._video_tab_loaded = True

    win.image_calls = []
    monkeypatch.setattr(
        main_window.QMessageBox, "warning",
        lambda *a, **k: win.image_calls.append("no-image warning"),
    )
    monkeypatch.setattr(
        main_window.QFileDialog, "getOpenFileName",
        lambda *a, **k: (win.image_calls.append("open dialog"), ("", ""))[1],
    )
    return win


@pytest.mark.parametrize(
    "handler, expected",
    [("_save_project", "save"), ("_save_project_as", "save_as"), ("_open_project", "open")],
)
def test_video_tab_delegates_to_workspace(window, handler, expected):
    window.tabs.setCurrentWidget(window.tab_video)

    getattr(window, handler)()

    assert window.video_calls == [expected]
    assert window.image_calls == []


@pytest.mark.parametrize(
    "handler, expected",
    [
        ("_save_project", "no-image warning"),
        ("_save_project_as", "no-image warning"),
        ("_open_project", "open dialog"),
    ],
)
def test_layout_tab_at_old_index_3_is_not_treated_as_video(window, handler, expected):
    window.tabs.setCurrentWidget(window.tab_layout)
    assert window.tabs.currentIndex() == 3  # the index the old code hard-coded

    getattr(window, handler)()

    assert window.video_calls == []
    assert window.image_calls == [expected]


def test_delegation_follows_the_video_tab_when_it_moves(window):
    window.tabs.tabBar().moveTab(window.tabs.indexOf(window.tab_video), 0)
    window.tabs.setCurrentWidget(window.tab_video)

    window._save_project()

    assert window.video_calls == ["save"]
