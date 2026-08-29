import threading
import time

import pytest
from PIL import Image

from core.sprite.extract import (
    FFmpegError,
    cull_duplicates,
    estimate_frame_count,
    extract_frames,
    probe_video,
    _run_ffmpeg,
)
from core.sprite.pipeline import CancelToken, Cancelled
from core.sprite.project import ExtractionSettings
from tests.sprite.synth import write_frames


def test_probe_reports_fps_frames_duration_and_size(synthetic_mp4):
    probe = probe_video(synthetic_mp4)
    assert probe["fps"] == pytest.approx(24.0)
    assert probe["nb_frames"] == 12
    assert probe["duration"] == pytest.approx(0.5, abs=0.05)
    assert (probe["width"], probe["height"]) == (112, 64)
    assert probe["source"] in ("ffprobe", "opencv")


def test_probe_missing_file_raises(tmp_path):
    with pytest.raises(FFmpegError):
        probe_video(tmp_path / "nope.mp4")


def test_estimate_frame_count_for_every_mode():
    probe = {"fps": 24.0, "nb_frames": 48, "duration": 2.0}
    assert estimate_frame_count(probe, ExtractionSettings(mode="every_n", every_n=8)) == 6
    assert estimate_frame_count(probe, ExtractionSettings(mode="target_fps", target_fps=12)) == 24
    assert estimate_frame_count(probe, ExtractionSettings(mode="exact_n", exact_n=8)) == 8
    assert estimate_frame_count(probe, ExtractionSettings(mode="exact_n", exact_n=99)) == 48
    trimmed = ExtractionSettings(mode="every_n", every_n=8, trim_start_s=0.5, trim_end_s=0.5)
    assert estimate_frame_count(probe, trimmed) == 3
    assert estimate_frame_count({"fps": 0, "duration": 0}, ExtractionSettings()) == 0
    with pytest.raises(ValueError):
        estimate_frame_count(probe, ExtractionSettings(mode="bogus"))


def test_extract_every_n(tmp_path, synthetic_mp4):
    result = extract_frames(synthetic_mp4, tmp_path / "out", ExtractionSettings(mode="every_n", every_n=4))
    assert [p.name for p in result.frames] == ["0001.png", "0002.png", "0003.png"]
    assert result.source_fps == pytest.approx(24.0)
    assert result.source_frames == 12
    with Image.open(result.frames[0]) as im:
        assert im.size == (112, 64)


def test_extract_target_fps(tmp_path, synthetic_mp4):
    result = extract_frames(synthetic_mp4, tmp_path / "out", ExtractionSettings(mode="target_fps", target_fps=12))
    assert len(result.frames) == 6


def test_extract_exact_n_picks_evenly_spaced_frames(tmp_path, synthetic_mp4):
    result = extract_frames(synthetic_mp4, tmp_path / "out", ExtractionSettings(mode="exact_n", exact_n=4))
    assert [p.name for p in result.frames] == ["0001.png", "0002.png", "0003.png", "0004.png"]
    # Picks are source frames 0, 4, 7, 11: the square's left edge moves 6 px per frame.
    edges = []
    for path in result.frames:
        with Image.open(path) as im:
            rgb = im.convert("RGB")
            row = [rgb.getpixel((x, 32)) for x in range(112)]
        edges.append(next(x for x, px in enumerate(row) if px[0] > 120))
    assert edges[0] < edges[1] < edges[2] < edges[3]
    assert not list((tmp_path / "out").parent.glob("extract_all_*"))


def test_extract_exact_n_of_one_keeps_the_first_frame(tmp_path, synthetic_mp4):
    result = extract_frames(synthetic_mp4, tmp_path / "out", ExtractionSettings(mode="exact_n", exact_n=1))
    assert len(result.frames) == 1


def test_extract_exact_n_above_the_frame_count_returns_every_frame(tmp_path, synthetic_mp4):
    """I3 regression: exact_n larger than the source's frame count must not
    truncate into the first half of the clip -- it should keep every frame,
    matching what estimate_frame_count already predicts (see test above,
    exact_n=99 on a 48-frame source estimates 48)."""
    result = extract_frames(synthetic_mp4, tmp_path / "out", ExtractionSettings(mode="exact_n", exact_n=99))
    assert len(result.frames) == 12
    assert [p.name for p in result.frames] == [f"{i:04d}.png" for i in range(1, 13)]
    # The square must still advance across the full clip, not just its first half.
    edges = []
    for path in result.frames:
        with Image.open(path) as im:
            rgb = im.convert("RGB")
            row = [rgb.getpixel((x, 32)) for x in range(112)]
        edges.append(next(x for x, px in enumerate(row) if px[0] > 120))
    assert edges == sorted(edges)
    assert edges[-1] - edges[0] >= 60


def test_extract_honours_trim(tmp_path, synthetic_mp4):
    settings = ExtractionSettings(mode="every_n", every_n=1, trim_start_s=0.25, trim_end_s=0.125)
    result = extract_frames(synthetic_mp4, tmp_path / "out", settings)
    assert 2 <= len(result.frames) <= 4


def test_extract_clears_stale_output(tmp_path, synthetic_mp4):
    out = tmp_path / "out"
    out.mkdir()
    (out / "9999.png").write_bytes(b"stale")
    extract_frames(synthetic_mp4, out, ExtractionSettings(mode="every_n", every_n=6))
    assert not (out / "9999.png").exists()


def test_extract_cancel(tmp_path, synthetic_mp4):
    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        extract_frames(synthetic_mp4, tmp_path / "out", ExtractionSettings(), token=token)


def test_run_ffmpeg_cancel_stops_a_running_process_promptly(tmp_path, ffmpeg_exe):
    # A slow lavfi source (20s of synthetic video) stands in for a real clip
    # long enough that the poll loop, not process completion, must be what
    # stops it. If cancellation only took effect between subprocess calls
    # (the pre-fix behaviour), this would block for the full 20s.
    # "-re" paces the lavfi source at its declared rate (real-time), so the
    # encode actually spans ~20s instead of ffmpeg draining the generator as
    # fast as it can (which finishes in well under a second and leaves
    # nothing running to cancel).
    cmd = [ffmpeg_exe, "-y", "-hide_banner", "-loglevel", "error",
           "-re", "-f", "lavfi", "-i", "testsrc=size=64x64:rate=25",
           "-t", "20", str(tmp_path / "%04d.png")]
    token = CancelToken()
    outcome = {}

    def run():
        started = time.monotonic()
        try:
            _run_ffmpeg(cmd, token)
        except Cancelled:
            outcome["cancelled"] = True
        outcome["elapsed"] = time.monotonic() - started

    thread = threading.Thread(target=run)
    thread.start()
    time.sleep(0.3)  # let ffmpeg actually start encoding
    token.cancel()
    thread.join(timeout=5)

    assert not thread.is_alive(), "cancellation did not stop the ffmpeg subprocess promptly"
    assert outcome.get("cancelled") is True
    assert outcome["elapsed"] < 5


def test_extract_bad_video_raises_ffmpeg_error(tmp_path, ffmpeg_exe):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    with pytest.raises(FFmpegError) as info:
        extract_frames(bad, tmp_path / "out", ExtractionSettings())
    assert info.value.user_message


def test_cull_duplicates_keeps_distinct_frames(tmp_path):
    frames = write_frames(tmp_path / "f", 4, alpha=False)
    dup = tmp_path / "f" / "0005.png"
    Image.open(frames[3]).save(dup)
    kept = cull_duplicates(frames + [dup], threshold=0.001)
    assert kept == frames
    assert cull_duplicates(frames, threshold=0.99) == [frames[0]]


def test_extract_with_cull_renumbers(tmp_path, synthetic_mp4):
    settings = ExtractionSettings(mode="every_n", every_n=1, cull_duplicates=True, duplicate_threshold=0.5)
    result = extract_frames(synthetic_mp4, tmp_path / "out", settings)
    assert [p.name for p in result.frames] == ["0001.png"]
