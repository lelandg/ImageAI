"""StyleAnalyzer sends its vision request through the shared builder.

Its Google branch used to build ``genai.Client(api_key=...)`` itself: with
Google Cloud login that was ``api_key=None`` and no Vertex configuration (or,
from the video tab, an OAuth access token used as an API key).

``chameleon_llm.completion`` is a recorder here: nothing reaches a provider.
"""
import base64
from types import SimpleNamespace
from unittest import mock

import pytest

from core import chameleon_llm
from core import llm_params
from core.video.style_analyzer import StyleAnalyzer

IMAGE = b"\x89PNG\r\n\x1a\n-not-a-real-image"
TOKEN = "oauth-access-token-not-an-api-key"
MODEL = "gemini-test-model"
_ENV = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "OPENAI_API_BASE", "OLLAMA_API_BASE")


class _Saved:
    def __init__(self, **values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in _ENV:
        monkeypatch.setenv(name, "x")
        monkeypatch.delenv(name)
    # Settings: API-key mode, unless a test says otherwise
    monkeypatch.setattr(llm_params, "_saved_settings",
                        lambda: _Saved(auth_mode="api-key"))


@pytest.fixture(autouse=True)
def _no_direct_sdk_client(monkeypatch):
    """The analyzer must not build its own google-genai client any more."""
    genai = pytest.importorskip("google.genai")

    def _refuse(*_args, **_kwargs):
        raise AssertionError("StyleAnalyzer built a google.genai.Client itself")

    monkeypatch.setattr(genai, "Client", _refuse)


@pytest.fixture
def completion():
    reply = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=" warm film grain "),
                                 finish_reason="stop")],
        usage=None, model="fake")

    def _fake(**kwargs):
        chameleon_llm.resolve_route(kwargs["model"], kwargs.get("api_base"))
        return reply

    with mock.patch("core.chameleon_llm.completion", side_effect=_fake) as m:
        yield m


@pytest.fixture
def frame(tmp_path):
    path = tmp_path / "previous.png"
    path.write_bytes(IMAGE)
    return path


def _image_urls(kwargs):
    return [part["image_url"]["url"]
            for message in kwargs["messages"] if isinstance(message["content"], list)
            for part in message["content"] if part.get("type") == "image_url"]


def test_google_api_key_mode_uses_the_gemini_route(completion, frame):
    analyzer = StyleAnalyzer(api_key="stored-key", llm_provider="google",
                             llm_model=MODEL)
    assert analyzer.analyze_for_style(frame) == "warm film grain"
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == f"gemini/{MODEL}"
    assert kwargs["api_key"] == "stored-key"
    assert kwargs["temperature"] == 0.7 and kwargs["max_tokens"] == 1000
    assert "vertex_project" not in kwargs
    expected = "data:image/png;base64," + base64.b64encode(IMAGE).decode()
    assert _image_urls(kwargs) == [expected]


@pytest.mark.parametrize("api_key", [None, TOKEN])
def test_google_cloud_mode_uses_vertex_with_the_project_and_no_key(
        completion, frame, api_key):
    analyzer = StyleAnalyzer(api_key=api_key, llm_provider="google", llm_model=MODEL,
                             auth_mode="gcloud", vertex_project="saved-project")
    assert analyzer.analyze_for_transition(frame, "next scene") == "warm film grain"
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == f"vertex_ai/{MODEL}"
    assert "api_key" not in kwargs
    assert kwargs["vertex_project"] == "saved-project"
    assert len(_image_urls(kwargs)) == 1


def test_google_cloud_mode_is_read_from_settings_when_not_passed(
        completion, frame, monkeypatch):
    """The video tab passes only ``get_api_key('google')``: an access token."""
    monkeypatch.setattr(llm_params, "_saved_settings", lambda: _Saved(
        auth_mode="gcloud", gcloud_project_id="settings-project"))
    analyzer = StyleAnalyzer(api_key=TOKEN, llm_provider="gemini", llm_model=MODEL)
    analyzer.analyze_for_style(frame)
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == f"vertex_ai/{MODEL}"
    assert "api_key" not in kwargs
    assert kwargs["vertex_project"] == "settings-project"


def test_the_request_is_one_the_gemini_adapter_accepts(completion, frame):
    """Run the recorded messages through the real adapter's request builder."""
    pytest.importorskip("google.genai")
    from core.chameleon_llm import gemini_adapter
    from core.chameleon_llm.routing import Route

    StyleAnalyzer(api_key="stored-key", llm_provider="google",
                  llm_model=MODEL).analyze_for_style(frame)
    kwargs = completion.call_args.kwargs
    request = gemini_adapter._build_request(
        Route("gemini", "gemini", MODEL), kwargs["messages"],
        {"temperature": kwargs["temperature"], "max_tokens": kwargs["max_tokens"]})
    parts = [p for content in request["contents"] for p in content.parts]
    blobs = [p.inline_data for p in parts if p.inline_data is not None]
    assert len(blobs) == 1
    assert blobs[0].data == IMAGE and blobs[0].mime_type == "image/png"
    assert any(p.text and "visual style" in p.text for p in parts)


@pytest.mark.parametrize("provider,model", [
    ("google", "ollama/llava-test"),
    ("openai", "ollama/llava-test"),
    ("openai", "lm_studio/llava-test"),
    ("anthropic", "ollama/llava-test"),
    ("openai", "anthropic/claude-test-model"),
])
def test_the_single_key_never_goes_to_another_providers_route(
        completion, frame, provider, model):
    analyzer = StyleAnalyzer(api_key="cloud-provider-key", llm_provider=provider,
                             llm_model=model)
    analyzer.analyze_for_style(frame)
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == model
    assert "api_key" not in kwargs


@pytest.mark.parametrize("provider,model,expected", [
    ("openai", "gpt-test-model", "gpt-test-model"),
    ("anthropic", "claude-test-model", "anthropic/claude-test-model"),
    ("claude", "claude-test-model", "anthropic/claude-test-model"),
])
def test_other_providers_keep_their_key(completion, frame, provider, model, expected):
    StyleAnalyzer(api_key="own-key", llm_provider=provider,
                  llm_model=model).analyze_for_style(frame)
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == expected
    assert kwargs["api_key"] == "own-key"
