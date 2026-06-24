# tests/layout/test_layout_tab_content.py
from core.layout import designer
from gui.layout.layout_tab import LayoutTab


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def _tab_with_regions():
    tab = LayoutTab(config=FakeConfig())
    tab.apply_designer_result(designer.DesignerResult(regions=[
        designer.Region(id="img", kind="image", bbox=(0, 0, 100, 100)),
        designer.Region(id="txt", kind="text", bbox=(0, 110, 100, 40), text="", role="title"),
    ]), user_text="page")
    return tab


def test_selecting_region_populates_inspector(qapp):
    tab = _tab_with_regions()
    tab._on_region_selected("img")
    assert tab.inspector.stack.currentIndex() == 1   # image editor
    tab._on_region_selected("txt")
    assert tab.inspector.stack.currentIndex() == 2   # text editor
    tab._on_region_selected("")                      # deselect
    assert tab.inspector.stack.currentIndex() == 0


def test_image_content_change_sets_image_ref(qapp):
    tab = _tab_with_regions()
    tab._on_region_content_changed("img", "/path/to/pic.png")
    assert tab.document.pages[0].regions[0].image_ref == "/path/to/pic.png"


def test_text_content_change_sets_text(qapp):
    tab = _tab_with_regions()
    tab._on_region_content_changed("txt", "Once upon a time")
    assert tab.document.pages[0].regions[1].text == "Once upon a time"


def test_set_region_content_unknown_id_is_noop(qapp):
    tab = _tab_with_regions()
    tab.set_region_content("nope", "x")  # must not raise
    assert tab.document.pages[0].regions[0].image_ref is None


def test_inspector_resets_on_new_document(qapp):
    tab = _tab_with_regions()
    tab._on_region_selected("img")
    assert tab.inspector.stack.currentIndex() == 1
    tab.new_document()
    assert tab.inspector.stack.currentIndex() == 0


def test_fill_image_and_text_then_export_pdf(qapp, tmp_path):
    # F-MVP acceptance: design a page, fill an image region (real file) and a
    # text region, then export a valid PDF — no AI content features needed.
    from PySide6.QtGui import QImage
    from PySide6.QtCore import Qt
    tab = _tab_with_regions()

    img_path = tmp_path / "pic.png"
    im = QImage(40, 40, QImage.Format_RGB32)
    im.fill(Qt.blue)
    assert im.save(str(img_path))

    tab.set_region_content("img", str(img_path))
    tab.set_region_content("txt", "The Title")

    page = tab.document.pages[0]
    assert page.regions[0].image_ref == str(img_path)
    assert page.regions[1].text == "The Title"

    out = tmp_path / "out.pdf"
    tab.export_pdf_to(str(out))
    assert out.exists() and out.read_bytes()[:4] == b"%PDF"
