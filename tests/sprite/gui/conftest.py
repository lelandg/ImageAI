# tests/sprite/gui/conftest.py
"""Shared fixtures for the Sprite GUI tests (offscreen, sandboxed QSettings)."""
import gc
import types

import pytest
from PySide6.QtWidgets import QApplication

from core.sprite.project import ActionCard, GenerationSettings


class FakeConfig:
    """Minimal ConfigManager stand-in: get/set/save/get_api_key/get_auth_mode."""

    def __init__(self, api_key="test-key"):
        self.store = {}
        self.api_key = api_key

    def get(self, key, default=None):
        return self.store.get(key, default)

    def set(self, key, value):
        self.store[key] = value

    def save(self):
        return True

    def get_api_key(self, provider):
        return self.api_key

    def get_auth_mode(self, provider="google"):
        return "api-key"


@pytest.fixture
def fake_config():
    return FakeConfig()


@pytest.fixture
def fake_project(tmp_path):
    """A SpriteProject-shaped namespace with the fields the panels read/write.

    A namespace (not the real dataclass) keeps these tests independent of the
    constructor defaults sub-project 1 chose; the tab smoke tests use the real
    class through SpriteProjectManager.
    """
    project_dir = tmp_path / "hero"
    project_dir.mkdir()
    return types.SimpleNamespace(
        name="hero",
        project_dir=project_dir,
        character_source=None,
        plate_path=None,
        plate_color="#00FF00",
        turnaround={},
        brief="",
        genre_preset="sidescroller",
        actions=[
            ActionCard(id="a1", name="idle", prompt="idle pose"),
            ActionCard(id="a2", name="walk", prompt="walk cycle", target_frames=8, fps=12),
        ],
        generation=GenerationSettings(),
        cost_ledger=[],
        stage_fingerprints={},
    )


@pytest.fixture
def png(tmp_path):
    from PIL import Image

    path = tmp_path / "char.png"
    Image.new("RGBA", (64, 48), (255, 0, 0, 255)).save(path)
    return path


@pytest.fixture
def wait_for_worker():
    """Return a helper that joins a WorkerHost's current worker and pumps events.

    Worker signals reach the panel's bound-method slots through the GUI event
    loop; a test has no running loop, so pump it by hand after the join.
    """

    def _wait(host, timeout_ms=10000):
        worker = host._worker
        assert worker is not None, "no worker was started"
        assert worker.wait(timeout_ms), "worker did not finish in time"
        for _ in range(3):
            QApplication.processEvents()
        return worker

    return _wait


@pytest.fixture(autouse=True)
def _collect_dead_qt_objects_between_tests(qapp):
    """Run the cyclic garbage collector at test teardown, when no worker runs.

    Closed dialogs/panels with worker plumbing form reference cycles. When
    the collector frees such a widget tree on the GUI thread while a later
    test's SpriteWorker runs Qt code, PySide crashes (5b Task 7 finding,
    3/10 segfaults with the per-file mitigation removed). Collecting at
    teardown — after the test joined its workers — keeps the pile of dead
    dialogs from reaching an automatic collection mid-job.
    """
    yield
    for _ in range(3):
        qapp.processEvents()
    gc.collect()
