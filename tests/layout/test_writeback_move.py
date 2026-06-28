from PySide6.QtWidgets import QGraphicsItem

from core.layout.models import Region, PathSegment
from core.layout import qt_renderer


def _triangle():
    return [
        PathSegment(type="move", pts=[(10.0, 10.0)]),
        PathSegment(type="line", pts=[(50.0, 10.0)]),
        PathSegment(type="line", pts=[(50.0, 50.0)]),
        PathSegment(type="close", pts=[]),
    ]


def test_writeback_translates_path_segments(qapp):
    r = Region(id="p1", kind="image", shape="path", segments=_triangle(), bbox=(10, 10, 40, 40))
    item = qt_renderer._RegionPathItem(qt_renderer.region_to_painter_path(r), r)
    item.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
    item.setPos(5.0, -3.0)  # fires itemChange -> _writeback_move

    assert r.segments[0].pts == [(15.0, 7.0)]
    assert r.segments[1].pts == [(55.0, 7.0)]
    assert r.segments[2].pts == [(55.0, 47.0)]
    assert r.bbox == (15, 7, 40, 40)


def test_writeback_rect_region_unchanged_behavior(qapp):
    r = Region(id="t1", kind="text", shape="rect", bbox=(0, 0, 100, 40))
    from PySide6.QtCore import QRectF
    item = qt_renderer._RegionRectItem(QRectF(0, 0, 100, 40), r)
    item.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
    item.setPos(7.0, 9.0)
    assert r.bbox == (7, 9, 100, 40)  # translate-only, size unchanged
