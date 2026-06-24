"""Live editor canvas: a QGraphicsView over a renderer-built scene."""
from typing import Optional

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtGui import QPainter
from PySide6.QtCore import Signal, Qt

from core.layout.models import PageSpec
from core.layout import qt_renderer


class CanvasWidget(QGraphicsView):
    regionSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self._page: Optional[PageSpec] = None
        self._scene: Optional[QGraphicsScene] = None
        self.setScene(QGraphicsScene(self))

    def load_page(self, page: PageSpec) -> None:
        old = self.scene()
        if old is not None:
            try:
                old.selectionChanged.disconnect(self._on_selection_changed)
            except (RuntimeError, TypeError):
                pass  # old scene's signal was not connected
        self._page = page
        scene = qt_renderer.build_scene(page, selectable=True)
        scene.setParent(self)
        scene.selectionChanged.connect(self._on_selection_changed)
        self.setScene(scene)
        self._scene = scene
        self.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)

    def selected_region_id(self) -> Optional[str]:
        for it in self.scene().selectedItems():
            rid = it.data(0)
            if rid:
                return rid
        return None

    def _on_selection_changed(self):
        rid = self.selected_region_id()
        self.regionSelected.emit(rid or "")
