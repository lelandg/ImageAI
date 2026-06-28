from core.layout.models import Region, PathSegment
from core.layout.region_ops import region_to_polygon


def test_region_to_polygon_rect():
    r = Region(id="r", kind="image", shape="rect", bbox=(10, 20, 100, 40))
    assert region_to_polygon(r) == [
        (10.0, 20.0), (110.0, 20.0), (110.0, 60.0), (10.0, 60.0)]


def test_region_to_polygon_polygon():
    r = Region(id="p", kind="image", shape="polygon",
               points=[(0, 0), (40, 0), (40, 30)], bbox=(0, 0, 40, 30))
    assert region_to_polygon(r) == [(0.0, 0.0), (40.0, 0.0), (40.0, 30.0)]


def test_region_to_polygon_straight_path():
    r = Region(id="q", kind="image", shape="path", bbox=(0, 0, 50, 50), segments=[
        PathSegment(type="move", pts=[(0.0, 0.0)]),
        PathSegment(type="line", pts=[(50.0, 0.0)]),
        PathSegment(type="line", pts=[(50.0, 50.0)]),
        PathSegment(type="close", pts=[]),
    ])
    assert region_to_polygon(r) == [(0.0, 0.0), (50.0, 0.0), (50.0, 50.0)]


def test_region_to_polygon_curved_path_none():
    r = Region(id="c", kind="image", shape="path", bbox=(0, 0, 50, 50), segments=[
        PathSegment(type="move", pts=[(0.0, 0.0)]),
        PathSegment(type="cubic", pts=[(10.0, 10.0), (20.0, 20.0), (50.0, 50.0)]),
        PathSegment(type="close", pts=[]),
    ])
    assert region_to_polygon(r) is None


def test_region_to_polygon_degenerate_polygon_none():
    r = Region(id="d", kind="image", shape="polygon", points=[(0, 0), (1, 1)], bbox=(0, 0, 1, 1))
    assert region_to_polygon(r) is None


from core.layout.region_ops import split_region


def _square(id="s"):
    return Region(id=id, kind="image", shape="rect", bbox=(0, 0, 100, 100),
                  bleed=True, z=5)


def test_split_square_vertical_midline():
    out = split_region(_square(), (50.0, 0.0), (50.0, 100.0))
    assert out is not None
    a, b = out
    assert a.shape == "polygon" and b.shape == "polygon"
    assert a.id == "s_a" and b.id == "s_b"
    assert a.bleed is True and a.z == 5  # identity/style copied
    xranges = sorted([
        (min(p[0] for p in a.points), max(p[0] for p in a.points)),
        (min(p[0] for p in b.points), max(p[0] for p in b.points)),
    ])
    assert xranges == [(0, 50), (50, 100)]


def test_split_miss_returns_none():
    # vertical line entirely to the right of the square -> one side empty
    assert split_region(_square(), (200.0, 0.0), (200.0, 100.0)) is None


def test_split_curved_path_none():
    r = Region(id="c", kind="image", shape="path", bbox=(0, 0, 50, 50), segments=[
        PathSegment(type="move", pts=[(0.0, 0.0)]),
        PathSegment(type="quad", pts=[(25.0, 25.0), (50.0, 0.0)]),
        PathSegment(type="close", pts=[]),
    ])
    assert split_region(r, (10.0, 0.0), (10.0, 50.0)) is None
