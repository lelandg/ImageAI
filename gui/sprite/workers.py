"""SpriteWorker: one QThread per long-running sprite job (design §1.1).

The job is a callable ``job(progress, token) -> object``. ``progress`` has the
``ProgressFn`` shape ``(stage, done, total, message)``; ``token`` is the
worker's own ``CancelToken``. Signals:

- ``progress(str, int, int, str)`` — forwarded from the job.
- ``finished(object)`` — the job's return value. This name shadows
  ``QThread.finished()``; use ``wait()`` / ``isRunning()`` for lifecycle.
- ``failed(str)`` — ``SpriteGenerationError.user_message`` or ``str(exc)``.
- ``cancelled()`` — the job raised ``Cancelled`` (or returned after cancel).

Connect these to bound methods of QObjects so the slot runs on the GUI thread.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from PySide6.QtCore import QThread, Signal

from core.sprite.generation.errors import SpriteGenerationError
from core.sprite.pipeline import Cancelled, CancelToken, ProgressFn

logger = logging.getLogger(__name__)

Job = Callable[[ProgressFn, CancelToken], Any]


class SpriteWorker(QThread):
    progress = Signal(str, int, int, str)
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, job: Job, *, label: str = "job", parent=None):
        super().__init__(parent)
        self._job = job
        self._label = label
        self._token = CancelToken()

    @property
    def token(self) -> CancelToken:
        return self._token

    @property
    def label(self) -> str:
        return self._label

    def cancel(self) -> None:
        """Ask the job to stop. The job polls the token between frames/stages."""
        self._token.cancel()

    def _report(self, stage: str, done: int, total: int, message: str) -> None:
        self.progress.emit(str(stage), int(done), int(total), str(message))

    def run(self) -> None:
        try:
            result = self._job(self._report, self._token)
        except Cancelled:
            logger.info("Sprite worker %r cancelled", self._label)
            self.cancelled.emit()
            return
        except SpriteGenerationError as exc:
            message = getattr(exc, "user_message", None) or str(exc)
            logger.error("Sprite worker %r failed: %s", self._label, message, exc_info=True)
            self.failed.emit(message)
            return
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI and the log
            logger.error("Sprite worker %r failed: %s", self._label, exc, exc_info=True)
            self.failed.emit(str(exc))
            return
        if self._token.cancelled:
            logger.info("Sprite worker %r finished after cancel; result dropped", self._label)
            self.cancelled.emit()
            return
        self.finished.emit(result)


class WorkerHost:
    """Mixin for a QObject that runs at most one SpriteWorker at a time.

    ``start_job`` refuses (returns ``None``) while a worker runs; callers log a
    warning. The worker is parented to the host so Qt keeps it alive; the
    host must call ``shutdown()`` before it is destroyed.
    """

    _worker: Optional[SpriteWorker] = None

    def start_job(self, job: Job, *, label: str, on_finished, on_failed,
                  on_cancelled=None, on_progress=None) -> Optional[SpriteWorker]:
        if self.is_busy():
            logger.warning("Sprite job %r refused: %r is still running", label, self._worker.label)
            return None
        worker = SpriteWorker(job, label=label, parent=self)
        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        if on_cancelled is not None:
            worker.cancelled.connect(on_cancelled)
        if on_progress is not None:
            worker.progress.connect(on_progress)
        # Release AFTER the caller's slots (same connection type keeps order).
        worker.finished.connect(self._release_worker)
        worker.failed.connect(self._release_worker)
        worker.cancelled.connect(self._release_worker)
        self._worker = worker
        worker.start()
        return worker

    def is_busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def cancel_running(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def shutdown(self, timeout_ms: int = 5000) -> None:
        """Cancel and join the running worker (call from closeEvent / tab shutdown)."""
        worker = self._worker
        if worker is None:
            return
        worker.cancel()
        if worker.isRunning() and not worker.wait(timeout_ms):
            logger.error("Sprite worker %r did not stop within %d ms", worker.label, timeout_ms)
        self._worker = None

    def _release_worker(self, *_args) -> None:
        self._worker = None
