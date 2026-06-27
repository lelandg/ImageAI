"""Native Qt renderer: PageSpec -> QGraphicsScene -> QImage/PNG (source of truth)."""
from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsRectItem, QGraphicsPolygonItem,
    QGraphicsSimpleTextItem, QGraphicsItem, QGraphicsPixmapItem, QGraphicsPathItem,
)
from PySide6.QtGui import (
    QColor, QBrush, QPen, QPolygonF, QImage, QPainter, QFont, QPixmap,
    QPdfWriter, QPageSize, QPageLayout, QPainterPath,
)
from PySide6.QtCore import QPointF, QRectF, Qt, QSizeF, QMarginsF

import logging

from core.layout.models import PageSpec, Region, DocumentSpec
from core.layout.styles import effective_text_style
from core.layout.geometry import validate_segments

logger = logging.getLogger(__name__)

_PLACEHOLDER_FILL = QColor("#E9ECEF")
_PLACEHOLDER_PEN = QColor("#ADB5BD")
# Text-region guide box: a medium grey dash that the cosmetic pen keeps at a
# constant on-screen width no matter how far the page is zoomed out, so empty
# text boxes stay visible in the editor instead of vanishing when fit-to-view
# shrinks a 300-DPI page.
_TEXT_GUIDE_PEN = QColor("#8A94A6")
# Readable fallback when a text region resolves no role/style at all — without
# it the bare QFont default (~16px) is invisible on a multi-thousand-pixel page.
_DEFAULT_TEXT_PX = 48


def _resolve_bg(page: PageSpec) -> str:
    """Resolve a page background to a hex color.

    Image-path backgrounds are deferred to a later phase; until then a
    non-hex background renders as white in every render path (editor, PNG,
    PDF), keeping them consistent.
    """
    if page.background and page.background.startswith("#"):
        return page.background
    return "#FFFFFF"


def region_to_painter_path(r: Region) -> QPainterPath:
    """Build a QPainterPath for a region (rect | polygon | path).

    Invalid path segments are logged and the region falls back to its bbox
    rectangle, so a region never renders as nothing.
    """
    path = QPainterPath()
    if r.shape == "path" and r.segments:
        issues = validate_segments(r.segments)
        if issues:
            logger.error("Region %s has invalid path segments; falling back to bbox: %s",
                         r.id, "; ".join(issues))
        else:
            for seg in r.segments:
                if seg.type == "move":
                    path.moveTo(*seg.pts[0])
                elif seg.type == "line":
                    path.lineTo(*seg.pts[0])
                elif seg.type == "quad":
                    (cx, cy), (ex, ey) = seg.pts
                    path.quadTo(cx, cy, ex, ey)
                elif seg.type == "cubic":
                    (c1x, c1y), (c2x, c2y), (ex, ey) = seg.pts
                    path.cubicTo(c1x, c1y, c2x, c2y, ex, ey)
                elif seg.type == "close":
                    path.closeSubpath()
            if not path.isEmpty():
                return path
    elif r.shape == "polygon" and r.points:
        path.addPolygon(QPolygonF([QPointF(px, py) for px, py in r.points]))
        path.closeSubpath()
        return path
    x, y, w, h = r.bbox
    path.addRect(QRectF(x, y, w, h))
    return path


def _apply_flags(item: QGraphicsItem, selectable: bool, region_id: str,
                 *, movable: bool = True) -> None:
    item.setData(0, region_id)
    if selectable:
        item.setFlag(QGraphicsItem.ItemIsSelectable, True)
        if movable:
            item.setFlag(QGraphicsItem.ItemIsMovable, True)
            # Needed for itemChange(ItemPositionHasChanged) to fire so a drag is
            # written back into the region's geometry (see _RegionMoveMixin).
            item.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)


def _writeback_move(item) -> None:
    """Persist a drag into the bound region's ``bbox`` (and polygon ``points``).

    Handles all carry their geometry in item-local coordinates with the item at
    scene pos (0,0); a drag therefore shows up purely as ``item.pos()``, which is
    the delta to apply to the region's original geometry.
    """
    region = getattr(item, "_region", None)
    if region is None:
        return
    dx, dy = item.x(), item.y()
    x, y, w, h = item._base_bbox
    region.bbox = (round(x + dx), round(y + dy), w, h)
    if item._base_points:
        region.points = [(round(px + dx), round(py + dy)) for px, py in item._base_points]


class _RegionMoveMixin:
    """Mix in to a QGraphicsItem to write drag deltas back into a Region.

    The renderer is rebuilt from the model on every refresh, so persisting moves
    here is what makes "unlock, drag, re-lock" survive a refresh and a save.
    """

    def _bind_region(self, region: Region) -> None:
        self._region = region
        self._base_bbox = tuple(region.bbox)
        self._base_points = list(region.points)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            _writeback_move(self)
        return super().itemChange(change, value)


class _RegionRectItem(_RegionMoveMixin, QGraphicsRectItem):
    def __init__(self, rect: QRectF, region: Region):
        super().__init__(rect)
        self._bind_region(region)


class _RegionPolygonItem(_RegionMoveMixin, QGraphicsPolygonItem):
    def __init__(self, polygon: QPolygonF, region: Region):
        super().__init__(polygon)
        self._bind_region(region)


class _RegionPixmapItem(_RegionMoveMixin, QGraphicsPixmapItem):
    def __init__(self, pixmap: QPixmap, region: Region):
        super().__init__(pixmap)
        self._bind_region(region)


class _RegionPathItem(_RegionMoveMixin, QGraphicsPathItem):
    def __init__(self, path: QPainterPath, region: Region):
        super().__init__(path)
        self._bind_region(region)

    def shape(self):
        # Clip children to the FILLED interior, not the stroked outline (the
        # default QGraphicsPathItem.shape() would return just the pen outline).
        return self.path()


def _add_image_region(scene: QGraphicsScene, r: Region, selectable: bool,
                      *, locked: bool = True) -> None:
    # Image frames are ALWAYS locked in position (only text follows the lock
    # toggle); they stay selectable so the region can be picked.
    movable = False
    istyle = r.image_style
    stroke_px = istyle.stroke_px if istyle else 0
    stroke_color = istyle.stroke_color if istyle else "#000000"
    fit = istyle.fit if istyle else "cover"

    path = region_to_painter_path(r)
    frame = _RegionPathItem(path, r)
    frame.setFlag(QGraphicsItem.ItemClipsChildrenToShape, True)
    frame.setPen(QPen(QColor(stroke_color), stroke_px) if stroke_px > 0 else QPen(Qt.NoPen))

    pix = QPixmap(r.image_ref) if r.image_ref else None
    filled = pix is not None and not pix.isNull()

    if filled:
        frame.setBrush(QBrush(Qt.transparent))
        x, y, w, h = r.bbox
        mode = Qt.KeepAspectRatioByExpanding if fit == "cover" else Qt.KeepAspectRatio
        scaled = pix.scaled(int(w), int(h), mode, Qt.SmoothTransformation)
        child = _RegionPixmapItem(scaled, r)
        # Center the scaled pixmap in the bbox; the parent shape clip crops the
        # overflow (cover) or reveals panel bg in the letterbox (contain).
        child.setOffset(x + (w - scaled.width()) / 2.0, y + (h - scaled.height()) / 2.0)
        child.setParentItem(frame)
        _apply_flags(child, selectable, r.id, movable=movable)
    else:
        frame.setBrush(QBrush(_PLACEHOLDER_FILL))
        if stroke_px == 0:
            # Keep empty image placeholders outlined in the editor even when no
            # comic-frame stroke is configured. A real stroke (stroke_px > 0) was
            # already applied to the frame above, so only fill the gap for 0.
            frame.setPen(QPen(_PLACEHOLDER_PEN, 1))
        lx, ly, _, _ = r.bbox
        label = QGraphicsSimpleTextItem(r.name or "[image]", frame)
        label.setPos(lx + 4, ly + 4)
        label.setBrush(QBrush(QColor("#6C757D")))

    _apply_flags(frame, selectable, r.id, movable=movable)
    scene.addItem(frame)


def _add_text_region(scene: QGraphicsScene, r: Region, selectable: bool, project_style=None,
                     *, locked: bool = True) -> None:
    x, y, w, h = r.bbox
    # The dashed guide box is an editor-only affordance (it's also the region's
    # selectable/movable handle). Export paths call build_scene(selectable=False),
    # so skipping it there keeps the guides out of the rendered PNG/PDF.
    box = None
    if selectable:
        box = _RegionRectItem(QRectF(x, y, w, h), r)
        box.setBrush(QBrush(Qt.transparent))
        pen = QPen(_TEXT_GUIDE_PEN, 1.5, Qt.DashLine)
        pen.setCosmetic(True)  # constant on-screen width at any zoom -> always visible
        box.setPen(pen)
        _apply_flags(box, selectable, r.id, movable=(selectable and not locked))
        scene.addItem(box)

    text = QGraphicsSimpleTextItem(r.text or "")
    ts = effective_text_style(r, project_style)
    font = QFont()
    if ts:
        if ts.family:
            font.setFamily(ts.family[0])
        font.setBold(ts.weight in ("bold", "black", "semibold"))
        font.setItalic(ts.italic)
        text.setBrush(QBrush(QColor(ts.color)))
    # Always pin a pixel size: an unresolved role/style would otherwise leave the
    # QFont at its ~16px default, which is invisible on a 300-DPI page.
    font.setPixelSize(ts.size_px if ts and ts.size_px else _DEFAULT_TEXT_PX)
    text.setFont(font)
    # In the editor the text is a child of the guide box so applied text stays
    # locked to its frame and moves with it; on export there is no box, so the
    # text is a top-level scene item.
    if box is not None:
        text.setParentItem(box)
    else:
        scene.addItem(text)
    text.setPos(x + 2, y + 2)


def build_scene(page: PageSpec, *, selectable: bool = False, style=None,
                locked: bool = True) -> QGraphicsScene:
    pw, ph = page.page_size_px
    scene = QGraphicsScene(0, 0, pw, ph)
    scene.setBackgroundBrush(QBrush(QColor(_resolve_bg(page))))
    for r in sorted(page.regions, key=lambda rr: rr.z):
        if r.kind == "image":
            _add_image_region(scene, r, selectable, locked=locked)
        else:
            _add_text_region(scene, r, selectable, project_style=style, locked=locked)
    return scene


def render_page_to_image(page: PageSpec, *, style=None) -> QImage:
    pw, ph = page.page_size_px
    scene = build_scene(page, style=style)
    img = QImage(pw, ph, QImage.Format_ARGB32)
    img.fill(QColor(_resolve_bg(page)))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing, True)
    scene.render(painter, QRectF(0, 0, pw, ph), QRectF(0, 0, pw, ph))
    painter.end()
    return img


def save_page_png(page: PageSpec, path: str, *, style=None) -> None:
    render_page_to_image(page, style=style).save(path, "PNG")


def export_document_pdf(doc: DocumentSpec, path: str, dpi: int = 300) -> None:
    writer = QPdfWriter(path)
    writer.setResolution(dpi)
    painter = QPainter()
    started = False
    for page in doc.pages:
        pw, ph = page.page_size_px
        size_inches = QSizeF(pw / dpi, ph / dpi)
        # QPdfWriter contract: set page size/margins BEFORE begin() (first page) or newPage() (subsequent).
        writer.setPageSize(QPageSize(size_inches, QPageSize.Inch))
        writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Inch)
        if not started:
            painter.begin(writer)
            started = True
        else:
            writer.newPage()
        scene = build_scene(page, style=doc.style)
        target = painter.viewport()
        scene.render(painter, QRectF(target), QRectF(0, 0, pw, ph))
    if started:
        painter.end()
