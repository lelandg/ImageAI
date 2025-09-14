"""Upscaling options widget for ImageAI."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QRadioButton, QButtonGroup, QLabel, QCheckBox,
    QPushButton, QComboBox, QMessageBox
)
from PySide6.QtCore import Signal
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class UpscalingSelector(QWidget):
    """Widget for selecting upscaling options when target resolution exceeds provider output."""

    upscalingChanged = Signal(dict)

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.setVisible(False)  # Hidden by default

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Main group box
        self.group = QGroupBox("Image Upscaling")
        group_layout = QVBoxLayout(self.group)

        # Info label
        self.info_label = QLabel("Target resolution exceeds provider capabilities. Choose upscaling method:")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #ff9900; padding: 5px;")
        group_layout.addWidget(self.info_label)

        # Method selection
        self.method_group = QButtonGroup()

        # None option
        self.none_radio = QRadioButton("No upscaling (keep original size)")
        self.none_radio.setToolTip("Use the image at its generated resolution")
        self.method_group.addButton(self.none_radio, 0)
        group_layout.addWidget(self.none_radio)

        # Lanczos option
        self.lanczos_radio = QRadioButton("Lanczos (fast, good quality)")
        self.lanczos_radio.setToolTip("Traditional high-quality resampling. Fast and reliable.")
        self.method_group.addButton(self.lanczos_radio, 1)
        group_layout.addWidget(self.lanczos_radio)

        # Real-ESRGAN option with install button
        self.realesrgan_container = QWidget()
        realesrgan_main_layout = QVBoxLayout(self.realesrgan_container)
        realesrgan_main_layout.setContentsMargins(0, 0, 0, 0)
        realesrgan_main_layout.setSpacing(5)

        # Radio button
        self.realesrgan_radio = QRadioButton("Real-ESRGAN AI (best quality, slower)")
        self.realesrgan_radio.setToolTip("AI-powered upscaling. Excellent quality but requires model download.")
        self.method_group.addButton(self.realesrgan_radio, 2)
        realesrgan_main_layout.addWidget(self.realesrgan_radio)

        # Install container (initially hidden)
        self.install_container = QWidget()
        install_layout = QHBoxLayout(self.install_container)
        install_layout.setContentsMargins(20, 0, 0, 0)

        install_info = QLabel("ℹ️ AI-powered upscaling for best quality")
        install_info.setStyleSheet("color: #888; font-size: 11px;")
        install_layout.addWidget(install_info)

        self.install_btn = QPushButton("Install AI Upscaling (~7GB)")
        self.install_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.install_btn.clicked.connect(self._on_install_clicked)
        install_layout.addWidget(self.install_btn)
        install_layout.addStretch()

        self.install_container.setVisible(False)
        realesrgan_main_layout.addWidget(self.install_container)

        group_layout.addWidget(self.realesrgan_container)

        # Stability API option
        self.stability_radio = QRadioButton("Stability AI API (cloud, uses credits)")
        self.stability_radio.setToolTip("Professional cloud upscaling. Requires API key and uses credits.")
        self.method_group.addButton(self.stability_radio, 3)
        group_layout.addWidget(self.stability_radio)

        # Default to Lanczos
        self.lanczos_radio.setChecked(True)

        # Real-ESRGAN model selection (initially hidden)
        self.esrgan_model_widget = QWidget()
        esrgan_layout = QHBoxLayout(self.esrgan_model_widget)
        esrgan_layout.setContentsMargins(40, 0, 0, 0)  # More indent for model selection
        esrgan_layout.addWidget(QLabel("Model:"))

        self.esrgan_model_combo = QComboBox()
        self.esrgan_model_combo.addItems([
            "RealESRGAN_x4plus",
            "RealESRGAN_x4plus_anime",
            "RealESRGAN_x2plus"
        ])
        esrgan_layout.addWidget(self.esrgan_model_combo)
        esrgan_layout.addStretch()

        self.esrgan_model_widget.setVisible(False)
        group_layout.addWidget(self.esrgan_model_widget)

        # Resolution info
        self.resolution_info = QLabel()
        self.resolution_info.setStyleSheet("color: #888; font-size: 10px; padding: 5px;")
        group_layout.addWidget(self.resolution_info)

        # Connect signals
        self.method_group.buttonClicked.connect(self._on_method_changed)
        self.esrgan_model_combo.currentTextChanged.connect(self._on_settings_changed)

        layout.addWidget(self.group)

    def _on_method_changed(self):
        """Handle method selection change."""
        # Show/hide Real-ESRGAN options
        method_id = self.method_group.checkedId()
        self.esrgan_model_widget.setVisible(method_id == 2)

        self._on_settings_changed()

    def _on_settings_changed(self):
        """Emit signal when settings change."""
        settings = self.get_settings()
        self.upscalingChanged.emit(settings)

    def update_resolution_info(self, current_width: int, current_height: int,
                             target_width: int, target_height: int):
        """Update the resolution information display."""
        if current_width and current_height and target_width and target_height:
            scale_factor = max(target_width / current_width, target_height / current_height)
            self.resolution_info.setText(
                f"Current: {current_width}×{current_height} → "
                f"Target: {target_width}×{target_height} "
                f"(×{scale_factor:.1f} upscaling)"
            )

            # Show the widget if upscaling is needed
            needs_upscaling = current_width < target_width or current_height < target_height
            self.setVisible(needs_upscaling)

            if needs_upscaling:
                self.info_label.setText(
                    f"Target resolution ({target_width}×{target_height}) exceeds "
                    f"provider output ({current_width}×{current_height}). "
                    f"Choose upscaling method:"
                )
        else:
            self.setVisible(False)

    def get_settings(self) -> dict:
        """Get current upscaling settings."""
        method_id = self.method_group.checkedId()

        method_map = {
            0: "none",
            1: "lanczos",
            2: "realesrgan",
            3: "stability_api"
        }

        settings = {
            "method": method_map.get(method_id, "lanczos"),
            "enabled": method_id != 0
        }

        # Add Real-ESRGAN specific settings
        if method_id == 2:
            settings["model_name"] = self.esrgan_model_combo.currentText()

        return settings

    def set_enabled_methods(self, lanczos=True, realesrgan=False, stability=False):
        """Enable/disable specific upscaling methods based on availability."""
        self.lanczos_radio.setEnabled(lanczos)
        self.realesrgan_radio.setEnabled(realesrgan)
        self.stability_radio.setEnabled(stability)

        # Show install button if Real-ESRGAN not available
        if not realesrgan:
            self.install_container.setVisible(True)
            self.realesrgan_radio.setToolTip(
                "Real-ESRGAN not installed. Click 'Install AI Upscaling' to enable."
            )
        else:
            self.install_container.setVisible(False)
            self.realesrgan_radio.setToolTip(
                "AI-powered upscaling. Excellent quality for significant upscaling."
            )

        if not stability:
            self.stability_radio.setToolTip(
                "Stability AI API requires API key configuration in Settings"
            )

    def check_realesrgan_availability(self) -> bool:
        """Check if Real-ESRGAN is available."""
        try:
            # First check if PyTorch is available
            import torch
            import torchvision

            # Patch the import issue if needed
            import sys
            if 'torchvision.transforms.functional_tensor' not in sys.modules:
                # Create a mock module to handle the old import path
                from torchvision.transforms import functional
                sys.modules['torchvision.transforms.functional_tensor'] = functional

            # Now try importing Real-ESRGAN
            import realesrgan
            return True
        except ImportError:
            return False

    def check_stability_api_availability(self, config) -> bool:
        """Check if Stability API is configured."""
        return bool(config.get_api_key("stability"))

    def _on_install_clicked(self):
        """Handle install button click."""
        from gui.install_dialog import InstallConfirmDialog, InstallProgressDialog

        # Show confirmation dialog
        confirm_dlg = InstallConfirmDialog(self)
        if confirm_dlg.exec():
            # Show progress dialog and start installation
            progress_dlg = InstallProgressDialog(self)
            progress_dlg.installation_complete.connect(self._on_installation_complete)
            progress_dlg.start_installation()
            progress_dlg.exec()

    def _on_installation_complete(self, success: bool, message: str):
        """Handle installation completion."""
        if success:
            # Check if Real-ESRGAN is now available
            if self.check_realesrgan_availability():
                # Update UI
                self.set_enabled_methods(
                    lanczos=True,
                    realesrgan=True,
                    stability=self.stability_radio.isEnabled()
                )

                # Show success message
                QMessageBox.information(
                    self,
                    "Installation Complete",
                    "Real-ESRGAN AI upscaling has been installed successfully!\n"
                    "You can now use AI upscaling for best quality results."
                )
            else:
                # Installation succeeded but still not detected
                QMessageBox.warning(
                    self,
                    "Restart Required",
                    "Installation complete. Please restart ImageAI to enable AI upscaling."
                )
        else:
            # Installation failed
            QMessageBox.critical(
                self,
                "Installation Failed",
                f"Failed to install AI upscaling:\n{message}\n\n"
                "You can try installing manually with:\n"
                "pip install basicsr realesrgan opencv-python"
            )