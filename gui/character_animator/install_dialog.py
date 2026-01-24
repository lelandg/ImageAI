"""
Installation dialogs for Character Animator puppet automation.

Follows the pattern established by gui/install_dialog.py for Real-ESRGAN.
Provides user confirmation before installing heavy AI dependencies and
shows progress during installation.
"""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from core.constants import get_user_data_dir

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QProgressBar, QMessageBox, QApplication,
    QSystemTrayIcon, QGroupBox, QCheckBox, QFrame,
)
from PySide6.QtCore import Qt, Signal, QTimer, QProcess
from PySide6.QtGui import QFont, QPixmap, QIcon

from core.package_installer import (
    PackageInstaller, ModelDownloader,
    check_disk_space, detect_nvidia_gpu,
    get_puppet_ai_packages, get_puppet_model_info,
)
from core.character_animator.installer import (
    get_install_info, get_missing_packages, PUPPET_MODELS,
)
from core.character_animator.availability import (
    check_all_dependencies, get_install_status_message,
)

logger = logging.getLogger(__name__)


class PuppetInstallConfirmDialog(QDialog):
    """
    Confirmation dialog before installing Character Animator AI components.

    Shows:
    - What will be installed (packages and models)
    - GPU detection status
    - Disk space requirements
    - Estimated download size
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Install Character Animator AI Components")
        self.setModal(True)
        self.setMinimumWidth(550)
        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Install AI Components for Puppet Generation")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Get installation info
        install_info = get_install_info()

        # Package list
        package_group = QGroupBox("Components to Install")
        package_layout = QVBoxLayout(package_group)

        packages_text = """This will install AI components for automatic puppet creation:

<b>Segmentation (SAM 2)</b> - Precise body part separation
<b>Pose Detection (MediaPipe)</b> - Skeleton and face landmarks

<b>Cloud AI (Gemini/OpenAI)</b> - Viseme generation via API
<i>Note: Uses your existing API keys from Settings. No large models to download.</i>

<b>Export Tools:</b>
- PSD file creation (psd-tools)
- SVG file creation (svgwrite)
"""

        packages_label = QLabel(packages_text)
        packages_label.setWordWrap(True)
        packages_label.setTextFormat(Qt.RichText)
        package_layout.addWidget(packages_label)
        layout.addWidget(package_group)

        # GPU and size info
        info_group = QGroupBox("Installation Details")
        info_layout = QVBoxLayout(info_group)

        # GPU status
        if install_info["has_gpu"]:
            gpu_text = f"GPU Detected: {install_info['gpu_name']}"
            gpu_label = QLabel(gpu_text)
            gpu_label.setStyleSheet("color: #00cc00;")
            info_layout.addWidget(gpu_label)

            cuda_label = QLabel("Will install CUDA-accelerated version for faster processing")
            cuda_label.setStyleSheet("color: #88cc88;")
            info_layout.addWidget(cuda_label)
        else:
            gpu_label = QLabel("No NVIDIA GPU detected")
            gpu_label.setStyleSheet("color: #ffcc00;")
            info_layout.addWidget(gpu_label)

            cpu_label = QLabel("Will install CPU-only version (slower but functional)")
            cpu_label.setStyleSheet("color: #cccc88;")
            info_layout.addWidget(cpu_label)

        # Download size
        size_text = f"\nEstimated download: ~{install_info['estimated_download_gb']:.1f} GB"
        size_label = QLabel(size_text)
        size_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(size_label)

        # Model details
        model_text = "AI models to download:\n"
        for model_name in install_info["models_to_download"][:3]:  # Show first 3
            if model_name in PUPPET_MODELS:
                model = PUPPET_MODELS[model_name]
                model_text += f"  - {model['description']} ({model['size_mb']}MB)\n"

        if len(install_info["models_to_download"]) > 3:
            model_text += f"  - ...and {len(install_info['models_to_download']) - 3} more\n"

        model_label = QLabel(model_text)
        model_label.setStyleSheet("color: #aaaaaa;")
        info_layout.addWidget(model_label)

        layout.addWidget(info_group)

        # Disk space check
        if not install_info["has_disk_space"]:
            warning_label = QLabel(f"WARNING: {install_info['disk_space_message']}")
            warning_label.setStyleSheet("color: #ff6666; font-weight: bold;")
            layout.addWidget(warning_label)
        else:
            space_label = QLabel(install_info["disk_space_message"])
            space_label.setStyleSheet("color: #66cc66;")
            layout.addWidget(space_label)

        # Time estimate
        time_label = QLabel("""
Installation time:
  - Cached/partial: ~1-5 minutes
  - Fresh install: 15-30 minutes (depends on bandwidth)
""")
        time_label.setStyleSheet("color: #888888;")
        layout.addWidget(time_label)

        # Warning
        warning_group = QGroupBox("Important")
        warning_layout = QVBoxLayout(warning_group)

        warning_text = """- Installation runs in the background
- Please don't close the application until finished
- Application restart required after installation
- You'll receive a notification when complete"""

        warning_label = QLabel(warning_text)
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet("color: #ff9900;")
        warning_layout.addWidget(warning_label)
        layout.addWidget(warning_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.install_btn = QPushButton("Install")
        self.install_btn.clicked.connect(self.accept)
        self.install_btn.setDefault(True)
        self.install_btn.setEnabled(install_info["has_disk_space"])
        button_layout.addWidget(self.install_btn)

        layout.addLayout(button_layout)


class PuppetInstallProgressDialog(QDialog):
    """
    Progress dialog for Character Animator AI component installation.

    Shows:
    - Package installation progress with timing
    - Model download progress with ETA
    - Elapsed time display
    - Background installation support
    """

    installation_complete = Signal(bool, str)  # Success, message

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Installing Character Animator AI")
        self.setModal(True)
        self.setMinimumWidth(650)
        self.setMinimumHeight(550)

        # Remove close button during installation
        self.setWindowFlags(
            Qt.Window |
            Qt.CustomizeWindowHint |
            Qt.WindowTitleHint
        )

        self.installer = None
        self.downloader = None
        self.start_time = None
        self.models_to_download = []
        self.current_model_index = 0

        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)

        # Title
        self.title_label = QLabel("Installing Character Animator AI Components...")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        layout.addWidget(self.title_label)

        # Time info
        time_layout = QHBoxLayout()

        self.time_label = QLabel("Estimated: 15-30 minutes for fresh install")
        self.time_label.setStyleSheet("color: #888;")
        time_layout.addWidget(self.time_label)

        time_layout.addStretch()

        self.elapsed_label = QLabel("Elapsed: 0:00")
        self.elapsed_label.setStyleSheet("color: #66ccff; font-weight: bold;")
        time_layout.addWidget(self.elapsed_label)

        layout.addLayout(time_layout)

        # Timer
        self.elapsed_timer = QTimer()
        self.elapsed_timer.timeout.connect(self.update_elapsed_time)
        self.elapsed_timer.setInterval(1000)

        # Warning
        warning_label = QLabel("Please don't close the application")
        warning_label.setStyleSheet("color: #ff9900; font-weight: bold; padding: 10px;")
        layout.addWidget(warning_label)

        # Current phase label
        self.phase_label = QLabel("Phase 1/3: Installing packages...")
        self.phase_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.phase_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Starting installation...")
        layout.addWidget(self.status_label)

        # Output text
        output_group = QGroupBox("Installation Output")
        output_layout = QVBoxLayout(output_group)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMinimumHeight(200)

        font = QFont("Consolas" if "Consolas" in QFont().families() else "Courier", 9)
        self.output_text.setFont(font)

        output_layout.addWidget(self.output_text)
        layout.addWidget(output_group, 1)

        # Background indicator
        self.background_label = QLabel("Running in background...")
        self.background_label.setStyleSheet("color: #66ccff; font-style: italic;")
        layout.addWidget(self.background_label)

        # Buttons (hidden initially)
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

        # Get packages and info
        packages, index_url = get_puppet_ai_packages()
        install_info = get_install_info()

        # Store models to download
        self.models_to_download = install_info["models_to_download"]

        # Show GPU status
        if install_info["has_gpu"]:
            self.on_progress(f"[{self._time_str()}] GPU detected: {install_info['gpu_name']}")
            self.on_progress(f"[{self._time_str()}] Installing CUDA-accelerated version...")
        else:
            self.on_progress(f"[{self._time_str()}] No GPU detected, installing CPU version...")

        # Create and start installer
        self.installer = PackageInstaller(
            packages,
            update_requirements=True,
            index_url=index_url
        )
        self.installer.progress.connect(self.on_progress)
        self.installer.percentage.connect(self.on_percentage)
        self.installer.finished.connect(self.on_packages_finished)

        self.installer.start()

    def _time_str(self) -> str:
        """Get current time string."""
        return datetime.now().strftime('%H:%M:%S')

    def update_elapsed_time(self):
        """Update elapsed time display."""
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
        from PySide6.QtGui import QTextCursor
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.output_text.setTextCursor(cursor)

    def on_percentage(self, percentage: int):
        """Update progress bar."""
        self.progress_bar.setValue(percentage)

    def on_packages_finished(self, success: bool, message: str):
        """Handle package installation completion."""
        if success:
            self.on_progress(f"[{self._time_str()}] Packages installed successfully")

            # Move to model download phase
            if self.models_to_download:
                self.phase_label.setText(f"Phase 2/3: Downloading AI models...")
                self.progress_bar.setValue(0)
                self.download_next_model()
            else:
                self.on_all_complete(True)
        else:
            self.title_label.setText("Installation Failed")
            self.status_label.setText(message)
            self.show_completion_buttons(False)
            self.show_notification("Installation Failed", message, QSystemTrayIcon.Critical)
            self.installation_complete.emit(False, message)

    def download_next_model(self):
        """Download the next model in the queue."""
        if self.current_model_index >= len(self.models_to_download):
            # All models downloaded
            self.phase_label.setText("Phase 3/3: Verifying installation...")
            self.verify_installation()
            return

        model_name = self.models_to_download[self.current_model_index]
        model_info = PUPPET_MODELS.get(model_name, {})

        if model_info.get("auto_download"):
            # HuggingFace models are auto-downloaded on first use
            self.on_progress(f"[{self._time_str()}] {model_name} will download on first use")
            self.current_model_index += 1
            self.download_next_model()
            return

        # Download model
        url = model_info.get("url", "")
        if not url:
            self.current_model_index += 1
            self.download_next_model()
            return

        # Set up model path in user data directory
        weights_dir = get_user_data_dir() / "weights" / "character_animator"
        weights_dir.mkdir(parents=True, exist_ok=True)
        model_path = weights_dir / model_info.get("filename", f"{model_name}.pt")

        self.on_progress(f"[{self._time_str()}] Downloading {model_name}...")

        self.downloader = ModelDownloader(url, model_path)
        self.downloader.progress.connect(self.on_progress)
        self.downloader.percentage.connect(self.on_percentage)
        self.downloader.finished.connect(self.on_model_downloaded)
        self.downloader.start()

    def on_model_downloaded(self, success: bool, message: str):
        """Handle model download completion."""
        if success:
            model_name = self.models_to_download[self.current_model_index]
            self.on_progress(f"[{self._time_str()}] Downloaded {model_name}")
        else:
            self.on_progress(f"[{self._time_str()}] Warning: {message}")

        self.current_model_index += 1
        self.download_next_model()

    def verify_installation(self):
        """Verify all components are installed correctly."""
        self.on_progress(f"[{self._time_str()}] Verifying installation...")

        # Re-check dependencies
        status = check_all_dependencies()

        all_ok = True
        for component, available in status.items():
            status_str = "OK" if available else "Missing"
            self.on_progress(f"  - {component}: {status_str}")
            if not available and component not in ["torch_cuda"]:  # CUDA is optional
                all_ok = False

        self.on_all_complete(all_ok)

    def on_all_complete(self, success: bool):
        """Handle completion of all installation steps."""
        self.elapsed_timer.stop()

        if success:
            self.title_label.setText("Installation Complete!")
            self.phase_label.setText("All components installed")
            self.status_label.setText("Character Animator AI is ready to use")
            self.time_label.setText("Please restart ImageAI to enable puppet generation")
            self.background_label.setText("")

            self.show_notification(
                "Installation Complete!",
                "Character Animator AI components installed. Please restart ImageAI.",
                QSystemTrayIcon.Information
            )

            self.installation_complete.emit(True, "Installation complete")
        else:
            self.title_label.setText("Partial Installation")
            self.status_label.setText("Some components may be missing")

            self.show_notification(
                "Partial Installation",
                "Some components may not have installed correctly.",
                QSystemTrayIcon.Warning
            )

            self.installation_complete.emit(True, "Partial installation")

        self.show_completion_buttons(success)

    def show_completion_buttons(self, show_restart: bool):
        """Show completion buttons."""
        self.close_btn.setVisible(True)
        self.restart_btn.setVisible(show_restart)

    def show_notification(self, title: str, message: str, icon: QSystemTrayIcon.MessageIcon):
        """Show system notification."""
        try:
            if QSystemTrayIcon.isSystemTrayAvailable():
                pixmap = QPixmap(16, 16)
                if icon == QSystemTrayIcon.Information:
                    pixmap.fill(Qt.green)
                elif icon == QSystemTrayIcon.Warning:
                    pixmap.fill(Qt.yellow)
                else:
                    pixmap.fill(Qt.red)

                tray = QSystemTrayIcon(self)
                tray.setIcon(QIcon(pixmap))
                tray.setVisible(True)
                tray.showMessage(title, message, icon, 10000)

                # Store reference to keep alive and use safe cleanup
                self._notification_tray = tray

                def safe_hide_tray():
                    try:
                        if hasattr(self, '_notification_tray') and self._notification_tray:
                            self._notification_tray.hide()
                            self._notification_tray = None
                    except RuntimeError:
                        pass  # Object already deleted

                QTimer.singleShot(11000, safe_hide_tray)
        except Exception as e:
            logger.warning(f"Could not show notification: {e}")

    def restart_application(self):
        """Restart the application."""
        try:
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
        if self.installer and self.installer.isRunning():
            QMessageBox.warning(
                self,
                "Installation in Progress",
                "Please wait for installation to complete."
            )
            return

        if self.downloader and self.downloader.isRunning():
            QMessageBox.warning(
                self,
                "Download in Progress",
                "Please wait for model download to complete."
            )
            return

        super().reject()
