from core.layout.models import ProjectStyle, DocumentSpec, PageSpec, Region, TextStyle
from core.layout import schema, styles


def test_default_style_for_comic_has_dialogue_role():
    st = styles.default_style_for("comic")
    assert "dialogue" in st.font_roles
    assert isinstance(st.font_roles["dialogue"], TextStyle)
    assert st.default_text_role == "dialogue"
    assert st.palette.get("text")


def test_default_style_for_children_has_title_and_narration():
    st = styles.default_style_for("children")
    assert set(["title", "narration"]).issubset(st.font_roles.keys())


def test_default_style_for_unknown_kind_falls_back():
    st = styles.default_style_for("totally-made-up")
    assert "body" in st.font_roles and "title" in st.font_roles


def test_project_style_roundtrip_via_schema():
    doc = DocumentSpec(title="D", pages=[PageSpec(page_size_px=(100, 100))],
                       style=styles.default_style_for("comic"))
    again = schema.document_from_dict(schema.document_to_dict(doc))
    assert again.style is not None
    assert "dialogue" in again.style.font_roles
    assert again.style.font_roles["dialogue"].size_px == doc.style.font_roles["dialogue"].size_px
    assert again.style.default_text_role == "dialogue"


def test_document_without_style_roundtrips_none():
    doc = DocumentSpec(title="D", pages=[PageSpec(page_size_px=(100, 100))])
    again = schema.document_from_dict(schema.document_to_dict(doc))
    assert again.style is None


def test_effective_text_style_prefers_explicit():
    explicit = TextStyle(family=["Arial"], size_px=20)
    r = Region(id="t", kind="text", role="title", text_style=explicit)
    st = ProjectStyle(font_roles={"title": TextStyle(family=["Georgia"], size_px=64)})
    assert styles.effective_text_style(r, st) is explicit


def test_effective_text_style_resolves_role():
    r = Region(id="t", kind="text", role="title")
    st = ProjectStyle(font_roles={"title": TextStyle(family=["Georgia"], size_px=64)})
    assert styles.effective_text_style(r, st).size_px == 64


def test_effective_text_style_falls_back_to_default_role():
    r = Region(id="t", kind="text", role="")  # no role -> default_text_role
    st = ProjectStyle(font_roles={"body": TextStyle(family=["Arial"], size_px=28)},
                      default_text_role="body")
    assert styles.effective_text_style(r, st).size_px == 28


def test_effective_text_style_none_when_unresolvable():
    r = Region(id="t", kind="text", role="ghost")
    assert styles.effective_text_style(r, None) is None
    st = ProjectStyle(font_roles={"body": TextStyle(family=["Arial"], size_px=28)},
                      default_text_role="body")
    assert styles.effective_text_style(r, st) is None  # 'ghost' role isn't defined
