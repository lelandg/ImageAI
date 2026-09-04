# tests/sprite/test_dejitter.py
from pathlib import Path
from unittest import mock

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


def test_estimate_shift_ignores_a_uniformly_opaque_mask():
    """I3 regression: skimage's phase path found a spurious ~0.7 px shift
    between two identical constant (structure-less) masks instead of (0, 0)."""
    ones = np.ones((48, 64), dtype=np.float32)
    assert stabilize.estimate_shift(ones, ones, "phase") == (0.0, 0.0)


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


def _uniform_rgba(width: int = 64, height: int = 48, alpha: int = 255,
                  color=(220, 40, 40)) -> np.ndarray:
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[:, :, 0], rgba[:, :, 1], rgba[:, :, 2] = color
    rgba[:, :, 3] = alpha
    return rgba


def test_dejitter_leaves_uniformly_opaque_frames_untouched(tmp_path):
    """I3 end-to-end regression, inside a multi-frame ``dejitter`` call: a
    key.method="none" sequence (no keying, alpha uniformly opaque) must not
    pick up a spurious sub-pixel resampling blur from the constant mask."""
    paths = [write_png(tmp_path / "in" / f"{i + 1:04d}.png", _uniform_rgba(color=(220 - i, 40, 40)))
             for i in range(4)]
    out = stabilize.dejitter(paths, tmp_path / "out", "phase")
    for src, dst in zip(paths, out):
        before = np.asarray(Image.open(src))
        after = np.asarray(Image.open(dst))
        assert (before == after).all(), dst.name


def test_dejitter_all_transparent_frames_do_not_raise(tmp_path):
    """Deferred minor 12 / T8: an all-transparent sequence inside a multi-frame
    ``dejitter`` call must not raise and must leave every frame unchanged."""
    paths = [write_png(tmp_path / "in" / f"{i + 1:04d}.png", _uniform_rgba(alpha=0, color=(0, 0, 0)))
             for i in range(3)]
    out = stabilize.dejitter(paths, tmp_path / "out", "phase")
    for src, dst in zip(paths, out):
        before = np.asarray(Image.open(src))
        after = np.asarray(Image.open(dst))
        assert (before == after).all(), dst.name


def test_dejitter_streams_frames_reading_and_writing_interleaved(tmp_path):
    """I2 regression: each frame is opened and written before the next frame
    is opened. The old implementation read every frame into a list first and
    only then wrote any of them, which would show up here as every "open"
    event before any "save" event instead of interleaved pairs."""
    paths = _write_sequence(tmp_path, [(32.0, 24.0), (35.0, 22.0), (30.5, 25.0)])
    events = []
    real_open = Image.open
    real_save = Image.Image.save

    def counting_open(path, *a, **kw):
        events.append(("open", Path(path).name))
        return real_open(path, *a, **kw)

    def counting_save(self, fp, *a, **kw):
        events.append(("save", Path(fp).name))
        return real_save(self, fp, *a, **kw)

    with mock.patch.object(Image, "open", side_effect=counting_open), \
         mock.patch.object(Image.Image, "save", counting_save):
        out = stabilize.dejitter(paths, tmp_path / "out", "centroid")
    names = [p.name for p in paths]
    assert events == [ev for name in names for ev in (("open", name), ("save", name))]
    assert len(out) == 3


def test_requirements_declare_the_dejitter_deps():
    text = (REPO / "requirements.txt").read_text(encoding="utf-8")
    names = {line.split("#")[0].strip().split(">=")[0].lower() for line in text.splitlines()
             if line.strip() and not line.startswith("#")}
    assert {"scikit-image", "scipy"} <= names


# --- content-loss guard -----------------------------------------------------------------
# A stabilize crop is the union alpha bbox with pad_px 0 by default, so subject pixels sit
# on the canvas edge. A registration shift must never push those pixels off the canvas: on
# pose animation the estimate is wrong anyway (rock_3 frame 7 lost 20 % of the character).

def _disc_with_edge_dot(center, dot_x0: int, dot_x1: int) -> np.ndarray:
    rgba = disc_rgba(center=center)
    rgba[22:26, dot_x0:dot_x1, :3] = (220, 40, 40)
    rgba[22:26, dot_x0:dot_x1, 3] = 255
    return rgba


def test_limit_shift_to_canvas_keeps_the_alpha_bbox_inside():
    alpha = _alpha(_disc_with_edge_dot((10.0, 24.0), 58, 60))      # bbox right edge = 60 of 64
    assert stabilize.limit_shift_to_canvas(alpha, 0.0, 16.0) == (0.0, 4.0)
    assert stabilize.limit_shift_to_canvas(alpha, 0.0, -30.0) == (0.0, 0.0)   # disc touches x=0
    assert stabilize.limit_shift_to_canvas(alpha, -3.0, 2.0) == (-3.0, 2.0)   # fits: unchanged


def test_dejitter_refuses_a_shift_that_would_push_the_subject_off_the_canvas(tmp_path, caplog):
    ref = _disc_with_edge_dot((40.0, 24.0), 62, 64)
    mov = _disc_with_edge_dot((10.0, 24.0), 62, 64)                # dot already on the edge
    paths = [write_png(tmp_path / "in" / "0001.png", ref), write_png(tmp_path / "in" / "0002.png", mov)]
    with caplog.at_level("WARNING"):
        out = stabilize.dejitter(paths, tmp_path / "out", "centroid")
    got = _alpha(np.asarray(Image.open(out[1])))
    assert abs(float(got.sum()) - float(_alpha(mov).sum())) < 1e-3   # every subject pixel kept
    c_in, c_out = centroid(_alpha(mov)), centroid(got)
    assert abs(c_out[1] - c_in[1]) < 0.3 and abs(c_out[0] - c_in[0]) < 0.3
    assert "canvas" in caplog.text.lower()


def test_dejitter_limits_a_shift_to_what_the_canvas_can_hold(tmp_path, caplog):
    ref = _disc_with_edge_dot((40.0, 24.0), 58, 60)
    mov = _disc_with_edge_dot((10.0, 24.0), 58, 60)                # 4 px of room on the right
    paths = [write_png(tmp_path / "in" / "0001.png", ref), write_png(tmp_path / "in" / "0002.png", mov)]
    with caplog.at_level("WARNING"):
        out = stabilize.dejitter(paths, tmp_path / "out", "centroid")
    got = _alpha(np.asarray(Image.open(out[1])))
    assert abs(float(got.sum()) - float(_alpha(mov).sum())) < 0.01 * float(_alpha(mov).sum())
    c_in, c_out = centroid(_alpha(mov)), centroid(got)
    assert abs((c_out[1] - c_in[1]) - 4.0) < 0.3 and abs(c_out[0] - c_in[0]) < 0.3
    assert "canvas" in caplog.text.lower()
