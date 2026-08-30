"""Queue panel: one row per action card, cost estimate + actual, Start/Cancel/Retry.

The panel runs ``ActionQueue`` inside a SpriteWorker; the queue owns retries
with backoff (design §1.3) and writes ``CostEntry`` rows. The panel only
reflects card status and logs ``user_message`` for failures.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QProgressBar,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from core.sprite.generation.cost import estimate_action, estimate_project
from core.sprite.generation.errors import SpriteGenerationError
from core.sprite.generation.queue import ActionQueue
from core.sprite.generation.video_route import refine_action
from core.sprite.pipeline import Cancelled, run_pipeline
from gui.common.dialog_conventions import bind_primary_action
from gui.dialog_utils import show_error, show_warning
from gui.sprite.workers import WorkerHost

logger = logging.getLogger(__name__)

COL_ACTION, COL_STATUS, COL_ESTIMATE, COL_ACTUAL = range(4)
HEADERS = ("Action", "Status", "Est. cost", "Actual cost")


def fmt_usd(value: Optional[float]) -> str:
    return "unknown" if value is None else f"${value:.2f}"


class QueuePanel(WorkerHost, QGroupBox):
    queueFinished = Signal(object)   # Dict[action_id, ClipRecord | SpriteGenerationError]
    statusChanged = Signal()
    logMessage = Signal(str, str)

    def __init__(self, config, parent=None):
        super().__init__("Render queue", parent)
        self.config = config
        self.project = None
        self._build()
        self._primary = bind_primary_action(self, self.start, context=Qt.WidgetWithChildrenShortcut)
        self._set_running(False)

    # -- build -------------------------------------------------------------

    def _build(self) -> None:
        root = QVBoxLayout(self)
        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_ACTION, QHeaderView.Stretch)
        for column in (COL_STATUS, COL_ESTIMATE, COL_ACTUAL):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        root.addWidget(self.table, 1)

        self.total_label = QLabel("Sheet estimate: unknown")
        root.addWidget(self.total_label)

        row = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.setToolTip("Render every queued card (Ctrl+Enter)")
        self.start_btn.clicked.connect(self.start)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel)
        self.retry_btn = QPushButton("Retry selected")
        self.retry_btn.clicked.connect(self.retry)
        for button in (self.start_btn, self.cancel_btn, self.retry_btn):
            row.addWidget(button)
        row.addStretch(1)
        root.addLayout(row)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)
        self.status_label = QLabel("")
        root.addWidget(self.status_label)

    def _set_running(self, running: bool) -> None:
        has_project = self.project is not None
        self.start_btn.setEnabled(has_project and not running)
        self.retry_btn.setEnabled(has_project and not running)
        self.cancel_btn.setEnabled(running)
        self.progress.setVisible(running)
        if running:
            self.progress.setRange(0, 0)
        if hasattr(self, "_primary"):
            self._primary.set_enabled(has_project and not running)

    # -- project / rows ----------------------------------------------------

    def _cards(self) -> list:
        return list(self.project.actions) if self.project is not None else []

    def _card(self, action_id: str):
        for card in self._cards():
            if card.id == action_id:
                return card
        return None

    def set_project(self, project) -> None:
        self.project = project
        self.refresh()
        self._set_running(self.is_busy())

    def _estimate(self, card) -> Optional[float]:
        try:
            return estimate_action(self.project.generation, card)
        except Exception as exc:  # noqa: BLE001 - label only, never blocks rendering
            logger.warning("Cost estimate failed for %s: %s", card.name, exc)
            return None

    def refresh(self) -> None:
        self.table.setRowCount(0)
        for card in self._cards():
            row = self.table.rowCount()
            self.table.insertRow(row)
            actual = getattr(card.clip, "actual_usd", None) if card.clip is not None else None
            values = (card.name, card.status, fmt_usd(self._estimate(card)),
                      "-" if actual is None else fmt_usd(actual))
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setData(Qt.UserRole, card.id)
                if column == COL_STATUS and card.error:
                    item.setToolTip(str(card.error))
                self.table.setItem(row, column, item)
        self._refresh_total()

    def _refresh_total(self) -> None:
        if self.project is None:
            self.total_label.setText("Sheet estimate: unknown")
            return
        try:
            usd, unknown = estimate_project(self.project)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Sheet estimate failed: %s", exc)
            usd, unknown = None, len(self._cards())
        if usd is None:
            suffix = f" ({unknown} actions without a verified rate)" if unknown else ""
            self.total_label.setText(f"Sheet estimate: unknown{suffix}")
        elif unknown:
            self.total_label.setText(f"Sheet estimate: {fmt_usd(usd)} + {unknown} unknown")
        else:
            self.total_label.setText(f"Sheet estimate: {fmt_usd(usd)}")

    def selected_ids(self) -> List[str]:
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        return [self.table.item(row, COL_ACTION).data(Qt.UserRole) for row in rows
                if self.table.item(row, COL_ACTION) is not None]

    # -- queue control -----------------------------------------------------

    def enqueue(self, ids: Sequence[str]) -> None:
        for action_id in ids:
            card = self._card(action_id)
            if card is not None:
                card.status = "queued"
                card.error = None
        self.refresh()
        self.statusChanged.emit()

    def _google_credentials(self) -> Optional[dict]:
        api_key = self.config.get_api_key("google")
        if not api_key:
            show_error(self, "Sprite queue", "No Google API key is configured. Add one in Settings.")
            return None
        return {"api_key": api_key, "auth_mode": self.config.get_auth_mode("google")}

    def start(self, ids: Optional[Sequence[str]] = None) -> None:
        if self.project is None:
            show_warning(self, "Sprite queue", "Open a sprite project first.")
            return
        if self.is_busy():
            self.logMessage.emit("The queue is already running.", "WARNING")
            return
        ids = [i for i in (ids or []) if self._card(i) is not None] or \
              [card.id for card in self._cards() if card.status == "queued"]
        if not ids:
            self.logMessage.emit("Nothing queued — press Render on a card first.", "WARNING")
            return
        credentials = self._google_credentials()
        if credentials is None:
            return
        project = self.project
        for action_id in ids:
            self._card(action_id).status = "queued"

        def job(progress, token):
            queue = ActionQueue(project, api_key=credentials["api_key"],
                                auth_mode=credentials["auth_mode"], progress=progress,
                                token=token, log=lambda m: progress("queue", 0, 0, m))
            queue.enqueue(ids)
            return queue.run()

        names = ", ".join(self._card(i).name for i in ids)
        self.logMessage.emit(f"Rendering {len(ids)} card(s): {names}", "INFO")
        worker = self.start_job(job, label="render queue", on_finished=self._on_queue_done,
                                on_failed=self._on_failed, on_cancelled=self._on_cancelled,
                                on_progress=self._on_progress)
        if worker is not None:
            self.refresh()
            self._set_running(True)

    def cancel(self) -> None:
        if self.is_busy():
            self.logMessage.emit("Cancelling the queue… (a running provider job keeps its "
                                 "operation id for recovery)", "WARNING")
            self.cancel_running()

    def retry(self) -> None:
        ids = [i for i in self.selected_ids() if getattr(self._card(i), "status", "") == "failed"]
        if not ids:
            self.logMessage.emit("Select a failed card to retry.", "WARNING")
            return
        self.enqueue(ids)
        self.start(ids)

    def refine(self, action_id: str, instruction: str) -> None:
        card = self._card(action_id)
        if card is None or self.project is None:
            return
        if card.clip is None:
            show_warning(self, "Sprite queue", f"Render {card.name} before refining it.")
            return
        if self.is_busy():
            self.logMessage.emit("The queue is already running.", "WARNING")
            return
        credentials = self._google_credentials()
        if credentials is None:
            return
        clips_dir = Path(self.project.project_dir) / "clips"
        revision = 1
        while (clips_dir / f"{action_id}.r{revision}.mp4").exists():
            revision += 1
        out_mp4 = clips_dir / f"{action_id}.r{revision}.mp4"
        project, clip = self.project, card.clip

        def job(progress, token):
            progress("refine", 0, 0, f"Refining {card.name}: {instruction}")
            clips_dir.mkdir(parents=True, exist_ok=True)
            record = refine_action(clip, instruction, out_mp4, api_key=credentials["api_key"],
                                   log=lambda m: progress("refine", 0, 0, m))
            token.raise_if_cancelled()
            card.clip = record
            card.status = "rendered"
            card.error = None
            try:
                run_pipeline(project, card, upto="stabilize", progress=progress, token=token,
                             force=True)
            except Cancelled:
                raise
            except Exception as exc:  # noqa: BLE001 - the clip is safe; report and continue
                card.error = f"pipeline: {exc}"
                progress("refine", 0, 0, f"Clip saved as {record.path}; pipeline failed: {exc}")
            return record

        self.logMessage.emit(f"Refine requested for {card.name}: {instruction}", "INFO")
        worker = self.start_job(job, label="refine", on_finished=self._on_refine_done,
                                on_failed=self._on_failed, on_cancelled=self._on_cancelled,
                                on_progress=self._on_progress)
        if worker is not None:
            self._set_running(True)

    # -- worker slots ------------------------------------------------------

    def _on_progress(self, stage: str, done: int, total: int, message: str) -> None:
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
        else:
            self.progress.setRange(0, 0)
        self.status_label.setText(f"{stage}: {message}")
        self.logMessage.emit(f"[{stage}] {message}", "INFO")
        if stage in ("render", "extract", "stabilize", "key", "cleanup", "alpha"):
            self.refresh()

    def _on_queue_done(self, results) -> None:
        self._set_running(False)
        self.status_label.setText("")
        results = dict(results or {})
        for action_id, outcome in results.items():
            card = self._card(action_id)
            name = card.name if card is not None else action_id
            if isinstance(outcome, SpriteGenerationError):
                message = getattr(outcome, "user_message", None) or str(outcome)
                self.logMessage.emit(f"{name}: {message}", "ERROR")
            else:
                cost = fmt_usd(getattr(outcome, "actual_usd", None))
                self.logMessage.emit(f"{name}: clip ready ({cost}) → {getattr(outcome, 'path', '')}",
                                     "SUCCESS")
        self.refresh()
        self.statusChanged.emit()
        self.queueFinished.emit(results)

    def _on_refine_done(self, record) -> None:
        self._set_running(False)
        self.status_label.setText("")
        self.logMessage.emit(f"Refined clip ready → {getattr(record, 'path', '')}", "SUCCESS")
        self.refresh()
        self.statusChanged.emit()

    def _on_failed(self, message: str) -> None:
        self._set_running(False)
        self.status_label.setText("")
        self.logMessage.emit(message, "ERROR")
        self.refresh()
        self.statusChanged.emit()
        show_error(self, "Sprite queue", message)

    def _on_cancelled(self) -> None:
        self._set_running(False)
        self.status_label.setText("Cancelled.")
        self.logMessage.emit("Queue cancelled.", "WARNING")
        self.refresh()
        self.statusChanged.emit()

    def _on_worker_idle(self) -> None:
        """A worker orphaned by a timed-out ``shutdown()`` finally stopped."""
        self._set_running(False)
