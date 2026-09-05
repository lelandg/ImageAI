"""Background selection must not bypass configured output geometry."""

import numpy as np
import pytest
from PIL import Image

from core.sprite.pipeline import (
    hd_runner, stage_fingerprint, stabilize_runner,
)
from core.sprite.pixelart import run_pixel_stage
from core.sprite.project import ActionCard, OutputProfile, SpriteProject


@pytest.mark.parametrize("mode", ["original", "transparent", "solid"])
@pytest.mark.parametrize("profile_name,runner", [("hd", hd_runner), ("pixel", run_pixel_stage)])
@pytest.mark.parametrize("cell", [(256, 256), (64, 64), (96, 48)])
def test_every_background_honors_exact_profile_canvas(tmp_path, mode, profile_name, runner, cell):
    project = SpriteProject(name="geometry", project_dir=tmp_path)
    project.background.mode = mode
    project.profiles = [OutputProfile(name=profile_name, cell_size=cell, palette_size=None)]
    frame = tmp_path / "wide.png"
    Image.new("RGBA", (1280, 720), (80, 120, 160, 255)).save(frame)
    result = runner(project, ActionCard(id="a1", name="walk", prompt="walk"), [frame], tmp_path / "out",
                    lambda *args: None, None)
    with Image.open(result[0]) as image:
        assert image.size == cell


def test_original_uses_same_crop_padding_and_anchor_as_other_modes(tmp_path):
    project = SpriteProject(name="geometry", project_dir=tmp_path)
    project.stabilize.pad_px = 3
    project.stabilize.anchor = "top_left"
    project.stabilize.dejitter = False
    action = ActionCard(id="a1", name="walk", prompt="walk")
    frame = tmp_path / "border.png"
    pixels = np.full((30, 50, 4), (50, 100, 150, 255), dtype=np.uint8)
    pixels[8:20, 10:35] = (200, 80, 60, 255)
    Image.fromarray(pixels).save(frame)
    outputs = []
    for mode in ("transparent", "solid", "original"):
        project.background.mode = mode
        result = stabilize_runner(project, action, [frame], tmp_path / mode,
                                  lambda *args: None, None)
        with Image.open(result[0]) as image:
            outputs.append(np.asarray(image))
    for output in outputs[1:]:
        np.testing.assert_array_equal(output, outputs[0])


@pytest.mark.parametrize("setting,value", [("upscale_method", "nearest"), ("palette_size", 4)])
def test_original_profile_cache_tracks_output_settings(tmp_path, setting, value):
    project = SpriteProject(name="geometry", project_dir=tmp_path)
    project.background.mode = "original"
    action = ActionCard(id="a1", name="walk", prompt="walk")
    before = stage_fingerprint(project, action, "pixel")
    setattr(project.profile("pixel"), setting, value)
    assert stage_fingerprint(project, action, "pixel") != before


def test_original_cache_tracks_anchor_and_padding(tmp_path):
    project = SpriteProject(name="geometry", project_dir=tmp_path)
    project.background.mode = "original"
    action = ActionCard(id="a1", name="walk", prompt="walk")
    before = stage_fingerprint(project, action, "stabilize")
    project.stabilize.pad_px += 5
    assert stage_fingerprint(project, action, "stabilize") != before
    before = stage_fingerprint(project, action, "hd")
    project.stabilize.anchor = "top_left"
    assert stage_fingerprint(project, action, "hd") != before
