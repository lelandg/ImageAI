import numpy as np
import pytest
from PIL import Image

from core.sprite import matting


def _pair(fg=(220, 40, 40), size=(32, 24), radius=8.0):
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cov = np.clip(radius + 0.5 - np.sqrt((xx - w / 2) ** 2 + (yy - h / 2) ** 2), 0, 1)
    f = np.array(fg, dtype=np.float32) / 255.0
    a = cov[:, :, None]
    on_white = a * f + (1 - a) * 1.0
    on_black = a * f
    to_img = lambda arr: Image.fromarray(np.round(arr * 255).astype(np.uint8))
    return to_img(on_white), to_img(on_black), cov, f * 255


def test_difference_matte_recovers_alpha_and_colour():
    white, black, cov, fg = _pair()
    out = np.asarray(matting.difference_matte(white, black)).astype(np.float32)
    assert out.shape == cov.shape + (4,)
    assert np.abs(out[:, :, 3] / 255.0 - cov).max() <= 2 / 255
    assert np.abs(out[cov == 1][:, :3] - fg).max() <= 2
    assert (out[cov == 0][:, 3] == 0).all()
    edge = (cov > 0.3) & (cov < 0.7)
    assert np.abs(out[edge][:, :3] - fg).max() <= 6


def test_difference_matte_returns_rgba_mode():
    white, black, _, _ = _pair()
    assert matting.difference_matte(white, black).mode == "RGBA"


def test_difference_matte_rejects_size_mismatch():
    white, black, _, _ = _pair()
    with pytest.raises(ValueError):
        matting.difference_matte(white, black.resize((8, 8)))
