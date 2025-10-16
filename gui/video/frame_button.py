"""
Frame button widget with hover preview for Veo 3.1 start/end frames.

This module provides a specialized button widget that displays frame images
with hover previews and supports various states (empty, generated, auto-linked).
"""

from pathlib import Path
from typing import Optional, Callable
import logging

from PySide6.QtWidgets import QPushButton, QLabel, QMenu
from PySide6.QtCore import Qt, Signal, QPoint, QEvent
from PySide6.QtGui import QPixmap, QCursor, QIcon, QAction


class FramePreviewPopup(QLabel):
    """Popup label that shows frame preview on hover"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 2px solid #333;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        self.setScaledContents(True)
        self.hide()
        self.logger = logging.getLogger(__name__)

    def show_preview(self, image_path: Path, cursor_pos: QPoint):
        """Show preview at cursor position"""
        try:
            if not image_path or not image_path.exists():
                return

            pixmap = QPixmap(str(image_path))
            if pixmap.isNull():
                return

            # Scale to 200x200 as specified in the plan
            pixmap = pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            self.setPixmap(pixmap)
            self.adjustSize()

            # Position near cursor (offset by 20px)
            from PySide6.QtWidgets import QApplication
            screen_geometry = QApplication.primaryScreen().geometry()
            x = cursor_pos.x() + 20
            y = cursor_pos.y() + 20

            # Adjust if preview would go off screen
            if x + self.width() > screen_geometry.right():
                x = cursor_pos.x() - self.width() - 20
            if y + self.height() > screen_geometry.bottom():
                y = cursor_pos.y() - self.height() - 20

            self.move(x, y)
            self.show()
        except Exception as e:
            self.logger.error(f"Failed to show frame preview: {e}")


class FrameButton(QPushButton):
    """
    Button for start/end frame with hover preview and context menu.

    States:
    - Empty: Shows "+" icon, no frame exists
    - Generated: Shows "🖼️" icon, frame exists
    - Auto-linked: Shows "🔗" icon, using next scene's start frame

    Features:
    - Hover preview (200x200px thumbnail)
    - Right-click context menu (View, Select, Generate, Clear, etc.)
    - Click to open full image viewer
    """

    # Signals
    frame_clicked = Signal()  # Emitted when button is clicked
    generate_requested = Signal()  # Emitted when user requests generation
    select_requested = Signal()  # Emitted when user wants to select from variants
    clear_requested = Signal()  # Emitted when user wants to clear frame
    view_requested = Signal()  # Emitted when user wants to view full image
    auto_link_requested = Signal()  # Emitted when user wants to use auto-link

    def __init__(self, frame_type: str = "start", parent=None):
        """
        Initialize frame button.

        Args:
            frame_type: "start" or "end" to differentiate button types
            parent: Parent widget
        """
        super().__init__(parent)
        self.frame_type = frame_type
        self.frame_path: Optional[Path] = None
        self.is_auto_linked = False
        self.preview_popup: Optional[FramePreviewPopup] = None
        self.logger = logging.getLogger(__name__)

        # Configure button appearance - match LLM button height
        self.setFixedHeight(30)  # Match PromptFieldWidget button height
        self.setMinimumWidth(50)
        self.setMaximumWidth(70)
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
        """)

        # Set initial state
        self.update_appearance()

        # Enable mouse tracking for hover
        self.setMouseTracking(True)

        # Connect signals
        self.clicked.connect(self._on_clicked)

    def set_frame(self, frame_path: Optional[Path], auto_linked: bool = False):
        """
        Set the frame for this button.

        Args:
            frame_path: Path to frame image, or None to clear
            auto_linked: True if this frame is auto-linked from next scene
        """
        self.frame_path = frame_path
        self.is_auto_linked = auto_linked
        self.update_appearance()

    def update_appearance(self):
        """Update button icon/text based on state"""
        if self.is_auto_linked:
            # Auto-linked state
            self.setText("🔗")
            tooltip = f"Auto-linked from next scene's start frame\nClick to view, right-click for options"
        elif self.frame_path and self.frame_path.exists():
            # Generated state
            self.setText("🖼️")
            tooltip = f"{self.frame_type.title()} frame generated\nClick to view, right-click for options\nHover for preview"
        else:
            # Empty state
            self.setText("➕")
            tooltip = f"Generate {self.frame_type} frame\nClick to generate, right-click for options"

        self.setToolTip(tooltip)

    def enterEvent(self, event):
        """Show preview on mouse enter"""
        if self.frame_path and self.frame_path.exists() and not self.is_auto_linked:
            self._show_preview()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hide preview on mouse leave"""
        self._hide_preview()
        super().leaveEvent(event)

    def _show_preview(self):
        """Show 200x200px thumbnail preview"""
        if not self.preview_popup:
            self.preview_popup = FramePreviewPopup(self)

        cursor_pos = QCursor.pos()
        self.preview_popup.show_preview(self.frame_path, cursor_pos)

    def _hide_preview(self):
        """Hide preview"""
        if self.preview_popup:
            self.preview_popup.hide()

    def _on_clicked(self):
        """Handle button click"""
        if self.frame_path and self.frame_path.exists():
            # Has frame: open viewer
            self.view_requested.emit()
        else:
            # No frame: request generation
            self.generate_requested.emit()

    def contextMenuEvent(self, event):
        """Show context menu on right-click"""
        menu = QMenu(self)

        if self.frame_path and self.frame_path.exists():
            # Frame exists: show view/select/regenerate/clear options
            view_action = QAction("View Full Image", self)
            view_action.triggered.connect(self.view_requested.emit)
            menu.addAction(view_action)

            select_action = QAction("Select from Variants", self)
            select_action.triggered.connect(self.select_requested.emit)
            menu.addAction(select_action)

            menu.addSeparator()

            regenerate_action = QAction("Regenerate", self)
            regenerate_action.triggered.connect(self.generate_requested.emit)
            menu.addAction(regenerate_action)

            # End frame specific: option to use next start frame
            if self.frame_type == "end":
                auto_link_action = QAction("Use Next Start Frame", self)
                auto_link_action.triggered.connect(self.auto_link_requested.emit)
                menu.addAction(auto_link_action)

            menu.addSeparator()

            clear_action = QAction("Clear", self)
            clear_action.triggered.connect(self.clear_requested.emit)
            menu.addAction(clear_action)
        else:
            # No frame: show generate options
            generate_action = QAction(f"Generate {self.frame_type.title()} Frame", self)
            generate_action.triggered.connect(self.generate_requested.emit)
            menu.addAction(generate_action)

            select_action = QAction("Select Existing Image...", self)
            select_action.triggered.connect(self.select_requested.emit)
            menu.addAction(select_action)

            # End frame specific: option to use next start frame
            if self.frame_type == "end":
                menu.addSeparator()
                auto_link_action = QAction("Use Next Start Frame", self)
                auto_link_action.triggered.connect(self.auto_link_requested.emit)
                menu.addAction(auto_link_action)

        menu.exec_(event.globalPos())

    def mouseMoveEvent(self, event):
        """Update preview position on mouse move"""
        if self.preview_popup and self.preview_popup.isVisible():
            cursor_pos = QCursor.pos()
            self.preview_popup.show_preview(self.frame_path, cursor_pos)
        super().mouseMoveEvent(event)
