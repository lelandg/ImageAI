"""Style Manager dialog: create, edit, analyze, import/export custom styles."""
import copy
import json
import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QSettings, QThread, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QListView, QMessageBox,
    QPushButton, QTextEdit, QVBoxLayout, QWidget)

from core.llm_models import get_provider_models
from core.styles.models import Style, StyleDescriptor
from core.styles.store import EXEMPLAR_DEFAULT_CAP, StyleStore
from gui.common.dialog_conventions import (
    DialogCleanupMixin, bind_primary_action, persist_splitter,
    restore_splitter, set_default_button, standard_splitter)
from gui.dialog_utils import OperationGuardMixin, show_error, show_question, show_warning
from gui.llm_utils import DialogStatusConsole

logger = logging.getLogger(__name__)

_SPLITTER_KEY = "splitter_state"

# Workers orphaned at dialog close live here until their run() returns,
# preventing Python GC from destroying a QThread that is still running.
_ORPHAN_WORKERS = set()


class StyleAnalysisWorker(QThread):
    """Runs StyleAnalysisService.derive off the UI thread."""
    progress = Signal(str)
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, service, paths, parent=None):
        super().__init__(parent)
        self._service = service
        self._paths = list(paths)

    def run(self):
        try:
            data = self._service.derive(self._paths,
                                        progress_cb=self.progress.emit)
            self.finished_ok.emit(data)
        except Exception as e:  # noqa: BLE001 - report to UI, never crash thread
            self.failed.emit(str(e))


class StyleManagerDialog(DialogCleanupMixin, QDialog, OperationGuardMixin):
    """Left: style list. Right: details + refs grid + analyze. Bottom: console."""

    def __init__(self, config, store: Optional[StyleStore] = None, parent=None):
        super().__init__(parent)
        self.config = config
        self.store = store or StyleStore()
        self._worker = None  # Task 13
        self.settings = QSettings("ImageAI", "StyleManagerDialog")
        self.setWindowTitle("Style Manager")
        self.resize(980, 680)
        self._build_ui()
        # init_operation_guard runs after UI construction so it can pick up
        # self.status_console (an alias for self.console — see _build_ui).
        self.init_operation_guard()
        self._load_styles()

    # ---- UI construction -------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        self.v_splitter = standard_splitter(Qt.Vertical, self)
        outer.addWidget(self.v_splitter)

        top = QWidget()
        top_layout = QHBoxLayout(top)

        # Left pane: list + list-level buttons
        left = QWidget()
        left_l = QVBoxLayout(left)
        self.style_list = QListWidget()
        left_l.addWidget(self.style_list)
        row1 = QHBoxLayout()
        self.new_btn = QPushButton("New")
        self.duplicate_btn = QPushButton("Duplicate")
        self.delete_btn = QPushButton("Delete")
        for b in (self.new_btn, self.duplicate_btn, self.delete_btn):
            row1.addWidget(b)
        left_l.addLayout(row1)
        row2 = QHBoxLayout()
        self.import_btn = QPushButton("Import…")
        self.export_btn = QPushButton("Export…")
        row2.addWidget(self.import_btn)
        row2.addWidget(self.export_btn)
        left_l.addLayout(row2)
        top_layout.addWidget(left, stretch=1)

        # Right pane: details
        right = QWidget()
        right_l = QVBoxLayout(right)
        form_row = QHBoxLayout()
        form_row.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit()
        form_row.addWidget(self.name_edit, stretch=1)
        form_row.addWidget(QLabel("Description:"))
        self.desc_edit = QLineEdit()
        form_row.addWidget(self.desc_edit, stretch=2)
        right_l.addLayout(form_row)

        right_l.addWidget(QLabel(
            f"Reference images (check up to {EXEMPLAR_DEFAULT_CAP} as exemplars "
            f"sent to image-capable providers):"))
        self.refs_list = QListWidget()
        self.refs_list.setViewMode(QListView.IconMode)
        self.refs_list.setIconSize(QPixmap(96, 96).size())
        self.refs_list.setResizeMode(QListView.Adjust)
        right_l.addWidget(self.refs_list, stretch=2)
        ref_row = QHBoxLayout()
        self.add_files_btn = QPushButton("Add Files…")
        self.add_folder_btn = QPushButton("Add Folder…")
        self.remove_ref_btn = QPushButton("Remove Selected")
        for b in (self.add_files_btn, self.add_folder_btn, self.remove_ref_btn):
            ref_row.addWidget(b)
        ref_row.addStretch()
        right_l.addLayout(ref_row)

        llm_row = QHBoxLayout()
        llm_row.addWidget(QLabel("Vision LLM:"))
        self.llm_provider_combo = QComboBox()
        self.llm_provider_combo.addItems(["openai", "anthropic", "gemini"])
        llm_row.addWidget(self.llm_provider_combo)
        self.llm_model_combo = QComboBox()
        self.llm_model_combo.setEditable(True)
        llm_row.addWidget(self.llm_model_combo, stretch=1)
        self.analyze_btn = QPushButton("Analyze Images")
        llm_row.addWidget(self.analyze_btn)
        right_l.addLayout(llm_row)

        right_l.addWidget(QLabel("Style prompt text (editable — this is what "
                                 "gets injected):"))
        self.prompt_text_edit = QTextEdit()
        self.prompt_text_edit.setMaximumHeight(90)
        right_l.addWidget(self.prompt_text_edit)
        place_row = QHBoxLayout()
        place_row.addWidget(QLabel("Placement:"))
        self.placement_combo = QComboBox()
        self.placement_combo.addItems(["suffix", "prefix"])
        place_row.addWidget(self.placement_combo)
        place_row.addStretch()
        self.save_btn = QPushButton("&Save Style")
        place_row.addWidget(self.save_btn)
        right_l.addLayout(place_row)
        right_l.addWidget(QLabel("Derived descriptor (read-only):"))
        self.descriptor_view = QTextEdit()
        self.descriptor_view.setReadOnly(True)
        self.descriptor_view.setMaximumHeight(110)
        right_l.addWidget(self.descriptor_view)
        top_layout.addWidget(right, stretch=3)

        self.v_splitter.addWidget(top)
        self.console = DialogStatusConsole("Analysis Console", self)
        # OperationGuardMixin looks for `status_console`; the binding widget
        # name required by Task 13 is `console` — alias so both work.
        self.status_console = self.console
        self.v_splitter.addWidget(self.console)
        if not restore_splitter(self.settings, _SPLITTER_KEY, self.v_splitter):
            self.v_splitter.setSizes([520, 160])

        set_default_button(self, self.save_btn)
        bind_primary_action(self, self._save_current)

        # wiring
        self.style_list.currentRowChanged.connect(self._on_selected)
        self.new_btn.clicked.connect(self._on_new)
        self.duplicate_btn.clicked.connect(self._on_duplicate)
        self.delete_btn.clicked.connect(self._on_delete)
        self.import_btn.clicked.connect(self._on_import)
        self.export_btn.clicked.connect(self._on_export)
        self.add_files_btn.clicked.connect(self._on_add_files)
        self.add_folder_btn.clicked.connect(self._on_add_folder)
        self.remove_ref_btn.clicked.connect(self._on_remove_ref)
        self.save_btn.clicked.connect(self._save_current)
        self.analyze_btn.clicked.connect(self._on_analyze)
        self.llm_provider_combo.currentTextChanged.connect(self._on_llm_provider_changed)
        self._on_llm_provider_changed(self.llm_provider_combo.currentText())

    # ---- data <-> widgets ------------------------------------------------

    def _load_styles(self, select_id: Optional[str] = None):
        self.style_list.clear()
        for s in self.store.list_styles():
            item = QListWidgetItem(s.name)
            item.setData(Qt.UserRole, s.id)
            self.style_list.addItem(item)
            if select_id and s.id == select_id:
                self.style_list.setCurrentItem(item)
        if self.style_list.currentRow() < 0 and self.style_list.count():
            self.style_list.setCurrentRow(0)

    def _current_style(self) -> Optional[Style]:
        item = self.style_list.currentItem()
        if item is None:
            return None
        return self.store.get(item.data(Qt.UserRole))

    def _on_selected(self, _row: int):
        # A derived descriptor only ever belongs to the style it was analyzed
        # for — never carry it across a selection change.
        self._pending_descriptor = None
        s = self._current_style()
        if s is None:
            return
        self.name_edit.setText(s.name)
        self.desc_edit.setText(s.description)
        self.prompt_text_edit.setPlainText(s.prompt_text)
        self.placement_combo.setCurrentText(s.placement)
        self.descriptor_view.setPlainText(
            json.dumps(s.descriptor.to_dict(), indent=2, ensure_ascii=False))
        self.refs_list.clear()
        base = self.store.style_dir(s.id)
        for rel in s.reference_images:
            item = QListWidgetItem(Path(rel).name)
            item.setData(Qt.UserRole, rel)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if rel in s.exemplars else Qt.Unchecked)
            p = base / rel
            if p.exists():
                item.setIcon(QIcon(QPixmap(str(p)).scaled(
                    96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
            self.refs_list.addItem(item)

    def _collect_exemplars(self) -> List[str]:
        out = []
        for i in range(self.refs_list.count()):
            item = self.refs_list.item(i)
            if item.checkState() == Qt.Checked:
                out.append(item.data(Qt.UserRole))
        return out

    def _save_current(self):
        s = self._current_style()
        if s is None:
            return
        s.name = self.name_edit.text().strip() or s.name
        s.description = self.desc_edit.text().strip()
        s.prompt_text = self.prompt_text_edit.toPlainText().strip()
        s.placement = self.placement_combo.currentText()
        exemplars = self._collect_exemplars()
        if not exemplars and s.reference_images:
            exemplars = s.reference_images[:EXEMPLAR_DEFAULT_CAP]
            self.console.log(
                f"No exemplars starred — auto-selected the first {len(exemplars)}.",
                "INFO")
        elif len(exemplars) > EXEMPLAR_DEFAULT_CAP:
            show_warning(self, "Style Manager",
                         f"Only the first {EXEMPLAR_DEFAULT_CAP} checked images "
                         f"are used as exemplars.")
            exemplars = exemplars[:EXEMPLAR_DEFAULT_CAP]
        s.exemplars = exemplars
        pending = getattr(self, "_pending_descriptor", None)
        if pending:
            s.descriptor = StyleDescriptor.from_dict(pending)
            self._pending_descriptor = None
        self.store.save(s)
        self.console.log(f"Saved style '{s.name}'", "SUCCESS")
        self._load_styles(select_id=s.id)

    # ---- list-level actions ---------------------------------------------

    def _on_new(self):
        name, ok = QInputDialog.getText(self, "New Style", "Style name:")
        if not ok or not name.strip():
            return
        s = Style(id=self.store.new_id(name.strip()), name=name.strip())
        self.store.save(s)
        self._load_styles(select_id=s.id)

    def _on_duplicate(self):
        s = self._current_style()
        if s is None:
            return
        dup = copy.deepcopy(s)
        dup.id = self.store.new_id(s.name)
        dup.name = f"{s.name} copy"
        dup.reference_images, dup.exemplars = [], []
        # Copy refs one at a time and map exemplars by identity (the source
        # rel path), not by position — a starred image isn't necessarily a
        # prefix of reference_images, and a missing/unreadable source file
        # must not shift the mapping for everything after it.
        for rel in s.reference_images:
            src = self.store.style_dir(s.id) / rel
            if not src.exists():
                continue
            added = self.store.add_reference_images(dup, [src])
            if added and rel in s.exemplars:
                dup.exemplars.append(added[0])
        self.store.save(dup)
        self._load_styles(select_id=dup.id)

    def _on_delete(self):
        s = self._current_style()
        if s is None:
            return
        answer = show_question(self, "Delete Style",
                               f"Delete style '{s.name}' and its images?")
        if answer not in (True, QMessageBox.Yes):
            return
        self.store.delete(s.id)
        self._load_styles()

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Style", "",
                                              "Style zip (*.zip)")
        if not path:
            return
        imported = self.store.import_zip(Path(path))
        if imported is None:
            show_error(self, "Style Manager", f"Not a valid style zip: {path}")
            return
        self.console.log(f"Imported '{imported.name}'", "SUCCESS")
        self._load_styles(select_id=imported.id)

    def _on_export(self):
        s = self._current_style()
        if s is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Style",
                                              f"{s.id}.zip", "Style zip (*.zip)")
        if not path:
            return
        if self.store.export_zip(s.id, Path(path)):
            self.console.log(f"Exported to {path}", "SUCCESS")

    # ---- reference images ------------------------------------------------

    def _on_add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Reference Images", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        self._add_paths([Path(p) for p in paths])

    def _on_add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Add Folder of Images")
        if not d:
            return
        exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        self._add_paths([p for p in sorted(Path(d).iterdir())
                         if p.suffix.lower() in exts])

    def _add_paths(self, paths):
        s = self._current_style()
        if s is None or not paths:
            return
        added = self.store.add_reference_images(s, paths)
        self.store.save(s)
        self.console.log(f"Added {len(added)} image(s)", "INFO")
        self._on_selected(self.style_list.currentRow())

    def _on_remove_ref(self):
        s = self._current_style()
        item = self.refs_list.currentItem()
        if s is None or item is None:
            return
        self.store.remove_reference_image(s, item.data(Qt.UserRole))
        self.store.save(s)
        self._on_selected(self.style_list.currentRow())

    # ---- vision LLM combos -------------------------------------------------

    def _on_llm_provider_changed(self, provider_id: str):
        self.llm_model_combo.clear()
        models = get_provider_models(provider_id)
        if models:
            self.llm_model_combo.addItems(models)

    # ---- analysis ----------------------------------------------------------

    def _on_analyze(self):
        s = self._current_style()
        if s is None:
            show_warning(self, "Style Manager",
                         "Select or create a style before analyzing.")
            return
        paths = self.store.resolve_refs(s)
        if not paths:
            show_warning(self, "Style Manager",
                         "Add reference images before analyzing.")
            return
        from core.styles.analyzer import StyleAnalysisError, StyleAnalysisService
        try:
            service = StyleAnalysisService(
                self.config,
                provider=self.llm_provider_combo.currentText(),
                model=self.llm_model_combo.currentText().strip() or None)
        except StyleAnalysisError as e:
            show_error(self, "Style Manager", str(e))
            return
        if not self.start_operation("analyze"):
            return
        self._pending_descriptor = None
        self.analyze_btn.setEnabled(False)
        self.console.separator()
        self.console.log(
            f"Analyzing {len(paths)} image(s) with {service.model}...", "INFO")
        # No Qt parent: dialog destruction must never cascade into a running
        # QThread. Lifecycle is managed explicitly (see on_dialog_close).
        self._worker = StyleAnalysisWorker(service, paths)
        self._worker.progress.connect(lambda m: self.console.log(m, "INFO"))
        self._worker.finished_ok.connect(self._on_analysis_done)
        self._worker.failed.connect(self._on_analysis_failed)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_analysis_done(self, data: dict):
        self.end_operation()
        self.analyze_btn.setEnabled(True)
        # Non-destructive: show in the editable fields; user must Save.
        self.prompt_text_edit.setPlainText(data.get("prompt_text", ""))
        self.descriptor_view.setPlainText(
            json.dumps(data.get("descriptor", {}), indent=2, ensure_ascii=False))
        self._pending_descriptor = data.get("descriptor", {})
        self.console.log("Analysis complete — review, then Save Style.", "SUCCESS")

    def _on_analysis_failed(self, message: str):
        self.end_operation()
        self.analyze_btn.setEnabled(True)
        self.console.log(f"Analysis failed: {message}", "ERROR")
        show_error(self, "Style Manager", f"Style analysis failed:\n{message}")

    # ---- lifecycle -------------------------------------------------------

    def on_dialog_close(self):
        w = self._worker
        if w is not None and w.isRunning():
            w.requestInterruption()
            if not w.wait(2000):
                # Still running (LLM call in flight): detach it from the UI
                # and keep it alive until it finishes on its own — the worker
                # is unparented, so nothing else holds a live reference.
                for sig in (w.progress, w.finished_ok, w.failed):
                    try:
                        sig.disconnect()
                    except (TypeError, RuntimeError):
                        pass
                _ORPHAN_WORKERS.add(w)
                w.finished.connect(lambda w=w: _ORPHAN_WORKERS.discard(w))
            self._worker = None
        persist_splitter(self.settings, _SPLITTER_KEY, self.v_splitter)
