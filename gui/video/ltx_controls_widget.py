"""
LTX-Video Controls Widget

This widget provides LTX-Video specific controls including:
- Deployment mode selection (Local GPU, Fal API, Replicate API, ComfyUI)
- Model selection (Fast, Pro, Ultra)
- FPS selector
- Camera motion controls
- Audio prompt input
- Advanced settings (LoRA, guidance, inference steps, seed, webhook)
"""

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QSlider,
    QFileDialog, QToolButton
)
from PySide6.QtCore import Qt, Signal

from core.config import ConfigManager


class LTXVideoControlsWidget(QWidget):
    """Widget for LTX-Video specific controls"""

    # Signals
    deployment_changed = Signal(str)  # deployment mode
    model_changed = Signal(str)  # model name
    fps_changed = Signal(int)  # FPS value
    settings_changed = Signal()  # Any setting changed

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Main controls group
        main_group = QGroupBox("LTX-Video Settings")
        main_layout = QVBoxLayout()

        # Row 1: Deployment mode and Model
        row1 = QHBoxLayout()

        # Deployment mode
        row1.addWidget(QLabel("Deployment:"))
        self.deployment_combo = QComboBox()
        self.deployment_combo.addItems([
            "Local GPU (Free)",
            "Fal API",
            "Replicate API",
            "ComfyUI"
        ])
        self.deployment_combo.setToolTip(
            "LTX-Video deployment mode:\n"
            "- Local GPU: Free, unlimited generation (requires RTX 4090+)\n"
            "- Fal API: Cloud API ($0.04-$0.16/second)\n"
            "- Replicate API: Alternative cloud option\n"
            "- ComfyUI: Integration with ComfyUI workflow"
        )
        self.deployment_combo.currentTextChanged.connect(self._on_deployment_changed)
        row1.addWidget(self.deployment_combo)

        # Model selection
        row1.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "ltx-video-2b (Fast)",
            "ltx-video-13b (High Quality)",
            "ltx-2-fast (Future)",
            "ltx-2-pro (Future)",
            "ltx-2-ultra (Future - 4K)"
        ])
        self.model_combo.setToolTip(
            "LTX-Video model:\n"
            "- 2B: Fast generation, good quality\n"
            "- 13B: Slower, higher quality\n"
            "- LTX-2 models: Coming soon with 4K, 50fps support"
        )
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        row1.addWidget(self.model_combo)

        row1.addStretch()
        main_layout.addLayout(row1)

        # Row 2: FPS and Camera Motion
        row2 = QHBoxLayout()

        # FPS selector
        row2.addWidget(QLabel("FPS:"))
        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["24", "30", "50"])
        self.fps_combo.setCurrentText("30")
        self.fps_combo.setToolTip(
            "Frames per second:\n"
            "- 24: Cinema standard\n"
            "- 30: Video standard\n"
            "- 50: High framerate (LTX-2 Pro/Ultra only)"
        )
        self.fps_combo.currentTextChanged.connect(self._on_fps_changed)
        row2.addWidget(self.fps_combo)

        # Camera motion
        row2.addWidget(QLabel("Camera Motion:"))
        self.camera_motion_combo = QComboBox()
        self.camera_motion_combo.addItems([
            "None",
            "Pan Left",
            "Pan Right",
            "Zoom In",
            "Zoom Out",
            "Orbit",
            "Dolly Forward",
            "Dolly Backward",
            "Crane Up",
            "Crane Down"
        ])
        self.camera_motion_combo.setToolTip("Add camera motion to the generated video")
        self.camera_motion_combo.currentTextChanged.connect(self._on_camera_motion_changed)
        row2.addWidget(self.camera_motion_combo)

        # Camera speed
        row2.addWidget(QLabel("Speed:"))
        self.camera_speed_spin = QDoubleSpinBox()
        self.camera_speed_spin.setRange(0.5, 2.0)
        self.camera_speed_spin.setSingleStep(0.1)
        self.camera_speed_spin.setValue(1.0)
        self.camera_speed_spin.setSuffix("×")
        self.camera_speed_spin.setToolTip("Camera motion speed multiplier")
        self.camera_speed_spin.setEnabled(False)  # Disabled until camera motion selected
        self.camera_speed_spin.valueChanged.connect(self._on_settings_changed)
        row2.addWidget(self.camera_speed_spin)

        row2.addStretch()
        main_layout.addLayout(row2)

        # Row 3: Audio prompt
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Audio Prompt:"))
        self.audio_prompt_edit = QLineEdit()
        self.audio_prompt_edit.setPlaceholderText("Optional: Describe audio/sound effects for the video")
        self.audio_prompt_edit.setToolTip("Separate audio description (LTX-2 only)")
        self.audio_prompt_edit.textChanged.connect(self._on_settings_changed)
        row3.addWidget(self.audio_prompt_edit)
        main_layout.addLayout(row3)

        main_group.setLayout(main_layout)
        layout.addWidget(main_group)

        # Advanced settings group (collapsible)
        self.advanced_group = QGroupBox("Advanced Settings")
        self.advanced_group.setCheckable(True)
        self.advanced_group.setChecked(False)
        advanced_layout = QVBoxLayout()

        # LoRA weights
        lora_layout = QHBoxLayout()
        lora_layout.addWidget(QLabel("LoRA Weights:"))
        self.lora_path_edit = QLineEdit()
        self.lora_path_edit.setPlaceholderText("Optional: Path to custom LoRA weights")
        self.lora_path_edit.setReadOnly(True)
        self.lora_path_edit.textChanged.connect(self._on_settings_changed)
        lora_layout.addWidget(self.lora_path_edit)

        lora_browse_btn = QToolButton()
        lora_browse_btn.setText("...")
        lora_browse_btn.setToolTip("Browse for LoRA weights file")
        lora_browse_btn.clicked.connect(self._browse_lora)
        lora_layout.addWidget(lora_browse_btn)

        advanced_layout.addLayout(lora_layout)

        # LoRA scale
        lora_scale_layout = QHBoxLayout()
        lora_scale_layout.addWidget(QLabel("LoRA Scale:"))
        self.lora_scale_spin = QDoubleSpinBox()
        self.lora_scale_spin.setRange(0.0, 2.0)
        self.lora_scale_spin.setSingleStep(0.1)
        self.lora_scale_spin.setValue(1.0)
        self.lora_scale_spin.setToolTip("LoRA weight scaling factor")
        self.lora_scale_spin.valueChanged.connect(self._on_settings_changed)
        lora_scale_layout.addWidget(self.lora_scale_spin)
        lora_scale_layout.addStretch()
        advanced_layout.addLayout(lora_scale_layout)

        # Guidance scale
        guidance_layout = QHBoxLayout()
        guidance_layout.addWidget(QLabel("Guidance Scale:"))
        self.guidance_scale_spin = QDoubleSpinBox()
        self.guidance_scale_spin.setRange(1.0, 20.0)
        self.guidance_scale_spin.setSingleStep(0.5)
        self.guidance_scale_spin.setValue(7.5)
        self.guidance_scale_spin.setToolTip("CFG scale - higher values follow prompt more closely")
        self.guidance_scale_spin.valueChanged.connect(self._on_settings_changed)
        guidance_layout.addWidget(self.guidance_scale_spin)
        guidance_layout.addStretch()
        advanced_layout.addLayout(guidance_layout)

        # Inference steps
        steps_layout = QHBoxLayout()
        steps_layout.addWidget(QLabel("Inference Steps:"))
        self.inference_steps_spin = QSpinBox()
        self.inference_steps_spin.setRange(20, 100)
        self.inference_steps_spin.setSingleStep(5)
        self.inference_steps_spin.setValue(50)
        self.inference_steps_spin.setToolTip("Number of denoising steps - higher is slower but better quality")
        self.inference_steps_spin.valueChanged.connect(self._on_settings_changed)
        steps_layout.addWidget(self.inference_steps_spin)
        steps_layout.addStretch()
        advanced_layout.addLayout(steps_layout)

        # Seed
        seed_layout = QHBoxLayout()
        seed_layout.addWidget(QLabel("Seed:"))
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(-1, 2147483647)
        self.seed_spin.setValue(-1)
        self.seed_spin.setSpecialValueText("Random")
        self.seed_spin.setToolTip("Random seed (-1 for random)")
        self.seed_spin.valueChanged.connect(self._on_settings_changed)
        seed_layout.addWidget(self.seed_spin)
        seed_layout.addStretch()
        advanced_layout.addLayout(seed_layout)

        # Webhook URL (for async notifications)
        webhook_layout = QHBoxLayout()
        webhook_layout.addWidget(QLabel("Webhook URL:"))
        self.webhook_edit = QLineEdit()
        self.webhook_edit.setPlaceholderText("Optional: Webhook for async notifications")
        self.webhook_edit.setToolTip("Webhook URL for generation completion notifications")
        self.webhook_edit.textChanged.connect(self._on_settings_changed)
        webhook_layout.addWidget(self.webhook_edit)
        advanced_layout.addLayout(webhook_layout)

        self.advanced_group.setLayout(advanced_layout)
        layout.addWidget(self.advanced_group)

    def _on_deployment_changed(self, deployment: str):
        """Handle deployment mode change"""
        # Extract deployment mode (remove the display text suffix)
        mode_map = {
            "Local GPU (Free)": "local",
            "Fal API": "fal",
            "Replicate API": "replicate",
            "ComfyUI": "comfyui"
        }
        mode = mode_map.get(deployment, "local")
        self.config.set_ltx_deployment(mode)
        self.deployment_changed.emit(mode)
        self._on_settings_changed()

    def _on_model_changed(self, model: str):
        """Handle model change"""
        # Extract model name (remove the display text suffix)
        model_map = {
            "ltx-video-2b (Fast)": "ltx-video-2b",
            "ltx-video-13b (High Quality)": "ltx-video-13b",
            "ltx-2-fast (Future)": "ltx-2-fast",
            "ltx-2-pro (Future)": "ltx-2-pro",
            "ltx-2-ultra (Future - 4K)": "ltx-2-ultra"
        }
        model_name = model_map.get(model, "ltx-video-2b")
        self.config.set_ltx_model(model_name)
        self.model_changed.emit(model_name)
        self._on_settings_changed()

    def _on_fps_changed(self, fps: str):
        """Handle FPS change"""
        fps_value = int(fps)
        self.config.set_ltx_fps(fps_value)
        self.fps_changed.emit(fps_value)
        self._on_settings_changed()

    def _on_camera_motion_changed(self, motion: str):
        """Handle camera motion change"""
        # Enable speed control only if motion is not "None"
        self.camera_speed_spin.setEnabled(motion != "None")

        # Save to config
        if motion == "None":
            self.config.set_ltx_camera_motion(None)
        else:
            # Convert display name to API format
            motion_api = motion.lower().replace(" ", "_")
            self.config.set_ltx_camera_motion(motion_api)

        self._on_settings_changed()

    def _browse_lora(self):
        """Browse for LoRA weights file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select LoRA Weights File",
            "",
            "LoRA Files (*.safetensors *.pt *.pth);;All Files (*)"
        )
        if file_path:
            self.lora_path_edit.setText(file_path)

    def _on_settings_changed(self):
        """Handle any settings change"""
        self.settings_changed.emit()

    def _load_settings(self):
        """Load settings from config"""
        # Deployment mode
        deployment = self.config.get_ltx_deployment()
        deployment_map = {
            "local": "Local GPU (Free)",
            "fal": "Fal API",
            "replicate": "Replicate API",
            "comfyui": "ComfyUI"
        }
        deployment_text = deployment_map.get(deployment, "Local GPU (Free)")
        index = self.deployment_combo.findText(deployment_text)
        if index >= 0:
            self.deployment_combo.setCurrentIndex(index)

        # Model
        model = self.config.get_ltx_model()
        model_map = {
            "ltx-video-2b": "ltx-video-2b (Fast)",
            "ltx-video-13b": "ltx-video-13b (High Quality)",
            "ltx-2-fast": "ltx-2-fast (Future)",
            "ltx-2-pro": "ltx-2-pro (Future)",
            "ltx-2-ultra": "ltx-2-ultra (Future - 4K)"
        }
        model_text = model_map.get(model, "ltx-video-2b (Fast)")
        index = self.model_combo.findText(model_text)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)

        # FPS
        fps = self.config.get_ltx_fps()
        self.fps_combo.setCurrentText(str(fps))

        # Camera motion
        camera_motion = self.config.get_ltx_camera_motion()
        if camera_motion:
            # Convert API format to display name
            motion_display = camera_motion.replace("_", " ").title()
            index = self.camera_motion_combo.findText(motion_display)
            if index >= 0:
                self.camera_motion_combo.setCurrentIndex(index)

        # Guidance scale
        guidance = self.config.get_ltx_guidance_scale()
        self.guidance_scale_spin.setValue(guidance)

        # Inference steps
        steps = self.config.get_ltx_num_inference_steps()
        self.inference_steps_spin.setValue(steps)

    def get_settings(self) -> dict:
        """Get current LTX settings as a dictionary"""
        return {
            'deployment': self.config.get_ltx_deployment(),
            'model': self.config.get_ltx_model(),
            'fps': self.config.get_ltx_fps(),
            'camera_motion': self.config.get_ltx_camera_motion(),
            'camera_speed': self.camera_speed_spin.value() if self.camera_speed_spin.isEnabled() else 1.0,
            'audio_prompt': self.audio_prompt_edit.text() or None,
            'lora_weights': Path(self.lora_path_edit.text()) if self.lora_path_edit.text() else None,
            'lora_scale': self.lora_scale_spin.value(),
            'guidance_scale': self.guidance_scale_spin.value(),
            'num_inference_steps': self.inference_steps_spin.value(),
            'seed': self.seed_spin.value() if self.seed_spin.value() >= 0 else None,
            'webhook_url': self.webhook_edit.text() or None
        }
