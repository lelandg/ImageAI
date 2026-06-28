"""Manual region-geometry editor: vertex/curve handles layered on the canvas.

The renderer rebuilds the whole scene on every refresh, so handles are
regenerated from the model after each rebuild (see LayoutTab._refresh) rather
than preserved. Move-only: handle generation here; dragging/commit is #5a Task 5.
"""
from typing import Callable, List, Optional

from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem
from PySide6.QtGui import QBrush, QPen, QColor
from PySide6.QtCore import QRectF

from core.layout.qt_renderer import region_to_painter_path

_HANDLE_R = 6.0  # handle radius in scene (page-pixel) units


class _EditPoint:
    """One draggable model point: its current position + how to write a new one."""
    __slots__ = ("x", "y", "is_control", "apply")

    def __init__(self, x: float, y: float, is_control: bool,
                 apply: Callable[[float, float], None]):
        self.x = x
        self.y = y
        self.is_control = is_control
        self.apply = apply


def edit_points_for_region(region) -> List["_EditPoint"]:
    """Ordered editable points for a path|polygon region (rect -> [])."""
    pts: List[_EditPoint] = []
    if region.shape == "polygon":
        for i in range(len(region.points)):
            pts.append(_polygon_point(region, i))
    elif region.shape == "path":
        for seg in region.segments:
            if seg.type in ("move", "line"):
                pts.append(_seg_point(seg, 0, is_control=False))
            elif seg.type == "quad":
                pts.append(_seg_point(seg, 0, is_control=True))
                pts.append(_seg_point(seg, 1, is_control=False))
            elif seg.type == "cubic":
                pts.append(_seg_point(seg, 0, is_control=True))
                pts.append(_seg_point(seg, 1, is_control=True))
                pts.append(_seg_point(seg, 2, is_control=False))
            # close -> no handle
    return pts


def _polygon_point(region, i: int) -> "_EditPoint":
    px, py = region.points[i]

    def apply(x: float, y: float):
        region.points[i] = (round(x), round(y))

    return _EditPoint(float(px), float(py), False, apply)


def _seg_point(seg, j: int, *, is_control: bool) -> "_EditPoint":
    px, py = seg.pts[j]

    def apply(x: float, y: float):
        seg.pts[j] = (x, y)

    return _EditPoint(float(px), float(py), is_control, apply)


class _HandleItem(QGraphicsEllipseItem):
    """A vertex/control handle. Visual in Task 4; made draggable in Task 5."""

    def __init__(self, editor: "GeometryEditor", index: int):
        super().__init__()
        self._editor = editor
        self._index = index


class GeometryEditor:
    """Owns the edit handles for one selected path/polygon region on a canvas."""

    def __init__(self, canvas, layout_tab):
        self._canvas = canvas
        self._tab = layout_tab
        self._edit_region_id: Optional[str] = None
        self._points: List[_EditPoint] = []
        self._handles: List[_HandleItem] = []
        self._shape_item = None

    def active_region_id(self) -> Optional[str]:
        return self._edit_region_id

    def edit_points(self) -> List[_EditPoint]:
        return self._points

    def set_edit_region(self, region_id: Optional[str]) -> None:
        self._edit_region_id = region_id or None
        self.rebuild_handles()

    def rebuild_handles(self) -> None:
        """Re-create handles from the model for the active region.

        Call after every scene rebuild — handles are not preserved across the
        renderer's full-scene rebuild, they are reconstructed here.
        """
        self._clear()
        if not self._edit_region_id:
            return
        region = self._tab._find_region(self._edit_region_id)
        if region is None or region.shape not in ("path", "polygon"):
            self._edit_region_id = None
            return
        scene = self._canvas.scene()
        if scene is None:
            return
        self._shape_item = self._find_shape_item(scene, region)
        self._points = edit_points_for_region(region)
        for idx, ep in enumerate(self._points):
            h = _HandleItem(self, idx)
            h.setRect(QRectF(-_HANDLE_R, -_HANDLE_R, 2 * _HANDLE_R, 2 * _HANDLE_R))
            h.setPos(ep.x, ep.y)
            h.setZValue(1_000_000)
            h.setBrush(QBrush(QColor("#FFFFFF") if ep.is_control else QColor("#2D7DD2")))
            h.setPen(QPen(QColor("#2D7DD2"), 1.5))
            scene.addItem(h)
            self._handles.append(h)

    def _find_shape_item(self, scene, region):
        for it in scene.items():
            if getattr(it, "_region", None) is region and hasattr(it, "setPath"):
                return it
        return None

    def _clear(self) -> None:
        scene = self._canvas.scene()
        if scene is not None:
            for h in self._handles:
                scene.removeItem(h)
        self._handles = []
        self._points = []
        self._shape_item = None
