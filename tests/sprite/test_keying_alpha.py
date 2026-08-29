# tests/sprite/test_keying_alpha.py
import numpy as np
import pytest

from core.sprite import keying
from tests.sprite.keying_fixtures import FIELD, disc_on_field


def test_hex_to_rgb_accepts_common_forms():
    assert keying.hex_to_rgb("#00FF00") == (0, 255, 0)
    assert keying.hex_to_rgb("00ff00") == (0, 255, 0)
    assert keying.hex_to_rgb("#0f0") == (0, 255, 0)
    assert keying.rgb_to_hex((0, 200, 0)) == "#00C800"


@pytest.mark.parametrize("bad", ["", "#12345", "#GGGGGG", "green"])
def test_hex_to_rgb_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        keying.hex_to_rgb(bad)


def test_field_with_luminance_gradient_keys_to_zero():
    rgb, cov = disc_on_field(gradient=True)
    alpha = keying.chroma_alpha(rgb, FIELD, tolerance=0.20, softness=0.10)
    assert alpha.dtype == np.float32
    assert alpha.shape == rgb.shape[:2]
    assert alpha[cov == 0].max() == 0.0


def test_disc_interior_is_fully_opaque():
    rgb, cov = disc_on_field()
    alpha = keying.chroma_alpha(rgb, FIELD, tolerance=0.20, softness=0.10)
    assert alpha[cov == 1].min() == 1.0


def test_wide_ramp_yields_partial_alpha_on_the_edge():
    rgb, cov = disc_on_field()
    alpha = keying.chroma_alpha(rgb, FIELD, tolerance=0.05, softness=0.80)
    edge = alpha[(cov > 0) & (cov < 1)]
    assert ((edge > 0.05) & (edge < 0.95)).any()


def test_ramp_midpoint_is_half():
    # The (Cb, Cr) distance from (220,40,40) to (0,200,0) is 0.6957 (normalized by 255).
    red = np.array([[[220, 40, 40]]], dtype=np.uint8)
    alpha = keying.chroma_alpha(red, FIELD, tolerance=0.6957 - 0.05, softness=0.10)
    assert abs(float(alpha[0, 0]) - 0.5) < 0.02


def test_brightness_offset_does_not_change_alpha():
    lifted = np.array([[[50, 250, 50]]], dtype=np.uint8)   # FIELD + 50 on every channel
    assert keying.chroma_alpha(lifted, FIELD, 0.01, 0.0)[0, 0] == 0.0
    assert keying.chroma_alpha(lifted, FIELD, 0.01, 0.05)[0, 0] == 0.0


def test_zero_softness_is_a_hard_step():
    rgb, _ = disc_on_field()
    alpha = keying.chroma_alpha(rgb, FIELD, tolerance=0.20, softness=0.0)
    assert set(np.unique(alpha).tolist()) <= {0.0, 1.0}


def test_rgba_input_ignores_the_alpha_channel():
    rgb, cov = disc_on_field()
    rgba = np.concatenate([rgb, np.full(rgb.shape[:2] + (1,), 255, np.uint8)], axis=2)
    a1 = keying.chroma_alpha(rgb, FIELD, 0.2, 0.1)
    a2 = keying.chroma_alpha(rgba, FIELD, 0.2, 0.1)
    assert (a1 == a2).all()


def test_chroma_alpha_rejects_non_image_arrays():
    with pytest.raises(ValueError):
        keying.chroma_alpha(np.zeros((4, 4), np.uint8), FIELD, 0.2, 0.1)
