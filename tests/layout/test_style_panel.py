from core.layout.models import ProjectStyle, TextStyle
from gui.layout.style_panel import StylePanel


def _style():
    return ProjectStyle(font_roles={
        "title": TextStyle(family=["Georgia"], size_px=64, weight="bold"),
        "body": TextStyle(family=["Arial"], size_px=28)},
        palette={"text": "#111111"}, default_text_role="body")


def test_panel_lists_roles(qapp):
    p = StylePanel()
    p.set_style(_style())
    assert p.role_combo.count() == 2


def test_editing_family_updates_style_and_emits(qapp):
    p = StylePanel()
    p.set_style(_style())
    got = []
    p.styleChanged.connect(lambda s: got.append(s))
    p.role_combo.setCurrentText("title")
    p.family_edit.setText("Impact")
    p._on_field_changed()  # internal slot
    assert p.style().font_roles["title"].family[0] == "Impact"
    assert got and got[-1].font_roles["title"].family[0] == "Impact"


def test_editing_size(qapp):
    p = StylePanel()
    p.set_style(_style())
    got = []
    p.styleChanged.connect(lambda s: got.append(s))
    p.role_combo.setCurrentText("body")
    p.size_spin.setValue(40)
    p._on_field_changed()
    assert p.style().font_roles["body"].size_px == 40
    assert got and got[-1].font_roles["body"].size_px == 40
