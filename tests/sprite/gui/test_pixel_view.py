from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest

from gui.sprite.pixel_view import (MAX_ZOOM, MIN_ZOOM, PixelView, checkerboard_brush,
                                   qimage_to_rgba)
from gui_synthetic import write_frame_png


def _image():
    image = QImage(4, 4, QImage.Format_RGBA8888)
    image.fill(QColor(0, 255, 0, 255))
    image.setPixelColor(1, 1, QColor(255, 0, 0, 255))
    return image


def test_set_image_from_path_and_qimage(qapp, tmp_path):
    view = PixelView()
    assert view.set_image(_image())
    assert view.image().width() == 4
    path = write_frame_png(tmp_path / "f.png", size=(6, 3))
    assert view.set_image(path)
    assert (view.image().width(), view.image().height()) == (6, 3)
    assert view.set_image(tmp_path / "missing.png") is False  # logged, previous image kept
    assert view.image().width() == 6


def test_zoom_is_integer_and_clamped(qapp):
    view = PixelView()
    view.set_image(_image())
    seen = []
    view.zoomChanged.connect(seen.append)
    view.set_zoom(4)
    assert view.zoom() == 4
    assert view.transform().m11() == 4 and view.transform().m22() == 4
    view.set_zoom(99)
    assert view.zoom() == MAX_ZOOM
    view.set_zoom(0)
    assert view.zoom() == MIN_ZOOM
    assert seen == [4, MAX_ZOOM, MIN_ZOOM]


def test_zoom_in_out_follow_steps(qapp):
    view = PixelView()
    view.set_image(_image())
    view.zoom_in()
    view.zoom_in()
    assert view.zoom() == 3
    view.zoom_out()
    assert view.zoom() == 2
    view.zoom_reset()
    assert view.zoom() == 1
    view.set_zoom(5)          # between steps
    view.zoom_in()
    assert view.zoom() == 6   # next step up
    view.zoom_out()
    assert view.zoom() == 4   # next step down


def test_pixmap_item_uses_nearest_neighbor(qapp):
    from PySide6.QtGui import QPainter
    view = PixelView()
    view.set_image(_image())
    assert view._item.transformationMode() == Qt.FastTransformation
    assert not (view.renderHints() & QPainter.SmoothPixmapTransform)


def test_grid_toggle(qapp):
    view = PixelView()
    got = []
    view.gridToggled.connect(got.append)
    assert view.grid_visible() is True
    assert view.toggle_grid() is False
    assert view.grid_visible() is False
    assert got == [False]


def test_color_at_returns_hex_or_none(qapp):
    view = PixelView()
    view.set_image(_image())
    assert view.color_at(1, 1) == "#FF0000"
    assert view.color_at(0, 0) == "#00FF00"
    assert view.color_at(4, 0) is None
    assert view.color_at(-1, 0) is None


def test_click_in_pick_mode_emits_color_and_leaves_pick_mode(qapp):
    view = PixelView()
    view.resize(160, 160)
    view.show()
    view.set_image(_image())
    view.set_zoom(8)
    qapp.processEvents()
    view.set_pick_mode(True)
    got = []
    view.colorPicked.connect(got.append)
    pos = view.mapFromScene(QPointF(1.5, 1.5))
    QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier, pos)
    assert got == ["#FF0000"]
    assert view.pick_mode() is False


def test_drag_in_select_mode_sets_selection_rect(qapp):
    view = PixelView()
    view.resize(160, 160)
    view.show()
    view.set_image(_image())
    view.set_zoom(8)
    qapp.processEvents()
    view.set_select_mode(True)
    got = []
    view.selectionChanged.connect(got.append)
    start = view.mapFromScene(QPointF(0.5, 0.5))
    end = view.mapFromScene(QPointF(2.5, 3.5))
    QTest.mousePress(view.viewport(), Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseRelease(view.viewport(), Qt.LeftButton, Qt.NoModifier, end)
    assert view.selection_rect() == (0, 0, 3, 4)
    assert got[-1] == (0, 0, 3, 4)
    assert view.select_mode() is False
    view.clear_selection()
    assert view.selection_rect() is None
    assert got[-1] is None
    view.set_selection_rect((1, 1, 9, 9))  # clamped to the 4x4 image
    assert view.selection_rect() == (1, 1, 3, 3)
    view.set_selection_rect((7, 7, 2, 2))  # fully outside -> cleared
    assert view.selection_rect() is None


def test_qimage_to_rgba_shape_and_values(qapp):
    arr = qimage_to_rgba(_image())
    assert arr.shape == (4, 4, 4)
    assert tuple(arr[1, 1]) == (255, 0, 0, 255)
    assert tuple(arr[0, 0]) == (0, 255, 0, 255)


def test_checkerboard_brush_is_textured(qapp):
    brush = checkerboard_brush(4)
    assert brush.style() == Qt.TexturePattern
    assert brush.texture().width() == 8


def test_fit_zoom_shortcuts_never_reverse_direction(qapp):
    view = PixelView()
    view.resize(400, 300)
    view.show()
    view.set_auto_fit(True)
    view.set_image(QImage(1600, 1200, QImage.Format_RGBA8888))
    qapp.processEvents()
    small = view.zoom()
    assert small < MIN_ZOOM
    view.zoom_out()
    assert view.zoom() <= small
    view.zoom_in()
    assert view.zoom() > small
    view.set_auto_fit(True)
    view.set_image(_image())
    large = view.zoom()
    assert large > MAX_ZOOM
    view.zoom_in()
    assert view.zoom() >= large
    view.zoom_out()
    assert view.zoom() < large
    view.close()
