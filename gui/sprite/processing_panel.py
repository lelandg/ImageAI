"""Processing panel: extraction, key, profiles, stabilize; runs the pipeline (design §4.5).

Every long job (pipeline, ffprobe, chroma preview, palette rebuild) runs in a
SpriteWorker. Editors write straight into the SpriteProject dataclasses; the
pipeline's stage cache (§1.2) decides what re-runs.
"""
from __future__ import annotations

import contextlib
import functools
import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from PIL import Image
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar,
                               QPushButton, QScrollArea, QSlider, QSpinBox, QVBoxLayout,
                               QWidget)

from core.sprite.extract import estimate_frame_count, probe_video
from core.sprite.keying import KEY_AUTO_MIN_UNIFORMITY, estimate_key_color, ffmpeg_chromakey_preview
from core.sprite.matting import REMBG_MODELS, available_backends
from core.sprite.pipeline import list_frames, run_pipeline, stage_dir
from core.sprite.pixelart import FLOYD_WARNING
from core.sprite.presets import CELL_PRESETS, CUSTOM_CELL_LABEL
from core.sprite.project import ActionCard, OutputProfile, SpriteProject
from gui.common.dialog_conventions import bind_primary_action

from .ml_install_dialog import SpriteMLInstallDialog
from .pixel_view import PixelView
from .workers import SpriteWorker, WorkerHost

logger = logging.getLogger(__name__)

EXTRACT_MODES = ("every_n", "target_fps", "exact_n")
KEY_METHODS = ("chroma", "ml", "none")
DESPILL_MODES = ("none", "average", "double", "limit")
ML_BACKENDS = ("mediapipe", "rembg")
DITHER_MODES = ("none", "bayer2", "bayer4", "bayer8", "floyd")
ANCHORS = ("bottom_center", "center", "top_left", "top_center", "bottom_left")
DEJITTER_METHODS = ("phase", "centroid")
CUSTOM_PRESET = CUSTOM_CELL_LABEL   # "Custom…" — one label, owned by core.sprite.presets
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


@contextlib.contextmanager
def _blocked(*widgets: QWidget):
    for widget in widgets:
        widget.blockSignals(True)
    try:
        yield
    finally:
        for widget in widgets:
            widget.blockSignals(False)


def _combo(values, labels: Optional[Dict[str, str]] = None) -> QComboBox:
    combo = QComboBox()
    for value in values:
        combo.addItem((labels or {}).get(value, value), value)
    return combo


class ProfileEditor(QGroupBox):
    """Editor for one OutputProfile (hd or pixel)."""

    changed = Signal()
    rebuildRequested = Signal(str)

    def __init__(self, profile_name: str, parent=None):
        super().__init__(f"Profile: {profile_name}", parent)
        self.profile_name = profile_name
        form = QFormLayout(self)

        self.enabled = QCheckBox("Enabled")
        form.addRow(self.enabled)

        self.preset = QComboBox()
        for label, _size in CELL_PRESETS:
            self.preset.addItem(label)
        self.preset.addItem(CUSTOM_PRESET)
        self.width = QSpinBox()
        self.width.setRange(1, 4096)
        self.height = QSpinBox()
        self.height.setRange(1, 4096)
        size_row = QHBoxLayout()
        size_row.addWidget(self.preset, 1)
        size_row.addWidget(self.width)
        size_row.addWidget(QLabel("×"))
        size_row.addWidget(self.height)
        form.addRow("Cell size:", size_row)

        self.binary_alpha = QCheckBox("Binary alpha")
        self.threshold = QSpinBox()
        self.threshold.setRange(0, 255)
        self.defringe = QSpinBox()
        self.defringe.setRange(0, 16)
        alpha_row = QHBoxLayout()
        alpha_row.addWidget(self.binary_alpha)
        alpha_row.addWidget(QLabel("threshold"))
        alpha_row.addWidget(self.threshold)
        alpha_row.addWidget(QLabel("defringe px"))
        alpha_row.addWidget(self.defringe)
        form.addRow("Alpha:", alpha_row)

        self.palette_size = QSpinBox()
        self.palette_size.setRange(0, 256)
        self.palette_size.setSpecialValueText("no quantize")
        self.palette_size.setToolTip("Shared palette size; 0 = keep true color")
        form.addRow("Palette size:", self.palette_size)

        self.dither = _combo(DITHER_MODES)
        form.addRow("Dither:", self.dither)
        self.dither_warning = QLabel(FLOYD_WARNING)
        self.dither_warning.setWordWrap(True)
        self.dither_warning.setStyleSheet("color: #cca700;")
        self.dither_warning.setVisible(False)
        form.addRow(self.dither_warning)

        self.palette_lock = QCheckBox("Lock palette (remap new frames)")
        self.rebuild_btn = QPushButton("Rebuild palette")
        self.rebuild_btn.setAutoDefault(False)
        self.rebuild_btn.clicked.connect(self._on_rebuild_clicked)
        lock_row = QHBoxLayout()
        lock_row.addWidget(self.palette_lock, 1)
        lock_row.addWidget(self.rebuild_btn)
        form.addRow("Palette lock:", lock_row)

        self.upscale_small = QCheckBox("Upscale sources smaller than the cell")
        self.upscale_small.setToolTip("Sub-project 4: upscale a small source before the integer fit "
                                      "instead of padding it; the pixel stage reports the case in pixel.json")
        form.addRow("Small sources:", self.upscale_small)

        self.preset.currentIndexChanged.connect(self._on_preset)
        self.dither.currentIndexChanged.connect(self._on_dither)
        for spin in (self.width, self.height, self.threshold, self.defringe, self.palette_size):
            spin.valueChanged.connect(self._on_value_changed)
        for box in (self.enabled, self.binary_alpha, self.palette_lock, self.upscale_small):
            box.toggled.connect(self._on_value_changed)

    def _on_rebuild_clicked(self) -> None:
        self.rebuildRequested.emit(self.profile_name)

    def _on_value_changed(self, *_args) -> None:
        self.changed.emit()

    def _on_preset(self, index: int) -> None:
        custom = self.preset.currentText() == CUSTOM_PRESET
        self.width.setEnabled(custom)
        self.height.setEnabled(custom)
        if not custom and 0 <= index < len(CELL_PRESETS):
            width, height = CELL_PRESETS[index][1]
            with _blocked(self.width, self.height):
                self.width.setValue(width)
                self.height.setValue(height)
        self.changed.emit()

    def _on_dither(self, _index: int) -> None:
        self.dither_warning.setVisible(self.dither.currentData() == "floyd")
        self.changed.emit()

    def load(self, profile: OutputProfile) -> None:
        with _blocked(self.enabled, self.preset, self.width, self.height, self.binary_alpha,
                      self.threshold, self.defringe, self.palette_size, self.dither,
                      self.palette_lock, self.upscale_small):
            self.enabled.setChecked(profile.enabled)
            match = next((i for i, (_l, size) in enumerate(CELL_PRESETS)
                          if tuple(size) == tuple(profile.cell_size)), None)
            self.preset.setCurrentIndex(match if match is not None else self.preset.count() - 1)
            self.width.setValue(int(profile.cell_size[0]))
            self.height.setValue(int(profile.cell_size[1]))
            self.width.setEnabled(match is None)
            self.height.setEnabled(match is None)
            self.binary_alpha.setChecked(profile.binary_alpha)
            self.threshold.setValue(int(profile.alpha_threshold))
            self.defringe.setValue(int(profile.defringe_px))
            self.palette_size.setValue(int(profile.palette_size or 0))
            self.dither.setCurrentIndex(max(0, self.dither.findData(profile.dither)))
            self.dither_warning.setVisible(profile.dither == "floyd")
            self.palette_lock.setChecked(profile.palette_lock)
            self.upscale_small.setChecked(bool(getattr(profile, "upscale_small", False)))

    def store(self, profile: OutputProfile) -> None:
        profile.enabled = self.enabled.isChecked()
        profile.cell_size = (self.width.value(), self.height.value())
        profile.binary_alpha = self.binary_alpha.isChecked()
        profile.alpha_threshold = self.threshold.value()
        profile.defringe_px = self.defringe.value()
        profile.palette_size = self.palette_size.value() or None
        profile.dither = self.dither.currentData()
        profile.palette_lock = self.palette_lock.isChecked()
        profile.upscale_small = self.upscale_small.isChecked()


class ProcessingPanel(WorkerHost, QWidget):
    """Settings groups + Run pipeline / Preview key / Export buttons.

    `WorkerHost` (5a) owns the one long-running SpriteWorker; `start_job` refuses a
    second job while one runs, and `shutdown()` cancels and joins it. A short-lived
    probe worker runs ffprobe beside it when the action changes.
    """

    pipelineFinished = Signal(str)
    settingsChanged = Signal()
    logMessage = Signal(str, str)
    exportRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project: Optional[SpriteProject] = None
        self._action: Optional[ActionCard] = None
        self._probe: Optional[Dict[str, Any]] = None
        self._probe_path: Optional[Path] = None
        self._probe_worker: Optional[SpriteWorker] = None
        self._probe_id = 0
        self._view: Optional[PixelView] = None
        self._loading = False
        self.profile_editors: Dict[str, ProfileEditor] = {}
        self._build()
        self._primary = bind_primary_action(self, self.run_pipeline,
                                            context=Qt.WidgetWithChildrenShortcut)
        self.refresh_backends()
        self._sync_enabled()

    # ----- UI ---------------------------------------------------------
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        self._body_layout = QVBoxLayout(body)
        self._body_layout.addWidget(self._build_extraction())
        self._body_layout.addWidget(self._build_key())
        self.profiles_box = QGroupBox("Output profiles")
        self.profiles_layout = QVBoxLayout(self.profiles_box)
        self._body_layout.addWidget(self.profiles_box)
        self._body_layout.addWidget(self._build_stabilize())
        self._body_layout.addStretch()
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        outer.addWidget(self._build_actions())

    def _build_extraction(self) -> QGroupBox:
        box = QGroupBox("Extraction")
        form = QFormLayout(box)
        self.extract_mode = _combo(EXTRACT_MODES, {"every_n": "every N frames",
                                                   "target_fps": "target fps",
                                                   "exact_n": "exactly N frames"})
        form.addRow("Mode:", self.extract_mode)
        self.every_n = QSpinBox()
        self.every_n.setRange(1, 120)
        form.addRow("Every N:", self.every_n)
        self.target_fps = QSpinBox()
        self.target_fps.setRange(1, 60)
        form.addRow("Target fps:", self.target_fps)
        self.exact_n = QSpinBox()
        self.exact_n.setRange(1, 512)
        form.addRow("Exact N:", self.exact_n)
        self.trim_start = QDoubleSpinBox()
        self.trim_start.setRange(0.0, 600.0)
        self.trim_start.setSuffix(" s")
        self.trim_end = QDoubleSpinBox()
        self.trim_end.setRange(0.0, 600.0)
        self.trim_end.setSuffix(" s")
        trim_row = QHBoxLayout()
        trim_row.addWidget(self.trim_start)
        trim_row.addWidget(QLabel("to"))
        trim_row.addWidget(self.trim_end)
        form.addRow("Trim:", trim_row)
        self.cull = QCheckBox("Cull duplicate frames")
        self.cull_threshold = QDoubleSpinBox()
        self.cull_threshold.setRange(0.0, 1.0)
        self.cull_threshold.setSingleStep(0.01)
        self.cull_threshold.setDecimals(3)
        cull_row = QHBoxLayout()
        cull_row.addWidget(self.cull)
        cull_row.addWidget(self.cull_threshold)
        form.addRow("Duplicates:", cull_row)
        self.estimate_label = QLabel("yields ~? frames")
        self.estimate_label.setStyleSheet("font-weight: bold;")
        form.addRow("Estimate:", self.estimate_label)

        self.extract_mode.currentIndexChanged.connect(self._on_changed)
        for spin in (self.every_n, self.target_fps, self.exact_n, self.trim_start,
                     self.trim_end, self.cull_threshold):
            spin.valueChanged.connect(self._on_changed)
        self.cull.toggled.connect(self._on_changed)
        return box

    def _build_key(self) -> QGroupBox:
        box = QGroupBox("Key / matte")
        form = QFormLayout(box)
        self.key_method = _combo(KEY_METHODS, {"chroma": "chroma key", "ml": "ML matte",
                                               "none": "none (source has alpha)"})
        form.addRow("Method:", self.key_method)
        self.key_color_edit = QLineEdit()
        self.key_color_edit.setPlaceholderText("auto (sampled from the clip)")
        self.key_color_edit.setToolTip(
            "#RRGGBB. Empty = sample the clip's border color automatically. The plate color "
            "is only the request sent to the model; the clip often drifts from it.")
        self.pick_btn = QPushButton("Pick…")
        self.pick_btn.setAutoDefault(False)
        self.pick_btn.setToolTip("Click a pixel in the preview to pick the key color")
        self.pick_btn.clicked.connect(self.pick_key_color)
        color_row = QHBoxLayout()
        color_row.addWidget(self.key_color_edit, 1)
        color_row.addWidget(self.pick_btn)
        form.addRow("Key color:", color_row)
        self.tolerance = QSlider(Qt.Horizontal)
        self.tolerance.setRange(0, 100)
        self.tolerance_label = QLabel("0.20")
        tol_row = QHBoxLayout()
        tol_row.addWidget(self.tolerance, 1)
        tol_row.addWidget(self.tolerance_label)
        form.addRow("Tolerance:", tol_row)
        self.softness = QSlider(Qt.Horizontal)
        self.softness.setRange(0, 100)
        self.softness_label = QLabel("0.10")
        soft_row = QHBoxLayout()
        soft_row.addWidget(self.softness, 1)
        soft_row.addWidget(self.softness_label)
        form.addRow("Softness:", soft_row)
        self.despill = _combo(DESPILL_MODES)
        form.addRow("Despill:", self.despill)
        self.decontaminate = QCheckBox("Edge decontaminate")
        form.addRow(self.decontaminate)
        self.choke = QSpinBox()
        self.choke.setRange(0, 16)
        self.feather = QSpinBox()
        self.feather.setRange(0, 16)
        self.despeckle = QSpinBox()
        self.despeckle.setRange(0, 16)
        edge_row = QHBoxLayout()
        for label, spin in (("choke", self.choke), ("feather", self.feather), ("despeckle", self.despeckle)):
            edge_row.addWidget(QLabel(label))
            edge_row.addWidget(spin)
        form.addRow("Edges (px):", edge_row)
        self.ml_backend = _combo(ML_BACKENDS)
        self.ml_model = QComboBox()
        for model, info in REMBG_MODELS.items():
            suffix = "" if info.get("default_ok", True) else " (non-commercial)"
            self.ml_model.addItem(f"{model}{suffix}", model)
        self.ml_refine = QCheckBox("Refine edges")
        self.ml_status = QLabel("")
        self.install_btn = QPushButton("Install…")
        self.install_btn.setAutoDefault(False)
        self.install_btn.clicked.connect(self.open_install_dialog)
        ml_row = QHBoxLayout()
        ml_row.addWidget(self.ml_backend)
        ml_row.addWidget(self.ml_model, 1)
        ml_row.addWidget(self.ml_refine)
        ml_row.addWidget(self.install_btn)
        form.addRow("ML backend:", ml_row)
        form.addRow("", self.ml_status)

        self.key_method.currentIndexChanged.connect(self._on_changed)
        self.key_color_edit.textChanged.connect(self._on_changed)
        self.tolerance.valueChanged.connect(self._on_tolerance_moved)
        self.softness.valueChanged.connect(self._on_softness_moved)
        self.tolerance.valueChanged.connect(self._on_changed)
        self.softness.valueChanged.connect(self._on_changed)
        self.despill.currentIndexChanged.connect(self._on_changed)
        self.decontaminate.toggled.connect(self._on_changed)
        for spin in (self.choke, self.feather, self.despeckle):
            spin.valueChanged.connect(self._on_changed)
        self.ml_backend.currentIndexChanged.connect(self._on_changed)
        self.ml_model.currentIndexChanged.connect(self._on_changed)
        self.ml_refine.toggled.connect(self._on_changed)
        return box

    def _on_tolerance_moved(self, value: int) -> None:
        self.tolerance_label.setText(f"{value / 100:.2f}")

    def _on_softness_moved(self, value: int) -> None:
        self.softness_label.setText(f"{value / 100:.2f}")

    def _build_stabilize(self) -> QGroupBox:
        box = QGroupBox("Stabilize")
        form = QFormLayout(box)
        self.anchor = _combo(ANCHORS)
        form.addRow("Anchor:", self.anchor)
        self.dejitter = QCheckBox("De-jitter")
        self.dejitter.setToolTip(
            "Register every frame to the first frame by its alpha mask. Use it for footage "
            "with camera jitter only. Off by default: on pose animation (headbang, arm swing) "
            "the alignment shifts the character, and the shift can move it off the frame.")
        self.dejitter_method = _combo(DEJITTER_METHODS)
        jitter_row = QHBoxLayout()
        jitter_row.addWidget(self.dejitter)
        jitter_row.addWidget(self.dejitter_method, 1)
        form.addRow("Jitter:", jitter_row)
        self.pad = QSpinBox()
        self.pad.setRange(0, 256)
        form.addRow("Pad (px):", self.pad)
        self.anchor.currentIndexChanged.connect(self._on_changed)
        self.dejitter.toggled.connect(self._on_changed)
        self.dejitter_method.currentIndexChanged.connect(self._on_changed)
        self.pad.valueChanged.connect(self._on_changed)
        return box

    def _build_actions(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.force_check = QCheckBox("Force re-run")
        self.force_check.setToolTip("Ignore the stage cache and re-run every stage")
        row.addWidget(self.force_check)
        row.addStretch()
        self.preview_btn = QPushButton("Preview key on clip")
        self.preview_btn.setToolTip("Write an ffmpeg chromakey preview of the clip and open it")
        self.preview_btn.clicked.connect(self.preview_key_on_clip)
        self.export_btn = QPushButton("Export…")
        self.export_btn.setToolTip("Open the export dialog")
        self.export_btn.clicked.connect(self.exportRequested.emit)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel)
        self.cancel_btn.setEnabled(False)
        self.run_btn = QPushButton("Run pipeline")
        self.run_btn.setToolTip("Run the processing pipeline for the selected action (Ctrl+Enter)")
        self.run_btn.clicked.connect(self.run_pipeline)
        for button in (self.preview_btn, self.export_btn, self.cancel_btn, self.run_btn):
            button.setAutoDefault(False)
            row.addWidget(button)
        layout.addLayout(row)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)
        return panel

    # ----- binding ----------------------------------------------------
    def set_project(self, project: Optional[SpriteProject]) -> None:
        self._project = project
        self._load_from_project()
        self._sync_enabled()

    def project(self) -> Optional[SpriteProject]:
        return self._project

    def set_action(self, action: Optional[ActionCard]) -> None:
        # Supersede first, and unconditionally: a probe started for the previous
        # action must be detached even when the new action has no clip to probe,
        # or its late result would still be the panel's "current" probe worker.
        self._supersede_probe()
        self._action = action
        self._probe = None
        self._probe_path = None
        self._sync_enabled()
        self._update_estimate()
        clip = getattr(action, "clip", None) if action is not None else None
        if clip is not None and getattr(clip, "path", None):
            self._probe_clip(Path(clip.path), action.id)

    def action(self) -> Optional[ActionCard]:
        return self._action

    def attach_pixel_view(self, view: PixelView) -> None:
        if self._view is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                self._view.colorPicked.disconnect(self._on_color_picked)
        self._view = view
        view.colorPicked.connect(self._on_color_picked)

    def set_probe(self, probe: Optional[Dict[str, Any]]) -> None:
        self._probe = dict(probe) if probe else None
        self._update_estimate()

    def estimate_text(self) -> str:
        return self.estimate_label.text()

    def _load_from_project(self) -> None:
        project = self._project
        for editor in self.profile_editors.values():
            self.profiles_layout.removeWidget(editor)
            editor.setParent(None)
            editor.deleteLater()
        self.profile_editors = {}
        if project is None:
            self._update_estimate()
            return
        self._loading = True
        try:
            ex = project.extraction
            with _blocked(self.extract_mode, self.every_n, self.target_fps, self.exact_n,
                          self.trim_start, self.trim_end, self.cull, self.cull_threshold):
                self.extract_mode.setCurrentIndex(max(0, self.extract_mode.findData(ex.mode)))
                self.every_n.setValue(int(ex.every_n))
                self.target_fps.setValue(int(ex.target_fps))
                self.exact_n.setValue(int(ex.exact_n))
                self.trim_start.setValue(float(ex.trim_start_s))
                self.trim_end.setValue(float(ex.trim_end_s))
                self.cull.setChecked(bool(ex.cull_duplicates))
                self.cull_threshold.setValue(float(ex.duplicate_threshold))
            key = project.key
            with _blocked(self.key_method, self.key_color_edit, self.tolerance, self.softness,
                          self.despill, self.decontaminate, self.choke, self.feather,
                          self.despeckle, self.ml_backend, self.ml_model, self.ml_refine):
                self.key_method.setCurrentIndex(max(0, self.key_method.findData(key.method)))
                self.key_color_edit.setText(key.key_color or "")
                self.tolerance.setValue(int(round(key.tolerance * 100)))
                self.softness.setValue(int(round(key.softness * 100)))
                self.tolerance_label.setText(f"{key.tolerance:.2f}")
                self.softness_label.setText(f"{key.softness:.2f}")
                self.despill.setCurrentIndex(max(0, self.despill.findData(key.despill)))
                self.decontaminate.setChecked(bool(key.edge_decontaminate))
                self.choke.setValue(int(key.choke_px))
                self.feather.setValue(int(key.feather_px))
                self.despeckle.setValue(int(key.despeckle_px))
                self.ml_backend.setCurrentIndex(max(0, self.ml_backend.findData(key.ml_backend)))
                self.ml_model.setCurrentIndex(max(0, self.ml_model.findData(key.ml_model)))
                self.ml_refine.setChecked(bool(key.ml_refine_edges))
            st = project.stabilize
            with _blocked(self.anchor, self.dejitter, self.dejitter_method, self.pad):
                self.anchor.setCurrentIndex(max(0, self.anchor.findData(st.anchor)))
                self.dejitter.setChecked(bool(st.dejitter))
                self.dejitter_method.setCurrentIndex(max(0, self.dejitter_method.findData(st.dejitter_method)))
                self.pad.setValue(int(st.pad_px))
            for profile in project.profiles:
                editor = ProfileEditor(profile.name)
                editor.load(profile)
                editor.changed.connect(self._on_changed)
                editor.rebuildRequested.connect(self.rebuild_palette_for)
                self.profiles_layout.addWidget(editor)
                self.profile_editors[profile.name] = editor
        finally:
            self._loading = False
        self._update_estimate()

    def _key_color_value(self) -> Optional[str]:
        text = self.key_color_edit.text().strip()
        if not text:
            return None
        if HEX_RE.match(text):
            return text.upper()
        logger.warning("Processing panel: invalid key color %r ignored", text)
        return None

    def _check_key_color_field(self) -> bool:
        """Block a commit point (Run pipeline / Preview key) on a typed key colour that
        does not parse, instead of silently keying on the plate colour (Important 6).

        Call after `_write_back()`, which already dropped the bad value to `None` with a
        log-only warning per keystroke; this re-reads the live field text so the two
        commit points show and log the refusal instead of running against the plate.
        """
        text = self.key_color_edit.text().strip()
        if text and not HEX_RE.match(text):
            self._warn("Key color", f"{text!r} is not #RRGGBB")
            return False
        return True

    def _write_back(self) -> None:
        project = self._project
        if project is None:
            return
        ex = project.extraction
        ex.mode = self.extract_mode.currentData()
        ex.every_n = self.every_n.value()
        ex.target_fps = self.target_fps.value()
        ex.exact_n = self.exact_n.value()
        ex.trim_start_s = self.trim_start.value()
        ex.trim_end_s = self.trim_end.value()
        ex.cull_duplicates = self.cull.isChecked()
        ex.duplicate_threshold = self.cull_threshold.value()
        key = project.key
        key.method = self.key_method.currentData()
        key.key_color = self._key_color_value()
        key.tolerance = self.tolerance.value() / 100.0
        key.softness = self.softness.value() / 100.0
        key.despill = self.despill.currentData()
        key.edge_decontaminate = self.decontaminate.isChecked()
        key.choke_px = self.choke.value()
        key.feather_px = self.feather.value()
        key.despeckle_px = self.despeckle.value()
        key.ml_backend = self.ml_backend.currentData()
        key.ml_model = self.ml_model.currentData()
        key.ml_refine_edges = self.ml_refine.isChecked()
        st = project.stabilize
        st.anchor = self.anchor.currentData()
        st.dejitter = self.dejitter.isChecked()
        st.dejitter_method = self.dejitter_method.currentData()
        st.pad_px = self.pad.value()
        for profile in project.profiles:
            editor = self.profile_editors.get(profile.name)
            if editor is not None:
                editor.store(profile)

    def _on_changed(self, *_args) -> None:
        if self._loading or self._project is None:
            return
        self._write_back()
        self.settingsChanged.emit()
        self._update_estimate()

    # ----- readouts ---------------------------------------------------
    def _update_estimate(self) -> None:
        if self._project is None or self._probe is None:
            self.estimate_label.setText("yields ~? frames (no clip probed)")
            return
        try:
            count = estimate_frame_count(self._probe, self._project.extraction)
        except Exception as exc:
            logger.warning("Frame estimate failed: %s", exc)
            self.estimate_label.setText("yields ~? frames")
            return
        self.estimate_label.setText(f"yields ~{count} frames")

    def refresh_backends(self) -> None:
        try:
            available = available_backends()
        except Exception as exc:
            logger.error("available_backends failed: %s", exc, exc_info=True)
            available = {}
        parts = []
        for name in ML_BACKENDS:
            ok = bool(available.get(name, False))
            parts.append(f"{name}: {'installed' if ok else 'not installed'}")
        self.ml_status.setText("; ".join(parts))
        self.install_btn.setVisible(not all(available.get(n, False) for n in ML_BACKENDS))

    def _sync_enabled(self) -> None:
        ready = self._project is not None and self._action is not None and not self.is_busy()
        self.run_btn.setEnabled(ready)
        self.preview_btn.setEnabled(ready)
        self.export_btn.setEnabled(self._project is not None and not self.is_busy())
        primary = getattr(self, "_primary", None)
        if primary is not None:
            primary.set_enabled(ready)

    def _on_worker_idle(self) -> None:
        """A worker orphaned by a timed-out ``shutdown()`` finally stopped.

        The orphan's terminal signal is dropped by ``WorkerHost._guarded`` (it is no
        longer the host's live worker), so ``_on_done``/``_on_failed`` never run and
        nothing else clears the run UI. Reset it here, the way
        ``gui/sprite/queue_panel.py`` does, or the progress bar and Cancel button
        stay live for a job that has already stopped (review, Minor 1).
        """
        self._set_running(self.is_busy())
        self._sync_enabled()

    # ----- user actions -----------------------------------------------
    def pick_key_color(self) -> None:
        if self._view is None:
            self._warn("Pick key color", "No preview is attached.")
            return
        self._view.set_pick_mode(True)
        self.logMessage.emit("Click a pixel in the preview to pick the key color.", "INFO")

    def _on_color_picked(self, color: str) -> None:
        self.key_color_edit.setText(color)
        self.logMessage.emit(f"Key color set to {color}", "INFO")

    def open_install_dialog(self) -> None:
        dialog = SpriteMLInstallDialog(self)
        dialog.installFinished.connect(self._on_install_finished)
        dialog.exec()
        self.refresh_backends()

    def _on_install_finished(self, _ok: bool) -> None:
        self.refresh_backends()

    # Names an external job that must finish before this panel runs the pipeline
    # (the render queue runs run_pipeline on its own thread, and two writers to
    # the same stage directories leave action.status/frames last-writer-wins).
    # The workspace installs it; None means no guard (PR #45 review).
    _busy_guard: Optional[Callable[[], Optional[str]]] = None

    def set_busy_guard(self, guard: Optional[Callable[[], Optional[str]]]) -> None:
        self._busy_guard = guard

    def _external_job(self) -> Optional[str]:
        guard = self._busy_guard
        return guard() if guard is not None else None

    def run_pipeline(self) -> None:
        project, action = self._project, self._action
        if project is None or action is None:
            self._warn("Run pipeline", "Select an action card first.")
            return
        external = self._external_job()
        if external:
            logger.warning("Run pipeline refused: the %s is still running", external)
            self.logMessage.emit(f"Wait for the {external} to finish before running the pipeline",
                                 "WARNING")
            return
        self._write_back()
        if not self._check_key_color_field():
            return
        force = self.force_check.isChecked()

        def job(progress, token):
            return run_pipeline(project, action, upto="pixel", progress=progress,
                                token=token, force=force)

        self.logMessage.emit(f"Run pipeline: action '{action.name}' (force={force})", "INFO")
        self._start(job, lambda result: self._pipeline_done(action, result), "Pipeline")

    def _pipeline_done(self, action: ActionCard, result: Any) -> None:
        stages = ", ".join(f"{k}={len(v)}" for k, v in (result or {}).items())
        self.logMessage.emit(f"Pipeline finished for '{action.name}': {stages or 'no output'}", "SUCCESS")
        self._log_pixel_warnings(action)
        self.pipelineFinished.emit(action.id)

    def _log_pixel_warnings(self, action: ActionCard) -> None:
        """Surface the pixel stage's warnings from stages/<id>/pixel/pixel.json (sub-project 4)."""
        project = self._project
        if project is None:
            return
        report = stage_dir(project, action, "pixel") / "pixel.json"
        if not report.exists():
            return
        try:
            data = json.loads(report.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("Cannot read %s: %s", report, exc)
            return
        for warning in data.get("warnings") or []:
            logger.warning("Pixel stage (%s): %s", action.name, warning)
            self.logMessage.emit(f"Pixel profile: {warning}", "WARNING")

    def cancel(self) -> None:
        if self.is_busy():
            self.cancel_running()
            self.logMessage.emit("Cancel requested…", "WARNING")

    def _sampled_key_color(self, action: ActionCard) -> Optional[str]:
        """The clip border color, from the first extracted frame, for the ffmpeg preview.

        Same rule as the key stage: the clip wins over the requested plate
        color. None when no extract output exists yet or the border is not
        one color.
        """
        project = self._project
        if project is None:
            return None
        frames = list_frames(stage_dir(project, action, "extract"))
        if not frames:
            return None
        try:
            with Image.open(frames[0]) as first:
                estimate = estimate_key_color(first, tolerance=project.key.tolerance)
        except (OSError, ValueError) as exc:
            logger.warning("Cannot sample the key color from %s: %s", frames[0], exc)
            return None
        if estimate.uniformity < KEY_AUTO_MIN_UNIFORMITY:
            return None
        return estimate.color

    def preview_key_on_clip(self) -> None:
        project, action = self._project, self._action
        if project is None or action is None:
            self._warn("Preview key", "Select an action card first.")
            return
        clip = getattr(action, "clip", None)
        if clip is None or not getattr(clip, "path", None):
            self._warn("Preview key", "This action has no clip. Render or import one first.")
            return
        self._write_back()
        if not self._check_key_color_field():
            return
        key = project.key
        color = key.key_color or self._sampled_key_color(action) or project.plate_color
        video = Path(clip.path)
        out_mp4 = stage_dir(project, action, "key") / "preview_chromakey.mp4"

        def job(progress, token):
            progress("key", 0, 0, "ffmpeg chromakey preview")
            out_mp4.parent.mkdir(parents=True, exist_ok=True)
            return ffmpeg_chromakey_preview(video, out_mp4, color, key.tolerance, key.softness)

        self.logMessage.emit(f"Chroma preview: {video.name} key={color}", "INFO")
        self._start(job, self._preview_done, "Chroma preview")

    def _preview_done(self, result: Any) -> None:
        path = Path(result)
        self.logMessage.emit(f"Chroma preview written: {path}", "SUCCESS")
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            logger.warning("Chroma preview: no handler opened %s", path)
            self.logMessage.emit(f"Chroma preview: could not open {path}; open it manually.", "WARNING")

    def rebuild_palette_for(self, profile_name: str) -> None:
        project, action = self._project, self._action
        if project is None or action is None:
            self._warn("Rebuild palette", "Select an action card first.")
            return
        profile = next((p for p in project.profiles if p.name == profile_name), None)
        if profile is None:
            self._warn("Rebuild palette", f"Unknown profile '{profile_name}'.")
            return
        self._write_back()

        # Sub-project 4 contract: `locked_palette` is part of the pixel-stage fingerprint.
        # Clearing it and re-running the pipeline makes `ensure_palette` rebuild the palette
        # from the fitted binary-alpha frames — the same frames the quantizer uses.
        profile.locked_palette = None
        self.logMessage.emit(f"Palette lock cleared for '{profile.name}'; re-running the pipeline", "INFO")
        force = self.force_check.isChecked()

        def job(progress, token):
            return run_pipeline(project, action, upto="pixel", progress=progress,
                                token=token, force=force)

        self._start(job, lambda result: self._palette_done(action, profile, result), "Rebuild palette")

    def _palette_done(self, action: ActionCard, profile: OutputProfile, _result: Any) -> None:
        colors = list(profile.locked_palette or [])
        self.logMessage.emit(f"Palette rebuilt for '{profile.name}': {len(colors)} colors", "SUCCESS")
        self._log_pixel_warnings(action)
        self.pipelineFinished.emit(action.id)

    # ----- worker plumbing (WorkerHost: one SpriteWorker at a time) ---
    def _start(self, job: Callable, on_done: Callable[[Any], None], label: str) -> bool:
        worker = self.start_job(job, label=label,
                                on_finished=lambda result: self._on_done(on_done, result),
                                on_failed=self._on_failed, on_cancelled=self._on_cancelled,
                                on_progress=self._on_progress)
        if worker is None:
            self._warn(label, "Wait for the current job to finish.")
            return False
        self._set_running(True, label)
        return True

    def _set_running(self, running: bool, label: str = "") -> None:
        self.progress_bar.setVisible(running)
        self.progress_label.setVisible(running)
        self.cancel_btn.setEnabled(running)
        if running:
            self.progress_bar.setRange(0, 0)
            self.progress_label.setText(f"{label}…")
        self._sync_enabled()

    def _on_progress(self, stage: str, done: int, total: int, message: str) -> None:
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(done)
        else:
            self.progress_bar.setRange(0, 0)
        self.progress_label.setText(f"{stage}: {message}")
        self.logMessage.emit(f"[{stage}] {done}/{total} {message}", "INFO")

    def _on_done(self, on_done: Callable[[Any], None], result: Any) -> None:
        self._set_running(False)
        try:
            on_done(result)
        except Exception as exc:
            logger.error("Sprite job completion handler failed: %s", exc, exc_info=True)
            self.logMessage.emit(f"Error: {exc}", "ERROR")
            QMessageBox.critical(self, "Sprite processing", str(exc))

    def _on_failed(self, message: str) -> None:
        self._set_running(False)
        logger.error("Sprite job failed: %s", message)
        self.logMessage.emit(f"Failed: {message}", "ERROR")
        QMessageBox.critical(self, "Sprite processing failed", message)

    def _on_cancelled(self) -> None:
        self._set_running(False)
        logger.info("Sprite job cancelled")
        self.logMessage.emit("Cancelled.", "WARNING")

    # ----- probe worker (short-lived, beside the WorkerHost worker) ---
    def _probe_clip(self, path: Path, action_id: Optional[str]) -> None:
        """Start an ffprobe worker for ``path``, superseding any probe in flight."""
        self._supersede_probe()
        self._probe_path = path
        self._probe_id += 1
        probe_id = self._probe_id
        # Parented to the panel so Qt owns the QThread: dropping the Python
        # reference in _release_probe must never destroy a running thread.
        worker = SpriteWorker(lambda progress, token: probe_video(path), label="probe", parent=self)
        # Bound to THIS run and the action it was started for, so a late event
        # from a superseded probe never touches the panel's current state.
        # The bound values are ints/str, never the worker itself: a partial that
        # holds the worker and is connected to that same worker keeps the QThread
        # wrapper alive past its refcount drop, which moves its teardown into an
        # arbitrary later GC pass and crashed this suite intermittently.
        worker.finished.connect(functools.partial(self._probe_done, probe_id, action_id))
        worker.failed.connect(functools.partial(self._probe_failed, probe_id, action_id))
        self._probe_worker = worker
        worker.start()

    def _probe_is_current(self, probe_id: int, action_id: Optional[str],
                          signal_name: str) -> bool:
        """True while run ``probe_id`` is still this panel's probe for the selected action.

        Mirrors ``WorkerHost._guarded`` (workers.py): the identity test lives in
        one place, so every probe slot drops a stale event the same way. Every
        path that detaches a probe — ``_supersede_probe``, ``_release_probe``,
        ``shutdown`` — clears ``_probe_worker``, and every new run bumps
        ``_probe_id``, so these two tests identify the live run exactly.
        """
        if probe_id != self._probe_id or self._probe_worker is None:
            logger.debug("Dropped probe %s: run %d was superseded", signal_name, probe_id)
            return False
        current = self._action.id if self._action is not None else None
        if action_id != current:
            logger.debug("Dropped probe %s: started for action %r, now %r",
                         signal_name, action_id, current)
            return False
        return True

    def _probe_done(self, probe_id: int, action_id: Optional[str], result: Any) -> None:
        if not self._probe_is_current(probe_id, action_id, "finished"):
            return
        self._release_probe(self._probe_worker)
        if isinstance(result, dict):
            self.set_probe(result)

    def _probe_failed(self, probe_id: int, action_id: Optional[str], message: str) -> None:
        """Log AND show every ffprobe failure; the estimate stays '~?'."""
        if not self._probe_is_current(probe_id, action_id, "failed"):
            return
        path = self._probe_path
        name = path.name if path is not None else "the clip"
        self._release_probe(self._probe_worker)
        logger.warning("ffprobe failed for %s: %s", path, message)
        self.logMessage.emit(f"ffprobe failed for {name}: {message}", "WARNING")

    def _supersede_probe(self) -> None:
        """Detach the current probe worker so a new probe can start.

        A worker that still runs becomes an orphan of this host: ``WorkerHost``
        reaps it when its thread exits, so it is never destroyed while it runs and
        ``is_busy()`` stays True until then. The worker is NOT cancelled: its token
        cannot stop the ffprobe subprocess, and cancelling would only turn the
        terminal signal into ``cancelled`` and hide the identity guard that must
        drop the stale result. A worker that already stopped is released here.
        """
        worker = self._probe_worker
        if worker is None:
            return
        self._probe_worker = None
        if worker.isRunning():
            logger.info("Probe worker for %s superseded; kept until its thread exits",
                        self._probe_path)
            self._adopt_orphan(worker)
        else:
            self._release_probe(worker)

    def _release_probe(self, worker: SpriteWorker) -> None:
        """Release the one probe worker whose job has already stopped.

        Takes the worker as an argument — never reads ``self._probe_worker`` — so a
        late event can never wait on a probe that is still running.

        Joins the thread and detaches the worker, the same way
        ``WorkerHost._release_worker`` releases the host's own worker (workers.py
        binds weak references into the signal partials and disconnects after
        release). A finished QThread left as a child of the panel rides along
        when the cyclic garbage collector frees the panel, and Qt aborts if any such
        child still runs. Detached and joined, the worker is released by the host here;
        it is freed once no partial connected to its signals still holds it — the
        partials bound above (``_probe_done``/``_probe_failed``) carry only
        ``probe_id``/``action_id``, never the worker itself, so nothing keeps it alive
        past this method's return. ``deleteLater()`` is NOT usable here: the worker's
        own signal delivery is still on the stack, and the deferred delete crashed this
        suite (measured: 10 segfaults in 16 runs).
        """
        if self._probe_worker is worker:
            self._probe_worker = None
        worker.wait()          # the caller established that this worker's job stopped
        worker.setParent(None)

    def shutdown(self, timeout_ms: int = 5000) -> bool:
        """Cancel and join both workers. False means one is still an orphan.

        The caller must call ``join_orphans()`` before this widget tree is
        destroyed; a QThread destroyed while it runs aborts the process.
        """
        joined = super().shutdown(timeout_ms)   # WorkerHost: cancel + join the main worker
        probe = self._probe_worker
        if probe is not None:
            probe.cancel()
            if probe.isRunning() and not probe.wait(timeout_ms):
                logger.error("Sprite probe worker did not stop within %d ms; kept as an orphan",
                             timeout_ms)
                self._probe_worker = None
                self._adopt_orphan(probe)
                joined = False
            else:
                self._release_probe(probe)
        return joined

    def _warn(self, title: str, message: str) -> None:
        logger.warning("%s: %s", title, message)
        self.logMessage.emit(f"{title}: {message}", "WARNING")
        QMessageBox.warning(self, title, message)
