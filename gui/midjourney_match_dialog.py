"""Dialog for confirming Midjourney image-to-prompt associations."""

import logging
from pathlib import Path
from typing import Dict, Optional, List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QGroupBox, QProgressBar, QComboBox,
    QDialogButtonBox, QSplitter, QWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

logger = logging.getLogger(__name__)


class MidjourneyMatchDialog(QDialog):
    """Dialog for confirming image-to-prompt matches."""

    # Signals
    accepted = Signal(str, str, Path)  # session_id, prompt, image_path
    rejected = Signal(Path)  # image_path

    def __init__(self, image_path: Path, confidence_data: Dict,
                 all_sessions: Optional[List] = None, parent=None):
        """
        Initialize the match confirmation dialog.

        Args:
            image_path: Path to the detected image
            confidence_data: Confidence scoring data
            all_sessions: List of all active sessions for manual selection
            parent: Parent widget
        """
        super().__init__(parent)
        self.image_path = image_path
        self.confidence_data = confidence_data
        self.all_sessions = all_sessions or []
        self.selected_session_id = confidence_data.get('session_id')

        self.setup_ui()
        self.load_image()

    def setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle("Confirm Midjourney Image Match")
        self.setModal(True)
        self.resize(900, 600)

        layout = QVBoxLayout(self)

        # Title
        title = QLabel(f"New Midjourney Image Detected: {self.image_path.name}")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; padding: 10px;")
        layout.addWidget(title)

        # Main content splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left side - Image preview
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        image_group = QGroupBox("Image Preview")
        image_layout = QVBoxLayout(image_group)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(400, 400)
        self.image_label.setScaledContents(False)
        self.image_label.setStyleSheet("border: 1px solid #ccc; background: #f0f0f0;")
        image_layout.addWidget(self.image_label)

        left_layout.addWidget(image_group)
        splitter.addWidget(left_widget)

        # Right side - Match details
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Confidence score
        confidence_group = QGroupBox("Confidence Analysis")
        confidence_layout = QVBoxLayout(confidence_group)

        # Confidence bar
        confidence_value = self.confidence_data.get('confidence', 0)
        self.confidence_bar = QProgressBar()
        self.confidence_bar.setRange(0, 100)
        self.confidence_bar.setValue(int(confidence_value))
        self.confidence_bar.setFormat(f"{confidence_value:.0f}% Confidence")

        # Color code based on confidence
        if confidence_value >= 85:
            self.confidence_bar.setStyleSheet("""
                QProgressBar::chunk { background-color: #4CAF50; }
            """)
        elif confidence_value >= 50:
            self.confidence_bar.setStyleSheet("""
                QProgressBar::chunk { background-color: #FFC107; }
            """)
        else:
            self.confidence_bar.setStyleSheet("""
                QProgressBar::chunk { background-color: #F44336; }
            """)

        confidence_layout.addWidget(self.confidence_bar)

        # Confidence details
        details_text = "\n".join(self.confidence_data.get('details', []))
        details_label = QLabel(details_text)
        details_label.setWordWrap(True)
        details_label.setStyleSheet("padding: 10px; background: #f5f5f5;")
        confidence_layout.addWidget(details_label)

        right_layout.addWidget(confidence_group)

        # Prompt selection
        prompt_group = QGroupBox("Associated Prompt")
        prompt_layout = QVBoxLayout(prompt_group)

        # Prompt text
        self.prompt_display = QTextEdit()
        self.prompt_display.setPlainText(self.confidence_data.get('prompt', ''))
        self.prompt_display.setReadOnly(True)
        self.prompt_display.setMaximumHeight(150)
        prompt_layout.addWidget(self.prompt_display)

        # Alternative session selection (if multiple sessions)
        if len(self.all_sessions) > 1:
            select_label = QLabel("Or select a different session:")
            prompt_layout.addWidget(select_label)

            self.session_combo = QComboBox()
            for session in self.all_sessions:
                display_text = f"{session.prompt[:50]}... ({session.time_since_start():.0f}s ago)"
                self.session_combo.addItem(display_text, session.session_id)

            # Set current selection
            if self.selected_session_id:
                for i in range(self.session_combo.count()):
                    if self.session_combo.itemData(i) == self.selected_session_id:
                        self.session_combo.setCurrentIndex(i)
                        break

            self.session_combo.currentIndexChanged.connect(self._on_session_changed)
            prompt_layout.addWidget(self.session_combo)

        right_layout.addWidget(prompt_group)

        # Add stretch
        right_layout.addStretch()

        splitter.addWidget(right_widget)
        splitter.setSizes([450, 450])

        layout.addWidget(splitter)

        # Dialog buttons
        button_layout = QHBoxLayout()

        # Action buttons
        self.accept_btn = QPushButton("✓ Accept Match")
        self.accept_btn.setToolTip("Accept this image-prompt association")
        self.accept_btn.clicked.connect(self._accept_match)
        self.accept_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        button_layout.addWidget(self.accept_btn)

        self.reject_btn = QPushButton("✗ Not This Image")
        self.reject_btn.setToolTip("This is not the correct image")
        self.reject_btn.clicked.connect(self._reject_match)
        self.reject_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        button_layout.addWidget(self.reject_btn)

        button_layout.addStretch()

        self.skip_btn = QPushButton("Skip")
        self.skip_btn.setToolTip("Skip this image for now")
        self.skip_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.skip_btn)

        layout.addLayout(button_layout)

        # Recommendation text
        if confidence_value >= 85:
            rec_text = "✓ High confidence - Recommended to accept"
            rec_color = "#4CAF50"
        elif confidence_value >= 50:
            rec_text = "⚠ Medium confidence - Please verify"
            rec_color = "#FFC107"
        else:
            rec_text = "⚠ Low confidence - Carefully review"
            rec_color = "#F44336"

        rec_label = QLabel(rec_text)
        rec_label.setAlignment(Qt.AlignCenter)
        rec_label.setStyleSheet(f"""
            padding: 10px;
            background-color: {rec_color}20;
            color: {rec_color};
            font-weight: bold;
            border: 1px solid {rec_color};
            border-radius: 5px;
        """)
        layout.addWidget(rec_label)

    def load_image(self):
        """Load and display the image preview."""
        try:
            pixmap = QPixmap(str(self.image_path))
            if not pixmap.isNull():
                # Scale to fit while maintaining aspect ratio
                scaled = pixmap.scaled(
                    400, 400,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.image_label.setPixmap(scaled)
            else:
                self.image_label.setText("Failed to load image")
        except Exception as e:
            logger.error(f"Error loading image preview: {e}")
            self.image_label.setText(f"Error: {str(e)}")

    def _on_session_changed(self, index: int):
        """Handle session selection change."""
        if hasattr(self, 'session_combo'):
            self.selected_session_id = self.session_combo.itemData(index)

            # Update prompt display
            for session in self.all_sessions:
                if session.session_id == self.selected_session_id:
                    self.prompt_display.setPlainText(session.prompt)
                    break

    def _accept_match(self):
        """Accept the image-prompt match."""
        prompt = self.prompt_display.toPlainText()
        if self.selected_session_id and prompt:
            self.accepted.emit(self.selected_session_id, prompt, self.image_path)
            self.accept()
        else:
            logger.warning("No session or prompt selected")

    def _reject_match(self):
        """Reject the image-prompt match."""
        self.rejected.emit(self.image_path)
        self.reject()

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if event.modifiers() & Qt.ControlModifier:
                self._accept_match()
            else:
                # Plain Enter also accepts for convenience
                self._accept_match()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)