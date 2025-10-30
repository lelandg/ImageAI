"""
Reference Images Widget for Imagen 3 multi-reference image generation.

This widget manages up to 4 reference images for Imagen 3 Customization API.
Each reference image can have a type (SUBJECT/STYLE) and optional description.
"""

import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QScrollArea, QFrame, QComboBox, QLineEdit,
    QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

from core.reference.imagen_reference import (
    ImagenReference, ImagenReferenceType, ImagenSubjectType,
    validate_references
)

logger = logging.getLogger(__name__)


class ImagenReferenceItemWidget(QWidget):
    """
    Widget for displaying a single Imagen reference image.

    Shows thumbnail, reference ID, type selectors, and description field.
    """

    # Signals
    reference_changed = Signal()  # Emitted when any property changes
    remove_requested = Signal()   # Emitted when remove button clicked

    def __init__(self, reference_id: int, parent=None):
        """
        Initialize reference item widget.

        Args:
            reference_id: Reference ID (1-4) for this item
            parent: Parent widget
        """
        super().__init__(parent)
        self.reference_id = reference_id
        self.reference_path: Optional[Path] = None
        self.logger = logging.getLogger(__name__)

        self._init_ui()

    def _init_ui(self):
        """Initialize user interface."""
        # Main vertical layout for compact side-by-side display
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Add border frame
        self.setStyleSheet("""
            ImagenReferenceItemWidget {
                border: 1px solid #ddd;
                border-radius: 5px;
                background-color: #fafafa;
            }
        """)
        self.setMaximumWidth(250)

        # Top row: ID badge and remove button
        top_row = QHBoxLayout()

        # Reference ID badge
        self.id_label = QLabel(f"[{self.reference_id}]")
        self.id_label.setStyleSheet("""
            QLabel {
                background-color: #2196F3;
                color: white;
                padding: 3px 8px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 10pt;
            }
        """)
        top_row.addWidget(self.id_label)

        top_row.addStretch()

        # Remove button
        self.btn_remove = QPushButton("✕")
        self.btn_remove.setFixedSize(24, 24)
        self.btn_remove.setToolTip("Remove this reference image")
        self.btn_remove.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 12pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        self.btn_remove.clicked.connect(self.remove_requested.emit)
        top_row.addWidget(self.btn_remove)

        layout.addLayout(top_row)

        # Thumbnail (centered)
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(120, 120)
        self.thumbnail_label.setStyleSheet("""
            QLabel {
                border: 2px solid #ddd;
                background-color: #f5f5f5;
            }
        """)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setText("No Image")
        layout.addWidget(self.thumbnail_label, alignment=Qt.AlignCenter)

        # File name label
        self.filename_label = QLabel("No file selected")
        self.filename_label.setStyleSheet("color: #666; font-size: 8pt;")
        self.filename_label.setWordWrap(True)
        self.filename_label.setAlignment(Qt.AlignCenter)
        self.filename_label.setMaximumWidth(240)
        layout.addWidget(self.filename_label)

        # Reference type selector
        type_layout = QVBoxLayout()
        type_layout.setSpacing(3)
        type_layout.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            ImagenReferenceType.SUBJECT.value.upper(),
            ImagenReferenceType.STYLE.value.upper(),
            ImagenReferenceType.CONTROL.value.upper()
        ])
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)

        # Subject type selector (only for SUBJECT references)
        subject_layout = QVBoxLayout()
        subject_layout.setSpacing(3)
        self.subject_label = QLabel("Subject:")
        subject_layout.addWidget(self.subject_label)
        self.subject_type_combo = QComboBox()
        self.subject_type_combo.addItems([
            ImagenSubjectType.PERSON.value.upper(),
            ImagenSubjectType.ANIMAL.value.upper(),
            ImagenSubjectType.PRODUCT.value.upper(),
            ImagenSubjectType.DEFAULT.value.upper()
        ])
        self.subject_type_combo.currentTextChanged.connect(self._on_subject_type_changed)
        subject_layout.addWidget(self.subject_type_combo)
        layout.addLayout(subject_layout)

        # Control type selector (only for CONTROL references)
        from core.reference.imagen_reference import ImagenControlType
        control_layout = QVBoxLayout()
        control_layout.setSpacing(3)
        self.control_label = QLabel("Control Type:")
        control_layout.addWidget(self.control_label)
        self.control_type_combo = QComboBox()
        self.control_type_combo.addItems([
            ImagenControlType.CANNY.value.upper(),
            ImagenControlType.SCRIBBLE.value.upper(),
            ImagenControlType.FACE_MESH.value.upper()
        ])
        self.control_type_combo.currentTextChanged.connect(self._on_control_type_changed)
        control_layout.addWidget(self.control_type_combo)
        layout.addLayout(control_layout)

        # Description field
        desc_layout = QVBoxLayout()
        desc_layout.setSpacing(3)
        desc_layout.addWidget(QLabel("Description:"))
        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Optional...")
        # Use lambda to ignore text parameter from textChanged signal
        self.description_edit.textChanged.connect(lambda: self.reference_changed.emit())
        desc_layout.addWidget(self.description_edit)
        layout.addLayout(desc_layout)

        layout.addStretch()

        # Update visibility based on initial type
        self._on_type_changed()

    def _on_control_type_changed(self):
        """Handle control type change."""
        self.reference_changed.emit()

    def set_reference_image(self, path: Path):
        """
        Set the reference image path.

        Args:
            path: Path to reference image file
        """
        self.reference_path = path

        # Update thumbnail
        if path and path.exists():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    116, 116,  # Slightly smaller than label for border
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.thumbnail_label.setPixmap(scaled_pixmap)
                self.thumbnail_label.setText("")

            # Update filename
            self.filename_label.setText(path.name)
        else:
            self.thumbnail_label.clear()
            self.thumbnail_label.setText("No Image")
            self.filename_label.setText("No file selected")

        self.reference_changed.emit()

    def get_reference(self) -> Optional[ImagenReference]:
        """
        Get the ImagenReference object for this item.

        Returns:
            ImagenReference if valid, None if no image set
        """
        if not self.reference_path or not self.reference_path.exists():
            return None

        # Get reference type
        ref_type_str = self.type_combo.currentText().lower()
        ref_type = ImagenReferenceType(ref_type_str)

        # Get subject type (if applicable)
        subject_type = None
        if ref_type == ImagenReferenceType.SUBJECT:
            subject_type_str = self.subject_type_combo.currentText().lower()
            subject_type = ImagenSubjectType(subject_type_str)

        # Get control type (if applicable)
        from core.reference.imagen_reference import ImagenControlType
        control_type = None
        if ref_type == ImagenReferenceType.CONTROL:
            control_type_str = self.control_type_combo.currentText().lower()
            control_type = ImagenControlType(control_type_str)

        # Get description
        description = self.description_edit.text().strip() or None

        return ImagenReference(
            path=self.reference_path,
            reference_type=ref_type,
            reference_id=self.reference_id,
            subject_type=subject_type,
            subject_description=description,
            control_type=control_type
        )

    def clear(self):
        """Clear the reference image."""
        self.reference_path = None
        self.thumbnail_label.clear()
        self.thumbnail_label.setText("No Image")
        self.filename_label.setText("No file selected")
        self.description_edit.clear()
        self.reference_changed.emit()

    def _on_type_changed(self):
        """Handle reference type change."""
        ref_type = self.type_combo.currentText()

        # Show/hide subject type selector based on reference type
        is_subject = ref_type == ImagenReferenceType.SUBJECT.value.upper()
        self.subject_type_combo.setVisible(is_subject)
        self.subject_label.setVisible(is_subject)

        # Show/hide control type selector based on reference type
        is_control = ref_type == ImagenReferenceType.CONTROL.value.upper()
        self.control_type_combo.setVisible(is_control)
        self.control_label.setVisible(is_control)

        # Update description placeholder
        if ref_type == ImagenReferenceType.STYLE.value.upper():
            self.description_edit.setPlaceholderText("Style desc...")
        elif is_control:
            self.description_edit.setPlaceholderText("Control desc...")
        else:
            self.description_edit.setPlaceholderText("Optional...")

        self.reference_changed.emit()

    def _on_subject_type_changed(self):
        """Handle subject type change."""
        self.reference_changed.emit()


class ImagenReferenceWidget(QWidget):
    """
    Main widget for managing Imagen 3 reference images.

    Allows adding up to 4 reference images with types and descriptions.
    Provides signals for when references change.
    """

    # Signals
    references_changed = Signal()  # Emitted when reference list changes

    def __init__(self, parent=None):
        """
        Initialize Imagen reference widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.max_references = 4
        self.reference_items: List[ImagenReferenceItemWidget] = []
        self.logger = logging.getLogger(__name__)

        self._init_ui()

    def _init_ui(self):
        """Initialize user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)

        # Header with count and add button
        header_layout = QHBoxLayout()

        self.count_label = QLabel("Reference Images (0/4)")
        self.count_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        header_layout.addWidget(self.count_label)

        header_layout.addStretch()

        self.btn_add = QPushButton("+ Add Reference Image")
        self.btn_add.setToolTip("Add a reference image (max 4)")
        self.btn_add.clicked.connect(self._add_reference)
        header_layout.addWidget(self.btn_add)

        main_layout.addLayout(header_layout)

        # Horizontal container for reference items (side-by-side)
        self.items_container = QWidget()
        self.items_layout = QHBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(10)
        self.items_layout.addStretch()

        main_layout.addWidget(self.items_container)

        # Info label
        info_label = QLabel("💡 Use [1], [2], [3], [4] in your prompt to reference these images\n"
                           "⚠️ Only works with Google Imagen 3 provider")
        info_label.setStyleSheet("color: #666; font-size: 9pt; padding: 5px;")
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)

    def _add_reference(self):
        """Add a new reference image."""
        # Check max references
        if len(self.reference_items) >= self.max_references:
            QMessageBox.warning(
                self,
                "Maximum References",
                f"Maximum {self.max_references} reference images allowed for Imagen 3."
            )
            return

        # Open file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reference Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.gif *.webp);;All Files (*.*)"
        )

        if not file_path:
            return

        # Create reference item
        reference_id = len(self.reference_items) + 1
        item_widget = ImagenReferenceItemWidget(reference_id, parent=self)
        item_widget.set_reference_image(Path(file_path))
        item_widget.reference_changed.connect(self._on_reference_changed)
        item_widget.remove_requested.connect(lambda: self._remove_reference(item_widget))

        # Add to layout (before stretch)
        self.items_layout.insertWidget(len(self.reference_items), item_widget)
        self.reference_items.append(item_widget)

        self._update_ui()
        self.logger.info(f"Added reference image {reference_id}: {file_path}")

    def _remove_reference(self, item_widget: ImagenReferenceItemWidget):
        """
        Remove a reference image.

        Args:
            item_widget: The item widget to remove
        """
        if item_widget in self.reference_items:
            self.reference_items.remove(item_widget)
            self.items_layout.removeWidget(item_widget)
            item_widget.deleteLater()

            # Reassign reference IDs
            for idx, item in enumerate(self.reference_items, start=1):
                item.reference_id = idx
                # Update the ID label using the stored reference
                if hasattr(item, 'id_label'):
                    item.id_label.setText(f"[{idx}]")

            self._update_ui()
            self.logger.info(f"Removed reference image, {len(self.reference_items)} remaining")

    def _on_reference_changed(self):
        """Handle when a reference item changes."""
        self.references_changed.emit()

    def _update_ui(self):
        """Update UI elements based on current state."""
        count = len(self.reference_items)
        self.count_label.setText(f"Reference Images ({count}/{self.max_references})")
        self.btn_add.setEnabled(count < self.max_references)
        self.references_changed.emit()

    def get_references(self) -> List[ImagenReference]:
        """
        Get all valid reference images.

        Returns:
            List of ImagenReference objects
        """
        references = []
        for item in self.reference_items:
            ref = item.get_reference()
            if ref:
                references.append(ref)
        return references

    def has_references(self) -> bool:
        """
        Check if any references are set.

        Returns:
            True if at least one reference exists
        """
        return len(self.get_references()) > 0

    def validate_references(self) -> tuple[bool, list[str]]:
        """
        Validate all references.

        Returns:
            Tuple of (is_valid, error_messages)
        """
        references = self.get_references()

        if not references:
            return True, []  # No references is valid (optional feature)

        return validate_references(references)

    def clear_all(self):
        """Clear all reference images."""
        for item in list(self.reference_items):
            self._remove_reference(item)

    def to_dict(self) -> list:
        """
        Serialize all references to a list of dictionaries.

        Returns:
            List of reference dictionaries
        """
        references = self.get_references()
        return [ref.to_dict() for ref in references]

    def from_dict(self, data: list):
        """
        Load references from a list of dictionaries.

        Args:
            data: List of reference dictionaries
        """
        # Clear existing references
        self.clear_all()

        if not data:
            return

        # Load each reference
        from core.reference.imagen_reference import ImagenReference
        for ref_dict in data:
            try:
                # Create ImagenReference from dict
                ref = ImagenReference.from_dict(ref_dict)

                # Verify the file still exists
                if not ref.path.exists():
                    self.logger.warning(f"Reference image not found: {ref.path}")
                    continue

                # Create reference item widget
                item_widget = ImagenReferenceItemWidget(ref.reference_id, parent=self)
                item_widget.set_reference_image(ref.path)

                # Set the type
                item_widget.type_combo.setCurrentText(ref.reference_type.value.upper())

                # Set subject type if applicable
                if ref.subject_type:
                    item_widget.subject_type_combo.setCurrentText(ref.subject_type.value.upper())

                # Set control type if applicable
                if ref.control_type:
                    item_widget.control_type_combo.setCurrentText(ref.control_type.value.upper())

                # Set description
                if ref.subject_description:
                    item_widget.description_edit.setText(ref.subject_description)

                # Connect signals
                item_widget.reference_changed.connect(self._on_reference_changed)
                item_widget.remove_requested.connect(lambda w=item_widget: self._remove_reference(w))

                # Add to layout (before stretch)
                self.items_layout.insertWidget(len(self.reference_items), item_widget)
                self.reference_items.append(item_widget)

            except Exception as e:
                self.logger.error(f"Failed to load reference from dict: {e}")

        self._update_ui()
        self.logger.info(f"Loaded {len(self.reference_items)} reference images from dict")
