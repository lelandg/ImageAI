"""
Floating image preview popup for hover preview functionality.
"""

from pathlib import Path
from PySide6.QtWidgets import QLabel, QFrame
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QPixmap, QPainter, QColor

class ImagePreviewPopup(QLabel):
    """Floating popup window that shows full-size image preview on hover."""

    def __init__(self, parent=None, max_width=400, max_height=400):
        super().__init__(parent)
        self.max_width = max_width
        self.max_height = max_height

        # Configure as popup
        self.setWindowFlags(
            Qt.ToolTip |  # Bypass window manager
            Qt.FramelessWindowHint |  # No window frame
            Qt.WindowStaysOnTopHint  # Always on top
        )

        # Style
        self.setFrameShape(QFrame.Box)
        self.setLineWidth(2)
        self.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                border: 2px solid #555;
                border-radius: 4px;
                padding: 4px;
            }
        """)

        # Center alignment for image
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(False)

        # Hide by default
        self.hide()

        # Timer for delayed hide (prevents flicker)
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

    def show_preview(self, image_path: Path, cursor_pos: QPoint):
        """
        Show preview at cursor position with smart positioning.

        Args:
            image_path: Path to image file
            cursor_pos: Global cursor position
        """
        if not image_path or not Path(image_path).exists():
            self.hide()
            return

        # Cancel any pending hide
        self.hide_timer.stop()

        # Load and scale image
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            self.hide()
            return

        # Scale to fit within max dimensions while preserving aspect ratio
        scaled_pixmap = pixmap.scaled(
            self.max_width,
            self.max_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.setPixmap(scaled_pixmap)

        # Calculate popup position (offset from cursor to avoid blocking it)
        offset_x = 15
        offset_y = 15

        popup_x = cursor_pos.x() + offset_x
        popup_y = cursor_pos.y() + offset_y

        # Get screen geometry to keep popup on screen
        screen = self.screen() if hasattr(self, 'screen') else None
        if screen:
            screen_rect = screen.availableGeometry()

            # Adjust if popup would go off right edge
            if popup_x + scaled_pixmap.width() + 10 > screen_rect.right():
                popup_x = cursor_pos.x() - scaled_pixmap.width() - offset_x

            # Adjust if popup would go off bottom edge
            if popup_y + scaled_pixmap.height() + 10 > screen_rect.bottom():
                popup_y = cursor_pos.y() - scaled_pixmap.height() - offset_y

            # Keep on screen (left/top edges)
            popup_x = max(screen_rect.left(), popup_x)
            popup_y = max(screen_rect.top(), popup_y)

        # Position and show
        self.move(popup_x, popup_y)
        self.show()
        self.raise_()

    def schedule_hide(self, delay_ms=200):
        """Schedule hiding the popup after a delay."""
        self.hide_timer.start(delay_ms)

    def cancel_hide(self):
        """Cancel scheduled hide."""
        self.hide_timer.stop()
