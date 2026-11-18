"""Bare Claude/Gemini model ids must reach chameleon_llm with a route prefix.

chameleon_llm never guesses a provider from a model name, so every call site
that receives a bare id builds its arguments with ``build_completion_kwargs``.
"""
from types import SimpleNamespace
from unittest import mock

import pytest

from core.lyrics_to_prompts import LyricsToPromptsGenerator
from core.video.prompt_engine import PromptEngine, UnifiedLLMProvider
from core.video.style_analyzer import StyleAnalyzer


def _fake_response(text="{}"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text),
                                 finish_reason="stop")],
        usage=None,
        model="fake",
    )


@pytest.fixture
def gemini_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)


@pytest.fixture
def no_gemini_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)


@pytest.fixture
def completion():
    with mock.patch("core.chameleon_llm.completion",
                    return_value=_fake_response("ok")) as m:
        yield m


@pytest.mark.parametrize("model,prefixes", [
    ("claude-test-model", ("anthropic/",)),
    ("gemini-test-model", ("gemini/",)),
    ("gpt-test-model", ("openai/", "gpt-test-model")),
])
def test_analyze_image_routes_bare_ids(completion, gemini_key, model, prefixes):
    provider = UnifiedLLMProvider({})
    out = provider.analyze_image(
        [{"role": "user", "content": "describe"}], model=model, max_retries=0)
    assert out == "ok"
    routed = completion.call_args.kwargs["model"]
    assert routed.startswith(prefixes), routed


@pytest.mark.parametrize("model,prefixes", [
    ("claude-test-model", ("anthropic/",)),
    ("gemini-test-model", ("gemini/",)),
])
def test_lyrics_to_prompts_routes_bare_ids(completion, gemini_key, model, prefixes):
    completion.return_value = _fake_response('{"prompts": []}')
    gen = LyricsToPromptsGenerator({})
    gen.generate(["line one"], model=model)
    routed = completion.call_args.kwargs["model"]
    assert routed.startswith(prefixes), routed


@pytest.mark.parametrize("model,method,prefixes", [
    ("claude-test-model", "_analyze_with_anthropic", ("anthropic/",)),
    ("gemini-test-model", "_analyze_with_openai", ("gemini/",)),
])
def test_style_analyzer_routes_bare_ids(completion, model, method, prefixes):
    analyzer = StyleAnalyzer.__new__(StyleAnalyzer)
    analyzer.llm_model = model
    analyzer.api_key = "test-key"
    out = getattr(analyzer, method)(b"\x89PNG", "image/png", "describe")
    assert out == "ok"
    routed = completion.call_args.kwargs["model"]
    assert routed.startswith(prefixes), routed


# Alias providers ("google") must reach chameleon_llm with a route prefix.
def _enhance(provider, model):
    return UnifiedLLMProvider({}).enhance_prompt("a cat", provider, model)


def _batch(provider, model):
    return UnifiedLLMProvider({}).batch_enhance(["a cat", "a dog"], provider, model)


def _batch_video(provider, model):
    return UnifiedLLMProvider({}).batch_enhance_for_video(
        ["a cat", "a dog"], provider, model)


def _enhance_for_video(provider, model):
    return PromptEngine(UnifiedLLMProvider({})).enhance_for_video(
        "a cat", provider, model)


ALIAS_SITES = [_enhance, _batch, _batch_video, _enhance_for_video]


@pytest.mark.parametrize("site", ALIAS_SITES, ids=lambda f: f.__name__)
def test_google_alias_uses_api_key_route_when_key_set(completion, gemini_key, site):
    site("google", "gemini-test-model")
    assert completion.call_args.kwargs["model"] == "gemini/gemini-test-model"


@pytest.mark.parametrize("site", ALIAS_SITES, ids=lambda f: f.__name__)
def test_google_alias_uses_vertex_route_without_key(completion, no_gemini_key, site):
    site("google", "gemini-test-model")
    assert completion.call_args.kwargs["model"] == "vertex_ai/gemini-test-model"
