# tests/layout/test_content_inspector.py
from core.layout.models import Region
from gui.layout.content_inspector import ContentInspector


def _img(rid="i", ref=None):
    return Region(id=rid, kind="image", bbox=(0, 0, 10, 10), image_ref=ref)


def _txt(rid="t", text=""):
    return Region(id=rid, kind="text", bbox=(0, 0, 10, 10), text=text)


def test_set_region_switches_editor(qapp):
    insp = ContentInspector()
    insp.set_region(_img(ref="/p.png"))
    assert insp.stack.currentIndex() == 1
    assert "/p.png" in insp.image_ref_label.text()
    insp.set_region(_txt(text="hello"))
    assert insp.stack.currentIndex() == 2
    assert insp.text_edit.toPlainText() == "hello"
    insp.set_region(None)
    assert insp.stack.currentIndex() == 0


def test_import_image_emits(qapp, monkeypatch):
    from gui.layout import content_inspector as ci
    insp = ContentInspector()
    insp.set_region(_img(rid="i1"))
    monkeypatch.setattr(ci.QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: ("/tmp/x.png", "")))
    got = []
    insp.regionContentChanged.connect(lambda rid, v: got.append((rid, v)))
    insp.import_btn.click()
    assert got == [("i1", "/tmp/x.png")]


def test_import_cancelled_emits_nothing(qapp, monkeypatch):
    from gui.layout import content_inspector as ci
    insp = ContentInspector()
    insp.set_region(_img(rid="i1"))
    monkeypatch.setattr(ci.QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: ("", "")))
    got = []
    insp.regionContentChanged.connect(lambda rid, v: got.append((rid, v)))
    insp.import_btn.click()
    assert got == []


def test_from_history_emits(qapp, monkeypatch):
    import gui.layout.image_history_dialog as ihd

    class FakeDlg:
        def __init__(self, config, parent=None):
            pass

        def exec(self):
            return True

        def get_selected_image(self):
            return "/hist/a.png"

    monkeypatch.setattr(ihd, "ImageHistoryDialog", FakeDlg)
    insp = ContentInspector(config=object())
    insp.set_region(_img(rid="i2"))
    got = []
    insp.regionContentChanged.connect(lambda rid, v: got.append((rid, v)))
    insp.history_btn.click()
    assert got == [("i2", "/hist/a.png")]


def test_apply_text_emits(qapp):
    insp = ContentInspector()
    insp.set_region(_txt(rid="t1", text="old"))
    got = []
    insp.regionContentChanged.connect(lambda rid, v: got.append((rid, v)))
    insp.text_edit.setPlainText("new text")
    insp.apply_text_btn.click()
    assert got == [("t1", "new text")]


def test_text_page_has_font_controls(qapp):
    from PySide6.QtWidgets import QComboBox, QSpinBox
    insp = ContentInspector()
    assert isinstance(insp.font_combo, QComboBox) and insp.font_combo.isEditable()
    assert isinstance(insp.size_spin, QSpinBox)


def test_set_region_loads_text_style_into_controls(qapp):
    from core.layout.models import TextStyle
    insp = ContentInspector()
    insp.set_region(_txt(rid="t", text="hi"),
                    text_style=TextStyle(family=["Georgia"], size_px=72))
    assert insp.font_combo.currentText() == "Georgia"
    assert insp.size_spin.value() == 72


def test_apply_text_emits_font_style(qapp):
    insp = ContentInspector()
    insp.set_region(_txt(rid="t1", text="old"))
    styles = []
    insp.regionTextStyleChanged.connect(
        lambda rid, fam, size: styles.append((rid, fam, size)))
    insp.font_combo.setEditText("Comic Sans MS")
    insp.size_spin.setValue(96)
    insp.apply_text_btn.click()
    assert styles == [("t1", "Comic Sans MS", 96)]


def test_populate_fonts_fills_combo(qapp):
    insp = ContentInspector()
    insp._populate_fonts(["Alpha", "Beta", "Gamma"])
    items = [insp.font_combo.itemText(i) for i in range(insp.font_combo.count())]
    assert items == ["Alpha", "Beta", "Gamma"]


def test_image_page_loads_prompt(qapp):
    insp = ContentInspector()
    insp.set_region(_img(rid="i", ref="/p.png"))
    insp._region.prompt = "a castle"          # set then re-show
    insp.set_region(insp._region)
    assert insp.prompt_edit.toPlainText() == "a castle"


def test_apply_prompt_emits(qapp):
    insp = ContentInspector()
    insp.set_region(_img(rid="i1"))
    got = []
    insp.regionPromptChanged.connect(lambda rid, v: got.append((rid, v)))
    insp.prompt_edit.setPlainText("a glowing forest")
    insp.apply_prompt_btn.click()
    assert got == [("i1", "a glowing forest")]


def test_suggest_prompt_emits_with_hint(qapp):
    insp = ContentInspector()
    insp.set_region(_img(rid="i1"))
    got = []
    insp.regionPromptSuggestRequested.connect(lambda rid, hint: got.append((rid, hint)))
    insp.prompt_edit.setPlainText("dawn light")   # current text becomes the hint
    insp.suggest_prompt_btn.click()
    assert got == [("i1", "dawn light")]


def test_set_prompt_text_only_updates_current_region(qapp):
    insp = ContentInspector()
    insp.set_region(_img(rid="i1"))
    insp.set_prompt_text("other", "ignored")
    assert insp.prompt_edit.toPlainText() == ""
    insp.set_prompt_text("i1", "applied")
    assert insp.prompt_edit.toPlainText() == "applied"
