"""core.config_io is the single gate to config.json.

config.json holds the API keys and the ``data_roots`` entry that records where
every other data directory lives. Two writers own it — ConfigManager and the
storage migrator — and both run a read-modify-write cycle. These tests pin the
three properties the writers depend on: an unreadable file is never mistaken
for an empty one, a write is atomic, and one lock covers the whole cycle for
threads and for processes.
"""
import json
import logging
import os
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from core import config_io
from core.config_io import (
    ConfigLockError,
    ConfigReadError,
    ConfigWriteError,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config_path(tmp_path):
    return tmp_path / "config.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --- read_config ------------------------------------------------------------


def test_missing_config_is_a_fresh_install(config_path):
    assert config_io.read_config(config_path) == {}


def test_read_returns_the_parsed_document(config_path):
    config_path.write_text(json.dumps({"provider": "google"}), encoding="utf-8")

    assert config_io.read_config(config_path) == {"provider": "google"}


def test_truncated_config_raises_instead_of_returning_empty(config_path, caplog):
    """A power loss leaves a half-written file. It is not an empty document."""
    config_path.write_text('{"providers": {"openai": {"api_key": "sk-REAL"}}, ',
                           encoding="utf-8")

    with caplog.at_level(logging.ERROR, logger="core.config_io"):
        with pytest.raises(ConfigReadError):
            config_io.read_config(config_path)

    assert caplog.records, "an unreadable config.json must reach the logger"


def test_utf16_config_raises_instead_of_returning_empty(config_path):
    """An editor that rewrote the file as UTF-16 must not look like a new install."""
    config_path.write_bytes(json.dumps({"provider": "google"}).encode("utf-16"))

    with pytest.raises(ConfigReadError):
        config_io.read_config(config_path)


def test_non_object_config_raises(config_path):
    config_path.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(ConfigReadError):
        config_io.read_config(config_path)


def test_non_object_data_roots_raises(config_path):
    config_path.write_text(json.dumps({"data_roots": "everywhere"}), encoding="utf-8")

    with pytest.raises(ConfigReadError):
        config_io.read_config(config_path)


def test_null_data_roots_raises(config_path, caplog):
    """An explicit JSON null is not a valid data_roots document.

    A move reads the document, mutates ``data_roots`` and writes it back. A
    null passes a "wrong type" check written as ``is not None``, and the
    mutation then fails with a TypeError after every rename already ran.
    """
    config_path.write_text(json.dumps({"data_roots": None}), encoding="utf-8")

    with caplog.at_level(logging.ERROR, logger="core.config_io"):
        with pytest.raises(ConfigReadError):
            config_io.read_config(config_path)

    assert caplog.records, "an invalid data_roots entry must reach the logger"


def test_absent_data_roots_is_valid(config_path):
    """Only an entry that is present and not an object is a failure."""
    config_path.write_text(json.dumps({"provider": "google"}), encoding="utf-8")

    assert config_io.read_config(config_path) == {"provider": "google"}


def test_update_refuses_a_null_data_roots_document(config_path):
    """The move must abort before it renames anything."""
    original = json.dumps({"data_roots": None})
    config_path.write_text(original, encoding="utf-8")

    def mutate(data):
        data["data_roots"]["video"] = "/somewhere"

    with pytest.raises(ConfigReadError):
        config_io.update_config(config_path, mutate)

    assert config_path.read_text(encoding="utf-8") == original


# --- read_config_document ---------------------------------------------------


def test_read_document_reports_a_missing_file_as_none(config_path):
    """A caller that merges needs "no document" apart from "empty document"."""
    assert config_io.read_config_document(config_path) is None


def test_read_document_returns_an_empty_document_as_a_dict(config_path):
    """A file another writer emptied is a real document, not a missing one."""
    config_path.write_text("{}", encoding="utf-8")

    assert config_io.read_config_document(config_path) == {}


def test_read_document_raises_for_an_unreadable_file(config_path):
    config_path.write_text("{ broken", encoding="utf-8")

    with pytest.raises(ConfigReadError):
        config_io.read_config_document(config_path)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission semantics")
@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores the permission bits")
def test_unreadable_config_raises(config_path):
    config_path.write_text(json.dumps({"provider": "google"}), encoding="utf-8")
    config_path.chmod(0o000)
    try:
        with pytest.raises(ConfigReadError):
            config_io.read_config(config_path)
    finally:
        config_path.chmod(0o600)


# --- write_config -----------------------------------------------------------


def test_write_replaces_the_document(config_path):
    config_io.write_config(config_path, {"provider": "stability"})

    assert _read(config_path) == {"provider": "stability"}


def test_failed_write_leaves_the_previous_file_intact(config_path, monkeypatch, caplog):
    config_io.write_config(config_path, {"provider": "google"})
    before = config_path.read_text(encoding="utf-8")

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(config_io.json, "dump", _boom)

    with caplog.at_level(logging.ERROR, logger="core.config_io"):
        with pytest.raises(ConfigWriteError):
            config_io.write_config(config_path, {"provider": "openai"})

    assert config_path.read_text(encoding="utf-8") == before
    assert not list(config_path.parent.glob("*.tmp*")), "temp file left behind"
    assert caplog.records, "a failed write must reach the logger"


# --- quarantine_unreadable --------------------------------------------------


def test_quarantine_copies_the_original_beside_it(config_path, caplog):
    config_path.write_text("{ broken", encoding="utf-8")

    with caplog.at_level(logging.ERROR, logger="core.config_io"):
        sidecar = config_io.quarantine_unreadable(config_path)

    assert sidecar is not None
    assert sidecar.read_text(encoding="utf-8") == "{ broken"
    assert sidecar.name.startswith("config.json.corrupt-")
    assert caplog.records, "the quarantine must reach the logger"


def test_quarantine_never_overwrites_an_earlier_sidecar(config_path):
    config_path.write_text("{ broken", encoding="utf-8")
    first = config_io.quarantine_unreadable(config_path)
    config_path.write_text("{ broken again", encoding="utf-8")
    second = config_io.quarantine_unreadable(config_path)

    assert first != second
    assert first.read_text(encoding="utf-8") == "{ broken"
    assert second.read_text(encoding="utf-8") == "{ broken again"


def test_quarantine_reports_failure_instead_of_pretending(config_path, monkeypatch,
                                                          caplog):
    config_path.write_text("{ broken", encoding="utf-8")

    def _boom(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(config_io.shutil, "copy2", _boom)

    with caplog.at_level(logging.ERROR, logger="core.config_io"):
        assert config_io.quarantine_unreadable(config_path) is None

    assert caplog.records, "a failed quarantine must reach the logger"


# --- update_config and the lock --------------------------------------------


def test_update_writes_the_mutated_document(config_path):
    config_io.write_config(config_path, {"provider": "google"})

    def mutate(data):
        data["provider"] = "openai"

    config_io.update_config(config_path, mutate)

    assert _read(config_path)["provider"] == "openai"


def test_update_refuses_an_unreadable_document(config_path):
    config_path.write_text("{ broken", encoding="utf-8")

    with pytest.raises(ConfigReadError):
        config_io.update_config(config_path, lambda data: {"provider": "openai"})

    assert config_path.read_text(encoding="utf-8") == "{ broken"


def test_concurrent_updates_in_one_process_do_not_lose_writes(config_path):
    """The OS file lock alone does not serialise threads. This must still hold."""
    config_io.write_config(config_path, {"counter": 0, "seen": []})

    workers = 8

    def bump(index):
        def mutate(data):
            current = data.get("counter", 0)
            # Widen the read-modify-write window so an unsynchronised
            # implementation loses updates every run.
            time.sleep(0.01)
            data["counter"] = current + 1
            data.setdefault("seen", []).append(index)

        config_io.update_config(config_path, mutate, timeout=30)

    threads = [threading.Thread(target=bump, args=(i,)) for i in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
        assert not thread.is_alive()

    result = _read(config_path)
    assert result["counter"] == workers
    assert sorted(result["seen"]) == list(range(workers))


def test_the_lock_is_reentrant_for_one_thread(config_path):
    """A nested acquisition must not deadlock against the flock this thread holds."""
    with config_io.config_lock(config_path, timeout=5):
        with config_io.config_lock(config_path, timeout=5):
            config_io.write_config(config_path, {"nested": True})

    assert _read(config_path) == {"nested": True}
    # The lock is fully released again.
    with config_io.config_lock(config_path, timeout=5):
        pass


def test_a_lock_held_by_another_thread_times_out(config_path, caplog):
    held = threading.Event()
    release = threading.Event()

    def holder():
        with config_io.config_lock(config_path, timeout=10):
            held.set()
            release.wait(10)

    thread = threading.Thread(target=holder)
    thread.start()
    try:
        assert held.wait(10)
        with caplog.at_level(logging.ERROR, logger="core.config_io"):
            with pytest.raises(ConfigLockError):
                with config_io.config_lock(config_path, timeout=0.1):
                    pass
        assert caplog.records, "a lock timeout must reach the logger"
    finally:
        release.set()
        thread.join(10)
    assert not thread.is_alive()


def test_a_lock_held_by_another_process_times_out(config_path):
    """The lock must cross processes: a second ImageAI window is a real case."""
    script = textwrap.dedent(
        f"""
        import sys, time
        sys.path.insert(0, {str(REPO_ROOT)!r})
        from core import config_io
        with config_io.config_lock({str(config_path)!r}, timeout=10):
            print("held", flush=True)
            time.sleep(5)
        """
    )
    child = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout.readline().strip() == "held"
        with pytest.raises(ConfigLockError):
            with config_io.config_lock(config_path, timeout=0.3):
                pass
    finally:
        child.kill()
        child.wait(10)
