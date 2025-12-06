"""Installation dialogs for MuseTalk lip-sync feature."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QProgressBar, QMessageBox, QApplication,
    QSystemTrayIcon, QGroupBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QTextCursor
from pathlib import Path
from datetime import datetime
import sys
import time
import logging

from core.package_installer import detect_nvidia_gpu, check_disk_space
from core.musetalk_installer import (
    MuseTalkPackageInstaller, MuseTalkModelDownloader,
    get_musetalk_packages, check_musetalk_installed,
    get_musetalk_disk_space_required, get_musetalk_model_path
)

logger = logging.getLogger(__name__)


class MuseTalkInstallConfirmDialog(QDialog):
    """Confirmation dialog before MuseTalk installation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Install MuseTalk Lip-Sync")
        self.setModal(True)
        self.setMinimumWidth(550)
        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Install MuseTalk Lip-Sync")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Information
        info_group = QGroupBox("Installation Details")
        info_layout = QVBoxLayout(info_group)

        # Check for GPU
        has_gpu, gpu_name = detect_nvidia_gpu()

        info_text = """MuseTalk generates lip-synced videos from images/videos and audio.

This will install:

Python Packages (~2GB):
  - PyTorch with torchvision
  - MMLab stack (mmengine, mmcv, mmdet, mmpose)
  - Diffusers, Transformers, Accelerate
  - Video processing (av, opencv)

AI Models (~2.5GB):
  - MuseTalk core model
  - DWPose body detection
  - Face parsing model
  - Stable Diffusion VAE
  - Whisper audio model
"""

        if has_gpu and gpu_name:
            info_text += f"\nGPU detected: {gpu_name}\n"
            info_text += "Will install CUDA-accelerated version for faster processing.\n"
        else:
            info_text += "\nNo NVIDIA GPU detected.\n"
            info_text += "Will install CPU-only version (slower but functional).\n"

        required_space = get_musetalk_disk_space_required()
        info_text += f"\nTotal disk space required: ~{required_space:.1f}GB"

        model_path = get_musetalk_model_path()
        info_text += f"\nModel storage: {model_path}"

        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        info_layout.addWidget(info_label)
        layout.addWidget(info_group)

        # GPU requirements note
        gpu_group = QGroupBox("GPU Requirements")
        gpu_layout = QVBoxLayout(gpu_group)

        gpu_text = """Minimum: 4GB VRAM
Recommended: RTX 3060 12GB or better

CPU mode is available but significantly slower."""

        gpu_label = QLabel(gpu_text)
        gpu_label.setStyleSheet("color: #888;")
        gpu_layout.addWidget(gpu_label)
        layout.addWidget(gpu_group)

        # Important notes
        warning_group = QGroupBox("Important")
        warning_layout = QVBoxLayout(warning_group)

        warning_text = """- Installation runs in background
- Please don't close the application during installation
- Application restart required after installation
- First generation may be slow (model loading)"""

        warning_label = QLabel(warning_text)
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet("color: #ff9900;")
        warning_layout.addWidget(warning_label)
        layout.addWidget(warning_group)

        # Check disk space
        has_space, space_msg = check_disk_space(required_space)
        if not has_space:
            space_label = QLabel(f"  {space_msg}")
            space_label.setStyleSheet("color: #ff6666; font-weight: bold;")
            layout.addWidget(space_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.install_btn = QPushButton("Install MuseTalk")
        self.install_btn.clicked.connect(self.accept)
        self.install_btn.setDefault(True)
        self.install_btn.setEnabled(has_space)
        button_layout.addWidget(self.install_btn)

        layout.addLayout(button_layout)


class MuseTalkInstallProgressDialog(QDialog):
    """Progress dialog for MuseTalk installation."""

    installation_complete = Signal(bool, str)  # Success, message

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Installing MuseTalk")
        self.setModal(True)
        self.setMinimumWidth(650)
        self.setMinimumHeight(550)

        # Remove close button during installation
        self.setWindowFlags(
            Qt.Window |
            Qt.CustomizeWindowHint |
            Qt.WindowTitleHint
        )

        self.package_installer = None
        self.model_downloader = None
        self.start_time = None
        self.current_phase = "packages"  # packages -> models
        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)

        # Title
        self.title_label = QLabel("Installing MuseTalk Components...")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        layout.addWidget(self.title_label)

        # Time display
        time_layout = QHBoxLayout()

        self.phase_label = QLabel("Phase 1/2: Installing packages...")
        self.phase_label.setStyleSheet("color: #888;")
        time_layout.addWidget(self.phase_label)

        time_layout.addStretch()

        self.elapsed_label = QLabel("Elapsed: 0:00")
        self.elapsed_label.setStyleSheet("color: #66ccff; font-weight: bold;")
        time_layout.addWidget(self.elapsed_label)

        layout.addLayout(time_layout)

        # Elapsed timer
        self.elapsed_timer = QTimer()
        self.elapsed_timer.timeout.connect(self.update_elapsed_time)
        self.elapsed_timer.setInterval(1000)

        # Warning
        warning_label = QLabel("Please don't close the application during installation")
        warning_label.setStyleSheet("color: #ff9900; font-weight: bold; padding: 10px;")
        layout.addWidget(warning_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        # Current status
        self.status_label = QLabel("Starting installation...")
        layout.addWidget(self.status_label)

        # Progress output
        output_group = QGroupBox("Installation Output")
        output_layout = QVBoxLayout(output_group)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMinimumHeight(200)

        # Monospace font
        font = QFont("Consolas" if "Consolas" in QFont().families() else "Courier", 9)
        self.output_text.setFont(font)

        output_layout.addWidget(self.output_text)
        layout.addWidget(output_group, 1)

        # Background indicator
        self.background_label = QLabel("Running in background...")
        self.background_label.setStyleSheet("color: #66ccff; font-style: italic;")
        layout.addWidget(self.background_label)

        # Buttons (initially hidden)
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setVisible(False)
        button_layout.addWidget(self.close_btn)

        self.restart_btn = QPushButton("Restart Application")
        self.restart_btn.clicked.connect(self.restart_application)
        self.restart_btn.setVisible(False)
        button_layout.addWidget(self.restart_btn)

        layout.addLayout(button_layout)

    def start_installation(self):
        """Start the installation process."""
        self.start_time = time.time()
        self.elapsed_timer.start()

        # Get packages to install
        packages, index_url = get_musetalk_packages()

        # Show GPU status
        has_gpu, gpu_name = detect_nvidia_gpu()
        if has_gpu and gpu_name:
            self.on_progress(f"[{datetime.now().strftime('%H:%M:%S')}] GPU detected: {gpu_name}")
            self.on_progress(f"[{datetime.now().strftime('%H:%M:%S')}] Installing CUDA-accelerated version...")
        else:
            self.on_progress(f"[{datetime.now().strftime('%H:%M:%S')}] No GPU detected, installing CPU version...")

        # Create package installer
        self.package_installer = MuseTalkPackageInstaller(packages, index_url)
        self.package_installer.progress.connect(self.on_progress)
        self.package_installer.percentage.connect(self.on_percentage)
        self.package_installer.finished.connect(self.on_packages_finished)

        self.package_installer.start()

    def update_elapsed_time(self):
        """Update the elapsed time display."""
        if self.start_time:
            elapsed = time.time() - self.start_time
            minutes = int(elapsed / 60)
            seconds = int(elapsed % 60)
            self.elapsed_label.setText(f"Elapsed: {minutes}:{seconds:02d}")

    def on_progress(self, message: str):
        """Handle progress messages."""
        self.status_label.setText(message)
        self.output_text.append(message)

        # Auto-scroll
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.output_text.setTextCursor(cursor)

    def on_percentage(self, percentage: int):
        """Update progress bar."""
        # Scale percentage based on phase
        if self.current_phase == "packages":
            # Packages are 50% of total
            scaled = int(percentage * 0.5)
        else:
            # Models are remaining 50%
            scaled = 50 + int(percentage * 0.5)

        self.progress_bar.setValue(scaled)

    def on_packages_finished(self, success: bool, message: str):
        """Handle package installation completion."""
        if success:
            self.on_progress(f"[{datetime.now().strftime('%H:%M:%S')}] Package installation complete!")

            # Start model downloads
            self.current_phase = "models"
            self.phase_label.setText("Phase 2/2: Downloading models...")
            self.download_models()
        else:
            self.title_label.setText("Installation Failed")
            self.status_label.setText(message)
            self.phase_label.setText("")
            self.background_label.setText("")

            self.close_btn.setVisible(True)
            self.elapsed_timer.stop()

            self.show_notification("Installation Failed", message, QSystemTrayIcon.Critical)
            self.installation_complete.emit(False, message)

    def download_models(self):
        """Start model downloads."""
        self.title_label.setText("Downloading AI Models...")
        self.on_progress(f"[{datetime.now().strftime('%H:%M:%S')}] Starting model downloads...")

        self.model_downloader = MuseTalkModelDownloader()
        self.model_downloader.progress.connect(self.on_progress)
        self.model_downloader.percentage.connect(self.on_percentage)
        self.model_downloader.finished.connect(self.on_models_finished)

        self.model_downloader.start()

    def on_models_finished(self, success: bool, message: str):
        """Handle model download completion."""
        self.elapsed_timer.stop()

        if success:
            self.title_label.setText("Installation Complete!")
            self.status_label.setText("MuseTalk is ready to use")
            self.phase_label.setText("Please restart ImageAI to enable lip-sync")
            self.background_label.setText("")
            self.progress_bar.setValue(100)

            self.close_btn.setVisible(True)
            self.restart_btn.setVisible(True)

            self.show_notification(
                "Installation Complete!",
                "MuseTalk lip-sync has been installed. Please restart ImageAI.",
                QSystemTrayIcon.Information
            )

            self.installation_complete.emit(True, "Installation complete")
        else:
            # Packages installed but models failed
            self.title_label.setText("Partial Installation")
            self.status_label.setText("Packages installed but model download failed")
            self.phase_label.setText("You can try downloading models again later")
            self.background_label.setText("")

            self.close_btn.setVisible(True)

            self.show_notification(
                "Partial Installation",
                "Packages installed but model download failed.",
                QSystemTrayIcon.Warning
            )

            self.installation_complete.emit(True, "Packages installed, model download failed")

    def show_notification(self, title: str, message: str, icon: QSystemTrayIcon.MessageIcon):
        """Show system tray notification if available."""
        try:
            if QSystemTrayIcon.isSystemTrayAvailable():
                from PySide6.QtGui import QPixmap, QIcon

                pixmap = QPixmap(16, 16)
                if icon == QSystemTrayIcon.Information:
                    pixmap.fill(Qt.green)
                elif icon == QSystemTrayIcon.Warning:
                    pixmap.fill(Qt.yellow)
                elif icon == QSystemTrayIcon.Critical:
                    pixmap.fill(Qt.red)
                else:
                    pixmap.fill(Qt.blue)

                tray = QSystemTrayIcon(self)
                tray.setIcon(QIcon(pixmap))
                tray.setVisible(True)
                tray.showMessage(title, message, icon, 10000)

                QTimer.singleShot(11000, lambda: tray.hide() if tray else None)
        except Exception as e:
            logger.warning(f"Could not show notification: {e}")

    def restart_application(self):
        """Restart the application."""
        try:
            from PySide6.QtCore import QProcess
            QProcess.startDetached(sys.executable, sys.argv)
            QApplication.quit()
        except Exception as e:
            logger.error(f"Failed to restart: {e}")
            QMessageBox.warning(
                self,
                "Restart Failed",
                "Please close and reopen ImageAI manually."
            )

    def reject(self):
        """Prevent closing during installation."""
        if (self.package_installer and self.package_installer.isRunning()) or \
           (self.model_downloader and self.model_downloader.isRunning()):
            QMessageBox.warning(
                self,
                "Installation in Progress",
                "Please wait for the installation to complete."
            )
            return

        super().reject()


def show_musetalk_install_dialog(parent=None) -> bool:
    """
    Show the MuseTalk installation dialog flow.

    Returns:
        True if installation was started, False if cancelled
    """
    # First check if already installed
    is_installed, status = check_musetalk_installed()
    if is_installed:
        QMessageBox.information(
            parent,
            "Already Installed",
            "MuseTalk is already installed and ready to use."
        )
        return False

    # Show confirmation dialog
    confirm_dialog = MuseTalkInstallConfirmDialog(parent)
    if confirm_dialog.exec() != QDialog.Accepted:
        return False

    # Show progress dialog and start installation
    progress_dialog = MuseTalkInstallProgressDialog(parent)
    progress_dialog.start_installation()
    progress_dialog.exec()

    return True
