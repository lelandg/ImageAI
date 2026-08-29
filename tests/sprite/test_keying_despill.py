# tests/sprite/test_keying_despill.py
import numpy as np
import pytest

from core.sprite import keying

Y = np.array([0.299, 0.587, 0.114], dtype=np.float32)
KEY = (0, 255, 0)
SPILLED = np.array([[[120, 200, 110]]], dtype=np.uint8)   # green spill on a grey-ish pixel
RED = np.array([[[220, 40, 40]]], dtype=np.uint8)


@pytest.mark.parametrize("mode", ["average", "double", "limit"])
def test_despill_removes_the_green_excess(mode):
    out = keying.despill(SPILLED, KEY, mode)
    assert out.dtype == np.uint8
    r, g, b = (int(v) for v in out[0, 0])
    assert g <= max(r, b) + 1


@pytest.mark.parametrize("mode", ["average", "double", "limit"])
def test_despill_restores_luminance(mode):
    y_before = float(SPILLED[0, 0].astype(np.float32) @ Y)
    out = keying.despill(SPILLED, KEY, mode)
    y_after = float(out[0, 0].astype(np.float32) @ Y)
    assert abs(y_before - y_after) < 1.5


def test_despill_leaves_unspilled_pixels_alone():
    assert (keying.despill(RED, KEY, "average") == RED).all()
    assert (keying.despill(SPILLED, KEY, "none") == SPILLED).all()


def test_despill_rejects_unknown_mode():
    with pytest.raises(ValueError):
        keying.despill(SPILLED, KEY, "bogus")


def test_despill_limit_is_stronger_than_average():
    avg = int(keying.despill(SPILLED, KEY, "average")[0, 0, 1])
    lim = int(keying.despill(SPILLED, KEY, "limit")[0, 0, 1])
    assert lim >= avg


def test_decontaminate_recovers_the_foreground_colour():
    fg = np.array([220, 40, 40], dtype=np.float32)
    key = np.array([0, 200, 0], dtype=np.float32)
    a = 0.4
    mixed = np.round(a * fg + (1 - a) * key).astype(np.uint8).reshape(1, 1, 3)
    alpha = np.array([[a]], dtype=np.float32)
    out = keying.decontaminate_edges(mixed, alpha, (0, 200, 0))
    assert out.dtype == np.uint8
    assert np.abs(out[0, 0].astype(np.float32) - fg).max() <= 3


def test_decontaminate_leaves_opaque_and_transparent_pixels_alone():
    mixed = np.array([[[88, 136, 16]]], dtype=np.uint8)
    for a in (0.0, 1.0):
        alpha = np.array([[a]], dtype=np.float32)
        assert (keying.decontaminate_edges(mixed, alpha, (0, 200, 0)) == mixed).all()


def test_decontaminate_clamps_to_uint8_range():
    dark = np.array([[[0, 0, 0]]], dtype=np.uint8)
    alpha = np.array([[0.1]], dtype=np.float32)
    out = keying.decontaminate_edges(dark, alpha, (0, 255, 0))
    assert out.min() >= 0 and out.max() <= 255
