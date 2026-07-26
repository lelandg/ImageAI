"""Construction + CRUD smoke tests (offscreen)."""
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
    def get_api_key(self, provider):
        return None


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def store(tmp_path):
    s = StyleStore(base_dir=tmp_path / "styles")
    s.save(Style(id="water", name="Water", prompt_text="washes",
                 description="soft"))
    return s


def _dialog(store):
    from gui.styles.style_manager_dialog import StyleManagerDialog
    return StyleManagerDialog(FakeConfig(), store=store)


def test_dialog_constructs_and_lists(qapp, store):
    dlg = _dialog(store)
    assert dlg.style_list.count() == 1
    assert dlg.style_list.item(0).text() == "Water"


def test_selecting_populates_fields(qapp, store):
    dlg = _dialog(store)
    dlg.style_list.setCurrentRow(0)
    assert dlg.name_edit.text() == "Water"
    assert dlg.prompt_text_edit.toPlainText() == "washes"
    assert dlg.placement_combo.currentText() == "suffix"


def test_save_writes_edits_back(qapp, store):
    dlg = _dialog(store)
    dlg.style_list.setCurrentRow(0)
    dlg.prompt_text_edit.setPlainText("new text")
    dlg.placement_combo.setCurrentText("prefix")
    dlg._save_current()
    s = store.get("water")
    assert s.prompt_text == "new text" and s.placement == "prefix"


def test_new_and_delete(qapp, store, monkeypatch):
    dlg = _dialog(store)
    monkeypatch.setattr(
        "gui.styles.style_manager_dialog.QInputDialog.getText",
        staticmethod(lambda *a, **k: ("Fresh", True)))
    dlg._on_new()
    assert store.get_by_name("Fresh") is not None
    assert dlg.style_list.count() == 2
    monkeypatch.setattr(
        "gui.styles.style_manager_dialog.show_question",
        lambda *a, **k: True)
    dlg.style_list.setCurrentRow([dlg.style_list.item(i).text()
                                  for i in range(dlg.style_list.count())].index("Fresh"))
    dlg._on_delete()
    assert store.get_by_name("Fresh") is None
