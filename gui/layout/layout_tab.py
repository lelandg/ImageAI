"""Layout tab — Phase 2: AI designer + history integration."""
import logging
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QLabel,
)
from PySide6.QtCore import Signal

from core.layout.models import DocumentSpec, PageSpec, PageSize
from core.layout import project_io, qt_renderer
from core.layout.history import History
from gui.layout.page_setup_widget import PageSetupWidget
from gui.layout.canvas_widget import CanvasWidget
from gui.layout.designer_panel import DesignerPanel
from gui.layout.history_window import HistoryWindow

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

        self.canvas = CanvasWidget()
        root.addWidget(self.canvas, 1)

        self.status = QLabel("")
        root.addWidget(self.status)

    # --- document lifecycle ---
    def new_document(self):
        ps = self.page_setup.page_size() if hasattr(self, "page_setup") else PageSize(8.5, 11, "in")
        pw, ph = ps.to_pixels()
        page = PageSpec(page_size_px=(pw, ph), page_size=ps, background="#FFFFFF")
        self.document = DocumentSpec(title="Untitled", pages=[page])
        self.history = History(self.document)
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
            self.canvas.load_page(self.document.pages[0])
            self.status.setText(f"{self.document.title} — {self.document.pages[0].page_size_px}")
        self.documentChanged.emit()

    # --- programmatic API (tested) ---
    def save_project_to(self, path: str):
        project_io.save_project(self.document, path)
        self.status.setText(f"Saved {path}")

    def open_project_from(self, path: str):
        self.document = project_io.load_project(path)
        self.history = History(self.document)
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
        self.document.content_kind = self.designer.content_kind()
        if result.regions:
            self.document.pages[0].regions = list(result.regions)
            self.history.append(user_text or "design")
            self._refresh()
        elif result.questions:
            self.status.setText(
                f"Designer asked {len(result.questions)} question(s) — see the Designer console.")

    def restore_snapshot(self, snapshot_id: str):
        restored = self.history.restore(snapshot_id)
        self.document = restored
        self.history = History(self.document)
        self._refresh()

    def _open_history(self):
        win = HistoryWindow(self.history, self)
        win.restoreRequested.connect(self.restore_snapshot)
        win.exec()

    # --- dialogs ---
    def _save_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "ImageAI Project (*.iaiproj.json)")
        if path:
            self.save_project_to(path)

    def _open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Project", "",
                                              "ImageAI Project (*.iaiproj.json *.layout.json)")
        if path:
            self.open_project_from(path)

    def _export_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF", "", "PDF (*.pdf)")
        if path:
            self.export_pdf_to(path)
