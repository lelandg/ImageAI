"""Tests for core/sprite/timing.py (clip-timing-hints)."""
import pytest

from core.sprite.project import ExtractionSettings
from core.sprite.timing import (
    frames_per_clip,
    legal_aspect_ratios,
    legal_durations,
    loop_seconds,
    ms_to_fps,
    snap_duration,
    suggest_clip_duration,
)

VEO_STD = "veo-3.1-generate-001"
VEO_FAST = "veo-3.1-fast-generate-001"


def test_loop_seconds():
    assert loop_seconds(8, 12) == pytest.approx(8 / 12)
    assert loop_seconds(24, 24) == 1.0


def test_loop_seconds_rejects_zero_fps():
    with pytest.raises(ValueError):
        loop_seconds(8, 0)


def test_legal_durations_per_provider():
    assert legal_durations("veo", VEO_STD) == (8,)
    assert legal_durations("veo", "") == (8,)
    assert legal_durations("veo", VEO_FAST) == (4, 6, 8)
    assert legal_durations("omni", "") == tuple(range(3, 11))
    with pytest.raises(ValueError):
        legal_durations("sora", "")


def test_legal_aspect_ratios_per_provider():
    assert legal_aspect_ratios("omni", "") == ("16:9", "9:16")
    assert "1:1" in legal_aspect_ratios("veo", "")
    assert "1:1" in legal_aspect_ratios("veo", VEO_STD)
    assert "1:1" not in legal_aspect_ratios("veo", VEO_FAST)
    assert legal_aspect_ratios("veo", "no-such-model") == legal_aspect_ratios("veo", VEO_STD)
    with pytest.raises(ValueError):
        legal_aspect_ratios("sora", "")


def test_suggest_duration_gives_at_least_two_loops():
    # 8 frames at 12 fps = 0.67 s per loop -> needs >= 1.33 s -> Omni 3 s.
    assert suggest_clip_duration(8, 12, "omni", "") == 3
    # 24 frames at 8 fps = 3 s per loop -> needs 6 s -> Omni 6 s, Veo fast 6 s.
    assert suggest_clip_duration(24, 8, "omni", "") == 6
    assert suggest_clip_duration(24, 8, "veo", VEO_FAST) == 6
    # Veo standard is always 8.
    assert suggest_clip_duration(8, 12, "veo", VEO_STD) == 8


def test_suggest_duration_caps_at_longest_legal():
    # 60 frames at 8 fps = 7.5 s per loop -> needs 15 s -> longest legal.
    assert suggest_clip_duration(60, 8, "omni", "") == 10
    assert suggest_clip_duration(60, 8, "veo", VEO_FAST) == 8


def test_snap_duration():
    assert snap_duration(5, "veo", VEO_FAST) == 6
    assert snap_duration(4, "veo", VEO_FAST) == 4
    assert snap_duration(4, "veo", VEO_STD) == 8
    assert snap_duration(4, "veo", VEO_FAST, loop_conditioning=True) == 8
    assert snap_duration(12, "omni", "") == 10
    assert snap_duration(1, "omni", "") == 3
    assert snap_duration(7, "omni", "") == 7


def test_frames_per_clip_modes():
    every = ExtractionSettings(mode="every_n", every_n=8)
    assert frames_per_clip(8.0, 24.0, every) == 24
    fps = ExtractionSettings(mode="target_fps", target_fps=12)
    assert frames_per_clip(8.0, 24.0, fps) == 96
    exact = ExtractionSettings(mode="exact_n", exact_n=10)
    assert frames_per_clip(8.0, 24.0, exact) == 10


def test_frames_per_clip_honors_trim():
    every = ExtractionSettings(mode="every_n", every_n=1, trim_start_s=1.0, trim_end_s=1.0)
    assert frames_per_clip(8.0, 24.0, every) == 144
    assert frames_per_clip(1.0, 24.0, every) == 0


def test_ms_to_fps_gcd():
    fps, mult = ms_to_fps([100, 100, 200])
    assert fps == 10
    assert mult == [1.0, 1.0, 2.0]


def test_ms_to_fps_reports_drift_in_multipliers():
    fps, mult = ms_to_fps([83, 83, 83])
    assert fps == 12
    assert all(abs(m - 1.0) < 0.01 for m in mult)
    assert mult[0] != 1.0


def test_ms_to_fps_clamps_to_60_and_handles_empty():
    fps, mult = ms_to_fps([5, 5])
    assert fps == 60
    assert ms_to_fps([]) == (12, [])
