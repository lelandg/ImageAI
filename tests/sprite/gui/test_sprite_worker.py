# tests/sprite/gui/test_sprite_worker.py
"""SpriteWorker contract (design §1.1): progress, finished(object), failed, cancelled."""
import threading
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


class _IdleHost(_Host):
    """Records the ``_on_worker_idle`` hook the panels override."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.idle_calls = 0

    def _on_worker_idle(self) -> None:
        self.idle_calls += 1


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
    assert host.shutdown(timeout_ms=5000) is True
    assert not worker.isRunning()
    assert worker.token.cancelled
    assert host._orphan_list() == []


def test_worker_host_shutdown_timeout_logs_error(qapp, caplog):
    """shutdown() times out: logs an error and reports False to the caller."""
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
        assert host.shutdown(timeout_ms=50) is False
    assert any("did not stop within" in record.message for record in caplog.records)
    assert worker.wait(2000)  # let the thread actually exit before the test ends
    for _ in range(5):
        qapp.processEvents()  # reap the orphan so the test leaves nothing behind


def test_new_job_is_refused_while_the_previous_result_is_undelivered(qapp):
    """Minor 5: the emit → delivery window must not admit a second job.

    ``run()`` emits ``finished`` and then returns, so ``isRunning()`` is
    already False while the result is still queued. A job started in that
    window used to take the host's ``_worker`` slot and ``_guarded`` then
    dropped the first result.
    """
    host = _Host()
    calls = []
    worker = host.start_job(lambda progress, token: "a-done", label="a",
                            on_finished=lambda r: calls.append(r), on_failed=lambda m: None)
    assert worker is not None
    assert worker.wait(5000)     # the thread exited; finished is queued, not delivered
    assert not worker.isRunning()
    assert host.is_busy()
    refused = host.start_job(lambda progress, token: "b-done", label="b",
                             on_finished=lambda r: calls.append(r), on_failed=lambda m: None)
    assert refused is None
    for _ in range(5):
        qapp.processEvents()
    assert calls == ["a-done"]   # A's result was delivered, not dropped as stale
    assert not host.is_busy()


def test_shutdown_timeout_keeps_the_worker_as_an_orphan(qapp, caplog):
    """Important 1: a timed-out shutdown() must not abandon a running QThread.

    The worker is kept (detached from the host widget), the host stays busy so
    no second job writes the same output paths, and the reaper clears it and
    calls ``_on_worker_idle`` once the job actually returns.
    """
    host = _IdleHost()
    release = threading.Event()

    def blocked(progress, token):
        release.wait(20)
        return "late result"

    worker = host.start_job(blocked, label="blocked",
                            on_finished=lambda r: None, on_failed=lambda m: None)
    assert worker is not None
    with caplog.at_level("ERROR"):
        assert host.shutdown(timeout_ms=50) is False
    assert any("kept as an orphan" in record.message for record in caplog.records)
    assert host._worker is None
    assert host.is_busy()                  # the orphan still runs
    assert host.busy_label == "blocked"    # never dereferences the cleared _worker
    assert host._orphan_list() == [worker]
    refused = host.start_job(blocked, label="second",
                             on_finished=lambda r: None, on_failed=lambda m: None)
    assert refused is None                 # no second writer for the same paths
    release.set()
    assert worker.wait(5000)
    for _ in range(5):
        qapp.processEvents()               # deliver the terminal event to the reaper
    assert host._orphan_list() == []
    assert not host.is_busy()
    assert host.busy_label is None
    assert host.idle_calls == 1


def test_second_shutdown_reports_a_running_orphan(qapp):
    """Re-review Important: shutdown() after an earlier timed-out shutdown()
    must still return False while that orphan runs, so MainWindow.closeEvent
    calls join_orphans() instead of destroying a running QThread."""
    host = _IdleHost()
    release = threading.Event()

    def blocked(progress, token):
        release.wait(20)
        return "late result"

    worker = host.start_job(blocked, label="blocked",
                            on_finished=lambda r: None, on_failed=lambda m: None)
    assert worker is not None
    assert host.shutdown(timeout_ms=50) is False
    assert host.shutdown(timeout_ms=50) is False   # second call: orphan still runs
    assert host.is_busy()
    release.set()
    assert worker.wait(5000)
    # The thread has exited but the reaper is not delivered yet: the orphan
    # still counts as busy, so no new job can slip in before the idle hook.
    assert host.is_busy()
    for _ in range(5):
        qapp.processEvents()
    assert host.shutdown(timeout_ms=50) is True
    assert not host.is_busy()
    assert host.idle_calls == 1


def test_orphan_idle_hook_is_skipped_while_a_new_job_runs(qapp):
    """The reaper must not tell the panel it is idle when a new live worker
    started after the orphan was reaped-eligible (re-review, Minor)."""
    host = _IdleHost()
    release = threading.Event()
    release2 = threading.Event()

    def blocked(progress, token):
        release.wait(20)
        return "a"

    def blocked2(progress, token):
        release2.wait(20)
        return "b"

    worker = host.start_job(blocked, label="a", on_finished=lambda r: None,
                            on_failed=lambda m: None)
    assert host.shutdown(timeout_ms=50) is False
    release.set()
    assert worker.wait(5000)
    for _ in range(5):
        qapp.processEvents()               # orphan reaped; host idle
    assert host.idle_calls == 1
    second = host.start_job(blocked2, label="b", on_finished=lambda r: None,
                            on_failed=lambda m: None)
    assert second is not None and host.is_busy()
    release2.set()
    assert second.wait(5000)
    for _ in range(5):
        qapp.processEvents()
    assert host.idle_calls == 1            # no spurious idle call for the live worker


def test_join_orphans_waits_for_the_released_orphan(qapp):
    """join_orphans() is what MainWindow.closeEvent uses instead of a destroy."""
    host = _Host()
    release = threading.Event()

    def blocked(progress, token):
        release.wait(20)
        return "late result"

    worker = host.start_job(blocked, label="blocked",
                            on_finished=lambda r: None, on_failed=lambda m: None)
    assert worker is not None
    assert host.shutdown(timeout_ms=50) is False
    assert host.join_orphans(timeout_ms=50) is False  # still running
    release.set()
    assert host.join_orphans() is True                # unbounded wait
    assert not worker.isRunning()
    for _ in range(5):
        qapp.processEvents()
    assert host._orphan_list() == []


def test_progress_from_a_released_worker_is_dropped(qapp, caplog):
    """Minor 3: an orphan's progress must not drive the host's current UI."""
    host = _Host()
    seen = []
    gate = threading.Event()

    def late_progress(progress, token):
        gate.wait(20)
        progress("plate", 0, 0, "line from the released worker")
        return "done"

    worker = host.start_job(late_progress, label="late",
                            on_finished=lambda r: None, on_failed=lambda m: None,
                            on_progress=lambda *args: seen.append(args))
    assert worker is not None
    assert host.shutdown(timeout_ms=50) is False
    with caplog.at_level("DEBUG", logger="gui.sprite.workers"):
        gate.set()
        assert worker.wait(5000)
        for _ in range(5):
            qapp.processEvents()
    assert seen == []
    assert any("Dropped stale progress" in record.message for record in caplog.records)


def test_worker_host_drops_stale_finished_event_after_shutdown(qapp, caplog):
    """Fix round 2 (review finding): a job that finishes naturally an instant
    before shutdown() still has its ``finished`` event queued (undelivered)
    at the moment shutdown() releases the worker (``self._worker = None``).
    That queued event must be dropped when the event loop later delivers it,
    not run against whatever the host's live state has since become."""
    host = _Host()
    calls = []

    def instant(progress, token):
        return "instant-result"

    worker = host.start_job(instant, label="instant",
                            on_finished=lambda r: calls.append(r), on_failed=lambda m: None)
    assert worker is not None
    assert worker.wait(5000)  # thread joined; finished is QUEUED, not yet delivered
    with caplog.at_level("DEBUG", logger="gui.sprite.workers"):
        host.shutdown()  # releases the worker before the queued event is drained
        for _ in range(3):
            QApplication.processEvents()  # deliver the now-stale queued event
    assert calls == []
    assert any("Dropped stale finished" in record.message for record in caplog.records)
    assert not host.is_busy()


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
