import pytest
from PIL import Image

from core.sprite.pipeline import CancelToken, Cancelled
from core.sprite.stabilize import (
    ANCHORS,
    anchor_offset,
    crop_and_pad,
    fit_size,
    has_transparency,
    solid_border_bbox,
    union_alpha_bbox,
)


def test_union_alpha_bbox_covers_every_frame(alpha_frames):
    assert union_alpha_bbox(alpha_frames) == (8, 20, 90, 24)
    assert union_alpha_bbox(alpha_frames[:1]) == (8, 20, 24, 24)


def test_solid_border_bbox_on_chroma_frames(green_frames):
    assert solid_border_bbox(green_frames) == (8, 20, 90, 24)
    assert has_transparency(green_frames[0]) is False


def test_has_transparency(alpha_frames):
    assert has_transparency(alpha_frames[0]) is True


def test_fit_size_never_distorts():
    assert fit_size((90, 24), (48, 48)) == (48, 13)
    assert fit_size((24, 24), (48, 48)) == (48, 48)
    assert fit_size((100, 50), (50, 50)) == (50, 25)


def test_fit_size_caps_the_scale_at_one_when_upscale_is_disallowed():
    """M1: OutputProfile.upscale_small=False keeps small content at its native size."""
    assert fit_size((24, 24), (48, 48), allow_upscale=False) == (24, 24)
    # Downscaling is unaffected -- the flag only caps growth, never shrinking.
    assert fit_size((90, 24), (48, 48), allow_upscale=False) == (48, 13)


@pytest.mark.parametrize("anchor,expected", [
    ("bottom_center", (12, 40)), ("center", (12, 20)), ("top_left", (0, 0)),
    ("top_center", (12, 0)), ("bottom_left", (0, 40)),
])
def test_anchor_offset(anchor, expected):
    assert anchor_offset(anchor, (40, 24), (64, 64)) == expected


def test_anchor_offset_rejects_unknown_names():
    with pytest.raises(ValueError):
        anchor_offset("upper_right", (1, 1), (2, 2))
    assert ANCHORS == ("bottom_center", "center", "top_left", "top_center", "bottom_left")


def test_crop_and_pad_scales_proportionally_and_anchors(tmp_path, alpha_frames):
    bbox = union_alpha_bbox(alpha_frames)
    out = crop_and_pad(alpha_frames, tmp_path / "cells", bbox, (64, 64), anchor="bottom_center", pad_px=0)
    assert len(out) == 12 and out[0].name == "0001.png"
    with Image.open(out[0]) as im:
        assert im.size == (64, 64)
        alpha = im.getchannel("A")
        solid = alpha.point(lambda v: 255 if v >= 128 else 0).getbbox()
        # The 90x24 crop scales by 64/90 to 64x17 and sits on the bottom edge.
        assert solid[3] == 64
        assert solid[1] >= 64 - 18
        # Frame 0 holds the square at the crop's left edge: 24 px scaled to ~17 px.
        assert solid[0] == 0
        assert 15 <= solid[2] - solid[0] <= 19
        assert alpha.getpixel((32, 2)) == 0


def test_crop_and_pad_identity_when_cell_equals_crop(tmp_path, alpha_frames):
    bbox = union_alpha_bbox(alpha_frames)
    cell = (bbox[2] + 4, bbox[3] + 4)
    out = crop_and_pad(alpha_frames, tmp_path / "cells", bbox, cell, anchor="top_left", pad_px=2)
    with Image.open(out[0]) as im, Image.open(alpha_frames[0]) as src:
        assert im.size == cell
        assert im.getpixel((2, 2)) == src.getpixel((8, 20))
        assert im.getpixel((0, 0)) == (0, 0, 0, 0)


def test_crop_and_pad_keeps_native_size_when_upscale_small_is_false(tmp_path, alpha_frames):
    """M1: a crop smaller than the cell is not enlarged when upscale_small=False."""
    bbox = (8, 20, 24, 24)  # frame 0's square, smaller than the 48x48 cell
    out = crop_and_pad([alpha_frames[0]], tmp_path / "cells", bbox, (48, 48),
                       anchor="top_left", upscale_small=False)
    with Image.open(out[0]) as im:
        assert im.size == (48, 48)
        alpha = im.getchannel("A")
        solid = alpha.point(lambda v: 255 if v >= 128 else 0).getbbox()
        assert solid == (0, 0, 24, 24)  # native size, anchored at top-left, not upscaled


def test_crop_and_pad_upscale_small_true_still_grows_with_the_default_lanczos(tmp_path, alpha_frames):
    bbox = (8, 20, 24, 24)
    out = crop_and_pad([alpha_frames[0]], tmp_path / "cells", bbox, (48, 48),
                       anchor="top_left", upscale_small=True)
    with Image.open(out[0]) as im:
        alpha = im.getchannel("A")
        solid = alpha.point(lambda v: 255 if v >= 128 else 0).getbbox()
        assert solid[2] - solid[0] == 48 and solid[3] - solid[1] == 48  # upscaled to fill the cell


def test_crop_and_pad_resample_method_is_honoured(tmp_path, alpha_frames):
    """M1: upscale_method picks the PIL resampling filter; nearest keeps hard
    edges (binary alpha) where lanczos introduces intermediate alpha values.

    The bbox pads well past the 24x24 square (frame 0's square sits at
    x=8..32, y=20..44) so the crop has a real alpha edge inside it to
    resample -- a bbox tight to the square's own bounds would leave a
    solid-alpha crop with nothing at its interior for the filters to differ on.
    """
    bbox = (0, 0, 48, 48)
    out_nearest = crop_and_pad([alpha_frames[0]], tmp_path / "nearest", bbox, (96, 96),
                               anchor="top_left", upscale_small=True, resample_method="nearest")
    out_lanczos = crop_and_pad([alpha_frames[0]], tmp_path / "lanczos", bbox, (96, 96),
                               anchor="top_left", upscale_small=True, resample_method="lanczos")
    with Image.open(out_nearest[0]) as im_near, Image.open(out_lanczos[0]) as im_lz:
        near_values = set(im_near.getchannel("A").getdata())
        lz_values = set(im_lz.getchannel("A").getdata())
        assert near_values <= {0, 255}
        assert any(0 < v < 255 for v in lz_values)


def test_crop_and_pad_cancel_and_validation(tmp_path, alpha_frames):
    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        crop_and_pad(alpha_frames, tmp_path / "c", (0, 0, 8, 8), (8, 8), token=token)
    with pytest.raises(ValueError):
        crop_and_pad(alpha_frames, tmp_path / "c", (0, 0, 8, 8), (0, 8))
    with pytest.raises(ValueError):
        crop_and_pad(alpha_frames, tmp_path / "c", (0, 0, 8, 8), (8, 8), anchor="nope")
