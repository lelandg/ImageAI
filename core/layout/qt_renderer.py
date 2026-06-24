"""Native Qt renderer: PageSpec -> QGraphicsScene -> QImage/PNG (source of truth)."""
from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsRectItem, QGraphicsPolygonItem,
    QGraphicsSimpleTextItem, QGraphicsItem, QGraphicsPixmapItem,
)
from PySide6.QtGui import (
    QColor, QBrush, QPen, QPolygonF, QImage, QPainter, QFont, QPixmap,
)
from PySide6.QtCore import QPointF, QRectF, Qt

from core.layout.models import PageSpec, Region

_PLACEHOLDER_FILL = QColor("#E9ECEF")
_PLACEHOLDER_PEN = QColor("#ADB5BD")


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


def _add_text_region(scene: QGraphicsScene, r: Region, selectable: bool) -> None:
    x, y, w, h = r.bbox
    box = QGraphicsRectItem(QRectF(x, y, w, h))
    box.setBrush(QBrush(Qt.transparent))
    box.setPen(QPen(QColor("#CED4DA"), 1, Qt.DashLine))
    _apply_flags(box, selectable, r.id)
    scene.addItem(box)

    text = QGraphicsSimpleTextItem(r.text or "")
    style = r.text_style
    font = QFont()
    if style:
        if style.family:
            font.setFamily(style.family[0])
        if style.size_px:
            font.setPixelSize(style.size_px)
        font.setBold(style.weight in ("bold", "black", "semibold"))
        font.setItalic(style.italic)
        text.setBrush(QBrush(QColor(style.color)))
    text.setFont(font)
    text.setPos(x + 2, y + 2)
    scene.addItem(text)


def build_scene(page: PageSpec, *, selectable: bool = False) -> QGraphicsScene:
    pw, ph = page.page_size_px
    scene = QGraphicsScene(0, 0, pw, ph)
    bg = page.background if (page.background and page.background.startswith("#")) else "#FFFFFF"
    scene.setBackgroundBrush(QBrush(QColor(bg)))
    for r in sorted(page.regions, key=lambda rr: rr.z):
        if r.kind == "image":
            _add_image_region(scene, r, selectable)
        else:
            _add_text_region(scene, r, selectable)
    return scene


def render_page_to_image(page: PageSpec) -> QImage:
    pw, ph = page.page_size_px
    scene = build_scene(page)
    img = QImage(pw, ph, QImage.Format_ARGB32)
    bg = page.background if (page.background and page.background.startswith("#")) else "#FFFFFF"
    img.fill(QColor(bg))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing, True)
    scene.render(painter, QRectF(0, 0, pw, ph), QRectF(0, 0, pw, ph))
    painter.end()
    return img


def save_page_png(page: PageSpec, path: str) -> None:
    render_page_to_image(page).save(path, "PNG")
