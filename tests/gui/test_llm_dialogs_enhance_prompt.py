"""Enhance Prompt worker, with a fake completion (C1, final review).

The dialog hands its provider combo's display text ("Anthropic", "Google",
"LM Studio", ...) to ``EnhanceWorker``; each must reach the right route.
``FakeCompletion`` also fails on a wrong route or an unaccepted parameter.
"""
import json

import pytest

from core.prompt_enhancer import EnhancementLevel
from gui.enhanced_prompt_dialog import EnhanceWorker

CANNED = json.dumps({"unified": {"prompt": "a cat, golden hour"}})

# (display name, api key, model, expected model)
BRANCHES = [
    pytest.param("OpenAI", "test-key", "gpt-test-model", "gpt-test-model", id="openai"),
    pytest.param("Anthropic", "test-key", "claude-test-model",
                 "anthropic/claude-test-model", id="anthropic"),
    pytest.param("Google", "test-key", "gemini-test-model",
                 "gemini/gemini-test-model", id="google-api-key"),
    pytest.param("Google", None, "gemini-test-model",
                 "vertex_ai/gemini-test-model", id="google-gcloud"),
    pytest.param("Ollama", None, "local-test-model", "ollama/local-test-model",
                 id="ollama"),
    pytest.param("LM Studio", None, "local-test-model", "local-test-model",
                 id="lm-studio"),
]


def _run(provider, api_key, model, temperature=0.7, max_tokens=500):
    worker = EnhanceWorker("a cat", provider, model, api_key, EnhancementLevel.MEDIUM,
                           temperature=temperature, max_tokens=max_tokens)
    results, errors = [], []
    worker.finished.connect(results.append)
    worker.error.connect(errors.append)
    worker.run()
    return results, errors


class _GcloudSettings:
    """Saved Settings that select Google Cloud login."""

    def get(self, key, default=None):
        return {"auth_mode": "gcloud"}.get(key, default)

    def get_api_key(self, provider):
        raise AssertionError("Google Cloud login must not look up an API key")


@pytest.mark.parametrize("provider, api_key, model, expected_model", BRANCHES)
def test_display_names_route(qapp, fake_completion, monkeypatch, provider, api_key,
                             model, expected_model):
    if expected_model.startswith("vertex_ai/"):
        # the dialog passes no key in gcloud mode; the mode is in Settings
        from core import llm_params
        monkeypatch.setattr(llm_params, "_saved_settings", _GcloudSettings)
    fake_completion.reply = CANNED
    results, errors = _run(provider, api_key, model)
    assert fake_completion.kwargs["model"] == expected_model
    assert results == ["a cat, golden hour"] and errors == []


def test_google_without_a_key_in_api_key_mode_stays_on_gemini(
        qapp, fake_completion, monkeypatch):
    """No key in the dialog and none in Settings: gemini/, never Vertex."""
    monkeypatch.setattr("core.config.ConfigManager.get_api_key",
                        lambda self, provider: None)
    fake_completion.reply = CANNED
    _run("Google", None, "gemini-test-model")
    kwargs = fake_completion.kwargs
    assert kwargs["model"] == "gemini/gemini-test-model"
    assert "api_key" not in kwargs


def test_reasoning_model_params_are_corralled(qapp, fake_completion):
    fake_completion.reply = CANNED
    _run("OpenAI", "test-key", "gpt-5-test", max_tokens=1000)
    kwargs = fake_completion.kwargs
    assert kwargs["max_completion_tokens"] == 1000
    assert "max_tokens" not in kwargs and "temperature" not in kwargs


# --- the dialog's live auth mode beats what is saved on disk ------------------

class _Persisted:
    def __init__(self, auth_mode):
        self._auth_mode = auth_mode
        self.key_lookups = []

    def get(self, key, default=None):
        return {"auth_mode": self._auth_mode}.get(key, default)

    def get_api_key(self, provider):
        self.key_lookups.append(provider)
        return "persisted-key"


def _run_with_mode(api_key, auth_mode, project=None):
    worker = EnhanceWorker("a cat", "Google", "gemini-test-model", api_key,
                           EnhancementLevel.MEDIUM, auth_mode=auth_mode,
                           vertex_project=project)
    worker.run()


def test_worker_in_live_gcloud_mode_ignores_api_key_mode_on_disk(
        qapp, fake_completion, monkeypatch):
    from core import llm_params
    saved = _Persisted("api-key")
    monkeypatch.setattr(llm_params, "_saved_settings", lambda: saved)
    fake_completion.reply = CANNED

    _run_with_mode(None, "gcloud", project="live-project")

    kwargs = fake_completion.kwargs
    assert kwargs["model"] == "vertex_ai/gemini-test-model"
    assert "api_key" not in kwargs
    assert kwargs["vertex_project"] == "live-project"
    assert saved.key_lookups == []


def test_worker_in_live_api_key_mode_ignores_gcloud_mode_on_disk(
        qapp, fake_completion, monkeypatch):
    from core import llm_params
    saved = _Persisted("gcloud")
    monkeypatch.setattr(llm_params, "_saved_settings", lambda: saved)
    fake_completion.reply = CANNED

    _run_with_mode("live-key", "api-key")

    kwargs = fake_completion.kwargs
    assert kwargs["model"] == "gemini/gemini-test-model"
    assert kwargs["api_key"] == "live-key"
    assert saved.key_lookups == []
