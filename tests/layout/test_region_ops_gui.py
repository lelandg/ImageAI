from gui.layout.layout_tab import LayoutTab
from core.layout.models import Region


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def _tab_with(regions):
    tab = LayoutTab(config=FakeConfig())
    tab.document.pages[0].regions = regions
    tab._refresh()
    return tab


def test_apply_delete_removes_and_snapshots(qapp):
    tab = _tab_with([
        Region(id="a", kind="image", shape="rect", bbox=(0, 0, 50, 50)),
        Region(id="b", kind="image", shape="rect", bbox=(50, 0, 50, 50)),
    ])
    before = len(tab.history.snapshots())
    assert tab._apply_delete("a") is True
    assert [r.id for r in tab.document.pages[0].regions] == ["b"]
    assert len(tab.history.snapshots()) == before + 1


def test_apply_knife_splits_in_place(qapp):
    tab = _tab_with([Region(id="x", kind="image", shape="rect", bbox=(0, 0, 100, 100))])
    before = len(tab.history.snapshots())
    assert tab._apply_knife("x", (50.0, 0.0), (50.0, 100.0)) is True
    assert [r.id for r in tab.document.pages[0].regions] == ["x_a", "x_b"]
    assert len(tab.history.snapshots()) == before + 1


def test_apply_knife_miss_no_change(qapp):
    tab = _tab_with([Region(id="x", kind="image", shape="rect", bbox=(0, 0, 100, 100))])
    before = len(tab.history.snapshots())
    assert tab._apply_knife("x", (200.0, 0.0), (200.0, 100.0)) is False
    assert [r.id for r in tab.document.pages[0].regions] == ["x"]
    assert len(tab.history.snapshots()) == before


def test_apply_merge_combines(qapp):
    tab = _tab_with([
        Region(id="L", kind="image", shape="rect", bbox=(0, 0, 50, 100)),
        Region(id="R", kind="image", shape="rect", bbox=(50, 0, 50, 100)),
    ])
    before = len(tab.history.snapshots())
    assert tab._apply_merge("L", "R") is True
    assert [r.id for r in tab.document.pages[0].regions] == ["L"]
    assert tab.document.pages[0].regions[0].bbox == (0, 0, 100, 100)
    assert len(tab.history.snapshots()) == before + 1


def test_apply_merge_disjoint_no_change(qapp):
    tab = _tab_with([
        Region(id="L", kind="image", shape="rect", bbox=(0, 0, 50, 100)),
        Region(id="R", kind="image", shape="rect", bbox=(60, 0, 50, 100)),
    ])
    before = len(tab.history.snapshots())
    assert tab._apply_merge("L", "R") is False
    assert len(tab.document.pages[0].regions) == 2
    assert len(tab.history.snapshots()) == before
