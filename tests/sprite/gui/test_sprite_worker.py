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


def test_worker_host_shutdown_timeout_logs_error(qapp, caplog):
    """shutdown() times out (Minor 1): logs an error but still returns."""
    host = _Host()

    def slow_to_cancel(progress, token):
        # Ignores the token past the shutdown timeout, then cooperates so the
        # thread eventually exits and the test doesn't leak it.
        start = time.time()
        while time.time() - start < 0.2:
            pass
        while True:
            token.raise_if_cancelled()
            time.sleep(0.005)

    worker = host.start_job(slow_to_cancel, label="stubborn",
                            on_finished=lambda r: None, on_failed=lambda m: None)
    assert worker is not None
    with caplog.at_level("ERROR"):
        host.shutdown(timeout_ms=50)
    assert any("did not stop within" in record.message for record in caplog.records)
    assert worker.wait(2000)  # let the thread actually exit before the test ends


def test_worker_host_starts_next_job_from_on_finished(qapp):
    """Queue-draining pattern (review finding, Task 1 fix round 1): starting
    job B from inside job A's on_finished must not let A's queued release
    event (delivered after B is already the current worker) orphan B."""
    host = _Host()
    calls = {"a": 0, "b": 0}
    result_b = []
    started = {}

    def job_a(progress, token):
        return "a-done"

    def job_b(progress, token):
        return "b-done"

    def on_finished_a(result):
        calls["a"] += 1

        def on_finished_b(r):
            calls["b"] += 1
            result_b.append(r)

        b_worker = host.start_job(job_b, label="b",
                                  on_finished=on_finished_b, on_failed=lambda m: None)
        assert b_worker is not None, "job B was refused: A's release fired before B started"
        assert host._worker is b_worker
        assert host.is_busy()
        started["b"] = b_worker

    first = host.start_job(job_a, label="a", on_finished=on_finished_a, on_failed=lambda m: None)
    assert first is not None
    assert first.wait(5000)
    for _ in range(5):
        qapp.processEvents()
    assert "b" in started, "on_finished_a did not run"
    assert started["b"].wait(5000)
    for _ in range(5):
        qapp.processEvents()
    assert calls == {"a": 1, "b": 1}
    assert result_b == ["b-done"]
    assert not host.is_busy()
    assert host._worker is None
