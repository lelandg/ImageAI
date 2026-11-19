"""LLMSyncAssistant (llm_sync_v2) builds kwargs via build_completion_kwargs (final-review sweep)."""
from types import SimpleNamespace
from unittest import mock

import pytest

from core.video.llm_sync_v2 import LLMSyncAssistant

_ENV = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "OPENAI_API_BASE", "OLLAMA_API_BASE")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in _ENV:
        monkeypatch.setenv(name, "x")
        monkeypatch.delenv(name)


@pytest.fixture
def completion():
    reply = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"lyrics": []}'),
                                 finish_reason="stop")],
        usage=None, model="fake")
    with mock.patch("core.chameleon_llm.completion", return_value=reply) as m:
        yield m


def test_openai_reasoning_model(completion):
    LLMSyncAssistant("openai", "gpt-5-test", {})._sync_with_openai("la la", None, 30.0)
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "gpt-5-test"
    assert "temperature" not in kwargs
    assert kwargs["response_format"] == {"type": "json_object"}


def test_anthropic_route(completion):
    LLMSyncAssistant("anthropic", "claude-test-model", {})._sync_with_anthropic(
        "la la", None, 30.0)
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "anthropic/claude-test-model"
    assert kwargs["max_tokens"] == 4000


def test_gemini_with_key_uses_api_key_route(completion):
    LLMSyncAssistant("gemini", "gemini-test-model",
                     {"google_api_key": "k"})._sync_single_section_with_gemini(
        "la la", None, 30.0, None)
    assert completion.call_args.kwargs["model"] == "gemini/gemini-test-model"


def test_gemini_without_key_stays_on_the_gemini_route(completion):
    LLMSyncAssistant("gemini", "gemini-test-model", {})._sync_single_section_with_gemini(
        "la la", None, 30.0, None)
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "gemini/gemini-test-model"
    assert "api_key" not in kwargs


def test_gemini_with_google_cloud_login_uses_vertex_route(completion):
    LLMSyncAssistant("gemini", "gemini-test-model",
                     {"auth_mode": "gcloud"})._sync_single_section_with_gemini(
        "la la", None, 30.0, None)
    assert completion.call_args.kwargs["model"] == "vertex_ai/gemini-test-model"
