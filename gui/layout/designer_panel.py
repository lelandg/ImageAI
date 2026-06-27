"""Designer panel: description/iterate input, status console, LLM worker."""
import logging
from typing import List, Dict, Optional, Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPlainTextEdit, QPushButton, QLabel,
)
from PySide6.QtCore import QThread, Signal

from core.layout import designer
from gui.llm_utils import DialogStatusConsole

logger = logging.getLogger("imageai.layout.designer_panel")

CONTENT_KINDS = ["children", "comic", "comic_strip", "magazine", "newspaper", "scientific", "custom"]


class DesignerWorker(QThread):
    progress = Signal(str)
    proposed = Signal(object)  # DesignerResult
    failed = Signal(str)

    def __init__(self, messages: List[Dict], page_px, completion_fn: Callable[[List[Dict]], str], parent=None):
        super().__init__(parent)
        self._messages = messages
        self._page_px = page_px
        self._completion_fn = completion_fn

    def run(self):
        try:
            self.progress.emit("Designing layout…")
            result = designer.run_design(self._messages, self._page_px, self._completion_fn)
            self.proposed.emit(result)
        except Exception as e:  # noqa: BLE001 - surfaced to UI + log
            logger.error("Designer worker failed: %s", e, exc_info=True)
            self.failed.emit(str(e))


class DesignerPanel(QWidget):
    layoutProposed = Signal(object)  # DesignerResult

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._worker: Optional[DesignerWorker] = None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel("Kind:"))
        self.kind_combo = QComboBox()
        self.kind_combo.addItems(CONTENT_KINDS)
        row.addWidget(self.kind_combo)
        row.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        self.model_combo = QComboBox()
        self._populate_providers()
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        row.addWidget(self.provider_combo)
        row.addWidget(self.model_combo)
        lay.addLayout(row)

        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlaceholderText(
            "Describe the page, or type a change to the current layout…")
        self.prompt_edit.setFixedHeight(70)
        lay.addWidget(self.prompt_edit)

        self.design_btn = QPushButton("Design / Iterate")
        lay.addWidget(self.design_btn)

        # Designer output starts collapsed; the user expands it on demand (it
        # still auto-opens on failure so errors are never hidden).
        self.console_toggle = QPushButton("▶ Show designer output")
        self.console_toggle.setCheckable(True)
        self.console_toggle.toggled.connect(self._on_toggle_console)
        lay.addWidget(self.console_toggle)

        self.console = DialogStatusConsole("Designer")
        self.console.setVisible(False)
        lay.addWidget(self.console)

    def _on_toggle_console(self, shown: bool):
        self.console.setVisible(shown)
        self.console_toggle.setText(
            "▼ Hide designer output" if shown else "▶ Show designer output")

    def _populate_providers(self):
        from core.llm_models import get_all_provider_ids, get_provider_display_name
        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()
        self.provider_combo.addItems([get_provider_display_name(p) for p in get_all_provider_ids()])
        saved = self._config.get_layout_llm_provider() if self._config else None
        if saved:
            idx = self.provider_combo.findText(saved)
            if idx < 0:
                idx = self.provider_combo.findText(saved.capitalize())
            if idx >= 0:
                self.provider_combo.setCurrentIndex(idx)
        self.provider_combo.blockSignals(False)
        self._on_provider_changed(self.provider_combo.currentText())

    def _on_provider_changed(self, provider: str):
        from core.llm_models import get_provider_models
        _, pid = designer.resolve_provider_ids(provider)  # single source of truth
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(get_provider_models(pid) or [])
        self.model_combo.blockSignals(False)

    def content_kind(self) -> str:
        return self.kind_combo.currentText()

    def start_design(self, user_text: str, page_px, current_regions=None,
                     completion_fn: Optional[Callable[[List[Dict]], str]] = None):
        # Don't overwrite a still-running QThread — dropping its only reference
        # risks "QThread: Destroyed while thread is still running".
        if self._worker is not None and self._worker.isRunning():
            self.console.log("A design is already running — please wait.", "WARNING")
            return
        kind = self.content_kind()
        messages = designer.build_messages(kind, page_px, user_text, current_regions)
        self.console.log(f"Designing ({kind}, {page_px[0]}x{page_px[1]})", "INFO")
        self.console.log("Prompt sent to LLM:\n" + messages[-1]["content"], "INFO")
        # Capture whether a completion_fn was injected BEFORE we build the production one.
        injected = completion_fn is not None
        if completion_fn is None:
            provider = self.provider_combo.currentText()
            model = self.model_combo.currentText()
            cfg = self._config
            completion_fn = lambda m: designer.run_completion(cfg, provider, model, m)
        self.design_btn.setEnabled(False)
        self._worker = DesignerWorker(messages, page_px, completion_fn)
        self._worker.progress.connect(lambda msg: self.console.log(msg, "INFO"))
        self._worker.proposed.connect(self._on_proposed)
        self._worker.failed.connect(self._on_failed)
        if injected:
            self._worker.run()      # synchronous for injected/test completions
        else:
            self._worker.start()

    def _on_proposed(self, result):
        self.design_btn.setEnabled(True)
        if result.raw:
            self.console.log("LLM response:\n" + result.raw, "INFO")
        n = len(result.regions) if result.regions else 0
        nov = len(getattr(result, "overlays", []) or [])
        self.console.log(
            f"Proposed layout: {n} regions; {nov} overlay(s); {len(result.questions)} question(s).",
            "SUCCESS")
        for q in result.questions:
            self.console.log(f"Q: {q}", "WARNING")
        self.layoutProposed.emit(result)

    def _on_failed(self, err: str):
        self.design_btn.setEnabled(True)
        if not self.console_toggle.isChecked():
            self.console_toggle.setChecked(True)  # surface the failure (expands the console)
        self.console.log(err, "ERROR")
