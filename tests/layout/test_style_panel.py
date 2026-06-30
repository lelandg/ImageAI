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


class StatefulFakeConfig:
    def __init__(self, **seed):
        self.layout = dict(seed)
    def get_layout_config(self): return dict(self.layout)
    def set_layout_config(self, c): self.layout = dict(c)
    def save(self): pass
    def get_layout_style_role(self): return self.layout.get("style_role", "")
    def set_layout_style_role(self, r): self.layout["style_role"] = r


def test_set_style_defaults_to_first_role_without_config(qapp):
    p = StylePanel()
    p.set_style(_style())
    assert p.role_combo.currentText() == p.role_combo.itemText(0)


def test_saved_role_restored_when_present(qapp):
    p = StylePanel(StatefulFakeConfig(style_role="title"))  # "body" sorts first
    p.set_style(_style())
    assert p.role_combo.currentText() == "title"


def test_saved_role_ignored_when_absent_from_style(qapp):
    p = StylePanel(StatefulFakeConfig(style_role="nonexistent-role"))
    p.set_style(_style())
    assert p.role_combo.currentText() == p.role_combo.itemText(0)


def test_role_change_persists(qapp):
    cfg = StatefulFakeConfig()
    p = StylePanel(cfg)
    p.set_style(_style())
    p.role_combo.setCurrentText("title")
    assert cfg.get_layout_style_role() == "title"
