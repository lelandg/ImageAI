import io
import json
import sys
import types

import numpy as np
import pytest
from PIL import Image

from core.sprite import pipeline as pipeline_mod
from core.sprite.pipeline import (
    STAGE_CODE_VERSION, STAGE_RUNNERS, STAGE_SETTINGS, STAGES, Cancelled, CancelToken,
    no_progress, run_pipeline, stage_dir, stage_fingerprint,
)
from core.sprite.pixelart import pixel_stage_settings, run_pixel_stage
from core.sprite.project import ActionCard, OutputProfile, SpriteProject, StabilizeSettings


def make_profile(**kw):
    base = dict(name="pixel", enabled=True, cell_size=(32, 32), binary_alpha=True,
                alpha_threshold=128, defringe_px=0, palette_size=4, dither="none",
                palette_lock=True, locked_palette=None, upscale_small=False,
                upscale_method="lanczos")
    base.update(kw)
    return OutputProfile(**base)


def make_project(tmp_path, profile):
    project = SpriteProject(name="proj", project_dir=tmp_path / "proj")
    project.profiles = [OutputProfile(name="hd", cell_size=(256, 256)), profile]
    project.stabilize = StabilizeSettings(anchor="bottom_center")
    return project


def make_action():
    return ActionCard(id="a1", name="walk", prompt="walk cycle")


def write_frames(tmp_path, count=3, size=(128, 128), square=(64, 128)):
    """Opaque red bar plus a 4 px soft (alpha 90) edge; the bar slides 8 px per frame."""
    src = tmp_path / "stabilized"
    src.mkdir()
    paths = []
    for i in range(count):
        arr = np.zeros((size[1], size[0], 4), dtype=np.uint8)
        x0 = 8 * i
        arr[:square[1], x0:x0 + square[0]] = (200, 40, 40, 255)
        arr[:square[1], x0 + square[0]:x0 + square[0] + 4] = (200, 40, 40, 90)
        path = src / f"{i + 1:04d}.png"
        Image.fromarray(arr).save(path)
        paths.append(path)
    return paths


def test_pixel_stage_writes_fitted_binary_quantized_frames(tmp_path):
    inputs = write_frames(tmp_path)
    profile = make_profile()
    project = make_project(tmp_path, profile)
    out_dir = tmp_path / "pixel"
    outputs = run_pixel_stage(project, make_action(), inputs, out_dir, no_progress, None)
    assert [p.name for p in outputs] == ["0001.png", "0002.png", "0003.png"]
    for path in outputs:
        img = Image.open(path)
        assert img.size == (32, 32) and img.mode == "RGBA"
        arr = np.asarray(img)
        assert set(np.unique(arr[..., 3]).tolist()) <= {0, 255}
        opaque = arr[arr[..., 3] == 255][:, :3]
        assert {tuple(px) for px in opaque} <= {(200, 40, 40)}
    assert profile.locked_palette == ["#C82828"]
    manifest = json.loads((out_dir / "pixel.json").read_text(encoding="utf-8"))
    assert manifest["scale"] == 4
    assert manifest["palette"] == ["#C82828"]
    assert manifest["warnings"] == []


def test_pixel_stage_reuses_locked_palette(tmp_path):
    inputs = write_frames(tmp_path)
    profile = make_profile(locked_palette=["#000000", "#FFFFFF"])
    project = make_project(tmp_path, profile)
    outputs = run_pixel_stage(project, make_action(), inputs, tmp_path / "pixel", no_progress, None)
    arr = np.asarray(Image.open(outputs[0]))
    opaque = arr[arr[..., 3] == 255][:, :3]
    assert {tuple(px) for px in opaque} == {(0, 0, 0)}
    assert profile.locked_palette == ["#000000", "#FFFFFF"]


def test_pixel_stage_warns_on_small_source_and_does_not_upscale(tmp_path):
    inputs = write_frames(tmp_path, count=1, size=(16, 16), square=(8, 16))
    project = make_project(tmp_path, make_profile(palette_size=None))
    messages = []
    outputs = run_pixel_stage(project, make_action(), inputs, tmp_path / "pixel",
                              lambda stage, done, total, msg: messages.append(msg), None)
    arr = np.asarray(Image.open(outputs[0]))
    assert int((arr[..., 3] == 255).sum()) == 8 * 16
    manifest = json.loads((tmp_path / "pixel" / "pixel.json").read_text(encoding="utf-8"))
    assert len(manifest["warnings"]) == 1 and "16x16" in manifest["warnings"][0]
    assert any(msg.startswith("warning: ") for msg in messages)
    assert manifest["palette"] == []


def test_pixel_stage_upscale_small_fills_cell(tmp_path, monkeypatch):
    fake = types.ModuleType("core.upscaling")
    calls = []

    def upscale_image(image_data, target_width, target_height, method="lanczos", **kwargs):
        calls.append(method)
        img = Image.open(io.BytesIO(image_data))
        img.load()
        out = io.BytesIO()
        img.resize((target_width, target_height), Image.Resampling.NEAREST).save(out, format="PNG")
        return out.getvalue()

    fake.upscale_image = upscale_image
    monkeypatch.setitem(sys.modules, "core.upscaling", fake)
    inputs = write_frames(tmp_path, count=1, size=(16, 16), square=(8, 16))
    profile = make_profile(palette_size=None)
    profile.upscale_small = True
    profile.upscale_method = "realesrgan"
    project = make_project(tmp_path, profile)
    outputs = run_pixel_stage(project, make_action(), inputs, tmp_path / "pixel", no_progress, None)
    arr = np.asarray(Image.open(outputs[0]))
    assert int((arr[..., 3] == 255).sum()) == 16 * 32
    assert calls == ["realesrgan"]
    manifest = json.loads((tmp_path / "pixel" / "pixel.json").read_text(encoding="utf-8"))
    assert manifest["warnings"] == []
    assert manifest["upscale_small"] is True and manifest["upscale_method"] == "realesrgan"


def test_pixel_stage_floyd_adds_crawl_warning(tmp_path):
    inputs = write_frames(tmp_path, count=2)
    project = make_project(tmp_path, make_profile(dither="floyd"))
    run_pixel_stage(project, make_action(), inputs, tmp_path / "pixel", no_progress, None)
    manifest = json.loads((tmp_path / "pixel" / "pixel.json").read_text(encoding="utf-8"))
    assert any("crawl" in text for text in manifest["warnings"])


def test_pixel_stage_skips_when_profile_disabled_or_absent(tmp_path):
    inputs = write_frames(tmp_path, count=1)
    project = make_project(tmp_path, make_profile(enabled=False))
    assert run_pixel_stage(project, make_action(), inputs, tmp_path / "pixel", no_progress, None) == []
    assert not (tmp_path / "pixel").exists()
    project.profiles = [OutputProfile(name="hd")]
    assert run_pixel_stage(project, make_action(), inputs, tmp_path / "pixel", no_progress, None) == []
    assert not (tmp_path / "pixel").exists()


def test_pixel_stage_honors_cancel_token(tmp_path):
    inputs = write_frames(tmp_path, count=3)
    project = make_project(tmp_path, make_profile())
    token = CancelToken()

    def cancel_after_first_fit(stage, done, total, msg):
        if msg.startswith("fit ") and done == 1:
            token.cancel()

    with pytest.raises(Cancelled):
        run_pixel_stage(project, make_action(), inputs, tmp_path / "pixel",
                        cancel_after_first_fit, token)
    assert not (tmp_path / "pixel" / "pixel.json").exists()


def test_pixel_stage_second_run_with_fewer_frames_removes_stale_output(tmp_path):
    inputs = write_frames(tmp_path, count=3)
    project = make_project(tmp_path, make_profile())
    out_dir = tmp_path / "pixel"
    run_pixel_stage(project, make_action(), inputs, out_dir, no_progress, None)
    assert sorted(p.name for p in out_dir.glob("*.png")) == ["0001.png", "0002.png", "0003.png"]
    run_pixel_stage(project, make_action(), inputs[:1], out_dir, no_progress, None)
    assert sorted(p.name for p in out_dir.glob("*.png")) == ["0001.png"]


def test_pixel_stage_is_registered_at_code_version_2():
    assert STAGE_RUNNERS["pixel"] is run_pixel_stage
    assert STAGE_SETTINGS["pixel"] is pixel_stage_settings
    assert STAGE_CODE_VERSION["pixel"] == 2


def test_pixel_settings_drive_the_fingerprint(tmp_path):
    profile = make_profile()
    project = make_project(tmp_path, profile)
    action = make_action()
    settings = pixel_stage_settings(project, action)
    assert settings["upscale_small"] is False and settings["upscale_method"] == "lanczos"
    assert settings["locked_palette"] is None
    base = stage_fingerprint(project, action, "pixel")
    profile.upscale_small = True
    assert stage_fingerprint(project, action, "pixel") != base
    profile.upscale_small = False
    profile.locked_palette = ["#112233"]
    assert stage_fingerprint(project, action, "pixel") != base
    profile.locked_palette = None
    profile.enabled = False
    assert pixel_stage_settings(project, action) == {}
    project.profiles = [OutputProfile(name="hd")]
    assert pixel_stage_settings(project, action) == {}


def test_run_pipeline_dispatches_pixel_runner_with_stabilize_frames(tmp_path, monkeypatch):
    project = make_project(tmp_path, make_profile())
    action = make_action()
    project.actions = [action]
    frame = write_frames(tmp_path, count=1)[0]
    for stage in STAGES[:STAGES.index("pixel")]:
        out_dir = stage_dir(project, action, stage)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / frame.name).write_bytes(frame.read_bytes())
        project.stage_fingerprints.setdefault(action.id, {})[stage] = stage_fingerprint(
            project, action, stage)
    calls = []

    def fake_runner(project, action, input_frames, out_dir, progress, token):
        calls.append(([p.name for p in input_frames], out_dir))
        return []

    monkeypatch.setitem(pipeline_mod.STAGE_RUNNERS, "pixel", fake_runner)
    run_pipeline(project, action, upto="pixel")
    assert calls == [(["0001.png"], stage_dir(project, action, "pixel"))]


def test_sheet_meta_pixel_carries_locked_palette(tmp_path):
    profile = make_profile(locked_palette=["#000000", "#FF00FF"])
    project = make_project(tmp_path, profile)
    assert project.sheet_meta("pixel").palette == ["#000000", "#FF00FF"]
    assert project.sheet_meta("hd").palette is None
