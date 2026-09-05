from pathlib import Path

from core.sprite.models import FrameMeta, SheetMeta, TagMeta
from core.constants import VERSION


def _sheet():
    frames = [FrameMeta(name=f"hero_walk_{i:02d}", source_path=Path(f"/x/{i}.png"), frame=(i * 16, 0, 16, 16),
                        sprite_source_size=(0, 0, 16, 16), source_size=(16, 16), duration_ms=80)
              for i in range(4)]
    tags = [TagMeta(name="walk", from_index=0, to_index=2, direction="pingpong", repeat=0, fps_hint=12),
            TagMeta(name="idle", from_index=3, to_index=3)]
    return SheetMeta(title="hero", frames=frames, tags=tags, sheet_size=(64, 16), cell_size=(16, 16))


def test_defaults_match_the_design():
    frame = FrameMeta(name="f", source_path=None, frame=(0, 0, 0, 0))
    assert frame.rotated is False
    assert frame.trimmed is False
    assert frame.duration_ms == 100
    assert frame.pivot == (0.5, 1.0)
    assert frame.overrides == {}
    tag = TagMeta(name="t", from_index=0, to_index=0)
    assert (tag.direction, tag.repeat, tag.fps_hint) == ("forward", 0, None)
    sheet = SheetMeta(title="s", frames=[], tags=[])
    assert sheet.cell_size == (64, 64)
    assert sheet.profile == "hd"
    assert sheet.app == "ImageAI"
    assert sheet.version == VERSION


def test_round_trip_through_dict_is_lossless():
    sheet = _sheet()
    sheet.palette = ["#000000", "#ffffff"]
    again = SheetMeta.from_dict(sheet.to_dict())
    assert again == sheet


def test_to_dict_uses_plain_json_types():
    import json
    data = _sheet().to_dict()
    json.dumps(data)
    assert data["frames"][0]["source_path"] == str(Path("/x/0.png"))
    assert data["frames"][0]["frame"] == [0, 0, 16, 16]
    assert data["tags"][0]["direction"] == "pingpong"


def test_frames_for_returns_the_tag_range_inclusive():
    sheet = _sheet()
    walk = sheet.frames_for(sheet.tags[0])
    assert [f.name for f in walk] == ["hero_walk_00", "hero_walk_01", "hero_walk_02"]
    assert [f.name for f in sheet.frames_for(sheet.tags[1])] == ["hero_walk_03"]
    assert sheet.frames_for(TagMeta(name="empty", from_index=3, to_index=1)) == []


def test_from_dict_tolerates_missing_optional_keys():
    frame = FrameMeta.from_dict({"name": "f", "frame": [1, 2, 3, 4]})
    assert frame.source_path is None
    assert frame.frame == (1, 2, 3, 4)
    tag = TagMeta.from_dict({"name": "t", "from_index": 0, "to_index": 1})
    assert tag.fps_hint is None
