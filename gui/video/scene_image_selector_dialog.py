"""Dialog for selecting images from any scene in the project."""

from pathlib import Path
from typing import List, Optional, Tuple
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QGridLayout, QButtonGroup, QRadioButton,
    QGroupBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


class SceneImageSelectorDialog(QDialog):
    """Dialog for selecting an image from any scene in the project."""

    def __init__(self, scenes: List, current_scene_index: int,
                 title: str = "Select Image from Scenes", parent=None):
        """
        Initialize the scene image selector dialog.

        Args:
            scenes: List of Scene objects from the project
            current_scene_index: Index of the current scene (for context)
            title: Dialog window title
            parent: Parent widget
        """
        super().__init__(parent)
        self.scenes = scenes
        self.current_scene_index = current_scene_index
        self.selected_image: Optional[Path] = None
        self.selected_scene_index: Optional[int] = None

        self.setWindowTitle(title)
        self.setMinimumSize(900, 700)

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel(f"Select an image from any scene (currently editing Scene {self.current_scene_index + 1}):")
        instructions.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(instructions)

        # Scroll area for all scenes
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        # Container widget for all scene groups
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(15)

        # Button group for radio buttons (to make them mutually exclusive across all scenes)
        self.button_group = QButtonGroup(self)

        # Create a group box for each scene that has images or last frame
        # NO FILE CHECKS - just check if the path is set
        scenes_with_images = []
        for scene_idx, scene in enumerate(self.scenes):
            has_images = hasattr(scene, 'images') and scene.images
            has_last_frame = hasattr(scene, 'last_frame') and scene.last_frame is not None
            if has_images or has_last_frame:
                scenes_with_images.append((scene_idx, scene))

        if not scenes_with_images:
            # No images available in any scene
            no_images_label = QLabel("No scenes have generated images yet.\nGenerate images first.")
            no_images_label.setStyleSheet("padding: 20px; color: #666;")
            no_images_label.setAlignment(Qt.AlignCenter)
            container_layout.addWidget(no_images_label)
        else:
            # Create scene groups
            for scene_idx, scene in scenes_with_images:
                scene_group = self._create_scene_group(scene_idx, scene)
                container_layout.addWidget(scene_group)

        container_layout.addStretch()
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
        select_btn.setEnabled(False)  # Disabled until selection is made
        self.select_btn = select_btn
        button_layout.addWidget(select_btn)

        layout.addLayout(button_layout)

    def _create_scene_group(self, scene_idx: int, scene) -> QGroupBox:
        """Create a group box for a scene's images."""
        # Group box title
        scene_num = scene_idx + 1
        title = f"Scene {scene_num}"
        if hasattr(scene, 'source') and scene.source:
            # Show first 50 chars of source text
            source_preview = scene.source[:50] + "..." if len(scene.source) > 50 else scene.source
            title += f" - {source_preview}"

        group_box = QGroupBox(title)
        group_layout = QVBoxLayout(group_box)

        # Grid for images
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)

        # Collect all images from this scene (variants + last frame)
        from core.video.project import ImageVariant
        all_images = []

        # Add scene images (variants)
        for variant in scene.images:
            if isinstance(variant, ImageVariant):
                all_images.append(("variant", variant.path))
            else:
                all_images.append(("variant", Path(variant)))

        # Add last frame if set (assume it exists - extracted frames are already on disk)
        if hasattr(scene, 'last_frame') and scene.last_frame:
            # Check if last_frame is already in the variant list
            last_frame_in_variants = any(img_path == scene.last_frame for _, img_path in all_images)
            if not last_frame_in_variants:
                all_images.append(("last_frame", scene.last_frame))

        columns = 4
        for img_idx, (img_type, img_path) in enumerate(all_images):
            # img_path is already extracted from tuple
            if not img_path:
                continue
            try:
                if not img_path.exists():
                    continue
            except:
                continue  # Invalid path

            # Create card widget
            card = QWidget()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(5, 5, 5, 5)

            # Radio button
            radio = QRadioButton()
            radio.setProperty("image_path", str(img_path))
            radio.setProperty("scene_index", scene_idx)

            # Connect radio button to update selection
            radio.toggled.connect(
                lambda checked, path=img_path, idx=scene_idx: self._on_selection_changed(checked, path, idx)
            )

            self.button_group.addButton(radio)
            card_layout.addWidget(radio, alignment=Qt.AlignCenter)

            # Image preview
            pixmap = QPixmap(str(img_path))
            if not pixmap.isNull():
                # Scale to fit (150x150 thumbnail - smaller since we show more images)
                pixmap = pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)

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

            # Image type label
            if img_type == "last_frame":
                type_label = QLabel("Last Frame")
                type_label.setStyleSheet("font-size: 10px; color: #0066cc; font-weight: bold;")
            else:
                # Count variant number (excluding last frames)
                variant_num = sum(1 for j in range(img_idx + 1) if all_images[j][0] == "variant")
                type_label = QLabel(f"Variant {variant_num}")
                type_label.setStyleSheet("font-size: 10px; color: #666;")
            type_label.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(type_label)

            # Add card to grid
            row = img_idx // columns
            col = img_idx % columns
            grid_layout.addWidget(card, row, col)

        group_layout.addLayout(grid_layout)
        return group_box

    def _on_selection_changed(self, checked: bool, image_path: Path, scene_index: int):
        """Handle selection change."""
        if checked:
            self.selected_image = image_path
            self.selected_scene_index = scene_index
            self.select_btn.setEnabled(True)

    def get_selected_image(self) -> Optional[Path]:
        """Get the selected image path."""
        return self.selected_image

    def get_selected_scene_index(self) -> Optional[int]:
        """Get the scene index of the selected image."""
        return self.selected_scene_index
