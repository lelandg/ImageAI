from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest

from core.sprite.models import TagMeta
from gui.sprite.preview_player import (MODES, PreviewPlayer, loop_seam_score, next_index,
                                       seam_level)
from gui_synthetic import make_frames


def test_next_index_modes():
    assert next_index(2, 0, 3, "forward", 1) == (3, 1)
    assert next_index(3, 0, 3, "forward", 1) == (0, 1)
    assert next_index(0, 0, 3, "reverse", -1) == (3, -1)
    assert next_index(2, 0, 3, "pingpong", 1) == (3, 1)
    assert next_index(3, 0, 3, "pingpong", 1) == (2, -1)
    assert next_index(0, 0, 3, "pingpong", -1) == (1, 1)
    assert next_index(0, 0, 0, "forward", 1) == (0, 1)


def test_loop_seam_score_zero_for_identical_and_positive_for_different(qapp):
    a = QImage(4, 4, QImage.Format_RGBA8888)
    a.fill(QColor(255, 0, 0, 255))
    b = QImage(a)
    assert loop_seam_score(a, b) == 0.0
    b.setPixelColor(0, 0, QColor(0, 0, 255, 255))
    score = loop_seam_score(a, b)
    assert 0.0 < score < 0.1
    assert seam_level(0.0) == "good"
    assert seam_level(0.05) == "warn"
    assert seam_level(0.5) == "bad"


def test_set_frames_shows_first_and_reports_seam(qapp, tmp_path):
    player = PreviewPlayer()
    frames = make_frames(tmp_path, 4)
    player.set_frames(frames)
    assert player.current_index() == 0
    assert player.view.image() is not None
    assert 0.0 < player.seam_score() < 0.1
    assert "12" in player.fps_readout() or "10" in player.fps_readout()  # 100 ms → 10.0 fps
    assert player.slider.maximum() == 3


def test_step_and_bounds(qapp, tmp_path):
    player = PreviewPlayer()
    player.set_frames(make_frames(tmp_path, 3))
    seen = []
    player.frameChanged.connect(seen.append)
    player.step_forward()
    player.step_forward()
    player.step_forward()  # wraps
    assert seen == [1, 2, 0]
    player.last()
    assert player.current_index() == 2
    player.first()
    assert player.current_index() == 0
    player.step_back()
    assert player.current_index() == 2


def test_tags_restrict_range_and_set_mode(qapp, tmp_path):
    player = PreviewPlayer()
    player.set_frames(make_frames(tmp_path, 6))
    player.set_tags([TagMeta(name="idle", from_index=0, to_index=1),
                     TagMeta(name="walk", from_index=2, to_index=5, direction="pingpong")])
    player.tag_combo.setCurrentIndex(2)  # 0 = All frames
    assert player.active_range() == (2, 5)
    assert player.current_index() == 2
    assert player.mode() == "pingpong"
    player.step_back()
    assert player.current_index() == 5  # wraps inside the tag range


def test_cycle_mode_order(qapp):
    player = PreviewPlayer()
    got = []
    player.modeChanged.connect(got.append)
    assert player.mode() == MODES[0]
    assert player.cycle_mode() == "reverse"
    assert player.cycle_mode() == "pingpong"
    assert player.cycle_mode() == "forward"
    assert got == ["reverse", "pingpong", "forward"]


def test_timer_playback_honors_duration(qapp, tmp_path):
    player = PreviewPlayer()
    player.set_frames(make_frames(tmp_path, 4, duration_ms=5))
    seen = []
    player.frameChanged.connect(seen.append)
    states = []
    player.playingChanged.connect(states.append)
    player.play()
    assert player.is_playing()
    QTest.qWait(150)
    player.pause()
    assert not player.is_playing()
    assert len(seen) >= 3
    assert states == [True, False]
    count_before = len(seen)
    QTest.qWait(40)
    assert len(seen) == count_before  # timer stopped


def test_sources_combo_emits(qapp):
    player = PreviewPlayer()
    got = []
    player.sourceChanged.connect(got.append)
    player.set_sources(["cells", "hd", "pixel"])
    assert player.source() == "cells"
    player.source_combo.setCurrentIndex(1)
    assert got == ["hd"]
    assert player.source() == "hd"


def test_empty_frames_are_safe(qapp):
    player = PreviewPlayer()
    player.set_frames([])
    player.play()
    player.step_forward()
    player.last()
    assert player.current_index() == 0
    assert player.seam_score() == 0.0
    assert not player.is_playing()
