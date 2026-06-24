import pytest
from core.layout.models import Region, PageSpec
from core.layout import qt_renderer


def _page():
    return PageSpec(page_size_px=(200, 150), background="#FFFFFF", regions=[
        Region(id="r1", kind="image", bbox=(10, 10, 80, 80)),
        Region(id="r2", kind="text", bbox=(10, 100, 180, 40), text="Hello"),
        Region(id="r3", kind="image", shape="polygon",
               points=[(100, 10), (190, 10), (145, 90)]),
    ])


def test_build_scene_item_count(qapp):
    scene = qt_renderer.build_scene(_page())
    # at least one graphics item per region
    assert len(scene.items()) >= 3
    assert scene.width() == 200 and scene.height() == 150


def test_build_scene_selectable_flag(qapp):
    from PySide6.QtWidgets import QGraphicsItem
    scene = qt_renderer.build_scene(_page(), selectable=True)
    selectable = [it for it in scene.items()
                  if it.flags() & QGraphicsItem.ItemIsSelectable]
    assert len(selectable) >= 3


def test_render_page_to_image_size(qapp):
    img = qt_renderer.render_page_to_image(_page())
    assert img.width() == 200 and img.height() == 150
    assert not img.isNull()


def test_save_png(qapp, tmp_path):
    out = tmp_path / "page.png"
    qt_renderer.save_page_png(_page(), str(out))
    assert out.exists() and out.stat().st_size > 0


def test_export_pdf(qapp, tmp_path):
    from core.layout.models import DocumentSpec
    from core.layout import qt_renderer
    doc = DocumentSpec(title="D", pages=[_page(), _page()])
    out = tmp_path / "doc.pdf"
    qt_renderer.export_document_pdf(doc, str(out))
    assert out.exists() and out.stat().st_size > 500
    assert out.read_bytes()[:4] == b"%PDF"
