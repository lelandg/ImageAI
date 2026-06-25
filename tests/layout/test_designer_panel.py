# tests/layout/test_designer_panel.py
from core.layout.models import Region
from gui.layout.designer_panel import DesignerPanel, DesignerWorker
from core.layout import designer


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def test_worker_emits_proposed_with_injected_completion(qapp):
    msgs = designer.build_messages("comic", (200, 200), "one panel")
    fake = lambda m: '{"layout": {"regions": [{"id":"a","kind":"image","bbox":[0,0,100,100]}]}}'
    w = DesignerWorker(msgs, (200, 200), fake)
    got = []
    w.proposed.connect(lambda res: got.append(res))
    w.run()  # run synchronously in-test (no thread start)
    assert got and [r.id for r in got[0].regions] == ["a"]


def test_panel_builds_and_reports_content_kind(qapp):
    p = DesignerPanel(FakeConfig())
    assert isinstance(p.content_kind(), str) and p.content_kind()


def test_panel_start_design_emits_layout_proposed(qapp):
    p = DesignerPanel(FakeConfig())
    got = []
    p.layoutProposed.connect(lambda res: got.append(res))
    fake = lambda m: '{"layout": {"regions": [{"id":"z","kind":"text","bbox":[0,0,50,50],"text":"hi"}]}}'
    p.start_design("a title page", (300, 300), completion_fn=fake)
    assert got and [r.id for r in got[0].regions] == ["z"]
