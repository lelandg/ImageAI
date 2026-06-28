"""Live editor canvas: a QGraphicsView over a renderer-built scene."""
from typing import Optional

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtGui import QPainter
from PySide6.QtCore import Signal, Qt

from core.layout.models import PageSpec
from core.layout import qt_renderer


class CanvasWidget(QGraphicsView):
    regionSelected = Signal(str)
    knifeLine = Signal(float, float, float, float)  # p1x, p1y, p2x, p2y (scene px)
    mergeTarget = Signal(str)                        # clicked region id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self._page: Optional[PageSpec] = None
        self._scene: Optional[QGraphicsScene] = None
        self.setScene(QGraphicsScene(self))
        self._tool_mode = "none"
        self._knife_first = None

    def load_page(self, page: PageSpec, style=None, *, locked: bool = True) -> None:
        old = self._scene
        if old is not None:
            try:
                old.selectionChanged.disconnect(self._on_selection_changed)
            except (RuntimeError, TypeError):
                pass
            old.deleteLater()  # don't let replaced scenes accumulate as children
        self._page = page
        scene = qt_renderer.build_scene(page, selectable=True, style=style, locked=locked)
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

    def set_tool_mode(self, mode: str) -> None:
        """Switch the canvas tool: "none" (normal select), "knife", or "merge"."""
        if mode not in ("none", "knife", "merge"):
            mode = "none"
        self._tool_mode = mode
        self._knife_first = None

    def tool_mode(self) -> str:
        return self._tool_mode

    def _register_knife_point(self, x: float, y: float):
        """Collect a knife click; return (x1,y1,x2,y2) on the second, else None."""
        if self._knife_first is None:
            self._knife_first = (x, y)
            return None
        x1, y1 = self._knife_first
        self._knife_first = None
        return (x1, y1, x, y)

    def _region_id_at(self, scene_pt):
        for it in self.scene().items(scene_pt):
            rid = it.data(0)
            if rid:
                return rid
        return None

    def mousePressEvent(self, event):
        if self._tool_mode == "knife":
            sp = self.mapToScene(event.position().toPoint())
            line = self._register_knife_point(sp.x(), sp.y())
            if line is not None:
                self._tool_mode = "none"
                self.knifeLine.emit(*line)
            event.accept()
            return
        if self._tool_mode == "merge":
            sp = self.mapToScene(event.position().toPoint())
            rid = self._region_id_at(sp)
            self._tool_mode = "none"
            if rid:
                self.mergeTarget.emit(rid)
            event.accept()
            return
        super().mousePressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        scene = self.scene()
        if scene is not None:
            self.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)

    def _on_selection_changed(self):
        rid = self.selected_region_id()
        self.regionSelected.emit(rid or "")
