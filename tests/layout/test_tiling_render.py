from core.layout.models import PageSpec
from core.layout.tiling import grid, apply_tiling
from core.layout import qt_renderer


def test_tiled_page_renders_with_background_gutters(qapp):
    # 1x2 grid on a white page: the vertical gutter between the two panels must be background.
    page = PageSpec(page_size_px=(200, 100), background="#FFFFFF")
    apply_tiling(page, grid(1, 2), gutter=20, margin=10)
    img = qt_renderer.render_page_to_image(page)
    assert img.width() == 200 and img.height() == 100
    # center column (x=100) lies in the 20px gutter between the two panels -> background (white)
    gutter_px = img.pixelColor(100, 50)
    assert gutter_px.red() > 240 and gutter_px.green() > 240 and gutter_px.blue() > 240
    # a point inside the left panel (well left of the gutter) is within an (empty) image
    # placeholder frame, i.e. NOT the page background — the placeholder fill is grey.
    left_px = img.pixelColor(40, 50)
    assert not (left_px.red() > 240 and left_px.green() > 240 and left_px.blue() > 240)


def test_two_panels_present(qapp):
    page = PageSpec(page_size_px=(200, 100), background="#FFFFFF")
    apply_tiling(page, grid(1, 2), gutter=20, margin=10)
    assert len(page.regions) == 2
    for r in page.regions:
        assert r.shape == "path"
