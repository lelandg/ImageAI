"""Native Qt renderer: PageSpec -> QGraphicsScene -> QImage/PNG (source of truth)."""
from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsRectItem,
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


def segments_to_painter_path(segments) -> QPainterPath:
    """Convert a list of PathSegment objects into a QPainterPath.

    Extracted from ``region_to_painter_path`` so overlays can reuse the same
    move/line/quad/cubic/close switch without going through a Region wrapper.
    """
    path = QPainterPath()
    for seg in segments:
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
    return path


def region_to_painter_path(r: Region) -> QPainterPath:
    """Build a QPainterPath for a region (rect | polygon | path).

    Invalid path segments are logged and the region falls back to its bbox
    rectangle, so a region never renders as nothing.
    """
    path = QPainterPath()
    if r.shape == "path":
        if not r.segments:
            logger.warning("Region %s has shape='path' but no segments; falling back to bbox", r.id)
        else:
            issues = validate_segments(r.segments)
            if issues:
                logger.error("Region %s has invalid path segments; falling back to bbox: %s",
                             r.id, "; ".join(issues))
            else:
                path = segments_to_painter_path(r.segments)
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
    """Persist a drag into the bound region's geometry.

    Handles carry their geometry in item-local coords with the item at scene
    (0,0), so a drag shows up purely as ``item.pos()`` — the delta to apply to
    the region's original geometry. For ``shape="path"`` regions the delta is
    applied to ``segments`` (the geometry the renderer reads); rect/polygon
    regions translate ``bbox`` and ``points``.
    """
    region = getattr(item, "_region", None)
    if region is None:
        return
    dx, dy = item.x(), item.y()
    bx, by, bw, bh = item._base_bbox
    if region.shape == "path" and getattr(item, "_base_segments", None):
        from core.layout.geometry import translate_segments
        region.segments = translate_segments(item._base_segments, dx, dy)
        region.bbox = (round(bx + dx), round(by + dy), bw, bh)
        return
    region.bbox = (round(bx + dx), round(by + dy), bw, bh)
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
        self._base_segments = list(region.segments)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            _writeback_move(self)
        return super().itemChange(change, value)


class _RegionRectItem(_RegionMoveMixin, QGraphicsRectItem):
    def __init__(self, rect: QRectF, region: Region):
        super().__init__(rect)
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

    # Editor-only dashed guide box doubles as the region's selectable/movable
    # handle; export paths (selectable=False) omit it.
    box = None
    if selectable:
        box = _RegionRectItem(QRectF(x, y, w, h), r)
        box.setBrush(QBrush(Qt.transparent))
        pen = QPen(_TEXT_GUIDE_PEN, 1.5, Qt.DashLine)
        pen.setCosmetic(True)
        box.setPen(pen)
        _apply_flags(box, selectable, r.id, movable=(selectable and not locked))
        scene.addItem(box)

    # Clip item: text is parented here so it cannot spill past the panel shape.
    # When a guide box exists, the clip rides under it so a drag moves both.
    clip = _RegionPathItem(region_to_painter_path(r), r)
    clip.setPen(QPen(Qt.NoPen))
    clip.setBrush(QBrush(Qt.transparent))
    clip.setFlag(QGraphicsItem.ItemClipsChildrenToShape, True)
    if box is not None:
        clip.setParentItem(box)
    else:
        scene.addItem(clip)

    text = QGraphicsSimpleTextItem(r.text or "")
    ts = effective_text_style(r, project_style)
    font = QFont()
    if ts:
        if ts.family:
            font.setFamily(ts.family[0])
        font.setBold(ts.weight in ("bold", "black", "semibold"))
        font.setItalic(ts.italic)
        text.setBrush(QBrush(QColor(ts.color)))
    font.setPixelSize(ts.size_px if ts and ts.size_px else _DEFAULT_TEXT_PX)
    text.setFont(font)
    text.setParentItem(clip)
    text.setPos(x + 2, y + 2)


class _OverlayPathItem(QGraphicsPathItem):
    """A QGraphicsPathItem whose shape() returns the FILLED interior.

    The default QGraphicsPathItem.shape() returns the pen-stroked outline, which
    causes ItemClipsChildrenToShape to clip children (the text item) to a thin
    ring — making text invisible. Overriding shape() to return self.path()
    (the filled region) matches what _RegionPathItem does for region children.
    """

    def shape(self):
        return self.path()


class _OverlayStyleable:
    """Minimal adapter exposing .text_style and .role for effective_text_style."""
    __slots__ = ("text_style", "role")

    def __init__(self, text_style, role):
        self.text_style = text_style
        self.role = role


def _overlay_as_styleable(ov, role):
    return _OverlayStyleable(ov.text_style, role)


def _add_overlay(scene: QGraphicsScene, ov, project_style, base_z: float) -> None:
    """Measure wrapped text, build balloon body+tail, add body and text to scene.

    Resolution 2 applied: body is _OverlayPathItem (overrides shape() to filled
    interior so text children are NOT clipped to a thin stroked ring).
    SFX overlays have no body (overlay_to_segments returns []) — text added directly.
    """
    from PySide6.QtCore import Qt, QRectF
    from PySide6.QtGui import QFont, QColor, QPen, QBrush, QFontMetricsF
    from PySide6.QtWidgets import QGraphicsTextItem
    from core.layout.balloons import overlay_to_segments

    # Resolve role: explicit > kind-default > "dialogue"
    role = ov.role or {
        "speech": "dialogue", "thought": "dialogue",
        "caption": "caption", "sfx": "sfx",
    }.get(ov.kind, "dialogue")
    ts = effective_text_style(_overlay_as_styleable(ov, role), project_style)

    # Build font from resolved text style — size via setPixelSize (PIXELS),
    # matching _add_text_region so overlay and region text render at the same scale.
    font = QFont()
    font.setFamily(ts.family[0] if ts and ts.family else "DejaVu Sans")
    font.setPixelSize(ts.size_px if ts and ts.size_px else 16)
    if ts and ts.italic:
        font.setItalic(True)

    # Measure wrapped text to size the body
    fm = QFontMetricsF(font)
    max_w = max(20.0, ov.style.max_width_px)
    rect = fm.boundingRect(QRectF(0, 0, max_w, 100000),
                           int(Qt.TextWordWrap), ov.text)
    text_w, text_h = rect.width(), rect.height()
    pad = ov.style.padding_px
    inner_w = text_w + 2 * pad
    inner_h = text_h + 2 * pad

    # Anchor body: center or topleft
    ax, ay = ov.anchor
    if ov.anchor_mode == "center":
        ix, iy = ax - inner_w / 2.0, ay - inner_h / 2.0
    else:
        ix, iy = ax, ay
    inner = (ix, iy, inner_w, inner_h)

    z = base_z + ov.z

    # Build body geometry via balloons
    segs = overlay_to_segments(ov.kind, inner, ov.tail_target, ov.style)
    body_item = None
    if segs:
        path = segments_to_painter_path(segs)
        body_item = _OverlayPathItem(path)
        body_item.setBrush(QBrush(QColor(ov.style.fill)))
        if ov.style.stroke_px > 0:
            body_item.setPen(QPen(QColor(ov.style.stroke_color), ov.style.stroke_px))
        else:
            body_item.setPen(QPen(Qt.NoPen))
        body_item.setZValue(z)
        body_item.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemClipsChildrenToShape, True)
        scene.addItem(body_item)

    # Text item: child of body (clipped) or direct scene item (sfx, no body)
    text_item = QGraphicsTextItem(ov.text, parent=body_item)
    text_item.setFont(font)
    if ts and ts.color:
        text_item.setDefaultTextColor(QColor(ts.color))
    text_item.setTextWidth(text_w)
    # body item lives at scene origin (path holds page-space verts), so the
    # text's parent-relative pos equals its scene pos.
    text_item.setPos(ix + pad, iy + pad)
    text_item.setZValue(z + 0.1)
    if body_item is None:  # sfx: no body, add text directly to scene
        scene.addItem(text_item)

    # Rotation: spin the body (text rides along as its child) or, for SFX with no
    # body, the text item — both about the overlay anchor (scene coords).
    rot = getattr(ov, "rotation", 0.0) or 0.0
    if rot:
        from PySide6.QtCore import QPointF
        if body_item is not None:
            body_item.setTransformOriginPoint(QPointF(ax, ay))  # body sits at scene origin
            body_item.setRotation(rot)
        else:
            text_item.setTransformOriginPoint(
                QPointF(ax - text_item.x(), ay - text_item.y()))
            text_item.setRotation(rot)


def build_scene(page: PageSpec, *, selectable: bool = False, style=None,
                locked: bool = True, region_filter=None,
                include_overlays: bool = True) -> QGraphicsScene:
    pw, ph = page.page_size_px
    scene = QGraphicsScene(0, 0, pw, ph)
    scene.setBackgroundBrush(QBrush(QColor(_resolve_bg(page))))
    regions = page.regions if region_filter is None else [r for r in page.regions if region_filter(r)]
    for r in sorted(regions, key=lambda rr: rr.z):
        if r.kind == "image":
            _add_image_region(scene, r, selectable, locked=locked)
        else:
            _add_text_region(scene, r, selectable, project_style=style, locked=locked)
    # Overlay pass: render after all regions so overlays sit on top.
    # Gated on include_overlays to avoid double-rendering in the bleed path
    # (Resolution 1): overlays live in page/trim coords and render with the
    # non-bleed scene only.
    if include_overlays and page.overlays:
        base_z = max((r.z for r in page.regions), default=0) + 1000
        for ov in sorted(page.overlays, key=lambda o: o.z):
            _add_overlay(scene, ov, style, base_z)
    return scene


def render_page_to_image(page: PageSpec, *, style=None) -> QImage:
    pw, ph = page.page_size_px
    b = max(0, int(getattr(page, "bleed_px", 0) or 0))
    cw, ch = pw + 2 * b, ph + 2 * b
    img = QImage(cw, ch, QImage.Format_ARGB32)
    img.fill(QColor(_resolve_bg(page)))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing, True)
    if b == 0:
        scene = build_scene(page, style=style)
        scene.render(painter, QRectF(0, 0, pw, ph), QRectF(0, 0, pw, ph))
        painter.end()
        return img
    # Non-bleed regions are clipped to the trim box, offset into the bleed canvas.
    painter.save()
    painter.setClipRect(QRectF(b, b, pw, ph))
    non_bleed = build_scene(page, style=style, region_filter=lambda r: not r.bleed)
    non_bleed.render(painter, QRectF(b, b, pw, ph), QRectF(0, 0, pw, ph))
    painter.restore()
    # Bleed regions may extend into the surrounding margin: map the full bleed box
    # in scene coords onto the whole canvas.  Use a transparent background so the
    # bleed scene does not paint over the already-rendered trim content.
    # include_overlays=False: overlays live in trim coords and were already rendered
    # with the non-bleed scene above (Resolution 1 — avoids double-rendering).
    bleed_scene = build_scene(page, style=style, region_filter=lambda r: r.bleed,
                              include_overlays=False)
    bleed_scene.setBackgroundBrush(Qt.transparent)
    bleed_scene.render(painter, QRectF(0, 0, cw, ch), QRectF(-b, -b, cw, ch))
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
