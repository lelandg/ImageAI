"""
Video button widget with hover preview for video clips.

This module provides a specialized button widget that displays video first frames
with hover previews and supports various states (no video, video exists).
"""

from pathlib import Path
from typing import Optional
import logging

from PySide6.QtWidgets import QPushButton, QMenu
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QAction

from gui.video.frame_button import FramePreviewPopup


class VideoButton(QPushButton):
    """
    Button for video clip with hover preview (first frame) and context menu.

    States:
    - No video: Shows "🎬" icon, video not generated yet
    - Has video: Shows "👁️" icon, video exists and has first frame

    Features:
    - Hover preview (200x200px thumbnail of first frame)
    - Right-click context menu (Play, Regenerate, Clear)
    - Click to load first frame in lower panel
    - Double-click to regenerate
    """

    # Signals
    clicked_load_frame = Signal()  # Emitted when user clicks to load frame in panel
    regenerate_requested = Signal()  # Emitted when user requests regeneration
    clear_requested = Signal()  # Emitted when user wants to clear video
    play_requested = Signal()  # Emitted when user wants to play video

    def __init__(self, parent=None):
        """
        Initialize video button.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.video_path: Optional[Path] = None
        self.first_frame_path: Optional[Path] = None
        self.has_video_prompt = False
        self.uses_veo_31 = False
        self.preview_popup: Optional[FramePreviewPopup] = None
        self.logger = logging.getLogger(__name__)

        # Configure button appearance - match LLM button height
        self.setFixedHeight(30)  # Match PromptFieldWidget button height
        self.setMinimumWidth(40)
        self.setMaximumWidth(50)
        self.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                padding: 2px;
                border: 2px solid #ccc;
                border-radius: 3px;
                background-color: #f5f5f5;
            }
            QPushButton:hover {
                border-color: #999;
                background-color: #e8e8e8;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
            QPushButton:disabled {
                background-color: #f9f9f9;
                color: #aaa;
                border-color: #ddd;
            }
        """)

        # Enable mouse tracking for hover
        self.setMouseTracking(True)

        # Connect signals
        self.clicked.connect(self._on_clicked)

        # Set initial state
        self.update_appearance()

    def set_video_state(
        self,
        video_path: Optional[Path],
        first_frame_path: Optional[Path],
        has_video_prompt: bool,
        uses_veo_31: bool
    ):
        """
        Set the video state for this button.

        Args:
            video_path: Path to video file, or None if no video
            first_frame_path: Path to first frame image, or None
            has_video_prompt: True if video prompt exists
            uses_veo_31: True if scene uses Veo 3.1
        """
        self.video_path = video_path
        self.first_frame_path = first_frame_path
        self.has_video_prompt = has_video_prompt
        self.uses_veo_31 = uses_veo_31
        self.update_appearance()

    def update_appearance(self):
        """Update button icon/text and tooltip based on state"""
        has_video = self.video_path is not None and self.video_path.exists() if self.video_path else False

        if has_video:
            # Video exists - show view icon
            self.setText("👁️")
            tooltip = "Click to view first frame\nRight-click for options (Play, Regenerate, Clear)\nDouble-click to regenerate\nHover for preview"
            self.setEnabled(True)
        else:
            # No video - show generate icon
            self.setText("🎬")
            if self.has_video_prompt:
                if self.uses_veo_31:
                    tooltip = "Generate video clip (Veo 3.1: start → end transition)"
                else:
                    tooltip = "Generate video clip (Veo 3: single-frame animation)"
                self.setEnabled(True)
            else:
                tooltip = "Generate video prompt first (✨ in Video Prompt column)"
                self.setEnabled(False)

        self.setToolTip(tooltip)

    def has_video(self) -> bool:
        """Check if video exists"""
        return self.video_path is not None and self.video_path.exists() if self.video_path else False

    def enterEvent(self, event):
        """Show preview on mouse enter"""
        if self.has_video() and self.first_frame_path and self.first_frame_path.exists():
            self._show_preview()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hide preview on mouse leave"""
        self._hide_preview()
        super().leaveEvent(event)

    def _show_preview(self):
        """Show 200x200px thumbnail preview of first frame"""
        if not self.preview_popup:
            self.preview_popup = FramePreviewPopup(self)

        cursor_pos = QCursor.pos()
        self.preview_popup.show_preview(self.first_frame_path, cursor_pos)

    def _hide_preview(self):
        """Hide preview"""
        if self.preview_popup:
            self.preview_popup.hide()

    def _on_clicked(self):
        """Handle button click"""
        if self.has_video():
            # Has video: load first frame in lower panel
            self.clicked_load_frame.emit()
        else:
            # No video: request generation
            self.regenerate_requested.emit()

    def contextMenuEvent(self, event):
        """Show context menu on right-click"""
        menu = QMenu(self)

        if self.has_video():
            # Video exists: show play/regenerate/clear options
            play_action = QAction("▶ Play Video", self)
            play_action.triggered.connect(self.play_requested.emit)
            menu.addAction(play_action)

            menu.addSeparator()

            regenerate_action = QAction("🔄 Regenerate Video", self)
            regenerate_action.triggered.connect(self.regenerate_requested.emit)
            menu.addAction(regenerate_action)

            menu.addSeparator()

            clear_action = QAction("🗑️ Clear Video", self)
            clear_action.triggered.connect(self.clear_requested.emit)
            menu.addAction(clear_action)
        else:
            # No video: show generate option
            generate_action = QAction("🎬 Generate Video", self)
            generate_action.triggered.connect(self.regenerate_requested.emit)
            menu.addAction(generate_action)

        menu.exec_(event.globalPos())

    def mouseMoveEvent(self, event):
        """Update preview position on mouse move"""
        if self.preview_popup and self.preview_popup.isVisible():
            cursor_pos = QCursor.pos()
            self.preview_popup.show_preview(self.first_frame_path, cursor_pos)
        super().mouseMoveEvent(event)
