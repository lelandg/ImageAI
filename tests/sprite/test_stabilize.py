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


def test_crop_and_pad_cancel_and_validation(tmp_path, alpha_frames):
    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        crop_and_pad(alpha_frames, tmp_path / "c", (0, 0, 8, 8), (8, 8), token=token)
    with pytest.raises(ValueError):
        crop_and_pad(alpha_frames, tmp_path / "c", (0, 0, 8, 8), (0, 8))
    with pytest.raises(ValueError):
        crop_and_pad(alpha_frames, tmp_path / "c", (0, 0, 8, 8), (8, 8), anchor="nope")
