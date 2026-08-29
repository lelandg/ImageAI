# tests/sprite/test_dejitter.py
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core.sprite import stabilize
from core.sprite.pipeline import CancelToken, Cancelled
from tests.sprite.keying_fixtures import centroid, disc_rgba, write_png

REPO = Path(__file__).resolve().parents[2]


def _alpha(rgba: np.ndarray) -> np.ndarray:
    return rgba[:, :, 3].astype(np.float32) / 255.0


def _write_sequence(tmp_path: Path, centers) -> list:
    paths = []
    for i, c in enumerate(centers):
        paths.append(write_png(tmp_path / "in" / f"{i + 1:04d}.png", disc_rgba(center=c)))
    return paths


@pytest.mark.parametrize("method", ["phase", "centroid"])
def test_estimate_shift_recovers_an_integer_offset(method):
    ref = _alpha(disc_rgba(center=(32.0, 24.0)))
    mov = _alpha(disc_rgba(center=(35.0, 22.0)))       # moved +3 x, -2 y
    dy, dx = stabilize.estimate_shift(ref, mov, method)
    assert abs(dy - 2.0) < 0.6 and abs(dx + 3.0) < 0.6


def test_estimate_shift_opencv_fallback_has_the_right_sign(monkeypatch):
    monkeypatch.setattr(stabilize, "_phase_cross_correlation", None)
    ref = _alpha(disc_rgba(center=(32.0, 24.0)))
    mov = _alpha(disc_rgba(center=(35.0, 22.0)))
    dy, dx = stabilize.estimate_shift(ref, mov, "phase")
    assert abs(dy - 2.0) < 0.6 and abs(dx + 3.0) < 0.6


def test_estimate_shift_falls_back_to_centroid_on_weak_response(monkeypatch):
    monkeypatch.setattr(stabilize, "_phase_cross_correlation", None)
    monkeypatch.setattr(stabilize.cv2, "phaseCorrelate", lambda a, b: ((99.0, 99.0), 0.0))
    ref = _alpha(disc_rgba(center=(32.0, 24.0)))
    mov = _alpha(disc_rgba(center=(35.0, 22.0)))
    dy, dx = stabilize.estimate_shift(ref, mov, "phase")
    assert abs(dy - 2.0) < 0.2 and abs(dx + 3.0) < 0.2


def test_estimate_shift_rejects_unknown_method():
    a = _alpha(disc_rgba())
    with pytest.raises(ValueError):
        stabilize.estimate_shift(a, a, "magic")


def test_empty_masks_give_zero_shift():
    empty = np.zeros((48, 64), dtype=np.float32)
    assert stabilize.estimate_shift(empty, empty, "centroid") == (0.0, 0.0)


def test_translate_rgba_keeps_colour_and_moves_subpixel():
    src = disc_rgba(center=(33.5, 24.0))
    out = stabilize.translate_rgba(src, 0.0, -1.5)
    c = centroid(_alpha(out))
    assert abs(c[1] - 32.0) < 0.3 and abs(c[0] - 24.0) < 0.3
    assert tuple(out[24, 32, :3]) == (220, 40, 40)
    assert out.dtype == np.uint8 and out.shape == src.shape


@pytest.mark.parametrize("method", ["phase", "centroid"])
def test_dejitter_aligns_every_frame_to_the_first(tmp_path, method):
    paths = _write_sequence(tmp_path, [(32.0, 24.0), (35.0, 22.0), (30.5, 25.0), (33.0, 26.5)])
    out = stabilize.dejitter(paths, tmp_path / "out", method)
    assert [p.name for p in out] == [p.name for p in paths]
    ref = centroid(_alpha(np.asarray(Image.open(out[0]))))
    for p in out[1:]:
        c = centroid(_alpha(np.asarray(Image.open(p))))
        assert abs(c[0] - ref[0]) < 0.6 and abs(c[1] - ref[1]) < 0.6, p.name


def test_dejitter_in_place_is_safe(tmp_path):
    paths = _write_sequence(tmp_path, [(32.0, 24.0), (36.0, 24.0)])
    out = stabilize.dejitter(paths, tmp_path / "in", "centroid")
    assert out[1] == paths[1]
    c = centroid(_alpha(np.asarray(Image.open(out[1]))))
    assert abs(c[1] - 32.0) < 0.6


def test_dejitter_clamps_wild_shifts(tmp_path, caplog):
    paths = _write_sequence(tmp_path, [(10.0, 24.0), (60.0, 24.0)])   # 50 px on a 64 px frame
    with caplog.at_level("WARNING"):
        out = stabilize.dejitter(paths, tmp_path / "out", "centroid")
    c = centroid(_alpha(np.asarray(Image.open(out[1]))))
    assert c[1] > 40.0                      # moved by at most 25 % of the width (16 px)
    assert "clamp" in caplog.text.lower()


def test_dejitter_reports_progress_and_honours_cancel(tmp_path):
    paths = _write_sequence(tmp_path, [(32.0, 24.0), (33.0, 24.0), (34.0, 24.0)])
    seen = []
    stabilize.dejitter(paths, tmp_path / "out", "centroid",
                       progress=lambda stage, done, total, msg: seen.append((stage, done, total)))
    assert seen[-1] == ("stabilize", 3, 3)
    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        stabilize.dejitter(paths, tmp_path / "out2", "centroid", token=token)


def test_requirements_declare_the_dejitter_deps():
    text = (REPO / "requirements.txt").read_text(encoding="utf-8")
    names = {line.split("#")[0].strip().split(">=")[0].lower() for line in text.splitlines()
             if line.strip() and not line.startswith("#")}
    assert {"scikit-image", "scipy"} <= names
