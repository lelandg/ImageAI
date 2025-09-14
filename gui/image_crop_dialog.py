"""
Image Crop Dialog with marching ants selection rectangle
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QWidget, QGraphicsView, QGraphicsScene,
                               QDialogButtonBox, QSizePolicy)
from PySide6.QtCore import Qt, QRectF, QTimer, QPointF, Signal
from PySide6.QtGui import (QPainter, QPen, QPixmap, QImage, QBrush,
                           QKeyEvent, QPainterPath)
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem
import logging

logger = logging.getLogger(__name__)


class MarchingAntsRect(QGraphicsRectItem):
    """Rectangle with marching ants animation"""

    def __init__(self, rect, parent=None):
        super().__init__(rect, parent)
        self.offset = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_offset)
        self.timer.start(50)  # Update every 50ms

        # Style
        self.setPen(self.create_pen())
        self.setBrush(QBrush(Qt.NoBrush))

    def create_pen(self):
        pen = QPen(Qt.white, 2, Qt.DashLine)
        pen.setDashPattern([4, 4])
        pen.setDashOffset(self.offset)
        return pen

    def update_offset(self):
        self.offset = (self.offset + 1) % 8
        self.setPen(self.create_pen())
        self.update()

    def stop_animation(self):
        self.timer.stop()


class ImageCropView(QGraphicsView):
    """Custom view for image cropping with keyboard controls"""

    selection_moved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selection_rect = None
        self.image_item = None
        self.move_step = 5  # Pixels to move per key press
        self.fast_move_step = 20  # Pixels to move with Shift

    def set_selection_rect(self, rect):
        self.selection_rect = rect
        # Set focus to enable keyboard events
        self.setFocus()

    def keyPressEvent(self, event: QKeyEvent):
        if not self.selection_rect:
            super().keyPressEvent(event)
            return

        # Determine move distance
        step = self.fast_move_step if event.modifiers() & Qt.ShiftModifier else self.move_step

        # Get current position
        rect = self.selection_rect.rect()
        new_pos = self.selection_rect.pos()

        # Move based on key
        moved = True
        if event.key() == Qt.Key_Left:
            new_pos.setX(new_pos.x() - step)
        elif event.key() == Qt.Key_Right:
            new_pos.setX(new_pos.x() + step)
        elif event.key() == Qt.Key_Up:
            new_pos.setY(new_pos.y() - step)
        elif event.key() == Qt.Key_Down:
            new_pos.setY(new_pos.y() + step)
        else:
            moved = False
            super().keyPressEvent(event)

        if moved:
            # Check bounds
            if self.image_item:
                img_rect = self.image_item.boundingRect()
                max_x = img_rect.width() - rect.width()
                max_y = img_rect.height() - rect.height()

                new_pos.setX(max(0, min(new_pos.x(), max_x)))
                new_pos.setY(max(0, min(new_pos.y(), max_y)))

            self.selection_rect.setPos(new_pos)
            self.selection_moved.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.selection_rect:
            # Start drag
            scene_pos = self.mapToScene(event.pos())

            # Get selection bounds in scene coordinates
            rect = self.selection_rect.rect()
            selection_pos = self.selection_rect.pos()
            selection_scene_rect = QRectF(
                selection_pos.x() + rect.x(),
                selection_pos.y() + rect.y(),
                rect.width(),
                rect.height()
            )

            # Check if click is within selection
            if selection_scene_rect.contains(scene_pos):
                self.drag_start = scene_pos - selection_pos
                self.dragging = True
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if hasattr(self, 'dragging') and self.dragging:
            scene_pos = self.mapToScene(event.pos())
            new_pos = scene_pos - self.drag_start

            # Check bounds
            rect = self.selection_rect.rect()
            if self.image_item:
                img_rect = self.image_item.boundingRect()
                max_x = img_rect.width() - rect.width()
                max_y = img_rect.height() - rect.height()

                new_pos.setX(max(0, min(new_pos.x(), max_x)))
                new_pos.setY(max(0, min(new_pos.y(), max_y)))

            self.selection_rect.setPos(new_pos)
            self.selection_moved.emit()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if hasattr(self, 'dragging'):
            self.dragging = False
        super().mouseReleaseEvent(event)


class ImageCropDialog(QDialog):
    """Dialog for cropping images with visual selection"""

    def __init__(self, image, target_width, target_height, parent=None):
        super().__init__(parent)
        self.original_image = image
        self.target_width = target_width
        self.target_height = target_height
        self.scaled_image = None
        self.cropped_image = None
        self.restore_mode = False

        self.setup_ui()
        self.scale_and_position_image()

    def setup_ui(self):
        self.setWindowTitle("Crop Image to Size")
        self.setModal(True)
        self.resize(900, 700)

        layout = QVBoxLayout()

        # Info label
        self.info_label = QLabel()
        layout.addWidget(self.info_label)

        # Main content area
        content_layout = QHBoxLayout()

        # Graphics view for image
        self.view = ImageCropView()
        self.view.setMinimumSize(600, 500)
        # Enable mouse tracking and interaction
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.view.setInteractive(True)
        content_layout.addWidget(self.view, 3)

        # Help panel
        help_panel = QWidget()
        help_layout = QVBoxLayout(help_panel)
        help_layout.setAlignment(Qt.AlignTop)

        help_title = QLabel("<b>Keyboard Controls:</b>")
        help_layout.addWidget(help_title)

        help_text = QLabel(
            "Arrow Keys - Move selection\n"
            "Shift + Arrow - Move faster\n"
            "Mouse Drag - Move selection\n"
            "\n"
            "<b>Actions:</b>\n"
            "OK - Crop to selection\n"
            "Cancel - Keep original\n"
            "Restore Size - Show original size"
        )
        help_text.setWordWrap(True)
        help_layout.addWidget(help_text)

        # Position info
        self.position_label = QLabel("Position: (0, 0)")
        help_layout.addWidget(self.position_label)

        help_layout.addStretch()
        content_layout.addWidget(help_panel, 1)

        layout.addLayout(content_layout)

        # Buttons
        button_layout = QHBoxLayout()

        self.restore_btn = QPushButton("Restore Size")
        self.restore_btn.clicked.connect(self.restore_size)
        button_layout.addWidget(self.restore_btn)

        button_layout.addStretch()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept_crop)
        self.button_box.rejected.connect(self.reject)
        button_layout.addWidget(self.button_box)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Setup scene
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)

    def scale_and_position_image(self):
        """Scale image to target width and setup selection rectangle"""
        # Calculate scale factor
        scale_factor = self.target_width / self.original_image.width()
        new_height = int(self.original_image.height() * scale_factor)

        # Scale image
        self.scaled_image = self.original_image.scaled(
            self.target_width, new_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        # Clear scene
        self.scene.clear()

        # Add image to scene
        pixmap = QPixmap.fromImage(self.scaled_image)
        self.image_item = self.scene.addPixmap(pixmap)

        # Create selection rectangle
        if new_height > self.target_height:
            # Need to crop - create rectangle at target size
            rect_height = self.target_height
            initial_y = (new_height - self.target_height) / 2  # Center vertically
        else:
            # Image is smaller than target - use full height
            rect_height = new_height
            initial_y = 0

        # Create rectangle at origin, will position it separately
        selection_rect = QRectF(0, 0, self.target_width, rect_height)
        self.selection = MarchingAntsRect(selection_rect)
        self.scene.addItem(self.selection)
        # Set initial position
        self.selection.setPos(0, initial_y)

        # Store in view for keyboard handling
        self.view.set_selection_rect(self.selection)
        self.view.image_item = self.image_item
        self.view.selection_moved.connect(self.update_position_info)

        # Update info
        self.update_info()
        self.update_position_info()

        # Fit view
        self.view.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    def update_info(self):
        """Update info label with current dimensions"""
        orig_w, orig_h = self.original_image.width(), self.original_image.height()
        scaled_w, scaled_h = self.scaled_image.width(), self.scaled_image.height()

        if self.restore_mode:
            info = f"Original Size: {orig_w}x{orig_h} | "
            info += f"Target: {self.target_width}x{self.target_height} | "
            info += f"Selection will be scaled to match proportions"
        else:
            info = f"Original: {orig_w}x{orig_h} → "
            info += f"Scaled: {scaled_w}x{scaled_h} | "
            info += f"Target: {self.target_width}x{self.target_height}"

            if scaled_h > self.target_height:
                info += " (Crop needed)"
            else:
                info += " (No crop needed)"

        self.info_label.setText(info)

    def update_position_info(self):
        """Update position label with current selection position"""
        if self.selection:
            pos = self.selection.pos()
            self.position_label.setText(f"Position: ({int(pos.x())}, {int(pos.y())})")

    def restore_size(self):
        """Switch to restore mode - show original size with proportional selection"""
        self.restore_mode = True

        # Clear scene
        self.scene.clear()

        # Add original image
        pixmap = QPixmap.fromImage(self.original_image)
        self.image_item = self.scene.addPixmap(pixmap)

        # Calculate proportional rectangle
        orig_w = self.original_image.width()
        orig_h = self.original_image.height()

        # Scale target dimensions to original image scale
        scale_factor = orig_w / self.target_width
        rect_w = orig_w  # Full width
        rect_h = int(self.target_height * scale_factor)

        # Center vertically if needed
        if rect_h < orig_h:
            initial_y = (orig_h - rect_h) / 2
        else:
            rect_h = orig_h
            initial_y = 0

        # Create rectangle at origin, position separately
        selection_rect = QRectF(0, 0, rect_w, rect_h)
        self.selection = MarchingAntsRect(selection_rect)
        self.scene.addItem(self.selection)
        # Set initial position
        self.selection.setPos(0, initial_y)

        # Update view
        self.view.set_selection_rect(self.selection)
        self.view.image_item = self.image_item

        # Update UI
        self.restore_btn.setText("Show Scaled")
        self.restore_btn.clicked.disconnect()
        self.restore_btn.clicked.connect(self.show_scaled)

        self.update_info()
        self.update_position_info()
        self.view.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    def show_scaled(self):
        """Return to scaled mode"""
        self.restore_mode = False
        self.restore_btn.setText("Restore Size")
        self.restore_btn.clicked.disconnect()
        self.restore_btn.clicked.connect(self.restore_size)

        self.scale_and_position_image()

    def accept_crop(self):
        """Apply the crop and close dialog"""
        if self.selection:
            # Get selection rectangle in image coordinates
            rect = self.selection.rect()
            pos = self.selection.pos()

            crop_rect = QRectF(
                pos.x(), pos.y(),
                rect.width(), rect.height()
            )

            # Crop the appropriate image
            if self.restore_mode:
                # Crop from original and then scale
                cropped = self.original_image.copy(crop_rect.toRect())
                self.cropped_image = cropped.scaled(
                    self.target_width, self.target_height,
                    Qt.IgnoreAspectRatio,
                    Qt.SmoothTransformation
                )
            else:
                # Crop from scaled image
                self.cropped_image = self.scaled_image.copy(crop_rect.toRect())

            # Stop animation
            self.selection.stop_animation()

        self.accept()

    def get_result(self):
        """Get the final processed image"""
        if self.cropped_image:
            return self.cropped_image
        else:
            return self.scaled_image