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
    QSizePolicy, QMessageBox, QRadioButton, QButtonGroup
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
        layout.setContentsMargins(5, 5, 5, 10)  # Extra bottom padding for combo boxes
        layout.setSpacing(5)

        # Add border frame and ensure proper z-ordering for combo boxes
        self.setStyleSheet("""
            ImagenReferenceItemWidget {
                border: 1px solid #ddd;
                border-radius: 5px;
                background-color: #fafafa;
            }
            QComboBox {
                padding: 3px;
                background-color: white;
                color: black;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
            QComboBox:hover {
                border: 1px solid #4A90E2;
                background-color: white;
                color: black;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #999;
                selection-background-color: #4A90E2;
                selection-color: white;
                background-color: white;
                color: black;
            }
        """)
        self.setMaximumWidth(250)
        # Compact height without extra stretch space
        self.setMinimumHeight(280)

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
        type_layout = QHBoxLayout()
        type_layout.setSpacing(5)
        type_layout.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.setAutoFillBackground(True)  # Ensure opaque background
        self.type_combo.addItems([
            ImagenReferenceType.SUBJECT.value.upper(),
            ImagenReferenceType.STYLE.value.upper(),
            ImagenReferenceType.CONTROL.value.upper()
        ])
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.type_combo, 1)  # Stretch combo to fill space
        layout.addLayout(type_layout)

        # Subject type selector (only for SUBJECT references)
        subject_layout = QHBoxLayout()
        subject_layout.setSpacing(5)
        self.subject_label = QLabel("Subject:")
        subject_layout.addWidget(self.subject_label)
        self.subject_type_combo = QComboBox()
        self.subject_type_combo.setAutoFillBackground(True)  # Ensure opaque background
        self.subject_type_combo.addItems([
            ImagenSubjectType.PERSON.value.upper(),
            ImagenSubjectType.ANIMAL.value.upper(),
            ImagenSubjectType.PRODUCT.value.upper(),
            ImagenSubjectType.DEFAULT.value.upper()
        ])
        self.subject_type_combo.currentTextChanged.connect(self._on_subject_type_changed)
        subject_layout.addWidget(self.subject_type_combo, 1)  # Stretch combo to fill space
        layout.addLayout(subject_layout)

        # Control type selector (only for CONTROL references)
        from core.reference.imagen_reference import ImagenControlType
        control_layout = QHBoxLayout()
        control_layout.setSpacing(5)
        self.control_label = QLabel("Control:")
        control_layout.addWidget(self.control_label)
        self.control_type_combo = QComboBox()
        self.control_type_combo.setAutoFillBackground(True)  # Ensure opaque background
        self.control_type_combo.addItems([
            ImagenControlType.CANNY.value.upper(),
            ImagenControlType.SCRIBBLE.value.upper(),
            ImagenControlType.FACE_MESH.value.upper()
        ])
        self.control_type_combo.currentTextChanged.connect(self._on_control_type_changed)
        control_layout.addWidget(self.control_type_combo, 1)  # Stretch combo to fill space
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

    Supports two modes:
    - Flexible: Single reference, style transformation (Google Gemini)
    - Strict: Multi-reference, subject preservation (Imagen 3 Customization)
    """

    # Signals
    references_changed = Signal()  # Emitted when reference list changes
    mode_changed = Signal(str)     # Emitted when mode changes (flexible/strict)

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
        self.current_mode = "strict"  # Default to strict mode

        self._init_ui()

    def _init_ui(self):
        """Initialize user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)

        # Mode selector (Flexible vs Strict)
        mode_layout = QHBoxLayout()
        mode_label = QLabel("Reference Mode:")
        mode_label.setStyleSheet("font-weight: bold;")
        mode_layout.addWidget(mode_label)

        # Create button group for exclusive selection
        self.mode_button_group = QButtonGroup(self)

        # Flexible mode radio button
        self.radio_flexible = QRadioButton("Flexible")
        self.radio_flexible.setToolTip(
            "Transform image style (cartoons, artistic styles).\n"
            "Single reference only. Uses Google Gemini."
        )
        self.mode_button_group.addButton(self.radio_flexible, 0)
        mode_layout.addWidget(self.radio_flexible)

        # Strict mode radio button
        self.radio_strict = QRadioButton("Strict")
        self.radio_strict.setToolTip(
            "Preserve subjects as-is, change scene/composition.\n"
            "Multi-reference support. Uses Imagen 3 Customization."
        )
        self.radio_strict.setChecked(True)  # Default to strict
        self.mode_button_group.addButton(self.radio_strict, 1)
        mode_layout.addWidget(self.radio_strict)

        mode_layout.addStretch()

        # Connect mode change signal
        self.mode_button_group.buttonClicked.connect(self._on_mode_changed)

        main_layout.addLayout(mode_layout)

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
        self.items_layout.setSpacing(20)  # Increased spacing to prevent widget overlap
        self.items_layout.addStretch()

        main_layout.addWidget(self.items_container)

    def _on_mode_changed(self):
        """Handle mode change between Flexible and Strict."""
        new_mode = "flexible" if self.radio_flexible.isChecked() else "strict"

        if new_mode == self.current_mode:
            return

        old_mode = self.current_mode
        self.current_mode = new_mode

        self.logger.info(f"Reference mode changed: {old_mode} -> {new_mode}")

        # If switching to Flexible mode and have more than 1 reference, remove extras
        if new_mode == "flexible" and len(self.reference_items) > 1:
            # Ask user if they want to keep first reference
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                "Mode Change",
                "Flexible mode only supports 1 reference image.\nKeep the first reference and remove the others?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                # Remove all but first
                while len(self.reference_items) > 1:
                    self._remove_reference(self.reference_items[-1])
            else:
                # Revert mode change
                self.radio_strict.setChecked(True)
                self.current_mode = old_mode
                return

        self._update_ui()
        self.mode_changed.emit(new_mode)

    def _add_reference(self):
        """Add a new reference image."""
        # Check max references based on mode
        max_allowed = 1 if self.current_mode == "flexible" else self.max_references

        if len(self.reference_items) >= max_allowed:
            mode_name = "Flexible" if self.current_mode == "flexible" else "Strict"
            QMessageBox.warning(
                self,
                "Maximum References",
                f"{mode_name} mode allows maximum {max_allowed} reference image(s)."
            )
            return

        # Open file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reference Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.gif *.webp);;All Files (*.*)",
            options=QFileDialog.Option.DontUseNativeDialog
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
        max_allowed = 1 if self.current_mode == "flexible" else self.max_references

        # Update count label with mode-aware max
        self.count_label.setText(f"Reference Images ({count}/{max_allowed})")
        self.btn_add.setEnabled(count < max_allowed)
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

    def get_mode(self) -> str:
        """
        Get the current reference mode.

        Returns:
            "flexible" or "strict"
        """
        return self.current_mode

    def is_flexible_mode(self) -> bool:
        """
        Check if currently in flexible mode.

        Returns:
            True if in flexible mode (style transfer)
        """
        return self.current_mode == "flexible"

    def is_strict_mode(self) -> bool:
        """
        Check if currently in strict mode.

        Returns:
            True if in strict mode (subject preservation)
        """
        return self.current_mode == "strict"

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

    def to_dict(self) -> dict:
        """
        Serialize all references and mode to a dictionary.

        Returns:
            Dictionary with mode and references
        """
        references = self.get_references()
        return {
            "mode": self.current_mode,
            "references": [ref.to_dict() for ref in references]
        }

    def from_dict(self, data):
        """
        Load references and mode from dictionary or list.

        Args:
            data: Dictionary with mode and references, or legacy list of reference dicts
        """
        # Clear existing references
        self.clear_all()

        if not data:
            return

        # Handle both new dict format and legacy list format
        if isinstance(data, dict):
            # New format with mode
            mode = data.get("mode", "strict")
            if mode == "flexible":
                self.radio_flexible.setChecked(True)
            else:
                self.radio_strict.setChecked(True)
            self.current_mode = mode

            ref_list = data.get("references", [])
        else:
            # Legacy list format - assume strict mode
            ref_list = data
            self.radio_strict.setChecked(True)
            self.current_mode = "strict"

        # Load each reference
        from core.reference.imagen_reference import ImagenReference
        for ref_dict in ref_list:
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
