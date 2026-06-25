"""Native Qt renderer: PageSpec -> QGraphicsScene -> QImage/PNG (source of truth)."""
from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsRectItem, QGraphicsPolygonItem,
    QGraphicsSimpleTextItem, QGraphicsItem, QGraphicsPixmapItem,
)
from PySide6.QtGui import (
    QColor, QBrush, QPen, QPolygonF, QImage, QPainter, QFont, QPixmap,
    QPdfWriter, QPageSize, QPageLayout,
)
from PySide6.QtCore import QPointF, QRectF, Qt, QSizeF, QMarginsF

from core.layout.models import PageSpec, Region, DocumentSpec
from core.layout.styles import effective_text_style

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


def _apply_flags(item: QGraphicsItem, selectable: bool, region_id: str,
                 *, movable: bool = True) -> None:
    item.setData(0, region_id)
    if selectable:
        item.setFlag(QGraphicsItem.ItemIsSelectable, True)
        if movable:
            item.setFlag(QGraphicsItem.ItemIsMovable, True)


def _add_image_region(scene: QGraphicsScene, r: Region, selectable: bool) -> None:
    x, y, w, h = r.bbox
    if r.shape == "polygon" and r.points:
        poly = QPolygonF([QPointF(px, py) for px, py in r.points])
        item = QGraphicsPolygonItem(poly)
    else:
        item = QGraphicsRectItem(QRectF(x, y, w, h))
    item.setBrush(QBrush(_PLACEHOLDER_FILL))
    item.setPen(QPen(_PLACEHOLDER_PEN, 1))
    _apply_flags(item, selectable, r.id)
    scene.addItem(item)

    if r.image_ref:
        pix = QPixmap(r.image_ref)
        if not pix.isNull():
            scaled = pix.scaled(int(w), int(h), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pi = QGraphicsPixmapItem(scaled)
            pi.setPos(x, y)
            # Selectable so a filled image can be re-picked, but not movable —
            # it sits on top of the (movable) placeholder rect and shouldn't be
            # dragged off it.
            _apply_flags(pi, selectable, r.id, movable=False)
            scene.addItem(pi)
            return

    label = QGraphicsSimpleTextItem(r.name or "[image]")
    label.setPos(x + 4, y + 4)
    label.setBrush(QBrush(QColor("#6C757D")))
    scene.addItem(label)


def _add_text_region(scene: QGraphicsScene, r: Region, selectable: bool, project_style=None) -> None:
    x, y, w, h = r.bbox
    # The dashed guide box is an editor-only affordance (it's also the region's
    # selectable/movable handle). Export paths call build_scene(selectable=False),
    # so skipping it there keeps the guides out of the rendered PNG/PDF.
    if selectable:
        box = QGraphicsRectItem(QRectF(x, y, w, h))
        box.setBrush(QBrush(Qt.transparent))
        pen = QPen(_TEXT_GUIDE_PEN, 1.5, Qt.DashLine)
        pen.setCosmetic(True)  # constant on-screen width at any zoom -> always visible
        box.setPen(pen)
        _apply_flags(box, selectable, r.id)
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
    text.setPos(x + 2, y + 2)
    scene.addItem(text)


def build_scene(page: PageSpec, *, selectable: bool = False, style=None) -> QGraphicsScene:
    pw, ph = page.page_size_px
    scene = QGraphicsScene(0, 0, pw, ph)
    scene.setBackgroundBrush(QBrush(QColor(_resolve_bg(page))))
    for r in sorted(page.regions, key=lambda rr: rr.z):
        if r.kind == "image":
            _add_image_region(scene, r, selectable)
        else:
            _add_text_region(scene, r, selectable, project_style=style)
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
