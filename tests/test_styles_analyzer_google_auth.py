"""core/styles/analyzer.build_completion_fn with Google, end to end.

It prefixes the model with ``gemini/`` before calling
``UnifiedLLMProvider.analyze_image``. With Google Cloud login that prefix used
to win over the auth mode: the request stayed on the API-key route.

``chameleon_llm.completion`` is a recorder here: nothing reaches a provider.
"""
from types import SimpleNamespace
from unittest import mock

import pytest

from core import chameleon_llm
from core import llm_params
from core.styles import analyzer

TOKEN = "oauth-access-token-not-an-api-key"
MODEL = "gemini-test-model"
MSGS = [{"role": "user", "content": "describe the style"}]
_ENV = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "OPENAI_API_BASE", "OLLAMA_API_BASE")


class _Config:
    """ConfigManager stand-in: in gcloud mode the Google lookup is a token."""

    def __init__(self, auth_mode, google_key, project=None):
        self._values = {"auth_mode": auth_mode, "gcloud_project_id": project,
                        "llm_provider": "google"}
        self._google_key = google_key

    def get(self, key, default=None):
        value = self._values.get(key)
        return default if value is None else value

    def get_api_key(self, provider):
        return self._google_key if provider == "google" else None


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in _ENV:
        monkeypatch.setenv(name, "x")
        monkeypatch.delenv(name)
    monkeypatch.setattr(llm_params, "_saved_settings", lambda: pytest.fail(
        "the config passed in is complete; saved Settings must not be read"))


@pytest.fixture
def completion():
    reply = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"),
                                 finish_reason="stop")],
        usage=None, model="fake")

    def _fake(**kwargs):
        chameleon_llm.resolve_route(kwargs["model"], kwargs.get("api_base"))
        return reply

    with mock.patch("core.chameleon_llm.completion", side_effect=_fake) as m:
        yield m


def test_gcloud_mode_with_a_token_uses_vertex_and_the_project(completion):
    config = _Config("gcloud", TOKEN, project="saved-project")
    fn, provider, _model = analyzer.build_completion_fn(
        config, provider="google", model=MODEL, max_retries=0)
    assert fn(MSGS) == "ok"
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == f"vertex_ai/{MODEL}"
    assert "api_key" not in kwargs
    assert kwargs["vertex_project"] == "saved-project"


def test_gcloud_mode_needs_no_key_at_all(completion):
    """No token (gcloud CLI not found) must not stop a Google Cloud login."""
    config = _Config("gcloud", None, project="saved-project")
    fn, _provider, _model = analyzer.build_completion_fn(
        config, provider="google", model=MODEL, max_retries=0)
    assert fn(MSGS) == "ok"
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == f"vertex_ai/{MODEL}"
    assert "api_key" not in kwargs


def test_api_key_mode_keeps_the_gemini_route_and_key(completion):
    config = _Config("api-key", "stored-key", project="saved-project")
    fn, _provider, _model = analyzer.build_completion_fn(
        config, provider="google", model=MODEL, max_retries=0)
    assert fn(MSGS) == "ok"
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == f"gemini/{MODEL}"
    assert kwargs["api_key"] == "stored-key"
    assert "vertex_project" not in kwargs


def test_api_key_mode_without_a_key_still_refuses(completion):
    config = _Config("api-key", None, project="saved-project")
    with pytest.raises(analyzer.StyleAnalysisError, match="No google API key"):
        analyzer.build_completion_fn(config, provider="google", model=MODEL)
    assert not completion.called
