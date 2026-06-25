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
    def get_layout_llm_provider(self):
        return "google"


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


def test_open_dialog_reports_error_on_malformed_file(qapp, tmp_path, monkeypatch):
    # A malformed project file must not raise out of the Qt slot — it must be
    # logged and surfaced via a dialog (repo rule: all errors logged + shown).
    import gui.layout.layout_tab as lt
    bad = tmp_path / "bad.iaiproj.json"
    bad.write_text("{ this is not valid json", encoding="utf-8")
    monkeypatch.setattr(lt.QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (str(bad), "")))
    reported = {}
    monkeypatch.setattr(LayoutTab, "_report_error",
                        lambda self, what, exc: reported.update(what=what, exc=exc))
    tab = LayoutTab(config=FakeConfig())
    tab._open_dialog()  # must not raise
    assert reported.get("what") == "open project"
    assert isinstance(reported.get("exc"), Exception)
