"""Worker thread emits progress/finished/failed correctly (offscreen)."""
import pytest

pytest.importorskip("PySide6")

from types import SimpleNamespace


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def _run_worker(qapp, service, paths):
    from gui.styles.style_manager_dialog import StyleAnalysisWorker
    worker = StyleAnalysisWorker(service, paths)
    got = {"progress": [], "ok": None, "fail": None}
    worker.progress.connect(got["progress"].append)
    worker.finished_ok.connect(lambda d: got.__setitem__("ok", d))
    worker.failed.connect(lambda m: got.__setitem__("fail", m))
    worker.run()  # synchronous call: same code path, no thread flakiness
    return got


def test_worker_success(qapp):
    derived = {"descriptor": {"summary": "s"}, "prompt_text": "t"}
    svc = SimpleNamespace(derive=lambda paths, progress_cb=None: (
        progress_cb and progress_cb("chunk 1/1"), derived)[1])
    got = _run_worker(qapp, svc, ["a.png"])
    assert got["ok"] == derived
    assert got["fail"] is None
    assert "chunk 1/1" in got["progress"]


def test_worker_failure(qapp):
    def boom(paths, progress_cb=None):
        raise RuntimeError("no key")
    got = _run_worker(qapp, SimpleNamespace(derive=boom), ["a.png"])
    assert got["ok"] is None
    assert "no key" in got["fail"]
