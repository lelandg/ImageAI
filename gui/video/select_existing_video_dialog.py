"""
Dialog for selecting existing video clips from the project to assign to a scene.

This dialog shows all available video clips from the current project in a list
with preview capability, allowing users to reuse existing clips when regenerating
the storyboard.
"""

from pathlib import Path
from typing import Optional, List, Tuple
import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton,
    QDialogButtonBox, QSplitter, QWidget, QTextEdit
)
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

from core.video.project import VideoProject, Scene


class SelectExistingVideoDialog(QDialog):
    """
    Dialog for selecting an existing video clip to assign to a scene.

    Features:
    - Lists all scenes with generated video clips
    - Shows video preview for selected clip
    - Displays source text and prompt for context
    - Returns selected video path on accept
    """

    def __init__(self, project: VideoProject, current_scene_id: str = None, parent=None):
        """
        Initialize the dialog.

        Args:
            project: Current video project with scenes
            current_scene_id: ID of the scene we're assigning to (for display context)
            parent: Parent widget
        """
        super().__init__(parent)
        self.project = project
        self.current_scene_id = current_scene_id
        self.selected_video_path: Optional[Path] = None
        self.logger = logging.getLogger(__name__)

        # Media player for video preview
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)

        self._setup_ui()
        self._load_available_clips()

    def _setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle("Select Existing Video Clip")
        self.setMinimumSize(900, 600)

        layout = QVBoxLayout(self)

        # Info label
        info_label = QLabel(
            "Select an existing video clip to assign to this scene. "
            "This allows you to reuse previously generated clips after regenerating the storyboard."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 5px; background-color: #e3f2fd; border-radius: 3px;")
        layout.addWidget(info_label)

        # Create splitter for list and preview
        splitter = QSplitter(Qt.Horizontal)

        # Left side: List of available clips
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_label = QLabel("Available Video Clips:")
        left_label.setStyleSheet("font-weight: bold; padding: 5px;")
        left_layout.addWidget(left_label)

        self.clips_list = QListWidget()
        self.clips_list.currentItemChanged.connect(self._on_selection_changed)
        self.clips_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        left_layout.addWidget(self.clips_list)

        splitter.addWidget(left_widget)

        # Right side: Preview panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_label = QLabel("Preview:")
        right_label.setStyleSheet("font-weight: bold; padding: 5px;")
        right_layout.addWidget(right_label)

        # Video preview widget
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(300)
        self.video_widget.setStyleSheet("background-color: black;")
        self.media_player.setVideoOutput(self.video_widget)
        right_layout.addWidget(self.video_widget)

        # Playback controls
        controls_layout = QHBoxLayout()

        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self._toggle_playback)
        self.play_btn.setEnabled(False)
        controls_layout.addWidget(self.play_btn)

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.clicked.connect(self._stop_playback)
        self.stop_btn.setEnabled(False)
        controls_layout.addWidget(self.stop_btn)

        controls_layout.addStretch()
        right_layout.addLayout(controls_layout)

        # Context info (source text and prompts)
        self.context_info = QTextEdit()
        self.context_info.setReadOnly(True)
        self.context_info.setMaximumHeight(150)
        self.context_info.setPlaceholderText("Select a clip to see details...")
        right_layout.addWidget(self.context_info)

        splitter.addWidget(right_widget)

        # Set splitter sizes (40% list, 60% preview)
        splitter.setSizes([360, 540])

        layout.addWidget(splitter)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.ok_button = button_box.button(QDialogButtonBox.Ok)
        self.ok_button.setEnabled(False)
        layout.addWidget(button_box)

    def _load_available_clips(self):
        """Load all scenes with video clips into the list"""
        self.clips_list.clear()

        if not self.project or not self.project.scenes:
            self.logger.warning("No project or scenes available")
            return

        clip_count = 0
        for scene in self.project.scenes:
            # Only show scenes that have generated video clips
            if scene.video_clip and scene.video_clip.exists():
                # Create list item with scene info
                source_preview = scene.source[:50] + "..." if len(scene.source) > 50 else scene.source
                item_text = f"Scene {scene.order + 1}: {source_preview}"

                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, scene)  # Store scene object

                # Add icon based on scene status
                if scene.id == self.current_scene_id:
                    item.setText(f"⭐ {item_text} (current)")
                    item.setToolTip("This is the scene you're assigning to")
                else:
                    item.setToolTip(f"Source: {scene.source}\nDuration: {scene.duration_sec:.1f}s")

                self.clips_list.addItem(item)
                clip_count += 1

        if clip_count == 0:
            placeholder = QListWidgetItem("No video clips found in project")
            placeholder.setFlags(Qt.NoItemFlags)
            self.clips_list.addItem(placeholder)
            self.logger.info("No scenes with video clips found")
        else:
            self.logger.info(f"Loaded {clip_count} available video clips")

    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        """Handle selection change in the clips list"""
        if not current:
            self._clear_preview()
            return

        # Get the scene from the item
        scene: Scene = current.data(Qt.UserRole)
        if not scene:
            self._clear_preview()
            return

        # Update preview and context
        self._update_preview(scene)
        self._update_context_info(scene)

        # Enable OK button
        self.ok_button.setEnabled(True)
        self.selected_video_path = scene.video_clip

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Handle double-click on item - accept immediately"""
        scene: Scene = item.data(Qt.UserRole)
        if scene and scene.video_clip:
            self.selected_video_path = scene.video_clip
            self.accept()

    def _update_preview(self, scene: Scene):
        """Update video preview for the selected scene"""
        if not scene.video_clip or not scene.video_clip.exists():
            self._clear_preview()
            return

        # Stop any current playback
        self.media_player.stop()

        # Load the video
        self.media_player.setSource(QUrl.fromLocalFile(str(scene.video_clip)))

        # Enable controls
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.play_btn.setText("▶ Play")

        self.logger.debug(f"Loaded video preview: {scene.video_clip}")

    def _update_context_info(self, scene: Scene):
        """Update context information for the selected scene"""
        info_parts = []

        info_parts.append(f"<b>Scene {scene.order + 1}</b>")
        info_parts.append(f"<b>Source:</b> {scene.source}")
        info_parts.append(f"<b>Duration:</b> {scene.duration_sec:.1f} seconds")

        if scene.prompt:
            info_parts.append(f"<b>Image Prompt:</b> {scene.prompt[:100]}...")

        if scene.video_prompt:
            info_parts.append(f"<b>Video Prompt:</b> {scene.video_prompt[:100]}...")

        if scene.video_clip:
            info_parts.append(f"<b>Video File:</b> {scene.video_clip.name}")

        self.context_info.setHtml("<br><br>".join(info_parts))

    def _clear_preview(self):
        """Clear the video preview"""
        self.media_player.stop()
        self.media_player.setSource(QUrl())
        self.play_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.context_info.clear()
        self.ok_button.setEnabled(False)
        self.selected_video_path = None

    def _toggle_playback(self):
        """Toggle video playback"""
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.media_player.pause()
            self.play_btn.setText("▶ Play")
        else:
            self.media_player.play()
            self.play_btn.setText("⏸ Pause")

    def _stop_playback(self):
        """Stop video playback"""
        self.media_player.stop()
        self.play_btn.setText("▶ Play")

    def get_selected_video_path(self) -> Optional[Path]:
        """
        Get the selected video path.

        Returns:
            Path to selected video clip, or None if no selection
        """
        return self.selected_video_path

    def closeEvent(self, event):
        """Handle dialog close - stop playback"""
        self.media_player.stop()
        super().closeEvent(event)
