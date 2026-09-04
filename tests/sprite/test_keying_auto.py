"""Auto key color: keying samples the clip border when no key color is set.

The plate step asks the image model for a pure color, but the model and the
video model both drift (a requested #00FF00 came back as #89C55F on a real
project). The key must follow the clip, not the request.
"""
import numpy as np
from PIL import Image

from core.sprite import keying
from tests.sprite.keying_fixtures import disc_on_field


def _image(rgb: np.ndarray) -> Image.Image:
    return Image.fromarray(rgb)


def test_estimate_key_color_reads_a_flat_field():
    rgb, _ = disc_on_field(field=(137, 197, 95), gradient=False)
    est = keying.estimate_key_color(_image(rgb))
    assert est.color == "#89C55F"
    assert est.uniformity == 1.0


def test_estimate_key_color_ignores_luminance_gradient():
    rgb, _ = disc_on_field(field=(0, 200, 0), gradient=True)
    est = keying.estimate_key_color(_image(rgb))
    # The gradient changes luminance only; every border pixel stays within tolerance.
    assert est.uniformity == 1.0
    assert keying.key_distance(keying.hex_to_rgb(est.color), (0, 200, 0)) < 0.05


def test_estimate_key_color_reports_a_noisy_border():
    rng = np.random.default_rng(1)
    rgb = rng.integers(0, 256, size=(48, 64, 3), dtype=np.uint8)
    est = keying.estimate_key_color(_image(rgb))
    assert est.uniformity < keying.KEY_AUTO_MIN_UNIFORMITY


def test_auto_key_color_prefers_the_sampled_color_over_the_plate_request():
    rgb, _ = disc_on_field(field=(137, 197, 95), gradient=False)
    color, message, level, sampled = keying.auto_key_color(_image(rgb), "#00FF00", tolerance=0.2)
    assert color == "#89C55F" and sampled is True
    assert level == "warning"
    assert "#89C55F" in message and "#00FF00" in message


def test_auto_key_color_stays_quiet_when_the_clip_matches_the_plate():
    rgb, _ = disc_on_field(field=(0, 255, 0), gradient=False)
    color, message, level, sampled = keying.auto_key_color(_image(rgb), "#00FF00", tolerance=0.2)
    assert color == "#00FF00" and sampled is True
    assert level == "info"


def test_auto_key_color_falls_back_to_the_plate_when_the_border_is_not_one_color():
    rng = np.random.default_rng(2)
    rgb = rng.integers(0, 256, size=(48, 64, 3), dtype=np.uint8)
    color, message, level, sampled = keying.auto_key_color(_image(rgb), "#00FF00", tolerance=0.2)
    assert color == "#00FF00" and sampled is False
    assert level == "warning"
    assert "not one color" in message


def _field_with_disc(field, disc, size=(64, 48), radius=10):
    rgb, _ = disc_on_field(width=size[0], height=size[1], center=(size[0] / 2.0, size[1] / 2.0),
                           field=field, disc=disc, gradient=False, radius=radius)
    return rgb


def test_neutral_key_uses_luminance_and_keeps_grays():
    """Omni returned a white background for Rock out 2. A Cb/Cr-only key sees
    white, gray and black as one color; the neutral path adds luminance."""
    rgb = _field_with_disc(field=(255, 255, 255), disc=(128, 128, 128))
    alpha = keying.chroma_alpha(rgb, (255, 255, 255), 0.2, 0.1)
    assert alpha[0, 0] == 0.0 and alpha[-1, -1] == 0.0
    assert alpha[24, 32] == 1.0
    assert keying.is_neutral_key((255, 255, 255)) and keying.is_neutral_key((0, 0, 0))
    assert not keying.is_neutral_key((137, 197, 95))


def test_despill_is_a_no_op_for_a_neutral_key():
    rgb = _field_with_disc(field=(255, 255, 255), disc=(220, 40, 40))
    out = keying.despill(rgb, (255, 255, 255), "average")
    assert tuple(out[24, 32]) == (220, 40, 40)


def test_detect_edge_bands_finds_pillarbox_bars():
    rgb = _field_with_disc(field=(0, 200, 0), disc=(220, 40, 40), size=(96, 48))
    rgb[:, :20] = 0
    rgb[:, -20:] = 0
    top, bottom, left, right = keying.detect_edge_bands(rgb)
    assert (left, right) == (20, 20)
    assert top == 0 and bottom == 0   # the top row crosses the bars and the field: not uniform


def test_estimate_key_color_samples_inside_pillarbox_bars():
    rgb = _field_with_disc(field=(0, 200, 0), disc=(220, 40, 40), size=(96, 48))
    rgb[:, :20] = 0
    rgb[:, -20:] = 0
    est = keying.estimate_key_color(_image(rgb))
    assert est.color == "#00C800"
    assert est.bands == (0, 0, 20, 20)
    assert est.uniformity == 1.0


def test_key_frame_removes_pillarbox_bars_and_the_plate_inside_them():
    rgb = _field_with_disc(field=(0, 200, 0), disc=(220, 40, 40), size=(96, 48))
    rgb[:, :20] = 0
    rgb[:, -20:] = 0
    settings = keying.KeySettings(method="chroma", key_color="#00C800")
    out = np.asarray(keying.key_frame(_image(rgb), settings, {}))
    assert out[24, 5, 3] == 0 and out[24, 90, 3] == 0    # bars
    assert out[5, 30, 3] == 0                              # plate
    assert out[24, 48, 3] == 255                           # disc
    assert tuple(out[24, 48, :3]) == (220, 40, 40)


def test_auto_key_color_names_the_bars_it_removes():
    rgb = _field_with_disc(field=(0, 200, 0), disc=(220, 40, 40), size=(96, 48))
    rgb[:, :20] = 0
    rgb[:, -20:] = 0
    color, message, level, sampled = keying.auto_key_color(_image(rgb), "#00FF00", tolerance=0.2)
    assert color == "#00C800" and sampled
    assert "bars" in message and "20" in message


def test_muted_key_never_reaches_the_grays():
    """A muted plate (#75BB65, chroma 0.16) with the default tolerance 0.2 would
    key the subject's white beard. The clamp keeps grays opaque and the plate gone."""
    key = keying.hex_to_rgb("#75BB65")
    tol, soft, clamped = keying.effective_key_tolerance(key, 0.2, 0.1)
    assert clamped and tol + soft < keying.key_chroma(key)
    rgb = _field_with_disc(field=(118, 188, 103), disc=(192, 202, 199))
    settings = keying.KeySettings(method="chroma", key_color="#75BB65")   # tolerance 0.2 default
    out = np.asarray(keying.key_frame(_image(rgb), settings, {}))
    assert out[0, 0, 3] == 0
    assert out[24, 32, 3] == 255
    # A raw chroma_alpha with the default tolerance would key the gray disc: that is the defect.
    assert keying.chroma_alpha(rgb, key, 0.2, 0.1)[24, 32] == 0.0
    # An explicit per-frame override is honored as given.
    wide = np.asarray(keying.key_frame(_image(rgb), settings, {"tolerance": 0.95}))
    assert wide[:, :, 3].max() == 0


def test_saturated_key_keeps_the_requested_tolerance():
    key = keying.hex_to_rgb("#00FF00")
    assert keying.effective_key_tolerance(key, 0.2, 0.1) == (0.2, 0.1, False)


def test_detect_edge_bands_survives_noise_and_a_glyph_on_the_bar_edge():
    """rock_3: the right bar carried compression noise and the sound glyphs touched it,
    so three of nine frames kept an opaque black block."""
    rng = np.random.default_rng(4)
    rgb = _field_with_disc(field=(118, 188, 103), disc=(220, 40, 40), size=(128, 64))
    rgb[:, :30] = 0
    rgb[:, -30:] = 0
    noise = rng.integers(0, 24, size=(64, 30, 3), dtype=np.uint8)
    rgb[:, -30:] = noise                                   # noisy black bar
    rgb[20:26, 92:100] = (250, 250, 250)                   # a white glyph across the boundary
    assert keying.detect_edge_bands(rgb) == (0, 0, 30, 30)
    out = np.asarray(keying.key_frame(_image(rgb), keying.KeySettings(key_color="#76BC67"), {}))
    assert out[:, -30:, 3].max() == 0 and out[:, :30, 3].max() == 0
    assert out[32, 64, 3] == 255
