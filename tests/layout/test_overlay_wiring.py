from gui.layout.layout_tab import LayoutTab
from core.layout.models import Region, Overlay


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def _tab():
    tab = LayoutTab(config=FakeConfig())
    tab.document.pages[0].regions = []
    tab.document.pages[0].overlays = []
    tab._refresh()
    return tab


def test_add_overlay_appends_and_snapshots(qapp):
    tab = _tab()
    before = len(tab.history.snapshots())
    tab._add_overlay("speech")
    ovs = tab.document.pages[0].overlays
    assert len(ovs) == 1 and ovs[0].kind == "speech"
    assert len(tab.history.snapshots()) == before + 1


def test_delete_overlay_removes_and_snapshots(qapp):
    tab = _tab()
    tab._add_overlay("sfx")
    oid = tab.document.pages[0].overlays[0].id
    before = len(tab.history.snapshots())
    tab._delete_overlay(oid)
    assert tab.document.pages[0].overlays == []
    assert len(tab.history.snapshots()) == before + 1


def test_set_overlay_rotation_writes_model(qapp):
    tab = _tab()
    tab._add_overlay("sfx")
    oid = tab.document.pages[0].overlays[0].id
    tab._set_overlay_rotation(oid, 75)
    assert tab.document.pages[0].overlays[0].rotation == 75


def test_apply_designer_regions_only_repositions_overlays(qapp):
    tab = _tab()
    tab.document.pages[0].overlays = [
        Overlay(id="o", kind="sfx", text="x", anchor=(5.0, 5.0))]  # will be stranded

    class R:  # minimal designer result: regions only, no overlays
        regions = [Region(id="r", kind="image", shape="rect", bbox=(200, 200, 100, 100))]
        overlays = []
    tab.apply_designer_result(R())
    assert tab.document.pages[0].overlays[0].anchor == (250.0, 250.0)
