"""
Export Settings Widget

This widget provides settings for final video export/assembly including:
- Output format and codec selection
- Audio mixing (background music, volume, fade)
- Transitions between clips
- Effects (color grading, watermark, text overlays)
- Output path configuration

This is provider-agnostic and applies to all video generation workflows.
"""

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QComboBox,
    QDoubleSpinBox, QCheckBox, QFileDialog,
    QToolButton, QSpinBox
)
from PySide6.QtCore import Qt, Signal

from core.config import ConfigManager


class ExportSettingsWidget(QWidget):
    """Widget for video export settings (provider-agnostic)"""

    # Signals
    settings_changed = Signal()
    export_requested = Signal()  # User clicked export button

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Main export settings group
        group = QGroupBox("Export Settings")
        group_layout = QVBoxLayout()

        # Row 1: Format, Codec, Quality
        row1 = QHBoxLayout()

        row1.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["MP4", "MOV", "AVI", "WebM"])
        self.format_combo.setToolTip("Output video format")
        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        row1.addWidget(self.format_combo)

        row1.addWidget(QLabel("Codec:"))
        self.codec_combo = QComboBox()
        self._update_codec_options("MP4")  # Default to MP4 codecs
        self.codec_combo.setToolTip("Video codec for encoding")
        self.codec_combo.currentTextChanged.connect(self._on_settings_changed)
        row1.addWidget(self.codec_combo)

        row1.addWidget(QLabel("Quality:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["High", "Medium", "Low", "Custom"])
        self.quality_combo.setToolTip(
            "Video quality preset:\n"
            "- High: Best quality, larger file size\n"
            "- Medium: Balanced quality and size\n"
            "- Low: Smaller file, lower quality\n"
            "- Custom: Specify bitrate manually"
        )
        self.quality_combo.currentTextChanged.connect(self._on_quality_changed)
        row1.addWidget(self.quality_combo)

        # Custom bitrate (hidden by default)
        row1.addWidget(QLabel("Bitrate:"))
        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(1, 100)
        self.bitrate_spin.setValue(10)
        self.bitrate_spin.setSuffix(" Mbps")
        self.bitrate_spin.setToolTip("Custom video bitrate")
        self.bitrate_spin.setVisible(False)
        self.bitrate_spin.valueChanged.connect(self._on_settings_changed)
        row1.addWidget(self.bitrate_spin)

        row1.addStretch()
        group_layout.addLayout(row1)

        # Row 2: Audio mixing
        audio_group = QGroupBox("Audio Mixing")
        audio_layout = QVBoxLayout()

        # Background music
        music_layout = QHBoxLayout()
        music_layout.addWidget(QLabel("Background Music:"))
        self.music_path_edit = QLineEdit()
        self.music_path_edit.setPlaceholderText("Optional: Select audio file for background music")
        self.music_path_edit.setReadOnly(True)
        self.music_path_edit.textChanged.connect(self._on_settings_changed)
        music_layout.addWidget(self.music_path_edit)

        music_browse_btn = QToolButton()
        music_browse_btn.setText("...")
        music_browse_btn.setToolTip("Browse for audio file")
        music_browse_btn.clicked.connect(self._browse_music)
        music_layout.addWidget(music_browse_btn)

        music_clear_btn = QToolButton()
        music_clear_btn.setText("✕")
        music_clear_btn.setToolTip("Clear music selection")
        music_clear_btn.clicked.connect(lambda: self.music_path_edit.clear())
        music_layout.addWidget(music_clear_btn)

        audio_layout.addLayout(music_layout)

        # Volume and fade controls
        volume_layout = QHBoxLayout()

        volume_layout.addWidget(QLabel("Music Volume:"))
        self.music_volume_spin = QSpinBox()
        self.music_volume_spin.setRange(0, 100)
        self.music_volume_spin.setValue(80)
        self.music_volume_spin.setSuffix("%")
        self.music_volume_spin.setToolTip("Background music volume level")
        self.music_volume_spin.valueChanged.connect(self._on_settings_changed)
        volume_layout.addWidget(self.music_volume_spin)

        self.fade_in_check = QCheckBox("Fade In")
        self.fade_in_check.setToolTip("Fade in audio at start")
        self.fade_in_check.stateChanged.connect(self._on_fade_changed)
        volume_layout.addWidget(self.fade_in_check)

        self.fade_in_duration_spin = QDoubleSpinBox()
        self.fade_in_duration_spin.setRange(0.5, 10.0)
        self.fade_in_duration_spin.setSingleStep(0.5)
        self.fade_in_duration_spin.setValue(2.0)
        self.fade_in_duration_spin.setSuffix("s")
        self.fade_in_duration_spin.setEnabled(False)
        self.fade_in_duration_spin.setToolTip("Fade in duration")
        self.fade_in_duration_spin.valueChanged.connect(self._on_settings_changed)
        volume_layout.addWidget(self.fade_in_duration_spin)

        self.fade_out_check = QCheckBox("Fade Out")
        self.fade_out_check.setToolTip("Fade out audio at end")
        self.fade_out_check.stateChanged.connect(self._on_fade_changed)
        volume_layout.addWidget(self.fade_out_check)

        self.fade_out_duration_spin = QDoubleSpinBox()
        self.fade_out_duration_spin.setRange(0.5, 10.0)
        self.fade_out_duration_spin.setSingleStep(0.5)
        self.fade_out_duration_spin.setValue(2.0)
        self.fade_out_duration_spin.setSuffix("s")
        self.fade_out_duration_spin.setEnabled(False)
        self.fade_out_duration_spin.setToolTip("Fade out duration")
        self.fade_out_duration_spin.valueChanged.connect(self._on_settings_changed)
        volume_layout.addWidget(self.fade_out_duration_spin)

        volume_layout.addStretch()
        audio_layout.addLayout(volume_layout)

        audio_group.setLayout(audio_layout)
        group_layout.addWidget(audio_group)

        # Row 3: Transitions and effects
        effects_layout = QHBoxLayout()

        effects_layout.addWidget(QLabel("Transitions:"))
        self.transitions_combo = QComboBox()
        self.transitions_combo.addItems(["None", "Fade", "Dissolve", "Wipe"])
        self.transitions_combo.setCurrentText("Fade")
        self.transitions_combo.setToolTip("Transition effect between clips")
        self.transitions_combo.currentTextChanged.connect(self._on_transition_changed)
        effects_layout.addWidget(self.transitions_combo)

        effects_layout.addWidget(QLabel("Duration:"))
        self.transition_duration_spin = QDoubleSpinBox()
        self.transition_duration_spin.setRange(0.1, 5.0)
        self.transition_duration_spin.setSingleStep(0.1)
        self.transition_duration_spin.setValue(1.0)
        self.transition_duration_spin.setSuffix("s")
        self.transition_duration_spin.setToolTip("Transition duration in seconds")
        self.transition_duration_spin.valueChanged.connect(self._on_settings_changed)
        effects_layout.addWidget(self.transition_duration_spin)

        effects_layout.addStretch()
        group_layout.addLayout(effects_layout)

        # Row 4: Output path
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output:"))
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Select output file path")
        self.output_path_edit.textChanged.connect(self._on_settings_changed)
        output_layout.addWidget(self.output_path_edit)

        output_browse_btn = QToolButton()
        output_browse_btn.setText("...")
        output_browse_btn.setToolTip("Browse for output location")
        output_browse_btn.clicked.connect(self._browse_output)
        output_layout.addWidget(output_browse_btn)

        group_layout.addLayout(output_layout)

        # Export button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.export_btn = QPushButton("Export Video")
        self.export_btn.setToolTip("Export final video with these settings")
        self.export_btn.clicked.connect(self._on_export_clicked)
        self.export_btn.setMinimumWidth(120)
        button_layout.addWidget(self.export_btn)

        group_layout.addLayout(button_layout)

        group.setLayout(group_layout)
        layout.addWidget(group)

    def _on_format_changed(self, format_name: str):
        """Handle format change - update codec options"""
        self._update_codec_options(format_name)
        self._on_settings_changed()

    def _update_codec_options(self, format_name: str):
        """Update codec dropdown based on selected format"""
        self.codec_combo.clear()

        codec_map = {
            "MP4": ["H.264", "H.265/HEVC", "MPEG-4"],
            "MOV": ["H.264", "H.265/HEVC", "ProRes"],
            "AVI": ["H.264", "MJPEG", "Xvid"],
            "WebM": ["VP8", "VP9", "AV1"]
        }

        codecs = codec_map.get(format_name, ["H.264"])
        self.codec_combo.addItems(codecs)

    def _on_quality_changed(self, quality: str):
        """Handle quality preset change"""
        # Show/hide custom bitrate option
        is_custom = quality == "Custom"
        self.bitrate_spin.setVisible(is_custom)
        self._on_settings_changed()

    def _on_fade_changed(self):
        """Handle fade checkbox changes"""
        self.fade_in_duration_spin.setEnabled(self.fade_in_check.isChecked())
        self.fade_out_duration_spin.setEnabled(self.fade_out_check.isChecked())
        self._on_settings_changed()

    def _on_transition_changed(self, transition: str):
        """Handle transition change"""
        # Enable duration control only if transition is not "None"
        self.transition_duration_spin.setEnabled(transition != "None")
        self._on_settings_changed()

    def _browse_music(self):
        """Browse for background music file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Background Music",
            "",
            "Audio Files (*.mp3 *.wav *.aac *.m4a *.ogg *.flac);;All Files (*)"
        )
        if file_path:
            self.music_path_edit.setText(file_path)

    def _browse_output(self):
        """Browse for output file location"""
        default_name = f"exported_video.{self.format_combo.currentText().lower()}"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Exported Video As",
            default_name,
            f"{self.format_combo.currentText()} Files (*.{self.format_combo.currentText().lower()});;All Files (*)"
        )
        if file_path:
            self.output_path_edit.setText(file_path)

    def _on_settings_changed(self):
        """Handle any settings change"""
        self.settings_changed.emit()

    def _on_export_clicked(self):
        """Handle export button click"""
        # Validate output path is set
        if not self.output_path_edit.text():
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Output Path Required",
                "Please specify an output file path before exporting."
            )
            return

        self.export_requested.emit()

    def get_settings(self) -> dict:
        """Get current export settings as a dictionary"""
        return {
            'format': self.format_combo.currentText().lower(),
            'codec': self.codec_combo.currentText(),
            'quality': self.quality_combo.currentText(),
            'bitrate': self.bitrate_spin.value() if self.quality_combo.currentText() == "Custom" else None,
            'background_music': Path(self.music_path_edit.text()) if self.music_path_edit.text() else None,
            'music_volume': self.music_volume_spin.value() / 100.0,  # Convert to 0.0-1.0
            'fade_in': self.fade_in_check.isChecked(),
            'fade_in_duration': self.fade_in_duration_spin.value() if self.fade_in_check.isChecked() else 0,
            'fade_out': self.fade_out_check.isChecked(),
            'fade_out_duration': self.fade_out_duration_spin.value() if self.fade_out_check.isChecked() else 0,
            'transitions': self.transitions_combo.currentText(),
            'transition_duration': self.transition_duration_spin.value() if self.transitions_combo.currentText() != "None" else 0,
            'output_path': Path(self.output_path_edit.text()) if self.output_path_edit.text() else None
        }

    def set_default_output_path(self, path: Path):
        """Set a default output path if none is currently set"""
        if not self.output_path_edit.text():
            self.output_path_edit.setText(str(path))
