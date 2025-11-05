"""
Reference Image Selection Dialog.

Reusable dialog for selecting N images from a larger set.
Used when switching modes or managing reference image limits.
"""

import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QCheckBox, QFrame, QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

logger = logging.getLogger(__name__)


class ReferenceImageCard(QFrame):
    """
    Selectable card widget for a reference image.
    """

    selection_changed = Signal(bool)  # selected state

    def __init__(self, image_path: Path, reference_id: int, parent=None):
        """
        Initialize reference image card.

        Args:
            image_path: Path to the reference image
            reference_id: Reference ID number
            parent: Parent widget
        """
        super().__init__(parent)
        self.image_path = image_path
        self.reference_id = reference_id
        self.is_selected = False

        self.setFrameShape(QFrame.Box)
        self.setLineWidth(2)
        self.setFixedSize(160, 220)

        self._init_ui()
        self._update_style()

    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        # Header with checkbox and ID
        header_layout = QHBoxLayout()

        self.checkbox = QCheckBox()
        self.checkbox.stateChanged.connect(self._on_checkbox_changed)
        header_layout.addWidget(self.checkbox)

        id_label = QLabel(f"[{self.reference_id}]")
        id_label.setStyleSheet("""
            QLabel {
                background-color: #2196F3;
                color: white;
                padding: 2px 6px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 9pt;
            }
        """)
        header_layout.addWidget(id_label)

        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Image thumbnail
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(140, 140)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setStyleSheet("background-color: #f5f5f5; border: 1px solid #ddd;")

        # Load thumbnail
        if self.image_path.exists():
            pixmap = QPixmap(str(self.image_path))
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    138, 138,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.thumbnail_label.setPixmap(scaled_pixmap)
            else:
                self.thumbnail_label.setText("Error")
        else:
            self.thumbnail_label.setText("Not Found")

        layout.addWidget(self.thumbnail_label)

        # Filename
        filename_label = QLabel(self.image_path.name)
        filename_label.setWordWrap(True)
        filename_label.setAlignment(Qt.AlignCenter)
        filename_label.setStyleSheet("font-size: 8pt; color: #666;")
        filename_label.setMaximumWidth(150)
        layout.addWidget(filename_label)

    def _on_checkbox_changed(self, state):
        """Handle checkbox state change."""
        self.is_selected = (state == Qt.CheckState.Checked.value)
        self._update_style()
        self.selection_changed.emit(self.is_selected)

    def _update_style(self):
        """Update card style based on selection."""
        if self.is_selected:
            self.setStyleSheet("""
                ReferenceImageCard {
                    border: 3px solid #4CAF50;
                    background-color: #f0fff0;
                }
            """)
        else:
            self.setStyleSheet("""
                ReferenceImageCard {
                    border: 2px solid #ddd;
                    background-color: white;
                }
            """)

    def set_selected(self, selected: bool):
        """Set selection state programmatically."""
        self.checkbox.setChecked(selected)

    def mousePressEvent(self, event):
        """Toggle selection on click."""
        if event.button() == Qt.LeftButton:
            self.checkbox.setChecked(not self.checkbox.isChecked())
        super().mousePressEvent(event)


class ReferenceSelectionDialog(QDialog):
    """
    Dialog for selecting N reference images from a larger set.

    Used when switching modes or enforcing reference image limits.
    """

    def __init__(
        self,
        image_paths: List[Path],
        max_selection: int,
        title: str = "Select Reference Images",
        message: str = "",
        parent=None
    ):
        """
        Initialize selection dialog.

        Args:
            image_paths: List of image paths to choose from
            max_selection: Maximum number of images that can be selected
            title: Dialog title
            message: Explanation message shown to user
            parent: Parent widget
        """
        super().__init__(parent)
        self.image_paths = image_paths
        self.max_selection = max_selection
        self.selected_paths: List[Path] = []
        self.cards: List[ReferenceImageCard] = []

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(800, 600)

        self._init_ui(message)

    def _init_ui(self, message: str):
        """Initialize UI."""
        layout = QVBoxLayout(self)

        # Header with message
        if message:
            msg_label = QLabel(message)
            msg_label.setWordWrap(True)
            msg_label.setStyleSheet("padding: 10px; font-size: 11pt;")
            layout.addWidget(msg_label)

        # Selection counter
        self.counter_label = QLabel(f"Selected: 0 / {self.max_selection}")
        self.counter_label.setStyleSheet("font-weight: bold; font-size: 11pt; padding: 5px;")
        layout.addWidget(self.counter_label)

        # Scroll area with cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(400)

        scroll_widget = QWidget()
        self.cards_layout = QHBoxLayout(scroll_widget)
        self.cards_layout.setAlignment(Qt.AlignLeft)
        self.cards_layout.setSpacing(15)

        # Create cards for each image
        for idx, img_path in enumerate(self.image_paths, start=1):
            card = ReferenceImageCard(img_path, idx, self)
            card.selection_changed.connect(self._on_selection_changed)
            self.cards_layout.addWidget(card)
            self.cards.append(card)

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, stretch=1)

        # Button box
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Store OK button for enabling/disabling
        self.ok_button = button_box.button(QDialogButtonBox.Ok)
        self._update_ok_button()

    def _on_selection_changed(self, selected: bool):
        """Handle selection change."""
        # Count selected
        selected_count = sum(1 for card in self.cards if card.is_selected)

        # Update counter
        self.counter_label.setText(f"Selected: {selected_count} / {self.max_selection}")

        # If trying to select more than max, deselect the most recent
        if selected_count > self.max_selection:
            # Find the most recently selected card and deselect it
            for card in reversed(self.cards):
                if card.is_selected:
                    card.set_selected(False)
                    break

        # Update OK button state
        self._update_ok_button()

    def _update_ok_button(self):
        """Update OK button enabled state."""
        selected_count = sum(1 for card in self.cards if card.is_selected)
        self.ok_button.setEnabled(selected_count == self.max_selection)

        # Update counter color
        if selected_count == self.max_selection:
            self.counter_label.setStyleSheet(
                "font-weight: bold; font-size: 11pt; padding: 5px; color: #4CAF50;"
            )
        else:
            self.counter_label.setStyleSheet(
                "font-weight: bold; font-size: 11pt; padding: 5px; color: #666;"
            )

    def _on_accept(self):
        """Handle OK button click."""
        # Collect selected paths
        self.selected_paths = [
            card.image_path for card in self.cards if card.is_selected
        ]

        if len(self.selected_paths) != self.max_selection:
            logger.warning(
                f"Selection mismatch: expected {self.max_selection}, "
                f"got {len(self.selected_paths)}"
            )
            return

        logger.info(f"Selected {len(self.selected_paths)} reference images")
        self.accept()

    def get_selected_paths(self) -> List[Path]:
        """
        Get the selected image paths.

        Returns:
            List of selected paths (exactly max_selection items)
        """
        return self.selected_paths
