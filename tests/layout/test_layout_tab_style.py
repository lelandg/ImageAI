# tests/layout/test_layout_tab_style.py
from gui.layout.layout_tab import LayoutTab


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def test_new_document_has_style(qapp):
    tab = LayoutTab(config=FakeConfig())
    assert tab.document.style is not None
    assert tab.document.style.font_roles  # non-empty role set


def test_apply_style_updates_document(qapp):
    from core.layout import styles
    tab = LayoutTab(config=FakeConfig())
    st = styles.default_style_for("comic")
    tab.apply_style(st)
    assert "dialogue" in tab.document.style.font_roles


def test_export_then_import_template_roundtrip(qapp, tmp_path):
    from core.layout import designer
    tab = LayoutTab(config=FakeConfig())
    tab.apply_designer_result(
        designer.DesignerResult(regions=[designer.Region(id="a", kind="text",
                                bbox=(0, 0, 100, 30), text="Hi", role="title")]),
        user_text="v1")
    p = tmp_path / "t.iailayout.json"
    tab.export_template_to(str(p))
    tab2 = LayoutTab(config=FakeConfig())
    tab2.import_template_from(str(p))
    regions = tab2.document.pages[0].regions
    assert [r.id for r in regions] == ["a"]
    assert regions[0].text == ""          # content stripped
    assert regions[0].role == "title"     # structure kept
    assert tab2.document.style is not None


def test_open_legacy_project_seeds_style(qapp, tmp_path):
    import json
    legacy = {"title": "Old", "pages": [{"page_size_px": [400, 400], "regions": []}]}
    p = tmp_path / "old.iaiproj.json"
    p.write_text(json.dumps(legacy), encoding="utf-8")
    tab = LayoutTab(config=FakeConfig())
    tab.open_project_from(str(p))
    assert tab.document.style is not None  # a default style is seeded for legacy projects
