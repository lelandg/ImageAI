"""Canvas widget for displaying and editing layout pages."""

import logging
from typing import Optional, List, Dict, Tuple
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel,
    QPushButton, QSlider, QToolButton, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QRect, QPoint, QSize
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QBrush, QFont,
    QPainterPath, QImage
)

from core.layout.models import PageSpec, TextBlock, ImageBlock, Rect as LayoutRect
from core.layout import LayoutEngine

logger = logging.getLogger(__name__)


class PageCanvas(QLabel):
    """A canvas for displaying a single page with block outlines."""

    blockClicked = Signal(str)  # Emits block ID when clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_spec: Optional[PageSpec] = None
        self.rendered_image: Optional[QPixmap] = None
        self.zoom_level = 1.0
        self.show_block_outlines = True
        self.selected_block_id: Optional[str] = None
        self.block_rects: Dict[str, QRect] = {}  # block_id -> QRect in widget coords

        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(400, 400)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background-color: #e5e7eb; border: 1px solid #d1d5db;")

    def set_page(self, page_spec: PageSpec, rendered_image: Optional[QPixmap] = None):
        """Set the page to display."""
        self.page_spec = page_spec
        self.rendered_image = rendered_image
        self.block_rects.clear()
        self.update_display()

    def set_rendered_image(self, image: QPixmap):
        """Set the rendered image."""
        self.rendered_image = image
        self.update_display()

    def set_zoom(self, zoom: float):
        """Set the zoom level (0.1 to 3.0)."""
        self.zoom_level = max(0.1, min(3.0, zoom))
        self.update_display()

    def set_show_outlines(self, show: bool):
        """Toggle block outline visibility."""
        self.show_block_outlines = show
        self.update_display()

    def set_selected_block(self, block_id: Optional[str]):
        """Set the selected block."""
        self.selected_block_id = block_id
        self.update_display()

    def update_display(self):
        """Update the canvas display."""
        if not self.page_spec:
            self.setPixmap(QPixmap())
            self.setText("No page loaded")
            return

        # Get page dimensions
        page_width, page_height = self.page_spec.page_size_px

        # Create canvas
        canvas_width = int(page_width * self.zoom_level)
        canvas_height = int(page_height * self.zoom_level)

        canvas = QPixmap(canvas_width, canvas_height)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw background
        if self.page_spec.background:
            bg_color = QColor(self.page_spec.background)
        else:
            bg_color = QColor("#FFFFFF")
        painter.fillRect(0, 0, canvas_width, canvas_height, bg_color)

        # Draw rendered image if available
        if self.rendered_image:
            scaled_image = self.rendered_image.scaled(
                canvas_width, canvas_height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            painter.drawPixmap(0, 0, scaled_image)

        # Draw block outlines if enabled
        if self.show_block_outlines:
            self.draw_block_outlines(painter)

        painter.end()

        # Update widget
        self.setPixmap(canvas)
        self.setText("")

    def draw_block_outlines(self, painter: QPainter):
        """Draw outlines around blocks."""
        if not self.page_spec:
            return

        self.block_rects.clear()

        # Draw each block
        for block in self.page_spec.blocks:
            block_id = block.id
            rect = block.rect

            # Convert to zoomed coordinates (rect is a tuple: (x, y, width, height))
            x = int(rect[0] * self.zoom_level)
            y = int(rect[1] * self.zoom_level)
            w = int(rect[2] * self.zoom_level)
            h = int(rect[3] * self.zoom_level)

            qrect = QRect(x, y, w, h)
            self.block_rects[block_id] = qrect

            # Determine outline color
            if block_id == self.selected_block_id:
                # Selected block - bright blue
                outline_color = QColor("#3B82F6")
                outline_width = 3
            elif isinstance(block, TextBlock):
                # Text block - yellow
                outline_color = QColor("#FCD34D")
                outline_width = 2
            elif isinstance(block, ImageBlock):
                # Image block - blue
                outline_color = QColor("#60A5FA")
                outline_width = 2
            else:
                # Unknown block - gray
                outline_color = QColor("#9CA3AF")
                outline_width = 2

            # Draw outline
            pen = QPen(outline_color, outline_width)
            pen.setStyle(Qt.DashLine if block_id != self.selected_block_id else Qt.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(qrect)

            # Draw block label
            label_font = QFont("Arial", max(8, int(10 * self.zoom_level)))
            painter.setFont(label_font)
            painter.setPen(QPen(QColor("#1F2937")))

            label_text = f"{block_id} ({type(block).__name__})"
            painter.drawText(
                qrect.adjusted(4, 2, -4, -2),
                Qt.AlignTop | Qt.AlignLeft,
                label_text
            )

    def mousePressEvent(self, event):
        """Handle mouse press to select blocks."""
        if event.button() == Qt.LeftButton:
            click_pos = event.pos()

            # Adjust for pixmap position (centered in label)
            if self.pixmap():
                pixmap_rect = self.pixmap().rect()
                label_rect = self.rect()

                # Calculate offset to center
                offset_x = (label_rect.width() - pixmap_rect.width()) // 2
                offset_y = (label_rect.height() - pixmap_rect.height()) // 2

                adjusted_pos = QPoint(
                    click_pos.x() - offset_x,
                    click_pos.y() - offset_y
                )

                # Check which block was clicked
                for block_id, rect in self.block_rects.items():
                    if rect.contains(adjusted_pos):
                        logger.info(f"Block clicked: {block_id}")
                        self.blockClicked.emit(block_id)
                        return

        super().mousePressEvent(event)


class CanvasWidget(QWidget):
    """Widget for displaying and editing layout pages."""

    blockSelected = Signal(str)  # Emits block ID when selected
    pageChanged = Signal(int)  # Emits page index when changed

    def __init__(self, layout_engine: Optional[LayoutEngine] = None, parent=None):
        super().__init__(parent)
        self.layout_engine = layout_engine
        self.current_pages: List[PageSpec] = []
        self.current_page_index = 0

        self.init_ui()

    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header with title and controls
        header_layout = QHBoxLayout()

        self.title_label = QLabel("Canvas")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 8px;")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        # Show outlines toggle
        self.outlines_btn = QToolButton()
        self.outlines_btn.setText("Outlines")
        self.outlines_btn.setCheckable(True)
        self.outlines_btn.setChecked(True)
        self.outlines_btn.clicked.connect(self.toggle_outlines)
        self.outlines_btn.setToolTip("Show/hide block outlines")
        header_layout.addWidget(self.outlines_btn)

        layout.addLayout(header_layout)

        # Zoom controls
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Zoom:"))

        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(10, 300)  # 10% to 300%
        self.zoom_slider.setValue(100)
        self.zoom_slider.setTickPosition(QSlider.TicksBelow)
        self.zoom_slider.setTickInterval(50)
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        zoom_layout.addWidget(self.zoom_slider, 1)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(50)
        self.zoom_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        zoom_layout.addWidget(self.zoom_label)

        # Zoom buttons
        zoom_out_btn = QToolButton()
        zoom_out_btn.setText("-")
        zoom_out_btn.clicked.connect(lambda: self.zoom_slider.setValue(self.zoom_slider.value() - 10))
        zoom_layout.addWidget(zoom_out_btn)

        zoom_in_btn = QToolButton()
        zoom_in_btn.setText("+")
        zoom_in_btn.clicked.connect(lambda: self.zoom_slider.setValue(self.zoom_slider.value() + 10))
        zoom_layout.addWidget(zoom_in_btn)

        zoom_fit_btn = QToolButton()
        zoom_fit_btn.setText("Fit")
        zoom_fit_btn.clicked.connect(lambda: self.zoom_slider.setValue(100))
        zoom_layout.addWidget(zoom_fit_btn)

        layout.addLayout(zoom_layout)

        # Scroll area for canvas
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setAlignment(Qt.AlignCenter)

        # Page canvas
        self.canvas = PageCanvas()
        self.canvas.blockClicked.connect(self.on_block_clicked)
        scroll_area.setWidget(self.canvas)

        layout.addWidget(scroll_area, 1)

        # Page navigation
        nav_layout = QHBoxLayout()

        self.prev_page_btn = QPushButton("< Previous")
        self.prev_page_btn.clicked.connect(self.previous_page)
        self.prev_page_btn.setEnabled(False)
        nav_layout.addWidget(self.prev_page_btn)

        self.page_label = QLabel("No page")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setStyleSheet("font-weight: bold;")
        nav_layout.addWidget(self.page_label, 1)

        self.next_page_btn = QPushButton("Next >")
        self.next_page_btn.clicked.connect(self.next_page)
        self.next_page_btn.setEnabled(False)
        nav_layout.addWidget(self.next_page_btn)

        layout.addLayout(nav_layout)

    def set_pages(self, pages: List[PageSpec]):
        """Set the pages to display."""
        self.current_pages = pages
        self.current_page_index = 0 if pages else -1
        self.update_page_display()

    def goto_page(self, page_index: int):
        """Navigate to a specific page by index."""
        if 0 <= page_index < len(self.current_pages):
            self.current_page_index = page_index
            self.update_page_display()

    def set_layout_engine(self, engine: LayoutEngine):
        """Set the layout engine."""
        self.layout_engine = engine

    def update_page_display(self):
        """Update the display for the current page."""
        if self.current_page_index >= 0 and self.current_page_index < len(self.current_pages):
            page = self.current_pages[self.current_page_index]
            self.canvas.set_page(page)

            # Update page label
            self.page_label.setText(f"Page {self.current_page_index + 1} of {len(self.current_pages)}")

            # Update navigation buttons
            self.prev_page_btn.setEnabled(self.current_page_index > 0)
            self.next_page_btn.setEnabled(self.current_page_index < len(self.current_pages) - 1)

            # Emit signal
            self.pageChanged.emit(self.current_page_index)

            # Render the page if engine is available
            if self.layout_engine:
                self.render_current_page()

        else:
            self.canvas.set_page(None)
            self.page_label.setText("No page")
            self.prev_page_btn.setEnabled(False)
            self.next_page_btn.setEnabled(False)

    def render_current_page(self):
        """Render the current page using the layout engine."""
        if not self.layout_engine or self.current_page_index < 0:
            return

        try:
            page = self.current_pages[self.current_page_index]

            # Render the page (returns PIL Image)
            pil_image = self.layout_engine.render_page_to_image(page)

            # Convert PIL Image to QPixmap
            if pil_image:
                # Convert PIL Image to bytes
                import io
                buffer = io.BytesIO()
                pil_image.save(buffer, format="PNG")
                buffer.seek(0)

                # Load into QPixmap
                qimage = QImage()
                qimage.loadFromData(buffer.read())
                pixmap = QPixmap.fromImage(qimage)

                self.canvas.set_rendered_image(pixmap)
                logger.info(f"Rendered page {self.current_page_index + 1}")

        except Exception as e:
            logger.error(f"Failed to render page: {e}", exc_info=True)

    def previous_page(self):
        """Go to the previous page."""
        if self.current_page_index > 0:
            self.current_page_index -= 1
            self.update_page_display()

    def next_page(self):
        """Go to the next page."""
        if self.current_page_index < len(self.current_pages) - 1:
            self.current_page_index += 1
            self.update_page_display()

    def toggle_outlines(self):
        """Toggle block outlines visibility."""
        show = self.outlines_btn.isChecked()
        self.canvas.set_show_outlines(show)

    def on_zoom_changed(self, value: int):
        """Handle zoom slider change."""
        zoom = value / 100.0
        self.canvas.set_zoom(zoom)
        self.zoom_label.setText(f"{value}%")

    def on_block_clicked(self, block_id: str):
        """Handle block click."""
        self.canvas.set_selected_block(block_id)
        self.blockSelected.emit(block_id)

    def get_current_page(self) -> Optional[PageSpec]:
        """Get the currently displayed page."""
        if self.current_page_index >= 0 and self.current_page_index < len(self.current_pages):
            return self.current_pages[self.current_page_index]
        return None

    def get_selected_block_id(self) -> Optional[str]:
        """Get the currently selected block ID."""
        return self.canvas.selected_block_id
