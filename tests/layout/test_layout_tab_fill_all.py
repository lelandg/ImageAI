# tests/layout/test_layout_tab_fill_all.py — Phase 5b layout-complete mode
from core.layout import designer
from gui.layout.layout_tab import LayoutTab


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def _tab(regions):
    tab = LayoutTab(config=FakeConfig())
    tab.apply_designer_result(designer.DesignerResult(regions=regions), user_text="page")
    return tab


def test_collect_fill_payloads_only_prompted_image_regions(qapp):
    tab = _tab([
        designer.Region(id="i1", kind="image", bbox=(0, 0, 100, 200), prompt="a cat"),
        designer.Region(id="i2", kind="image", bbox=(0, 0, 50, 50), prompt=""),     # no prompt
        designer.Region(id="t1", kind="text", bbox=(0, 0, 50, 50), text="hi", prompt="x"),  # text
        designer.Region(id="i3", kind="image", bbox=(0, 0, 300, 100), prompt="a dog"),
    ])
    payloads = tab._collect_fill_payloads()
    assert [p["region_id"] for p in payloads] == ["i1", "i3"]   # ordered, prompted images only
    assert payloads[0] == {"region_id": "i1", "prompt": "a cat", "width": 100, "height": 200}


def test_fill_all_emits_payload_list(qapp):
    tab = _tab([
        designer.Region(id="i1", kind="image", bbox=(0, 0, 100, 100), prompt="a cat"),
        designer.Region(id="i2", kind="image", bbox=(0, 0, 100, 100), prompt="a dog"),
    ])
    got = []
    tab.fillAllRequested.connect(lambda payloads: got.append(payloads))
    tab._on_fill_all_clicked()
    assert len(got) == 1
    assert [p["region_id"] for p in got[0]] == ["i1", "i2"]


def test_fill_all_with_no_prompts_does_not_emit(qapp):
    tab = _tab([designer.Region(id="i1", kind="image", bbox=(0, 0, 100, 100), prompt="")])
    got = []
    tab.fillAllRequested.connect(lambda payloads: got.append(payloads))
    tab._on_fill_all_clicked()
    assert got == []
    assert "no image regions with prompts" in tab.status.text().lower()
