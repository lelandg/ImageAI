# tests/sprite/gui/test_sprite_worker.py
"""SpriteWorker contract (design §1.1): progress, finished(object), failed, cancelled."""
import time

from PySide6.QtWidgets import QApplication, QWidget

from core.sprite.generation.errors import SpriteGenerationError
from gui.sprite.workers import SpriteWorker, WorkerHost


class _UserError(SpriteGenerationError):
    """Independent of the real constructor: sets the two documented attributes."""

    def __init__(self, message):
        Exception.__init__(self, message)
        self.user_message = message
        self.retryable = False


def _run(worker, timeout_ms=5000):
    worker.start()
    assert worker.wait(timeout_ms)
    # The worker QObject keeps the creating (main) thread's affinity, so Qt
    # delivers cross-thread signals via the queued connection even to plain
    # lambdas (PySide6 6.11.1) - pump the queue once the thread has joined.
    for _ in range(3):
        QApplication.processEvents()


def test_finished_carries_job_result(qapp):
    seen = []
    worker = SpriteWorker(lambda progress, token: 42, label="answer")
    worker.finished.connect(lambda result: seen.append(result))
    _run(worker)
    assert seen == [42]
    assert worker.label == "answer"


def test_progress_forwards_stage_tuple(qapp):
    seen = []

    def job(progress, token):
        progress("extract", 1, 4, "frame 1")
        return None

    worker = SpriteWorker(job)
    worker.progress.connect(lambda *args: seen.append(args))
    _run(worker)
    assert seen == [("extract", 1, 4, "frame 1")]


def test_failed_uses_user_message(qapp):
    seen = []

    def job(progress, token):
        raise _UserError("Quota exceeded - try again later")

    worker = SpriteWorker(job)
    worker.failed.connect(lambda message: seen.append(message))
    _run(worker)
    assert seen == ["Quota exceeded - try again later"]


def test_unexpected_exception_is_reported_not_raised(qapp, caplog):
    seen = []

    def job(progress, token):
        raise RuntimeError("boom")

    worker = SpriteWorker(job)
    worker.failed.connect(lambda message: seen.append(message))
    with caplog.at_level("ERROR"):
        _run(worker)
    assert seen == ["boom"]
    assert any("boom" in record.message for record in caplog.records)


def test_cancel_sets_token_and_emits_cancelled(qapp):
    outcome = []

    def job(progress, token):
        while True:
            token.raise_if_cancelled()
            time.sleep(0.005)

    worker = SpriteWorker(job)
    worker.cancelled.connect(lambda: outcome.append("cancelled"))
    worker.failed.connect(lambda message: outcome.append(("failed", message)))
    worker.start()
    worker.cancel()
    assert worker.wait(5000)
    for _ in range(3):
        QApplication.processEvents()
    assert worker.token.cancelled
    assert outcome == ["cancelled"]


class _Host(WorkerHost, QWidget):
    pass


def test_worker_host_runs_one_job_at_a_time(qapp):
    host = _Host()
    results = []

    def slow(progress, token):
        time.sleep(0.05)
        return "done"

    first = host.start_job(slow, label="a",
                           on_finished=lambda r: results.append(r),
                           on_failed=lambda m: results.append(("failed", m)))
    assert first is not None and host.is_busy()
    second = host.start_job(slow, label="b",
                            on_finished=lambda r: None, on_failed=lambda m: None)
    assert second is None  # busy: refused, not queued
    assert first.wait(5000)
    for _ in range(3):
        qapp.processEvents()
    assert results == ["done"]
    assert not host.is_busy()


def test_worker_host_shutdown_cancels_and_joins(qapp):
    host = _Host()

    def forever(progress, token):
        while True:
            token.raise_if_cancelled()
            time.sleep(0.005)

    worker = host.start_job(forever, label="loop",
                            on_finished=lambda r: None, on_failed=lambda m: None)
    assert worker is not None
    host.shutdown(timeout_ms=5000)
    assert not worker.isRunning()
    assert worker.token.cancelled
