from core.layout.models import PageSpec, Region, Overlay
from core.layout.overlay_ops import (
    overlay_anchor_stranded, nearest_region_center, reposition_stranded_overlays,
)


def _regions():
    return [
        Region(id="a", kind="image", shape="rect", bbox=(0, 0, 100, 100)),
        Region(id="b", kind="image", shape="rect", bbox=(200, 0, 100, 100)),
    ]


def test_stranded_true_when_outside_all_bboxes():
    ov = Overlay(id="o", kind="sfx", text="x", anchor=(150.0, 50.0))  # in the gap
    assert overlay_anchor_stranded(ov, _regions()) is True


def test_stranded_false_when_inside_a_bbox():
    ov = Overlay(id="o", kind="sfx", text="x", anchor=(50.0, 50.0))  # inside region a
    assert overlay_anchor_stranded(ov, _regions()) is False


def test_nearest_region_center_picks_closest():
    assert nearest_region_center((150.0, 50.0), _regions()) == (250.0, 50.0)
    assert nearest_region_center((140.0, 50.0), _regions()) == (50.0, 50.0)


def test_nearest_region_center_none_when_no_regions():
    assert nearest_region_center((10.0, 10.0), []) is None


def test_reposition_moves_only_stranded():
    page = PageSpec(page_size_px=(400, 400), regions=_regions(), overlays=[
        Overlay(id="in", kind="sfx", text="x", anchor=(50.0, 50.0)),    # inside a
        Overlay(id="out", kind="sfx", text="y", anchor=(150.0, 50.0)),  # stranded -> nearest b
    ])
    moved = reposition_stranded_overlays(page)
    assert moved == 1
    by_id = {o.id: o.anchor for o in page.overlays}
    assert by_id["in"] == (50.0, 50.0)        # untouched
    assert by_id["out"] == (250.0, 50.0)      # moved to region b center


def test_reposition_noop_without_regions():
    page = PageSpec(page_size_px=(400, 400), regions=[], overlays=[
        Overlay(id="o", kind="sfx", text="x", anchor=(10.0, 10.0))])
    assert reposition_stranded_overlays(page) == 0
