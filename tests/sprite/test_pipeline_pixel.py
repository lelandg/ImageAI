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
    PipelineError, no_progress, run_pipeline, stage_dir, stage_fingerprint,
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


def test_pixel_stage_is_registered_at_code_version_3():
    assert STAGE_RUNNERS["pixel"] is run_pixel_stage
    assert STAGE_SETTINGS["pixel"] is pixel_stage_settings
    assert STAGE_CODE_VERSION["pixel"] == 3


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


def _write_solid_frames(tmp_path, subdir, count, color):
    src = tmp_path / subdir
    src.mkdir()
    paths = []
    for i in range(count):
        arr = np.zeros((32, 32, 4), dtype=np.uint8)
        arr[:, :] = (*color, 255)
        path = src / f"{i + 1:04d}.png"
        Image.fromarray(arr).save(path)
        paths.append(path)
    return paths


def test_pixel_stage_unlocked_shares_one_palette_across_actions(tmp_path):
    """I1 regression: with palette_lock=False and more than one action, a
    second action's run must not overwrite the project-wide locked_palette
    action A was quantized with -- that overwrite would change A's stage
    fingerprint (locked_palette feeds it via pixel_stage_settings) so A's
    second run is never a cache hit, and SheetMeta.palette would describe
    only the last action processed instead of matching A's PNGs on disk."""
    profile = make_profile(palette_lock=False, palette_size=2)
    project = make_project(tmp_path, profile)
    action_a = ActionCard(id="a1", name="walk", prompt="walk")
    action_b = ActionCard(id="b1", name="run", prompt="run")
    inputs_a = _write_solid_frames(tmp_path, "a_src", 2, (200, 40, 40))
    inputs_b = _write_solid_frames(tmp_path, "b_src", 2, (40, 40, 200))
    out_a = tmp_path / "pixel_a"
    out_b = tmp_path / "pixel_b"

    run_pixel_stage(project, action_a, inputs_a, out_a, no_progress, None)
    fingerprint_a_after_first_run = stage_fingerprint(project, action_a, "pixel")
    palette_after_a = list(profile.locked_palette)
    assert palette_after_a == ["#C82828"]

    run_pixel_stage(project, action_b, inputs_b, out_b, no_progress, None)
    # B's run must not have changed the shared palette -- so A's fingerprint,
    # which hashes locked_palette, is unchanged and a second run of A would
    # be a cache hit (is_stage_current would see no settings change).
    assert profile.locked_palette == palette_after_a
    assert stage_fingerprint(project, action_a, "pixel") == fingerprint_a_after_first_run

    run_pixel_stage(project, action_a, inputs_a, out_a, no_progress, None)
    assert profile.locked_palette == palette_after_a

    arr = np.asarray(Image.open(sorted(out_a.glob("*.png"))[0]))
    opaque = arr[arr[..., 3] == 255][:, :3]
    assert {tuple(px) for px in opaque} <= {(200, 40, 40)}
    # SheetMeta.palette must match what is actually on disk for action A.
    assert project.sheet_meta("pixel").palette == palette_after_a


@pytest.mark.parametrize("field, bad_value", [
    ("dither", "bogus"),
    ("palette_size", 0),
    ("upscale_method", "bogus"),
])
def test_run_pixel_stage_raises_pipeline_error_on_bad_profile_field(tmp_path, caplog, field, bad_value):
    """I2 regression: bad profile config must surface as PipelineError with a
    user-facing message and be logged, like every sibling runner, instead of
    an un-annotated ValueError."""
    inputs = write_frames(tmp_path, count=1)
    project = make_project(tmp_path, make_profile(**{field: bad_value}))
    with caplog.at_level("ERROR"):
        with pytest.raises(PipelineError) as excinfo:
            run_pixel_stage(project, make_action(), inputs, tmp_path / "pixel", no_progress, None)
    assert str(bad_value) in excinfo.value.user_message
    assert any(str(bad_value) in record.message for record in caplog.records)


def test_pixel_stage_scale_comes_from_the_whole_frame_not_the_subject(tmp_path):
    """1280x720 frames fit a 64x64 cell at the shared integer scale 1/20.

    Regression guard for the padded-fit contract on the pixel stage default
    path. A cell-aspect crop was tried on 2026-09-01. It gained 0-1.4% on the
    three real projects and the user rejected the crop. The subject has
    transparent margin on every side: a subject that touches the frame
    edges makes the protect rect equal the frame, and that crop was a no-op
    on such input, so the old edge-to-edge fixture could not detect it.
    Against the crop the scale was 12 and the bbox differed.
    """
    from core.sprite.project import default_profiles

    src = tmp_path / "stabilized"
    src.mkdir()
    inputs = []
    for i in range(2):
        arr = np.zeros((720, 1280, 4), dtype=np.uint8)
        arr[35:685, 440:840] = (200, 40, 40, 255)
        path = src / f"{i + 1:04d}.png"
        Image.fromarray(arr).save(path)
        inputs.append(path)
    project = SpriteProject(name="proj", project_dir=tmp_path / "proj")
    project.profiles = default_profiles()          # pixel cell 64x64, palette 32
    project.stabilize = StabilizeSettings(anchor="bottom_center")
    out_dir = tmp_path / "pixel"

    outputs = run_pixel_stage(project, make_action(), inputs, out_dir, no_progress, None)

    manifest = json.loads((out_dir / "pixel.json").read_text(encoding="utf-8"))
    assert manifest["scale"] == 20
    assert len(outputs) == 2
    for path in outputs:
        with Image.open(path) as im:
            assert im.size == (64, 64)
            alpha = np.asarray(im.getchannel("A"))
        # 1280x720 / 20 = 64x36, bottom-center: rows 28..63. The subject at
        # rows 35..685, cols 440..840 lands at rows 30..61, cols 22..41.
        assert Image.fromarray(alpha).getbbox() == (22, 30, 42, 62)


def test_pixel_stage_keeps_every_row_of_a_portrait_frame(tmp_path):
    """498x588 frames fit a 128x128 cell at scale 1/5 with no row lost.

    Regression guard for the padded-fit contract (sprite-3's frame size).
    The bars sit inside a transparent margin, so a crop of either axis
    changes the bbox; the scale alone would survive a crop that only trims
    height.
    """
    src = tmp_path / "stabilized"
    src.mkdir()
    inputs = []
    for i in range(2):
        arr = np.zeros((588, 498, 4), dtype=np.uint8)
        # A vertical bar (rows 40..548) and a horizontal bar (cols 30..468).
        arr[40:548, 100 + 5 * i:400 + 5 * i] = (200, 40, 40, 255)
        arr[200:300, 30:468] = (200, 40, 40, 255)
        path = src / f"{i + 1:04d}.png"
        Image.fromarray(arr).save(path)
        inputs.append(path)
    project = make_project(tmp_path, make_profile(cell_size=(128, 128)))
    out_dir = tmp_path / "pixel"

    outputs = run_pixel_stage(project, make_action(), inputs, out_dir, no_progress, None)

    manifest = json.loads((out_dir / "pixel.json").read_text(encoding="utf-8"))
    assert manifest["scale"] == 5
    for path in outputs:
        with Image.open(path) as im:
            assert im.size == (128, 128)
            alpha = np.asarray(im.getchannel("A"))
        # ceil(498 / 5) x ceil(588 / 5) = 100x118 at (14, 10), bottom-center.
        # Bars: cols 30..468 -> 6..93 (+14 = 20..108); rows 40..548 -> 8..109
        # (+10 = 18..120).
        assert Image.fromarray(alpha).getbbox() == (20, 18, 108, 120)
