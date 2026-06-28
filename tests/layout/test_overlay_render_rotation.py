from core.layout.models import PageSpec, Overlay
from core.layout import qt_renderer


def _page(overlays):
    return PageSpec(page_size_px=(400, 400), regions=[], overlays=overlays)


def test_sfx_overlay_rotation_applied(qapp):
    ov = Overlay(id="s", kind="sfx", text="POW", anchor=(200.0, 200.0), rotation=30.0)
    scene = qt_renderer.build_scene(_page([ov]))
    rots = [it.rotation() for it in scene.items() if hasattr(it, "rotation")]
    assert any(abs(r - 30.0) < 1e-6 for r in rots)


def test_speech_overlay_rotation_applied(qapp):
    ov = Overlay(id="b", kind="speech", text="hi", anchor=(200.0, 200.0), rotation=45.0)
    scene = qt_renderer.build_scene(_page([ov]))
    rots = [it.rotation() for it in scene.items() if hasattr(it, "rotation")]
    assert any(abs(r - 45.0) < 1e-6 for r in rots)


def test_zero_rotation_no_transform(qapp):
    ov = Overlay(id="b", kind="speech", text="hi", anchor=(200.0, 200.0))
    scene = qt_renderer.build_scene(_page([ov]))
    rots = [it.rotation() for it in scene.items() if hasattr(it, "rotation")]
    assert all(abs(r) < 1e-6 for r in rots)
