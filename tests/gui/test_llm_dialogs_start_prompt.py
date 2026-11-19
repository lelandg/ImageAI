"""StartPromptDialog (video start-frame prompt), offscreen, with a fake completion.

The dialog generates on construction; ``inline_threads`` makes that run the
real ``StartPromptGenerationThread.run`` in the test thread.
"""
from unittest.mock import MagicMock

import pytest

from core import chameleon_llm
from gui.video.start_prompt_dialog import StartPromptDialog

CANNED = "A neon-lit rainy street at night, cinematic wide shot"

# (provider, api key, model, expected model)
BRANCHES = [
    pytest.param("openai", "test-key", "gpt-test-model", "gpt-test-model", id="openai"),
    pytest.param("anthropic", "test-key", "claude-test-model",
                 "anthropic/claude-test-model", id="anthropic"),
    pytest.param("claude", "test-key", "claude-test-model",
                 "anthropic/claude-test-model", id="claude-alias"),
    pytest.param("google", "test-key", "gemini-test-model",
                 "gemini/gemini-test-model", id="google-api-key"),
    pytest.param("google", "", "gemini-test-model",
                 "vertex_ai/gemini-test-model", id="google-gcloud"),
]


def _dialog(widgets, provider, api_key, model):
    return widgets(StartPromptDialog(MagicMock(), "rainy street", "", provider, model, api_key))


@pytest.mark.parametrize("provider, api_key, model, expected_model", BRANCHES)
def test_generation_routes_each_provider_and_shows_the_reply(
        widgets, fake_completion, inline_threads, provider, api_key, model, expected_model):
    fake_completion.reply = CANNED

    dialog = _dialog(widgets, provider, api_key, model)

    kwargs = fake_completion.kwargs
    assert kwargs["model"] == expected_model
    assert ("api_key" in kwargs) is bool(api_key)
    assert dialog.get_prompt() == CANNED
    assert dialog.generated_prompt_edit.toPlainText() == CANNED
    widget_text = dialog.status_console.console.toPlainText()
    assert f"{provider}/{model}" in widget_text
    assert CANNED in widget_text
    assert dialog.ok_btn.isEnabled()


def test_rate_limit_is_reported_not_raised(widgets, fake_completion, inline_threads, error_logged):
    fake_completion.error = chameleon_llm.RateLimitError("RateLimitError: slow down",
                                                         provider="test")

    dialog = _dialog(widgets, "openai", "test-key", "gpt-test-model")  # must not raise

    assert len(fake_completion.calls) == 1
    widget_text = dialog.status_console.console.toPlainText()
    assert "RateLimitError: slow down" in widget_text
    assert "RateLimitError: slow down" in dialog.generated_prompt_edit.toPlainText()
    assert error_logged()


# --- the configured Google auth mode reaches the worker -----------------------

OAUTH_TOKEN = "oauth-access-token-not-an-api-key"


def test_gcloud_mode_uses_vertex_and_never_sends_the_oauth_token(
        widgets, fake_completion, inline_threads):
    """In gcloud mode ``get_api_key("google")`` can answer with an OAuth access
    token. Even if one is handed in, it must not travel as a Gemini API key."""
    fake_completion.reply = CANNED

    dialog = widgets(StartPromptDialog(
        MagicMock(), "rainy street", "", "google", "gemini-test-model", OAUTH_TOKEN,
        auth_mode="gcloud", vertex_project="saved-project"))

    kwargs = fake_completion.kwargs
    assert kwargs["model"] == "vertex_ai/gemini-test-model"
    assert "api_key" not in kwargs
    assert kwargs["vertex_project"] == "saved-project"
    assert dialog.get_prompt() == CANNED


def test_gcloud_mode_without_any_key_still_generates(
        widgets, fake_completion, inline_threads):
    fake_completion.reply = CANNED

    dialog = widgets(StartPromptDialog(
        MagicMock(), "rainy street", "", "gemini", "gemini-test-model", None,
        auth_mode="gcloud"))

    kwargs = fake_completion.kwargs
    assert kwargs["model"] == "vertex_ai/gemini-test-model"
    assert "api_key" not in kwargs and "vertex_project" not in kwargs
    assert dialog.get_prompt() == CANNED


def test_api_key_mode_keeps_the_gemini_route(widgets, fake_completion, inline_threads):
    fake_completion.reply = CANNED

    widgets(StartPromptDialog(
        MagicMock(), "rainy street", "", "google", "gemini-test-model", "test-key",
        auth_mode="api-key", vertex_project="saved-project"))

    kwargs = fake_completion.kwargs
    assert kwargs["model"] == "gemini/gemini-test-model"
    assert kwargs["api_key"] == "test-key"
    assert "vertex_project" not in kwargs


def test_auth_mode_does_not_change_other_providers(
        widgets, fake_completion, inline_threads):
    fake_completion.reply = CANNED

    widgets(StartPromptDialog(
        MagicMock(), "rainy street", "", "openai", "gpt-test-model", "test-key",
        auth_mode="gcloud", vertex_project="saved-project"))

    kwargs = fake_completion.kwargs
    assert kwargs["model"] == "gpt-test-model"
    assert kwargs["api_key"] == "test-key"
    assert "vertex_project" not in kwargs


def test_gcloud_mode_keeps_the_token_away_from_the_style_analyzer(
        widgets, fake_completion, inline_threads, monkeypatch, tmp_path):
    import gui.video.start_prompt_dialog as module
    from core.video.style_analyzer import ContinuityMode

    built = []

    class _Analyzer:
        def __init__(self, **kwargs):
            built.append(kwargs)

        def analyze_for_style(self, _path):
            return "warm film grain"

    monkeypatch.setattr(module, "StyleAnalyzer", _Analyzer)
    fake_completion.reply = CANNED
    frame = tmp_path / "prev.png"
    frame.write_bytes(b"not a real image")

    widgets(StartPromptDialog(
        MagicMock(), "rainy street", "", "google", "gemini-test-model", OAUTH_TOKEN,
        ContinuityMode.STYLE_ONLY, frame, auth_mode="gcloud",
        vertex_project="saved-project"))

    assert len(built) == 1
    assert built[0]["api_key"] is None
    # the analyzer is told how to sign in instead: Vertex, with the project
    assert built[0]["auth_mode"] == "gcloud"
    assert built[0]["vertex_project"] == "saved-project"
    assert "api_key" not in fake_completion.kwargs
