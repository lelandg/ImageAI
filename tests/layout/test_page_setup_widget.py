from core.layout.models import PageSize
from gui.layout.page_setup_widget import PageSetupWidget


class FakeConfig:
    def __init__(self):
        self.store = {"layout": {}}
    def get_layout_config(self):
        return dict(self.store["layout"])
    def set_layout_config(self, cfg):
        self.store["layout"] = cfg
    def save(self):
        pass


def test_widget_builds_and_default_page_size(qapp):
    w = PageSetupWidget(FakeConfig())
    ps = w.page_size()
    assert isinstance(ps, PageSize)
    assert ps.to_pixels()[0] > 0


def test_orientation_swap_changes_dims(qapp):
    w = PageSetupWidget(FakeConfig())
    w.set_page_size(PageSize(8.5, 11, "in", "portrait", 300))
    before = w.page_size().to_pixels()
    w._on_landscape()  # internal slot
    after = w.page_size().to_pixels()
    assert after == (before[1], before[0])


def test_add_custom_persists(qapp):
    cfg = FakeConfig()
    w = PageSetupWidget(cfg)
    assert w.add_custom_from_text("5.5 x 8.5") is True
    assert any(s["name"].startswith("Custom") for s in cfg.store["layout"]["custom_page_sizes"])


def test_emits_page_size_changed(qapp):
    w = PageSetupWidget(FakeConfig())
    received = []
    w.pageSizeChanged.connect(lambda ps: received.append(ps))
    w.set_page_size(PageSize(4, 6, "in", "portrait", 300))
    assert received and received[-1].to_pixels() == (1200, 1800)


def test_orientation_buttons_default_portrait(qapp):
    w = PageSetupWidget(FakeConfig())
    assert w.portrait_btn.isChecked()
    assert not w.landscape_btn.isChecked()


def test_orientation_buttons_sync_on_load(qapp):
    w = PageSetupWidget(FakeConfig())
    w.set_page_size(PageSize(11, 8.5, "in", "landscape", 300))
    assert w.landscape_btn.isChecked()
    assert not w.portrait_btn.isChecked()
    w.set_page_size(PageSize(8.5, 11, "in", "portrait", 300))
    assert w.portrait_btn.isChecked()
    assert not w.landscape_btn.isChecked()


def test_orientation_buttons_sync_on_click(qapp):
    w = PageSetupWidget(FakeConfig())
    w._on_landscape()
    assert w.landscape_btn.isChecked() and not w.portrait_btn.isChecked()
    w._on_portrait()
    assert w.portrait_btn.isChecked() and not w.landscape_btn.isChecked()
