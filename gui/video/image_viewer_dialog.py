"""Simple image viewer dialog for displaying video frames and images."""

from pathlib import Path
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QKeySequence, QShortcut


class ImageViewerDialog(QDialog):
    """Simple dialog for viewing an image."""

    def __init__(self, image_path: Path, title: str = "Image Viewer", parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setWindowTitle(title)
        self.setMinimumSize(600, 400)

        self.init_ui()
        self.load_image()

        # Escape to close
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self.close)

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Image display
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("QLabel { background-color: #2b2b2b; }")
        layout.addWidget(self.image_label)

        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def load_image(self):
        """Load and display the image."""
        if not self.image_path or not self.image_path.exists():
            self.image_label.setText("Image not found")
            return

        pixmap = QPixmap(str(self.image_path))
        if pixmap.isNull():
            self.image_label.setText("Failed to load image")
            return

        # Scale to fit dialog while maintaining aspect ratio
        scaled_pixmap = pixmap.scaled(
            self.image_label.size() * 2,  # Allow larger images
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        """Handle resize to scale image."""
        super().resizeEvent(event)
        if hasattr(self, 'image_path') and self.image_path and self.image_path.exists():
            self.load_image()
