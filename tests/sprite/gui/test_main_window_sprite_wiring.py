# tests/sprite/gui/test_main_window_sprite_wiring.py
"""MainWindow ↔ SpriteTab wiring: lazy placeholder swap and Send to Sprite (3 surfaces).

MainWindow is never constructed here (it scans history and builds every tab);
the methods run unbound against a SimpleNamespace stub, as
tests/gui/test_storage_settings.py does for close_data_handles.
"""
import inspect
import types
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget, QWidget

from core.video.project import ReferenceImage
from gui.video.reference_library_widget import ReferenceCard, ReferenceLibraryWidget


class _FakeSpriteTab(QWidget):
    addToHistoryRequested = Signal(dict)

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.sources = []

    def set_character_source(self, path):
        self.sources.append(Path(path))

    def shutdown(self):
        pass


class _Logger:
    def __init__(self):
        self.errors, self.infos = [], []

    def info(self, message, *a, **k):
        self.infos.append(message)

    def error(self, message, *a, **k):
        self.errors.append(message)

    debug = warning = info


def _stub(monkeypatch, tab_cls=_FakeSpriteTab):
    from gui.main_window import MainWindow

    monkeypatch.setattr("gui.sprite.SpriteTab", tab_cls)
    tabs = QTabWidget()
    placeholder = QWidget()
    tabs.addTab(QWidget(), "🎨 Image")
    tabs.addTab(placeholder, "🎮 Sprite")
    tabs.addTab(QWidget(), "⚙️ Settings")
    history = []

    def add_to_history(entry):  # plain function: signals connect to it cleanly
        history.append(entry)

    stub = types.SimpleNamespace(tabs=tabs, tab_sprite=placeholder, _sprite_tab_loaded=False,
                                 config=object(), logger=_Logger(),
                                 add_to_history=add_to_history, history_entries=history)
    stub._load_sprite_tab = lambda: MainWindow._load_sprite_tab(stub)
    stub._on_send_to_sprite = lambda path: MainWindow._on_send_to_sprite(stub, path)
    return MainWindow, stub


def test_init_ui_adds_sprite_placeholder_after_layout(qapp):
    from gui.main_window import MainWindow

    source = inspect.getsource(MainWindow._init_ui)
    assert "self._sprite_tab_loaded = False" in source
    assert source.index('"📖 Layout"') < source.index('"🎮 Sprite"') < source.index('"⚙️ Settings"')
    changed = inspect.getsource(MainWindow._on_tab_changed)
    assert "self.tab_sprite" in changed and "_load_sprite_tab" in changed
    close = inspect.getsource(MainWindow.closeEvent)
    assert "tab_sprite" in close and "shutdown" in close


def test_load_sprite_tab_swaps_placeholder_in_place(qapp, monkeypatch):
    MainWindow, stub = _stub(monkeypatch)
    MainWindow._load_sprite_tab(stub)
    assert stub._sprite_tab_loaded is True
    assert isinstance(stub.tab_sprite, _FakeSpriteTab)
    assert stub.tab_sprite.config is stub.config
    assert stub.tabs.count() == 3
    assert stub.tabs.widget(1) is stub.tab_sprite
    assert stub.tabs.tabText(1) == "🎮 Sprite"
    assert stub.tabs.currentIndex() == 1
    stub.tab_sprite.addToHistoryRequested.emit({"path": Path("p.png")})
    assert stub.history_entries == [{"path": Path("p.png")}]


def test_load_sprite_tab_is_idempotent(qapp, monkeypatch):
    MainWindow, stub = _stub(monkeypatch)
    MainWindow._load_sprite_tab(stub)
    first = stub.tab_sprite
    MainWindow._load_sprite_tab(stub)
    assert stub.tab_sprite is first and stub.tabs.count() == 3


def test_load_sprite_tab_failure_is_logged_and_shown(qapp, monkeypatch):
    class _Broken(QWidget):
        def __init__(self, config=None, parent=None):
            raise RuntimeError("sprite import exploded")

    import gui.main_window as mw
    warnings = []
    monkeypatch.setattr(mw.QMessageBox, "warning",
                        staticmethod(lambda parent, title, text: warnings.append((title, text))))
    MainWindow, stub = _stub(monkeypatch, tab_cls=_Broken)
    MainWindow._load_sprite_tab(stub)
    assert stub._sprite_tab_loaded is False
    assert stub.tabs.widget(1) is stub.tab_sprite  # placeholder kept
    assert any("sprite import exploded" in message for message in stub.logger.errors)
    assert warnings and "sprite import exploded" in warnings[0][1]


def test_send_to_sprite_loads_tab_and_routes_path(qapp, monkeypatch, png):
    MainWindow, stub = _stub(monkeypatch)
    MainWindow._on_send_to_sprite(stub, str(png))
    assert stub._sprite_tab_loaded is True
    assert stub.tabs.currentWidget() is stub.tab_sprite
    assert stub.tab_sprite.sources == [png]


def test_send_to_sprite_missing_file_is_reported_not_routed(qapp, monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr("gui.dialog_utils.show_error",
                        lambda parent, title, message, exception=None: seen.append(message))
    MainWindow, stub = _stub(monkeypatch)
    MainWindow._on_send_to_sprite(stub, tmp_path / "gone.png")
    assert seen and "gone.png" in seen[0]
    assert stub._sprite_tab_loaded is False


def test_send_to_sprite_menu_action_enabled_only_when_path_exists(qapp, monkeypatch, png, tmp_path):
    MainWindow, stub = _stub(monkeypatch)
    menu = MainWindow._build_send_to_sprite_menu(stub, png)
    actions = menu.actions()
    assert [a.text() for a in actions] == ["Send to Sprite"]
    assert actions[0].isEnabled()
    actions[0].trigger()
    assert stub.tab_sprite.sources == [png]
    disabled = MainWindow._build_send_to_sprite_menu(stub, tmp_path / "missing.png")
    assert not disabled.actions()[0].isEnabled()
    none_menu = MainWindow._build_send_to_sprite_menu(stub, None)
    assert not none_menu.actions()[0].isEnabled()


def test_reference_card_context_menu_sends_to_sprite(qapp, png):
    card = ReferenceCard(ReferenceImage(path=png))
    got = []
    card.send_to_sprite_clicked.connect(lambda p: got.append(p))
    menu = card._build_context_menu()
    texts = [action.text() for action in menu.actions()]
    assert texts == ["Edit Info", "Send to Sprite", "Remove"]
    menu.actions()[1].trigger()
    assert got == [png]


def test_reference_library_forwards_send_to_sprite(qapp, png):
    library = ReferenceLibraryWidget(None, None)
    got = []
    library.sendToSpriteRequested.connect(lambda p: got.append(p))
    card = ReferenceCard(ReferenceImage(path=png))
    library._connect_card(card)
    card.send_to_sprite_clicked.emit(png)
    assert got == [png]


def test_video_tab_declares_and_main_window_connects_the_signal(qapp):
    from gui.main_window import MainWindow
    from gui.video.video_project_tab import VideoProjectTab

    assert hasattr(VideoProjectTab, "sendToSpriteRequested")
    source = inspect.getsource(MainWindow._load_video_tab)
    assert "sendToSpriteRequested" in source and "_on_send_to_sprite" in source
