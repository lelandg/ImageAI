"""Manual overlay editor: body/tail drag handles layered on the canvas.

Mirrors GeometryEditor: handles are regenerated from the model after each scene
rebuild (LayoutTab._refresh), not preserved. Move-only. Tail drags snap to the
nearest region center on commit.
"""
from typing import List, Optional

from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem
from PySide6.QtGui import QBrush, QPen, QColor
from PySide6.QtCore import QRectF

from core.layout.models import PathSegment

_HANDLE_R = 6.0
_SNAP_RADIUS = 40.0  # px: tail snaps to a region center within this distance

_HANDLE_COLORS = {
    "body": "#2D7DD2", "tail": "#E84A5F",
    "tp0": "#39A96B", "tp1": "#39A96B", "tpc": "#F6B93B",
}


class _OvHandle(QGraphicsEllipseItem):
    """A draggable overlay handle. ``kind`` is "body" or "tail"."""

    def __init__(self, editor: "OverlayEditor", kind: str):
        super().__init__()
        self._editor = editor
        self._kind = kind
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

    def mousePressEvent(self, event):
        self._editor.begin_edit()
        super().mousePressEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self._editor.move_handle(self._kind, self.x(), self.y())
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._editor.commit()


class OverlayEditor:
    """Owns body/tail drag handles for one selected overlay on a canvas."""

    def __init__(self, canvas, layout_tab):
        self._canvas = canvas
        self._tab = layout_tab
        self._edit_id: Optional[str] = None
        self._handles: List[_OvHandle] = []
        self._pre = None

    def active_overlay_id(self) -> Optional[str]:
        return self._edit_id

    def set_edit_overlay(self, overlay_id: Optional[str]) -> None:
        self._edit_id = overlay_id or None
        self.rebuild_handles()

    def _find_overlay(self, overlay_id):
        page = self._tab._current_page()
        if page is None or not overlay_id:
            return None
        for ov in page.overlays:
            if ov.id == overlay_id:
                return ov
        return None

    def _clear(self):
        for h in self._handles:
            s = h.scene()
            if s is not None:
                s.removeItem(h)
        self._handles = []

    def rebuild_handles(self) -> None:
        self._clear()
        ov = self._find_overlay(self._edit_id)
        if ov is None:
            self._edit_id = None
            return
        scene = self._canvas.scene()
        if scene is None:
            return
        self._add_handle("body", ov.anchor)
        if ov.tail_target is not None:
            self._add_handle("tail", ov.tail_target)
        if getattr(ov, "text_path", None):
            self._add_handle("tp0", ov.text_path[0].pts[0])
            self._add_handle("tpc", ov.text_path[1].pts[0])
            self._add_handle("tp1", ov.text_path[1].pts[1])

    def _add_handle(self, kind: str, pos):
        scene = self._canvas.scene()
        h = _OvHandle(self, kind)
        h.setRect(QRectF(-_HANDLE_R, -_HANDLE_R, 2 * _HANDLE_R, 2 * _HANDLE_R))
        h.setPos(pos[0], pos[1])
        h.setZValue(1_000_000)
        h.setBrush(QBrush(QColor(_HANDLE_COLORS.get(kind, "#2D7DD2"))))
        h.setPen(QPen(QColor("#FFFFFF"), 1.5))
        scene.addItem(h)
        self._handles.append(h)

    def begin_edit(self) -> None:
        ov = self._find_overlay(self._edit_id)
        if ov is None:
            self._pre = None
            return
        tp = getattr(ov, "text_path", None)
        tp_copy = ([PathSegment(type=s.type, pts=[tuple(p) for p in s.pts]) for s in tp]
                   if tp else None)
        self._pre = (ov.anchor, ov.tail_target, tp_copy)
        self._tab.set_refresh_suspended(True)

    def move_handle(self, kind: str, x: float, y: float) -> None:
        ov = self._find_overlay(self._edit_id)
        if ov is None:
            return
        if kind == "body":
            ov.anchor = (x, y)
        elif kind == "tail":
            ov.tail_target = (x, y)
        elif kind in ("tp0", "tpc", "tp1") and getattr(ov, "text_path", None):
            if kind == "tp0":
                ov.text_path[0].pts[0] = (x, y)
            elif kind == "tpc":
                ov.text_path[1].pts[0] = (x, y)
            else:
                ov.text_path[1].pts[1] = (x, y)

    def commit(self) -> None:
        self._tab.set_refresh_suspended(False)
        ov = self._find_overlay(self._edit_id)
        if ov is None:
            self._pre = None
            return
        # Tail snaps to the nearest region center within the snap radius.
        if ov.tail_target is not None:
            from core.layout.overlay_ops import nearest_region_center
            page = self._tab._current_page()
            regions = list(page.regions) if page is not None else []
            center = nearest_region_center(ov.tail_target, regions)
            if center is not None:
                dx = center[0] - ov.tail_target[0]
                dy = center[1] - ov.tail_target[1]
                if (dx * dx + dy * dy) ** 0.5 <= _SNAP_RADIUS:
                    ov.tail_target = center
        if getattr(ov, "text_path", None):
            from core.layout.text_path import validate_text_path
            if validate_text_path(ov.text_path):
                # Invalid mid-drag geometry: restore the pre-drag snapshot.
                if self._pre is not None and len(self._pre) == 3 and self._pre[2]:
                    ov.text_path = self._pre[2]
        self._pre = None
        self._tab.snapshot_and_refresh(f"edit overlay: {ov.id}")
