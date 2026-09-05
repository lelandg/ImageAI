"""Exercise startup/tab activation without providers, history, or user sessions."""
import logging
import time

from PySide6.QtWidgets import QMainWindow, QWidget


def make_window(monkeypatch):
    from gui.main_window import MainWindow
    import gui.layout

    calls = []

    class Layout(QWidget):
        def __init__(self, config=None):
            super().__init__()
            calls.append("layout")

    monkeypatch.setattr(gui.layout, "LayoutTab", Layout)

    class Window(MainWindow):
        def __init__(self):
            QMainWindow.__init__(self)
            self.config = type("Config", (), {"get": lambda self, key, default=None: default})()
            self.logger = logging.getLogger(__name__)

        def _init_generate_tab(self):
            calls.append("image")

        def _init_settings_tab(self):
            calls.append("settings")

        def _init_history_tab(self):
            calls.append("history")

        def _init_help_tab(self):
            calls.append("help")

        def _init_templates_tab(self):
            calls.append("templates")

        def _trigger_help_render(self):
            pass

    return Window(), calls


def test_startup_defers_unopened_tabs(qapp, monkeypatch):
    window, calls = make_window(monkeypatch)
    started = time.perf_counter()
    window._init_ui()
    print(f"UI orchestration: {time.perf_counter() - started:.4f}s; constructors: {calls}")
    assert calls == ["image", "templates", "settings", "history"]
    window.tabs.setCurrentWidget(window.tab_help)
    window.tabs.setCurrentWidget(window.tab_generate)
    window.tabs.setCurrentWidget(window.tab_help)
    assert calls.count("help") == 1
    window.tabs.setCurrentWidget(window.tab_layout)
    assert calls.count("layout") == 1


def test_sprite_swap_does_not_activate_neighbor(qapp, monkeypatch):
    from PySide6.QtCore import Signal
    import gui.sprite

    class Sprite(QWidget):
        addToHistoryRequested = Signal(dict)

        def __init__(self, config=None):
            super().__init__()

    monkeypatch.setattr(gui.sprite, "SpriteTab", Sprite)
    window, calls = make_window(monkeypatch)
    window._init_ui()
    neighbors = []
    window._load_video_tab = lambda: neighbors.append("video")
    window.tabs.setCurrentWidget(window.tab_sprite)
    assert not neighbors
    assert window.tabs.currentWidget() is window.tab_sprite


def test_video_swap_does_not_load_layout(qapp, monkeypatch):
    import gui.main_window
    import gui.video.video_project_tab
    import core.llm_models

    class Video(QWidget):
        def __init__(self, config, providers):
            super().__init__()

    monkeypatch.setattr(gui.video.video_project_tab, "VideoProjectTab", Video)
    monkeypatch.setattr(gui.main_window, "list_providers", lambda: [])
    monkeypatch.setattr(core.llm_models, "update_ollama_models", lambda: False)
    window, calls = make_window(monkeypatch)
    window.current_provider = "google"
    window._init_ui()
    window.tabs.setCurrentWidget(window.tab_video)
    assert "layout" not in calls
    assert window._video_tab_loaded
    assert window.tabs.currentWidget() is window.tab_video


def test_help_failure_is_logged_and_can_retry(qapp, monkeypatch, caplog):
    import gui.main_window

    window, calls = make_window(monkeypatch)
    window._init_ui()
    original = window.tab_help
    shown = []
    monkeypatch.setattr(gui.main_window.QMessageBox, "warning", lambda *args: shown.append(args))
    def fail():
        raise RuntimeError("browser unavailable")
    window._init_help_tab = fail
    window.tabs.setCurrentWidget(window.tab_help)
    assert not window._help_tab_loaded
    assert window.tab_help is original
    assert shown and "Failed to load Help tab" in caplog.text
    window._init_help_tab = lambda: calls.append("help")
    window.tabs.setCurrentWidget(window.tab_generate)
    window.tabs.setCurrentWidget(window.tab_help)
    assert window._help_tab_loaded
    assert window.tabs.count() == 8
