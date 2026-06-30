from argparse import Namespace
import pytest
from cli.commands.video import build_omni_config, build_veo_config, VideoCliError


def _ns(**kw):
    base = dict(prompt="p", aspect=None, ref_image=None, last_frame=None,
                extend=None, video_model=None)
    base.update(kw)
    return Namespace(**base)


def test_omni_text_to_video():
    cfg = build_omni_config(_ns())
    assert cfg.task == "text_to_video"
    assert cfg.reference_image is None


def test_omni_single_ref_is_image_to_video():
    cfg = build_omni_config(_ns(ref_image=["a.png"]))
    assert cfg.task == "image_to_video"
    assert str(cfg.reference_image).endswith("a.png")


def test_omni_rejects_extend():
    with pytest.raises(VideoCliError, match="extend"):
        build_omni_config(_ns(extend="prev.mp4"))


def test_omni_rejects_last_frame():
    with pytest.raises(VideoCliError, match="last-frame"):
        build_omni_config(_ns(last_frame="end.png"))


def test_omni_rejects_two_refs():
    with pytest.raises(VideoCliError, match="1 reference"):
        build_omni_config(_ns(ref_image=["a.png", "b.png"]))


def test_veo_accepts_three_refs():
    cfg = build_veo_config(_ns(ref_image=["a.png", "b.png", "c.png"]))
    assert len(cfg.reference_images) == 3


def test_veo_rejects_four_refs():
    with pytest.raises(VideoCliError, match="up to 3"):
        build_veo_config(_ns(ref_image=["a", "b", "c", "d"]))


def test_veo_unknown_model_errors():
    with pytest.raises(VideoCliError, match="Unknown Veo model"):
        build_veo_config(_ns(video_model="not-a-model"))


def test_veo_default_model():
    from core.video.veo_client import VeoModel
    cfg = build_veo_config(_ns())
    assert cfg.model == VeoModel.VEO_3_1_GENERATE
