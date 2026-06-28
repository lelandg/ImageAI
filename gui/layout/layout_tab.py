"""Layout tab — Phase 3: style panel + template export/import integration."""
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QLabel,
)
from PySide6.QtCore import Signal

from core.layout.models import DocumentSpec, PageSpec, PageSize, TextStyle
from core.layout import project_io, qt_renderer
from core.layout import styles, template_io
from core.layout import designer, prompt_helper, bundle_io
from core.layout.history import History
from gui.layout.page_setup_widget import PageSetupWidget
from gui.layout.canvas_widget import CanvasWidget
from gui.layout.designer_panel import DesignerPanel
from gui.layout.history_window import HistoryWindow
from gui.layout.style_panel import StylePanel
from gui.layout.content_inspector import ContentInspector

logger = logging.getLogger("imageai.layout.tab")

_DEFAULT_STROKE_PX = 4  # panel stroke applied when "borderless" is unchecked


class LayoutTab(QWidget):
    documentChanged = Signal()
    # Ask the host (MainWindow) to open the Image tab for a region. Payload dict:
    # {region_id, prompt, width, height}. The host places the result back via
    # set_region_content(region_id, path). Decouples LayoutTab from MainWindow.
    sendToImageRequested = Signal(object)
    # Layout-complete mode: an ordered list of the above payloads (one per image
    # region with a prompt). The host fills them one at a time via the Image tab.
    fillAllRequested = Signal(object)

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.document: Optional[DocumentSpec] = None
        self.history: Optional[History] = None
        self._prompt_worker = None  # keep alive so the QThread isn't GC'd mid-run
        self._locked = self._load_locked()
        self._build()
        self._restore_session_or_new()

    def _build(self):
        root = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        for label, slot in [
            ("New", self.new_document), ("Open…", self._open_dialog),
            ("Save…", self._save_dialog), ("Export PDF…", self._export_dialog),
            ("History…", self._open_history),
            ("Export Template…", self._export_template_dialog),
            ("Import Template…", self._import_template_dialog),
            ("Export Bundle…", self._export_bundle_dialog),
            ("Import Bundle…", self._import_bundle_dialog),
            ("Fill all regions →", self._on_fill_all_clicked),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            toolbar.addWidget(btn)
        toolbar.addStretch(1)
        # Lock toggle: when locked (default) generated frames and applied text
        # stay put; unlock to reposition them. State persists across launches.
        self.lock_btn = QPushButton()
        self.lock_btn.setCheckable(True)
        self.lock_btn.setChecked(self._locked)
        self.lock_btn.toggled.connect(self._on_lock_toggled)
        self._update_lock_button()
        toolbar.addWidget(self.lock_btn)
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
        self.inspector.regionPromptChanged.connect(self._on_region_prompt_changed)
        self.inspector.regionPromptSuggestRequested.connect(self._on_region_prompt_suggest)
        self.inspector.regionSendToImageRequested.connect(self._on_region_send_to_image)
        root.addWidget(self.inspector)

        from gui.layout.geometry_inspector import GeometryInspector
        self.geometry_inspector = GeometryInspector()
        self.geometry_inspector.bleedToggled.connect(self._on_region_bleed_toggled)
        self.geometry_inspector.borderlessToggled.connect(self._on_region_borderless_toggled)
        self.geometry_inspector.zChanged.connect(self._on_region_z_changed)
        root.addWidget(self.geometry_inspector)

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
            self.canvas.load_page(self.document.pages[0], self.document.style,
                                  locked=self._locked)
            self.status.setText(f"{self.document.title} — {self.document.pages[0].page_size_px}")
        self.documentChanged.emit()

    # --- lock state (frames + applied text stay put until unlocked) ---
    def _load_locked(self) -> bool:
        if not self.config:
            return True
        try:
            return bool(self.config.get_layout_config().get("items_locked", True))
        except Exception:  # noqa: BLE001 - config read must never block startup
            logger.exception("Layout: failed to read lock state; defaulting to locked")
            return True

    def _update_lock_button(self):
        # Frames are always locked; this toggle only governs text.
        self.lock_btn.setText("🔒 Text locked" if self._locked else "🔓 Text unlocked")
        self.lock_btn.setToolTip(
            "Text is locked to its frame — click to unlock and reposition text. "
            "(Image frames are always locked in place.)"
            if self._locked else
            "Text can be moved — click to lock it back to its frame. "
            "(Image frames are always locked in place.)")

    def _on_lock_toggled(self, checked: bool):
        self._locked = bool(checked)
        self._update_lock_button()
        self._persist_locked()
        self._refresh()

    def _persist_locked(self):
        if not self.config:
            return
        try:
            cfg = self.config.get_layout_config()
            cfg["items_locked"] = self._locked
            self.config.set_layout_config(cfg)
            self.config.save()
        except Exception:  # noqa: BLE001 - persistence is best-effort
            logger.exception("Layout: failed to persist lock state")

    # --- session persistence (reload last layout on startup) ---
    def _session_path(self) -> Optional[Path]:
        base = getattr(self.config, "config_dir", None) if self.config else None
        if not base:
            return None
        return Path(base) / "layout" / "last_session.iaiproj.json"

    def _restore_session_or_new(self):
        path = self._session_path()
        if path and path.exists():
            try:
                self._adopt_document(project_io.load_project(str(path)))
                page = (self.document.pages[0]
                        if self.document and self.document.pages else None)
                if page is not None and page.page_size and hasattr(self, "page_setup"):
                    self.page_setup.set_page_size(page.page_size)
                self._refresh()
                logger.info("Layout: restored last session from %s", path)
                return
            except Exception:  # noqa: BLE001 - a bad session must not block the tab
                logger.exception("Layout: failed to restore last session; starting new")
        self.new_document()

    def save_session(self):
        """Persist the current document + lock state so the tab reloads next launch.

        Invoked from ``MainWindow.closeEvent`` so the Layout tab remembers its
        work the way the other tabs remember theirs.
        """
        self._persist_locked()
        path = self._session_path()
        if not path or self.document is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            project_io.save_project(self.document, str(path))
            logger.info("Layout: saved session to %s", path)
        except Exception:  # noqa: BLE001 - autosave is best-effort
            logger.exception("Layout: failed to save session")

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
        self.geometry_inspector.set_region(region)

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

    def _on_region_bleed_toggled(self, region_id: str, bleed: bool):
        region = self._find_region(region_id)
        if region is None:
            return
        region.bleed = bool(bleed)
        if self.history is not None:
            self.history.append(f"bleed: {region.name or region.id}")
        self._refresh()

    def _on_region_borderless_toggled(self, region_id: str, borderless: bool):
        region = self._find_region(region_id)
        if region is None:
            return
        from core.layout.models import ImageStyle
        if region.image_style is None:
            region.image_style = ImageStyle()
        region.image_style.stroke_px = 0 if borderless else _DEFAULT_STROKE_PX
        if self.history is not None:
            self.history.append(f"borderless: {region.name or region.id}")
        self._refresh()

    def _on_region_z_changed(self, region_id: str, z: int):
        region = self._find_region(region_id)
        if region is None:
            return
        region.z = int(z)
        if self.history is not None:
            self.history.append(f"z: {region.name or region.id}")
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

    # --- per-region AI image-prompt help (Phase 5a) ---
    def _on_region_prompt_changed(self, region_id: str, prompt: str):
        """Persist an edited image prompt on the region (metadata; no re-render)."""
        region = self._find_region(region_id)
        if region is None or region.kind != "image":
            return
        region.prompt = prompt
        self.status.setText(f"Saved prompt for {region.name or region.id}")

    def _on_region_prompt_suggest(self, region_id: str, hint: str):
        self.suggest_region_prompt(region_id, hint)

    def _on_region_send_to_image(self, region_id: str, prompt: str):
        """Persist the prompt and ask the host to open the Image tab for it."""
        region = self._find_region(region_id)
        if region is None or region.kind != "image":
            return
        region.prompt = prompt
        _, _, w, h = region.bbox
        self.sendToImageRequested.emit({
            "region_id": region_id, "prompt": prompt,
            "width": int(w), "height": int(h),
        })
        self.status.setText(f"Sent {region.name or region.id} to the Image tab")

    def _collect_fill_payloads(self):
        """Ordered payloads for every image region carrying a prompt (page 0)."""
        payloads = []
        if not self.document or not self.document.pages:
            return payloads
        for r in self.document.pages[0].regions:
            if r.kind != "image" or not (r.prompt or "").strip():
                continue
            _, _, w, h = r.bbox
            payloads.append({"region_id": r.id, "prompt": r.prompt,
                             "width": int(w), "height": int(h)})
        return payloads

    def _on_fill_all_clicked(self):
        """Layout-complete mode: fill every prompted image region in sequence."""
        payloads = self._collect_fill_payloads()
        if not payloads:
            self.status.setText(
                "No image regions with prompts — add prompts (Suggest with AI) first.")
            return
        self.fillAllRequested.emit(payloads)
        self.status.setText(f"Filling {len(payloads)} image region(s) via the Image tab…")

    def suggest_region_prompt(self, region_id: str, hint: str = "", completion_fn=None):
        """Draft an image prompt for ``region_id`` from the project theme.

        ``completion_fn`` is injected in tests (run synchronously); in production
        it wraps ``designer.run_completion`` with the Designer panel's selected
        provider/model so there's a single LLM config for the tab.
        """
        region = self._find_region(region_id)
        if region is None or region.kind != "image" or self.document is None:
            return
        if self._prompt_worker is not None and self._prompt_worker.isRunning():
            self.designer.console.log("A prompt suggestion is already running.", "WARNING")
            return
        messages = prompt_helper.build_prompt_messages(self.document, region, hint)
        self.designer.console.log(
            f"Suggesting image prompt for {region.name or region.id}:\n"
            + messages[-1]["content"], "INFO")
        injected = completion_fn is not None
        if completion_fn is None:
            provider = self.designer.provider_combo.currentText()
            model = self.designer.model_combo.currentText()
            cfg = self.config
            completion_fn = lambda m: designer.run_completion(cfg, provider, model, m)
        self.inspector.set_suggest_enabled(False)
        from gui.layout.prompt_worker import PromptSuggestWorker
        self._prompt_worker = PromptSuggestWorker(region_id, messages, completion_fn)
        self._prompt_worker.suggested.connect(self._on_prompt_suggested)
        self._prompt_worker.failed.connect(self._on_prompt_failed)
        if injected:
            self._prompt_worker.run()   # synchronous for injected/test completions
        else:
            self._prompt_worker.start()

    def _on_prompt_suggested(self, region_id: str, prompt: str):
        self.inspector.set_suggest_enabled(True)
        region = self._find_region(region_id)
        if region is None or region.kind != "image":
            return
        if not prompt:
            self.designer.console.log(
                "Prompt suggestion came back empty — keeping the existing prompt.",
                "WARNING")
            return
        region.prompt = prompt
        self.inspector.set_prompt_text(region_id, prompt)
        self.designer.console.log("Suggested prompt:\n" + prompt, "SUCCESS")
        self.status.setText(f"Suggested prompt for {region.name or region.id}")

    def _on_prompt_failed(self, region_id: str, err: str):
        self.inspector.set_suggest_enabled(True)
        if not self.designer.console_toggle.isChecked():
            self.designer.console_toggle.setChecked(True)  # surface the failure
        self.designer.console.log(f"Prompt suggestion failed: {err}", "ERROR")
        self.status.setText("Error: prompt suggestion failed")

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
        applied = False
        if result.regions:
            self.document.pages[0].regions = list(result.regions)
            applied = True
        if getattr(result, "overlays", None):
            self.document.pages[0].overlays = list(result.overlays)
            applied = True
        if applied:
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

    # --- bundles (.iaibundle: project + images + fonts, self-contained) ---
    def _bundle_font_resolver(self):
        """Lazily build a font_resolver from FontManager (best-effort).

        Discovery scans system fonts, so it's built once and cached; any failure
        degrades to None (fonts recorded by-name) — never blocks export.
        """
        if getattr(self, "_font_manager", None) is None:
            try:
                from core.layout.font_manager import FontManager
                custom = self.config.get_fonts_dir() if self.config else None
                self._font_manager = FontManager(
                    custom_dirs=[custom] if custom else None)
            except Exception:  # noqa: BLE001 - font scan must never block export
                logger.exception("Layout: font discovery failed; bundling by name")
                self._font_manager = False  # sentinel: tried and failed
        fm = self._font_manager
        return fm.select_font_file if fm else None

    def _bundle_extract_dir(self, path: str) -> Path:
        stem = Path(path).stem
        base = getattr(self.config, "config_dir", None) if self.config else None
        if base:
            return Path(base) / "layout" / "bundles" / stem
        return Path(path).parent / f"{stem}_files"

    def export_bundle_to(self, path: str):
        if self.document is None:
            return
        manifest = bundle_io.export_bundle(
            self.document, path, font_resolver=self._bundle_font_resolver())
        msg = f"Exported bundle {path}"
        if manifest.warnings:
            msg += f" ({len(manifest.warnings)} warning(s))"
        self.status.setText(msg)

    def import_bundle_from(self, path: str):
        dest = self._bundle_extract_dir(path)
        self._adopt_document(bundle_io.import_bundle(path, str(dest)))
        page = (self.document.pages[0]
                if self.document and self.document.pages else None)
        if page is not None and page.page_size and hasattr(self, "page_setup"):
            self.page_setup.set_page_size(page.page_size)
        self._refresh()

    def _export_bundle_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Bundle", "",
                                              "ImageAI Layout Bundle (*.iaibundle)")
        if path:
            try:
                self.export_bundle_to(path)
            except Exception as e:  # noqa: BLE001 - surfaced to UI + log
                self._report_error("export bundle", e)

    def _import_bundle_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Bundle", "",
                                              "ImageAI Layout Bundle (*.iaibundle)")
        if path:
            try:
                self.import_bundle_from(path)
            except Exception as e:  # noqa: BLE001 - surfaced to UI + log
                self._report_error("import bundle", e)

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
