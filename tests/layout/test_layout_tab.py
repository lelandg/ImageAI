# tests/layout/test_layout_tab.py
from gui.layout.layout_tab import LayoutTab


class FakeConfig:
    def __init__(self):
        self.store = {"layout": {}}
    def get_layout_config(self):
        return dict(self.store["layout"])
    def set_layout_config(self, cfg):
        self.store["layout"] = cfg
    def save(self):
        pass


def test_new_document_creates_one_page(qapp):
    tab = LayoutTab(config=FakeConfig())
    tab.new_document()
    assert tab.document is not None
    assert len(tab.document.pages) == 1


def test_save_then_open_roundtrip(qapp, tmp_path):
    tab = LayoutTab(config=FakeConfig())
    tab.new_document()
    tab.document.title = "RoundTrip"
    p = tmp_path / "proj.iaiproj.json"
    tab.save_project_to(str(p))
    assert p.exists()

    tab2 = LayoutTab(config=FakeConfig())
    tab2.open_project_from(str(p))
    assert tab2.document.title == "RoundTrip"


def test_export_pdf(qapp, tmp_path):
    tab = LayoutTab(config=FakeConfig())
    tab.new_document()
    out = tmp_path / "out.pdf"
    tab.export_pdf_to(str(out))
    assert out.exists() and out.read_bytes()[:4] == b"%PDF"
