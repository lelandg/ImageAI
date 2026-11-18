"""designer.run_completion builds its request with build_completion_kwargs.

The completion is a recorder: no test here can reach a provider.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core import chameleon_llm
from core.layout import designer

MSGS = [{"role": "user", "content": "design a page"}]
_ENV = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "OPENAI_API_BASE", "OLLAMA_API_BASE")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in _ENV:
        monkeypatch.setenv(name, "x")
        monkeypatch.delenv(name)


@pytest.fixture
def completion(monkeypatch):
    calls = []

    def _fake(**kwargs):
        calls.append(kwargs)
        chameleon_llm.resolve_route(kwargs["model"], kwargs.get("api_base"))
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="{}"), finish_reason="stop")])

    monkeypatch.setattr(chameleon_llm, "completion", _fake)
    return calls


def _config(**values):
    config = MagicMock()
    config.get.side_effect = lambda key, default=None: values.get(key, default)
    config.get_api_key.side_effect = (
        lambda provider: None if provider in ("ollama", "lmstudio") else "stored-key")
    config.get_layout_llm_provider.return_value = "google"
    return config


def _run(provider, model, **values):
    return designer.run_completion(_config(**values), provider, model, MSGS)


@pytest.mark.parametrize("auth_mode", ["gcloud", "Google Cloud Account"])
def test_google_cloud_auth_selects_the_vertex_route(completion, auth_mode):
    _run("Google", "gemini-test-model", auth_mode=auth_mode,
         gcloud_project_id="saved-project")
    kwargs = completion[0]
    assert kwargs["model"] == "vertex_ai/gemini-test-model"
    assert "api_key" not in kwargs
    assert kwargs["vertex_project"] == "saved-project"
    assert "api_base" not in kwargs


def test_google_api_key_auth_keeps_the_gemini_route(completion):
    _run("Google", "gemini-test-model", auth_mode="api-key",
         gcloud_project_id="saved-project")
    kwargs = completion[0]
    assert kwargs["model"] == "gemini/gemini-test-model"
    assert kwargs["api_key"] == "stored-key"
    assert "vertex_project" not in kwargs


def test_lm_studio_goes_to_the_configured_endpoint(completion):
    _run("LM Studio", "local-test-model",
         lmstudio_endpoint="http://lm-host:4321/v1")
    kwargs = completion[0]
    assert kwargs["model"] == "local-test-model"
    assert kwargs["api_base"] == "http://lm-host:4321/v1"
    assert "api_key" not in kwargs


def test_lm_studio_without_a_configured_endpoint_uses_the_default(completion):
    _run("LM Studio", "local-test-model")
    kwargs = completion[0]
    assert kwargs["model"] == "local-test-model"
    assert kwargs["api_base"] == "http://localhost:1234/v1"


@pytest.mark.parametrize("provider,model,expected", [
    ("OpenAI", "gpt-test-model", "gpt-test-model"),
    ("Anthropic", "claude-test-model", "anthropic/claude-test-model"),
    ("Google", "gemini-test-model", "gemini/gemini-test-model"),
    ("Ollama", "llama-test", "ollama/llama-test"),
])
def test_cloud_and_ollama_requests_never_get_the_lm_studio_endpoint(
        completion, provider, model, expected):
    _run(provider, model, auth_mode="api-key",
         lmstudio_endpoint="http://lm-host:4321/v1")
    kwargs = completion[0]
    assert kwargs["model"] == expected
    assert "api_base" not in kwargs


def test_temperature_is_corralled_per_model(completion):
    _run("OpenAI", "gpt-5-test")
    assert "temperature" not in completion[0]  # fixed at the default for gpt-5
    _run("OpenAI", "gpt-4-test")
    assert completion[1]["temperature"] == 0.4


def test_reply_text_is_returned(completion):
    assert _run("OpenAI", "gpt-test-model") == "{}"
