# tests/layout/test_layout_tab_bundle.py — Phase 5a .iaibundle wiring
from pathlib import Path

from core.layout import designer
from gui.layout.layout_tab import LayoutTab


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def _tab_with_image(image_ref):
    tab = LayoutTab(config=FakeConfig())
    tab.apply_designer_result(designer.DesignerResult(regions=[
        designer.Region(id="img", kind="image", bbox=(0, 0, 100, 100), image_ref=image_ref),
    ]), user_text="page")
    return tab


def test_export_then_import_bundle_round_trip(qapp, tmp_path):
    img = tmp_path / "pic.png"; img.write_bytes(b"IMG")
    tab = _tab_with_image(str(img))
    out = tmp_path / "b.iaibundle"
    tab.export_bundle_to(str(out))
    assert out.exists()
    assert "Exported bundle" in tab.status.text()

    # a fresh tab opens the bundle with no access to the original file
    tab2 = LayoutTab(config=FakeConfig())
    tab2.import_bundle_from(str(out))
    r = tab2.document.pages[0].regions[0]
    assert Path(r.image_ref).is_absolute() and Path(r.image_ref).exists()
    assert Path(r.image_ref).read_bytes() == b"IMG"


def test_export_bundle_missing_image_reports_warning(qapp, tmp_path):
    tab = _tab_with_image("/no/such/file.png")
    out = tmp_path / "b.iaibundle"
    tab.export_bundle_to(str(out))           # must not raise
    assert out.exists()
    assert "warning" in tab.status.text().lower()
