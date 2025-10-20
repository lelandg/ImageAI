"""
Reference Library Management Widget.
Displays and manages global reference images for video projects.
"""

import logging
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QFrame, QScrollArea, QComboBox,
    QLineEdit, QFileDialog, QMenu, QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QAction

from core.video.project import ReferenceImage, VideoProject
from core.video.reference_manager import ReferenceImageType, ReferenceImageValidator

logger = logging.getLogger(__name__)


class ReferenceCard(QFrame):
    """Card widget displaying a single reference image"""

    remove_clicked = Signal(object)  # ReferenceImage
    edit_clicked = Signal(object)  # ReferenceImage

    def __init__(self, reference: ReferenceImage, parent=None):
        super().__init__(parent)
        self.reference = reference

        self.setFrameShape(QFrame.Box)
        self.setLineWidth(2)
        self.setMinimumSize(200, 280)
        self.setMaximumWidth(250)

        self.setup_ui()
        self.update_validation_border()

    def setup_ui(self):
        """Setup card UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)

        # Type and name header
        header_layout = QHBoxLayout()

        # Type badge
        type_name = self.reference.ref_type.value if hasattr(self.reference.ref_type, 'value') else str(self.reference.ref_type)
        self.type_label = QLabel(type_name.upper())
        self.type_label.setStyleSheet(
            f"background: {self._get_type_color()}; color: white; "
            "padding: 2px 8px; border-radius: 3px; font-size: 10px; font-weight: bold;"
        )
        header_layout.addWidget(self.type_label)

        # Global checkbox
        self.global_checkbox = QCheckBox("Global")
        self.global_checkbox.setChecked(self.reference.is_global)
        self.global_checkbox.setStyleSheet("font-size: 10px;")
        self.global_checkbox.setToolTip("Use this reference in all video generations")
        self.global_checkbox.stateChanged.connect(self._on_global_changed)
        header_layout.addWidget(self.global_checkbox)

        header_layout.addStretch()

        # Remove button
        remove_btn = QPushButton("✕")
        remove_btn.setMaximumSize(24, 24)
        remove_btn.setStyleSheet("background: #ff4444; color: white; border-radius: 12px; font-weight: bold;")
        remove_btn.setToolTip("Remove reference")
        remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.reference))
        header_layout.addWidget(remove_btn)

        layout.addLayout(header_layout)

        # Image preview
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(180, 180)
        self.image_label.setStyleSheet("background: #f5f5f5; border: 1px solid #ddd;")

        # Load image
        if self.reference.path.exists():
            pixmap = QPixmap(str(self.reference.path))
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_label.setPixmap(scaled_pixmap)
            else:
                self.image_label.setText("(Failed to load)")
        else:
            self.image_label.setText("(File not found)")
            self.image_label.setStyleSheet("background: #ffe0e0; color: red; border: 1px solid #ff8888;")

        layout.addWidget(self.image_label)

        # Name
        name = self.reference.name or self.reference.path.stem
        self.name_label = QLabel(name)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        self.name_label.setWordWrap(True)
        layout.addWidget(self.name_label)

        # Description
        if self.reference.description:
            desc_label = QLabel(self.reference.description)
            desc_label.setAlignment(Qt.AlignCenter)
            desc_label.setStyleSheet("color: gray; font-size: 10px; font-style: italic;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        # Validation status
        self.validation_label = QLabel()
        self.validation_label.setAlignment(Qt.AlignCenter)
        self.validation_label.setStyleSheet("font-size: 10px;")
        layout.addWidget(self.validation_label)

        self.update_validation_status()

    def _on_global_changed(self, state):
        """Handle global checkbox state change"""
        self.reference.is_global = (state == Qt.CheckState.Checked.value)
        logger.info(f"Reference {self.reference.name or self.reference.path.stem} global flag set to: {self.reference.is_global}")

    def _get_type_color(self):
        """Get color for reference type badge"""
        type_colors = {
            "character": "#4CAF50",
            "object": "#2196F3",
            "environment": "#FF9800",
            "style": "#9C27B0"
        }
        type_val = self.reference.ref_type.value if hasattr(self.reference.ref_type, 'value') else str(self.reference.ref_type)
        return type_colors.get(type_val.lower(), "#666")

    def update_validation_status(self):
        """Update validation status display"""
        if not self.reference.path.exists():
            self.validation_label.setText("✗ File not found")
            self.validation_label.setStyleSheet("color: red; font-size: 10px; font-weight: bold;")
            return

        validator = ReferenceImageValidator()
        info = validator.validate_reference_image(self.reference.path)

        if info.is_valid:
            if info.validation_warnings:
                self.validation_label.setText(f"⚠ {len(info.validation_warnings)} warning(s)")
                self.validation_label.setStyleSheet("color: orange; font-size: 10px;")
                self.validation_label.setToolTip("\n".join(info.validation_warnings))
            else:
                self.validation_label.setText(f"✓ Valid ({info.width}×{info.height})")
                self.validation_label.setStyleSheet("color: green; font-size: 10px;")
                self.validation_label.setToolTip(f"{info.format}, {info.file_size_mb:.1f}MB")
        else:
            self.validation_label.setText(f"✗ {len(info.validation_errors)} error(s)")
            self.validation_label.setStyleSheet("color: red; font-size: 10px; font-weight: bold;")
            self.validation_label.setToolTip("\n".join(info.validation_errors))

    def update_validation_border(self):
        """Update border color based on validation"""
        if not self.reference.path.exists():
            self.setStyleSheet("QFrame { border: 2px solid #ff4444; }")
            return

        validator = ReferenceImageValidator()
        info = validator.validate_reference_image(self.reference.path)

        if info.is_valid:
            if info.validation_warnings:
                self.setStyleSheet("QFrame { border: 2px solid #ff9800; }")  # Orange for warnings
            else:
                self.setStyleSheet("QFrame { border: 2px solid #4CAF50; }")  # Green for valid
        else:
            self.setStyleSheet("QFrame { border: 2px solid #ff4444; }")  # Red for errors

    def contextMenuEvent(self, event):
        """Show context menu"""
        menu = QMenu(self)

        edit_action = QAction("Edit Info", self)
        edit_action.triggered.connect(lambda: self.edit_clicked.emit(self.reference))
        menu.addAction(edit_action)

        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(lambda: self.remove_clicked.emit(self.reference))
        menu.addAction(remove_action)

        menu.exec_(event.globalPos())


class ReferenceLibraryWidget(QWidget):
    """Widget for managing global reference images"""

    references_changed = Signal()  # Emitted when references are added/removed

    def __init__(self, parent=None, project: Optional[VideoProject] = None):
        super().__init__(parent)
        self.project = project
        self.reference_cards = []

        self.setup_ui()
        if self.project:
            self.refresh()

    def setup_ui(self):
        """Setup widget UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("📸 Reference Library")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        header_layout.addWidget(title)

        self.count_label = QLabel("(0 global / 0 total)")
        self.count_label.setStyleSheet("color: gray; font-size: 12px;")
        header_layout.addWidget(self.count_label)

        header_layout.addStretch()

        # Add buttons
        self.generate_btn = QPushButton("🎨 Generate Character Refs")
        self.generate_btn.setToolTip("Auto-generate 3 character reference images")
        self.generate_btn.clicked.connect(self.on_generate_clicked)
        header_layout.addWidget(self.generate_btn)

        self.add_existing_btn = QPushButton("📁 Add Existing Image")
        self.add_existing_btn.setToolTip("Add existing image as reference")
        self.add_existing_btn.clicked.connect(self.on_add_existing_clicked)
        header_layout.addWidget(self.add_existing_btn)

        layout.addLayout(header_layout)

        # Help text
        help_text = QLabel(
            "Reference images maintain character/object/environment consistency across all scenes. "
            "Maximum 3 global references."
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: gray; font-size: 11px; font-style: italic; padding: 5px;")
        layout.addWidget(help_text)

        # Scroll area for reference cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(300)

        scroll_widget = QWidget()
        self.cards_layout = QHBoxLayout(scroll_widget)
        self.cards_layout.setAlignment(Qt.AlignLeft)
        self.cards_layout.setSpacing(15)

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, stretch=1)

        # Empty state
        self.empty_label = QLabel(
            "No reference images yet.\n\n"
            "Click 'Generate Character Refs' to create 3 reference images automatically,\n"
            "or 'Add Existing Image' to use your own images."
        )
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: gray; font-style: italic; padding: 40px;")
        layout.addWidget(self.empty_label)

    def set_project(self, project: VideoProject):
        """Set the project"""
        self.project = project
        self.refresh()

    def refresh(self):
        """Refresh display from project"""
        # Clear existing cards
        for card in self.reference_cards:
            card.deleteLater()
        self.reference_cards.clear()

        if not self.project:
            self.empty_label.setVisible(True)
            self.count_label.setText("(No project)")
            return

        # Get references
        refs = self.project.global_reference_images

        # Update count
        global_count = sum(1 for ref in refs if ref.is_global)
        total_count = len(refs)
        self.count_label.setText(f"({global_count} global / {total_count} total)")

        # Always enable buttons (no max limit)
        self.count_label.setStyleSheet("color: gray; font-size: 12px;")
        self.add_existing_btn.setEnabled(True)
        self.add_existing_btn.setToolTip("Add existing image as reference")
        self.generate_btn.setEnabled(True)
        self.generate_btn.setToolTip("Auto-generate 3 character reference images")

        # Show/hide empty state
        self.empty_label.setVisible(len(refs) == 0)

        # Create cards
        for ref in refs:
            card = ReferenceCard(ref, self)
            card.remove_clicked.connect(self.on_remove_reference)
            card.edit_clicked.connect(self.on_edit_reference)
            self.cards_layout.addWidget(card)
            self.reference_cards.append(card)

    def on_generate_clicked(self):
        """Handle generate button clicked"""
        from gui.video.reference_generation_dialog import ReferenceGenerationDialog

        # Walk up the parent chain to find video_project_tab with generate_reference_image_sync
        parent_tab = self.parent()
        while parent_tab and not hasattr(parent_tab, 'generate_reference_image_sync'):
            parent_tab = parent_tab.parent()

        if not parent_tab:
            QMessageBox.warning(
                self,
                "Image Generator Not Available",
                "Could not find parent tab with image generation capability.\n\n"
                "This should not happen - please report this issue."
            )
            return

        # Create image generator wrapper
        def image_generator(prompt: str, output_dir: Path, filename_prefix: str) -> Optional[Path]:
            """Wrapper for image generation"""
            try:
                # Generate image using parent tab's method
                result_path = parent_tab.generate_reference_image_sync(prompt, output_dir, filename_prefix)
                return result_path
            except Exception as e:
                logger.error(f"Image generation failed: {e}", exc_info=True)
                return None

        # Open dialog
        dialog = ReferenceGenerationDialog(self, self.project, image_generator)
        dialog.references_generated.connect(self.on_references_generated)
        dialog.exec()

    def on_add_existing_clicked(self):
        """Handle add existing button clicked"""
        if not self.project:
            return

        # File dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reference Image",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg)"
        )

        if not file_path:
            return

        path = Path(file_path)

        # Validate
        validator = ReferenceImageValidator()
        info = validator.validate_reference_image(path)

        if not info.is_valid:
            errors = "\n".join(info.validation_errors)
            QMessageBox.critical(
                self,
                "Invalid Reference Image",
                f"The selected image does not meet Veo 3 requirements:\n\n{errors}"
            )
            return

        # Show warnings if any
        if info.validation_warnings:
            warnings = "\n".join(info.validation_warnings)
            result = QMessageBox.question(
                self,
                "Reference Image Warnings",
                f"The image has the following warnings:\n\n{warnings}\n\nAdd anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if result != QMessageBox.Yes:
                return

        # Ask for type and name
        from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle("Reference Image Details")
        dialog.setModal(True)

        dialog_layout = QVBoxLayout(dialog)

        form_layout = QFormLayout()

        # Type
        type_combo = QComboBox()
        type_combo.addItems(["CHARACTER", "OBJECT", "ENVIRONMENT", "STYLE"])
        form_layout.addRow("Type:", type_combo)

        # Name
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("e.g., Sarah, Vintage Car, Coffee Shop...")
        form_layout.addRow("Name:", name_edit)

        # Description
        desc_edit = QLineEdit()
        desc_edit.setPlaceholderText("Optional description...")
        form_layout.addRow("Description:", desc_edit)

        dialog_layout.addLayout(form_layout)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog_layout.addWidget(button_box)

        if dialog.exec() != QDialog.Accepted:
            return

        # Get values
        ref_type_str = type_combo.currentText().lower()
        ref_type = ReferenceImageType(ref_type_str)
        name = name_edit.text().strip() or path.stem
        description = desc_edit.text().strip()

        # Create reference
        ref_image = ReferenceImage(
            path=path,
            ref_type=ref_type,
            name=name,
            description=description or None,
            is_global=True  # Default to global
        )

        # Add to project
        if self.project.add_global_reference(ref_image):
            self.project.save()
            logger.info(f"Added reference to project: {path.name}")
            self.refresh()
            self.references_changed.emit()
        else:
            QMessageBox.warning(
                self,
                "Failed to Add Reference",
                "Could not add reference. Please check the error log."
            )

    def on_remove_reference(self, reference: ReferenceImage):
        """Handle remove reference"""
        result = QMessageBox.question(
            self,
            "Remove Reference",
            f"Remove reference '{reference.name or reference.path.name}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if result != QMessageBox.Yes:
            return

        if self.project and self.project.remove_global_reference(reference.path):
            self.project.save()
            logger.info(f"Removed reference: {reference.path.name}")
            self.refresh()
            self.references_changed.emit()

    def on_edit_reference(self, reference: ReferenceImage):
        """Handle edit reference"""
        from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Reference Details")
        dialog.setModal(True)

        dialog_layout = QVBoxLayout(dialog)

        form_layout = QFormLayout()

        # Type
        type_combo = QComboBox()
        type_combo.addItems(["CHARACTER", "OBJECT", "ENVIRONMENT", "STYLE"])
        current_type = reference.ref_type.value if hasattr(reference.ref_type, 'value') else str(reference.ref_type)
        type_combo.setCurrentText(current_type.upper())
        form_layout.addRow("Type:", type_combo)

        # Name
        name_edit = QLineEdit()
        name_edit.setText(reference.name or "")
        form_layout.addRow("Name:", name_edit)

        # Description
        desc_edit = QLineEdit()
        desc_edit.setText(reference.description or "")
        form_layout.addRow("Description:", desc_edit)

        dialog_layout.addLayout(form_layout)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog_layout.addWidget(button_box)

        if dialog.exec() != QDialog.Accepted:
            return

        # Update reference
        ref_type_str = type_combo.currentText().lower()
        reference.ref_type = ReferenceImageType(ref_type_str)
        reference.name = name_edit.text().strip() or None
        reference.description = desc_edit.text().strip() or None

        # Save project
        if self.project:
            self.project.save()
            logger.info(f"Updated reference: {reference.path.name}")
            self.refresh()
            self.references_changed.emit()

    def on_references_generated(self, paths: List[Path]):
        """Handle references generated from wizard"""
        logger.info(f"References generated: {len(paths)} images")
        self.refresh()
        self.references_changed.emit()
