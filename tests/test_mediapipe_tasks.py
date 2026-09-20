"""Offline checks for the shared Tasks model download boundary."""
import hashlib
from types import SimpleNamespace

import pytest

from core import mediapipe_tasks as tasks


class Response:
    status_code = 200

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self.body


@pytest.fixture
def download(monkeypatch, tmp_path):
    expected = b"verified model"
    digest = hashlib.sha256(expected).hexdigest()
    monkeypatch.setattr(tasks, "_MODELS", {"test": ("test/model.task", digest)})
    monkeypatch.setattr(tasks, "get_data_paths", lambda: SimpleNamespace(model_cache=lambda name: tmp_path))
    seen = []

    def request(url, **kwargs):
        seen.append((url, kwargs))
        return Response(expected)

    monkeypatch.setattr(tasks.requests, "get", request)
    return expected, seen, tmp_path


def test_verified_model_download_is_cached(download):
    expected, seen, directory = download
    path = tasks.model_path("test")
    assert path.parent == directory and path.read_bytes() == expected
    assert tasks.model_path("test") == path
    assert len(seen) == 1
    assert seen[0][0] == "https://storage.googleapis.com/mediapipe-models/test/model.task"
    assert seen[0][1]["allow_redirects"] is False
    assert not list(directory.glob("*.part"))


def test_corrupt_cached_model_is_replaced_only_after_verification(download, monkeypatch, caplog):
    _, _, directory = download
    cached = directory / "model.task"
    cached.write_bytes(b"old corrupt cache")
    monkeypatch.setattr(tasks.requests, "get", lambda *a, **k: Response(b"tampered"))
    with pytest.raises(RuntimeError, match="checksum"):
        tasks.model_path("test")
    assert cached.read_bytes() == b"old corrupt cache"
    assert not list(directory.glob("*.part"))
    assert "Could not prepare MediaPipe" in caplog.text


def test_oversize_download_is_rejected_and_cleaned(download, monkeypatch):
    _, _, directory = download
    monkeypatch.setattr(tasks, "_MAX_MODEL_BYTES", 4)
    with pytest.raises(RuntimeError, match="size limit"):
        tasks.model_path("test")
    assert not (directory / "model.task").exists()
    assert not list(directory.glob("*.part"))


def test_unknown_model_cannot_select_arbitrary_download_path(download):
    _, seen, _ = download
    with pytest.raises(KeyError):
        tasks.model_path("../../other")
    assert not seen


@pytest.mark.parametrize("installed,available", [("0.10.14", False), ("1.0.1", True), ("2.0.0", False)])
def test_legacy_or_unsupported_mediapipe_offers_upgrade(monkeypatch, installed, available):
    monkeypatch.setattr(tasks, "version", lambda name: installed)
    assert tasks.mediapipe_available() is available


def test_offline_first_use_logs_failure_without_cache(download, monkeypatch, caplog):
    _, _, directory = download

    def offline(*args, **kwargs):
        raise tasks.requests.ConnectionError("offline")

    monkeypatch.setattr(tasks.requests, "get", offline)
    with pytest.raises(tasks.requests.ConnectionError, match="offline"):
        tasks.model_path("test")
    assert not (directory / "model.task").exists()
    assert not list(directory.glob("*.part"))
    assert "Could not prepare MediaPipe" in caplog.text
