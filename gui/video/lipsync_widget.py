"""Lip-sync widget for video generation."""

from pathlib import Path
from typing import Optional
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QSlider, QComboBox, QProgressBar, QFileDialog,
    QFrame, QSizePolicy, QMessageBox, QSplitter
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent

from core.musetalk_installer import check_musetalk_installed
from gui.video.musetalk_install_dialog import show_musetalk_install_dialog
from providers.video import (
    LipSyncBackend, get_lipsync_provider, get_available_lipsync_backends
)

logger = logging.getLogger(__name__)


class LipSyncGenerationThread(QThread):
    """Thread for lip-sync generation."""

    progress = Signal(str)  # Progress message
    finished = Signal(bool, str, str)  # Success, message, output_path

    def __init__(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Optional[Path],
        backend: LipSyncBackend,
        bbox_shift: int
    ):
        super().__init__()
        self.video_path = video_path
        self.audio_path = audio_path
        self.output_path = output_path
        self.backend = backend
        self.bbox_shift = bbox_shift

    def run(self):
        """Run lip-sync generation."""
        try:
            self.progress.emit("Initializing lip-sync provider...")

            provider = get_lipsync_provider(self.backend)

            self.progress.emit("Starting lip-sync generation...")

            output = provider.generate(
                video_path=self.video_path,
                audio_path=self.audio_path,
                output_path=self.output_path,
                bbox_shift=self.bbox_shift
            )

            self.progress.emit("Generation complete!")
            self.finished.emit(True, "Lip-sync video generated successfully", str(output))

        except Exception as e:
            logger.error(f"Lip-sync generation failed: {e}")
            self.finished.emit(False, str(e), "")


class DropLabel(QLabel):
    """Label that accepts drag-and-drop files."""

    file_dropped = Signal(str)

    def __init__(self, text: str, accepted_extensions: list, parent=None):
        super().__init__(text, parent)
        self.accepted_extensions = [ext.lower() for ext in accepted_extensions]
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #555;
                border-radius: 8px;
                padding: 20px;
                background-color: #2a2a2a;
                color: #888;
            }
            QLabel:hover {
                border-color: #888;
                background-color: #333;
            }
        """)
        self.setMinimumHeight(100)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter."""
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0]
            file_path = url.toLocalFile()
            ext = Path(file_path).suffix.lower()

            if ext in self.accepted_extensions:
                event.acceptProposedAction()
                self.setStyleSheet("""
                    QLabel {
                        border: 2px dashed #66ccff;
                        border-radius: 8px;
                        padding: 20px;
                        background-color: #2a3a4a;
                        color: #66ccff;
                    }
                """)

    def dragLeaveEvent(self, event):
        """Handle drag leave."""
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #555;
                border-radius: 8px;
                padding: 20px;
                background-color: #2a2a2a;
                color: #888;
            }
            QLabel:hover {
                border-color: #888;
                background-color: #333;
            }
        """)

    def dropEvent(self, event: QDropEvent):
        """Handle file drop."""
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0]
            file_path = url.toLocalFile()
            ext = Path(file_path).suffix.lower()

            if ext in self.accepted_extensions:
                self.file_dropped.emit(file_path)

        # Reset style
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #555;
                border-radius: 8px;
                padding: 20px;
                background-color: #2a2a2a;
                color: #888;
            }
            QLabel:hover {
                border-color: #888;
                background-color: #333;
            }
        """)


class LipSyncWidget(QWidget):
    """
    Main widget for lip-sync functionality.

    Allows users to:
    - Select a source video or image
    - Select an audio file
    - Configure lip-sync parameters
    - Generate lip-synced video
    """

    generation_started = Signal()
    generation_finished = Signal(str)  # output path
    generation_failed = Signal(str)  # error message

    def __init__(self, parent=None):
        super().__init__(parent)
        self.video_path: Optional[Path] = None
        self.audio_path: Optional[Path] = None
        self.generation_thread: Optional[LipSyncGenerationThread] = None
        self.init_ui()
        self.update_install_status()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Development notice banner
        dev_notice = QFrame()
        dev_notice.setStyleSheet("""
            QFrame {
                background-color: #3d2a1a;
                border: 1px solid #ff9933;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        dev_notice_layout = QHBoxLayout(dev_notice)
        dev_notice_layout.setContentsMargins(12, 8, 12, 8)

        notice_icon = QLabel("\u26a0")  # Warning sign
        notice_icon.setStyleSheet("font-size: 16px; color: #ff9933;")
        dev_notice_layout.addWidget(notice_icon)

        notice_text = QLabel("This feature is in development and may not be fully functional yet.")
        notice_text.setStyleSheet("color: #ffcc66; font-weight: bold;")
        notice_text.setWordWrap(True)
        dev_notice_layout.addWidget(notice_text, 1)

        layout.addWidget(dev_notice)

        # Status bar at top
        self.status_frame = QFrame()
        self.status_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a2e;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        status_layout = QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(10, 5, 10, 5)

        self.status_icon = QLabel()
        status_layout.addWidget(self.status_icon)

        self.status_label = QLabel("Checking MuseTalk installation...")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.install_btn = QPushButton("Install MuseTalk")
        self.install_btn.clicked.connect(self.on_install_clicked)
        self.install_btn.setVisible(False)
        status_layout.addWidget(self.install_btn)

        layout.addWidget(self.status_frame)

        # Main content area with splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left panel - inputs
        input_panel = QWidget()
        input_layout = QVBoxLayout(input_panel)
        input_layout.setContentsMargins(0, 0, 0, 0)

        # Source video/image section
        source_group = QGroupBox("Source Video/Image")
        source_layout = QVBoxLayout(source_group)

        # Drop zone for video
        self.video_drop = DropLabel(
            "Drag & drop video/image here\nor click Browse",
            [".mp4", ".avi", ".mov", ".mkv", ".webm", ".jpg", ".jpeg", ".png", ".bmp", ".webp"]
        )
        self.video_drop.file_dropped.connect(self.on_video_dropped)
        source_layout.addWidget(self.video_drop)

        # Video info and controls
        video_controls = QHBoxLayout()

        self.video_info = QLabel("No file selected")
        self.video_info.setStyleSheet("color: #888;")
        video_controls.addWidget(self.video_info, 1)

        self.browse_video_btn = QPushButton("Browse...")
        self.browse_video_btn.clicked.connect(self.browse_video)
        video_controls.addWidget(self.browse_video_btn)

        self.clear_video_btn = QPushButton("Clear")
        self.clear_video_btn.clicked.connect(self.clear_video)
        self.clear_video_btn.setEnabled(False)
        video_controls.addWidget(self.clear_video_btn)

        source_layout.addLayout(video_controls)
        input_layout.addWidget(source_group)

        # Audio section
        audio_group = QGroupBox("Audio File")
        audio_layout = QVBoxLayout(audio_group)

        # Drop zone for audio
        self.audio_drop = DropLabel(
            "Drag & drop audio file here\nor click Browse",
            [".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"]
        )
        self.audio_drop.file_dropped.connect(self.on_audio_dropped)
        audio_layout.addWidget(self.audio_drop)

        # Audio info and controls
        audio_controls = QHBoxLayout()

        self.audio_info = QLabel("No file selected")
        self.audio_info.setStyleSheet("color: #888;")
        audio_controls.addWidget(self.audio_info, 1)

        self.browse_audio_btn = QPushButton("Browse...")
        self.browse_audio_btn.clicked.connect(self.browse_audio)
        audio_controls.addWidget(self.browse_audio_btn)

        self.clear_audio_btn = QPushButton("Clear")
        self.clear_audio_btn.clicked.connect(self.clear_audio)
        self.clear_audio_btn.setEnabled(False)
        audio_controls.addWidget(self.clear_audio_btn)

        audio_layout.addLayout(audio_controls)
        input_layout.addWidget(audio_group)

        splitter.addWidget(input_panel)

        # Right panel - parameters and output
        params_panel = QWidget()
        params_layout = QVBoxLayout(params_panel)
        params_layout.setContentsMargins(0, 0, 0, 0)

        # Parameters section
        params_group = QGroupBox("Parameters")
        params_form = QVBoxLayout(params_group)

        # Provider selection
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Provider:"))

        self.provider_combo = QComboBox()
        self.provider_combo.addItem("MuseTalk (Local)", LipSyncBackend.MUSETALK)
        self.provider_combo.addItem("D-ID (Cloud)", LipSyncBackend.DID)
        self.provider_combo.setItemData(1, False, Qt.UserRole - 1)  # Disable D-ID for now
        provider_layout.addWidget(self.provider_combo)
        provider_layout.addStretch()

        params_form.addLayout(provider_layout)

        # Bbox shift slider
        bbox_layout = QVBoxLayout()

        bbox_header = QHBoxLayout()
        bbox_header.addWidget(QLabel("Mouth Openness (bbox_shift):"))

        self.bbox_value_label = QLabel("0")
        self.bbox_value_label.setStyleSheet("color: #66ccff; font-weight: bold;")
        bbox_header.addWidget(self.bbox_value_label)
        bbox_header.addStretch()

        bbox_layout.addLayout(bbox_header)

        self.bbox_slider = QSlider(Qt.Horizontal)
        self.bbox_slider.setRange(-7, 7)
        self.bbox_slider.setValue(0)
        self.bbox_slider.setTickPosition(QSlider.TicksBelow)
        self.bbox_slider.setTickInterval(1)
        self.bbox_slider.valueChanged.connect(self.on_bbox_changed)
        bbox_layout.addWidget(self.bbox_slider)

        bbox_hint = QLabel("Negative: smaller mouth | Positive: larger mouth")
        bbox_hint.setStyleSheet("color: #666; font-size: 11px;")
        bbox_layout.addWidget(bbox_hint)

        params_form.addLayout(bbox_layout)
        params_layout.addWidget(params_group)

        # Output section
        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout(output_group)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        output_layout.addWidget(self.progress_bar)

        # Status message
        self.output_status = QLabel("")
        self.output_status.setWordWrap(True)
        output_layout.addWidget(self.output_status)

        # Output preview (placeholder)
        self.output_preview = QLabel()
        self.output_preview.setAlignment(Qt.AlignCenter)
        self.output_preview.setMinimumHeight(150)
        self.output_preview.setStyleSheet("""
            QLabel {
                border: 1px solid #444;
                border-radius: 4px;
                background-color: #1a1a1a;
            }
        """)
        output_layout.addWidget(self.output_preview, 1)

        # Open output button
        self.open_output_btn = QPushButton("Open Output Folder")
        self.open_output_btn.clicked.connect(self.open_output_folder)
        self.open_output_btn.setEnabled(False)
        output_layout.addWidget(self.open_output_btn)

        params_layout.addWidget(output_group, 1)

        splitter.addWidget(params_panel)
        splitter.setSizes([400, 300])

        layout.addWidget(splitter, 1)

        # Generate button
        self.generate_btn = QPushButton("Generate Lip-Sync Video")
        self.generate_btn.setMinimumHeight(40)
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d5a27;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3d7a37;
            }
            QPushButton:pressed {
                background-color: #1d4a17;
            }
            QPushButton:disabled {
                background-color: #333;
                color: #666;
            }
        """)
        self.generate_btn.clicked.connect(self.start_generation)
        self.generate_btn.setEnabled(False)
        layout.addWidget(self.generate_btn)

    def update_install_status(self):
        """Update the installation status display."""
        is_installed, status = check_musetalk_installed()

        if is_installed:
            self.status_icon.setText("")
            self.status_label.setText("MuseTalk is installed and ready")
            self.status_label.setStyleSheet("color: #66cc66;")
            self.install_btn.setVisible(False)
            self.status_frame.setStyleSheet("""
                QFrame {
                    background-color: #1a2e1a;
                    border-radius: 6px;
                    padding: 8px;
                }
            """)
        else:
            self.status_icon.setText("")
            self.status_label.setText(f"MuseTalk not installed: {status}")
            self.status_label.setStyleSheet("color: #ff9966;")
            self.install_btn.setVisible(True)
            self.status_frame.setStyleSheet("""
                QFrame {
                    background-color: #2e2a1a;
                    border-radius: 6px;
                    padding: 8px;
                }
            """)

        self.update_generate_button()

    def update_generate_button(self):
        """Update the generate button state."""
        is_installed, _ = check_musetalk_installed()
        has_video = self.video_path is not None
        has_audio = self.audio_path is not None
        not_running = self.generation_thread is None or not self.generation_thread.isRunning()

        can_generate = is_installed and has_video and has_audio and not_running

        self.generate_btn.setEnabled(can_generate)

        if not is_installed:
            self.generate_btn.setText("Install MuseTalk First")
        elif not has_video:
            self.generate_btn.setText("Select Video/Image")
        elif not has_audio:
            self.generate_btn.setText("Select Audio")
        elif not not_running:
            self.generate_btn.setText("Generating...")
        else:
            self.generate_btn.setText("Generate Lip-Sync Video")

    def on_install_clicked(self):
        """Handle install button click."""
        show_musetalk_install_dialog(self)
        self.update_install_status()

    def browse_video(self):
        """Open file browser for video/image."""
        file_filter = (
            "Video/Image Files (*.mp4 *.avi *.mov *.mkv *.webm *.jpg *.jpeg *.png *.bmp *.webp);;"
            "Video Files (*.mp4 *.avi *.mov *.mkv *.webm);;"
            "Image Files (*.jpg *.jpeg *.png *.bmp *.webp);;"
            "All Files (*)"
        )

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video or Image",
            "",
            file_filter
        )

        if file_path:
            self.set_video_path(file_path)

    def browse_audio(self):
        """Open file browser for audio."""
        file_filter = (
            "Audio Files (*.wav *.mp3 *.m4a *.aac *.flac *.ogg);;"
            "All Files (*)"
        )

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File",
            "",
            file_filter
        )

        if file_path:
            self.set_audio_path(file_path)

    def on_video_dropped(self, file_path: str):
        """Handle video file drop."""
        self.set_video_path(file_path)

    def on_audio_dropped(self, file_path: str):
        """Handle audio file drop."""
        self.set_audio_path(file_path)

    def set_video_path(self, file_path: str):
        """Set the video/image path."""
        self.video_path = Path(file_path)
        self.video_info.setText(self.video_path.name)
        self.video_info.setStyleSheet("color: #66ccff;")
        self.clear_video_btn.setEnabled(True)

        # Update drop zone text
        self.video_drop.setText(f"Selected: {self.video_path.name}")

        self.update_generate_button()

    def set_audio_path(self, file_path: str):
        """Set the audio path."""
        self.audio_path = Path(file_path)
        self.audio_info.setText(self.audio_path.name)
        self.audio_info.setStyleSheet("color: #66ccff;")
        self.clear_audio_btn.setEnabled(True)

        # Update drop zone text
        self.audio_drop.setText(f"Selected: {self.audio_path.name}")

        self.update_generate_button()

    def clear_video(self):
        """Clear the selected video."""
        self.video_path = None
        self.video_info.setText("No file selected")
        self.video_info.setStyleSheet("color: #888;")
        self.clear_video_btn.setEnabled(False)
        self.video_drop.setText("Drag & drop video/image here\nor click Browse")
        self.update_generate_button()

    def clear_audio(self):
        """Clear the selected audio."""
        self.audio_path = None
        self.audio_info.setText("No file selected")
        self.audio_info.setStyleSheet("color: #888;")
        self.clear_audio_btn.setEnabled(False)
        self.audio_drop.setText("Drag & drop audio file here\nor click Browse")
        self.update_generate_button()

    def on_bbox_changed(self, value: int):
        """Handle bbox slider change."""
        self.bbox_value_label.setText(str(value))

    def start_generation(self):
        """Start lip-sync generation."""
        if self.video_path is None or self.audio_path is None:
            return

        # Get parameters
        backend = self.provider_combo.currentData()
        bbox_shift = self.bbox_slider.value()

        # Prepare output path
        output_dir = self.video_path.parent / "lipsync_output"
        output_path = output_dir / f"{self.video_path.stem}_lipsync.mp4"

        # Start generation thread
        self.generation_thread = LipSyncGenerationThread(
            video_path=self.video_path,
            audio_path=self.audio_path,
            output_path=output_path,
            backend=backend,
            bbox_shift=bbox_shift
        )

        self.generation_thread.progress.connect(self.on_generation_progress)
        self.generation_thread.finished.connect(self.on_generation_finished)

        # Update UI
        self.progress_bar.setVisible(True)
        self.output_status.setText("Starting generation...")
        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("Generating...")

        self.generation_started.emit()
        self.generation_thread.start()

    def on_generation_progress(self, message: str):
        """Handle generation progress update."""
        self.output_status.setText(message)

    def on_generation_finished(self, success: bool, message: str, output_path: str):
        """Handle generation completion."""
        self.progress_bar.setVisible(False)

        if success:
            self.output_status.setText(f"Success! Output: {output_path}")
            self.output_status.setStyleSheet("color: #66cc66;")
            self.open_output_btn.setEnabled(True)
            self._output_path = Path(output_path)
            self.generation_finished.emit(output_path)
        else:
            self.output_status.setText(f"Failed: {message}")
            self.output_status.setStyleSheet("color: #ff6666;")
            self.generation_failed.emit(message)

        self.update_generate_button()

    def open_output_folder(self):
        """Open the output folder in file manager."""
        if hasattr(self, '_output_path') and self._output_path.exists():
            import subprocess
            import platform

            folder = self._output_path.parent

            if platform.system() == "Windows":
                subprocess.run(['explorer', str(folder)])
            elif platform.system() == "Darwin":
                subprocess.run(['open', str(folder)])
            else:
                subprocess.run(['xdg-open', str(folder)])

    def set_video_from_project(self, video_path: Path):
        """
        Set video from a project clip.

        This allows integration with the video project tab.
        """
        if video_path and video_path.exists():
            self.set_video_path(str(video_path))
