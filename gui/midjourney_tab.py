"""Dedicated Midjourney command builder tab for ImageAI - ToS compliant."""

import logging
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QGroupBox, QPushButton, QLabel, QComboBox, QLineEdit,
    QSpinBox, QSlider, QTextEdit, QSplitter, QTabWidget,
    QCheckBox, QDoubleSpinBox, QScrollArea, QMessageBox, QListWidget
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QGuiApplication

logger = logging.getLogger(__name__)


class MidjourneyTab(QWidget):
    """Midjourney command builder tab - generates Discord commands only."""

    # Signals
    commandGenerated = Signal(str)  # Emitted when command is generated

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.last_command = None
        self.command_history = []
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Info banner
        info_banner = QLabel(
            "ℹ️ Midjourney Command Builder - Creates Discord commands for manual use.\n"
            "Commands are copied to clipboard. Paste them in Discord's Midjourney bot channel."
        )
        info_banner.setStyleSheet("""
            QLabel {
                background-color: #5865F2;
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
        """)
        info_banner.setWordWrap(True)
        layout.addWidget(info_banner)

        # Create splitter for main content
        splitter = QSplitter(Qt.Horizontal)

        # Left panel - Parameters
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Model selection
        model_group = QGroupBox("Model")
        model_layout = QVBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.addItems(["v7", "v6.1", "v6", "v5.2", "v5.1", "v5", "niji6", "niji5"])
        self.model_combo.setCurrentText("v7")
        self.model_combo.currentTextChanged.connect(self.update_command)
        model_layout.addWidget(self.model_combo)
        model_group.setLayout(model_layout)
        left_layout.addWidget(model_group)

        # Aspect Ratio
        aspect_group = QGroupBox("Aspect Ratio")
        aspect_layout = QVBoxLayout()
        self.aspect_combo = QComboBox()
        self.aspect_combo.addItems([
            "1:1 (Square)",
            "4:3 (Classic)",
            "3:2 (Print)",
            "16:9 (Widescreen)",
            "21:9 (Ultrawide)",
            "9:16 (Portrait)",
            "2:3 (Vertical)",
            "3:4 (Vertical Classic)",
            "Custom"
        ])
        self.aspect_combo.setCurrentText("1:1 (Square)")
        self.aspect_combo.currentTextChanged.connect(self._on_aspect_changed)
        aspect_layout.addWidget(self.aspect_combo)

        # Custom aspect ratio
        self.custom_ar_widget = QWidget()
        custom_ar_layout = QHBoxLayout(self.custom_ar_widget)
        custom_ar_layout.setContentsMargins(0, 0, 0, 0)
        custom_ar_layout.addWidget(QLabel("W:"))
        self.ar_width_spin = QSpinBox()
        self.ar_width_spin.setRange(1, 100)
        self.ar_width_spin.setValue(16)
        self.ar_width_spin.valueChanged.connect(self.update_command)
        custom_ar_layout.addWidget(self.ar_width_spin)
        custom_ar_layout.addWidget(QLabel("H:"))
        self.ar_height_spin = QSpinBox()
        self.ar_height_spin.setRange(1, 100)
        self.ar_height_spin.setValue(9)
        self.ar_height_spin.valueChanged.connect(self.update_command)
        custom_ar_layout.addWidget(self.ar_height_spin)
        self.custom_ar_widget.setVisible(False)
        aspect_layout.addWidget(self.custom_ar_widget)

        aspect_group.setLayout(aspect_layout)
        left_layout.addWidget(aspect_group)

        # Parameters
        params_group = QGroupBox("Parameters")
        params_layout = QFormLayout()

        # Stylize
        stylize_widget = QWidget()
        stylize_layout = QHBoxLayout(stylize_widget)
        stylize_layout.setContentsMargins(0, 0, 0, 0)
        self.stylize_slider = QSlider(Qt.Horizontal)
        self.stylize_slider.setRange(0, 1000)
        self.stylize_slider.setValue(100)
        self.stylize_slider.valueChanged.connect(self._update_stylize_label)
        stylize_layout.addWidget(self.stylize_slider)
        self.stylize_label = QLabel("100")
        self.stylize_label.setMinimumWidth(40)
        stylize_layout.addWidget(self.stylize_label)
        params_layout.addRow("Stylize:", stylize_widget)

        # Chaos
        chaos_widget = QWidget()
        chaos_layout = QHBoxLayout(chaos_widget)
        chaos_layout.setContentsMargins(0, 0, 0, 0)
        self.chaos_slider = QSlider(Qt.Horizontal)
        self.chaos_slider.setRange(0, 100)
        self.chaos_slider.setValue(0)
        self.chaos_slider.valueChanged.connect(self._update_chaos_label)
        chaos_layout.addWidget(self.chaos_slider)
        self.chaos_label = QLabel("0")
        self.chaos_label.setMinimumWidth(40)
        chaos_layout.addWidget(self.chaos_label)
        params_layout.addRow("Chaos:", chaos_widget)

        # Weird
        weird_widget = QWidget()
        weird_layout = QHBoxLayout(weird_widget)
        weird_layout.setContentsMargins(0, 0, 0, 0)
        self.weird_slider = QSlider(Qt.Horizontal)
        self.weird_slider.setRange(0, 3000)
        self.weird_slider.setValue(0)
        self.weird_slider.valueChanged.connect(self._update_weird_label)
        weird_layout.addWidget(self.weird_slider)
        self.weird_label = QLabel("0")
        self.weird_label.setMinimumWidth(50)
        weird_layout.addWidget(self.weird_label)
        params_layout.addRow("Weird:", weird_widget)

        # Quality
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["0.25", "0.5", "1", "2"])
        self.quality_combo.setCurrentText("1")
        self.quality_combo.currentTextChanged.connect(self.update_command)
        params_layout.addRow("Quality:", self.quality_combo)

        # Seed
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(-1, 2147483647)
        self.seed_spin.setValue(-1)
        self.seed_spin.setSpecialValueText("Random")
        self.seed_spin.valueChanged.connect(self.update_command)
        params_layout.addRow("Seed:", self.seed_spin)

        params_group.setLayout(params_layout)
        left_layout.addWidget(params_group)

        left_layout.addStretch()
        splitter.addWidget(left_widget)

        # Center panel - Prompt and Command
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)

        # Prompt input
        prompt_group = QGroupBox("Prompt")
        prompt_layout = QVBoxLayout()
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText(
            "Enter your Midjourney prompt here...\n\n"
            "Tips:\n"
            "- Be descriptive and specific\n"
            "- Use artistic terms (lighting, style, mood)\n"
            "- Specify camera/lens for photos\n"
            "- Add art style references"
        )
        self.prompt_edit.setMaximumHeight(200)
        self.prompt_edit.textChanged.connect(self.update_command)
        prompt_layout.addWidget(self.prompt_edit)

        # Negative prompt
        neg_layout = QHBoxLayout()
        self.use_negative = QCheckBox("Exclude elements (--no)")
        self.use_negative.toggled.connect(self._toggle_negative)
        neg_layout.addWidget(self.use_negative)
        neg_layout.addStretch()
        prompt_layout.addLayout(neg_layout)

        self.negative_edit = QLineEdit()
        self.negative_edit.setPlaceholderText("e.g., people, cars, text")
        self.negative_edit.setVisible(False)
        self.negative_edit.textChanged.connect(self.update_command)
        prompt_layout.addWidget(self.negative_edit)

        prompt_group.setLayout(prompt_layout)
        center_layout.addWidget(prompt_group)

        # Command output
        command_group = QGroupBox("Generated Command")
        command_layout = QVBoxLayout()

        self.command_display = QTextEdit()
        self.command_display.setReadOnly(True)
        self.command_display.setMaximumHeight(120)
        self.command_display.setFont(QFont("Consolas", 11))
        self.command_display.setStyleSheet("""
            QTextEdit {
                background-color: #2B2D31;
                color: #00D4AA;
                border: 2px solid #5865F2;
                border-radius: 5px;
                padding: 8px;
                selection-background-color: #5865F2;
            }
        """)
        command_layout.addWidget(self.command_display)

        # Command info
        self.command_info = QLabel()
        self.command_info.setStyleSheet("color: gray; font-size: 10px;")
        command_layout.addWidget(self.command_info)

        # Copy button
        button_layout = QHBoxLayout()
        self.copy_button = QPushButton("📋 Copy Command")
        self.copy_button.setStyleSheet("""
            QPushButton {
                background-color: #5865F2;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4752C4;
            }
            QPushButton:pressed {
                background-color: #3B45A0;
            }
        """)
        self.copy_button.clicked.connect(self.copy_command)
        button_layout.addWidget(self.copy_button)

        self.copy_status = QLabel()
        self.copy_status.setStyleSheet("color: #00D4AA; font-weight: bold;")
        button_layout.addWidget(self.copy_status)
        button_layout.addStretch()

        command_layout.addLayout(button_layout)
        command_group.setLayout(command_layout)
        center_layout.addWidget(command_group)

        center_layout.addStretch()
        splitter.addWidget(center_widget)

        # Right panel - Templates and History
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Templates
        templates_group = QGroupBox("Templates")
        templates_layout = QVBoxLayout()

        self.template_combo = QComboBox()
        self.template_combo.addItems([
            "-- Select Template --",
            "📷 Photorealistic",
            "🎬 Cinematic",
            "🎨 Artistic",
            "🏛️ Architecture",
            "📦 Product Photo",
            "🎭 Character Portrait",
            "🌆 Landscape",
            "✨ Fantasy Art",
            "🤖 Sci-Fi",
            "🎌 Anime/Manga"
        ])
        self.template_combo.currentTextChanged.connect(self.apply_template)
        templates_layout.addWidget(self.template_combo)

        templates_group.setLayout(templates_layout)
        right_layout.addWidget(templates_group)

        # History
        history_group = QGroupBox("Command History")
        history_layout = QVBoxLayout()

        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(200)
        self.history_list.itemDoubleClicked.connect(self.restore_from_history)
        history_layout.addWidget(self.history_list)

        clear_btn = QPushButton("Clear History")
        clear_btn.clicked.connect(self.clear_history)
        history_layout.addWidget(clear_btn)

        history_group.setLayout(history_layout)
        right_layout.addWidget(history_group)

        # Tips
        tips_group = QGroupBox("Quick Tips")
        tips_layout = QVBoxLayout()
        tips_text = QLabel(
            "• V7 is the latest model\n"
            "• Lower stylize = more literal\n"
            "• Higher chaos = more variety\n"
            "• Quality 2 = best detail\n"
            "• Use --no to exclude items\n"
            "• Seeds make results repeatable"
        )
        tips_text.setStyleSheet("color: gray; font-size: 11px;")
        tips_text.setWordWrap(True)
        tips_layout.addWidget(tips_text)
        tips_group.setLayout(tips_layout)
        right_layout.addWidget(tips_group)

        right_layout.addStretch()
        splitter.addWidget(right_widget)

        # Set splitter sizes (left: 25%, center: 50%, right: 25%)
        splitter.setSizes([300, 600, 300])

        layout.addWidget(splitter)

    def _on_aspect_changed(self, text):
        """Handle aspect ratio change."""
        self.custom_ar_widget.setVisible("Custom" in text)
        self.update_command()

    def _toggle_negative(self, checked):
        """Toggle negative prompt visibility."""
        self.negative_edit.setVisible(checked)
        self.update_command()

    def _update_stylize_label(self, value):
        """Update stylize label."""
        self.stylize_label.setText(str(value))
        self.update_command()

    def _update_chaos_label(self, value):
        """Update chaos label."""
        self.chaos_label.setText(str(value))
        self.update_command()

    def _update_weird_label(self, value):
        """Update weird label."""
        self.weird_label.setText(str(value))
        self.update_command()

    def update_command(self):
        """Update the command display."""
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            self.command_display.clear()
            self.command_info.clear()
            return

        # Build command
        params = []

        # Add negative prompt
        if self.use_negative.isChecked() and self.negative_edit.text():
            params.append(f"--no {self.negative_edit.text()}")

        # Add aspect ratio
        aspect_text = self.aspect_combo.currentText()
        if "Custom" in aspect_text:
            aspect = f"{self.ar_width_spin.value()}:{self.ar_height_spin.value()}"
        else:
            # Extract ratio from text (e.g., "16:9 (Widescreen)" -> "16:9")
            aspect = aspect_text.split()[0] if aspect_text and aspect_text[0].isdigit() else "1:1"

        if aspect != "1:1":
            params.append(f"--ar {aspect}")

        # Add stylize
        stylize = self.stylize_slider.value()
        if stylize != 100:
            params.append(f"--s {stylize}")

        # Add chaos
        chaos = self.chaos_slider.value()
        if chaos > 0:
            params.append(f"--chaos {chaos}")

        # Add weird
        weird = self.weird_slider.value()
        if weird > 0:
            params.append(f"--weird {weird}")

        # Add quality
        quality = self.quality_combo.currentText()
        if quality != "1":
            params.append(f"--q {quality}")

        # Add seed
        seed = self.seed_spin.value()
        if seed >= 0:
            params.append(f"--seed {seed}")

        # Add version
        model = self.model_combo.currentText()
        if model.startswith("niji"):
            params.append(f"--niji {model.replace('niji', '')}")
        else:
            params.append(f"--v {model.replace('v', '')}")

        # Build full command
        full_prompt = prompt
        if params:
            full_prompt += " " + " ".join(params)

        command = f"/imagine prompt: {full_prompt}"
        self.last_command = command

        # Update display
        self.command_display.setText(command)

        # Update info
        char_count = len(command)
        param_count = len(params)
        self.command_info.setText(
            f"Length: {char_count}/2000 chars | Parameters: {param_count} | Model: {model}"
        )

        # Check length warning
        if char_count > 2000:
            self.command_info.setStyleSheet("color: red; font-size: 10px; font-weight: bold;")
            self.command_info.setText(
                f"⚠️ Command too long: {char_count}/2000 chars (Discord limit)"
            )
        elif char_count > 1800:
            self.command_info.setStyleSheet("color: orange; font-size: 10px;")
        else:
            self.command_info.setStyleSheet("color: gray; font-size: 10px;")

    def copy_command(self):
        """Copy command to clipboard."""
        if not self.last_command:
            return

        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.last_command)

        # Add to history
        self.add_to_history(self.last_command)

        # Show success feedback
        self.copy_status.setText("✅ Copied!")
        QTimer.singleShot(2000, lambda: self.copy_status.clear())

        logger.info(f"Copied Midjourney command: {self.last_command[:100]}...")

    def add_to_history(self, command):
        """Add command to history."""
        # Don't add duplicates
        for i in range(self.history_list.count()):
            if self.history_list.item(i).text() == command:
                return

        # Add to list (newest first)
        self.history_list.insertItem(0, command)

        # Limit history
        while self.history_list.count() > 50:
            self.history_list.takeItem(50)

    def restore_from_history(self, item):
        """Restore command from history."""
        command = item.text()

        # Parse command back to UI
        if command.startswith("/imagine prompt: "):
            # Extract prompt and parameters
            full_text = command[17:]  # Remove "/imagine prompt: "

            # Find where parameters start (look for --)
            import re
            param_match = re.search(r' --', full_text)

            if param_match:
                prompt = full_text[:param_match.start()]
                params_text = full_text[param_match.start():]

                # Parse parameters
                self._parse_parameters(params_text)
            else:
                prompt = full_text

            self.prompt_edit.setText(prompt)

    def _parse_parameters(self, params_text):
        """Parse parameters from command text."""
        import re

        # Parse each parameter
        if "--ar" in params_text:
            match = re.search(r'--ar (\S+)', params_text)
            if match:
                ratio = match.group(1)
                # Try to find in combo
                found = False
                for i in range(self.aspect_combo.count()):
                    if ratio in self.aspect_combo.itemText(i):
                        self.aspect_combo.setCurrentIndex(i)
                        found = True
                        break
                if not found and ":" in ratio:
                    # Custom ratio
                    self.aspect_combo.setCurrentText("Custom")
                    w, h = ratio.split(":")
                    self.ar_width_spin.setValue(int(w))
                    self.ar_height_spin.setValue(int(h))

        if "--s" in params_text:
            match = re.search(r'--s (\d+)', params_text)
            if match:
                self.stylize_slider.setValue(int(match.group(1)))

        if "--chaos" in params_text:
            match = re.search(r'--chaos (\d+)', params_text)
            if match:
                self.chaos_slider.setValue(int(match.group(1)))

        if "--weird" in params_text:
            match = re.search(r'--weird (\d+)', params_text)
            if match:
                self.weird_slider.setValue(int(match.group(1)))

        if "--q" in params_text:
            match = re.search(r'--q ([\d.]+)', params_text)
            if match:
                self.quality_combo.setCurrentText(match.group(1))

        if "--seed" in params_text:
            match = re.search(r'--seed (\d+)', params_text)
            if match:
                self.seed_spin.setValue(int(match.group(1)))

        if "--no" in params_text:
            match = re.search(r'--no ([^-]+)', params_text)
            if match:
                self.use_negative.setChecked(True)
                self.negative_edit.setText(match.group(1).strip())

    def clear_history(self):
        """Clear command history."""
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Clear all command history?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.history_list.clear()

    def apply_template(self, template_name):
        """Apply a template."""
        templates = {
            "📷 Photorealistic": {
                "prompt": "ultra realistic photograph, professional photography, detailed",
                "model": "v7",
                "aspect": "3:2 (Print)",
                "stylize": 50,
                "quality": "2"
            },
            "🎬 Cinematic": {
                "prompt": "cinematic still, film photography, movie scene",
                "model": "v7",
                "aspect": "21:9 (Ultrawide)",
                "stylize": 750,
                "chaos": 30,
                "quality": "1"
            },
            "🎨 Artistic": {
                "prompt": "artistic interpretation, painterly style",
                "model": "v7",
                "aspect": "4:3 (Classic)",
                "stylize": 1000,
                "weird": 500
            },
            "🏛️ Architecture": {
                "prompt": "architectural photography, building exterior",
                "model": "v7",
                "aspect": "16:9 (Widescreen)",
                "stylize": 100,
                "quality": "2"
            },
            "📦 Product Photo": {
                "prompt": "product photography, white background, commercial",
                "model": "v7",
                "aspect": "1:1 (Square)",
                "stylize": 20,
                "quality": "2"
            },
            "🎌 Anime/Manga": {
                "prompt": "anime art style, manga illustration",
                "model": "niji6",
                "aspect": "2:3 (Vertical)",
                "stylize": 180
            }
        }

        if template_name in templates:
            template = templates[template_name]

            # Don't overwrite existing prompt, prepend template
            current_prompt = self.prompt_edit.toPlainText().strip()
            if current_prompt:
                self.prompt_edit.setText(f"{template['prompt']}, {current_prompt}")
            else:
                self.prompt_edit.setText(template['prompt'])

            # Apply settings
            if "model" in template:
                idx = self.model_combo.findText(template["model"])
                if idx >= 0:
                    self.model_combo.setCurrentIndex(idx)

            if "aspect" in template:
                for i in range(self.aspect_combo.count()):
                    if template["aspect"] in self.aspect_combo.itemText(i):
                        self.aspect_combo.setCurrentIndex(i)
                        break

            if "stylize" in template:
                self.stylize_slider.setValue(template["stylize"])

            if "chaos" in template:
                self.chaos_slider.setValue(template.get("chaos", 0))

            if "weird" in template:
                self.weird_slider.setValue(template.get("weird", 0))

            if "quality" in template:
                self.quality_combo.setCurrentText(template["quality"])

    def load_settings(self):
        """Load saved settings."""
        if not self.config:
            return

        settings = self.config.get("midjourney_tab_settings", {})

        # Restore last used values
        if "model" in settings:
            idx = self.model_combo.findText(settings["model"])
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)

        if "quality" in settings:
            self.quality_combo.setCurrentText(settings["quality"])

    def save_settings(self):
        """Save current settings."""
        if not self.config:
            return

        settings = {
            "model": self.model_combo.currentText(),
            "quality": self.quality_combo.currentText()
        }

        self.config.set("midjourney_tab_settings", settings)
        self.config.save()