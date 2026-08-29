"""Tests for core/sprite/generation/video_route.py (video-route-rendering)."""
from pathlib import Path

import pytest

from core.sprite.generation.errors import ProviderError
from core.sprite.generation.prompts import CHROMA_SUFFIX, LOOP_SUFFIX
from core.sprite.generation.video_route import (
    RenderRequest,
    build_omni_config,
    build_veo_config,
)
from core.sprite.project import GenerationSettings
from core.video.veo_client import VeoModel

VEO_STD = VeoModel.VEO_3_1_GENERATE.value
VEO_FAST = VeoModel.VEO_3_1_FAST.value


@pytest.fixture
def request_for(png_file, make_action, tmp_path):
    def _make(provider="omni", refs=2, **settings):
        plate = png_file("plate.png", color=(0, 255, 0, 255))
        ref_paths = [png_file(f"ref{i}.png") for i in range(refs)]
        gen = GenerationSettings(provider=provider, **settings)
        return RenderRequest(action=make_action(), plate=plate, refs=ref_paths,
                             settings=gen, out_mp4=tmp_path / "clips" / "a1.mp4")
    return _make


# --- Omni ---------------------------------------------------------------------

def test_omni_config_prompt_refs_and_aspect(request_for):
    req = request_for("omni", refs=1, aspect_ratio="9:16")
    cfg = build_omni_config(req)
    assert cfg.aspect_ratio == "9:16"
    assert cfg.reference_images[0] == req.plate
    assert cfg.reference_images[1:] == req.refs
    assert cfg.task == "reference_to_video"
    assert CHROMA_SUFFIX.format(color_name="green", hex="#00FF00") in cfg.prompt
    assert LOOP_SUFFIX in cfg.prompt
    assert "4 seconds" in cfg.prompt
    assert "9:16" not in cfg.prompt and "transparent" not in cfg.prompt.lower()


def test_omni_config_caps_reference_images_at_three(request_for):
    req = request_for("omni", refs=4)
    cfg = build_omni_config(req)
    assert len(cfg.reference_images) == 3
    assert cfg.reference_images[0] == req.plate


def test_omni_config_uses_settings_model_and_no_loop_suffix(request_for, make_action):
    req = request_for("omni", refs=0, model="omni-custom")
    req.action = make_action(loop=False, duration_s=12)
    cfg = build_omni_config(req)
    assert cfg.model == "omni-custom"
    assert cfg.task == "image_to_video"
    assert LOOP_SUFFIX not in cfg.prompt
    assert "10 seconds" in cfg.prompt   # snapped to the Omni maximum


def test_omni_config_rejects_unsupported_aspect(request_for):
    req = request_for("omni", aspect_ratio="4:3")
    with pytest.raises(ProviderError, match="aspect"):
        build_omni_config(req)


# --- Veo ----------------------------------------------------------------------

def test_veo_config_loop_conditioning_forces_first_last_and_8s(request_for):
    seen = []
    req = request_for("veo", model=VEO_FAST, duration_s=4, loop_conditioning=True,
                      include_audio=False, resolution="720p")
    cfg = build_veo_config(req, log=seen.append)
    assert cfg.model == VeoModel.VEO_3_1_FAST
    assert cfg.image == req.plate and cfg.last_frame == req.plate
    assert cfg.duration == 8
    assert cfg.include_audio is False
    assert cfg.reference_images == req.refs
    assert any("8" in line and "loop" in line.lower() for line in seen)


def test_veo_config_without_loop_conditioning_snaps_duration(request_for, make_action):
    req = request_for("veo", model=VEO_FAST, loop_conditioning=False, resolution="720p")
    req.action = make_action(duration_s=5)
    cfg = build_veo_config(req)
    assert cfg.image is None and cfg.last_frame is None
    assert cfg.duration == 6


def test_veo_config_default_model_and_resolution_fallback(request_for):
    req = request_for("veo", model="", resolution="1080p", loop_conditioning=False)
    cfg = build_veo_config(req)
    assert cfg.model == VeoModel.VEO_3_1_GENERATE
    assert cfg.duration == 8 and cfg.resolution == "1080p"
    fast = request_for("veo", model=VEO_FAST, resolution="1080p", loop_conditioning=False)
    cfg_fast = build_veo_config(fast)
    assert cfg_fast.resolution == "720p"     # Fast is 720p only; snapped with a log line


def test_veo_config_rejects_unknown_model(request_for):
    req = request_for("veo", model="veo-9-imaginary")
    with pytest.raises(ProviderError, match="Unknown Veo model"):
        build_veo_config(req)


def test_veo_config_prompt_has_chroma_and_no_sizes(request_for):
    cfg = build_veo_config(request_for("veo", model=VEO_STD, resolution="1080p"))
    assert CHROMA_SUFFIX.format(color_name="green", hex="#00FF00") in cfg.prompt
    assert "16:9" not in cfg.prompt and "px" not in cfg.prompt.lower()
