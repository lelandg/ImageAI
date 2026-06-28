"""Renderer overlay pass: smoke tests for Task 6 (measure -> balloons -> draw).

Full pixel-level assertions live in Task 7; these tests verify:
  1. A speech overlay with a filled+stroked body produces visible dark stroke pixels.
  2. Multiple overlay kinds (caption, sfx) render without error.
"""
from core.layout.models import PageSpec, Overlay, OverlayStyle
from core.layout import qt_renderer


def qt_renderer_pixel_is_dark(img, x, y):
    c = img.pixelColor(x, y)
    return c.red() < 80 and c.green() < 80 and c.blue() < 80


def test_speech_overlay_renders_body_and_text(qapp):
    page = PageSpec(page_size_px=(200, 160), background="#FFFFFF")
    page.overlays.append(Overlay(
        id="b1", kind="speech", text="Hello there friend",
        anchor=(100.0, 70.0), tail_target=(100.0, 150.0),
        style=OverlayStyle(fill="#FFFFFF", stroke_px=3.0, stroke_color="#000000")))
    img = qt_renderer.render_page_to_image(page)
    assert img.width() == 200 and img.height() == 160
    # a black stroked outline pixel exists somewhere on the body perimeter
    found_stroke = any(
        qt_renderer_pixel_is_dark(img, x, y)
        for x in range(40, 160) for y in range(40, 110)
    )
    assert found_stroke


def test_overlays_render_count_and_kinds(qapp):
    page = PageSpec(page_size_px=(200, 200), background="#FFFFFF")
    page.overlays.append(Overlay(id="cap", kind="caption", text="Narration",
                                 anchor=(10.0, 10.0), anchor_mode="topleft"))
    page.overlays.append(Overlay(id="sfx", kind="sfx", text="BOOM", anchor=(120.0, 120.0)))
    img = qt_renderer.render_page_to_image(page)
    assert img.width() == 200 and img.height() == 200  # renders without error


def _is_white(img, x, y):
    c = img.pixelColor(x, y)
    return c.red() > 240 and c.green() > 240 and c.blue() > 240


def test_speech_body_fill_and_background(qapp):
    # blue page so the white balloon fill is unambiguous
    page = PageSpec(page_size_px=(220, 180), background="#1144CC")
    page.overlays.append(Overlay(
        id="b", kind="speech", text="Hello there friend, how are you",
        anchor=(110.0, 70.0), tail_target=(110.0, 165.0),
        style=OverlayStyle(fill="#FFFFFF", stroke_px=3.0)))
    img = qt_renderer.render_page_to_image(page)
    assert _is_white(img, 110, 70)              # inside the balloon body -> white fill
    assert not _is_white(img, 5, 5)             # page corner -> blue background
    # tail extends downward toward the target (a non-background pixel below the body)
    assert any(not (img.pixelColor(110, y).blue() > 200 and img.pixelColor(110, y).red() < 80)
               for y in range(110, 160))


def test_overlay_z_order_higher_on_top(qapp):
    page = PageSpec(page_size_px=(200, 200), background="#FFFFFF")
    page.overlays.append(Overlay(id="low", kind="caption", text="LOW",
                                 anchor=(60.0, 60.0), anchor_mode="topleft", z=0,
                                 style=OverlayStyle(fill="#FF0000")))
    page.overlays.append(Overlay(id="high", kind="caption", text="HIGH",
                                 anchor=(70.0, 70.0), anchor_mode="topleft", z=5,
                                 style=OverlayStyle(fill="#00AA00")))
    img = qt_renderer.render_page_to_image(page)
    # in the overlap region the higher-z (green) overlay wins
    c = img.pixelColor(95, 95)
    assert c.green() > c.red()


def test_caption_and_sfx_render(qapp):
    page = PageSpec(page_size_px=(200, 120), background="#FFFFFF")
    page.overlays.append(Overlay(id="cap", kind="caption", text="Meanwhile...",
                                 anchor=(8.0, 8.0), anchor_mode="topleft",
                                 style=OverlayStyle(fill="#FFFFAA")))
    page.overlays.append(Overlay(id="sfx", kind="sfx", text="KRAK", anchor=(150.0, 60.0)))
    img = qt_renderer.render_page_to_image(page)
    # caption box has its yellow fill
    c = img.pixelColor(20, 20)
    assert c.red() > 200 and c.green() > 200 and c.blue() < 200
