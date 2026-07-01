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
    assert str(cfg.reference_images[0]).endswith("a.png")


def test_omni_rejects_extend():
    with pytest.raises(VideoCliError, match="extend"):
        build_omni_config(_ns(extend="prev.mp4"))


def test_omni_rejects_last_frame():
    with pytest.raises(VideoCliError, match="last-frame"):
        build_omni_config(_ns(last_frame="end.png"))


def test_omni_accepts_three_refs(tmp_path):
    refs = []
    for i in range(3):
        p = tmp_path / f"r{i}.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        refs.append(str(p))
    cfg = build_omni_config(_ns(prompt="together", ref_image=refs))
    assert len(cfg.reference_images) == 3
    assert cfg.task == "reference_to_video"


def test_omni_rejects_four_refs(tmp_path):
    refs = [str(tmp_path / f"r{i}.png") for i in range(4)]
    with pytest.raises(VideoCliError, match="3"):
        build_omni_config(_ns(prompt="x", ref_image=refs))


def test_omni_delivery_uri_passthrough():
    cfg = build_omni_config(_ns(prompt="a sunset", delivery="uri"))
    assert cfg.delivery == "uri"


def test_veo_rejects_delivery():
    with pytest.raises(VideoCliError, match="omni"):
        build_veo_config(_ns(prompt="x", delivery="uri"))


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


def test_omni_refine_from_maps_to_previous_interaction():
    cfg = build_omni_config(_ns(prompt="make the violin invisible",
                                refine_from="int_abc123"))
    assert cfg.previous_interaction_id == "int_abc123"
    assert cfg.task == "edit"


def test_omni_edit_video_maps_to_input_video(tmp_path):
    vid = tmp_path / "clip.mp4"
    vid.write_bytes(b"\x00\x00\x00\x18ftypmp42fake")
    cfg = build_omni_config(_ns(prompt="ripple the mirror", edit_video=str(vid)))
    assert cfg.input_video == vid
    assert cfg.task == "edit"


def test_omni_edit_video_missing_file_errors(tmp_path):
    with pytest.raises(VideoCliError, match="not found"):
        build_omni_config(_ns(prompt="x", edit_video=str(tmp_path / "nope.mp4")))


def test_veo_rejects_refine_from():
    with pytest.raises(VideoCliError, match="omni"):
        build_veo_config(_ns(prompt="x", refine_from="int_abc"))


def test_veo_rejects_edit_video():
    with pytest.raises(VideoCliError, match="omni"):
        build_veo_config(_ns(prompt="x", edit_video="clip.mp4"))
