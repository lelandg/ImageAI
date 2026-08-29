import json
from pathlib import Path

import pytest
from PIL import Image

from core.sprite.exporters import GridOptions, aseprite_document, export_aseprite_json, export_grid
from core.sprite.exporters.grid import next_power_of_two
from core.sprite.models import FrameMeta, SheetMeta, TagMeta
from tests.sprite.synth import draw_frame

GOLDEN = Path(__file__).parent / "golden"


def _meta(tmp_path, cell=16, walk=3, idle=2):
    """Deterministic sheet: walk (3 frames) + idle (2 frames), 16x16 cells."""
    frames = []
    for index in range(walk + idle):
        path = tmp_path / "src" / f"{index + 1:04d}.png"
        path.parent.mkdir(exist_ok=True)
        draw_frame(index, alpha=True, size=(cell, cell), square=6, step=1).save(path)
        tag = "walk" if index < walk else "idle"
        local = index if index < walk else index - walk
        frames.append(FrameMeta(name=f"hero_{tag}_{local:02d}", source_path=path, frame=(0, 0, cell, cell),
                                sprite_source_size=(0, 0, cell, cell), source_size=(cell, cell),
                                duration_ms=83 if tag == "walk" else 200))
    tags = [TagMeta(name="walk", from_index=0, to_index=walk - 1, direction="forward", fps_hint=12),
            TagMeta(name="idle", from_index=walk, to_index=walk + idle - 1, direction="pingpong", repeat=2)]
    return SheetMeta(title="hero", frames=frames, tags=tags, cell_size=(cell, cell))


def _normalized(document):
    document = json.loads(json.dumps(document))
    document["meta"]["version"] = "TEST"
    return document


# --- grid -------------------------------------------------------------------

def test_export_grid_one_row_per_tag_fills_rects_and_writes_sidecars(tmp_path):
    meta = _meta(tmp_path)
    out = tmp_path / "exports" / "hero.png"
    filled = export_grid(meta, out, GridOptions(shape_px=0))
    assert filled.sheet_size == (48, 32)
    assert [f.frame for f in filled.frames] == [(0, 0, 16, 16), (16, 0, 16, 16), (32, 0, 16, 16),
                                                (0, 16, 16, 16), (16, 16, 16, 16)]
    assert filled.frames[0].source_size == (16, 16)
    assert meta.frames[0].frame == (0, 0, 16, 16)  # input meta untouched
    with Image.open(out) as im:
        assert im.size == (48, 32)
        assert im.getpixel((12, 8)) == (200, 40, 40, 255)
    assert (tmp_path / "exports" / "hero.json").exists()  # Aseprite sidecar, always
    assert (tmp_path / "exports" / "hero.png.json").exists()  # ImageAI metadata sidecar
    aseprite = json.loads((tmp_path / "exports" / "hero.json").read_text())
    assert aseprite["meta"]["image"] == "hero.png"
    assert aseprite["frames"]["hero_idle_01"]["frame"] == {"x": 16, "y": 16, "w": 16, "h": 16}


def test_export_grid_padding_knobs_and_fixed_columns(tmp_path):
    meta = _meta(tmp_path)
    opts = GridOptions(columns=2, border_px=2, shape_px=3, inner_px=1)
    filled = export_grid(meta, tmp_path / "s.png", opts)
    # cell = 18x18, 2 cols x 3 rows: w = 4 + 36 + 3 = 43; h = 4 + 54 + 6 = 64
    assert filled.sheet_size == (43, 64)
    assert filled.cell_size == (18, 18)
    assert filled.frames[0].frame == (3, 3, 16, 16)
    assert filled.frames[1].frame == (3 + 18 + 3, 3, 16, 16)
    assert filled.frames[2].frame == (3, 3 + 18 + 3, 16, 16)


def test_export_grid_extrude_repeats_edge_pixels(tmp_path):
    meta = _meta(tmp_path)
    # Make frame 0 fully opaque red so the extruded border is visible.
    Image.new("RGBA", (16, 16), (200, 40, 40, 255)).save(meta.frames[0].source_path)
    filled = export_grid(meta, tmp_path / "s.png", GridOptions(border_px=2, shape_px=4, extrude_px=2))
    x, y, w, h = filled.frames[0].frame
    with Image.open(tmp_path / "s.png") as im:
        assert im.getpixel((x - 1, y)) == (200, 40, 40, 255)
        assert im.getpixel((x - 2, y - 2)) == (200, 40, 40, 255)
        assert im.getpixel((x + w, y + h)) == (200, 40, 40, 255)
    with pytest.raises(ValueError):
        export_grid(meta, tmp_path / "t.png", GridOptions(shape_px=3, border_px=2, extrude_px=2))
    with pytest.raises(ValueError):
        export_grid(meta, tmp_path / "t.png", GridOptions(shape_px=4, border_px=1, extrude_px=2))


def test_export_grid_power_of_two_and_scaled_copies(tmp_path):
    meta = _meta(tmp_path)
    out = tmp_path / "hero.png"
    filled = export_grid(meta, out, GridOptions(shape_px=0, power_of_two=True, scales=(1, 2, 4)))
    assert filled.sheet_size == (64, 32)
    for scale in (2, 4):
        copy = tmp_path / f"hero@{scale}x.png"
        with Image.open(copy) as im:
            assert im.size == (64 * scale, 32 * scale)
            assert im.getpixel((12 * scale, 8 * scale)) == (200, 40, 40, 255)
        data = json.loads(copy.with_suffix(".json").read_text())
        assert data["meta"]["scale"] == str(scale)
        assert data["frames"]["hero_walk_01"]["frame"]["x"] == 16 * scale
        assert copy.with_name(copy.name + ".json").exists()
    assert next_power_of_two(48) == 64 and next_power_of_two(64) == 64 and next_power_of_two(1) == 1
    with pytest.raises(ValueError):
        export_grid(meta, tmp_path / "x.png", GridOptions(scales=(2,)))


def test_export_grid_requires_frames_and_files(tmp_path):
    with pytest.raises(ValueError):
        export_grid(SheetMeta(title="e", frames=[], tags=[]), tmp_path / "e.png", GridOptions())
    meta = _meta(tmp_path)
    meta.frames[0].source_path = tmp_path / "missing.png"
    with pytest.raises(FileNotFoundError):
        export_grid(meta, tmp_path / "m.png", GridOptions())


# --- aseprite ----------------------------------------------------------------

def test_aseprite_hash_matches_golden(tmp_path):
    filled = export_grid(_meta(tmp_path), tmp_path / "hero.png", GridOptions(shape_px=0))
    document = aseprite_document(filled, image_name="hero.png", layout="hash")
    assert _normalized(document) == json.loads((GOLDEN / "aseprite_hash.json").read_text())


def test_aseprite_array_matches_golden(tmp_path):
    filled = export_grid(_meta(tmp_path), tmp_path / "hero.png", GridOptions(shape_px=0))
    out = tmp_path / "hero_array.json"
    export_aseprite_json(filled, out, image_name="hero.png", layout="array")
    assert _normalized(json.loads(out.read_text())) == json.loads((GOLDEN / "aseprite_array.json").read_text())


def test_aseprite_rejects_unknown_layout(tmp_path):
    with pytest.raises(ValueError):
        aseprite_document(_meta(tmp_path), image_name="x.png", layout="tree")


# --- texturepacker --------------------------------------------------------------
from core.sprite.exporters.texturepacker_json import (  # noqa: E402 - grouped with the tests it serves
    export_texturepacker_json,
    texturepacker_document,
)


def test_texturepacker_hash_matches_golden(tmp_path):
    filled = export_grid(_meta(tmp_path), tmp_path / "hero.png", GridOptions(shape_px=0))
    out = tmp_path / "hero_tp.json"
    export_texturepacker_json(filled, out, image_name="hero.png", layout="hash")
    assert _normalized(json.loads(out.read_text())) == json.loads((GOLDEN / "texturepacker_hash.json").read_text())


def test_texturepacker_array_has_filenames_and_animations(tmp_path):
    filled = export_grid(_meta(tmp_path), tmp_path / "hero.png", GridOptions(shape_px=0))
    document = texturepacker_document(filled, image_name="hero.png", layout="array")
    assert document["frames"][0]["filename"] == "hero_walk_00.png"
    assert document["frames"][0]["pivot"] == {"x": 0.5, "y": 1.0}
    assert document["animations"] == {"walk": ["hero_walk_00.png", "hero_walk_01.png", "hero_walk_02.png"],
                                      "idle": ["hero_idle_00.png", "hero_idle_01.png"]}


# --- png sequence ---------------------------------------------------------------
from core.sprite.exporters.png_sequence import (  # noqa: E402 - grouped with the tests it serves
    export_png_sequence,
    export_single_frame,
    render_frame_name,
)


def test_render_frame_name_fields():
    assert render_frame_name("{title}_{tag}_{frame01}.png", title="hero", tag="walk", frame=4, tagframe=1) == "hero_walk_02.png"
    assert render_frame_name("{tag}-{tagframe}-{frame}.png", title="h", tag="idle", frame=4, tagframe=1) == "idle-1-4.png"
    assert render_frame_name("{title}/{tag}.png", title="a b", tag="x", frame=0, tagframe=0) == "a_b_x.png"


def test_export_png_sequence_writes_per_tag_files_with_sidecars(tmp_path):
    meta = _meta(tmp_path)
    out = export_png_sequence(meta, tmp_path / "seq")
    names = [p.name for p in out]
    assert names == ["hero_walk_01.png", "hero_walk_02.png", "hero_walk_03.png", "hero_idle_01.png", "hero_idle_02.png"]
    for path in out:
        assert path.with_name(path.name + ".json").exists()
    sidecar = json.loads((tmp_path / "seq" / "hero_idle_01.png.json").read_text())
    assert sidecar["tag"] == "idle" and sidecar["index"] == 3 and sidecar["duration_ms"] == 200


def test_export_png_sequence_puts_untagged_frames_last(tmp_path):
    meta = _meta(tmp_path)
    meta.tags = meta.tags[:1]
    out = export_png_sequence(meta, tmp_path / "seq", template="{tag}_{frame01}.png")
    assert [p.name for p in out][-2:] == ["untagged_01.png", "untagged_02.png"]


def test_export_single_frame(tmp_path):
    meta = _meta(tmp_path)
    out = export_single_frame(meta.frames[4], tmp_path / "one" / "frame.png")
    assert out.exists() and out.with_name("frame.png.json").exists()
    with Image.open(out) as im:
        assert im.size == (16, 16) and im.mode == "RGBA"
