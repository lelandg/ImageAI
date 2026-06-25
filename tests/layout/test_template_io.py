from core.layout.models import Region, PageSpec, DocumentSpec
from core.layout import template_io, styles


def _doc():
    page = PageSpec(page_size_px=(500, 500), regions=[
        Region(id="img", kind="image", bbox=(0, 0, 200, 200), image_ref="/a.png",
               prompt="a red car"),
        Region(id="txt", kind="text", bbox=(0, 220, 500, 60), text="My Title", role="title"),
    ])
    doc = DocumentSpec(title="Proj", content_kind="comic", pages=[page],
                       style=styles.default_style_for("comic"))
    return doc


def test_export_strips_content_keeps_structure(tmp_path):
    p = tmp_path / "t.iailayout.json"
    template_io.export_template(_doc(), str(p))
    loaded = template_io.import_template(str(p))
    regions = loaded.pages[0].regions
    # geometry + shape + role + prompt preserved
    assert [r.id for r in regions] == ["img", "txt"]
    assert regions[0].bbox == (0, 0, 200, 200)
    assert regions[0].prompt == "a red car"
    assert regions[1].role == "title"
    # content stripped
    assert regions[0].image_ref is None
    assert regions[1].text == ""
    # style preserved
    assert loaded.style is not None and "dialogue" in loaded.style.font_roles
    # content_kind preserved, history dropped
    assert loaded.content_kind == "comic"
    assert loaded.history == []
