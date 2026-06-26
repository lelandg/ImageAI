# tests/layout/test_layout_tab_send_to_image.py — Phase 5b Send-to-Image handoff
from core.layout import designer
from gui.layout.layout_tab import LayoutTab


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def _tab():
    tab = LayoutTab(config=FakeConfig())
    tab.apply_designer_result(designer.DesignerResult(regions=[
        designer.Region(id="img", kind="image", name="hero", bbox=(10, 20, 640, 480)),
        designer.Region(id="txt", kind="text", bbox=(0, 510, 100, 40), text="hi"),
    ]), user_text="page")
    return tab


def test_send_to_image_emits_payload(qapp):
    tab = _tab()
    got = []
    tab.sendToImageRequested.connect(lambda p: got.append(p))
    tab._on_region_send_to_image("img", "a brave hero")
    assert got == [{"region_id": "img", "prompt": "a brave hero",
                    "width": 640, "height": 480}]
    # the prompt is persisted on the region too
    assert tab.document.pages[0].regions[0].prompt == "a brave hero"


def test_send_to_image_uses_unsaved_inspector_prompt(qapp):
    # The inspector forwards its current (possibly unsaved) text as the prompt.
    tab = _tab()
    tab._on_region_selected("img")
    tab.inspector.prompt_edit.setPlainText("typed but not applied")
    got = []
    tab.sendToImageRequested.connect(lambda p: got.append(p))
    tab.inspector.send_to_image_btn.click()
    assert got and got[0]["prompt"] == "typed but not applied"
    assert got[0]["region_id"] == "img"


def test_send_to_image_text_region_is_noop(qapp):
    tab = _tab()
    got = []
    tab.sendToImageRequested.connect(lambda p: got.append(p))
    tab._on_region_send_to_image("txt", "nope")
    assert got == []


def test_send_to_image_unknown_id_is_noop(qapp):
    tab = _tab()
    got = []
    tab.sendToImageRequested.connect(lambda p: got.append(p))
    tab._on_region_send_to_image("nope", "x")  # must not raise
    assert got == []
