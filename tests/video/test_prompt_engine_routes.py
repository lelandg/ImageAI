"""Bare Claude/Gemini model ids must reach chameleon_llm with a route prefix.

chameleon_llm never guesses a provider from a model name, so every call site
that receives a bare id builds its arguments with ``build_completion_kwargs``.
"""
from types import SimpleNamespace
from unittest import mock

import pytest

from core.lyrics_to_prompts import LyricsToPromptsGenerator
from core.video.prompt_engine import UnifiedLLMProvider
from core.video.style_analyzer import StyleAnalyzer


def _fake_response(text="{}"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text),
                                 finish_reason="stop")],
        usage=None,
        model="fake",
    )


@pytest.fixture
def completion():
    with mock.patch("core.chameleon_llm.completion",
                    return_value=_fake_response("ok")) as m:
        yield m


@pytest.mark.parametrize("model,prefixes", [
    ("claude-test-model", ("anthropic/",)),
    ("gemini-test-model", ("gemini/", "vertex_ai/")),
    ("gpt-test-model", ("openai/", "gpt-test-model")),
])
def test_analyze_image_routes_bare_ids(completion, model, prefixes):
    provider = UnifiedLLMProvider({})
    out = provider.analyze_image(
        [{"role": "user", "content": "describe"}], model=model, max_retries=0)
    assert out == "ok"
    routed = completion.call_args.kwargs["model"]
    assert routed.startswith(prefixes), routed


@pytest.mark.parametrize("model,prefixes", [
    ("claude-test-model", ("anthropic/",)),
    ("gemini-test-model", ("gemini/", "vertex_ai/")),
])
def test_lyrics_to_prompts_routes_bare_ids(completion, model, prefixes):
    completion.return_value = _fake_response('{"prompts": []}')
    gen = LyricsToPromptsGenerator({})
    gen.generate(["line one"], model=model)
    routed = completion.call_args.kwargs["model"]
    assert routed.startswith(prefixes), routed


@pytest.mark.parametrize("model,method,prefixes", [
    ("claude-test-model", "_analyze_with_anthropic", ("anthropic/",)),
    ("gemini-test-model", "_analyze_with_openai", ("gemini/", "vertex_ai/")),
])
def test_style_analyzer_routes_bare_ids(completion, model, method, prefixes):
    analyzer = StyleAnalyzer.__new__(StyleAnalyzer)
    analyzer.llm_model = model
    analyzer.api_key = "test-key"
    out = getattr(analyzer, method)(b"\x89PNG", "image/png", "describe")
    assert out == "ok"
    routed = completion.call_args.kwargs["model"]
    assert routed.startswith(prefixes), routed
