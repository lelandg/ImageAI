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


# --- I5b: an LM Studio endpoint stays on the object, never in OPENAI_API_BASE -

@pytest.fixture
def no_openai_base(monkeypatch):
    # set-then-delete so monkeypatch also undoes a value the app writes
    monkeypatch.setenv("OPENAI_API_BASE", "x")
    monkeypatch.delenv("OPENAI_API_BASE")


def test_lyrics_lmstudio_endpoint_not_set_process_wide(completion, no_openai_base):
    import os
    LyricsToPromptsGenerator({"lmstudio_endpoint": "http://lm-host:1234/v1"})
    assert "OPENAI_API_BASE" not in os.environ


def test_lyrics_local_model_goes_to_configured_lmstudio(completion, no_openai_base):
    completion.return_value = _fake_response('{"prompts": []}')
    gen = LyricsToPromptsGenerator({"lmstudio_endpoint": "http://lm-host:1234/v1"})
    gen.generate(["line one"], model="local-test-model")
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "local-test-model"
    assert kwargs["api_base"] == "http://lm-host:1234/v1"


def test_lyrics_cloud_model_ignores_lmstudio_endpoint(completion, no_openai_base):
    completion.return_value = _fake_response('{"prompts": []}')
    gen = LyricsToPromptsGenerator({"lmstudio_endpoint": "http://lm-host:1234/v1"})
    gen.generate(["line one"], model="gpt-test-model")
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "gpt-test-model"
    assert "api_base" not in kwargs


@pytest.mark.parametrize("model", ["gpt-oss-20b", "gpt-oss:20b"])
def test_lyrics_gpt_oss_goes_to_configured_lmstudio(completion, no_openai_base,
                                                    model):
    """An open-weight gpt-oss id is a local model, not cloud OpenAI: it keeps
    the configured LM Studio endpoint and never gets the OpenAI key."""
    completion.return_value = _fake_response('{"prompts": []}')
    gen = LyricsToPromptsGenerator({
        "lmstudio_endpoint": "http://lm-host:1234/v1",
        "openai_api_key": "cloud-openai-key"})
    gen.generate(["line one"], model=model)
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == model
    assert kwargs["api_base"] == "http://lm-host:1234/v1"
    assert "api_key" not in kwargs


# --- analyze_image: the credential follows the resolved provider --------------

ALL_KEYS = {"openai_api_key": "cloud-openai-key",
            "anthropic_api_key": "cloud-anthropic-key",
            "google_api_key": "cloud-google-key"}
CLOUD_KEYS = set(ALL_KEYS.values())


@pytest.fixture(autouse=True)
def _restore_key_env(monkeypatch):
    # UnifiedLLMProvider copies configured keys into os.environ; set-then-
    # delete makes monkeypatch put the environment back after each test.
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setenv(name, "x")
        monkeypatch.delenv(name)


def _analyze(model, config=ALL_KEYS):
    provider = UnifiedLLMProvider(dict(config))
    provider.analyze_image(
        [{"role": "user", "content": "describe"}], model=model, max_retries=0)


@pytest.mark.parametrize("model", [
    "ollama/gpt-oss:20b",          # "gpt" in a local model's name
    "ollama/openai-community-x",   # "openai" in a local model's name
    "ollama/claude-style-llama",
    "ollama_chat/gemini-like:7b",
    "lm_studio/gpt-oss-20b",
    "ollama/llava:13b",
])
def test_analyze_image_never_hands_a_cloud_key_to_a_local_route(
        completion, no_openai_base, model):
    _analyze(model)
    kwargs = completion.call_args.kwargs
    assert kwargs.get("api_key") not in CLOUD_KEYS, kwargs.get("model")
    assert "api_key" not in kwargs


@pytest.mark.parametrize("model,expected_key,route", [
    ("gpt-test-model", "cloud-openai-key", "gpt-test-model"),
    ("openai/gpt-test-model", "cloud-openai-key", "openai/gpt-test-model"),
    ("claude-test-model", "cloud-anthropic-key", "anthropic/claude-test-model"),
    ("anthropic/claude-test-model", "cloud-anthropic-key",
     "anthropic/claude-test-model"),
    ("gemini-test-model", "cloud-google-key", "gemini/gemini-test-model"),
    # A name that mentions another vendor still gets its own provider's key.
    ("anthropic/claude-gpt-hybrid", "cloud-anthropic-key",
     "anthropic/claude-gpt-hybrid"),
    ("gemini/gemini-openai-compat", "cloud-google-key",
     "gemini/gemini-openai-compat"),
])
def test_analyze_image_key_matches_the_resolved_provider(
        completion, no_openai_base, model, expected_key, route):
    _analyze(model)
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == route
    assert kwargs["api_key"] == expected_key


def test_analyze_image_without_a_configured_key_sends_none(
        completion, no_openai_base):
    _analyze("gpt-test-model", config={})
    assert "api_key" not in completion.call_args.kwargs


# --- the saved Google Cloud project reaches every Vertex call ------------------

_PROJECT = {"gcloud_project_id": "saved-project"}
_VERTEX_SITES = [
    lambda cfg: UnifiedLLMProvider(cfg).enhance_prompt(
        "a cat", "google", "gemini-test-model"),
    lambda cfg: UnifiedLLMProvider(cfg).batch_enhance(
        ["a cat", "a dog"], "google", "gemini-test-model"),
    lambda cfg: UnifiedLLMProvider(cfg).batch_enhance_for_video(
        ["a cat", "a dog"], "google", "gemini-test-model"),
    lambda cfg: PromptEngine(UnifiedLLMProvider(cfg)).enhance_for_video(
        "a cat", "google", "gemini-test-model"),
    lambda cfg: UnifiedLLMProvider(cfg).analyze_image(
        [{"role": "user", "content": "describe"}], model="gemini-test-model",
        max_retries=0),
]
_VERTEX_IDS = ["enhance", "batch", "batch_video", "enhance_for_video",
               "analyze_image"]


@pytest.mark.parametrize("site", _VERTEX_SITES, ids=_VERTEX_IDS)
def test_vertex_route_carries_the_saved_project(completion, no_gemini_key, site):
    site(dict(_PROJECT))
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "vertex_ai/gemini-test-model"
    assert kwargs["vertex_project"] == "saved-project"


@pytest.mark.parametrize("site", _VERTEX_SITES, ids=_VERTEX_IDS)
def test_api_key_route_does_not_carry_the_project(completion, site):
    site({**_PROJECT, "google_api_key": "k"})
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "gemini/gemini-test-model"
    assert "vertex_project" not in kwargs


# --- Addendum (httpx2): wrapped transport errors stay retryable ---------------

def test_wrapped_transport_errors_are_retryable():
    from core.chameleon_llm.errors import wrap_sdk_error

    class TransportError(Exception):
        pass

    class ReadError(TransportError):  # httpx/httpx2 shape, no library needed
        pass

    class ReadTimeout(TransportError):
        pass

    provider = UnifiedLLMProvider({})
    for exc in (ReadError("reset"), ReadTimeout("slow")):
        assert provider._is_retryable_error(wrap_sdk_error(exc, "gemini"))
