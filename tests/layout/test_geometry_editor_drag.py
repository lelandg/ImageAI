from gui.layout.layout_tab import LayoutTab
from core.layout.models import Region, PathSegment


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def _tri():
    return Region(id="p1", kind="image", shape="path", bbox=(10, 10, 40, 40), segments=[
        PathSegment(type="move", pts=[(10.0, 10.0)]),
        PathSegment(type="line", pts=[(50.0, 10.0)]),
        PathSegment(type="line", pts=[(50.0, 50.0)]),
        PathSegment(type="close", pts=[]),
    ])


def _editing_tab():
    tab = LayoutTab(config=FakeConfig())
    tab.document.pages[0].regions = [_tri()]
    tab._refresh()
    tab.geometry_editor.set_edit_region("p1")
    return tab


def test_move_handle_mutates_segment_point(qapp):
    tab = _editing_tab()
    tab.geometry_editor.begin_edit()
    tab.geometry_editor.move_handle(0, 20.0, 5.0)  # drag the 'move' anchor
    seg0 = tab.document.pages[0].regions[0].segments[0]
    assert seg0.pts == [(20.0, 5.0)]


def test_commit_recomputes_bbox_and_snapshots(qapp):
    tab = _editing_tab()
    before = len(tab.history.snapshots())
    tab.geometry_editor.begin_edit()
    tab.geometry_editor.move_handle(2, 90.0, 90.0)  # move the 2nd line endpoint out
    tab.geometry_editor.commit()
    r = tab.document.pages[0].regions[0]
    assert r.segments[2].pts == [(90.0, 90.0)]
    assert r.bbox == (10, 10, 80, 80)  # segments_bbox over (10,10),(50,10),(90,90)
    assert len(tab.history.snapshots()) == before + 1


def test_begin_edit_suspends_refresh_commit_resumes(qapp):
    tab = _editing_tab()
    tab.geometry_editor.begin_edit()
    assert tab._suspend_refresh is True
    tab.geometry_editor.commit()
    assert tab._suspend_refresh is False


def test_polygon_vertex_edit_commits(qapp):
    tab = LayoutTab(config=FakeConfig())
    tab.document.pages[0].regions = [Region(id="q1", kind="image", shape="polygon",
                                            points=[(0, 0), (40, 0), (40, 30)], bbox=(0, 0, 40, 30))]
    tab._refresh()
    tab.geometry_editor.set_edit_region("q1")
    tab.geometry_editor.begin_edit()
    tab.geometry_editor.move_handle(2, 60.0, 50.0)
    tab.geometry_editor.commit()
    r = tab.document.pages[0].regions[0]
    assert r.points[2] == (60, 50)
    assert r.bbox == (0, 0, 60, 50)
