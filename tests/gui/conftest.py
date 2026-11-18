"""Shared fixtures for the offscreen LLM dialog tests (tests/gui/test_llm_dialogs_*.py).

Every test that uses ``fake_completion`` runs with no network, no subprocess,
no API keys and no Qt event loop of its own: ``core.chameleon_llm.completion``
is replaced by a recorder, the environment variables that steer provider
routing are pinned, and worker threads run inline in the test thread.
"""
import json
import logging
import os
import socket
import subprocess
import time
from unittest.mock import MagicMock

import pytest

from core import chameleon_llm
from core.chameleon_llm import Choice, Completion, Message, Usage
from core.model_registry import FALLBACK_PATH
from core.model_registry import client as _registry_client


def _prime_registry_cache():
    """Seed the model-registry cache with the bundled snapshot.

    ``core.llm_models`` resolves model ids when it is first imported, and that
    import happens while pytest collects the GUI test modules. With the cache
    primed, the lookup is answered from the snapshot instead of a live fetch.
    """
    url = os.environ.get("MODEL_REGISTRY_URL") or _registry_client.DEFAULT_URL
    with open(FALLBACK_PATH, encoding="utf-8") as fh:
        _registry_client._cache[url] = (json.load(fh), time.time())


_prime_registry_cache()

# Environment variables that change which route or endpoint a call takes.
_PINNED_ENV = (
    "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "OPENAI_API_BASE", "OLLAMA_API_BASE",
)


_TRANSPORT_KWARGS = frozenset(
    {"model", "messages", "api_key", "api_base", "timeout", "max_retries"})


def check_completion_kwargs(kwargs):
    """Fail as the real ``completion`` would on a wrong route, and also on a
    parameter the route's adapter does not accept (the real call would drop
    it with a WARNING, so a dialog test would not notice the lost setting)."""
    from core.chameleon_llm.dispatch import _load_adapter
    route = chameleon_llm.resolve_route(kwargs.get("model", ""), kwargs.get("api_base"))
    accepted = _load_adapter(route.adapter).ACCEPTED_PARAMS | _TRANSPORT_KWARGS
    rejected = sorted(k for k, v in kwargs.items() if k not in accepted and v is not None)
    if rejected:
        raise AssertionError(
            f"completion kwargs not accepted by the {route.route} route "
            f"({kwargs.get('model')!r}): {rejected}")
    return route


class FakeCompletion:
    """Stands in for ``chameleon_llm.completion``: records kwargs, returns ``reply``.

    Each call is checked against the real router and the routed adapter's
    accepted parameters (see ``check_completion_kwargs``), so a dialog that
    builds a wrong route or an unaccepted parameter fails its test.
    """

    def __init__(self):
        self.reply = ""
        self.error = None
        self.calls = []
        self.violations = []  # also asserted empty at fixture teardown

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        try:
            check_completion_kwargs(kwargs)
        except Exception as exc:  # dialogs catch errors; teardown still sees it
            self.violations.append(f"{type(exc).__name__}: {exc}")
            raise
        if self.error is not None:
            raise self.error
        return Completion(
            model="test-model",
            choices=[Choice(0, Message("assistant", self.reply), "stop")],
            usage=Usage(1, 1, 2),
        )

    @property
    def kwargs(self):
        """The kwargs of the one call the test expects."""
        assert len(self.calls) == 1, f"expected exactly one completion call, got {len(self.calls)}"
        return self.calls[0]


@pytest.fixture
def llm_sandbox(monkeypatch):
    """Keep a test off the network, off subprocesses and off the developer's environment."""
    for name in _PINNED_ENV:
        # set-then-delete so monkeypatch restores whatever an app helper
        # (UnifiedLLMProvider writes keys into os.environ) leaves behind
        monkeypatch.setenv(name, "x")
        monkeypatch.delenv(name)

    def _blocked(*_args, **_kwargs):
        raise OSError("network and subprocesses are disabled in LLM dialog tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(subprocess, "Popen", _blocked)
    # Ollama model discovery is an HTTP GET; the registry snapshot is bundled.
    monkeypatch.setattr("core.llm_models.fetch_ollama_models", lambda *a, **k: [])


@pytest.fixture
def stub_api_key(monkeypatch):
    """Every ``ConfigManager.get_api_key`` lookup answers ``"test-key"``."""
    monkeypatch.setattr("core.config.ConfigManager.get_api_key",
                        lambda self, provider: "test-key")


@pytest.fixture
def fake_completion(monkeypatch, llm_sandbox, stub_api_key):
    fake = FakeCompletion()
    monkeypatch.setattr(chameleon_llm, "completion", fake)
    yield fake
    assert not fake.violations, fake.violations


@pytest.fixture
def fake_config():
    """A ConfigManager stand-in with an API key and the API-key auth mode."""
    config = MagicMock()
    config.get_api_key.return_value = "test-key"
    config.get_auth_mode.return_value = "api-key"
    config.get_layout_llm_provider.return_value = "google"

    def _get(key, default=None):
        if key == "auth_mode":
            return "api-key"
        return "test-key" if key.endswith("api_key") else default

    config.get.side_effect = _get
    return config


@pytest.fixture
def console_log():
    """Messages written to the ``console`` logger (the app's status-console feed)."""
    records = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    handler = _Capture()
    logger = logging.getLogger("console")
    old_level = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    yield records
    logger.removeHandler(handler)
    logger.setLevel(old_level)
    # LLMHandler.setup_llm mirrors package logs to the console; drop that handler
    pkg_logger = logging.getLogger("chameleon_llm")
    for existing in list(pkg_logger.handlers):
        if getattr(existing, "_imageai_console", False):
            pkg_logger.removeHandler(existing)


@pytest.fixture
def message_boxes(monkeypatch):
    """Replace the blocking QMessageBox statics; returns the (kind, title, text) shown."""
    from PySide6.QtWidgets import QMessageBox

    shown = []
    for kind in ("critical", "warning", "information", "question"):
        def _record(parent, title, text, *args, _kind=kind, **kwargs):
            shown.append((_kind, title, text))
            return QMessageBox.StandardButton.Ok
        monkeypatch.setattr(QMessageBox, kind, staticmethod(_record))
    return shown


@pytest.fixture
def inline_threads(monkeypatch):
    """``QThread.start()`` runs ``run()`` in the calling thread (no real thread)."""
    from PySide6.QtCore import QThread
    monkeypatch.setattr(QThread, "start", lambda self, *a: self.run())


@pytest.fixture
def widgets(qapp):
    """``widgets(w)`` registers a widget; teardown deletes it and drains the event queue."""
    made = []

    def _track(widget):
        made.append(widget)
        return widget

    yield _track
    for widget in reversed(made):
        widget.deleteLater()
    qapp.processEvents()


@pytest.fixture
def error_logged(caplog):
    """After the test body: True when an ERROR record was logged (caplog at INFO)."""
    caplog.set_level(logging.INFO)
    return lambda: any(r.levelno >= logging.ERROR for r in caplog.records)
