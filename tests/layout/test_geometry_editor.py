from gui.layout.layout_tab import LayoutTab
from gui.layout.geometry_editor import edit_points_for_region
from core.layout.models import Region, PathSegment


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def _diamond_path():
    return Region(id="p1", kind="image", shape="path", bbox=(0, 0, 100, 100), segments=[
        PathSegment(type="move", pts=[(50.0, 0.0)]),
        PathSegment(type="line", pts=[(100.0, 50.0)]),
        PathSegment(type="cubic", pts=[(80.0, 80.0), (60.0, 100.0), (50.0, 100.0)]),
        PathSegment(type="close", pts=[]),
    ])


def test_edit_points_for_path_region():
    pts = edit_points_for_region(_diamond_path())
    # move(1 anchor) + line(1 anchor) + cubic(2 controls + 1 anchor) + close(0) = 5
    assert len(pts) == 5
    assert (pts[0].x, pts[0].y) == (50.0, 0.0)
    assert pts[2].is_control is True and pts[3].is_control is True
    assert pts[4].is_control is False and (pts[4].x, pts[4].y) == (50.0, 100.0)


def test_edit_points_for_polygon_region():
    r = Region(id="q1", kind="image", shape="polygon", points=[(0, 0), (40, 0), (40, 30)],
               bbox=(0, 0, 40, 30))
    pts = edit_points_for_region(r)
    assert len(pts) == 3
    assert all(not p.is_control for p in pts)
    assert (pts[1].x, pts[1].y) == (40.0, 0.0)


def test_edit_points_rect_region_empty():
    r = Region(id="t1", kind="text", shape="rect", bbox=(0, 0, 50, 20))
    assert edit_points_for_region(r) == []


def test_handles_appear_and_survive_refresh(qapp):
    tab = LayoutTab(config=FakeConfig())
    tab.document.pages[0].regions = [_diamond_path()]
    tab._refresh()
    tab.geometry_editor.set_edit_region("p1")
    assert len(tab.geometry_editor._handles) == 5
    tab._refresh()  # full scene rebuild
    assert len(tab.geometry_editor._handles) == 5  # regenerated, not lost


def test_edit_mode_off_clears_handles(qapp):
    tab = LayoutTab(config=FakeConfig())
    tab.document.pages[0].regions = [_diamond_path()]
    tab._refresh()
    tab.geometry_editor.set_edit_region("p1")
    tab.geometry_editor.set_edit_region(None)
    assert tab.geometry_editor._handles == []
