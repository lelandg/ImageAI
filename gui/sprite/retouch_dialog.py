"""Retouch dialog: one frame, one instruction, one provider call in a SpriteWorker."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, List, Optional, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from core.sprite.generation.retouch import retouch_frame
from core.sprite.models import Rect
from core.sprite.pipeline import CancelToken, ProgressFn
from gui.common.dialog_conventions import DialogCleanupMixin, bind_primary_action, set_default_button
from gui.llm_utils import DialogStatusConsole
from gui.sprite.workers import SpriteWorker

logger = logging.getLogger(__name__)

PROVIDERS = (("google", "Google Gemini"), ("openai", "OpenAI gpt-image"))


class RetouchDialog(DialogCleanupMixin, QDialog):
    """Ctrl+Enter runs the retouch; Escape closes. Never overwrites the source frame."""

    retouched = Signal(object)   # Path of the new frame file
    logLine = Signal(str)        # worker-thread log lines -> console (queued)

    def __init__(self, frame: Path, neighbors: Sequence[Path], *,
                 provider_factory: Callable[[str], object], region: Optional[Rect] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.frame = Path(frame)
        self.neighbors: List[Path] = [Path(n) for n in neighbors]
        self.region: Optional[Rect] = tuple(region) if region else None
        self._provider_factory = provider_factory
        self._worker: Optional[SpriteWorker] = None
        self.result_path: Optional[Path] = None
        self.setWindowTitle(f"Retouch {self.frame.name}")
        self._build_ui()
        self.logLine.connect(self.console.log)

    # ----------------------------------------------------------------- ui
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Vertical, self)
        top = QWidget()
        form = QFormLayout(top)
        self.instruction = QPlainTextEdit()
        self.instruction.setPlaceholderText("What to change in this frame, e.g. 'fix the left hand: five fingers, same glove'")
        form.addRow("Instruction:", self.instruction)
        self.provider_combo = QComboBox()
        for pid, label in PROVIDERS:
            self.provider_combo.addItem(label, pid)
        form.addRow("Provider:", self.provider_combo)
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("provider default")
        form.addRow("Model:", self.model_edit)
        region_row = QHBoxLayout()
        self.region_label = QLabel(self._region_text())
        self.clear_region_btn = QPushButton("Clear region")
        self.clear_region_btn.setEnabled(self.region is not None)
        self.clear_region_btn.clicked.connect(self.clear_region)
        region_row.addWidget(self.region_label, 1)
        region_row.addWidget(self.clear_region_btn)
        form.addRow("Region:", region_row)
        form.addRow("Neighbors:", QLabel(", ".join(p.name for p in self.neighbors) or "(none)"))
        splitter.addWidget(top)
        self.console = DialogStatusConsole("Status Console", self)
        splitter.addWidget(self.console)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.run_btn = QPushButton("Retouch (Ctrl+Enter)")
        self.run_btn.clicked.connect(self.start_retouch)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_retouch)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        for button in (self.run_btn, self.cancel_btn, self.close_btn):
            buttons.addWidget(button)
        root.addLayout(buttons)
        self._primary = bind_primary_action(self, self.start_retouch)
        set_default_button(self, self.run_btn, focus=False)
        self.instruction.setFocus()
        self.resize(560, 480)

    def _region_text(self) -> str:
        if self.region is None:
            return "whole frame"
        x, y, w, h = self.region
        return f"x={x} y={y} w={w} h={h}"

    def clear_region(self) -> None:
        self.region = None
        self.region_label.setText(self._region_text())
        self.clear_region_btn.setEnabled(False)

    # ----------------------------------------------------------------- job
    def build_job(self) -> Callable[[ProgressFn, CancelToken], Path]:
        instruction = self.instruction.toPlainText().strip()
        provider_id = self.provider_combo.currentData()
        model = self.model_edit.text().strip() or None
        frame, neighbors, region = self.frame, list(self.neighbors), self.region
        factory = self._provider_factory
        console_log = self.logLine.emit

        def job(progress: ProgressFn, token: CancelToken) -> Path:
            progress("retouch", 0, 1, f"Retouching {frame.name} with {provider_id}")
            token.raise_if_cancelled()
            provider = factory(provider_id)
            out = retouch_frame(provider, frame, instruction, neighbors=neighbors, region=region,
                                model=model, log=console_log)
            progress("retouch", 1, 1, f"Saved {out.name}")
            return out

        return job

    def start_retouch(self) -> None:
        if self._worker is not None:
            self.console.log("A retouch is already running.", "WARNING")
            return
        if not self.instruction.toPlainText().strip():
            logger.warning("retouch: empty instruction")
            self.console.log("Enter an instruction first.", "WARNING")
            return
        self._worker = SpriteWorker(self.build_job(), parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.console.log(f"Retouch started: {self.frame.name}")
        self._worker.start()

    def cancel_retouch(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.console.log("Cancel requested", "WARNING")

    def _on_progress(self, stage: str, done: int, total: int, message: str) -> None:
        self.console.log(f"[{stage}] {message}")

    def _on_finished(self, result) -> None:
        self.result_path = Path(result)
        self.console.log(f"Retouch saved: {self.result_path}", "SUCCESS")
        self._finish_worker()
        self.retouched.emit(self.result_path)

    def _on_failed(self, message: str) -> None:
        logger.error("retouch failed: %s", message)
        self.console.log(f"Retouch failed: {message}", "ERROR")
        self._finish_worker()

    def _on_cancelled(self) -> None:
        logger.info("retouch cancelled: %s", self.frame.name)
        self.console.log("Retouch cancelled.", "WARNING")
        self._finish_worker()

    def _finish_worker(self) -> None:
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._worker = None

    def on_dialog_close(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait(2000)
            self._worker = None
