import io
import sys
import types
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from core.sprite import pixelart
from core.sprite.pixelart import (
    anchor_offset, fit_pad_integer, integer_fit_scale,
)


def square_frame(size, square, color=(200, 40, 40, 255), origin=(0, 0)):
    """RGBA frame of ``size`` with one opaque square of ``square`` px at ``origin``."""
    arr = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    x0, y0 = origin
    arr[y0:y0 + square[1], x0:x0 + square[0]] = color
    return Image.fromarray(arr)


def opaque_pixels(image):
    arr = np.asarray(image.convert("RGBA"))
    return int((arr[..., 3] > 0).sum())


def install_fake_upscaler(monkeypatch, calls):
    """Stand in for core.upscaling (its real import pulls torchvision, ~23 s)."""
    fake = types.ModuleType("core.upscaling")

    def upscale_image(image_data, target_width, target_height, method="lanczos", **kwargs):
        calls.append((target_width, target_height, method))
        img = Image.open(io.BytesIO(image_data))
        img.load()
        out = io.BytesIO()
        img.resize((target_width, target_height), Image.Resampling.LANCZOS).save(out, format="PNG")
        return out.getvalue()

    fake.upscale_image = upscale_image
    monkeypatch.setitem(sys.modules, "core.upscaling", fake)


# --- Task 1 -------------------------------------------------------------------------

def test_integer_fit_scale_exact_multiple():
    assert integer_fit_scale((256, 256), (64, 64)) == 4


def test_integer_fit_scale_rounds_up_to_fit():
    assert integer_fit_scale((500, 500), (64, 64)) == 8
    assert integer_fit_scale((100, 800), (64, 64)) == 13


def test_integer_fit_scale_is_one_when_source_fits():
    assert integer_fit_scale((64, 64), (64, 64)) == 1
    assert integer_fit_scale((10, 10), (64, 64)) == 1


def test_integer_fit_scale_rejects_zero():
    with pytest.raises(ValueError):
        integer_fit_scale((0, 10), (64, 64))


def test_anchor_offsets():
    assert anchor_offset((10, 20), (64, 64), "bottom_center") == (27, 44)
    assert anchor_offset((10, 20), (64, 64), "center") == (27, 22)
    assert anchor_offset((10, 20), (64, 64), "top_left") == (0, 0)
    assert anchor_offset((10, 20), (64, 64), "top_center") == (27, 0)
    assert anchor_offset((10, 20), (64, 64), "bottom_left") == (0, 44)


def test_anchor_offset_rejects_unknown_and_oversize():
    with pytest.raises(ValueError):
        anchor_offset((10, 10), (64, 64), "middle")
    with pytest.raises(ValueError):
        anchor_offset((65, 10), (64, 64), "center")


def test_fit_pad_integer_downscales_by_box_filter_and_pads():
    src = square_frame((256, 256), (128, 256), origin=(64, 0))
    out = fit_pad_integer(src, (64, 64), "bottom_center")
    assert out.size == (64, 64)
    assert out.mode == "RGBA"
    arr = np.asarray(out)
    assert arr[..., 3].sum() // 255 == 32 * 64
    assert (arr[:, 16:48, 3] == 255).all()
    assert (arr[:, :16, 3] == 0).all() and (arr[:, 48:, 3] == 0).all()


def test_fit_pad_integer_never_upscales_small_source():
    src = square_frame((16, 16), (16, 16))
    out = fit_pad_integer(src, (64, 64), "bottom_center")
    assert out.size == (64, 64)
    assert opaque_pixels(out) == 16 * 16
    arr = np.asarray(out)
    assert (arr[48:64, 24:40, 3] == 255).all()


def test_fit_pad_integer_honors_forced_scale():
    src = square_frame((64, 64), (64, 64))
    out = fit_pad_integer(src, (64, 64), "top_left", scale=2)
    assert opaque_pixels(out) == 32 * 32


def test_fit_pad_integer_box_filter_blends_alpha_edge():
    src = square_frame((8, 8), (4, 8))
    out = fit_pad_integer(src, (2, 2), "top_left")
    arr = np.asarray(out)
    assert tuple(arr[0, 0]) == (200, 40, 40, 255)
    assert tuple(arr[0, 1]) == (0, 0, 0, 0)


def test_fit_pad_integer_non_multiple_fits():
    src = square_frame((500, 300), (500, 300))
    out = fit_pad_integer(src, (64, 64), "bottom_center")
    assert out.size == (64, 64)
    assert opaque_pixels(out) == 63 * 38
