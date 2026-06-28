from gui.layout.layout_tab import LayoutTab
from gui.layout.geometry_inspector import GeometryInspector
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


def test_inspector_emits_delete_and_toggles(qapp):
    insp = GeometryInspector()
    r = Region(id="p", kind="image", shape="polygon",
               points=[(0, 0), (10, 0), (10, 10)], bbox=(0, 0, 10, 10))
    insp.set_region(r)
    seen = []
    insp.deleteRequested.connect(lambda rid: seen.append(("del", rid)))
    insp.knifeToggled.connect(lambda rid, on: seen.append(("knife", rid, on)))
    insp.delete_btn.click()
    insp.knife_btn.setChecked(True)
    assert ("del", "p") in seen
    assert ("knife", "p", True) in seen


def test_knife_wiring_end_to_end(qapp):
    tab = _tab_with([Region(id="x", kind="image", shape="rect", bbox=(0, 0, 100, 100))])
    tab._on_region_knife_toggled("x", True)
    assert tab.canvas.tool_mode() == "knife"
    tab.canvas.knifeLine.emit(50.0, 0.0, 50.0, 100.0)
    assert [r.id for r in tab.document.pages[0].regions] == ["x_a", "x_b"]


def test_merge_wiring_end_to_end(qapp):
    tab = _tab_with([
        Region(id="L", kind="image", shape="rect", bbox=(0, 0, 50, 100)),
        Region(id="R", kind="image", shape="rect", bbox=(50, 0, 50, 100)),
    ])
    tab._on_region_merge_toggled("L", True)
    assert tab.canvas.tool_mode() == "merge"
    tab.canvas.mergeTarget.emit("R")
    assert [r.id for r in tab.document.pages[0].regions] == ["L"]


def test_op_completion_unchecks_tool_button(qapp):
    tab = _tab_with([Region(id="x", kind="image", shape="rect", bbox=(0, 0, 100, 100))])
    tab._on_region_knife_toggled("x", True)
    assert tab.geometry_inspector.knife_btn.isChecked() is True
    tab.canvas.knifeLine.emit(50.0, 0.0, 50.0, 100.0)
    assert tab.geometry_inspector.knife_btn.isChecked() is False
    assert tab.canvas.tool_mode() == "none"


def test_selection_change_disarms_tool(qapp):
    tab = _tab_with([
        Region(id="a", kind="image", shape="rect", bbox=(0, 0, 50, 50)),
        Region(id="b", kind="image", shape="rect", bbox=(50, 0, 50, 50)),
    ])
    tab._on_region_knife_toggled("a", True)
    assert tab.canvas.tool_mode() == "knife"
    tab._on_region_selected("b")
    assert tab.canvas.tool_mode() == "none"
    assert tab._knife_region_id is None
