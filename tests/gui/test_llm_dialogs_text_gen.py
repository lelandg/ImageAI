"""TextGenerationDialog (layout text blocks), offscreen, with a fake completion.

``QThread.start`` is patched to run inline (``inline_threads``), so the real
Generate action runs the real worker in the test thread.
"""
import pytest

from core import chameleon_llm
from core.layout.models import TextBlock
from gui.layout.text_gen_dialog import TextGenerationDialog

CANNED = "Once upon a time, a very small robot learned to paint."

# (provider, auth_mode, model, expected model, expected api_base)
BRANCHES = [
    pytest.param("openai", "api-key", "gpt-test-model", "gpt-test-model", None, id="openai"),
    pytest.param("anthropic", "api-key", "claude-test-model",
                 "anthropic/claude-test-model", None, id="anthropic"),
    pytest.param("google", "api-key", "gemini-test-model",
                 "gemini/gemini-test-model", None, id="google-api-key"),
    pytest.param("google", "gcloud", "gemini-test-model",
                 "vertex_ai/gemini-test-model", None, id="google-gcloud"),
    pytest.param("ollama", "api-key", "llama-test", "ollama/llama-test", None, id="ollama"),
    pytest.param("LM Studio", "api-key", "llama-test", "llama-test",
                 "http://localhost:1234/v1", id="lm-studio"),
]


def _dialog(widgets, config, provider, model, auth_mode="api-key"):
    config.get.side_effect = lambda key, default=None: auth_mode if key == "auth_mode" else default
    block = TextBlock(id="b1", rect=(0, 0, 100, 50), text="hello")
    return widgets(TextGenerationDialog(config, block, provider=provider, model=model))


@pytest.mark.parametrize("provider, auth_mode, model, expected_model, api_base", BRANCHES)
def test_generate_routes_each_provider_and_shows_the_reply(
        widgets, fake_config, fake_completion, inline_threads, console_log,
        provider, auth_mode, model, expected_model, api_base):
    fake_completion.reply = CANNED
    dialog = _dialog(widgets, fake_config, provider, model, auth_mode)

    dialog.generate()

    kwargs = fake_completion.kwargs
    assert kwargs["model"] == expected_model
    assert kwargs.get("api_base") == api_base
    assert ("api_key" in kwargs) is (auth_mode != "gcloud")
    assert dialog.preview_edit.toPlainText() == CANNED
    assert dialog.get_generated_text() == CANNED
    assert dialog.apply_btn.isEnabled()
    widget_text = dialog.status_console.console.toPlainText()
    assert f"Calling {expected_model}" in widget_text
    assert "Text generation complete" in widget_text
    assert CANNED in "\n".join(console_log)


def test_rate_limit_is_reported_not_raised(widgets, fake_config, fake_completion,
                                           inline_threads, console_log, error_logged):
    fake_completion.error = chameleon_llm.RateLimitError("RateLimitError: slow down",
                                                         provider="test")
    dialog = _dialog(widgets, fake_config, "openai", "gpt-test-model")

    dialog.generate()  # must not raise

    assert len(fake_completion.calls) == 1
    assert "RateLimitError: slow down" in dialog.status_console.console.toPlainText()
    assert any("RateLimitError: slow down" in line for line in console_log)
    assert error_logged()
    assert dialog.preview_edit.toPlainText() == ""
    assert dialog.generate_btn.isEnabled() and not dialog.apply_btn.isEnabled()


# --- the Google Cloud project saved in Settings reaches Vertex calls ----------

def _dialog_with_project(widgets, config, provider, model, auth_mode, project):
    values = {"auth_mode": auth_mode, "gcloud_project_id": project}
    config.get.side_effect = lambda key, default=None: values.get(key, default)
    block = TextBlock(id="b1", rect=(0, 0, 100, 50), text="hello")
    return widgets(TextGenerationDialog(config, block, provider=provider, model=model))


def test_gcloud_mode_sends_the_saved_project(
        widgets, fake_config, fake_completion, inline_threads):
    fake_completion.reply = CANNED
    dialog = _dialog_with_project(widgets, fake_config, "google",
                                  "gemini-test-model", "gcloud", "saved-project")

    dialog.generate()

    kwargs = fake_completion.kwargs
    assert kwargs["model"] == "vertex_ai/gemini-test-model"
    assert kwargs["vertex_project"] == "saved-project"
    assert "api_key" not in kwargs


@pytest.mark.parametrize("provider, auth_mode, model", [
    ("google", "api-key", "gemini-test-model"),
    ("openai", "gcloud", "gpt-test-model"),
])
def test_saved_project_is_not_sent_off_the_vertex_route(
        widgets, fake_config, fake_completion, inline_threads,
        provider, auth_mode, model):
    fake_completion.reply = CANNED
    dialog = _dialog_with_project(widgets, fake_config, provider, model,
                                  auth_mode, "saved-project")

    dialog.generate()

    assert "vertex_project" not in fake_completion.kwargs


def test_gcloud_mode_without_a_saved_project_sends_none(
        widgets, fake_config, fake_completion, inline_threads):
    fake_completion.reply = CANNED
    dialog = _dialog_with_project(widgets, fake_config, "google",
                                  "gemini-test-model", "gcloud", "")

    dialog.generate()

    assert "vertex_project" not in fake_completion.kwargs
