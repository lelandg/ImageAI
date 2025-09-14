"""Installation dialog for Real-ESRGAN AI upscaling."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QProgressBar, QMessageBox, QApplication,
    QSystemTrayIcon, QGroupBox
)
from PySide6.QtCore import Qt, Signal, QProcess, QTimer
from PySide6.QtGui import QFont, QIcon
from pathlib import Path
from datetime import datetime
import sys
import time
import logging

from core.package_installer import (
    PackageInstaller, ModelDownloader,
    check_disk_space, get_realesrgan_packages,
    get_model_info, detect_nvidia_gpu
)

logger = logging.getLogger(__name__)


class InstallConfirmDialog(QDialog):
    """Confirmation dialog before installation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Install AI Upscaling")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Install Real-ESRGAN AI Upscaling")
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

        info_text = """This will install the following components:

• Real-ESRGAN - AI-powered image upscaling
• BasicSR - Image restoration framework
• OpenCV - Computer vision library
• PyTorch with torchvision - Deep learning framework
"""

        if has_gpu and gpu_name:
            info_text += f"\n✅ NVIDIA GPU detected: {gpu_name}\n"
            info_text += "• Will install CUDA-accelerated version for faster upscaling\n"
            info_text += "\nDownload size: ~3-4GB (CUDA-enabled PyTorch)\n"
        else:
            info_text += "\nℹ️ No NVIDIA GPU detected\n"
            info_text += "• Will install CPU-only version (smaller but slower)\n"
            info_text += "\nDownload size: ~2-3GB (CPU-only PyTorch)\n"

        info_text += """Installation time:
  • Cached/partial install: ~30 seconds
  • Fresh install: 3-15 minutes (depends on bandwidth)
  • Typical fresh install: ~3 minutes
Disk space required: ~7GB (mostly PyTorch)"""

        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        info_layout.addWidget(info_label)
        layout.addWidget(info_group)

        # Important notes
        warning_group = QGroupBox("⚠️ Important")
        warning_layout = QVBoxLayout(warning_group)

        warning_text = """• Installation runs in the background
• Please don't close the application until finished
• Your requirements.txt will be automatically updated
• Application restart required after installation
• You'll receive a notification when complete"""

        warning_label = QLabel(warning_text)
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet("color: #ff9900;")
        warning_layout.addWidget(warning_label)
        layout.addWidget(warning_group)

        # Check disk space (7.5GB needed for PyTorch + Real-ESRGAN)
        has_space, space_msg = check_disk_space(7.5)
        if not has_space:
            space_label = QLabel(f"❌ {space_msg}")
            space_label.setStyleSheet("color: #ff6666; font-weight: bold;")
            layout.addWidget(space_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.install_btn = QPushButton("Install")
        self.install_btn.clicked.connect(self.accept)
        self.install_btn.setDefault(True)
        self.install_btn.setEnabled(has_space)
        button_layout.addWidget(self.install_btn)

        layout.addLayout(button_layout)


class InstallProgressDialog(QDialog):
    """Progress dialog for installation."""

    installation_complete = Signal(bool, str)  # Success, message

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Installing AI Upscaling")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        # Remove close button - user can't close during installation
        self.setWindowFlags(
            Qt.Window |
            Qt.CustomizeWindowHint |
            Qt.WindowTitleHint
        )

        self.installer = None
        self.downloader = None
        self.start_time = None
        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)

        # Title
        self.title_label = QLabel("Installing AI Upscaling Components...")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        layout.addWidget(self.title_label)

        # Time estimate and elapsed time
        time_layout = QHBoxLayout()

        self.time_label = QLabel("Estimated: 30 seconds (cached) to 3-5 minutes (fresh)")
        self.time_label.setStyleSheet("color: #888;")
        time_layout.addWidget(self.time_label)

        time_layout.addStretch()

        self.elapsed_label = QLabel("Elapsed: 0:00")
        self.elapsed_label.setStyleSheet("color: #66ccff; font-weight: bold;")
        time_layout.addWidget(self.elapsed_label)

        layout.addLayout(time_layout)

        # Timer to update elapsed time
        self.elapsed_timer = QTimer()
        self.elapsed_timer.timeout.connect(self.update_elapsed_time)
        self.elapsed_timer.setInterval(1000)  # Update every second

        # Warning
        warning_label = QLabel("⚠️ Please don't close the application")
        warning_label.setStyleSheet("color: #ff9900; font-weight: bold; padding: 10px;")
        layout.addWidget(warning_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        # Current status
        self.status_label = QLabel("Starting installation...")
        layout.addWidget(self.status_label)

        # Progress output (expandable)
        output_group = QGroupBox("Installation Output")
        output_layout = QVBoxLayout(output_group)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        # Remove maximum height to allow expansion
        self.output_text.setMinimumHeight(150)

        # Set monospace font
        font = QFont("Consolas" if "Consolas" in QFont().families() else "Courier", 9)
        self.output_text.setFont(font)

        output_layout.addWidget(self.output_text)
        # Set stretch factor to make this expand
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
        # Record start time and start elapsed timer
        self.start_time = time.time()
        self.elapsed_timer.start()

        # Get packages to install with GPU detection
        packages, index_url = get_realesrgan_packages()

        # Show GPU status in progress dialog
        has_gpu, gpu_name = detect_nvidia_gpu()
        if has_gpu and gpu_name:
            self.on_progress(f"[{datetime.now().strftime('%H:%M:%S')}] GPU detected: {gpu_name}")
            self.on_progress(f"[{datetime.now().strftime('%H:%M:%S')}] Installing CUDA-accelerated version...")
        else:
            self.on_progress(f"[{datetime.now().strftime('%H:%M:%S')}] No GPU detected, installing CPU version...")

        # Create installer thread with index_url
        self.installer = PackageInstaller(packages, update_requirements=True, index_url=index_url)
        self.installer.progress.connect(self.on_progress)
        self.installer.percentage.connect(self.on_percentage)
        self.installer.finished.connect(self.on_installation_finished)

        # Start installation
        self.installer.start()

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

        # Auto-scroll to bottom
        from PySide6.QtGui import QTextCursor
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.output_text.setTextCursor(cursor)

    def on_percentage(self, percentage: int):
        """Update progress bar."""
        self.progress_bar.setValue(percentage)

    def on_installation_finished(self, success: bool, message: str):
        """Handle installation completion."""
        # Stop the elapsed timer but keep the final time visible
        self.elapsed_timer.stop()

        if success:
            self.title_label.setText("✅ Installation Complete!")
            self.status_label.setText("Packages installed successfully")
            self.time_label.setText("")
            self.background_label.setText("")

            # Now download model weights
            self.download_model()
        else:
            self.title_label.setText("❌ Installation Failed")
            self.status_label.setText(message)
            self.time_label.setText("")
            self.background_label.setText("")

            # Show close button
            self.close_btn.setVisible(True)

            # Show error notification
            self.show_notification("Installation Failed", message, QSystemTrayIcon.Critical)
            self.installation_complete.emit(False, message)

    def download_model(self):
        """Download the default Real-ESRGAN model."""
        self.title_label.setText("Downloading AI Model...")
        self.status_label.setText("Downloading RealESRGAN_x4plus model...")

        # Get model info
        models = get_model_info()
        default_model = "RealESRGAN_x4plus"
        model_info = models[default_model]

        # Set up paths
        weights_dir = Path("weights")
        model_path = weights_dir / f"{default_model}.pth"

        # Create downloader
        self.downloader = ModelDownloader(model_info["url"], model_path)
        self.downloader.progress.connect(self.on_progress)
        self.downloader.percentage.connect(self.on_percentage)
        self.downloader.finished.connect(self.on_download_finished)

        # Start download
        self.downloader.start()

    def on_download_finished(self, success: bool, message: str):
        """Handle model download completion."""
        if success:
            self.title_label.setText("✅ Installation Complete!")
            self.status_label.setText("AI upscaling is ready to use")
            self.time_label.setText("Please restart ImageAI to enable AI upscaling")
            self.background_label.setText("")

            # Show restart button
            self.close_btn.setVisible(True)
            self.restart_btn.setVisible(True)

            # Show success notification
            self.show_notification(
                "Installation Complete!",
                "Real-ESRGAN AI upscaling has been installed successfully. Please restart ImageAI.",
                QSystemTrayIcon.Information
            )

            self.installation_complete.emit(True, "Installation complete")
        else:
            # Installation succeeded but model download failed - not critical
            self.title_label.setText("⚠️ Partial Installation")
            self.status_label.setText("Packages installed but model download failed")
            self.time_label.setText("You can download the model manually later")
            self.background_label.setText("")

            # Show close button
            self.close_btn.setVisible(True)

            self.show_notification(
                "Partial Installation",
                "Packages installed but model download failed. You can try again later.",
                QSystemTrayIcon.Warning
            )

            self.installation_complete.emit(True, "Packages installed, model download failed")

    def show_notification(self, title: str, message: str, icon: QSystemTrayIcon.MessageIcon):
        """Show system tray notification if available."""
        try:
            if QSystemTrayIcon.isSystemTrayAvailable():
                # Create a simple icon for the tray
                from PySide6.QtGui import QPixmap, QIcon

                # Create a simple colored pixmap as icon
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
                tray.showMessage(title, message, icon, 10000)  # 10 seconds

                # Hide tray icon after message
                QTimer.singleShot(11000, lambda: tray.hide() if tray else None)
        except Exception as e:
            logger.warning(f"Could not show system notification: {e}")
            # Fall back to just logging the notification
            logger.info(f"Notification: {title} - {message}")

    def restart_application(self):
        """Restart the application."""
        try:
            # Start new instance
            QProcess.startDetached(sys.executable, sys.argv)
            # Close current instance
            QApplication.quit()
        except Exception as e:
            logger.error(f"Failed to restart application: {e}")
            QMessageBox.warning(
                self,
                "Restart Failed",
                "Could not restart automatically. Please close and reopen ImageAI manually."
            )

    def reject(self):
        """Prevent closing during installation."""
        if self.installer and self.installer.isRunning():
            QMessageBox.warning(
                self,
                "Installation in Progress",
                "Please wait for the installation to complete.\n"
                "Closing now may leave packages partially installed."
            )
            return

        super().reject()


class InstallCompleteDialog(QDialog):
    """Dialog shown when installation is complete."""

    def __init__(self, success: bool, message: str, parent=None):
        super().__init__(parent)
        self.success = success
        self.message = message
        self.setWindowTitle("Installation Complete" if success else "Installation Failed")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)

        # Icon and title
        if self.success:
            title = QLabel("✅ Real-ESRGAN AI has been installed!")
            title.setStyleSheet("color: #00cc00; font-size: 14px; font-weight: bold;")
        else:
            title = QLabel("❌ Installation Failed")
            title.setStyleSheet("color: #ff6666; font-size: 14px; font-weight: bold;")

        layout.addWidget(title)

        # Message
        msg_label = QLabel(self.message)
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)

        if self.success:
            # Additional info
            info = QLabel("\nYour requirements.txt has been updated.\n"
                         "Please restart ImageAI to use AI upscaling.")
            info.setWordWrap(True)
            layout.addWidget(info)

            # Buttons
            button_layout = QHBoxLayout()
            button_layout.addStretch()

            later_btn = QPushButton("Later")
            later_btn.clicked.connect(self.reject)
            button_layout.addWidget(later_btn)

            restart_btn = QPushButton("Restart Now")
            restart_btn.clicked.connect(self.restart_application)
            restart_btn.setDefault(True)
            button_layout.addWidget(restart_btn)

            layout.addLayout(button_layout)
        else:
            # Error suggestions
            suggestions = QLabel("\nSuggestions:\n"
                               "• Check your internet connection\n"
                               "• Ensure you have sufficient disk space\n"
                               "• Try installing manually: pip install realesrgan")
            suggestions.setWordWrap(True)
            suggestions.setStyleSheet("color: #888;")
            layout.addWidget(suggestions)

            # OK button
            button_layout = QHBoxLayout()
            button_layout.addStretch()

            ok_btn = QPushButton("OK")
            ok_btn.clicked.connect(self.accept)
            button_layout.addWidget(ok_btn)

            layout.addLayout(button_layout)

    def restart_application(self):
        """Restart the application."""
        try:
            QProcess.startDetached(sys.executable, sys.argv)
            QApplication.quit()
        except Exception as e:
            logger.error(f"Failed to restart: {e}")
            QMessageBox.warning(self, "Restart Failed",
                              "Please close and reopen ImageAI manually.")
        self.accept()