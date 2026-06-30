# tests/layout/test_designer_panel.py
from core.layout.models import Region
from gui.layout.designer_panel import DesignerPanel, DesignerWorker
from core.layout import designer


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


class StatefulFakeConfig:
    """Records layout settings so save/restore round-trips can be asserted."""
    def __init__(self, **seed):
        self.layout = dict(seed)
        self.saved = 0
    def get_layout_config(self): return dict(self.layout)
    def set_layout_config(self, c): self.layout = dict(c)
    def save(self): self.saved += 1
    def get_layout_llm_provider(self): return self.layout.get("llm_provider", "google")
    def set_layout_llm_provider(self, p): self.layout["llm_provider"] = p
    def get_layout_llm_model(self): return self.layout.get("llm_model", "")
    def set_layout_llm_model(self, m): self.layout["llm_model"] = m
    def get_layout_content_kind(self): return self.layout.get("content_kind", "")
    def set_layout_content_kind(self, k): self.layout["content_kind"] = k


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


def test_design_button_reenabled_after_completion(qapp):
    p = DesignerPanel(FakeConfig())
    fake = lambda m: '{"layout": {"regions": [{"id":"z","kind":"image","bbox":[0,0,50,50]}]}}'
    p.start_design("a page", (300, 300), completion_fn=fake)
    assert p.design_btn.isEnabled()  # re-enabled once the (synchronous) design finished


def test_design_button_reenabled_after_failure(qapp):
    p = DesignerPanel(FakeConfig())

    def boom(m):
        raise RuntimeError("provider exploded")

    p.start_design("a page", (300, 300), completion_fn=boom)
    assert p.design_btn.isEnabled()  # _on_failed must re-enable the button


def test_console_collapsed_by_default_and_toggles(qapp):
    # isHidden() reflects the explicit hidden flag without needing the top-level
    # widget to be shown (isVisible() would be False for any child until then).
    p = DesignerPanel(FakeConfig())
    assert p.console.isHidden()                # collapsed on open
    assert not p.console_toggle.isChecked()
    p.console_toggle.setChecked(True)          # user expands it
    assert not p.console.isHidden()
    assert "Hide" in p.console_toggle.text()


def test_failure_auto_expands_console(qapp):
    p = DesignerPanel(FakeConfig())

    def boom(m):
        raise RuntimeError("provider exploded")

    p.start_design("a page", (300, 300), completion_fn=boom)
    assert p.console_toggle.isChecked() and not p.console.isHidden()  # errors never hidden


def test_content_kind_restored_from_config(qapp):
    p = DesignerPanel(StatefulFakeConfig(content_kind="magazine"))
    assert p.kind_combo.currentText() == "magazine"


def test_content_kind_change_persists(qapp):
    cfg = StatefulFakeConfig()
    p = DesignerPanel(cfg)
    p.kind_combo.setCurrentText("newspaper")
    assert cfg.get_layout_content_kind() == "newspaper"


def test_provider_change_persists(qapp):
    cfg = StatefulFakeConfig()
    p = DesignerPanel(cfg)
    if p.provider_combo.count() < 2:
        return  # only one provider available in this environment
    p.provider_combo.setCurrentIndex(
        (p.provider_combo.currentIndex() + 1) % p.provider_combo.count())
    assert cfg.get_layout_llm_provider() == p.provider_combo.currentText()


def test_model_restored_from_config(qapp):
    # Discover a real model from a fresh panel, seed it, then rebuild and assert
    # it is reselected after the provider repopulates the model list.
    probe = DesignerPanel(StatefulFakeConfig())
    if probe.model_combo.count() < 2:
        return  # no alternate model to distinguish a restore from the default
    target = probe.model_combo.itemText(1)
    cfg = StatefulFakeConfig(llm_model=target)
    p = DesignerPanel(cfg)
    assert p.model_combo.currentText() == target


def test_model_change_persists(qapp):
    cfg = StatefulFakeConfig()
    p = DesignerPanel(cfg)
    if p.model_combo.count() < 2:
        return
    p.model_combo.setCurrentIndex(1)
    assert cfg.get_layout_llm_model() == p.model_combo.currentText()
