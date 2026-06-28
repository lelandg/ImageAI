from gui.layout.layout_tab import LayoutTab
from core.layout import designer
from core.layout.models import Overlay


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def test_apply_designer_result_writes_overlays(qapp):
    tab = LayoutTab(config=FakeConfig())
    res = designer.DesignerResult(
        regions=[designer.Region(id="p1", kind="image", bbox=(0, 0, 200, 200))],
        overlays=[Overlay(id="o1", kind="speech", text="Hi", anchor=(50.0, 40.0))],
    )
    tab.apply_designer_result(res, user_text="v1")
    page = tab.document.pages[0]
    assert [r.id for r in page.regions] == ["p1"]
    assert [o.id for o in page.overlays] == ["o1"]


def test_apply_designer_result_overlays_only(qapp):
    tab = LayoutTab(config=FakeConfig())
    res = designer.DesignerResult(
        regions=None,
        overlays=[Overlay(id="o1", kind="sfx", text="BOOM", anchor=(20.0, 20.0))],
    )
    tab.apply_designer_result(res, user_text="add sfx")
    assert [o.id for o in tab.document.pages[0].overlays] == ["o1"]
