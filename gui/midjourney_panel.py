"""Midjourney provider panel widget for custom UI controls."""

import logging
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QPushButton, QLabel, QComboBox,
    QSpinBox, QSlider, QLineEdit, QRadioButton,
    QButtonGroup, QTextEdit, QCheckBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)


class MidjourneyPanel(QWidget):
    """Custom panel for Midjourney-specific controls."""

    # Signals
    settingsChanged = Signal(dict)  # Emitted when any setting changes
    openDiscord = Signal()           # Open Discord to paste command

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.settings = {}
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Info box
        info_label = QLabel("ℹ️ Midjourney Manual Mode")
        info_label.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(info_label)

        info_text = QLabel("This will generate a Discord command that you can paste into Midjourney.\nThe command will be copied to your clipboard automatically.")
        info_text.setWordWrap(True)
        info_text.setStyleSheet("color: gray; padding: 5px 5px 10px 5px;")
        layout.addWidget(info_text)

        # Midjourney Parameters
        params_group = QGroupBox("Midjourney Parameters")
        params_layout = QFormLayout()

        # Model Version
        self.version_combo = QComboBox()
        self.version_combo.addItems(["v7", "v6.1", "v6", "v5.2", "v5.1", "v5", "niji6", "niji5"])
        self.version_combo.setCurrentText("v7")
        params_layout.addRow("Version:", self.version_combo)

        # Aspect Ratio (for future use)
        aspect_widget = QWidget()
        aspect_layout = QHBoxLayout(aspect_widget)
        aspect_layout.setContentsMargins(0, 0, 0, 0)

        self.aspect_combo = QComboBox()
        self.aspect_combo.addItems(["1:1", "4:3", "3:2", "16:9", "2:3", "3:4", "9:16"])
        aspect_layout.addWidget(self.aspect_combo)

        aspect_note = QLabel("(Coming soon)")
        aspect_note.setStyleSheet("color: gray; font-style: italic;")
        aspect_layout.addWidget(aspect_note)
        aspect_layout.addStretch()

        self.aspect_combo.setEnabled(False)  # Disabled for now
        params_layout.addRow("Aspect Ratio:", aspect_widget)

        # Stylize
        self.stylize_slider = QSlider(Qt.Horizontal)
        self.stylize_slider.setRange(0, 1000)
        self.stylize_slider.setValue(100)
        self.stylize_slider.setTickInterval(100)
        self.stylize_slider.setTickPosition(QSlider.TicksBelow)
        self.stylize_label = QLabel("100")
        stylize_widget = QWidget()
        stylize_layout = QHBoxLayout(stylize_widget)
        stylize_layout.setContentsMargins(0, 0, 0, 0)
        stylize_layout.addWidget(self.stylize_slider)
        stylize_layout.addWidget(self.stylize_label)
        params_layout.addRow("Stylize:", stylize_widget)

        # Chaos
        self.chaos_slider = QSlider(Qt.Horizontal)
        self.chaos_slider.setRange(0, 100)
        self.chaos_slider.setValue(0)
        self.chaos_slider.setTickInterval(10)
        self.chaos_slider.setTickPosition(QSlider.TicksBelow)
        self.chaos_label = QLabel("0")
        chaos_widget = QWidget()
        chaos_layout = QHBoxLayout(chaos_widget)
        chaos_layout.setContentsMargins(0, 0, 0, 0)
        chaos_layout.addWidget(self.chaos_slider)
        chaos_layout.addWidget(self.chaos_label)
        params_layout.addRow("Chaos:", chaos_widget)

        # Weird
        self.weird_slider = QSlider(Qt.Horizontal)
        self.weird_slider.setRange(0, 3000)
        self.weird_slider.setValue(0)
        self.weird_slider.setTickInterval(250)
        self.weird_slider.setTickPosition(QSlider.TicksBelow)
        self.weird_label = QLabel("0")
        weird_widget = QWidget()
        weird_layout = QHBoxLayout(weird_widget)
        weird_layout.setContentsMargins(0, 0, 0, 0)
        weird_layout.addWidget(self.weird_slider)
        weird_layout.addWidget(self.weird_label)
        params_layout.addRow("Weird:", weird_widget)

        # Quality
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["0.25", "0.5", "1", "2"])
        self.quality_combo.setCurrentText("1")
        params_layout.addRow("Quality:", self.quality_combo)

        # Seed (optional)
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(-1, 2147483647)
        self.seed_spin.setValue(-1)
        self.seed_spin.setSpecialValueText("Random")
        self.seed_spin.setSuffix(" (-1 for random)")
        params_layout.addRow("Seed:", self.seed_spin)

        params_group.setLayout(params_layout)
        layout.addWidget(params_group)

        # Discord Command Display
        self.command_group = QGroupBox("Discord Command")
        command_layout = QVBoxLayout()

        self.command_display = QTextEdit()
        self.command_display.setReadOnly(True)
        self.command_display.setMaximumHeight(80)
        self.command_display.setFont(QFont("Consolas", 10))
        self.command_display.setStyleSheet("""
            QTextEdit {
                background-color: #40444B;
                color: #7289DA;
                border: 2px solid #7289DA;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        command_layout.addWidget(self.command_display)

        # Note about automatic copy
        note_label = QLabel("Command is automatically copied when you generate an image")
        note_label.setStyleSheet("color: #7289DA; font-style: italic; padding: 5px;")
        command_layout.addWidget(note_label)
        self.command_group.setLayout(command_layout)
        layout.addWidget(self.command_group)

        # Status/Info
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: gray; padding: 5px;")
        layout.addWidget(self.status_label)

        layout.addStretch()

        # Connect signals
        self.stylize_slider.valueChanged.connect(lambda v: self.stylize_label.setText(str(v)))
        self.chaos_slider.valueChanged.connect(lambda v: self.chaos_label.setText(str(v)))
        self.weird_slider.valueChanged.connect(lambda v: self.weird_label.setText(str(v)))

        # Connect all controls to settings changed
        self.version_combo.currentTextChanged.connect(self.on_settings_changed)
        self.aspect_combo.currentTextChanged.connect(self.on_settings_changed)
        self.stylize_slider.valueChanged.connect(self.on_settings_changed)
        self.chaos_slider.valueChanged.connect(self.on_settings_changed)
        self.weird_slider.valueChanged.connect(self.on_settings_changed)
        self.quality_combo.currentTextChanged.connect(self.on_settings_changed)
        self.seed_spin.valueChanged.connect(self.on_settings_changed)


    def on_settings_changed(self):
        """Collect all settings and emit signal."""
        self.settings = self.get_settings()
        self.settingsChanged.emit(self.settings)

    def get_settings(self) -> Dict[str, Any]:
        """Get current Midjourney settings."""
        settings = {
            'mode': 'manual',  # Always manual mode now
            'model_version': self.version_combo.currentText(),
            'aspect_ratio': self.aspect_combo.currentText(),
            'stylize': self.stylize_slider.value(),
            'chaos': self.chaos_slider.value(),
            'weird': self.weird_slider.value(),
            'quality': float(self.quality_combo.currentText()),
            'seed': self.seed_spin.value() if self.seed_spin.value() >= 0 else None,
        }

        return settings

    def set_settings(self, settings: Dict[str, Any]):
        """Apply settings to UI."""
        # Mode is always manual now, skip mode setting

        if 'model_version' in settings:
            idx = self.version_combo.findText(settings['model_version'])
            if idx >= 0:
                self.version_combo.setCurrentIndex(idx)

        if 'aspect_ratio' in settings:
            idx = self.aspect_combo.findText(settings['aspect_ratio'])
            if idx >= 0:
                self.aspect_combo.setCurrentIndex(idx)

        if 'stylize' in settings:
            self.stylize_slider.setValue(settings['stylize'])

        if 'chaos' in settings:
            self.chaos_slider.setValue(settings['chaos'])

        if 'weird' in settings:
            self.weird_slider.setValue(settings['weird'])

        if 'quality' in settings:
            idx = self.quality_combo.findText(str(settings['quality']))
            if idx >= 0:
                self.quality_combo.setCurrentIndex(idx)

        if 'seed' in settings:
            self.seed_spin.setValue(settings['seed'] if settings['seed'] else -1)

    def update_command(self, prompt: str):
        """Update the Discord command display."""
        if not prompt:
            self.command_display.clear()
            return

        # Build command
        params = []

        if self.aspect_combo.isEnabled() and self.aspect_combo.currentText() != '1:1':
            params.append(f'--ar {self.aspect_combo.currentText()}')

        if self.stylize_slider.value() != 100:
            params.append(f'--stylize {self.stylize_slider.value()}')

        if self.chaos_slider.value() > 0:
            params.append(f'--chaos {self.chaos_slider.value()}')

        if self.weird_slider.value() > 0:
            params.append(f'--weird {self.weird_slider.value()}')

        if self.quality_combo.currentText() != '1':
            params.append(f'--q {self.quality_combo.currentText()}')

        if self.seed_spin.value() >= 0:
            params.append(f'--seed {self.seed_spin.value()}')

        # Add version parameter (always specify for clarity)
        version = self.version_combo.currentText()
        if version.startswith('niji'):
            params.append(f'--niji {version.replace("niji", "")}')
        else:
            params.append(f'--v {version.replace("v", "")}')

        full_prompt = f"{prompt} {' '.join(params)}".strip()
        command = f"/imagine {full_prompt}"

        self.command_display.setText(command)



    def load_settings(self):
        """Load settings from config."""
        if not self.config:
            return

        settings = self.config.config.get('midjourney_settings', {})
        self.set_settings(settings)

    def save_settings(self):
        """Save settings to config."""
        if not self.config:
            return

        self.config.set('midjourney_settings', self.get_settings())