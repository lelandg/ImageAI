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
    QSizePolicy, QMessageBox, QRadioButton, QButtonGroup, QDialog, QLayout, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QRect, QSize, QPoint
from PySide6.QtGui import QPixmap

from core.reference.imagen_reference import (
    ImagenReference, ImagenReferenceType, ImagenSubjectType,
    validate_references
)

logger = logging.getLogger(__name__)


class FlowLayout(QLayout):
    """
    A layout that arranges widgets in a flowing manner, wrapping to new rows as needed.
    Widgets flow left-to-right, top-to-bottom, wrapping when they reach the edge.
    """

    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._item_list = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._item_list.append(item)

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self._do_layout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        margin, _, _, _ = self.getContentsMargins()
        size += QSize(2 * margin, 2 * margin)
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0

        for item in self._item_list:
            wid = item.widget()
            space_x = self.spacing()
            space_y = self.spacing()
            next_x = x + item.sizeHint().width() + space_x

            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y()


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
        self.type_label = QLabel("Type:")
        type_layout.addWidget(self.type_label)
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

    def set_combos_visible(self, visible: bool):
        """
        Show or hide the type and subject combo boxes.

        Used when switching between flexible and strict modes.
        In flexible mode, combo boxes are hidden since the mode is style transfer.

        Args:
            visible: True to show combos, False to hide
        """
        # Hide/show type combo and label
        self.type_combo.setVisible(visible)
        self.type_label.setVisible(visible)

        # Hide/show subject combo and label
        self.subject_type_combo.setVisible(visible)
        self.subject_label.setVisible(visible)

        # Hide/show control combo and label
        self.control_type_combo.setVisible(visible)
        self.control_label.setVisible(visible)


class ImagenReferenceWidget(QWidget):
    """
    Main widget for managing Imagen 3 reference images.

    Allows adding up to 4 reference images with types and descriptions.
    Provides signals for when references change.

    Supports two modes:
    - Flexible: Single reference, style transformation (Google Gemini)
    - Strict: Multi-reference, subject preservation (Imagen 3 Customization)
    """

    # Model-specific reference image limits
    MODEL_REF_LIMITS = {
        'gemini-2.5-flash-image': 5,       # Standard Nano Banana
        'gemini-3-pro-image-preview': 14,  # Nano Banana Pro - up to 14 reference images
        'default': 3                        # Default for other models
    }

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
        self.current_model = None
        self.max_references_strict = self.MODEL_REF_LIMITS['default']  # Dynamic based on model
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
            "Multiple references supported (auto-composited). Uses Google Gemini."
        )
        self.mode_button_group.addButton(self.radio_flexible, 0)
        mode_layout.addWidget(self.radio_flexible)

        # Strict mode radio button
        self.radio_strict = QRadioButton("Strict")
        self.radio_strict.setToolTip(
            "Preserve subjects as-is, change scene/composition.\n"
            "Up to 3 references. Uses Imagen 3 Customization."
        )
        self.radio_strict.setChecked(True)  # Default to strict
        self.mode_button_group.addButton(self.radio_strict, 1)
        mode_layout.addWidget(self.radio_strict)

        mode_layout.addStretch()

        # Connect mode change signal
        self.mode_button_group.buttonClicked.connect(self._on_mode_changed)

        main_layout.addLayout(mode_layout)

        # Help text for multiple references in flexible mode
        self.multi_ref_help = QLabel()
        self.multi_ref_help.setWordWrap(True)
        self.multi_ref_help.setStyleSheet(
            "background-color: #fff3cd; color: #856404; "
            "border: 1px solid #ffc107; border-radius: 4px; "
            "padding: 8px; font-size: 10pt;"
        )
        self.multi_ref_help.setText(
            "Multiple references: Images are sent directly to the model for free prompting. "
            "Enable 'Composite Images' to combine them into a single grid instead."
        )
        self.multi_ref_help.setVisible(False)  # Hidden by default
        main_layout.addWidget(self.multi_ref_help)

        # Header with count and add button
        header_layout = QHBoxLayout()

        self.count_label = QLabel("Reference Images (0/3)")
        self.count_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        header_layout.addWidget(self.count_label)

        header_layout.addStretch()

        # Edit Mode checkbox
        self.chk_edit_mode = QCheckBox("Edit Mode")
        self.chk_edit_mode.setToolTip(
            "When enabled with a single reference image, auto-prefix the prompt with:\n"
            "\"Edit this image. Keep everything already in the image exactly the same.\""
        )
        self.chk_edit_mode.stateChanged.connect(self._on_edit_mode_changed)
        header_layout.addWidget(self.chk_edit_mode)

        # Composite Mode checkbox (for multiple references in flexible mode)
        self.chk_composite_mode = QCheckBox("Composite Images")
        self.chk_composite_mode.setToolTip(
            "When enabled, multiple reference images are composited into a single grid.\n"
            "When disabled, images are sent directly to the model (recommended for Gemini 3 Pro)."
        )
        self.chk_composite_mode.setChecked(False)  # Default OFF - send images directly
        self.chk_composite_mode.setVisible(False)  # Only show when multiple refs in flexible mode
        header_layout.addWidget(self.chk_composite_mode)

        self.btn_add = QPushButton("+ Add Reference Image")
        self.btn_add.setToolTip("Add a reference image")
        self.btn_add.clicked.connect(self._add_reference)
        header_layout.addWidget(self.btn_add)

        main_layout.addLayout(header_layout)

        # Scrollable container for reference items with flow layout (wraps automatically)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.items_container = QWidget()
        self.items_layout = FlowLayout(self.items_container, margin=0, spacing=20)

        scroll_area.setWidget(self.items_container)
        main_layout.addWidget(scroll_area)

    def _on_mode_changed(self):
        """Handle mode change between Flexible and Strict."""
        new_mode = "flexible" if self.radio_flexible.isChecked() else "strict"

        if new_mode == self.current_mode:
            return

        old_mode = self.current_mode
        self.current_mode = new_mode

        self.logger.info(f"Reference mode changed: {old_mode} -> {new_mode}")

        # If switching to Strict mode and have more than 3 references, show selection dialog
        if new_mode == "strict" and len(self.reference_items) > self.max_references_strict:
            # Show selection dialog to choose which 3 to keep
            from gui.reference_selection_dialog import ReferenceSelectionDialog

            image_paths = [item.reference_path for item in self.reference_items if item.reference_path]

            dialog = ReferenceSelectionDialog(
                image_paths=image_paths,
                max_selection=self.max_references_strict,
                title="Select References for Strict Mode",
                message=f"Strict mode allows maximum {self.max_references_strict} reference images.\n"
                        f"Please select {self.max_references_strict} images to keep:",
                parent=self
            )

            if dialog.exec() != QDialog.Accepted:
                # User cancelled - revert mode change
                self.radio_flexible.setChecked(True)
                self.current_mode = old_mode
                return

            # Get selected paths
            selected_paths = dialog.get_selected_paths()

            # Remove items not in selection
            items_to_remove = [
                item for item in self.reference_items
                if item.reference_path not in selected_paths
            ]

            for item in items_to_remove:
                self._remove_reference(item)

        self._update_ui()
        self.mode_changed.emit(new_mode)

    def _add_reference(self):
        """Add one or more reference images."""
        # Check max references based on mode (only for strict mode)
        if self.current_mode == "strict":
            max_allowed = self.max_references_strict
            if len(self.reference_items) >= max_allowed:
                QMessageBox.warning(
                    self,
                    "Maximum References",
                    f"Strict mode allows maximum {max_allowed} reference images."
                )
                return

        # Open file dialog for multiple selection
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Reference Image(s)",
            "",
            "Image Files (*.png *.jpg *.jpeg *.gif *.webp);;All Files (*.*)"
        )

        if not file_paths:
            return

        # Check if adding these would exceed strict mode limit
        if self.current_mode == "strict":
            total_after = len(self.reference_items) + len(file_paths)
            if total_after > self.max_references_strict:
                QMessageBox.warning(
                    self,
                    "Too Many References",
                    f"Strict mode allows maximum {self.max_references_strict} reference images.\n"
                    f"You selected {len(file_paths)} images, but only {self.max_references_strict - len(self.reference_items)} can be added."
                )
                return

        # Add each selected file
        for file_path in file_paths:
            reference_id = len(self.reference_items) + 1
            item_widget = ImagenReferenceItemWidget(reference_id, parent=self)
            item_widget.set_reference_image(Path(file_path))
            item_widget.reference_changed.connect(self._on_reference_changed)
            item_widget.remove_requested.connect(lambda w=item_widget: self._remove_reference(w))

            # Add to flow layout
            self.items_layout.addWidget(item_widget)
            self.reference_items.append(item_widget)

        self._update_ui()
        self.logger.info(f"Added {len(file_paths)} reference image(s)")

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
        self._update_ui()
        self.references_changed.emit()

    def _on_edit_mode_changed(self):
        """Handle when edit mode checkbox changes."""
        # Just emit signal - MainWindow will handle the logic
        self.references_changed.emit()

    def _update_ui(self):
        """Update UI elements based on current state."""
        count = len(self.reference_items)

        # Update count label and button based on mode
        if self.current_mode == "flexible":
            # Flexible mode: unlimited images
            self.count_label.setText(f"Reference Images ({count})")
            self.btn_add.setEnabled(True)

            # Show help text only for gemini-2.5-flash (older model needs guidance)
            # NBP (gemini-3) supports multi-reference natively, no help needed
            is_legacy_model = bool(self.current_model and 'gemini-2.5-flash' in self.current_model)
            self.multi_ref_help.setVisible(count > 1 and is_legacy_model)

            # Show composite mode checkbox only when >1 reference in flexible mode
            self.chk_composite_mode.setVisible(count > 1)

            # Hide combo boxes in flexible mode (style transfer doesn't need type/subject)
            for item in self.reference_items:
                item.set_combos_visible(False)
        else:
            # Strict mode: max 3 images
            max_allowed = self.max_references_strict
            self.count_label.setText(f"Reference Images ({count}/{max_allowed})")
            self.btn_add.setEnabled(count < max_allowed)

            # Hide help text and composite mode in strict mode
            self.multi_ref_help.setVisible(False)
            self.chk_composite_mode.setVisible(False)

            # Show combo boxes in strict mode (need to specify type/subject)
            for item in self.reference_items:
                item.set_combos_visible(True)

        # Update edit mode checkbox state
        # Edit mode only applicable when exactly 1 reference image
        self.chk_edit_mode.setEnabled(count == 1)
        if count != 1:
            # Auto-disable if not exactly 1 reference
            self.chk_edit_mode.setChecked(False)

        self.references_changed.emit()

    def update_model(self, model_id: str):
        """
        Update reference image limit based on the selected model.

        Args:
            model_id: The model identifier (e.g., 'gemini-3-pro-image-preview')
        """
        self.current_model = model_id

        # Get model-specific limit
        new_limit = self.MODEL_REF_LIMITS.get(model_id, self.MODEL_REF_LIMITS['default'])
        old_limit = self.max_references_strict

        if new_limit != old_limit:
            self.max_references_strict = new_limit
            self.logger.info(f"Reference image limit updated: {old_limit} -> {new_limit} for model {model_id}")

            # Update tooltip to reflect new limit
            is_nbp = "gemini-3" in model_id if model_id else False
            if is_nbp:
                self.radio_strict.setToolTip(
                    f"Preserve subjects as-is, change scene/composition.\n"
                    f"Up to {new_limit} references (Nano Banana Pro). Uses Imagen 3 Customization."
                )
            else:
                self.radio_strict.setToolTip(
                    f"Preserve subjects as-is, change scene/composition.\n"
                    f"Up to {new_limit} references. Uses Imagen 3 Customization."
                )

            # Update the UI to reflect new limits
            self._update_ui()

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

    def needs_compositing(self) -> bool:
        """
        Check if images need to be composited before generation.

        Returns:
            True if in flexible mode with multiple images
        """
        return self.is_flexible_mode() and len(self.reference_items) > 1

    def is_edit_mode_active(self) -> bool:
        """
        Check if edit mode is active.

        Edit mode is active when:
        - The checkbox is enabled AND checked
        - There is exactly one reference image

        Returns:
            True if edit mode is active
        """
        return (self.chk_edit_mode.isEnabled() and
                self.chk_edit_mode.isChecked() and
                len(self.reference_items) == 1)

    def is_composite_mode(self) -> bool:
        """
        Check if composite mode is active for multiple reference images.

        Composite mode combines multiple images into a single grid.
        When disabled, images are sent directly to the model.

        Returns:
            True if images should be composited into a grid
        """
        return (self.chk_composite_mode.isVisible() and
                self.chk_composite_mode.isChecked())

    def get_edit_mode_prefix(self) -> str:
        """
        Get the edit mode prompt prefix.

        Returns:
            The prefix string to add to prompts in edit mode
        """
        return "Edit this image. Keep everything already in the image exactly the same.\n"

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

                # Add to flow layout
                self.items_layout.addWidget(item_widget)
                self.reference_items.append(item_widget)

            except Exception as e:
                self.logger.error(f"Failed to load reference from dict: {e}")

        self._update_ui()
        self.logger.info(f"Loaded {len(self.reference_items)} reference images from dict")
