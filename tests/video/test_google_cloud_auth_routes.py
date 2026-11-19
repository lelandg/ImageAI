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
from core.video.llm_sync_v2 import LLMSyncAssistant as LLMSyncAssistantV2
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

    def __init__(self, google_key=None, **values):
        self._values = values
        self._google_key = google_key
        self.key_lookups = []

    def get(self, key, default=None):
        return self._values.get(key, default)

    def get_api_key(self, provider):
        # as ConfigManager: in gcloud mode the Google lookup is an access token
        self.key_lookups.append(provider)
        if provider != "google":
            return None
        if self._values.get("auth_mode") == "gcloud":
            return TOKEN
        return self._google_key


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


@sites
def test_api_key_mode_sends_its_own_key_explicitly(
        completion, saved_api_key_mode, site):
    """The key travels in the request, not through GEMINI_API_KEY: nothing is
    exported, so no other object's routing can depend on it."""
    site({"google_api_key": "stored-key", "gcloud_project_id": "saved-project"})
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == f"gemini/{MODEL}"
    assert kwargs["api_key"] == "stored-key"
    assert "vertex_project" not in kwargs
    assert "GEMINI_API_KEY" not in os.environ


# --- two objects with different Google settings do not affect each other ------

API_KEY_DICT = {"google_api_key": "stored-key", "auth_mode": "api-key"}

MAKERS = {
    "provider": lambda c: (lambda p: lambda: p.enhance_prompt("a cat", "google", MODEL))(
        UnifiedLLMProvider(dict(c))),
    "provider_batch": lambda c: (lambda p: lambda: p.batch_enhance(
        ["a cat", "a dog"], "google", MODEL))(UnifiedLLMProvider(dict(c))),
    "analyze_image": lambda c: (lambda p: lambda: p.analyze_image(
        [{"role": "user", "content": "describe"}], model=MODEL, max_retries=0))(
        UnifiedLLMProvider(dict(c))),
    "prompt_engine": lambda c: (lambda e: lambda: e.enhance_for_video(
        "a cat", "google", MODEL))(PromptEngine(UnifiedLLMProvider(dict(c)))),
    "scene_suggester": lambda c: (lambda s: lambda: s._call_llm(
        "tag these lyrics", "google", MODEL, 0.7))(SceneSuggester(dict(c))),
    "llm_sync": lambda c: (lambda a: lambda: a.sync_with_llm("la la", None, 30.0))(
        LLMSyncAssistant("google", MODEL, dict(c))),
    "llm_sync_v2": lambda c: (lambda a: lambda: a._sync_single_section_with_gemini(
        "la la", None, 30.0, None))(LLMSyncAssistantV2("gemini", MODEL, dict(c))),
    "lyrics": lambda c: (lambda g: lambda: g.generate(["line one"], model=MODEL))(
        LyricsToPromptsGenerator(dict(c))),
}
makers = pytest.mark.parametrize("make", list(MAKERS.values()), ids=list(MAKERS))


def _call(completion, call):
    completion.reset_mock()
    call()
    return completion.call_args.kwargs


def _assert_api_key_route(kwargs):
    assert kwargs["model"] == f"gemini/{MODEL}"
    assert kwargs["api_key"] == "stored-key"


@makers
def test_api_key_object_first_then_gcloud_object(completion, make):
    first = make(API_KEY_DICT)          # object A: API-key mode
    _assert_api_key_route(_call(completion, first))
    second = make(GCLOUD_DICT)          # object B: Google Cloud login
    _assert_vertex(_call(completion, second), "saved-project")
    # creating and using B changed nothing for A
    _assert_api_key_route(_call(completion, first))
    assert "GEMINI_API_KEY" not in os.environ


@makers
def test_gcloud_object_first_then_api_key_object(completion, make):
    first = make(GCLOUD_DICT)
    _assert_vertex(_call(completion, first), "saved-project")
    second = make(API_KEY_DICT)
    _assert_api_key_route(_call(completion, second))
    # creating and using the API-key object changed nothing for the first
    _assert_vertex(_call(completion, first), "saved-project")
    assert "GEMINI_API_KEY" not in os.environ


@makers
def test_keyless_object_is_not_given_another_objects_key(
        completion, saved_api_key_mode, make):
    keyless = make({})
    make(API_KEY_DICT)
    kwargs = _call(completion, keyless)
    assert kwargs["model"] == f"gemini/{MODEL}"   # API-key mode: never Vertex
    assert "api_key" not in kwargs


@sites
def test_api_key_mode_without_any_key_stays_on_the_gemini_route(
        completion, saved_api_key_mode, site):
    """A missing key is an authentication error on gemini/ (the package's
    AuthError when it really runs), never a silent move to Vertex."""
    site({})
    for call in completion.call_args_list:
        assert call.kwargs["model"] == f"gemini/{MODEL}"
        assert "api_key" not in call.kwargs
        assert "vertex_project" not in call.kwargs


@sites
def test_api_key_mode_reads_the_settings_key_when_the_dict_has_none(
        completion, monkeypatch, site):
    """A key stored in the keyring is not in the config dict some callers
    build with ``config.get('google_api_key')``; the object looks it up
    through ``get_api_key`` and sends it."""
    saved = _Saved(google_key="settings-key", auth_mode="api-key")
    monkeypatch.setattr(llm_params, "_saved_settings", lambda: saved)
    site({"google_api_key": None})
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == f"gemini/{MODEL}"
    assert kwargs["api_key"] == "settings-key"
    assert "GEMINI_API_KEY" not in os.environ


def test_the_dict_key_wins_and_no_lookup_is_made(completion, monkeypatch):
    saved = _Saved(google_key="settings-key", auth_mode="api-key")
    monkeypatch.setattr(llm_params, "_saved_settings", lambda: saved)
    _provider({"google_api_key": "dict-key"}).enhance_prompt("a cat", "google", MODEL)
    assert completion.call_args.kwargs["api_key"] == "dict-key"
    assert saved.key_lookups == []


def test_the_settings_key_is_looked_up_once_per_object(completion, monkeypatch):
    saved = _Saved(google_key="settings-key", auth_mode="api-key")
    monkeypatch.setattr(llm_params, "_saved_settings", lambda: saved)
    provider = _provider({})
    provider.enhance_prompt("a cat", "google", MODEL)
    provider.batch_enhance(["a cat", "a dog"], "google", MODEL)
    assert saved.key_lookups == ["google"]


@sites
def test_gcloud_mode_never_looks_up_a_google_key(completion, monkeypatch, site):
    """In gcloud mode ``get_api_key('google')`` would answer with a token."""
    saved = _Saved(auth_mode="gcloud", gcloud_project_id="settings-project")
    monkeypatch.setattr(llm_params, "_saved_settings", lambda: saved)
    site({})
    assert saved.key_lookups == []
    _assert_vertex(completion.call_args.kwargs, "settings-project")


def test_dict_says_api_key_but_settings_say_gcloud_makes_no_lookup(
        completion, monkeypatch):
    """The saved lookup would be a token; an explicit api-key dict gets none."""
    saved = _Saved(auth_mode="gcloud")
    monkeypatch.setattr(llm_params, "_saved_settings", lambda: saved)
    _provider({"auth_mode": "api-key"}).enhance_prompt("a cat", "google", MODEL)
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == f"gemini/{MODEL}"
    assert "api_key" not in kwargs
    assert saved.key_lookups == []


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


def test_analyze_image_sends_lm_studio_endpoint_to_lm_studio_only(completion):
    provider = _provider({"lmstudio_endpoint": "http://lm-host:4321/v1",
                          "openai_api_key": "openai-key"})
    messages = [{"role": "user", "content": "describe"}]
    provider.analyze_image(messages, model="lm_studio/llava", max_retries=0)
    kwargs = completion.call_args.kwargs
    assert kwargs["api_base"] == "http://lm-host:4321/v1"
    assert "api_key" not in kwargs
    provider.analyze_image(messages, model="gpt-4-test", max_retries=0)
    assert "api_base" not in completion.call_args.kwargs


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
