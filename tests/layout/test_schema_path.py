from core.layout.models import Region, PathSegment
from core.layout.schema import (
    region_to_dict, region_from_dict, normalize_region, REGION_JSON_SCHEMA,
)


def _segs():
    return [
        PathSegment(type="move", pts=[(10.0, 10.0)]),
        PathSegment(type="line", pts=[(90.0, 10.0)]),
        PathSegment(type="line", pts=[(50.0, 80.0)]),
        PathSegment(type="close", pts=[]),
    ]


def test_path_region_round_trips():
    r = Region(id="p", kind="image", shape="path", segments=_segs(), bleed=True)
    r2 = region_from_dict(region_to_dict(r))
    assert r2.shape == "path"
    assert r2.bleed is True
    assert [s.type for s in r2.segments] == ["move", "line", "line", "close"]
    assert r2.segments[1].pts == [(90.0, 10.0)]


def test_schema_advertises_path_segments_bleed():
    assert "path" in REGION_JSON_SCHEMA["properties"]["shape"]["enum"]
    assert "segments" in REGION_JSON_SCHEMA["properties"]
    assert "bleed" in REGION_JSON_SCHEMA["properties"]


def test_normalize_region_derives_bbox_from_segments():
    r = Region(id="p", kind="image", shape="path", segments=_segs())
    n = normalize_region(r, (200, 200))
    # bbox = bounding box of points (10,10)-(90,80)
    assert n.bbox == (10, 10, 80, 70)
