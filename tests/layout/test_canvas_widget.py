from core.layout.models import Region, PageSpec
from gui.layout.canvas_widget import CanvasWidget


def _page():
    return PageSpec(page_size_px=(300, 200), regions=[
        Region(id="a", kind="image", bbox=(10, 10, 80, 80)),
        Region(id="b", kind="text", bbox=(10, 100, 200, 40), text="Hi"),
    ])


def test_load_page_builds_selectable_scene(qapp):
    w = CanvasWidget()
    w.load_page(_page())
    from PySide6.QtWidgets import QGraphicsItem
    sel = [it for it in w.scene().items()
           if it.flags() & QGraphicsItem.ItemIsSelectable]
    assert len(sel) >= 2


def test_selection_emits_region_id(qapp):
    w = CanvasWidget()
    w.load_page(_page())
    got = []
    w.regionSelected.connect(lambda rid: got.append(rid))
    # select the first selectable item programmatically
    from PySide6.QtWidgets import QGraphicsItem
    item = next(it for it in w.scene().items()
                if it.flags() & QGraphicsItem.ItemIsSelectable and it.data(0) == "a")
    item.setSelected(True)
    assert got and got[-1] == "a"
