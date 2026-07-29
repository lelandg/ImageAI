from PySide6.QtWidgets import QGraphicsPathItem

from core.layout.models import Overlay, PageSpec, PathSegment, TextStyle
from core.layout import qt_renderer


def _tp(y=200.0, peak=40.0):
    return [PathSegment(type="move", pts=[(50.0, y)]),
            PathSegment(type="quad", pts=[(200.0, y - 2 * peak), (350.0, y)])]


def _curved(text="CURVED TITLE", **kw):
    ts = kw.pop("text_style", TextStyle(family=["DejaVu Sans"], size_px=32,
                                        color="#000000", align="center"))
    return Overlay(id="c1", kind="caption", text=text, anchor=(200.0, 200.0),
                   text_path=_tp(), text_style=ts, **kw)


def _page(overlays):
    return PageSpec(page_size_px=(400, 400), regions=[], overlays=overlays)


def _path_items(scene):
    return [it for it in scene.items()
            if isinstance(it, QGraphicsPathItem) and it.data(0) == "c1"]


def test_curved_overlay_adds_single_path_item_no_body(qapp):
    scene = qt_renderer.build_scene(_page([_curved()]))
    items = _path_items(scene)
    assert len(items) == 1
    # No balloon body: the only other items would be body/_OverlayPathItem or text
    assert not any(isinstance(it, qt_renderer._OverlayPathItem) for it in scene.items())


def test_glyphs_follow_curve_above_chord(qapp):
    scene = qt_renderer.build_scene(_page([_curved()]))
    item = _path_items(scene)[0]
    r = item.path().boundingRect()
    # Peak is 40px above the chord at y=200; glyph tops must reach well above
    # the chord, and the path must span most of the curve horizontally.
    assert r.top() < 175.0
    assert r.width() > 150.0


def test_curved_text_renders_pixels_along_arc(qapp):
    img = qt_renderer.render_page_to_image(_page([_curved()]))
    # Sample mid-glyph above the arc baseline (baseline dips to y=160 at the
    # midpoint; a 32px font's glyph bodies sit roughly y 135-160) — must be inked.
    found_dark = False
    for dx in range(-30, 31, 5):
        c = img.pixelColor(200 + dx, 150)
        if c.lightness() < 200:
            found_dark = True
            break
    assert found_dark


def test_outline_pen_applied(qapp):
    ts = TextStyle(family=["DejaVu Sans"], size_px=32, color="#FFD700",
                   align="center", outline_px=3.0, outline_color="#331100")
    scene = qt_renderer.build_scene(_page([_curved(text_style=ts)]))
    item = _path_items(scene)[0]
    assert abs(item.pen().widthF() - 3.0) < 1e-6
    assert item.brush().color().name().lower() == "#ffd700"


def test_no_outline_means_no_pen(qapp):
    from PySide6.QtCore import Qt
    scene = qt_renderer.build_scene(_page([_curved()]))
    assert _path_items(scene)[0].pen().style() == Qt.NoPen


def test_rotation_applied_about_anchor(qapp):
    scene = qt_renderer.build_scene(_page([_curved(rotation=25.0)]))
    item = _path_items(scene)[0]
    assert abs(item.rotation() - 25.0) < 1e-6


def test_invalid_text_path_falls_back_to_straight_block(qapp, caplog):
    ov = _curved()
    ov.text_path = [PathSegment(type="move", pts=[(0.0, 0.0)])]  # invalid: no quad
    with caplog.at_level("WARNING"):
        scene = qt_renderer.build_scene(_page([ov]))
    # Falls through to the normal caption path -> a balloon body exists.
    assert any(isinstance(it, qt_renderer._OverlayPathItem) for it in scene.items())


def test_speech_kind_ignores_text_path(qapp):
    ov = Overlay(id="c1", kind="speech", text="hi", anchor=(200.0, 200.0),
                 text_path=_tp())
    scene = qt_renderer.build_scene(_page([ov]))
    assert any(isinstance(it, qt_renderer._OverlayPathItem) for it in scene.items())


def test_empty_text_adds_nothing_and_does_not_crash(qapp):
    scene = qt_renderer.build_scene(_page([_curved(text="")]))
    assert _path_items(scene) == []
