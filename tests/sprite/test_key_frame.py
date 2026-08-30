# tests/sprite/test_key_frame.py
import numpy as np
import pytest
from PIL import Image

from core.sprite import keying
from core.sprite.models import FrameMeta
from core.sprite.project import KeySettings
from tests.sprite.keying_fixtures import disc_on_field, disc_rgba


def _image():
    rgb, cov = disc_on_field()
    return Image.fromarray(rgb), cov


def test_resolve_key_settings_falls_back_to_plate_color():
    s = keying.resolve_key_settings(KeySettings(), "#00C800")
    assert s.key_color == "#00C800"
    s2 = keying.resolve_key_settings(KeySettings(key_color="#FF00FF"), "#00C800")
    assert s2.key_color == "#FF00FF"


def test_apply_overrides_changes_only_known_keys(caplog):
    base = KeySettings(key_color="#00C800", tolerance=0.2, softness=0.1, choke_px=3)
    out = keying.apply_overrides(base, {"tolerance": 0.5, "softness": "0.25", "key_color": "#00FF00",
                                        "choke_px": 9, "mystery": 1})
    assert (out.tolerance, out.softness, out.key_color) == (0.5, 0.25, "#00FF00")
    assert out.choke_px == 3
    assert base.tolerance == 0.2


def test_apply_overrides_ignores_none_values():
    base = KeySettings(key_color="#00C800", tolerance=0.2)
    assert keying.apply_overrides(base, {"tolerance": None}).tolerance == 0.2


def test_apply_overrides_rejects_an_unparseable_tolerance(caplog):
    """I1 regression: a bad tolerance/softness override must raise KeyingError
    (logged, with a user_message), not a bare ValueError."""
    base = KeySettings(key_color="#00C800", tolerance=0.2)
    with caplog.at_level("ERROR"):
        with pytest.raises(keying.KeyingError) as info:
            keying.apply_overrides(base, {"tolerance": "not-a-number"}, frame_name="0003.png")
    assert info.value.user_message
    assert "0003.png" in caplog.text and "not-a-number" in caplog.text


def test_frame_overrides_reads_frame_meta():
    frames = [FrameMeta(name="a", source_path=None, frame=(0, 0, 0, 0)),
              FrameMeta(name="b", source_path=None, frame=(0, 0, 0, 0), overrides={"tolerance": 0.9})]
    assert keying.frame_overrides(frames, 0) == {}
    assert keying.frame_overrides(frames, 1) == {"tolerance": 0.9}
    assert keying.frame_overrides(frames, 7) == {}
    assert keying.frame_overrides([], 0) == {}


def test_key_frame_chroma_produces_rgba_with_keyed_field():
    img, cov = _image()
    out = keying.key_frame(img, KeySettings(key_color="#00C800"), {})
    assert out.mode == "RGBA"
    arr = np.asarray(out)
    assert arr[cov == 0][:, 3].max() == 0
    assert arr[cov == 1][:, 3].min() == 255
    assert tuple(arr[24, 32, :3]) == (220, 40, 40)


def test_key_frame_override_tolerance_keys_everything():
    img, cov = _image()
    out = np.asarray(keying.key_frame(img, KeySettings(key_color="#00C800"), {"tolerance": 0.95}))
    assert out[:, :, 3].max() == 0


def test_key_frame_without_key_color_samples_the_corner(caplog):
    img, cov = _image()
    with caplog.at_level("WARNING"):
        out = np.asarray(keying.key_frame(img, KeySettings(), {}))
    assert out[cov == 0][:, 3].max() == 0
    assert "key color" in caplog.text.lower()


def test_key_frame_none_method_keeps_existing_alpha():
    rgba = disc_rgba()
    out = np.asarray(keying.key_frame(Image.fromarray(rgba), KeySettings(method="none"), {}))
    assert (out == rgba).all()


def test_key_frame_none_method_on_rgb_is_opaque():
    img, _ = _image()
    out = np.asarray(keying.key_frame(img, KeySettings(method="none"), {}))
    assert (out[:, :, 3] == 255).all()


def test_key_frame_ml_method_dispatches_to_matting(monkeypatch):
    img, cov = _image()
    calls = []

    def fake_ml(image, backend, model, refine_edges):
        calls.append((backend, model, refine_edges))
        return cov.astype(np.float32)

    monkeypatch.setattr(keying, "_ml_alpha", fake_ml)
    settings = KeySettings(method="ml", ml_backend="rembg", ml_model="u2netp", ml_refine_edges=True)
    out = np.asarray(keying.key_frame(img, settings, {}))
    assert calls == [("rembg", "u2netp", True)]
    assert out[cov == 1][:, 3].min() == 255 and out[cov == 0][:, 3].max() == 0


def test_key_frame_rejects_unknown_method():
    img, _ = _image()
    with pytest.raises(keying.KeyingError):
        keying.key_frame(img, KeySettings(method="magic"), {})


def test_cleanup_and_decontaminate_are_applied():
    img, cov = _image()
    plain = np.asarray(keying.key_frame(img, KeySettings(key_color="#00C800", edge_decontaminate=False), {}))
    choked = np.asarray(keying.key_frame(img, KeySettings(key_color="#00C800", choke_px=2), {}))
    assert choked[:, :, 3].sum() < plain[:, :, 3].sum()
    decon = np.asarray(keying.key_frame(img, KeySettings(key_color="#00C800", tolerance=0.05, softness=0.8,
                                                         edge_decontaminate=True), {}))
    edge = (cov > 0.3) & (cov < 0.7)
    # decontaminated edge pixels lean red, not green
    assert (decon[edge][:, 0].astype(int) > decon[edge][:, 1].astype(int)).mean() > 0.9


def test_key_pass_returns_key_rgb_for_chroma_only():
    img, _ = _image()
    _rgb, _alpha, key = keying.key_pass(img, KeySettings(key_color="#00C800"), {})
    assert key == (0, 200, 0)
    _rgb, _alpha, key = keying.key_pass(img, KeySettings(method="none"), {})
    assert key is None


def test_key_pass_rejects_a_bad_key_color(caplog):
    """I1 regression: keying.py:261's hex_to_rgb call must raise KeyingError,
    named with the offending value and frame name, not a bare ValueError."""
    img, _ = _image()
    with caplog.at_level("ERROR"):
        with pytest.raises(keying.KeyingError) as info:
            keying.key_pass(img, KeySettings(key_color="not-a-color"), {}, frame_name="0007.png")
    assert info.value.user_message
    assert "0007.png" in caplog.text and "not-a-color" in caplog.text


def test_key_frame_rejects_a_bad_key_color_override():
    img, _ = _image()
    with pytest.raises(keying.KeyingError):
        keying.key_frame(img, KeySettings(key_color="#00C800"), {"key_color": "rgb(0,200,0)"})
