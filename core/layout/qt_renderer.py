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

_PLACEHOLDER_FILL = QColor("#E9ECEF")
_PLACEHOLDER_PEN = QColor("#ADB5BD")


def _resolve_bg(page: PageSpec) -> str:
    """Resolve a page background to a hex color.

    Image-path backgrounds are deferred to a later phase; until then a
    non-hex background renders as white in every render path (editor, PNG,
    PDF), keeping them consistent.
    """
    if page.background and page.background.startswith("#"):
        return page.background
    return "#FFFFFF"


def _apply_flags(item: QGraphicsItem, selectable: bool, region_id: str) -> None:
    item.setData(0, region_id)
    if selectable:
        item.setFlag(QGraphicsItem.ItemIsSelectable, True)
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
            pi.setData(0, r.id)
            scene.addItem(pi)
            return

    label = QGraphicsSimpleTextItem(r.name or "[image]")
    label.setPos(x + 4, y + 4)
    label.setBrush(QBrush(QColor("#6C757D")))
    scene.addItem(label)


def _add_text_region(scene: QGraphicsScene, r: Region, selectable: bool, project_style=None) -> None:
    x, y, w, h = r.bbox
    box = QGraphicsRectItem(QRectF(x, y, w, h))
    box.setBrush(QBrush(Qt.transparent))
    box.setPen(QPen(QColor("#CED4DA"), 1, Qt.DashLine))
    _apply_flags(box, selectable, r.id)
    scene.addItem(box)

    text = QGraphicsSimpleTextItem(r.text or "")
    ts = r.text_style
    if ts is None and project_style is not None:
        role = r.role or project_style.default_text_role
        ts = project_style.font_roles.get(role)
    font = QFont()
    if ts:
        if ts.family:
            font.setFamily(ts.family[0])
        if ts.size_px:
            font.setPixelSize(ts.size_px)
        font.setBold(ts.weight in ("bold", "black", "semibold"))
        font.setItalic(ts.italic)
        text.setBrush(QBrush(QColor(ts.color)))
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
