"""
Image History Browser Dialog

Allows users to browse and select from previously generated images
for use in layout image blocks.
"""

from pathlib import Path
from typing import Optional, List
import json
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QLineEdit, QComboBox, QFrame, QSplitter
)
from PySide6.QtCore import Qt, Signal, QSize, QThread
from PySide6.QtGui import QPixmap, QImage

from core.config import ConfigManager
from core.logging_config import LogManager


class ImageCard(QFrame):
    """
    A card widget displaying an image thumbnail with metadata.
    """
    clicked = Signal(str)  # Emits image path when clicked

    def __init__(self, image_path: str, metadata: dict, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.metadata = metadata
        self.selected = False

        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setLineWidth(2)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(200, 240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Thumbnail
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(184, 184)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setStyleSheet("background-color: #f0f0f0;")
        self.thumbnail_label.setScaledContents(False)

        # Load and display thumbnail
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(184, 184, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.thumbnail_label.setPixmap(scaled)
        else:
            self.thumbnail_label.setText("No Preview")

        layout.addWidget(self.thumbnail_label)

        # Metadata
        info_text = self._format_metadata()
        self.info_label = QLabel(info_text)
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("font-size: 10px; color: #666;")
        self.info_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.info_label.setMaximumHeight(40)
        layout.addWidget(self.info_label)

        self._update_style()

    def _format_metadata(self) -> str:
        """Format metadata for display."""
        lines = []

        # Provider and model
        provider = self.metadata.get('provider', 'unknown')
        model = self.metadata.get('model', 'unknown')
        lines.append(f"{provider}/{model}")

        # Dimensions
        width = self.metadata.get('width', '?')
        height = self.metadata.get('height', '?')
        lines.append(f"{width}x{height}")

        # Date
        timestamp = self.metadata.get('timestamp', '')
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                lines.append(dt.strftime("%Y-%m-%d %H:%M"))
            except:
                pass

        return "\n".join(lines)

    def mousePressEvent(self, event):
        """Handle click to select."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.image_path)

    def set_selected(self, selected: bool):
        """Update selection state."""
        self.selected = selected
        self._update_style()

    def _update_style(self):
        """Update visual style based on selection."""
        if self.selected:
            self.setStyleSheet("""
                QFrame {
                    border: 2px solid #2196F3;
                    background-color: #E3F2FD;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    border: 1px solid #ddd;
                    background-color: white;
                }
                QFrame:hover {
                    border: 2px solid #64B5F6;
                    background-color: #F5F5F5;
                }
            """)


class ImageHistoryDialog(QDialog):
    """
    Dialog for browsing and selecting previously generated images.
    """

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self.logger = LogManager.get_logger("imageai.layout.image_history")
        self.selected_image_path: Optional[str] = None
        self.image_cards: List[ImageCard] = []

        self.setWindowTitle("Select Image from History")
        self.setMinimumSize(900, 700)

        self._init_ui()
        self._load_images()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Top controls
        controls_layout = QHBoxLayout()

        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by prompt...")
        self.search_input.textChanged.connect(self._filter_images)
        controls_layout.addWidget(QLabel("Search:"))
        controls_layout.addWidget(self.search_input, stretch=1)

        # Provider filter
        self.provider_combo = QComboBox()
        self.provider_combo.addItem("All Providers")
        self.provider_combo.addItems(["google", "openai", "stability", "local"])
        self.provider_combo.currentTextChanged.connect(self._filter_images)
        controls_layout.addWidget(QLabel("Provider:"))
        controls_layout.addWidget(self.provider_combo)

        layout.addLayout(controls_layout)

        # Image grid in scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(12)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        scroll.setWidget(self.grid_container)
        layout.addWidget(scroll, stretch=1)

        # Status label
        self.status_label = QLabel("Loading images...")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.select_btn = QPushButton("Select")
        self.select_btn.setEnabled(False)
        self.select_btn.clicked.connect(self.accept)
        self.select_btn.setMinimumWidth(100)
        button_layout.addWidget(self.select_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumWidth(100)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _load_images(self):
        """Load all generated images from the output directory."""
        try:
            output_dir = self.config.get_output_directory()
            if not output_dir.exists():
                self.status_label.setText("No images found (output directory doesn't exist)")
                return

            # Find all PNG/JPG images
            image_files = []
            for ext in ['*.png', '*.jpg', '*.jpeg']:
                image_files.extend(output_dir.glob(ext))

            if not image_files:
                self.status_label.setText("No generated images found in output directory")
                return

            # Sort by modification time (newest first)
            image_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            # Load metadata for each image
            self.all_images = []
            for img_path in image_files:
                metadata = self._load_metadata(img_path)
                self.all_images.append({
                    'path': str(img_path),
                    'metadata': metadata
                })

            self._display_images(self.all_images)
            self.status_label.setText(f"Found {len(self.all_images)} images")

        except Exception as e:
            self.logger.error(f"Error loading images: {e}")
            self.status_label.setText(f"Error loading images: {e}")

    def _load_metadata(self, image_path: Path) -> dict:
        """Load metadata from sidecar JSON file."""
        metadata_path = image_path.with_suffix(image_path.suffix + '.json')
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Could not load metadata for {image_path.name}: {e}")

        # Default metadata if sidecar doesn't exist
        return {
            'provider': 'unknown',
            'model': 'unknown',
            'prompt': image_path.stem,
            'width': 0,
            'height': 0,
            'timestamp': datetime.fromtimestamp(image_path.stat().st_mtime).isoformat()
        }

    def _display_images(self, images: List[dict]):
        """Display images in the grid."""
        # Clear existing cards
        for card in self.image_cards:
            card.deleteLater()
        self.image_cards.clear()

        # Add image cards to grid
        cols = 4  # Number of columns
        for idx, img_data in enumerate(images):
            card = ImageCard(img_data['path'], img_data['metadata'], self.grid_container)
            card.clicked.connect(self._on_image_selected)

            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(card, row, col)
            self.image_cards.append(card)

    def _filter_images(self):
        """Filter images based on search and provider."""
        search_text = self.search_input.text().lower()
        provider = self.provider_combo.currentText()

        filtered = []
        for img_data in self.all_images:
            # Provider filter
            if provider != "All Providers":
                if img_data['metadata'].get('provider', '').lower() != provider.lower():
                    continue

            # Search filter
            if search_text:
                prompt = img_data['metadata'].get('prompt', '').lower()
                if search_text not in prompt:
                    continue

            filtered.append(img_data)

        self._display_images(filtered)
        self.status_label.setText(f"Showing {len(filtered)} of {len(self.all_images)} images")

    def _on_image_selected(self, image_path: str):
        """Handle image selection."""
        self.selected_image_path = image_path

        # Update visual selection
        for card in self.image_cards:
            card.set_selected(card.image_path == image_path)

        self.select_btn.setEnabled(True)

    def get_selected_image(self) -> Optional[str]:
        """Get the selected image path."""
        return self.selected_image_path
