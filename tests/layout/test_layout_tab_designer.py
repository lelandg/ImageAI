# tests/layout/test_layout_tab_designer.py
from core.layout import designer
from gui.layout.layout_tab import LayoutTab


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def test_apply_designer_result_sets_regions_and_snapshots(qapp):
    tab = LayoutTab(config=FakeConfig())
    res = designer.DesignerResult(
        questions=[], regions=[designer.Region(id="a", kind="image", bbox=(0, 0, 100, 100))],
        raw="")
    tab.apply_designer_result(res, user_text="one panel")
    assert [r.id for r in tab.document.pages[0].regions] == ["a"]
    assert len(tab.history.snapshots()) == 1
    assert tab.history.snapshots()[0].prompt == "one panel"


def test_restore_snapshot_reloads_document(qapp):
    tab = LayoutTab(config=FakeConfig())
    # iteration 1
    tab.apply_designer_result(
        designer.DesignerResult(regions=[designer.Region(id="a", kind="image", bbox=(0, 0, 50, 50))]),
        user_text="v1")
    sid = tab.history.snapshots()[0].id
    # iteration 2 (different regions)
    tab.apply_designer_result(
        designer.DesignerResult(regions=[designer.Region(id="b", kind="text", bbox=(0, 0, 50, 50), text="x")]),
        user_text="v2")
    assert [r.id for r in tab.document.pages[0].regions] == ["b"]
    tab.restore_snapshot(sid)
    assert [r.id for r in tab.document.pages[0].regions] == ["a"]  # back to v1


def test_design_button_calls_start_design_with_page_size(qapp):
    tab = LayoutTab(config=FakeConfig())
    captured = {}
    tab.designer.start_design = lambda *a, **k: captured.setdefault("call", (a, k))
    tab.designer.prompt_edit.setPlainText("a comic cover")
    tab._on_design_clicked()
    a, k = captured["call"]
    assert a[0] == "a comic cover"                       # prompt text passed
    assert a[1] == tab.document.pages[0].page_size_px    # current page size supplied


def test_apply_designer_result_questions_only_sets_status(qapp):
    tab = LayoutTab(config=FakeConfig())
    res = designer.DesignerResult(questions=["how many panels?"], regions=None, raw="")
    tab.apply_designer_result(res, user_text="a comic")
    assert "question" in tab.status.text().lower()
