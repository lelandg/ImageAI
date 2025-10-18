"""
Reference Images Widget for Veo 3 visual continuity.

This widget manages up to 3 reference images for style/character/environment consistency.
Each reference image can be generated, loaded, or auto-linked from previous scenes.
"""

from pathlib import Path
from typing import List, Optional
import logging

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Signal

from gui.video.frame_button import FrameButton


class ReferenceImagesWidget(QWidget):
    """
    Widget for managing up to 3 reference images for a scene.

    Each reference slot can:
    - Generate a new reference image
    - Load an existing image
    - Auto-link from previous scene's last frame
    - Clear the reference

    Signals:
        reference_changed: Emitted when any reference image changes
    """

    # Signals
    reference_changed = Signal(int, object)  # (slot_index, path or None)
    generate_requested = Signal(int)  # (slot_index)
    select_requested = Signal(int)  # (slot_index) - select from variants
    select_from_scene_requested = Signal(int)  # (slot_index) - select from any scene
    view_requested = Signal(int)  # (slot_index)
    load_requested = Signal(int)  # (slot_index)

    def __init__(self, max_references: int = 3, parent=None):
        """
        Initialize reference images widget.

        Args:
            max_references: Maximum number of reference images (default 3 for Veo 3)
            parent: Parent widget
        """
        super().__init__(parent)
        self.max_references = max_references
        self.logger = logging.getLogger(__name__)
        self.reference_buttons: List[FrameButton] = []

        # Set minimum width to show all buttons with minimal spacing
        # 3 buttons * 50px (min width) + 2 * 2px (spacing) + 4px (margins) = 158px
        self.setMinimumWidth(158)

        # Create layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)  # Reduced from 5 to 2 for minimal spacing

        # Create reference image slots
        for i in range(max_references):
            # Create frame button for this reference
            ref_button = FrameButton(frame_type=f"ref{i+1}", parent=self)
            ref_button.setToolTip(
                f"Reference Image {i+1}\n"
                f"Optional style/character/environment reference\n"
                f"Click to generate/select, right-click for options"
            )

            # Connect signals
            ref_button.generate_requested.connect(lambda idx=i: self._on_generate_requested(idx))
            ref_button.select_requested.connect(lambda idx=i: self._on_select_requested(idx))
            ref_button.select_from_scene_requested.connect(lambda idx=i: self._on_select_from_scene_requested(idx))
            ref_button.clear_requested.connect(lambda idx=i: self._on_clear_requested(idx))
            ref_button.view_requested.connect(lambda idx=i: self._on_view_requested(idx))
            ref_button.load_image_requested.connect(lambda idx=i: self._on_load_requested(idx))

            self.reference_buttons.append(ref_button)
            layout.addWidget(ref_button)

        # Add stretch to keep buttons compact
        layout.addStretch()

    def set_reference_image(self, index: int, path: Optional[Path], auto_linked: bool = False):
        """
        Set a reference image at the specified index.

        Args:
            index: Reference slot index (0-2)
            path: Path to reference image, or None to clear
            auto_linked: True if auto-linked from previous scene
        """
        if 0 <= index < self.max_references:
            self.reference_buttons[index].set_frame(path, auto_linked)
            self.reference_changed.emit(index, path)

    def get_reference_image(self, index: int) -> Optional[Path]:
        """
        Get the reference image path at the specified index.

        Args:
            index: Reference slot index (0-2)

        Returns:
            Path to reference image, or None if empty
        """
        if 0 <= index < self.max_references:
            return self.reference_buttons[index].frame_path
        return None

    def get_all_references(self) -> List[Optional[Path]]:
        """
        Get all reference image paths.

        Returns:
            List of paths (may contain None for empty slots)
        """
        return [btn.frame_path for btn in self.reference_buttons]

    def get_valid_references(self) -> List[Path]:
        """
        Get all valid (non-None, existing) reference image paths.

        Returns:
            List of valid paths (empty list if none)
        """
        return [
            btn.frame_path
            for btn in self.reference_buttons
            if btn.frame_path and btn.frame_path.exists()
        ]

    def clear_all(self):
        """Clear all reference images"""
        for i in range(self.max_references):
            self.set_reference_image(i, None, False)

    def _on_generate_requested(self, index: int):
        """Handle generate request for reference slot"""
        self.logger.info(f"Generate reference image {index+1} requested")
        self.generate_requested.emit(index)

    def _on_select_requested(self, index: int):
        """Handle select request for reference slot"""
        self.logger.info(f"Select reference image {index+1} from variants requested")
        self.select_requested.emit(index)

    def _on_select_from_scene_requested(self, index: int):
        """Handle select from scene request for reference slot"""
        self.logger.info(f"Select reference image {index+1} from scene images requested")
        self.select_from_scene_requested.emit(index)

    def _on_clear_requested(self, index: int):
        """Handle clear request for reference slot"""
        self.set_reference_image(index, None, False)

    def _on_view_requested(self, index: int):
        """Handle view request for reference slot"""
        ref_path = self.get_reference_image(index)
        if ref_path and ref_path.exists():
            self.logger.info(f"View reference image {index+1}: {ref_path}")
            self.view_requested.emit(index)

    def _on_load_requested(self, index: int):
        """Handle load image request for reference slot"""
        self.logger.info(f"Load reference image {index+1} from disk requested")
        self.load_requested.emit(index)
