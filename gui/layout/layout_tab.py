"""Layout tab — Phase 3: style panel + template export/import integration."""
import logging
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QLabel,
)
from PySide6.QtCore import Signal

from core.layout.models import DocumentSpec, PageSpec, PageSize, TextStyle
from core.layout import project_io, qt_renderer
from core.layout import styles, template_io
from core.layout.history import History
from gui.layout.page_setup_widget import PageSetupWidget
from gui.layout.canvas_widget import CanvasWidget
from gui.layout.designer_panel import DesignerPanel
from gui.layout.history_window import HistoryWindow
from gui.layout.style_panel import StylePanel
from gui.layout.content_inspector import ContentInspector

logger = logging.getLogger("imageai.layout.tab")


class LayoutTab(QWidget):
    documentChanged = Signal()

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.document: Optional[DocumentSpec] = None
        self.history: Optional[History] = None
        self._build()
        self.new_document()

    def _build(self):
        root = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        for label, slot in [
            ("New", self.new_document), ("Open…", self._open_dialog),
            ("Save…", self._save_dialog), ("Export PDF…", self._export_dialog),
            ("History…", self._open_history),
            ("Export Template…", self._export_template_dialog),
            ("Import Template…", self._import_template_dialog),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            toolbar.addWidget(btn)
        toolbar.addStretch(1)
        root.addLayout(toolbar)

        self.page_setup = PageSetupWidget(self.config)
        self.page_setup.pageSizeChanged.connect(self._on_page_size_changed)
        root.addWidget(self.page_setup)

        self.designer = DesignerPanel(self.config)
        self.designer.layoutProposed.connect(self._on_layout_proposed)
        self.designer.design_btn.clicked.connect(self._on_design_clicked)
        root.addWidget(self.designer)

        self.style_panel = StylePanel()
        self.style_panel.styleChanged.connect(self.apply_style)
        root.addWidget(self.style_panel)

        self.canvas = CanvasWidget()
        root.addWidget(self.canvas, 1)

        self.inspector = ContentInspector(self.config)
        self.inspector.regionContentChanged.connect(self._on_region_content_changed)
        self.inspector.regionTextStyleChanged.connect(self._on_region_text_style_changed)
        root.addWidget(self.inspector)
        self.canvas.regionSelected.connect(self._on_region_selected)

        self.status = QLabel("")
        root.addWidget(self.status)

    # --- document lifecycle ---
    def _adopt_document(self, doc):
        self.document = doc
        self.history = History(self.document)
        if self.document.style is None:
            self.document.style = styles.default_style_for(self.document.content_kind)
        self._style_user_modified = False
        if hasattr(self, "style_panel") and self.document.style:
            self.style_panel.set_style(self.document.style)
        if hasattr(self, "inspector"):
            self.inspector.set_region(None)

    def new_document(self):
        ps = self.page_setup.page_size() if hasattr(self, "page_setup") else PageSize(8.5, 11, "in")
        pw, ph = ps.to_pixels()
        page = PageSpec(page_size_px=(pw, ph), page_size=ps, background="#FFFFFF")
        self._adopt_document(DocumentSpec(title="Untitled", pages=[page]))
        self._refresh()

    def _on_page_size_changed(self, ps: PageSize):
        if not self.document or not self.document.pages:
            return
        page = self.document.pages[0]
        page.page_size = ps
        page.page_size_px = ps.to_pixels()
        self._refresh()

    def _refresh(self):
        if self.document and self.document.pages:
            self.canvas.load_page(self.document.pages[0], self.document.style)
            self.status.setText(f"{self.document.title} — {self.document.pages[0].page_size_px}")
        self.documentChanged.emit()

    # --- content inspector ---
    def _find_region(self, region_id: str):
        # MVP edits the first page only (the whole tab operates on pages[0]);
        # revisit when multi-page navigation lands.
        if not region_id or not self.document or not self.document.pages:
            return None
        for r in self.document.pages[0].regions:
            if r.id == region_id:
                return r
        return None

    def _on_region_selected(self, region_id: str):
        region = self._find_region(region_id)
        ts = None
        if region is not None and region.kind != "image":
            style = self.document.style if self.document else None
            ts = styles.effective_text_style(region, style)
        self.inspector.set_region(region, text_style=ts)

    def _on_region_content_changed(self, region_id: str, value: str):
        self.set_region_content(region_id, value)

    def _on_region_text_style_changed(self, region_id: str, family: str, size_px: int):
        """Apply the inspector's font family/size to a text region as an explicit
        ``text_style`` (decoupling it from its role so per-box edits stick)."""
        region = self._find_region(region_id)
        if region is None or region.kind == "image":
            return
        base = (region.text_style
                or styles.effective_text_style(region, self.document.style if self.document else None)
                or TextStyle(family=["Arial"]))
        region.text_style = TextStyle(
            family=[family] if family else list(base.family),
            weight=base.weight, italic=base.italic,
            size_px=size_px, line_height=base.line_height, color=base.color,
            align=base.align, wrap=base.wrap, letter_spacing=base.letter_spacing,
        )
        self._refresh()

    def set_region_content(self, region_id: str, value: str):
        """Apply edited content to a region and re-render (programmatic API)."""
        region = self._find_region(region_id)
        if region is None:
            return
        if region.kind == "image":
            if region.image_ref == value:
                return
            region.image_ref = value
        else:
            if region.text == value:
                return
            region.text = value
        self._refresh()

    # --- programmatic API (tested) ---
    def save_project_to(self, path: str):
        project_io.save_project(self.document, path)
        self.status.setText(f"Saved {path}")

    def open_project_from(self, path: str):
        self._adopt_document(project_io.load_project(path))
        self._refresh()

    def export_pdf_to(self, path: str):
        qt_renderer.export_document_pdf(self.document, path)
        self.status.setText(f"Exported {path}")

    # --- designer + history methods ---
    def _on_design_clicked(self):
        if not self.document or not self.document.pages:
            return
        text = self.designer.prompt_edit.toPlainText().strip()
        if not text:
            return
        page = self.document.pages[0]
        self.designer.start_design(text, page.page_size_px,
                                   current_regions=page.regions or None)

    def _on_layout_proposed(self, result):
        text = self.designer.prompt_edit.toPlainText().strip()
        self.apply_designer_result(result, user_text=text)

    def apply_designer_result(self, result, user_text: str = ""):
        if not self.document or not self.document.pages:
            return
        kind = self.designer.content_kind()
        if kind != self.document.content_kind:
            self.document.content_kind = kind
            if not getattr(self, "_style_user_modified", False):
                self.document.style = styles.default_style_for(kind)
                if hasattr(self, "style_panel"):
                    self.style_panel.set_style(self.document.style)
        if result.regions:
            self.document.pages[0].regions = list(result.regions)
            self.history.append(user_text or "design")
            self._refresh()
        elif result.questions:
            self.status.setText(
                f"Designer asked {len(result.questions)} question(s) — see the Designer console.")

    def restore_snapshot(self, snapshot_id: str):
        restored = self.history.restore(snapshot_id)
        self._adopt_document(restored)
        # Continuing from a restored point is a branch: the next design snapshot
        # must parent to snapshot_id, not the timeline's tail.
        self.history.branch_from(snapshot_id)
        self._refresh()

    def _open_history(self):
        win = HistoryWindow(self.history, self)
        win.restoreRequested.connect(self.restore_snapshot)
        win.exec()

    def apply_style(self, style):
        if self.document is None:
            return
        self.document.style = style
        self._style_user_modified = True
        self._refresh()

    def export_template_to(self, path: str):
        if self.document is None:
            return
        template_io.export_template(self.document, path)
        self.status.setText(f"Exported template {path}")

    def import_template_from(self, path: str):
        self._adopt_document(template_io.import_template(path))
        self._refresh()

    # --- error reporting (repo rule: all errors logged + shown to the user) ---
    def _report_error(self, what: str, exc: Exception):
        logger.error("Layout: failed to %s: %s", what, exc, exc_info=True)
        if hasattr(self, "status"):
            self.status.setText(f"Error: failed to {what}")
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Layout error", f"Failed to {what}:\n{exc}")
        except Exception:  # noqa: BLE001 - error reporting must never itself crash
            pass

    def _export_template_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Template", "",
                                              "ImageAI Layout Template (*.iailayout.json)")
        if path:
            try:
                self.export_template_to(path)
            except Exception as e:  # noqa: BLE001 - surfaced to UI + log
                self._report_error("export template", e)

    def _import_template_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Template", "",
                                              "ImageAI Layout Template (*.iailayout.json)")
        if path:
            try:
                self.import_template_from(path)
            except Exception as e:  # noqa: BLE001 - surfaced to UI + log
                self._report_error("import template", e)

    # --- dialogs ---
    def _save_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "ImageAI Project (*.iaiproj.json)")
        if path:
            try:
                self.save_project_to(path)
            except Exception as e:  # noqa: BLE001 - surfaced to UI + log
                self._report_error("save project", e)

    def _open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Project", "",
                                              "ImageAI Project (*.iaiproj.json *.layout.json)")
        if path:
            try:
                self.open_project_from(path)
            except Exception as e:  # noqa: BLE001 - surfaced to UI + log
                self._report_error("open project", e)

    def _export_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF", "", "PDF (*.pdf)")
        if path:
            try:
                self.export_pdf_to(path)
            except Exception as e:  # noqa: BLE001 - surfaced to UI + log
                self._report_error("export PDF", e)
