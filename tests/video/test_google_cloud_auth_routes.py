"""Google Cloud login (gcloud auth mode) through UnifiedLLMProvider and friends.

In that mode ``ConfigManager.get_api_key("google")`` answers with an OAuth
access token, and the GUI puts it in the provider config as ``google_api_key``.
It is not a Gemini API key: nothing may export it as ``GEMINI_API_KEY`` or send
it as ``api_key``, and Gemini models must take ``vertex_ai/`` with the project
saved in Settings.

``chameleon_llm.completion`` is a recorder here: nothing reaches a provider.
"""
import os
from types import SimpleNamespace
from unittest import mock

import pytest

from core import chameleon_llm
from core import llm_params
from core.lyrics_to_prompts import LyricsToPromptsGenerator
from core.prompt_enhancer_llm import PromptEnhancerLLM
from core.video.end_prompt_generator import EndPromptContext, EndPromptGenerator
from core.video.llm_sync import LLMSyncAssistant
from core.video.prompt_engine import PromptEngine, UnifiedLLMProvider
from core.video.scene_suggester import SceneSuggester
from core.video.storyboard_v2 import EnhancedStoryboardGenerator

TOKEN = "oauth-access-token-not-an-api-key"
MODEL = "gemini-test-model"
_ENV = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "OPENAI_API_BASE", "OLLAMA_API_BASE")

# What the GUI dict builders hand over in gcloud mode, plus the mode itself.
GCLOUD_DICT = {"google_api_key": TOKEN, "auth_mode": "gcloud",
               "gcloud_project_id": "saved-project"}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in _ENV:
        monkeypatch.setenv(name, "x")
        monkeypatch.delenv(name)
    llm_params._forget_exported_gemini_keys()
    yield
    llm_params._forget_exported_gemini_keys()


@pytest.fixture
def completion():
    reply = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="[]"),
                                 finish_reason="stop")],
        usage=None, model="fake")

    def _fake(**kwargs):
        chameleon_llm.resolve_route(kwargs["model"], kwargs.get("api_base"))
        return reply

    with mock.patch("core.chameleon_llm.completion", side_effect=_fake) as m:
        yield m


class _Saved:
    """Stands in for the ConfigManager that holds the saved Settings."""

    def __init__(self, **values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


@pytest.fixture
def saved_gcloud(monkeypatch):
    """Settings say: Google Cloud login, project "settings-project"."""
    monkeypatch.setattr(llm_params, "_saved_settings", lambda: _Saved(
        auth_mode="gcloud", gcloud_project_id="settings-project"))


@pytest.fixture
def saved_api_key_mode(monkeypatch):
    monkeypatch.setattr(llm_params, "_saved_settings",
                        lambda: _Saved(auth_mode="api-key"))


def _provider(config):
    return UnifiedLLMProvider(dict(config))


SITES = {
    "enhance_prompt": lambda c: _provider(c).enhance_prompt("a cat", "google", MODEL),
    "batch_enhance": lambda c: _provider(c).batch_enhance(
        ["a cat", "a dog"], "google", MODEL),
    "batch_enhance_for_video": lambda c: _provider(c).batch_enhance_for_video(
        ["a cat", "a dog"], "google", MODEL),
    "enhance_for_video": lambda c: PromptEngine(_provider(c)).enhance_for_video(
        "a cat", "google", MODEL),
    "analyze_image": lambda c: _provider(c).analyze_image(
        [{"role": "user", "content": "describe"}], model=MODEL, max_retries=0),
    "scene_suggester": lambda c: SceneSuggester(dict(c))._call_llm(
        "tag these lyrics", "google", MODEL, 0.7),
    "storyboard": lambda c: EnhancedStoryboardGenerator(
        _provider(c))._generate_structured_json(
            "la la", "Song", 30, "google", MODEL, "cinematic", ""),
    "llm_sync": lambda c: LLMSyncAssistant("google", MODEL, dict(c)).sync_with_llm(
        "la la", None, 30.0),
    "end_prompt": lambda c: EndPromptGenerator(_provider(c)).generate_end_prompt(
        EndPromptContext(start_prompt="a cat"), "google", MODEL),
    "prompt_enhancer": lambda c: PromptEnhancerLLM(_provider(c)).enhance_with_llm(
        prompt="a cat", provider="google", model=MODEL, llm_provider="Google",
        max_tokens=100),
    "lyrics": lambda c: LyricsToPromptsGenerator(dict(c)).generate(
        ["line one"], model=MODEL),
}
sites = pytest.mark.parametrize("site", list(SITES.values()), ids=list(SITES))


def _assert_vertex(kwargs, project):
    assert kwargs["model"] == f"vertex_ai/{MODEL}"
    assert "api_key" not in kwargs
    assert kwargs.get("vertex_project") == project
    assert TOKEN not in repr({k: v for k, v in kwargs.items() if k != "messages"})


@sites
def test_gcloud_mode_in_the_dict_uses_vertex_and_never_the_token(completion, site):
    site(GCLOUD_DICT)
    _assert_vertex(completion.call_args.kwargs, "saved-project")
    assert "GEMINI_API_KEY" not in os.environ


@sites
def test_gcloud_mode_from_saved_settings_when_the_dict_lacks_it(
        completion, saved_gcloud, site):
    """The seven GUI dict builders pass only ``google_api_key`` (the token)."""
    site({"google_api_key": TOKEN})
    _assert_vertex(completion.call_args.kwargs, "settings-project")
    assert "GEMINI_API_KEY" not in os.environ


@sites
def test_gcloud_mode_ignores_a_gemini_key_in_the_environment(
        completion, saved_gcloud, monkeypatch, site):
    monkeypatch.setenv("GEMINI_API_KEY", "user-env-key")
    site({"google_api_key": TOKEN})
    _assert_vertex(completion.call_args.kwargs, "settings-project")
    # the user's own variable is not this code's to delete
    assert os.environ["GEMINI_API_KEY"] == "user-env-key"


def test_gcloud_mode_removes_a_key_an_earlier_provider_exported(
        completion, saved_api_key_mode, monkeypatch):
    UnifiedLLMProvider({"google_api_key": "stored-key"})
    assert os.environ["GEMINI_API_KEY"] == "stored-key"
    # the user switches Settings to Google Cloud login; a new provider is built
    monkeypatch.setattr(llm_params, "_saved_settings",
                        lambda: _Saved(auth_mode="gcloud"))
    UnifiedLLMProvider({"google_api_key": TOKEN})
    assert "GEMINI_API_KEY" not in os.environ


def test_lyrics_gcloud_mode_removes_a_key_exported_earlier(
        completion, saved_api_key_mode, monkeypatch):
    LyricsToPromptsGenerator({"google_api_key": "stored-key"})
    assert os.environ["GEMINI_API_KEY"] == "stored-key"
    monkeypatch.setattr(llm_params, "_saved_settings",
                        lambda: _Saved(auth_mode="gcloud"))
    LyricsToPromptsGenerator({"google_api_key": TOKEN})
    assert "GEMINI_API_KEY" not in os.environ


@sites
def test_api_key_mode_behaves_as_before(completion, saved_api_key_mode, site):
    site({"google_api_key": "stored-key", "gcloud_project_id": "saved-project"})
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == f"gemini/{MODEL}"
    assert "vertex_project" not in kwargs
    assert os.environ["GEMINI_API_KEY"] == "stored-key"


@sites
def test_api_key_mode_without_a_key_still_falls_back_to_vertex(
        completion, saved_api_key_mode, site):
    site({})
    assert completion.call_args.kwargs["model"] == f"vertex_ai/{MODEL}"


@pytest.mark.parametrize("raw", ["gcloud", "Google Cloud Account", "GCLOUD", "adc"])
def test_gcloud_mode_spellings(completion, raw):
    _provider({"google_api_key": TOKEN, "auth_mode": raw}).enhance_prompt(
        "a cat", "google", MODEL)
    assert completion.call_args.kwargs["model"] == f"vertex_ai/{MODEL}"


def test_other_providers_are_untouched_in_gcloud_mode(completion):
    config = {**GCLOUD_DICT, "openai_api_key": "openai-key",
              "anthropic_api_key": "anthropic-key"}
    provider = _provider(config)
    provider.enhance_prompt("a cat", "openai", "gpt-4-test")
    assert completion.call_args.kwargs["model"] == "gpt-4-test"
    provider.analyze_image([{"role": "user", "content": "describe"}],
                           model="claude-test-model", max_retries=0)
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "anthropic/claude-test-model"
    assert kwargs["api_key"] == "anthropic-key"
    assert os.environ["OPENAI_API_KEY"] == "openai-key"


def test_token_is_never_logged(completion, caplog):
    import logging
    with caplog.at_level(logging.DEBUG):
        for site in SITES.values():
            site(GCLOUD_DICT)
    assert TOKEN not in caplog.text


# --- google_auth_settings ------------------------------------------------------

def test_settings_come_from_the_dict_when_it_has_them(monkeypatch):
    monkeypatch.setattr(llm_params, "_saved_settings", lambda: pytest.fail(
        "the saved Settings must not be read when the dict is complete"))
    assert llm_params.google_auth_settings(
        {"auth_mode": "gcloud", "gcloud_project_id": "p"}) == ("gcloud", "p")


def test_settings_fall_back_to_saved_settings(saved_gcloud):
    assert llm_params.google_auth_settings({}) == ("gcloud", "settings-project")
    assert llm_params.google_auth_settings(None) == ("gcloud", "settings-project")
    # the dict's own project wins over the saved one
    assert llm_params.google_auth_settings(
        {"gcloud_project_id": "p"}) == ("gcloud", "p")


def test_settings_default_to_api_key_mode_when_nothing_is_readable(monkeypatch):
    monkeypatch.setattr(llm_params, "_saved_settings", lambda: None)
    assert llm_params.google_auth_settings({}) == ("api-key", None)


def test_real_saved_settings_are_read_from_the_sandbox():
    """Unpatched: the test sandbox has no config.json, so api-key mode."""
    assert llm_params.google_auth_settings({}) == ("api-key", None)
