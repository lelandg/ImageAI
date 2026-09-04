import json
import shutil
import threading
from pathlib import Path

import pytest

from core.sprite.models import FrameMeta
from core.sprite.project import (
    PROJECT_FILE_NAME,
    ActionCard,
    ClipRecord,
    CostEntry,
    ExtractionSettings,
    GenerationSettings,
    KeySettings,
    OutputProfile,
    SpriteProject,
    SpriteProjectManager,
    StabilizeSettings,
    default_profiles,
)


def _write(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    return path


def _build(project_dir: Path) -> SpriteProject:
    project = SpriteProject(name="Hero Sprite")
    project.project_dir = project_dir
    project.character_source = _write(project_dir / "source" / "character.png")
    project.plate_path = _write(project_dir / "source" / "plate.png")
    project.turnaround = {"front": _write(project_dir / "source" / "turnaround" / "front.png")}
    action = ActionCard(id="a1", name="walk", prompt="walk cycle")
    action.clip = ClipRecord(path=_write(project_dir / "clips" / "a1.mp4"), provider="omni", model="m",
                             operation_id="op", params={"fps": 24}, prompt="p", generated_at="2026-08-29T10:00:00",
                             estimated_usd=0.5, actual_usd=None)
    action.frames = [FrameMeta(name="walk_00", source_path=_write(project_dir / "stages" / "a1" / "stabilize" / "0001.png"),
                               frame=(0, 0, 32, 32), source_size=(32, 32))]
    project.actions = [action]
    project.cost_ledger = [CostEntry(action_id="a1", action_name="walk", provider="omni", model="m", seconds=8,
                                     estimated_usd=0.5, actual_usd=0.4, timestamp="2026-08-29T10:00:00")]
    return project


def test_defaults_match_the_design():
    g = GenerationSettings()
    assert (g.provider, g.resolution, g.aspect_ratio, g.duration_s, g.fps) == ("omni", "720p", "16:9", 8, 24)
    assert g.loop_conditioning and g.plate_color == "#00FF00" and g.config_name == "Default"
    e = ExtractionSettings()
    assert (e.mode, e.every_n, e.target_fps, e.exact_n, e.duplicate_threshold) == ("every_n", 8, 12, 8, 0.02)
    k = KeySettings()
    assert (k.method, k.tolerance, k.softness, k.despill, k.ml_backend, k.ml_model) == ("chroma", 0.20, 0.10, "average", "mediapipe", "isnet-anime")
    s = StabilizeSettings()
    assert (s.anchor, s.dejitter, s.dejitter_method, s.pad_px) == ("bottom_center", True, "phase", 0)
    p = OutputProfile(name="hd")
    assert (p.enabled, p.cell_size, p.binary_alpha, p.alpha_threshold, p.dither, p.palette_lock) == (True, (64, 64), False, 128, "none", True)
    profiles = default_profiles()
    assert [p.name for p in profiles] == ["hd", "pixel"]
    assert all(p.enabled for p in profiles)
    assert (profiles[0].cell_size, profiles[1].cell_size) == ((256, 256), (64, 64))
    assert (p.upscale_small, p.upscale_method) == (False, "lanczos")
    assert OutputProfile.from_dict(profiles[1].to_dict()) == profiles[1]
    project = SpriteProject(name="x")
    assert project.genre_preset == "sidescroller"
    assert project.plate_color == "#00FF00"
    assert project.stage_fingerprints == {}


def test_save_and_load_round_trip(tmp_path):
    project = _build(tmp_path / "sprites" / "Hero_Sprite_20260829_100000")
    path = project.save()
    assert path.name == PROJECT_FILE_NAME
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["format"] == "iasprite"
    loaded = SpriteProject.load(path)
    assert loaded.name == "Hero Sprite"
    assert loaded.project_dir == project.project_dir
    assert loaded.actions[0].clip.path == project.actions[0].clip.path
    assert loaded.actions[0].frames[0].source_path == project.actions[0].frames[0].source_path
    assert loaded.turnaround["front"] == project.turnaround["front"]
    assert loaded.cost_ledger[0].actual_usd == 0.4
    assert loaded.profiles[1].name == "pixel"
    assert loaded.to_dict()["actions"] == project.to_dict()["actions"]


def test_load_reanchors_media_after_a_storage_move(tmp_path):
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    project_dir = old_root / "sprites" / "Hero_Sprite_20260829_100000"
    project = _build(project_dir)
    project.save()
    new_root.mkdir()
    shutil.move(str(old_root / "sprites"), str(new_root / "sprites"))
    new_dir = new_root / "sprites" / "Hero_Sprite_20260829_100000"

    loaded = SpriteProject.load(new_dir / PROJECT_FILE_NAME)
    assert loaded.character_source == new_dir / "source" / "character.png"
    assert loaded.plate_path.exists()
    assert loaded.turnaround["front"] == new_dir / "source" / "turnaround" / "front.png"
    assert loaded.actions[0].clip.path == new_dir / "clips" / "a1.mp4"
    assert loaded.actions[0].frames[0].source_path == new_dir / "stages" / "a1" / "stabilize" / "0001.png"


def test_reanchor_leaves_existing_and_unresolvable_paths_alone(tmp_path):
    project = _build(tmp_path / "sprites" / "P_1")
    external = _write(tmp_path / "elsewhere" / "char.png")
    project.character_source = external
    project.plate_path = Path("/nowhere/plate.png")
    assert project.reanchor_media_paths() == 0
    assert project.character_source == external
    assert project.plate_path == Path("/nowhere/plate.png")


def test_load_rejects_empty_and_corrupt_files(tmp_path):
    empty = tmp_path / PROJECT_FILE_NAME
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        SpriteProject.load(empty)
    empty.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        SpriteProject.load(empty)
    assert (tmp_path / "project.iasprite.json.corrupted").exists() or (tmp_path / "project.json.corrupted").exists()


def test_total_cost_sums_the_ledger():
    project = SpriteProject(name="x")
    project.cost_ledger = [
        CostEntry("a", "walk", "omni", "m", 8, 0.5, 0.4, "t"),
        CostEntry("b", "run", "veo", "m", 8, None, 1.0, "t"),
    ]
    assert project.total_cost() == (0.5, 1.4)


def test_sheet_meta_points_frames_at_the_profile_stage(tmp_path):
    project = _build(tmp_path / "sprites" / "P_1")
    hd_file = _write(project.project_dir / "stages" / "a1" / "hd" / "0001.png")
    project.profiles[0].cell_size = (128, 128)
    meta = project.sheet_meta("hd")
    assert meta.title == "Hero_Sprite"
    assert meta.profile == "hd"
    assert meta.cell_size == (128, 128)
    assert meta.frames[0].source_path == hd_file
    assert meta.tags[0].name == "walk"
    assert (meta.tags[0].from_index, meta.tags[0].to_index) == (0, 0)
    assert meta.tags[0].fps_hint == 12
    assert (meta.tags[0].direction, meta.tags[0].repeat) == ("forward", 0)
    project.actions[0].loop = False
    assert project.sheet_meta("hd").tags[0].repeat == 1
    # No pixel stage output yet: fall back to the stabilize frame.
    pixel = project.sheet_meta("pixel")
    assert pixel.frames[0].source_path == project.actions[0].frames[0].source_path
    project.profiles[1].locked_palette = ["#000000", "#ffffff"]
    assert project.sheet_meta("pixel").palette == ["#000000", "#ffffff"]
    project.profiles[1].palette_size = None  # quantization off: no palette reported
    assert project.sheet_meta("pixel").palette is None
    with pytest.raises(ValueError):
        project.sheet_meta("nope")


def test_purge_intermediates_recycles_stages_and_clips(tmp_path, monkeypatch):
    project = _build(tmp_path / "sprites" / "P_1")
    recycled = []

    def fake_recycle(path):
        recycled.append(path)
        shutil.rmtree(path)
        return True

    monkeypatch.setattr("core.sprite.project.send_to_recycle_bin", fake_recycle)
    project.stage_fingerprints = {"a1": {"extract": "abc"}}
    removed = project.purge_intermediates()
    assert removed == 2  # one stage PNG + one clip
    assert sorted(p.name for p in recycled) == ["clips", "stages"]
    assert not (project.project_dir / "stages").exists()
    assert (project.project_dir / "source").exists()
    assert project.stage_fingerprints == {}


def test_manager_creates_lists_loads_and_deletes(tmp_path):
    manager = SpriteProjectManager(base_dir=tmp_path / "sprites")
    project = manager.create_project("My Hero!")
    assert project.project_dir.parent == tmp_path / "sprites"
    assert project.project_dir.name.startswith("My_Hero")
    for sub in ("source", "clips", "stages", "exports"):
        assert (project.project_dir / sub).is_dir()
    assert (project.project_dir / PROJECT_FILE_NAME).exists()
    listed = manager.list_projects()
    assert len(listed) == 1 and listed[0]["name"] == "My Hero!"
    assert listed[0]["slug"] == project.project_dir.name
    assert listed[0]["actions"] == 0
    loaded = manager.load_project(listed[0]["path"])
    assert loaded.name == "My Hero!"
    assert manager.load_project(project.project_dir).name == "My Hero!"
    assert manager.find_project("my hero!") == listed[0]["path"]
    assert manager.find_project(project.project_dir.name) == listed[0]["path"]
    assert manager.find_project("nope") is None
    assert manager.delete_project(loaded)
    assert manager.list_projects() == []


def test_manager_save_project_gives_a_homeless_project_a_directory(tmp_path):
    manager = SpriteProjectManager(base_dir=tmp_path / "sprites")
    project = SpriteProject(name="Loose")
    path = manager.save_project(project)
    assert path.parent == project.project_dir
    assert project.project_dir.parent == tmp_path / "sprites"
    assert (project.project_dir / "stages").is_dir()
    assert manager.save_project(project) == path


def test_concurrent_save_is_serialized_and_never_corrupts_the_file(tmp_path):
    """Minor 4 (interim fix): two threads racing SpriteProject.save() must not

    hit a torn tmp-write-and-replace. The single-writer redesign (GUI owns
    every save) is deferred to sub-project 5b; this only guards the file.
    """
    project = _build(tmp_path / "sprites" / "P_race")
    errors = []

    def hammer():
        try:
            for _ in range(200):
                project.save()
        except Exception as exc:  # noqa: BLE001 - captured and asserted below
            errors.append(exc)

    threads = [threading.Thread(target=hammer) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert not errors
    assert all(not t.is_alive() for t in threads)
    loaded = SpriteProject.load(project.project_file())
    assert loaded.name == project.name
    assert loaded.actions[0].id == "a1"


def test_manager_defaults_to_the_sprite_projects_path(tmp_path, monkeypatch):
    import core.paths as paths_mod

    class FakePaths:
        def sprite_projects(self):
            return tmp_path / "S" / "sprites"

    monkeypatch.setattr(paths_mod, "get_data_paths", lambda: FakePaths())
    assert SpriteProjectManager().base_dir == tmp_path / "S" / "sprites"


# --- sheet_meta fallback warnings (T3: the fallback is never silent) ----------------
import logging  # noqa: E402


def _two_action_project(tmp_path):
    project = _build(tmp_path / "sprites" / "P_warn")
    second = ActionCard(id="a2", name="run", prompt="run cycle")
    second.frames = [
        FrameMeta(name=f"run_{i:02d}",
                  source_path=_write(project.project_dir / "stages" / "a2" / "stabilize" / f"{i + 1:04d}.png"),
                  frame=(0, 0, 32, 32), source_size=(32, 32))
        for i in range(3)
    ]
    project.actions.append(second)
    return project


def _fallback_warnings(caplog):
    return [r for r in caplog.records if r.levelno == logging.WARNING and "native size" in r.message]


def test_sheet_meta_warns_once_per_action_when_the_profile_dir_is_missing(tmp_path, caplog):
    project = _two_action_project(tmp_path)
    with caplog.at_level(logging.WARNING, logger="core.sprite.project"):
        project.sheet_meta("hd")
    warnings = _fallback_warnings(caplog)
    assert len(warnings) == 2  # one per action, not one per frame
    assert "'walk'" in warnings[0].message and "'run'" in warnings[1].message
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="core.sprite.project"):
        project.sheet_meta("hd")
    assert len(_fallback_warnings(caplog)) == 2  # every call warns again


def test_sheet_meta_warning_names_project_action_profile_and_directory(tmp_path, caplog):
    project = _build(tmp_path / "sprites" / "P_warn")
    project.profiles[0].cell_size = (128, 96)
    with caplog.at_level(logging.WARNING, logger="core.sprite.project"):
        project.sheet_meta("hd")
    (record,) = _fallback_warnings(caplog)
    text = record.message
    assert "Hero Sprite" in text
    assert "'walk'" in text
    assert "Export of hd" in text
    assert str(project.project_dir / "stages" / "a1" / "hd") in text
    assert "128x96" in text
    assert "is missing or incomplete" in text
    assert "Run the pipeline" in text


def test_sheet_meta_warns_when_a_frame_has_no_source_path(tmp_path, caplog):
    project = _build(tmp_path / "sprites" / "P_warn")
    _write(project.project_dir / "stages" / "a1" / "hd" / "0001.png")
    project.actions[0].frames[0].source_path = None
    with caplog.at_level(logging.WARNING, logger="core.sprite.project"):
        meta = project.sheet_meta("hd")
    (record,) = _fallback_warnings(caplog)
    assert "'walk'" in record.message
    assert meta.frames[0].source_path is None


def test_sheet_meta_warn_false_keeps_the_fallback_silent(tmp_path, caplog):
    """A preview (player, dialog) passes warn=False; the export keeps the default."""
    project = _two_action_project(tmp_path)
    with caplog.at_level(logging.WARNING, logger="core.sprite.project"):
        meta = project.sheet_meta("hd", warn=False)
    assert _fallback_warnings(caplog) == []
    assert len(meta.frames) == len(project.actions[0].frames) + 3


def test_sheet_meta_does_not_warn_when_the_profile_frames_exist(tmp_path, caplog):
    project = _build(tmp_path / "sprites" / "P_warn")
    _write(project.project_dir / "stages" / "a1" / "hd" / "0001.png")
    with caplog.at_level(logging.WARNING, logger="core.sprite.project"):
        meta = project.sheet_meta("hd")
    assert _fallback_warnings(caplog) == []
    assert meta.frames[0].source_path == project.project_dir / "stages" / "a1" / "hd" / "0001.png"


def test_sheet_meta_does_not_warn_for_a_disabled_profile(tmp_path, caplog):
    project = _build(tmp_path / "sprites" / "P_warn")
    project.profiles[1].enabled = False
    with caplog.at_level(logging.WARNING, logger="core.sprite.project"):
        meta = project.sheet_meta("pixel")
    assert _fallback_warnings(caplog) == []
    assert meta.frames[0].source_path == project.actions[0].frames[0].source_path


def test_legacy_crop_to_cell_aspect_key_is_ignored():
    """A saved ``crop_to_cell_aspect`` key loads inert and never saves back.

    sprite-alpha's project file on disk carries this key from 2026-09-01. The
    crop gained 0-1.4% on real data and the user rejected the crop, so the
    profile has no such field. Do not reintroduce the field, not as an opt-in.
    """
    data = default_profiles()[0].to_dict()
    data["crop_to_cell_aspect"] = True
    profile = OutputProfile.from_dict(data)
    assert profile.cell_size == (256, 256)
    assert not hasattr(profile, "crop_to_cell_aspect")
    assert "crop_to_cell_aspect" not in profile.to_dict()
    assert profile == default_profiles()[0]


def test_project_round_trip_drops_legacy_crop_key(tmp_path):
    """from_dict/to_dict drops ``crop_to_cell_aspect`` from both profiles.

    Same reason as the profile test: the crop gained 0-1.4% on real data and
    the user rejected the crop. A legacy key must not survive a save.
    """
    project = _build(tmp_path / "proj")
    data = project.to_dict()
    assert [p["name"] for p in data["profiles"]] == ["hd", "pixel"]
    for entry in data["profiles"]:
        entry["crop_to_cell_aspect"] = True
    loaded = SpriteProject.from_dict(data)
    saved = loaded.to_dict()
    assert [p["name"] for p in saved["profiles"]] == ["hd", "pixel"]
    assert all("crop_to_cell_aspect" not in p for p in saved["profiles"])
    assert "crop_to_cell_aspect" not in json.dumps(saved)
    assert loaded.profiles == project.profiles
