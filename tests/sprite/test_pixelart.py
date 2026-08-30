import io
import sys
import types
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from core.sprite import pixelart
from core.sprite.pixelart import (
    anchor_offset, bayer_matrix, fit_pad_integer, integer_fit_scale,
    resolution_check, upscale_then_fit,
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


# --- Task 2 -------------------------------------------------------------------------

def test_resolution_check_none_when_source_large_enough():
    assert resolution_check((64, 64), (64, 64)) is None
    assert resolution_check((256, 256), (64, 64)) is None
    assert resolution_check((100, 40), (64, 64)) is None


def test_resolution_check_warns_when_smaller_in_both_axes():
    text = resolution_check((40, 30), (64, 64))
    assert text is not None
    assert "40x30" in text and "64x64" in text
    assert "upscale_small=True" in text
    assert "128x128" in text


def test_upscale_then_fit_upscales_small_source_proportionally(monkeypatch):
    calls = []
    install_fake_upscaler(monkeypatch, calls)
    src = square_frame((16, 8), (16, 8))
    out = upscale_then_fit(src, (64, 64), "bottom_center", method="lanczos")
    assert calls == [(64, 32, "lanczos")]
    assert out.size == (64, 64)
    arr = np.asarray(out)
    rows = np.where(arr[..., 3] > 0)[0]
    cols = np.where(arr[..., 3] > 0)[1]
    assert cols.min() == 0 and cols.max() == 63
    assert rows.max() == 63 and rows.min() == 32


def test_upscale_then_fit_is_fit_pad_when_source_large_enough():
    src = square_frame((128, 128), (128, 128))
    out = upscale_then_fit(src, (64, 64), "top_left", method="lanczos")
    assert np.array_equal(np.asarray(out), np.asarray(fit_pad_integer(src, (64, 64), "top_left")))


def test_upscale_then_fit_pads_when_upscaler_returns_original(monkeypatch):
    calls = []
    fake = types.ModuleType("core.upscaling")
    fake.upscale_image = lambda data, w, h, method="lanczos", **kw: (calls.append((w, h, method)), data)[1]
    monkeypatch.setitem(sys.modules, "core.upscaling", fake)
    src = square_frame((10, 20), (10, 20))
    out = upscale_then_fit(src, (64, 64), "center", method="lanczos")
    assert calls == [(32, 64, "lanczos")]
    assert out.size == (64, 64)
    assert opaque_pixels(out) == 10 * 20


def test_upscale_then_fit_rejects_unknown_method():
    with pytest.raises(ValueError):
        upscale_then_fit(square_frame((8, 8), (8, 8)), (64, 64), "center", method="magic")


# --- Task 3 -------------------------------------------------------------------------

def test_bayer2_values():
    m = bayer_matrix(2)
    expected = (np.array([[0, 2], [3, 1]], dtype=np.float64) + 0.5) / 4.0
    assert np.allclose(m, expected)


def test_bayer_matrices_are_permutations_with_mean_half():
    for n in (2, 4, 8):
        m = bayer_matrix(n)
        assert m.shape == (n, n)
        ranks = np.round(m * n * n - 0.5).astype(int)
        assert sorted(ranks.flatten().tolist()) == list(range(n * n))
        assert abs(m.mean() - 0.5) < 1e-12
        assert m.min() > 0.0 and m.max() < 1.0


def test_bayer4_top_left_block_is_scaled_bayer2():
    m4 = bayer_matrix(4)
    ranks = np.round(m4 * 16 - 0.5).astype(int)
    assert ranks[:2, :2].tolist() == [[0, 8], [12, 4]]


def test_bayer_rejects_other_sizes():
    for bad in (1, 3, 16):
        with pytest.raises(ValueError):
            bayer_matrix(bad)
