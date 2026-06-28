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


def test_render_page_to_image_scale_doubles_dimensions(qapp):
    from core.layout import qt_renderer
    from core.layout.models import PageSpec
    page = PageSpec(page_size_px=(200, 150), regions=[], overlays=[])
    base = qt_renderer.render_page_to_image(page)
    scaled = qt_renderer.render_page_to_image(page, scale=2.0)
    assert (scaled.width(), scaled.height()) == (base.width() * 2, base.height() * 2)


def _doc():
    from core.layout.models import DocumentSpec, PageSpec, Region
    return DocumentSpec(title="t", pages=[PageSpec(
        page_size_px=(200, 150),
        regions=[Region(id="r", kind="image", shape="rect", bbox=(0, 0, 100, 100))],
        overlays=[])])


def test_export_worker_pdf_executes_via_qt(qapp, tmp_path):
    # Execute the PDF worker path (not just grep its source): proves
    # export_document_pdf(dpi=...) actually accepts the kwarg and renders.
    from gui.layout.export_dialog import ExportWorker
    out = tmp_path / "doc.pdf"
    worker = ExportWorker(_doc(), "pdf", str(out), dpi=300)
    worker._export_pdf(out, [0], 1)
    assert out.exists() and out.stat().st_size > 0


def test_export_worker_png_executes_via_qt(qapp, tmp_path):
    # Execute the PNG worker path end-to-end through the Qt renderer (dpi -> scale).
    from gui.layout.export_dialog import ExportWorker
    out = tmp_path / "doc.png"
    worker = ExportWorker(_doc(), "png", str(out), dpi=144)
    worker._export_png(out, [0], 1)
    assert out.exists() and out.stat().st_size > 0
