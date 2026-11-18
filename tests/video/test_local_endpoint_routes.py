"""Video call sites build their request through route_completion_kwargs.

Each site used to glue the provider prefix on by hand. That sent LM Studio
requests to cloud OpenAI ("openai/<model>" with no api_base) and kept Gemini
on the API-key route when the user signs in with Google Cloud.

``chameleon_llm.completion`` is a recorder here: nothing reaches a provider.
"""
from types import SimpleNamespace
from unittest import mock

import pytest

from core import chameleon_llm
from core.video.end_prompt_generator import EndPromptContext, EndPromptGenerator
from core.video.llm_sync import LLMSyncAssistant
from core.video.project import Scene
from core.video.prompt_engine import UnifiedLLMProvider
from core.video.scene_suggester import SceneSuggester
from core.video.storyboard_v2 import EnhancedStoryboardGenerator

LM_BASE = "http://lm-host:4321/v1"
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
        choices=[SimpleNamespace(message=SimpleNamespace(content="[]"),
                                 finish_reason="stop")],
        usage=None, model="fake")

    def _fake(**kwargs):
        # fail like the real dispatcher on a model id it cannot route
        chameleon_llm.resolve_route(kwargs["model"], kwargs.get("api_base"))
        return reply

    with mock.patch("core.chameleon_llm.completion", side_effect=_fake) as m:
        yield m


def _scene_suggester(config, provider, model):
    SceneSuggester(dict(config))._call_llm("tag these lyrics", provider, model, 0.7)


def _storyboard(config):
    return EnhancedStoryboardGenerator(UnifiedLLMProvider(dict(config)))


def _veo_batches(config, provider, model):
    scenes = [Scene(source="la la", prompt="a cat", duration_sec=4.0),
              Scene(source="da da", prompt="a dog", duration_sec=4.0)]
    _storyboard(config)._generate_veo_batches(
        scenes, "la la\nda da", "Song", "cinematic", provider, model)


def _structured_json(config, provider, model):
    _storyboard(config)._generate_structured_json(
        "la la", "Song", 30, provider, model, "cinematic", "")


def _directors_treatment(config, provider, model):
    _storyboard(config)._generate_directors_treatment(
        "la la", "Song", 30, provider, model, "cinematic", "")


def _llm_sync(config, provider, model):
    LLMSyncAssistant(provider, model, dict(config)).sync_with_llm(
        "la la\nda da", None, 30.0)


def _end_prompt(config, provider, model):
    EndPromptGenerator(UnifiedLLMProvider(dict(config))).generate_end_prompt(
        EndPromptContext(start_prompt="a cat"), provider, model)


SITES = [_scene_suggester, _veo_batches, _structured_json, _directors_treatment,
         _llm_sync, _end_prompt]
sites = pytest.mark.parametrize("site", SITES, ids=lambda f: f.__name__)


@sites
@pytest.mark.parametrize("provider", ["lmstudio", "LM Studio"])
def test_lm_studio_goes_to_the_configured_endpoint(completion, site, provider):
    site({"lmstudio_endpoint": LM_BASE, "openai_api_key": "cloud-openai-key"},
         provider, "local-test-model")
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "local-test-model"
    assert kwargs["api_base"] == LM_BASE
    assert "api_key" not in kwargs


@sites
def test_lm_studio_without_a_configured_endpoint_uses_the_default(completion, site):
    site({}, "lmstudio", "local-test-model")
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "local-test-model"
    assert kwargs["api_base"] == "http://localhost:1234/v1"


@sites
@pytest.mark.parametrize("provider,model,expected", [
    ("openai", "gpt-4-test", "gpt-4-test"),
    ("anthropic", "claude-test-model", "anthropic/claude-test-model"),
    ("claude", "claude-test-model", "anthropic/claude-test-model"),
    ("ollama", "llama-test", "ollama/llama-test"),
])
def test_cloud_and_ollama_requests_never_get_the_lm_studio_endpoint(
        completion, site, provider, model, expected):
    site({"lmstudio_endpoint": LM_BASE}, provider, model)
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == expected
    assert "api_base" not in kwargs


@sites
@pytest.mark.parametrize("provider", ["gemini", "google"])
def test_gemini_with_a_key_uses_the_api_key_route(completion, site, provider):
    site({"google_api_key": "k", "lmstudio_endpoint": LM_BASE,
          "gcloud_project_id": "saved-project"}, provider, "gemini-test-model")
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "gemini/gemini-test-model"
    assert "api_base" not in kwargs
    assert "vertex_project" not in kwargs


@sites
@pytest.mark.parametrize("provider", ["gemini", "google"])
def test_gemini_without_a_key_uses_vertex_with_the_saved_project(
        completion, site, provider):
    """No Gemini key anywhere means Google Cloud login: vertex_ai/, and the
    project saved in Settings when the provider config carries it."""
    site({"gcloud_project_id": "saved-project", "lmstudio_endpoint": LM_BASE},
         provider, "gemini-test-model")
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "vertex_ai/gemini-test-model"
    assert kwargs["vertex_project"] == "saved-project"
    assert "api_base" not in kwargs and "api_key" not in kwargs


@sites
def test_reasoning_model_params_are_corralled(completion, site):
    site({}, "openai", "gpt-5-test")
    kwargs = completion.call_args.kwargs
    assert "temperature" not in kwargs
    assert "max_tokens" not in kwargs


def test_llm_sync_keeps_json_mode_for_openai_only(completion):
    _llm_sync({}, "openai", "gpt-4-test")
    assert completion.call_args.kwargs["response_format"] == {"type": "json_object"}
    _llm_sync({}, "anthropic", "claude-test-model")
    assert "response_format" not in completion.call_args.kwargs
