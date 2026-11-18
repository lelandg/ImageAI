"""VideoPromptGenerator builds its kwargs with build_completion_kwargs (C2, final review).

OpenAI reasoning models (gpt-5.x, o-series) need ``max_completion_tokens`` and
reject a non-default temperature; the vendored package passes params through
unchanged, so the call site must corral them. Provider display names must
reach the right route.
"""
from types import SimpleNamespace
from unittest import mock

import pytest

from core.video.video_prompt_generator import VideoPromptContext, VideoPromptGenerator

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
        choices=[SimpleNamespace(message=SimpleNamespace(content="1. pan left\n2. zoom in"),
                                 finish_reason="stop")],
        usage=None, model="fake")
    with mock.patch("core.chameleon_llm.completion", return_value=reply) as m:
        yield m


CONFIG = {"openai_api_key": "k", "anthropic_api_key": "k", "google_api_key": "k"}


def _single(provider, model, config=CONFIG):
    gen = VideoPromptGenerator(config=dict(config) if config is not None else None)
    return gen.generate_video_prompt(VideoPromptContext(start_prompt="a cat"),
                                     provider, model, temperature=0.7)


def _batch(provider, model, config=CONFIG):
    gen = VideoPromptGenerator(config=dict(config) if config is not None else None)
    contexts = [VideoPromptContext(start_prompt="a cat"),
                VideoPromptContext(start_prompt="a dog")]
    return gen.batch_generate_video_prompts(contexts, provider, model, temperature=0.7)


SITES = [_single, _batch]


@pytest.mark.parametrize("site", SITES, ids=lambda f: f.__name__)
def test_reasoning_model_gets_completion_tokens_and_no_temperature(completion, site):
    site("openai", "gpt-5-test")
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "gpt-5-test"
    assert "max_completion_tokens" in kwargs
    assert "max_tokens" not in kwargs
    assert "temperature" not in kwargs


@pytest.mark.parametrize("site", SITES, ids=lambda f: f.__name__)
def test_classic_model_keeps_max_tokens_and_temperature(completion, site):
    site("openai", "gpt-4-test")
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "gpt-4-test"
    assert "max_tokens" in kwargs and "max_completion_tokens" not in kwargs
    assert kwargs["temperature"] == 0.7


@pytest.mark.parametrize("site", SITES, ids=lambda f: f.__name__)
@pytest.mark.parametrize("provider,model,expected", [
    ("OpenAI", "gpt-4-test", "gpt-4-test"),
    ("Anthropic", "claude-test-model", "anthropic/claude-test-model"),
    ("claude", "claude-test-model", "anthropic/claude-test-model"),
    ("Google", "gemini-test-model", "gemini/gemini-test-model"),
    ("Ollama", "local-test-model", "ollama/local-test-model"),
    ("lm studio", "local-test-model", "local-test-model"),
])
def test_display_names_route(completion, site, provider, model, expected):
    site(provider, model)
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == expected
    if expected == "local-test-model":
        assert kwargs["api_base"] == "http://localhost:1234/v1"


def test_single_google_gcloud_auth_uses_vertex_without_key(completion):
    gen = VideoPromptGenerator(config=None)
    gen.config = mock.MagicMock()
    gen.config.get.side_effect = lambda k, d=None: "gcloud" if k == "auth_mode" else d
    gen.generate_video_prompt(VideoPromptContext(start_prompt="a cat"),
                              "google", "gemini-test-model")
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "vertex_ai/gemini-test-model"
    assert "api_key" not in kwargs


def test_single_passes_configured_key(completion):
    _single("Anthropic", "claude-test-model", {"anthropic_api_key": "the-key"})
    assert completion.call_args.kwargs["api_key"] == "the-key"


# --- R2: configured local endpoints are used ----------------------------------

@pytest.mark.parametrize("site", SITES, ids=lambda f: f.__name__)
@pytest.mark.parametrize("provider,key,endpoint,expected_model", [
    ("LM Studio", "lmstudio_endpoint", "http://lm-host:4321/v1", "local-test-model"),
    ("Ollama", "ollama_endpoint", "http://ollama-host:5678", "ollama/local-test-model"),
])
def test_configured_local_endpoint_is_the_api_base(completion, site, provider, key,
                                                    endpoint, expected_model):
    site(provider, "local-test-model", {key: endpoint})
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == expected_model
    assert kwargs["api_base"] == endpoint


@pytest.mark.parametrize("site", SITES, ids=lambda f: f.__name__)
def test_ollama_without_configured_endpoint_has_no_api_base(completion, site):
    site("Ollama", "local-test-model", {})
    assert "api_base" not in completion.call_args.kwargs
