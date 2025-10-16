"""Dialog for selecting image variants for start/end frames."""

from pathlib import Path
from typing import List, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QGridLayout, QButtonGroup, QRadioButton
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


class VariantSelectorDialog(QDialog):
    """Dialog for selecting an image variant from a list of generated images."""

    def __init__(self, image_variants: List, current_selection: Optional[Path] = None,
                 title: str = "Select Image", parent=None):
        """
        Initialize the variant selector dialog.

        Args:
            image_variants: List of ImageVariant objects or Path objects
            current_selection: Currently selected image path (to show as selected)
            title: Dialog window title
            parent: Parent widget
        """
        super().__init__(parent)
        self.image_variants = image_variants
        self.current_selection = current_selection
        self.selected_image: Optional[Path] = current_selection

        self.setWindowTitle(title)
        self.setMinimumSize(800, 600)

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel("Select an image variant:")
        instructions.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(instructions)

        # Scroll area for images
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Container widget for grid
        container = QWidget()
        grid_layout = QGridLayout(container)
        grid_layout.setSpacing(10)

        # Button group for radio buttons (to make them mutually exclusive)
        self.button_group = QButtonGroup(self)

        # Create image cards in a grid (3 columns)
        columns = 3
        for i, variant in enumerate(self.image_variants):
            # Get path from variant (could be ImageVariant object or Path)
            from core.video.project import ImageVariant
            if isinstance(variant, ImageVariant):
                img_path = variant.path
            else:
                img_path = Path(variant)

            if not img_path or not img_path.exists():
                continue

            # Create card widget
            card = QWidget()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(5, 5, 5, 5)

            # Radio button
            radio = QRadioButton()
            radio.setProperty("image_path", str(img_path))

            # Check if this is the current selection
            if self.current_selection and img_path == self.current_selection:
                radio.setChecked(True)

            # Connect radio button to update selection
            radio.toggled.connect(lambda checked, path=img_path: self._on_selection_changed(checked, path))

            self.button_group.addButton(radio)
            card_layout.addWidget(radio, alignment=Qt.AlignCenter)

            # Image preview
            pixmap = QPixmap(str(img_path))
            if not pixmap.isNull():
                # Scale to fit (200x200 thumbnail)
                pixmap = pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                image_label = QLabel()
                image_label.setPixmap(pixmap)
                image_label.setAlignment(Qt.AlignCenter)
                image_label.setStyleSheet("""
                    QLabel {
                        border: 2px solid #ccc;
                        border-radius: 5px;
                        padding: 5px;
                        background-color: white;
                    }
                """)

                # Make clickable
                image_label.mousePressEvent = lambda event, r=radio: r.setChecked(True)

                card_layout.addWidget(image_label)

            # Filename label
            filename_label = QLabel(img_path.name)
            filename_label.setWordWrap(True)
            filename_label.setAlignment(Qt.AlignCenter)
            filename_label.setStyleSheet("font-size: 10px; color: #666;")
            card_layout.addWidget(filename_label)

            # Add card to grid
            row = i // columns
            col = i % columns
            grid_layout.addWidget(card, row, col)

        scroll_area.setWidget(container)
        layout.addWidget(scroll_area)

        # Button box
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        select_btn = QPushButton("Select")
        select_btn.setDefault(True)
        select_btn.clicked.connect(self.accept)
        button_layout.addWidget(select_btn)

        layout.addLayout(button_layout)

    def _on_selection_changed(self, checked: bool, image_path: Path):
        """Handle selection change."""
        if checked:
            self.selected_image = image_path

    def get_selected_image(self) -> Optional[Path]:
        """Get the selected image path."""
        return self.selected_image
