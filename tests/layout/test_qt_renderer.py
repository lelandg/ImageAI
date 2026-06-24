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


def test_text_region_resolves_font_role_from_style(qapp):
    from core.layout.models import Region, PageSpec, ProjectStyle, TextStyle
    from core.layout import qt_renderer
    from PySide6.QtWidgets import QGraphicsSimpleTextItem
    style = ProjectStyle(font_roles={"title": TextStyle(family=["Georgia"], size_px=64, weight="bold")})
    page = PageSpec(page_size_px=(400, 200), regions=[
        Region(id="t", kind="text", bbox=(0, 0, 400, 100), text="Hi", role="title")])
    scene = qt_renderer.build_scene(page, style=style)
    texts = [it for it in scene.items() if isinstance(it, QGraphicsSimpleTextItem)]
    assert texts, "expected a text item"
    f = texts[0].font()
    assert f.pixelSize() == 64
    assert f.bold() is True


def test_explicit_text_style_overrides_role(qapp):
    from core.layout.models import Region, PageSpec, ProjectStyle, TextStyle
    from core.layout import qt_renderer
    from PySide6.QtWidgets import QGraphicsSimpleTextItem
    style = ProjectStyle(font_roles={"title": TextStyle(family=["Georgia"], size_px=64)})
    page = PageSpec(page_size_px=(400, 200), regions=[
        Region(id="t", kind="text", bbox=(0, 0, 400, 100), text="Hi", role="title",
               text_style=TextStyle(family=["Arial"], size_px=20))])
    scene = qt_renderer.build_scene(page, style=style)
    texts = [it for it in scene.items() if isinstance(it, QGraphicsSimpleTextItem)]
    assert texts[0].font().pixelSize() == 20  # explicit style wins


def test_unroled_text_uses_default_text_role(qapp):
    from core.layout.models import Region, PageSpec, ProjectStyle, TextStyle
    from core.layout import qt_renderer
    from PySide6.QtWidgets import QGraphicsSimpleTextItem
    style = ProjectStyle(font_roles={"body": TextStyle(family=["Arial"], size_px=33)},
                         default_text_role="body")
    page = PageSpec(page_size_px=(400, 200), regions=[
        Region(id="t", kind="text", bbox=(0, 0, 400, 100), text="Hi", role="")])
    scene = qt_renderer.build_scene(page, style=style)
    texts = [it for it in scene.items() if isinstance(it, QGraphicsSimpleTextItem)]
    assert texts[0].font().pixelSize() == 33  # fell back to default_text_role
