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
