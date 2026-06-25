# tests/layout/test_layout_tab_prompt.py — Phase 5a per-region AI prompt help
from core.layout import designer
from gui.layout.layout_tab import LayoutTab


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def _tab_with_regions():
    tab = LayoutTab(config=FakeConfig())
    tab.apply_designer_result(designer.DesignerResult(regions=[
        designer.Region(id="img", kind="image", name="hero", bbox=(0, 0, 100, 100)),
        designer.Region(id="txt", kind="text", bbox=(0, 110, 100, 40), text="hi", role="title"),
    ]), user_text="page")
    return tab


def test_suggest_writes_prompt_and_updates_inspector(qapp):
    tab = _tab_with_regions()
    tab._on_region_selected("img")          # show the image editor
    captured = {}

    def fake(messages):
        captured["msgs"] = messages
        return '{"prompt": "a brave hero on a cliff at dawn"}'

    tab.suggest_region_prompt("img", hint="dawn", completion_fn=fake)
    region = tab.document.pages[0].regions[0]
    assert region.prompt == "a brave hero on a cliff at dawn"
    assert tab.inspector.prompt_edit.toPlainText() == "a brave hero on a cliff at dawn"
    # the hint reached the LLM messages
    assert "dawn" in " ".join(m["content"] for m in captured["msgs"])


def test_empty_suggestion_keeps_existing_prompt(qapp):
    tab = _tab_with_regions()
    tab.document.pages[0].regions[0].prompt = "keep me"
    tab.suggest_region_prompt("img", completion_fn=lambda m: "")
    assert tab.document.pages[0].regions[0].prompt == "keep me"


def test_suggest_on_text_region_is_noop(qapp):
    tab = _tab_with_regions()
    called = {"n": 0}

    def fake(m):
        called["n"] += 1
        return '{"prompt": "x"}'

    tab.suggest_region_prompt("txt", completion_fn=fake)
    assert called["n"] == 0  # never calls the LLM for a text region


def test_suggest_unknown_id_is_noop(qapp):
    tab = _tab_with_regions()
    tab.suggest_region_prompt("nope", completion_fn=lambda m: '{"prompt":"x"}')  # must not raise


def test_apply_prompt_persists_on_region(qapp):
    tab = _tab_with_regions()
    tab._on_region_prompt_changed("img", "manually typed prompt")
    assert tab.document.pages[0].regions[0].prompt == "manually typed prompt"


def test_apply_prompt_on_text_region_is_noop(qapp):
    tab = _tab_with_regions()
    tab._on_region_prompt_changed("txt", "should not stick")
    # text regions have no image prompt; nothing written
    assert tab.document.pages[0].regions[1].prompt == ""


def test_failed_suggestion_surfaces_in_console(qapp):
    tab = _tab_with_regions()

    def boom(m):
        raise RuntimeError("network down")

    tab.suggest_region_prompt("img", completion_fn=boom)
    # failure must expand the designer console (errors are never hidden)
    assert tab.designer.console_toggle.isChecked()
