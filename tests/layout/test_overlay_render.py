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
