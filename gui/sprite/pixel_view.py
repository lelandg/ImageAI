"""Nearest-neighbor zoom view for one sprite frame (design Section 4.5).

Integer zoom 1-16x or optional automatic fit, a pixel grid at zoom >= 4, a fixed-size checkerboard behind
the transparent areas, and a click-to-pick mode for the key color.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap, QTransform
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

logger = logging.getLogger(__name__)

MIN_ZOOM = 1
MAX_ZOOM = 16
GRID_MIN_ZOOM = 4
ZOOM_STEPS = (1, 2, 3, 4, 6, 8, 12, 16)
CHECKER_SIZE = 8
Rect = Tuple[int, int, int, int]   # x, y, w, h in image pixels (same shape as core.sprite.models.Rect)


def checkerboard_brush(size: int = CHECKER_SIZE, light: str = "#c8c8c8",
                       dark: str = "#8c8c8c") -> QBrush:
    """A 2x2 checker tile brush; drawn in device pixels so it never zooms."""
    tile = QPixmap(size * 2, size * 2)
    tile.fill(QColor(light))
    painter = QPainter(tile)
    painter.fillRect(0, 0, size, size, QColor(dark))
    painter.fillRect(size, size, size, size, QColor(dark))
    painter.end()
    return QBrush(tile)


def qimage_to_rgba(image: QImage) -> np.ndarray:
    """Copy a QImage into an (h, w, 4) uint8 RGBA array."""
    converted = image.convertToFormat(QImage.Format_RGBA8888)
    width, height = converted.width(), converted.height()
    stride = converted.bytesPerLine()
    buffer = bytes(converted.constBits())
    rows = np.frombuffer(buffer, dtype=np.uint8)[: stride * height].reshape(height, stride)
    return rows[:, : width * 4].reshape(height, width, 4).copy()


class PixelView(QGraphicsView):
    """Nearest-neighbor image view with manual integer zoom and optional auto-fit."""

    colorPicked = Signal(str)
    zoomChanged = Signal(float)
    fitModeChanged = Signal(bool)
    gridToggled = Signal(bool)
    selectionChanged = Signal(object)   # Optional[Rect]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._item = QGraphicsPixmapItem()
        self._item.setTransformationMode(Qt.FastTransformation)
        self._scene.addItem(self._item)
        self._image: Optional[QImage] = None
        self._zoom = 1.0
        self._auto_fit = False
        self._grid = True
        self._pick_mode = False
        self._select_mode = False
        self._selection: Optional[Rect] = None
        self._drag_start: Optional[Tuple[int, int]] = None
        self._checker = checkerboard_brush()

        self.setRenderHint(QPainter.Antialiasing, False)
        self.setRenderHint(QPainter.SmoothPixmapTransform, False)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setAlignment(Qt.AlignCenter)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)

    # ----- image ------------------------------------------------------
    def set_image(self, source: Union[Path, str, QImage, QPixmap, None]) -> bool:
        """Show `source`. Returns False (and keeps the old image) when a file fails to decode."""
        if source is None:
            image = None
        elif isinstance(source, QImage):
            image = source
        elif isinstance(source, QPixmap):
            image = source.toImage()
        else:
            image = QImage(str(source))
            if image.isNull():
                logger.error("PixelView: cannot decode image %s", source)
                return False
        self._image = image
        if image is None:
            self._item.setPixmap(QPixmap())
            self._scene.setSceneRect(QRectF())
        else:
            self._item.setPixmap(QPixmap.fromImage(image))
            self._scene.setSceneRect(QRectF(0, 0, image.width(), image.height()))
        if self._auto_fit:
            self._apply_fit()
        self.viewport().update()
        return True

    def image(self) -> Optional[QImage]:
        return self._image

    # ----- zoom -------------------------------------------------------
    def zoom(self) -> float:
        return self._zoom

    def set_zoom(self, zoom: int) -> None:
        self.set_auto_fit(False)
        zoom = max(MIN_ZOOM, min(MAX_ZOOM, int(zoom)))
        self._zoom = zoom
        self.resetTransform()
        self.scale(zoom, zoom)
        self.zoomChanged.emit(zoom)
        self.viewport().update()

    def zoom_in(self) -> None:
        if self._zoom >= MAX_ZOOM:
            return
        self.set_zoom(next((z for z in ZOOM_STEPS if z > self._zoom), MAX_ZOOM))

    def zoom_out(self) -> None:
        if self._zoom <= MIN_ZOOM:
            return
        self.set_zoom(next((z for z in reversed(ZOOM_STEPS) if z < self._zoom), MIN_ZOOM))

    def zoom_reset(self) -> None:
        self.set_zoom(MIN_ZOOM)

    def fit_zoom(self) -> int:
        """Largest integer zoom that keeps the whole image inside the viewport."""
        if self._image is None or self._image.width() == 0 or self._image.height() == 0:
            return int(self._zoom)
        vw, vh = self.viewport().width(), self.viewport().height()
        zoom = min(vw // self._image.width(), vh // self._image.height())
        self.set_zoom(max(MIN_ZOOM, min(MAX_ZOOM, zoom)))
        return int(self._zoom)

    def auto_fit(self) -> bool:
        return self._auto_fit

    def set_auto_fit(self, enabled: bool) -> None:
        """Track viewport/frame size; manual zoom commands leave fit mode."""
        changed = self._auto_fit != bool(enabled)
        self._auto_fit = bool(enabled)
        policy = (Qt.ScrollBarPolicy.ScrollBarAlwaysOff if enabled
                  else Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(policy)
        self.setVerticalScrollBarPolicy(policy)
        if enabled:
            self._apply_fit()
        if changed:
            self.fitModeChanged.emit(self._auto_fit)

    def _apply_fit(self) -> None:
        if self._image is None or self._image.isNull():
            return
        size = self.viewport().size()
        if size.width() <= 0 or size.height() <= 0:
            return
        self._zoom = min(size.width() / self._image.width(),
                         size.height() / self._image.height())
        self.setTransform(QTransform().scale(self._zoom, self._zoom))
        self.centerOn(self._item)
        self.zoomChanged.emit(self._zoom)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._auto_fit:
            self._apply_fit()

    # ----- grid -------------------------------------------------------
    def grid_visible(self) -> bool:
        return self._grid

    def set_grid_visible(self, visible: bool) -> None:
        self._grid = bool(visible)
        self.gridToggled.emit(self._grid)
        self.viewport().update()

    def toggle_grid(self) -> bool:
        self.set_grid_visible(not self._grid)
        return self._grid

    # ----- picking ----------------------------------------------------
    def pick_mode(self) -> bool:
        return self._pick_mode

    def set_pick_mode(self, enabled: bool) -> None:
        self._pick_mode = bool(enabled)
        if self._pick_mode:
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.CrossCursor)
        else:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.viewport().unsetCursor()

    def color_at(self, x: int, y: int) -> Optional[str]:
        """Hex color of the image pixel at (x, y), or None outside the image."""
        if self._image is None:
            return None
        if not (0 <= x < self._image.width() and 0 <= y < self._image.height()):
            return None
        return self._image.pixelColor(x, y).name(QColor.HexRgb).upper()

    # ----- region selection (sub-project 6 retouch reads it) ----------
    def select_mode(self) -> bool:
        return self._select_mode

    def set_select_mode(self, enabled: bool) -> None:
        self._select_mode = bool(enabled)
        self._drag_start = None
        if self._select_mode:
            self.setDragMode(QGraphicsView.NoDrag)
            self.viewport().setCursor(Qt.CrossCursor)
        elif not self._pick_mode:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.viewport().unsetCursor()

    def selection_rect(self) -> Optional[Rect]:
        return self._selection

    def set_selection_rect(self, rect: Optional[Rect]) -> None:
        """Store `rect` clamped to the image; an empty or outside rect clears the selection."""
        clamped: Optional[Rect] = None
        if rect is not None and self._image is not None:
            x, y, w, h = (int(v) for v in rect)
            x0, y0 = max(0, x), max(0, y)
            x1 = min(self._image.width(), x + w)
            y1 = min(self._image.height(), y + h)
            if x1 > x0 and y1 > y0:
                clamped = (x0, y0, x1 - x0, y1 - y0)
        self._selection = clamped
        self.selectionChanged.emit(clamped)
        self.viewport().update()

    def clear_selection(self) -> None:
        self.set_selection_rect(None)

    def _scene_pixel(self, event) -> Tuple[int, int]:
        point = self.mapToScene(event.position().toPoint())
        return int(point.x()) if point.x() >= 0 else -1, int(point.y()) if point.y() >= 0 else -1

    # ----- events -----------------------------------------------------
    def mousePressEvent(self, event):
        if self._pick_mode and event.button() == Qt.LeftButton:
            x, y = self._scene_pixel(event)
            color = self.color_at(x, y)
            self.set_pick_mode(False)
            if color is not None:
                logger.info("PixelView: picked color %s at (%d, %d)", color, x, y)
                self.colorPicked.emit(color)
            event.accept()
            return
        if self._select_mode and event.button() == Qt.LeftButton:
            self._drag_start = self._scene_pixel(event)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._select_mode and self._drag_start is not None:
            self._selection = self._rect_between(self._drag_start, self._scene_pixel(event))
            self.viewport().update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._select_mode and self._drag_start is not None and event.button() == Qt.LeftButton:
            rect = self._rect_between(self._drag_start, self._scene_pixel(event))
            self._drag_start = None
            self.set_select_mode(False)
            self.set_selection_rect(rect)
            logger.info("PixelView: selected region %s", rect)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _rect_between(self, a: Tuple[int, int], b: Tuple[int, int]) -> Optional[Rect]:
        if self._image is None:
            return None
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        return (x0, y0, x1 - x0 + 1, y1 - y0 + 1)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.save()
        painter.resetTransform()
        painter.fillRect(self.viewport().rect(), self._checker)
        painter.restore()

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        self._draw_selection(painter)
        if not self._grid or self._zoom < GRID_MIN_ZOOM or self._image is None:
            return
        width, height = self._image.width(), self._image.height()
        area = rect.intersected(QRectF(0, 0, width, height))
        if area.isEmpty():
            return
        pen = QPen(QColor(0, 0, 0, 90))
        pen.setCosmetic(True)
        pen.setWidth(1)
        painter.setPen(pen)
        for x in range(int(area.left()), min(int(area.right()) + 1, width) + 1):
            painter.drawLine(QPointF(x, area.top()), QPointF(x, area.bottom()))
        for y in range(int(area.top()), min(int(area.bottom()) + 1, height) + 1):
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))

    def _draw_selection(self, painter: QPainter) -> None:
        if self._selection is None:
            return
        x, y, w, h = self._selection
        pen = QPen(QColor(255, 255, 0, 220))
        pen.setCosmetic(True)
        pen.setWidth(1)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 255, 0, 40))
        painter.drawRect(QRectF(x, y, w, h))
