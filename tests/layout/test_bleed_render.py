from PySide6.QtGui import QImage
from PySide6.QtCore import Qt
from core.layout.models import Region, PageSpec
from core.layout import qt_renderer


def _solid_png(tmp_path, color, size=(200, 60)):
    im = QImage(size[0], size[1], QImage.Format_RGB32)
    im.fill(color)
    p = tmp_path / "ref.png"
    assert im.save(str(p))
    return str(p)


def test_canvas_grows_by_bleed(qapp):
    page = PageSpec(page_size_px=(200, 150), bleed_px=20, background="#FFFFFF")
    img = qt_renderer.render_page_to_image(page)
    assert img.width() == 240 and img.height() == 190


def test_bleed_region_paints_into_margin(qapp, tmp_path):
    ref = _solid_png(tmp_path, Qt.red)
    # geometry spans y in [-20, 20] (into the top bleed) across the full width
    page = PageSpec(page_size_px=(200, 150), bleed_px=20, background="#FFFFFF", regions=[
        Region(id="b", kind="image", bbox=(0, -20, 200, 40), image_ref=ref, bleed=True)])
    img = qt_renderer.render_page_to_image(page)
    # device (100, 5) is inside the top bleed band [0,20)
    c = img.pixelColor(100, 5)
    assert c.red() > 200 and c.green() < 80


def test_non_bleed_region_is_clipped_at_trim(qapp, tmp_path):
    ref = _solid_png(tmp_path, Qt.red)
    page = PageSpec(page_size_px=(200, 150), bleed_px=20, background="#FFFFFF", regions=[
        Region(id="n", kind="image", bbox=(0, -20, 200, 40), image_ref=ref, bleed=False)])
    img = qt_renderer.render_page_to_image(page)
    margin = img.pixelColor(100, 5)    # top bleed band -> clipped away -> bg
    inside = img.pixelColor(100, 25)   # within trim (device y >= 20) -> red
    assert margin.red() > 200 and margin.green() > 200
    assert inside.red() > 200 and inside.green() < 80
