"""The Enhance Prompt path routes provider display names (C1, final review).

The Enhance Prompt dialog passes the provider combo's display text
("Anthropic", "Google", "LM Studio", ...) to ``PromptEnhancerLLM``; each one
must reach ``chameleon_llm.completion`` with the right route, and a failed
call must be logged at ERROR with the provider and model before the
non-LLM fallback is returned.
"""
import logging
from types import SimpleNamespace
from unittest import mock

import pytest

from core.prompt_enhancer_llm import PromptEnhancerLLM
from core.video.prompt_engine import UnifiedLLMProvider

_ENV = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "OPENAI_API_BASE", "OLLAMA_API_BASE")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    # set-then-delete so monkeypatch also undoes what UnifiedLLMProvider writes
    for name in _ENV:
        monkeypatch.setenv(name, "x")
        monkeypatch.delenv(name)


@pytest.fixture
def completion():
    reply = SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content='{"unified": {"prompt": "ok"}}'),
            finish_reason="stop")],
        usage=None, model="fake")
    with mock.patch("core.chameleon_llm.completion", return_value=reply) as m:
        yield m


def _enhance(provider, model, api_config=None):
    enhancer = PromptEnhancerLLM(UnifiedLLMProvider(api_config or {}))
    return enhancer.enhance_with_llm(
        prompt="a cat", provider="google", model=model,
        llm_provider=provider, max_tokens=100)


@pytest.mark.parametrize("provider,model,api_config,expected", [
    ("OpenAI", "gpt-test-model", {"openai_api_key": "k"}, "gpt-test-model"),
    ("Anthropic", "claude-test-model", {"anthropic_api_key": "k"},
     "anthropic/claude-test-model"),
    ("Google", "gemini-test-model", {"google_api_key": "k"},
     "gemini/gemini-test-model"),
    ("Google", "gemini-test-model", {"auth_mode": "gcloud"},
     "vertex_ai/gemini-test-model"),
    # API-key mode with no key stays on gemini/ (never a move to Vertex)
    ("Google", "gemini-test-model", {"auth_mode": "api-key"},
     "gemini/gemini-test-model"),
    ("Ollama", "local-test-model", {}, "ollama/local-test-model"),
    ("LM Studio", "local-test-model", {}, "local-test-model"),
])
def test_display_names_route(completion, provider, model, api_config, expected):
    result = _enhance(provider, model, api_config)
    assert result == {"unified": {"prompt": "ok"}}
    assert completion.call_args.kwargs["model"] == expected


def test_lm_studio_gets_its_endpoint(completion):
    _enhance("LM Studio", "local-test-model")
    assert completion.call_args.kwargs["api_base"] == "http://localhost:1234/v1"


def test_reasoning_model_gets_completion_token_param(completion):
    _enhance("OpenAI", "gpt-5-test", {"openai_api_key": "k"})
    kwargs = completion.call_args.kwargs
    assert kwargs["max_completion_tokens"] == 100
    assert "max_tokens" not in kwargs and "temperature" not in kwargs


def test_failed_call_logged_at_error_with_provider_and_model(completion, caplog):
    completion.side_effect = RuntimeError("boom")
    with caplog.at_level(logging.INFO):
        result = _enhance("Anthropic", "claude-test-model",
                          {"anthropic_api_key": "k"})
    assert result  # the non-LLM fallback
    errors = [r.getMessage() for r in caplog.records
              if r.levelno >= logging.ERROR and r.name == "core.prompt_enhancer_llm"]
    assert any("Anthropic" in m and "claude-test-model" in m and "boom" in m
               for m in errors), errors
