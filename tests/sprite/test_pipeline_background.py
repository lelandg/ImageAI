"""Original background skips removal but shares geometry and output profiles."""

import numpy as np
import pytest
from PIL import Image

from core.sprite import keying
from core.sprite.pipeline import (
    STAGES, ensure_profile_stages, is_stage_current, register_external_frames,
    run_pipeline, stage_dir, stage_fingerprint,
)
from core.sprite.project import ActionCard, BackgroundSettings, OutputProfile, SpriteProject


def make_project(tmp_path, *, alpha=False, cell=(80, 80), upscale=False):
    project = SpriteProject(name="background", project_dir=tmp_path / "project")
    project.background = BackgroundSettings(mode="original")
    project.profiles = [
        OutputProfile(name=name, enabled=True, cell_size=cell, binary_alpha=True,
                      palette_size=2, locked_palette=["#000000", "#FFFFFF"],
                      upscale_small=upscale)
        for name in ("hd", "pixel")
    ]
    project.key.method = "chroma"
    project.key.key_color = "#00FF00"
    project.key.choke_px = 3
    project.key.feather_px = 2
    project.key.despeckle_px = 20
    project.key.edge_decontaminate = True
    project.stabilize.pad_px = 8
    project.stabilize.dejitter = True
    action = ActionCard(id="a1", name="walk", prompt="walk")
    project.actions = [action]
    directory = stage_dir(project, action, "extract")
    directory.mkdir(parents=True)
    arrays = []
    for index in range(2):
        pixels = np.full((24, 40, 4), (0, 255, 0, 255), dtype=np.uint8)
        y, x = np.indices((12, 20))
        pixels[6:18, 10 + index:30 + index, :3] = np.stack(
            ((x * 11) % 255, (y * 19) % 255, (x + y) * 7), axis=-1)
        if alpha:
            pixels[..., 3] = np.arange(40, dtype=np.uint8)[None, :] * 6
        Image.fromarray(pixels).save(directory / f"{index + 1:04d}.png")
        arrays.append(pixels)
    register_external_frames(project, action)
    return project, action, arrays


@pytest.mark.parametrize("alpha", [False, True])
def test_original_preserves_border_color_pattern_and_source_alpha(tmp_path, monkeypatch, alpha):
    project, action, expected = make_project(tmp_path, alpha=alpha)

    def unwanted(*args, **kwargs):
        pytest.fail("Original background must not run subject cleanup")

    for name in ("key_pass", "cleanup_pass", "alpha_pass"):
        monkeypatch.setattr(keying, name, unwanted)
    output = run_pipeline(project, action)
    for stage, paths in output.items():
        if stage in ("stabilize", "hd", "pixel"):
            continue
        for path, pixels in zip(paths, expected):
            with Image.open(path) as image:
                assert image.size == (40, 24), stage
                np.testing.assert_array_equal(np.asarray(image.convert("RGBA")), pixels)
    for stage in ("hd", "pixel"):
        for path in output[stage]:
            with Image.open(path) as image:
                assert image.size == (80, 80)
    assert not (stage_dir(project, action, "key") / "key.json").exists()


@pytest.mark.parametrize("cell,upscale", [
    ((20, 20), False),
    ((80, 80), True),
    ((80, 80), False),
])
def test_original_profiles_apply_canvas_and_requested_palette(
        tmp_path, cell, upscale):
    project, action, _ = make_project(tmp_path, cell=cell, upscale=upscale)
    output = run_pipeline(project, action)
    for name in ("hd", "pixel"):
        for path in output[name]:
            with Image.open(path) as image:
                assert image.size == cell
                if name == "pixel":
                    pixels = np.asarray(image.convert("RGBA"))
                    colors = {tuple(rgb) for rgb in pixels[pixels[..., 3] > 0, :3]}
                    assert colors <= {(0, 0, 0), (255, 255, 255)}


def test_background_mode_cache_roundtrip_and_export_stale_guard(tmp_path):
    project, action, _ = make_project(tmp_path)
    first = run_pipeline(project, action)
    expected = [path.read_bytes() for path in first["pixel"]]
    original = {stage: stage_fingerprint(project, action, stage) for stage in STAGES}
    project.background.mode = "transparent"
    keyed = {stage: stage_fingerprint(project, action, stage) for stage in STAGES}
    assert original["extract"] == keyed["extract"]
    for stage in STAGES[1:]:
        assert original[stage] != keyed[stage]
        assert not is_stage_current(project, action, stage)
    assert "stale" in ensure_profile_stages(project, action, ["hd"])["hd"]
    run_pipeline(project, action, upto="stabilize")
    project.background.mode = "original"
    assert not is_stage_current(project, action, "stabilize")
    output = run_pipeline(project, action)
    assert [path.read_bytes() for path in output["pixel"]] == expected
    assert all(is_stage_current(project, action, stage) for stage in STAGES)


def test_original_cache_ignores_only_disabled_cleanup_and_fill_color_settings(tmp_path):
    project, action, _ = make_project(tmp_path)
    before = {stage: stage_fingerprint(project, action, stage) for stage in STAGES}
    project.key.tolerance = 0.7
    project.background.color = "#123456"
    assert {stage: stage_fingerprint(project, action, stage) for stage in STAGES} == before
    project.profile("pixel").cell_size = (20, 20)
    assert stage_fingerprint(project, action, "pixel") != before["pixel"]
    assert stage_fingerprint(project, action, "hd") == before["hd"]


def test_transparent_and_solid_share_processing_cache(tmp_path):
    project, action, _ = make_project(tmp_path)
    project.background.mode = "transparent"
    before = {stage: stage_fingerprint(project, action, stage) for stage in STAGES}
    project.background.mode = "solid"
    project.background.color = "#ABCDEF"
    assert {stage: stage_fingerprint(project, action, stage) for stage in STAGES} == before
