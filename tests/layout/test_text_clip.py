from PySide6.QtWidgets import QGraphicsItem, QGraphicsSimpleTextItem
from core.layout.models import Region, PageSpec
from core.layout import qt_renderer


def test_text_is_child_of_a_clipping_path_item(qapp):
    page = PageSpec(page_size_px=(400, 200), regions=[
        Region(id="t", kind="text", bbox=(0, 0, 100, 40), text="Hello world")])
    scene = qt_renderer.build_scene(page)  # export path (selectable=False)
    texts = [it for it in scene.items() if isinstance(it, QGraphicsSimpleTextItem)]
    assert texts, "expected a text item"
    parent = texts[0].parentItem()
    assert parent is not None
    assert bool(parent.flags() & QGraphicsItem.ItemClipsChildrenToShape)


def test_guide_box_still_editor_only(qapp):
    from PySide6.QtWidgets import QGraphicsRectItem
    page = PageSpec(page_size_px=(400, 200), regions=[
        Region(id="t", kind="text", bbox=(0, 0, 100, 40), text="Hi")])
    editor = qt_renderer.build_scene(page, selectable=True)
    assert any(isinstance(it, QGraphicsRectItem) and it.data(0) == "t" for it in editor.items())
    export = qt_renderer.build_scene(page, selectable=False)
    assert not any(isinstance(it, QGraphicsRectItem) and it.data(0) == "t" for it in export.items())
