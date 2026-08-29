# tests/sprite/test_keying_ffmpeg.py
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core.sprite import keying
from core.video.ffmpeg_utils import get_ffmpeg_path, is_ffmpeg_available
from tests.sprite.keying_fixtures import disc_on_field

needs_ffmpeg = pytest.mark.skipif(not is_ffmpeg_available(), reason="ffmpeg not available")


def _synthetic_clip(tmp_path: Path) -> Path:
    frames = tmp_path / "frames"
    frames.mkdir()
    for i in range(6):
        rgb = np.zeros((48, 64, 3), dtype=np.uint8)
        rgb[:, :, 1] = 255
        rgb[16:32, 20 + i:36 + i] = (220, 40, 40)
        Image.fromarray(rgb).save(frames / f"{i + 1:04d}.png")
    clip = tmp_path / "src.mp4"
    subprocess.run([get_ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-framerate", "12",
                    "-i", str(frames / "%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)],
                   check=True, capture_output=True, text=True)
    return clip


def _first_frame(video: Path, out_png: Path) -> np.ndarray:
    subprocess.run([get_ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
                    "-frames:v", "1", str(out_png)], check=True, capture_output=True, text=True)
    return np.asarray(Image.open(out_png).convert("RGB"))


@needs_ffmpeg
def test_preview_keys_green_to_grey_and_keeps_the_subject(tmp_path):
    clip = _synthetic_clip(tmp_path)
    out = keying.ffmpeg_chromakey_preview(clip, tmp_path / "preview.mp4", "#00FF00", 0.30, 0.10)
    assert out.exists() and out.stat().st_size > 0
    px = _first_frame(out, tmp_path / "first.png")
    corner = px[2, 2].astype(int)
    center = px[24, 28].astype(int)
    assert abs(corner[0] - corner[1]) < 20 and abs(corner[1] - corner[2]) < 20   # grey
    assert center[0] > 150 and center[1] < 100                                   # red survives


@needs_ffmpeg
def test_preview_failure_raises_keying_error_with_message(tmp_path, caplog):
    with caplog.at_level("ERROR"):
        with pytest.raises(keying.KeyingError) as info:
            keying.ffmpeg_chromakey_preview(tmp_path / "missing.mp4", tmp_path / "out.mp4", "#00FF00", 0.3, 0.1)
    assert info.value.user_message
    assert "chromakey preview" in caplog.text.lower()


def test_preview_without_ffmpeg_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(keying, "get_ffmpeg_path", lambda: None)
    with pytest.raises(keying.KeyingError):
        keying.ffmpeg_chromakey_preview(tmp_path / "a.mp4", tmp_path / "b.mp4", "#00FF00", 0.3, 0.1)


def test_pick_key_color_averages_a_window():
    rgb, _ = disc_on_field(gradient=False)
    img = Image.fromarray(rgb)
    assert keying.pick_key_color(img, (2, 2)) == "#00C800"
    assert keying.pick_key_color(img, (32, 24), radius=0) == "#DC2828"
    assert keying.pick_key_color(img, (0, 0), radius=5) == "#00C800"     # window clipped at the border


def test_pick_key_color_rejects_points_outside_the_image():
    rgb, _ = disc_on_field()
    with pytest.raises(ValueError):
        keying.pick_key_color(Image.fromarray(rgb), (999, 0))
