# tests/sprite/test_aseprite_native.py
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core.sprite.exporters.aseprite_native import (
    CHUNK_CEL, CHUNK_COLOR_PROFILE, CHUNK_LAYER, CHUNK_PALETTE, CHUNK_TAGS,
    FRAME_MAGIC, HEADER_MAGIC, export_aseprite, read_aseprite_summary,
)
from core.sprite.models import FrameMeta, SheetMeta, TagMeta


def _frame_png(path: Path, seed: int, size=(8, 8)) -> bytes:
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 256, size=(size[1], size[0], 4), dtype=np.uint8)
    Image.fromarray(arr).save(path)
    return arr.tobytes()


def _meta(tmp_path: Path, palette=None):
    frames, raw = [], []
    for i in range(3):
        p = tmp_path / f"{i + 1:04d}.png"
        raw.append(_frame_png(p, i))
        frames.append(FrameMeta(name=f"hero_{i}", source_path=p, frame=(0, 0, 8, 8),
                                sprite_source_size=(0, 0, 8, 8), source_size=(8, 8),
                                duration_ms=100 + 50 * i))
    tags = [TagMeta(name="walk", from_index=0, to_index=1, direction="pingpong"),
            TagMeta(name="idle", from_index=2, to_index=2, repeat=1)]
    return SheetMeta(title="hero", frames=frames, tags=tags, cell_size=(8, 8), palette=palette), raw


def test_header_fields(tmp_path):
    meta, _ = _meta(tmp_path)
    out = export_aseprite(meta, tmp_path / "hero.aseprite")
    s = read_aseprite_summary(out)
    assert s["magic"] == HEADER_MAGIC
    assert s["frames"] == 3 and s["width"] == 8 and s["height"] == 8 and s["depth"] == 32
    assert s["file_size"] == s["actual_size"]
    assert s["frame_magics"] == [FRAME_MAGIC] * 3
    assert (tmp_path / "hero.aseprite.json").exists()


def test_chunk_layout_first_frame_carries_metadata(tmp_path):
    meta, _ = _meta(tmp_path)
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    first = [ctype for ctype, _size in s["chunks"][0]]
    assert first == [CHUNK_COLOR_PROFILE, CHUNK_LAYER, CHUNK_TAGS, CHUNK_CEL]
    assert [[c for c, _ in frame] for frame in s["chunks"][1:]] == [[CHUNK_CEL], [CHUNK_CEL]]
    assert all(size >= 6 for frame in s["chunks"] for _c, size in frame)


def test_frame_sizes_sum_to_file_size(tmp_path):
    meta, _ = _meta(tmp_path)
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    assert 128 + sum(s["frame_sizes"]) == s["actual_size"]
    for frame_size, chunks in zip(s["frame_sizes"], s["chunks"]):
        assert frame_size == 16 + sum(size for _c, size in chunks)


def test_cel_pixels_round_trip(tmp_path):
    meta, raw = _meta(tmp_path)
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    assert [c["pixels"] for c in s["cels"]] == raw
    assert all(c["type"] == 2 and c["width"] == 8 and c["height"] == 8 and c["layer"] == 0 for c in s["cels"])


def test_durations_and_layer_name(tmp_path):
    meta, _ = _meta(tmp_path)
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    assert s["frame_durations"] == [100, 150, 200]
    assert s["layers"] == ["Sprite"]


def test_tags_directions_and_repeat(tmp_path):
    meta, _ = _meta(tmp_path)
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    assert s["tags"] == [
        {"name": "walk", "from": 0, "to": 1, "direction": 2, "repeat": 0},
        {"name": "idle", "from": 2, "to": 2, "direction": 0, "repeat": 1},
    ]


def test_palette_chunk_when_quantized(tmp_path):
    meta, _ = _meta(tmp_path, palette=["#FF0000", "#00FF00", "#0000FF"])
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    first = [ctype for ctype, _ in s["chunks"][0]]
    assert first == [CHUNK_COLOR_PROFILE, CHUNK_PALETTE, CHUNK_LAYER, CHUNK_TAGS, CHUNK_CEL]
    assert s["palette"] == ["#FF0000", "#00FF00", "#0000FF"]
    assert s["ncolors"] == 3


def test_no_palette_chunk_without_palette(tmp_path):
    meta, _ = _meta(tmp_path)
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    assert CHUNK_PALETTE not in [c for c, _ in s["chunks"][0]]
    assert s["ncolors"] == 0


def test_oversized_frame_is_fit_proportionally(tmp_path):
    meta, _ = _meta(tmp_path)
    wide = tmp_path / "wide.png"
    _frame_png(wide, 9, size=(16, 8))
    meta.frames[1].source_path = wide
    s = read_aseprite_summary(export_aseprite(meta, tmp_path / "hero.aseprite"))
    cel = s["cels"][1]
    assert (cel["width"], cel["height"]) == (8, 4)
    assert (cel["x"], cel["y"]) == (0, 2)


def test_requires_frames(tmp_path):
    with pytest.raises(ValueError):
        export_aseprite(SheetMeta(title="x", frames=[], tags=[]), tmp_path / "x.aseprite")
