import os
from gui.layout.layout_tab import LayoutTab


class FakeConfig:
    def get_layout_config(self): return {}
    def set_layout_config(self, c): pass
    def save(self): pass
    def get_layout_llm_provider(self): return "google"


def test_export_png_to_writes_file(qapp, tmp_path):
    tab = LayoutTab(config=FakeConfig())
    out = tmp_path / "page.png"
    tab.export_png_to(str(out))
    assert out.exists() and out.stat().st_size > 0


def test_export_worker_uses_qt_renderer(qapp):
    # The PIL LayoutEngine must no longer be used for image rendering in the worker.
    import inspect
    from gui.layout import export_dialog
    src = inspect.getsource(export_dialog.LayoutExportWorker)
    assert "qt_renderer" in src
    assert "engine.render_page" not in src  # PIL render path removed
