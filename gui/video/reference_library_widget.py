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


class ExtractedFrameCard(QFrame):
    """Compact card widget for extracted video frames (first/last frames)"""

    add_as_reference_clicked = Signal(Path, str)  # Path, frame_type ("start" or "end")

    def __init__(self, frame_path: Path, frame_type: str, scene_source: str, parent=None):
        super().__init__(parent)
        self.frame_path = frame_path
        self.frame_type = frame_type  # "start" or "end"
        self.scene_source = scene_source

        self.setFrameShape(QFrame.Box)
        self.setLineWidth(1)
        self.setFixedSize(160, 200)  # Compact fixed size

        self.setup_ui()

    def setup_ui(self):
        """Setup compact card UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(3, 3, 3, 3)

        # Image preview (most of the space)
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setFixedSize(154, 154)
        image_label.setStyleSheet("background: #f5f5f5; border: 1px solid #ddd;")

        if self.frame_path.exists():
            pixmap = QPixmap(str(self.frame_path))
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(152, 152, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                image_label.setPixmap(scaled_pixmap)
            else:
                image_label.setText("Error")
        else:
            image_label.setText("Missing")

        layout.addWidget(image_label)

        # Compact footer with badge and button
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(2)
        footer_layout.setContentsMargins(0, 0, 0, 0)

        # Frame type badge (tiny)
        color = "#4CAF50" if self.frame_type == "start" else "#2196F3"
        type_badge = QLabel(self.frame_type[0].upper())  # Just "S" or "E"
        type_badge.setStyleSheet(
            f"background: {color}; color: white; "
            "padding: 1px 3px; border-radius: 2px; font-size: 8px; font-weight: bold;"
        )
        type_badge.setFixedWidth(12)
        type_badge.setToolTip(f"{self.frame_type.title()} frame")
        footer_layout.addWidget(type_badge)

        # Add button (compact)
        add_btn = QPushButton("+Ref")
        add_btn.setStyleSheet("font-size: 8px; padding: 1px 3px;")
        add_btn.setToolTip(f"Add as reference\n{self.scene_source[:40]}...")
        add_btn.clicked.connect(lambda: self.add_as_reference_clicked.emit(self.frame_path, self.frame_type))
        footer_layout.addWidget(add_btn)

        layout.addLayout(footer_layout)


class ReferenceLibraryWidget(QWidget):
    """Widget for managing global reference images"""

    references_changed = Signal()  # Emitted when references are added/removed
    frame_selected = Signal(Path)  # Emitted when an extracted frame is selected to add as reference

    def __init__(self, parent=None, project: Optional[VideoProject] = None):
        super().__init__(parent)
        self.project = project
        self.reference_cards = []
        self.extracted_frame_cards = []

        self.setup_ui()
        if self.project:
            self.refresh()

    def setup_ui(self):
        """Setup widget UI"""
        from PySide6.QtWidgets import QTabWidget

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create tab widget for different library sections
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Tab 1: Reference Images
        self._setup_references_tab()

        # Tab 2: Extracted Frames
        self._setup_extracted_frames_tab()

    def _setup_references_tab(self):
        """Setup the reference images tab"""
        ref_tab = QWidget()
        layout = QVBoxLayout(ref_tab)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("📸 Reference Images")
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
            "Reference images maintain character/object/environment consistency across all scenes.\n"
            "Multiple references can be auto-composited into character design sheets for models with limits."
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

        self.tab_widget.addTab(ref_tab, "References")

    def _setup_extracted_frames_tab(self):
        """Setup the extracted frames tab with compact grid layout"""
        from PySide6.QtWidgets import QGridLayout

        frames_tab = QWidget()
        layout = QVBoxLayout(frames_tab)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("🎞️ Extracted Frames")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        header_layout.addWidget(title)

        self.frames_count_label = QLabel("(0 frames)")
        self.frames_count_label.setStyleSheet("color: gray; font-size: 12px;")
        header_layout.addWidget(self.frames_count_label)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Help text (compact)
        help_text = QLabel("Extracted frames from generated videos. Hover over +Ref to see scene text.")
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: gray; font-size: 9px; font-style: italic; padding: 2px;")
        layout.addWidget(help_text)

        # Scroll area for frame cards in grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(300)

        scroll_widget = QWidget()
        self.frames_layout = QGridLayout(scroll_widget)
        self.frames_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.frames_layout.setSpacing(5)  # Compact spacing
        self.frames_layout.setContentsMargins(5, 5, 5, 5)

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, stretch=1)

        # Empty state
        self.frames_empty_label = QLabel(
            "No extracted frames yet.\n\n"
            "Generate videos in the workspace to extract start/end frames."
        )
        self.frames_empty_label.setAlignment(Qt.AlignCenter)
        self.frames_empty_label.setStyleSheet("color: gray; font-style: italic; padding: 40px;")
        layout.addWidget(self.frames_empty_label)

        self.tab_widget.addTab(frames_tab, "Extracted Frames")

    def set_project(self, project: VideoProject):
        """Set the project"""
        self.project = project
        self.refresh()

    def refresh(self):
        """Refresh display from project"""
        # Clear existing reference cards
        for card in self.reference_cards:
            card.deleteLater()
        self.reference_cards.clear()

        # Clear existing frame cards
        for card in self.extracted_frame_cards:
            card.deleteLater()
        self.extracted_frame_cards.clear()

        if not self.project:
            self.empty_label.setVisible(True)
            self.frames_empty_label.setVisible(True)
            self.count_label.setText("(No project)")
            self.frames_count_label.setText("(No project)")
            return

        # Refresh reference images tab
        self._refresh_references()

        # Refresh extracted frames tab
        self._refresh_extracted_frames()

    def _refresh_references(self):
        """Refresh the reference images tab"""
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

    def _refresh_extracted_frames(self):
        """Refresh the extracted frames tab with grid layout"""
        from core.video.project import Scene

        frames = []

        # Scan all scenes in the project for extracted frames
        if self.project and hasattr(self.project, 'scenes'):
            for scene in self.project.scenes:
                # Add first frame (start frame) if exists
                if scene.first_frame and scene.first_frame.exists():
                    frames.append((scene.first_frame, "start", scene.source, scene))

                # Add last frame (end frame) if exists
                if scene.last_frame and scene.last_frame.exists():
                    frames.append((scene.last_frame, "end", scene.source, scene))

        # Update count
        self.frames_count_label.setText(f"({len(frames)} frames)")

        # Show/hide empty state
        self.frames_empty_label.setVisible(len(frames) == 0)

        # Create cards in grid layout (auto-wrapping)
        # Calculate columns based on available width (160px per card + 5px spacing)
        cols_per_row = 6  # Default, will auto-wrap anyway

        for i, (frame_path, frame_type, scene_source, scene) in enumerate(frames):
            card = ExtractedFrameCard(frame_path, frame_type, scene_source, self)
            card.add_as_reference_clicked.connect(self.on_frame_selected)

            row = i // cols_per_row
            col = i % cols_per_row
            self.frames_layout.addWidget(card, row, col)
            self.extracted_frame_cards.append(card)

        logger.info(f"Refreshed extracted frames tab: {len(frames)} frames found in grid layout")

    def on_generate_clicked(self):
        """Handle generate button clicked"""
        from gui.video.reference_generation_dialog import ReferenceGenerationDialog

        # Walk up the parent chain to find video_project_tab with config and providers
        parent_tab = self.parent()
        while parent_tab and not hasattr(parent_tab, 'config'):
            parent_tab = parent_tab.parent()

        if not parent_tab or not hasattr(parent_tab, 'providers'):
            QMessageBox.warning(
                self,
                "Configuration Not Available",
                "Could not find parent tab with configuration.\n\n"
                "This should not happen - please report this issue."
            )
            return

        # Open dialog with config and providers
        dialog = ReferenceGenerationDialog(
            parent=self,
            project=self.project,
            config=parent_tab.config,
            providers=parent_tab.providers
        )
        dialog.references_generated.connect(self.on_references_generated)
        dialog.exec()

    def on_add_existing_clicked(self):
        """Handle add existing button clicked"""
        logger.info("=== ADD EXISTING IMAGE CLICKED ===")

        if not self.project:
            logger.warning("No project loaded - cannot add reference image")
            QMessageBox.warning(self, "No Project", "Please create or load a project first.")
            return

        logger.info("Opening file dialog...")

        try:
            # File dialog
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Reference Image",
                str(Path.home()),
                "Images (*.png *.jpg *.jpeg)"
            )

            logger.info(f"File dialog returned: {file_path}")

        except Exception as e:
            logger.error(f"File dialog exception: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"File dialog failed: {e}")
            return

        if not file_path:
            logger.info("No file selected (user cancelled)")
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

    def on_frame_selected(self, frame_path: Path, frame_type: str):
        """Handle extracted frame selected to add as reference"""
        from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox

        # Ask for reference details
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Add {frame_type.title()} Frame as Reference")
        dialog.setModal(True)

        dialog_layout = QVBoxLayout(dialog)

        # Show frame preview
        preview_label = QLabel()
        preview_label.setAlignment(Qt.AlignCenter)
        if frame_path.exists():
            pixmap = QPixmap(str(frame_path))
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                preview_label.setPixmap(scaled_pixmap)
        dialog_layout.addWidget(preview_label)

        form_layout = QFormLayout()

        # Type
        type_combo = QComboBox()
        type_combo.addItems(["CHARACTER", "OBJECT", "ENVIRONMENT", "STYLE"])
        form_layout.addRow("Type:", type_combo)

        # Name
        name_edit = QLineEdit()
        name_edit.setPlaceholderText(f"e.g., Character from scene...")
        name_edit.setText(f"Extracted {frame_type} frame")
        form_layout.addRow("Name:", name_edit)

        # Description
        desc_edit = QLineEdit()
        desc_edit.setPlaceholderText("Optional description...")
        desc_edit.setText(f"{frame_type.title()} frame from generated video")
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
        name = name_edit.text().strip() or frame_path.stem
        description = desc_edit.text().strip()

        # Create reference
        ref_image = ReferenceImage(
            path=frame_path,
            ref_type=ref_type,
            name=name,
            description=description or None,
            is_global=True  # Default to global
        )

        # Add to project
        if self.project.add_global_reference(ref_image):
            self.project.save()
            logger.info(f"Added extracted frame as reference: {frame_path.name}")
            self.refresh()
            self.references_changed.emit()
            QMessageBox.information(
                self,
                "Frame Added",
                f"Successfully added {frame_type} frame as a reference image!"
            )
        else:
            QMessageBox.warning(
                self,
                "Failed to Add Reference",
                "Could not add reference. Please check the error log."
            )

