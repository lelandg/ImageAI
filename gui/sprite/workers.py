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

import functools
import logging
from typing import Any, Callable, List, Optional

from PySide6.QtCore import QThread, Signal

from core.sprite.generation.errors import SpriteGenerationError
from core.sprite.pipeline import Cancelled, CancelToken, ProgressFn

logger = logging.getLogger(__name__)

# Strong references to every orphaned worker until its thread exits. An
# orphan's only other owners form a pure Python cycle (worker -> reaper
# partial -> host -> host._orphans -> worker); the cyclic garbage collector
# may collect that cycle while the thread still runs, and deleting a running
# QThread aborts the process (5b Task 7 finding).
_LIVE_ORPHANS: "set[SpriteWorker]" = set()

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
        self._terminal_delivered = False

    @property
    def token(self) -> CancelToken:
        return self._token

    @property
    def terminal_delivered(self) -> bool:
        """True once finished/failed/cancelled has been delivered on the GUI thread.

        ``run()`` emits its terminal signal before the thread exits and the
        event is delivered later, so ``isRunning()`` is False for a stretch in
        which the result has not reached the host yet. ``WorkerHost`` uses this
        flag — not ``isRunning()`` — to decide whether it is still busy
        (final review, Minor 5).
        """
        return self._terminal_delivered

    def mark_terminal(self) -> None:
        """Called by the host from the terminal signal, before the caller's slot."""
        self._terminal_delivered = True

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

    A worker that outlives ``shutdown()``'s bounded join becomes an *orphan*:
    the host keeps a reference to it, detaches it from the host widget and
    reaps it when its thread finally exits. An orphan still counts as busy, so
    no second job can write the same output paths, and the host widget can be
    destroyed without Qt aborting on "QThread: Destroyed while thread is still
    running" (final review, Important 1 / Minor 5).
    """

    _worker: Optional[SpriteWorker] = None
    _orphans: Optional[List[SpriteWorker]] = None

    def _orphan_list(self) -> List[SpriteWorker]:
        """The host's orphan list, created on first use.

        ``WorkerHost`` is a mixin with no ``__init__`` of its own, so the list
        cannot be created in a constructor without forcing every subclass to
        cooperate; this one accessor owns the lazy creation.
        """
        orphans = getattr(self, "_orphans", None)
        if orphans is None:
            orphans = []
            self._orphans = orphans
        return orphans

    def start_job(self, job: Job, *, label: str, on_finished, on_failed,
                  on_cancelled=None, on_progress=None) -> Optional[SpriteWorker]:
        if self.is_busy():
            logger.warning("Sprite job %r refused: %r is still running", label, self.busy_label)
            return None
        worker = SpriteWorker(job, label=label, parent=self)
        # FIRST connection, so it runs before the caller's slots: the worker
        # stops counting as live the moment its terminal event reaches the GUI
        # thread. That closes the Minor 5 window (a new job started between the
        # emit and the delivery) while keeping the queue-drain pattern working
        # (starting job B from inside job A's on_finished).
        mark = functools.partial(self._mark_terminal, worker)
        worker.finished.connect(mark)
        worker.failed.connect(mark)
        worker.cancelled.connect(mark)
        # Guarded: a finished/failed/cancelled event queued for a worker that
        # shutdown()/_release_worker already released (e.g. the host switched
        # to a different project/worker before the event was delivered) must
        # be dropped rather than run against whatever is now the host's live
        # state (review finding, Task 8 fix round 2 - stale queued events).
        worker.finished.connect(functools.partial(self._guarded, worker, "finished", on_finished))
        worker.failed.connect(functools.partial(self._guarded, worker, "failed", on_failed))
        if on_cancelled is not None:
            worker.cancelled.connect(functools.partial(self._guarded, worker, "cancelled", on_cancelled))
        if on_progress is not None:
            # Guarded like the terminal signals: progress from a released or
            # orphaned worker must not drive the host's current UI/project
            # (final review, Minor 3).
            worker.progress.connect(functools.partial(self._guarded, worker, "progress", on_progress))
        # Release AFTER the caller's slots (same connection type keeps order).
        # Bound to this worker instance: a queued release event for a worker
        # that has already been superseded by a newer one (e.g. the caller
        # started job B from inside job A's on_finished) must not clear the
        # host's current _worker.
        release = functools.partial(self._release_worker, worker)
        worker.finished.connect(release)
        worker.failed.connect(release)
        worker.cancelled.connect(release)
        self._worker = worker
        worker.start()
        return worker

    def _guarded(self, worker: SpriteWorker, signal_name: str, callback, *args) -> None:
        """Run ``callback(*args)`` only while ``worker`` is still the host's live worker.

        Dropping a stale event here — rather than in every panel's own
        on_finished/on_failed/on_cancelled — protects every ``WorkerHost``
        subclass at the source, including future ones.
        """
        if self._worker is not worker:
            logger.debug("Dropped stale %s from released worker %r", signal_name, worker.label)
            return
        callback(*args)

    def _mark_terminal(self, worker: SpriteWorker, *_args) -> None:
        worker.mark_terminal()

    def _live_worker(self) -> Optional[SpriteWorker]:
        """The host's worker while its result has not been delivered yet.

        Not ``isRunning()``: ``run()`` emits its terminal signal before the
        thread exits, so an ``isRunning()`` test leaves a window in which a
        second job starts and the first result is then dropped as stale
        (final review, Minor 5).
        """
        worker = self._worker
        if worker is not None and not worker.terminal_delivered:
            return worker
        return None

    def is_busy(self) -> bool:
        """True while this host has a live worker or an unreaped orphan.

        An orphan counts as busy until ``_reap_orphan`` removes it — not
        until ``isRunning()`` drops — so the emit-to-delivery window that
        ``terminal_delivered`` closes for the live worker stays closed for
        orphans too (re-review, Minor 5 residual).
        """
        if self._live_worker() is not None:
            return True
        return bool(self._orphan_list())

    @property
    def busy_label(self) -> Optional[str]:
        """The busy worker's label, or ``None`` when idle.

        Public accessor for callers (e.g. ``SpriteTab``) that want to report
        what job is being cancelled without reaching into the private
        ``_worker`` attribute. Falls back to a still-running orphan's label so
        it never dereferences a cleared ``_worker``.
        """
        worker = self._live_worker()
        if worker is not None:
            return worker.label
        for orphan in self._orphan_list():
            return orphan.label
        return None

    def cancel_running(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def shutdown(self, timeout_ms: int = 5000) -> bool:
        """Cancel and join the running worker (call from closeEvent / tab shutdown).

        Returns True when the worker stopped inside ``timeout_ms``. On a
        timeout the worker is NOT dropped: it becomes an orphan of this host
        (see the class docstring) and False is returned so the caller can
        decide to wait longer — ``join_orphans()`` — before the widget tree is
        destroyed.
        """
        worker = self._worker
        if worker is not None:
            worker.cancel()
            if worker.isRunning() and not worker.wait(timeout_ms):
                logger.error("Sprite worker %r did not stop within %d ms; kept as an orphan",
                             worker.label, timeout_ms)
                # Clear the live slot BEFORE adopting, so a synchronous reap
                # inside _adopt_orphan sees the post-shutdown state.
                self._worker = None
                self._adopt_orphan(worker)
            self._worker = None
        # An orphan from an EARLIER timed-out shutdown still counts: the caller
        # must join_orphans() before the widget tree is destroyed (re-review,
        # Important: second shutdown() must not report an all-clear).
        return not self._orphan_list()

    def _adopt_orphan(self, worker: SpriteWorker) -> None:
        """Keep ``worker`` alive and detached until its thread exits.

        ``setParent(None)`` takes the QThread out of the host widget's child
        tree, so destroying the widget cannot destroy a running thread. The
        reaper is wired to the worker's own Python ``finished``/``failed``/
        ``cancelled`` signals — ``run()`` always emits exactly one of them
        before it returns — because the Python ``finished = Signal(object)``
        shadows ``QThread.finished()``.
        """
        worker.setParent(None)
        self._orphan_list().append(worker)
        _LIVE_ORPHANS.add(worker)
        reaper = functools.partial(self._reap_orphan, worker)
        worker.finished.connect(reaper)
        worker.failed.connect(reaper)
        worker.cancelled.connect(reaper)
        if not worker.isRunning():
            # The job ended between the wait() timeout and the connect above,
            # so no terminal signal is left to trigger the reaper.
            self._reap_orphan(worker)

    def _reap_orphan(self, worker: SpriteWorker, *_args) -> None:
        """Drop a finished orphan and tell the host it may be idle again.

        Idempotent: the orphan list is the single guard, so a terminal signal
        that arrives after ``_adopt_orphan``'s direct call is a no-op.
        """
        orphans = self._orphan_list()
        if worker not in orphans:
            return
        orphans.remove(worker)
        worker.wait()  # the job emitted its terminal signal; the thread is exiting
        _LIVE_ORPHANS.discard(worker)
        logger.info("Sprite orphan worker %r finished after shutdown", worker.label)
        worker.deleteLater()
        if self.is_busy():
            return  # a new live worker started meanwhile; its own slots re-sync the UI
        try:
            self._on_worker_idle()
        except RuntimeError as exc:
            # The host widget was already destroyed (app exit drained the
            # queued terminal event after teardown); nothing left to re-sync.
            logger.debug("Sprite orphan idle hook skipped: %s", exc)

    def _on_worker_idle(self) -> None:
        """Hook: the last orphan stopped and the host is idle. Panels re-sync their UI."""

    def join_orphans(self, timeout_ms: Optional[int] = None) -> bool:
        """Wait for every orphan of this host. ``None`` waits without a bound.

        Call this before the host widget is destroyed when ``shutdown()``
        returned False; a QThread destroyed while it runs aborts the process.
        """
        joined = True
        for worker in list(self._orphan_list()):
            if timeout_ms is None:
                worker.wait()
            elif not worker.wait(timeout_ms):
                joined = False
        return joined

    def _release_worker(self, worker: SpriteWorker, *_args) -> None:
        """Clear ``self._worker`` only if it still points at ``worker``.

        A queued finished/failed/cancelled event for a worker that a later
        ``start_job`` call has already superseded must be a no-op, or it
        would orphan the new worker (see review finding, Task 1 fix round 1).
        """
        if self._worker is worker:
            self._worker = None
        # The terminal event has been delivered and run() returned right after
        # emitting it, so the thread is exiting: join it and detach it from the
        # host. A finished QThread left as a child of a parentless host (e.g.
        # ExportDialog) rides along when the cyclic garbage collector frees
        # that host, and Qt aborts if any such child still runs (5b Task 7
        # finding). Detached and joined, the worker is freed by Python when
        # its last reference drops — never while its thread runs. (deleteLater
        # here crashes: the worker's own signal delivery is still on the stack.)
        worker.wait()
        worker.setParent(None)
