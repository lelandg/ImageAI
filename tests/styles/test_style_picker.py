"""Headless smoke tests for StylePickerWidget (QT_QPA_PLATFORM=offscreen)."""
import pytest

pytest.importorskip("PySide6")

from core.styles.models import Style
from core.styles.store import StyleStore


class FakeConfig(dict):
    def get(self, k, d=None):
        return dict.get(self, k, d)
    def set(self, k, v):
        self[k] = v
    def save(self):
        pass


@pytest.fixture
def store(tmp_path):
    s = StyleStore(base_dir=tmp_path / "styles")
    s.save(Style(id="water", name="Water", prompt_text="washes"))
    s.save(Style(id="neon", name="Neon", prompt_text="glow"))
    return s


def _picker(qapp, store, config=None, **kw):
    from gui.styles.style_picker import StylePickerWidget
    if config is None:
        config = FakeConfig()
    w = StylePickerWidget(config, "image", **kw)
    w.set_store(store)
    w.refresh()
    return w


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_picker_lists_styles_with_none_first(qapp, store):
    w = _picker(qapp, store)
    labels = [w.combo.itemText(i) for i in range(w.combo.count())]
    assert labels[0] == "None"
    assert "Water" in labels and "Neon" in labels
    assert w.current_style() is None


def test_selection_returns_style_and_persists(qapp, store):
    cfg = FakeConfig()
    w = _picker(qapp, store, config=cfg)
    w.combo.setCurrentText("Water")
    assert w.current_style().id == "water"
    assert cfg["style_selected_image"] == "water"
    # a new picker restores the selection
    w2 = _picker(qapp, store, config=cfg)
    assert w2.current_style().id == "water"


def test_smart_checkbox_persists(qapp, store):
    cfg = FakeConfig()
    w = _picker(qapp, store, config=cfg)
    w.smart_check.setChecked(True)
    assert w.smart_merge_enabled() is True
    assert cfg["style_smart_image"] is True


def test_hide_smart(qapp, store):
    w = _picker(qapp, store, show_smart=False)
    assert w.smart_check is None
    assert w.smart_merge_enabled() is False


def test_refresh_keeps_selection_when_possible(qapp, store):
    w = _picker(qapp, store)
    w.combo.setCurrentText("Neon")
    store.save(Style(id="extra", name="Extra"))
    w.refresh()
    assert w.current_style().id == "neon"


def test_manager_close_refreshes_all_pickers(qapp, store, monkeypatch):
    """Closing the Style Manager refreshes EVERY surface's picker, not just
    the one that opened it (issue #37)."""
    from gui.styles.style_picker import StylePickerWidget
    a = _picker(qapp, store)
    b = StylePickerWidget(FakeConfig(), "video")
    b.set_store(store)
    b.refresh()

    class FakeDlg:
        def __init__(self, config, store=None, parent=None):
            self._s = store

        def exec(self):
            self._s.save(Style(id="fresh", name="Fresh"))

    monkeypatch.setattr(
        "gui.styles.style_manager_dialog.StyleManagerDialog", FakeDlg)
    a._open_manager()
    assert a.combo.findData("fresh") >= 0
    assert b.combo.findData("fresh") >= 0   # the OTHER picker refreshed too
