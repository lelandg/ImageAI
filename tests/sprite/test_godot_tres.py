# tests/sprite/test_godot_tres.py
from pathlib import Path

import pytest

from core.sprite.exporters.godot_tres import (
    export_godot_tres, ordered_frame_indices, render_godot_tres,
)
from core.sprite.models import FrameMeta, SheetMeta, TagMeta

GOLDEN = Path(__file__).parent / "golden" / "godot.tres"


def _meta() -> SheetMeta:
    frames = [
        FrameMeta(name="hero_walk_01", source_path=None, frame=(0, 0, 16, 16),
                  sprite_source_size=(0, 0, 16, 16), source_size=(16, 16), duration_ms=100),
        FrameMeta(name="hero_walk_02", source_path=None, frame=(16, 0, 12, 14), trimmed=True,
                  sprite_source_size=(2, 1, 12, 14), source_size=(16, 16), duration_ms=100),
        FrameMeta(name="hero_idle_01", source_path=None, frame=(0, 16, 16, 16),
                  sprite_source_size=(0, 0, 16, 16), source_size=(16, 16), duration_ms=200),
    ]
    tags = [
        TagMeta(name="walk", from_index=0, to_index=1),
        TagMeta(name="idle", from_index=2, to_index=2, repeat=1),
    ]
    return SheetMeta(title="hero", frames=frames, tags=tags, sheet_size=(32, 32), cell_size=(16, 16))


def _lines(text: str) -> list:
    """Line list tolerant of end-of-line trailing whitespace and a trailing EOF newline.

    Godot's text-resource parser is line-oriented: every ``[section]`` header
    and every ``key = value`` must start its own line. Comparing line by line
    (instead of collapsing all whitespace) catches a regression that keeps
    every token in order but drops the line breaks Godot needs to parse it.
    """
    return [line.rstrip() for line in text.splitlines()]


def test_export_matches_golden_line_by_line(tmp_path):
    out = export_godot_tres(_meta(), tmp_path / "hero.tres", atlas_res_path="res://hero.png")
    assert out.exists()
    assert _lines(out.read_text(encoding="utf-8")) == _lines(GOLDEN.read_text(encoding="utf-8"))


def test_export_writes_json_sidecar(tmp_path):
    out = export_godot_tres(_meta(), tmp_path / "hero.tres", atlas_res_path="res://hero.png")
    sidecar = tmp_path / "hero.tres.json"
    assert sidecar.exists()
    assert '"godot_tres"' in sidecar.read_text(encoding="utf-8")


def test_load_steps_is_ext_plus_subs_plus_resource():
    text = render_godot_tres(_meta(), atlas_res_path="res://hero.png")
    assert "load_steps=5" in text.splitlines()[0]


def test_margin_only_on_trimmed_frames():
    text = render_godot_tres(_meta(), atlas_res_path="res://hero.png")
    assert text.count("margin = ") == 1
    assert "margin = Rect2(2, 1, 4, 2)" in text


def test_loop_false_when_repeat_set():
    text = render_godot_tres(_meta(), atlas_res_path="res://hero.png")
    assert '"loop": false' in text and '"loop": true' in text


def test_pingpong_and_reverse_are_unrolled():
    assert ordered_frame_indices(TagMeta(name="a", from_index=0, to_index=3, direction="pingpong")) == [0, 1, 2, 3, 2, 1]
    assert ordered_frame_indices(TagMeta(name="a", from_index=0, to_index=3, direction="reverse")) == [3, 2, 1, 0]
    assert ordered_frame_indices(TagMeta(name="a", from_index=1, to_index=3, direction="pingpong_reverse")) == [3, 2, 1, 2]
    assert ordered_frame_indices(TagMeta(name="a", from_index=2, to_index=2, direction="pingpong")) == [2]


def test_requires_filled_grid_rects():
    meta = _meta()
    meta.sheet_size = (0, 0)
    with pytest.raises(ValueError):
        render_godot_tres(meta, atlas_res_path="res://hero.png")


def test_requires_frames():
    with pytest.raises(ValueError):
        render_godot_tres(SheetMeta(title="x", frames=[], tags=[], sheet_size=(1, 1)), atlas_res_path="res://x.png")


def test_tag_name_with_quotes_and_backslash_is_escaped(tmp_path):
    meta = _meta()
    meta.tags = [TagMeta(name='he said "run"\\now', from_index=0, to_index=1)]
    text = render_godot_tres(meta, atlas_res_path="res://hero.png")
    assert 'he said \\"run\\"\\\\now' in text
    out = export_godot_tres(meta, tmp_path / "hero.tres", atlas_res_path="res://hero.png")
    assert out.exists()
