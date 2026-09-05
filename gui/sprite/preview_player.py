"""Animation preview: QTimer + QPixmap, per-frame duration, loop modes, seam meter.

No QMovie (Qt cannot decode APNG; WebP stutters). Frames decode lazily on
first use and stay cached until `set_frames` replaces the list.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton, QSlider,
                               QVBoxLayout, QWidget)

from core.sprite.models import FrameMeta, TagMeta

from .pixel_view import PixelView, qimage_to_rgba

logger = logging.getLogger(__name__)

MODES = ("forward", "reverse", "pingpong")
SEAM_GOOD = 0.02
SEAM_WARN = 0.08
MIN_TIMER_MS = 1
SEAM_STYLES = {
    "good": "color: #73c991; font-weight: bold;",
    "warn": "color: #cca700; font-weight: bold;",
    "bad": "color: #f14c4c; font-weight: bold;",
}
SEAM_TEXT = {"good": "seamless", "warn": "small jump", "bad": "visible seam"}


def next_index(index: int, lo: int, hi: int, mode: str, direction: int) -> Tuple[int, int]:
    """Next frame index inside [lo, hi] for `mode`; returns (index, direction)."""
    if hi <= lo:
        return lo, direction
    if mode == "forward":
        return (lo if index >= hi else index + 1), 1
    if mode == "reverse":
        return (hi if index <= lo else index - 1), -1
    candidate = index + direction
    if candidate > hi:
        return hi - 1, -1
    if candidate < lo:
        return lo + 1, 1
    return candidate, direction


def loop_seam_score(first: QImage, last: QImage) -> float:
    """Mean absolute RGBA difference between the loop's last and first frame (0..1)."""
    a = qimage_to_rgba(first).astype(np.float32) / 255.0
    b = qimage_to_rgba(last).astype(np.float32) / 255.0
    if a.shape != b.shape:
        height = max(a.shape[0], b.shape[0])
        width = max(a.shape[1], b.shape[1])
        padded_a = np.zeros((height, width, 4), np.float32)
        padded_b = np.zeros((height, width, 4), np.float32)
        padded_a[: a.shape[0], : a.shape[1]] = a
        padded_b[: b.shape[0], : b.shape[1]] = b
        a, b = padded_a, padded_b
    return float(np.abs(a - b).mean())


def seam_level(score: float) -> str:
    if score < SEAM_GOOD:
        return "good"
    if score < SEAM_WARN:
        return "warn"
    return "bad"


class PreviewPlayer(QWidget):
    """Plays a frame list with per-frame durations; shows fps and loop-seam readouts."""

    frameChanged = Signal(int)
    playingChanged = Signal(bool)
    modeChanged = Signal(str)
    sourceChanged = Signal(str)
    decodeFailed = Signal(str)   # source path of a frame that did not decode

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frames: List[FrameMeta] = []
        self._tags: List[TagMeta] = []
        self._cache: Dict[int, QPixmap] = {}
        self._range: Tuple[int, int] = (0, -1)
        self._index = 0
        self._direction = 1
        self._mode = MODES[0]
        self._playing = False
        self._seam = 0.0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance)
        self._build()

    # ----- UI ---------------------------------------------------------
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        self.source_combo = QComboBox()
        self.source_combo.setToolTip("Which frames to preview: pipeline cells or a profile output")
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        self.source_combo.setVisible(False)
        top.addWidget(QLabel("Source:"))
        top.addWidget(self.source_combo)
        self.tag_combo = QComboBox()
        self.tag_combo.addItem("All frames")
        self.tag_combo.currentIndexChanged.connect(self._on_tag_changed)
        top.addWidget(QLabel("Tag:"))
        top.addWidget(self.tag_combo)
        top.addStretch()
        self.fps_label = QLabel("")
        top.addWidget(self.fps_label)
        self.seam_label = QLabel("")
        self.seam_label.setToolTip("Loop seam: mean RGBA difference between the last and first frame (0 = perfect loop)")
        top.addWidget(self.seam_label)
        layout.addLayout(top)

        self.view = PixelView()
        self.view.set_auto_fit(True)
        layout.addWidget(self.view, 1)

        self.size_btn = QPushButton("Original size (1×)")
        self.size_btn.setAutoDefault(False)
        self.size_btn.setToolTip("Show at 100% with scrolling; click again to fit the preview")
        self.size_btn.clicked.connect(self._toggle_size)
        self.view.fitModeChanged.connect(self._sync_size_button)
        top.addWidget(self.size_btn)

        controls = QHBoxLayout()
        self.first_btn = QPushButton("|<")
        self.first_btn.setToolTip("First frame (Home)")
        self.first_btn.clicked.connect(self.first)
        self.prev_btn = QPushButton("<")
        self.prev_btn.setToolTip("Previous frame (,)")
        self.prev_btn.clicked.connect(self.step_back)
        self.play_btn = QPushButton("Play")
        self.play_btn.setToolTip("Play / pause (Space)")
        self.play_btn.clicked.connect(self.toggle_play)
        self.next_btn = QPushButton(">")
        self.next_btn.setToolTip("Next frame (.)")
        self.next_btn.clicked.connect(self.step_forward)
        self.last_btn = QPushButton(">|")
        self.last_btn.setToolTip("Last frame (End)")
        self.last_btn.clicked.connect(self.last)
        self.mode_btn = QPushButton(self._mode)
        self.mode_btn.setToolTip("Loop mode: forward → reverse → ping-pong (L)")
        self.mode_btn.clicked.connect(self.cycle_mode)
        for button in (self.first_btn, self.prev_btn, self.play_btn, self.next_btn,
                       self.last_btn, self.mode_btn):
            button.setAutoDefault(False)
            controls.addWidget(button)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.valueChanged.connect(self._on_slider)
        controls.addWidget(self.slider, 1)
        self.index_label = QLabel("0 / 0")
        controls.addWidget(self.index_label)
        layout.addLayout(controls)

    def _toggle_size(self) -> None:
        if self.view.auto_fit():
            self.view.zoom_reset()
        else:
            self.view.set_auto_fit(True)

    def _sync_size_button(self, fitting: bool) -> None:
        self.size_btn.setText("Original size (1×)" if fitting else "Fit to panel")
        self.size_btn.setToolTip(
            "Show at 100% with scrolling; click again to fit the preview" if fitting
            else "Scale the whole frame to fit, following panel resizing")

    # ----- data -------------------------------------------------------
    def set_frames(self, frames: Sequence[FrameMeta]) -> None:
        self.pause()
        self._frames = list(frames)
        self._cache = {}
        self._range = (0, len(self._frames) - 1)
        self._direction = 1
        self.slider.blockSignals(True)
        self.slider.setRange(0, max(0, len(self._frames) - 1))
        self.slider.blockSignals(False)
        self._index = 0
        self._show(0, emit=False)
        self._update_readouts()

    def frames(self) -> List[FrameMeta]:
        return list(self._frames)

    def set_tags(self, tags: Sequence[TagMeta]) -> None:
        self._tags = list(tags)
        self.tag_combo.blockSignals(True)
        self.tag_combo.clear()
        self.tag_combo.addItem("All frames")
        for tag in self._tags:
            self.tag_combo.addItem(tag.name)
        self.tag_combo.blockSignals(False)
        self._apply_tag(0)

    def active_range(self) -> Tuple[int, int]:
        return self._range

    def set_sources(self, names: Sequence[str]) -> None:
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        for name in names:
            self.source_combo.addItem(name)
        self.source_combo.blockSignals(False)
        self.source_combo.setVisible(bool(names))

    def source(self) -> str:
        return self.source_combo.currentText()

    # ----- position ---------------------------------------------------
    def current_index(self) -> int:
        return self._index

    def set_current_index(self, index: int) -> None:
        if not self._frames:
            return
        self._show(max(0, min(len(self._frames) - 1, int(index))))

    def step(self, delta: int) -> None:
        if not self._frames:
            return
        lo, hi = self._range
        span = hi - lo + 1
        if span <= 0:
            return
        offset = (self._index - lo + delta) % span
        self._show(lo + offset)

    def step_back(self) -> None:
        self.step(-1)

    def step_forward(self) -> None:
        self.step(1)

    def first(self) -> None:
        if self._frames:
            self._show(self._range[0])

    def last(self) -> None:
        if self._frames:
            self._show(self._range[1])

    # ----- playback ---------------------------------------------------
    def play(self) -> None:
        if self._playing or not self._frames:
            return
        self._playing = True
        self.play_btn.setText("Pause")
        self.playingChanged.emit(True)
        self._schedule()

    def pause(self) -> None:
        if not self._playing:
            return
        self._playing = False
        self._timer.stop()
        self.play_btn.setText("Play")
        self.playingChanged.emit(False)

    def toggle_play(self) -> None:
        if self._playing:
            self.pause()
        else:
            self.play()

    def is_playing(self) -> bool:
        return self._playing

    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            mode = MODES[0]
        self._mode = mode
        self._direction = -1 if mode == "reverse" else 1
        self.mode_btn.setText(mode)
        self.modeChanged.emit(mode)

    def cycle_mode(self) -> str:
        self.set_mode(MODES[(MODES.index(self._mode) + 1) % len(MODES)])
        return self._mode

    # ----- readouts ---------------------------------------------------
    def seam_score(self) -> float:
        return self._seam

    def fps_readout(self) -> str:
        lo, hi = self._range
        if not self._frames or hi < lo:
            return ""
        durations = [max(1, f.duration_ms) for f in self._frames[lo:hi + 1]]
        mean = sum(durations) / len(durations)
        text = f"{1000.0 / mean:.1f} fps"
        if len(set(durations)) > 1:
            text += " (variable)"
        return text

    # ----- internals --------------------------------------------------
    def _pixmap(self, index: int) -> QPixmap:
        pixmap = self._cache.get(index)
        if pixmap is None:
            frame = self._frames[index]
            pixmap = QPixmap(str(frame.source_path)) if frame.source_path else QPixmap()
            if pixmap.isNull():
                logger.error("PreviewPlayer: cannot decode frame %s (%s)", index, frame.source_path)
                # The owner (FramesWorkspace) shows this in the tab console: a blank
                # preview must never be the only sign that a frame failed to decode.
                self.decodeFailed.emit(str(frame.source_path or ""))
            self._cache[index] = pixmap
        return pixmap

    def _show(self, index: int, emit: bool = True) -> None:
        if not self._frames:
            self._index = 0
            self.view.set_image(None)
            self.index_label.setText("0 / 0")
            return
        self._index = index
        self.view.set_image(self._pixmap(index))
        self.slider.blockSignals(True)
        self.slider.setValue(index)
        self.slider.blockSignals(False)
        self.index_label.setText(f"{index + 1} / {len(self._frames)}")
        if emit:
            self.frameChanged.emit(index)

    def _schedule(self) -> None:
        if not self._playing or not self._frames:
            return
        frame = self._frames[self._index]
        self._timer.start(max(MIN_TIMER_MS, int(frame.duration_ms)))

    def _advance(self) -> None:
        if not self._playing or not self._frames:
            return
        lo, hi = self._range
        self._index, self._direction = next_index(self._index, lo, hi, self._mode, self._direction)
        self._show(self._index)
        self._schedule()

    def _on_slider(self, value: int) -> None:
        self._show(value)

    def _on_tag_changed(self, combo_index: int) -> None:
        self._apply_tag(combo_index)

    def _apply_tag(self, combo_index: int) -> None:
        count = len(self._frames)
        if combo_index <= 0 or combo_index > len(self._tags) or count == 0:
            self._range = (0, count - 1)
        else:
            tag = self._tags[combo_index - 1]
            lo = max(0, min(count - 1, tag.from_index))
            hi = max(lo, min(count - 1, tag.to_index))
            self._range = (lo, hi)
            if tag.direction.startswith("pingpong"):
                self.set_mode("pingpong")
                if tag.direction == "pingpong_reverse":
                    self._direction = -1
            elif tag.direction == "reverse":
                self.set_mode("reverse")
            else:
                self.set_mode("forward")
        if count:
            self._show(self._range[0])
        self._update_readouts()

    def _on_source_changed(self, _index: int) -> None:
        self.sourceChanged.emit(self.source())

    def _update_readouts(self) -> None:
        self.fps_label.setText(self.fps_readout())
        lo, hi = self._range
        if not self._frames or hi <= lo:
            self._seam = 0.0
            self.seam_label.setText("")
            return
        first = self._pixmap(lo).toImage()
        last = self._pixmap(hi).toImage()
        if first.isNull() or last.isNull():
            self._seam = 0.0
            self.seam_label.setText("Loop seam: n/a")
            return
        self._seam = loop_seam_score(first, last)
        level = seam_level(self._seam)
        self.seam_label.setText(f"Loop seam: {self._seam:.3f} ({SEAM_TEXT[level]})")
        self.seam_label.setStyleSheet(SEAM_STYLES[level])
