"""
Reference Selector Dialog.
Allows user to select which reference images to use when more than 3 global references exist.
"""

import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QCheckBox, QGroupBox
)
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QPixmap

from core.video.project import ReferenceImage
from core.video.reference_manager import ReferenceImageType

logger = logging.getLogger(__name__)


class ReferenceCheckCard(QFrame):
    """Checkable reference card for selection"""

    def __init__(self, reference: ReferenceImage, parent=None):
        super().__init__(parent)
        self.reference = reference

        self.setFrameShape(QFrame.Box)
        self.setLineWidth(1)
        self.setMinimumSize(180, 240)
        self.setMaximumWidth(200)

        self.setup_ui()

    def setup_ui(self):
        """Setup card UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)

        # Checkbox header
        header_layout = QHBoxLayout()

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(True)  # Default to selected
        header_layout.addWidget(self.checkbox)

        # Type badge
        type_name = self.reference.ref_type.value if hasattr(self.reference.ref_type, 'value') else str(self.reference.ref_type)
        type_label = QLabel(type_name.upper())
        type_label.setStyleSheet(
            f"background: {self._get_type_color()}; color: white; "
            "padding: 2px 6px; border-radius: 3px; font-size: 9px; font-weight: bold;"
        )
        header_layout.addWidget(type_label)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Image preview
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setMinimumSize(160, 160)
        image_label.setStyleSheet("background: #f5f5f5; border: 1px solid #ddd;")

        # Load image
        if self.reference.path.exists():
            pixmap = QPixmap(str(self.reference.path))
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                image_label.setPixmap(scaled_pixmap)
            else:
                image_label.setText("(Failed to load)")
        else:
            image_label.setText("(File not found)")
            image_label.setStyleSheet("background: #ffe0e0; color: red; border: 1px solid #ff8888;")

        layout.addWidget(image_label)

        # Name
        name = self.reference.name or self.reference.path.stem
        name_label = QLabel(name)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        name_label.setWordWrap(True)
        layout.addWidget(name_label)

        # Description
        if self.reference.description:
            desc_label = QLabel(self.reference.description)
            desc_label.setAlignment(Qt.AlignCenter)
            desc_label.setStyleSheet("color: gray; font-size: 9px; font-style: italic;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

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

    def is_checked(self) -> bool:
        """Return whether this reference is selected"""
        return self.checkbox.isChecked()


class ReferenceSelectorDialog(QDialog):
    """Dialog for selecting which references to use for video generation"""

    def __init__(self, available_refs: List[ReferenceImage], max_selection: int = 3, parent=None):
        super().__init__(parent)
        self.available_refs = available_refs
        self.max_selection = max_selection
        self.reference_cards: List[ReferenceCheckCard] = []
        self.selected_references: List[ReferenceImage] = []
        self.settings = QSettings("ImageAI", "ReferenceSelectorDialog")

        self.setWindowTitle("Select Reference Images")
        self.setMinimumSize(700, 600)

        self.setup_ui()
        self.restore_window_geometry()
        self.restore_selected_references()

    def setup_ui(self):
        """Setup dialog UI"""
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("Select Reference Images for Video Generation")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        # Info label
        info_text = (
            f"You have {len(self.available_refs)} global references available, but Veo 3 can only use "
            f"up to {self.max_selection} references per video generation.\n"
            f"Please select which references to use:"
        )
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(info_label)

        # Selection count
        self.count_label = QLabel()
        self.count_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(self.count_label)

        # Scroll area with reference cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(400)

        scroll_widget = QWidget()
        scroll_layout = QHBoxLayout(scroll_widget)
        scroll_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        # Group by type
        refs_by_type = {}
        for ref in self.available_refs:
            ref_type = ref.ref_type
            if ref_type not in refs_by_type:
                refs_by_type[ref_type] = []
            refs_by_type[ref_type].append(ref)

        # Create type groups
        for ref_type, refs in refs_by_type.items():
            type_group = QGroupBox(ref_type.value.upper() if hasattr(ref_type, 'value') else str(ref_type).upper())
            type_layout = QHBoxLayout(type_group)
            type_layout.setAlignment(Qt.AlignLeft)

            for ref in refs:
                card = ReferenceCheckCard(ref)
                card.checkbox.stateChanged.connect(self.update_selection_count)
                self.reference_cards.append(card)
                type_layout.addWidget(card)

            scroll_layout.addWidget(type_group)

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Quick selection buttons
        quick_layout = QHBoxLayout()

        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all)
        quick_layout.addWidget(select_all_btn)

        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self.select_none)
        quick_layout.addWidget(select_none_btn)

        select_first_n_btn = QPushButton(f"Select First {self.max_selection}")
        select_first_n_btn.clicked.connect(self.select_first_n)
        quick_layout.addWidget(select_first_n_btn)

        quick_layout.addStretch()
        layout.addLayout(quick_layout)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.ok_btn = QPushButton("Use Selected References")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_btn)

        layout.addLayout(button_layout)

        # Update initial count
        self.update_selection_count()

    def update_selection_count(self):
        """Update the selection count label"""
        selected_count = sum(1 for card in self.reference_cards if card.is_checked())

        if selected_count > self.max_selection:
            self.count_label.setText(
                f"⚠ {selected_count} selected (exceeds limit of {self.max_selection})"
            )
            self.count_label.setStyleSheet("color: orange; font-weight: bold; font-size: 12px;")
            self.ok_btn.setEnabled(False)
            self.ok_btn.setText("Use Selected References")
        elif selected_count == 0:
            self.count_label.setText("ℹ No references selected - will use text-to-video mode")
            self.count_label.setStyleSheet("color: #2196F3; font-weight: bold; font-size: 12px;")
            self.ok_btn.setEnabled(True)  # Allow generation with no references
            self.ok_btn.setText("Continue (Text-to-Video)")
        else:
            self.count_label.setText(f"✓ {selected_count} / {self.max_selection} references selected")
            self.count_label.setStyleSheet("color: green; font-weight: bold; font-size: 12px;")
            self.ok_btn.setEnabled(True)
            self.ok_btn.setText("Use Selected References")

    def select_all(self):
        """Select all references"""
        for card in self.reference_cards:
            card.checkbox.setChecked(True)

    def select_none(self):
        """Deselect all references"""
        for card in self.reference_cards:
            card.checkbox.setChecked(False)

    def select_first_n(self):
        """Select first N references"""
        for i, card in enumerate(self.reference_cards):
            card.checkbox.setChecked(i < self.max_selection)

    def get_selected_references(self) -> List[ReferenceImage]:
        """Return list of selected references"""
        return [card.reference for card in self.reference_cards if card.is_checked()]

    def accept(self):
        """Handle accept"""
        self.selected_references = self.get_selected_references()
        logger.info(f"User selected {len(self.selected_references)} references for video generation")
        self.save_window_geometry()
        self.save_selected_references()
        super().accept()

    def reject(self):
        """Handle reject"""
        self.save_window_geometry()
        super().reject()

    def restore_window_geometry(self):
        """Restore window size and position from settings"""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
            logger.debug("Restored window geometry from settings")

    def save_window_geometry(self):
        """Save window size and position to settings"""
        self.settings.setValue("geometry", self.saveGeometry())
        logger.debug("Saved window geometry to settings")

    def restore_selected_references(self):
        """Restore previously selected references from settings"""
        saved_paths = self.settings.value("selected_paths", [])
        if not saved_paths:
            return

        # Convert saved paths to Path objects
        saved_path_set = {Path(p) for p in saved_paths if p}

        # Check each card and restore selection state
        restored_count = 0
        for card in self.reference_cards:
            if card.reference.path in saved_path_set:
                card.checkbox.setChecked(True)
                restored_count += 1
            else:
                card.checkbox.setChecked(False)

        if restored_count > 0:
            logger.info(f"Restored selection for {restored_count} reference(s) from settings")
        else:
            # If no selections were restored, default to selecting first N
            self.select_first_n()

    def save_selected_references(self):
        """Save selected references to settings for next time"""
        selected_paths = [str(card.reference.path) for card in self.reference_cards if card.is_checked()]
        self.settings.setValue("selected_paths", selected_paths)
        logger.debug(f"Saved {len(selected_paths)} selected reference path(s) to settings")
