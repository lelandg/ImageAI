import numpy as np
from PIL import Image

from core.sprite import keying
from core.sprite.project import OutputProfile
from tests.sprite.keying_fixtures import disc_rgba


def _square_with_speck():
    a = np.zeros((32, 32), dtype=np.float32)
    a[8:24, 8:24] = 1.0
    a[2, 2] = 1.0
    return a


def test_choke_erodes_the_mask():
    a = _square_with_speck()
    out = keying.choke_feather(a, choke_px=2, feather_px=0, despeckle_px=0)
    assert out.dtype == np.float32
    assert out.sum() < a.sum()
    assert out[16, 16] == 1.0 and out[8, 8] == 0.0


def test_negative_choke_spreads_the_mask():
    a = _square_with_speck()
    out = keying.choke_feather(a, choke_px=-2, feather_px=0, despeckle_px=0)
    assert out.sum() > a.sum()


def test_feather_softens_the_edge():
    a = _square_with_speck()
    out = keying.choke_feather(a, choke_px=0, feather_px=2, despeckle_px=0)
    assert out.max() <= 1.0 and out.min() >= 0.0
    assert ((out > 0.05) & (out < 0.95)).any()


def test_despeckle_removes_islands_smaller_than_the_kernel():
    a = _square_with_speck()
    out = keying.choke_feather(a, choke_px=0, feather_px=0, despeckle_px=1)
    assert out[2, 2] == 0.0 and out[16, 16] == 1.0


def test_zero_settings_return_the_input_values():
    a = _square_with_speck()
    out = keying.choke_feather(a, 0, 0, 0)
    assert (out == a).all()


def test_binary_alpha_thresholds_on_255_scale():
    a = np.array([[0.0, 0.4, 0.5, 0.6, 1.0]], dtype=np.float32)
    out = keying.binary_alpha(a, threshold=128)
    assert out.dtype == np.float32
    assert out.tolist() == [[0.0, 0.0, 0.0, 1.0, 1.0]]     # 0.5*255 = 127.5 < 128
    assert keying.binary_alpha(a, threshold=100).tolist() == [[0.0, 1.0, 1.0, 1.0, 1.0]]


def test_binary_alpha_accepts_uint8():
    a = np.array([[0, 100, 128, 255]], dtype=np.uint8)
    assert keying.binary_alpha(a, 128).tolist() == [[0.0, 0.0, 1.0, 1.0]]


def test_binary_alpha_defringe_erodes():
    a = np.zeros((16, 16), dtype=np.float32)
    a[4:12, 4:12] = 1.0
    out = keying.binary_alpha(a, 128, defringe_px=1)
    assert out.sum() < a.sum() and out[8, 8] == 1.0
    assert set(np.unique(out).tolist()) <= {0.0, 1.0}


def test_compose_and_split_round_trip():
    rgba = disc_rgba()
    rgb, alpha = keying.split_rgba(Image.fromarray(rgba))
    assert rgb.dtype == np.uint8 and alpha.dtype == np.float32
    back = np.asarray(keying.compose_rgba(rgb, alpha))
    assert (back == rgba).all()


def test_split_rgba_of_an_rgb_image_is_opaque():
    img = Image.new("RGB", (4, 3), (10, 20, 30))
    _rgb, alpha = keying.split_rgba(img)
    assert (alpha == 1.0).all()


def test_hd_profile_keeps_soft_alpha_by_default():
    img = Image.fromarray(disc_rgba())
    hd = OutputProfile(name="hd")
    out = np.asarray(keying.apply_profile_alpha(img, hd))
    values = set(np.unique(out[:, :, 3]).tolist())
    assert values - {0, 255}, "soft edge values must survive"
    assert (out == np.asarray(img)).all()


def test_profile_binary_alpha_binarizes_and_keeps_colour():
    img = Image.fromarray(disc_rgba())
    prof = OutputProfile(name="hd", binary_alpha=True, alpha_threshold=128, defringe_px=0)
    out = np.asarray(keying.apply_profile_alpha(img, prof))
    assert set(np.unique(out[:, :, 3]).tolist()) <= {0, 255}
    assert tuple(out[24, 32, :3]) == (220, 40, 40)
