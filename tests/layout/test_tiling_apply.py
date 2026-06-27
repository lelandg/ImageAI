from core.layout.models import PageSpec, Region
from core.layout.tiling import grid, three_tiers, diagonal_action, feature_L, apply_tiling, tile
from core.layout.geometry import validate_segments
from core.layout.schema import region_to_dict, region_from_dict


def test_grid_preset_counts():
    assert len(tile(grid(2, 3), (0, 0, 120, 90), gutter=6, margin=6)) == 6


def test_named_presets_build_and_tile():
    for tree in (three_tiers(), diagonal_action(), feature_L()):
        regions = tile(tree, (0, 0, 200, 300), gutter=8, margin=10)
        assert regions  # non-empty
        for r in regions:
            assert r.shape == "path"
            assert validate_segments(r.segments) == []  # every emitted region is a valid path


def test_emitted_regions_round_trip_through_schema():
    regions = tile(grid(2, 2), (0, 0, 100, 100), gutter=6, margin=6)
    for r in regions:
        r2 = region_from_dict(region_to_dict(r))
        assert r2.shape == "path"
        assert [s.type for s in r2.segments] == [s.type for s in r.segments]


def test_apply_tiling_seeds_regions_and_layers_floating():
    page = PageSpec(page_size_px=(100, 100))
    floating = (Region(id="float1", kind="image", bbox=(20, 20, 30, 30)),)
    out = apply_tiling(page, grid(2, 2), gutter=6, margin=6, floating=floating)
    ids = [r.id for r in out.regions]
    assert "float1" in ids
    base = [r for r in out.regions if r.id != "float1"]
    fl = [r for r in out.regions if r.id == "float1"][0]
    # floating is layered on top: its z exceeds every base panel's z
    assert fl.z > max(r.z for r in base)
