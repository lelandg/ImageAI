from PySide6.QtGui import QImage
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem
from PySide6.QtCore import Qt

from core.layout.models import Region, PageSpec, PathSegment, ImageStyle
from core.layout import qt_renderer


def _solid_png(tmp_path, color, name="src.png", size=(80, 80)):
    im = QImage(size[0], size[1], QImage.Format_RGB32)
    im.fill(color)
    p = tmp_path / name
    assert im.save(str(p))
    return str(p)


def _triangle_segments():
    # apex at bottom-center, wide top edge; bbox (100,10,90,80)
    return [PathSegment(type="move", pts=[(100.0, 10.0)]),
            PathSegment(type="line", pts=[(190.0, 10.0)]),
            PathSegment(type="line", pts=[(145.0, 90.0)]),
            PathSegment(type="close", pts=[])]


def test_image_is_clipped_to_triangle(qapp, tmp_path):
    ref = _solid_png(tmp_path, Qt.red, size=(90, 80))
    page = PageSpec(page_size_px=(200, 150), background="#FFFFFF", regions=[
        Region(id="t", kind="image", shape="path", segments=_triangle_segments(),
               bbox=(100, 10, 90, 80), image_ref=ref)])
    img = qt_renderer.render_page_to_image(page)
    inside = img.pixelColor(145, 30)     # near top-center of triangle
    outside = img.pixelColor(105, 85)    # bbox corner OUTSIDE the triangle
    assert inside.red() > 200 and inside.green() < 80      # red image
    assert outside.red() > 200 and outside.green() > 200   # white page bg (clipped away)


def test_concave_notch_is_background(qapp, tmp_path):
    ref = _solid_png(tmp_path, Qt.red, size=(100, 100))
    # L-shape (concave): outer 0..100 square with a notch cut out of the top-right
    segs = [PathSegment(type="move", pts=[(0.0, 0.0)]),
            PathSegment(type="line", pts=[(50.0, 0.0)]),
            PathSegment(type="line", pts=[(50.0, 50.0)]),
            PathSegment(type="line", pts=[(100.0, 50.0)]),
            PathSegment(type="line", pts=[(100.0, 100.0)]),
            PathSegment(type="line", pts=[(0.0, 100.0)]),
            PathSegment(type="close", pts=[])]
    page = PageSpec(page_size_px=(120, 120), background="#FFFFFF", regions=[
        Region(id="L", kind="image", shape="path", segments=segs,
               bbox=(0, 0, 100, 100), image_ref=ref)])
    img = qt_renderer.render_page_to_image(page)
    notch = img.pixelColor(75, 25)   # inside bbox, inside the removed notch
    body = img.pixelColor(25, 25)    # solid part of the L
    assert notch.red() > 200 and notch.green() > 200   # background
    assert body.red() > 200 and body.green() < 80      # red image


def test_borderless_when_stroke_zero(qapp, tmp_path):
    page = PageSpec(page_size_px=(200, 150), regions=[
        Region(id="e", kind="image", bbox=(10, 10, 80, 80),
               image_style=ImageStyle(stroke_px=0))])
    scene = qt_renderer.build_scene(page)
    frame = [it for it in scene.items()
             if it.data(0) == "e" and hasattr(it, "path")][0]
    assert frame.pen().style() == Qt.NoPen


def test_stroke_pen_when_stroke_positive(qapp):
    page = PageSpec(page_size_px=(200, 150), regions=[
        Region(id="e", kind="image", bbox=(10, 10, 80, 80),
               image_style=ImageStyle(stroke_px=4, stroke_color="#FF0000"))])
    scene = qt_renderer.build_scene(page)
    frame = [it for it in scene.items()
             if it.data(0) == "e" and hasattr(it, "path")][0]
    assert frame.pen().widthF() == 4
    assert frame.pen().color().red() == 255


def test_filled_image_region_still_selectable(qapp, tmp_path):
    ref = _solid_png(tmp_path, Qt.white)
    page = PageSpec(page_size_px=(200, 150), regions=[
        Region(id="img1", kind="image", bbox=(10, 10, 80, 80), image_ref=ref)])
    scene = qt_renderer.build_scene(page, selectable=True)
    pix = [it for it in scene.items() if isinstance(it, QGraphicsPixmapItem)]
    assert pix and (pix[0].flags() & QGraphicsItem.ItemIsSelectable)
    assert pix[0].data(0) == "img1"
