"""Real headless import/process/export contracts, including safe replacement."""

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from cli.commands.sprite_media import execute_media
from core.sprite.exporters.engine_presets import ENGINE_PRESETS, FORMAT_IDS
from core.sprite.pipeline import CancelToken, Cancelled, is_stage_current, list_frames, no_progress, stage_dir
from core.sprite.project import ActionCard, BackgroundSettings, OutputProfile, SpriteProject
from core.utils import sidecar_path


def run(operation, project, **data):
    return execute_media(operation, project, data, log=lambda *_: None,
                         progress=no_progress, token=CancelToken())


@pytest.fixture
def project(tmp_path):
    result = SpriteProject("CLI Lantern", project_dir=tmp_path / "project")
    result.actions = [ActionCard("pulse", "Pulse", "pulse"), ActionCard("orbit", "Orbit", "orbit")]
    result.key.method = "none"
    result.profiles = [OutputProfile("hd", cell_size=(32, 32)), OutputProfile("pixel", cell_size=(16, 16))]
    result.save()
    return result


@pytest.fixture
def sources(tmp_path):
    paths = []
    for i, color in enumerate(("#ee6633", "#33dd99", "#5577ee")):
        image = Image.new("RGBA", (24, 20), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((5 + i, 5, 16 + i, 16), fill=color)
        path = tmp_path / f"source{i}.png"
        image.save(path)
        paths.append(str(path))
    return paths


def prepare(project, sources, action="pulse"):
    run("import-frames", project, actions=[action], paths=sources)
    run("process", project, actions=[action])


def test_import_process_all_formats_and_profiles_roundtrip(project, sources):
    for action in ("pulse", "orbit"):
        prepare(project, sources, action)
    result = run("export", project, formats=list(FORMAT_IDS), grid={"scales": [1, 2]})
    assert result["profiles"] == ["hd", "pixel"]
    assert result["actions"] == ["pulse", "orbit"]
    assert all(Path(path).is_file() for path in result["files"])
    assert any("@2x.png" in p for p in result["files"])
    assert any(p.endswith(".tres") for p in result["files"])
    assert any(p.endswith(".aseprite") for p in result["files"])
    manifest = json.loads(Path(result["manifest"]).read_text())
    assert manifest["files"] == result["files"]
    saved = SpriteProject.load(project.project_file())
    assert all(is_stage_current(saved, action, "pixel") for action in saved.actions)
    with Image.open(next(p for p in result["files"] if p.endswith("Pulse.gif") and "hd" in p)) as image:
        assert image.n_frames == 3
        assert image.size == (32, 32)


def test_selection_names_timing_direction_and_solid_background(project, sources):
    prepare(project, sources)
    # An unprocessed, unselected action must not prevent exporting the selected action.
    result = run("preview", project, actions=["Pulse"], profiles=["hd"],
                 background={"mode": "solid", "color": "#a1b2c3"},
                 tags={"pulse": {"direction": "pingpong", "repeat": 2, "durations_ms": [50, 100, 150]}})
    gif = Path(next(p for p in result["files"] if p.endswith(".gif")))
    with Image.open(gif) as image:
        assert image.n_frames == 4
        assert image.convert("RGB").getpixel((0, 0)) == (161, 178, 195)
        assert "transparency" not in image.info
    details = json.loads(sidecar_path(gif).read_text())
    assert details["durations_ms"] == [50, 100, 150, 100]
    assert details["background_mode"] == "solid"
    assert project.background.mode == "transparent"


def test_stale_pipeline_is_rejected_before_export(project, sources):
    prepare(project, sources)
    project.key.tolerance = 0.44
    with pytest.raises(ValueError, match="stale"):
        run("export", project, actions=["pulse"], formats=["gif"])
    assert not list((project.project_dir / "exports").rglob("*.gif"))


def test_incomplete_profile_cannot_fall_back_to_stabilize_frames(project, sources):
    prepare(project, sources)
    profile = stage_dir(project, project.actions[0], "hd")
    list_frames(profile)[1].unlink()
    with pytest.raises(ValueError, match="incomplete"):
        run("export", project, actions=["pulse"], profiles=["hd"], formats=["gif"])


def test_reimport_shorter_sequence_removes_trailing_frames_and_invalidates_cache(project, sources):
    prepare(project, sources)
    action = project.actions[0]
    run("import-frames", project, actions=["pulse"], paths=sources[:1])
    assert len(list_frames(stage_dir(project, action, "extract"))) == 1
    assert action.frames == []
    assert list(project.stage_fingerprints[action.id]) == ["extract"]
    run("process", project, actions=["pulse"])
    assert len(action.frames) == 1


def test_failed_import_keeps_accepted_frames_and_project(project, sources, tmp_path):
    prepare(project, sources)
    before = project.project_file().read_bytes()
    extract = stage_dir(project, project.actions[0], "extract")
    pixels = {p.name: p.read_bytes() for p in list_frames(extract)}
    corrupt = tmp_path / "broken.png"
    corrupt.write_bytes(b"not an image")
    with pytest.raises(ValueError, match="Cannot read image"):
        run("import-frames", project, actions=["pulse"], paths=[sources[0], str(corrupt)])
    assert project.project_file().read_bytes() == before
    assert {p.name: p.read_bytes() for p in list_frames(extract)} == pixels
    assert is_stage_current(project, project.actions[0], "pixel")


def test_import_rolls_back_when_project_cannot_be_saved(project, sources, monkeypatch):
    prepare(project, sources)
    before = project.to_dict()
    paths = list_frames(stage_dir(project, project.actions[0], "extract"))
    pixels = [p.read_bytes() for p in paths]

    def failure(*args, **kwargs):
        raise OSError("disk is full")

    monkeypatch.setattr(project, "save", failure)
    with pytest.raises(OSError, match="disk is full"):
        run("import-frames", project, actions=["pulse"], paths=sources[:1])
    assert project.to_dict() == before
    assert [p.read_bytes() for p in paths] == pixels


def test_ctrl_c_during_import_promotion_restores_project_and_frames(project, sources, monkeypatch):
    prepare(project, sources)
    before = project.project_file().read_bytes()
    paths = list_frames(stage_dir(project, project.actions[0], "extract"))
    pixels = [p.read_bytes() for p in paths]
    original_save = project.save

    def interrupted_save(*args, **kwargs):
        original_save(*args, **kwargs)
        raise KeyboardInterrupt

    monkeypatch.setattr(project, "save", interrupted_save)
    with pytest.raises(KeyboardInterrupt):
        run("import-frames", project, actions=["pulse"], paths=sources[:1])
    assert project.project_file().read_bytes() == before
    assert [p.read_bytes() for p in paths] == pixels


def test_sheet_import_checks_bounds_before_replacing(project, sources, tmp_path):
    prepare(project, sources)
    action = project.actions[0]
    sheet = Image.new("RGBA", (48, 20))
    for x, source in zip((0, 24), sources):
        with Image.open(source) as image:
            sheet.paste(image, (x, 0))
    path = tmp_path / "sheet.png"
    sheet.save(path)
    with pytest.raises(ValueError, match="does not fit"):
        run("import-sheet", project, actions=["Pulse"], path=str(path), columns=3, rows=1, cell=[24, 20])
    assert is_stage_current(project, action, "pixel")
    result = run("import-sheet", project, actions=["Pulse"], path=str(path), columns=2, rows=1)
    assert result["frames"] == 2
    run("process", project, actions=["pulse"], upto="stabilize")
    # Profile preparation is allowed after current stabilize; it saves its cache.
    run("export", project, actions=["pulse"], profiles=["hd"], formats=["gif"])
    assert is_stage_current(project, action, "hd")


def test_frame_export_uses_requested_profile_and_sidecar(project, sources, tmp_path):
    prepare(project, sources)
    output = tmp_path / "single.png"
    result = run("frame-export", project, actions=["pulse"], profile="pixel", index=1, output=str(output))
    assert result["files"] == [str(output), str(sidecar_path(output))]
    with Image.open(output) as image:
        assert image.size == (16, 16)
    with pytest.raises(ValueError, match="outside"):
        run("frame-export", project, actions=["pulse"], index=99)


@pytest.mark.parametrize("preset", list(ENGINE_PRESETS))
def test_engine_presets_produce_their_documented_formats(project, sources, preset):
    prepare(project, sources)
    result = run("export", project, actions=["pulse"], profiles=["pixel"], engine_preset=preset)
    assert result["formats"] == list(ENGINE_PRESETS[preset].formats)
    assert result["files"]
    assert all(Path(p).exists() for p in result["files"])


def test_invalid_template_and_unknown_action_do_not_write_exports(project, sources):
    prepare(project, sources)
    with pytest.raises(ValueError, match="duplicate"):
        run("export", project, actions=["pulse"], formats=["gif", "png_sequence"], template="same.png")
    with pytest.raises(ValueError, match="unknown"):
        run("process", project, actions=["Pusle"])
    assert not (project.project_dir / "exports").exists()


def test_process_saves_checkpoints_before_later_cancellation(project, sources):
    run("import-frames", project, actions=["pulse"], paths=sources)
    token = CancelToken()

    def cancel_after_key(stage, done, total, message):
        if message == "key: done":
            token.cancel()

    with pytest.raises(Cancelled):
        execute_media("process", project, {"actions": ["pulse"]}, log=lambda *_: None,
                      progress=cancel_after_key, token=token)
    saved = SpriteProject.load(project.project_file())
    assert is_stage_current(saved, saved.actions[0], "key")
    assert not is_stage_current(saved, saved.actions[0], "cleanup")


def test_original_background_requires_processing_mode_change(project, sources):
    prepare(project, sources)
    with pytest.raises(ValueError, match="run process"):
        run("export", project, actions=["pulse"], background={"mode": "original"})
    project.background = BackgroundSettings(mode="original")
    run("process", project, actions=["pulse"])
    result = run("preview", project, actions=["pulse"], profiles=["hd"])
    assert result["background"]["mode"] == "original"


def test_video_import_extracts_and_persists_copy(project, synthetic_mp4):
    result = run("import-video", project, actions=["pulse"], path=str(synthetic_mp4),
                 extraction={"mode": "exact_n", "exact_n": 3})
    action = project.actions[0]
    assert result["frames"] == 3
    assert action.clip.path != synthetic_mp4
    assert action.clip.path.read_bytes() == synthetic_mp4.read_bytes()
    assert is_stage_current(project, action, "extract")
    run("process", project, actions=["pulse"], profiles=["hd"])
    assert len(SpriteProject.load(project.project_file()).actions[0].frames) == 3
