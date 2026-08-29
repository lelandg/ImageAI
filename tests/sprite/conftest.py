"""Fixtures for the sprite suite (design section 5).

``alpha_frames`` and ``green_frames`` are twelve synthetic PNGs per test.
``synthetic_mp4`` encodes the green frames once per session with ffmpeg
and skips every test that needs it when ffmpeg is unavailable. The repo's
``tests/conftest.py`` already sandboxes ``core.paths`` and QSettings.
"""
import subprocess
from pathlib import Path
from typing import List

import pytest

from tests.sprite.synth import FRAME_COUNT, write_frames


@pytest.fixture
def alpha_frames(tmp_path) -> List[Path]:
    return write_frames(tmp_path / "alpha", alpha=True)


@pytest.fixture
def green_frames(tmp_path) -> List[Path]:
    return write_frames(tmp_path / "green", alpha=False)


@pytest.fixture(scope="session")
def ffmpeg_exe() -> str:
    """The ffmpeg executable, or skip. Resolved lazily so the FFmpegManager
    config write lands in the sandboxed user directory, not the real one."""
    from core.video.ffmpeg_utils import get_ffmpeg_path

    path = get_ffmpeg_path()
    if not path:
        pytest.skip("ffmpeg is not available")
    return path


@pytest.fixture(scope="session")
def synthetic_mp4(tmp_path_factory, ffmpeg_exe) -> Path:
    """A 12-frame, 24 fps, 112x64 H.264 clip of the moving square on green."""
    root = tmp_path_factory.mktemp("clip")
    write_frames(root / "src", FRAME_COUNT, alpha=False)
    out = root / "clip.mp4"
    cmd = [ffmpeg_exe, "-y", "-loglevel", "error", "-framerate", "24",
           "-i", str(root / "src" / "%04d.png"), "-c:v", "libx264",
           "-pix_fmt", "yuv420p", str(out)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0 or not out.exists():
        pytest.skip(f"ffmpeg could not encode the fixture clip: {result.stderr[-300:]}")
    return out
