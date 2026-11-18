"""PromptGenerationDialog and its LLMWorker, offscreen, with a fake completion.

The worker's ``run()`` is called directly in the test thread and its signals are
wired to the dialog's own slots, so nothing starts a QThread or an event loop.
"""
import json

import pytest
from PySide6.QtCore import Qt

from core import chameleon_llm
from gui.prompt_generation_dialog import LLMWorker, PromptGenerationDialog

CANNED = json.dumps(["canned prompt alpha", "canned prompt beta"])

# (provider label, api key, model, expected model, expect api_key sent)
PROVIDER_BRANCHES = [
    pytest.param("OpenAI", "test-key", "gpt-test-model", "gpt-test-model", True, id="openai"),
    pytest.param("Anthropic", "test-key", "claude-test-model",
                 "anthropic/claude-test-model", True, id="anthropic"),
    pytest.param("Claude", "test-key", "claude-test-model",
                 "anthropic/claude-test-model", True, id="claude-alias"),
    pytest.param("Google", "test-key", "gemini-test-model",
                 "gemini/gemini-test-model", True, id="google-api-key"),
    pytest.param("Gemini", "", "gemini-test-model",
                 "vertex_ai/gemini-test-model", False, id="google-gcloud"),
]


def _run_worker(dialog, provider, api_key, model):
    """Run the dialog's worker class like the dialog does, minus the thread."""
    worker = LLMWorker("generate", "a lighthouse at dawn", 2, provider, model, api_key,
                       temperature=0.8, max_tokens=1000)
    worker.finished.connect(dialog.on_generation_finished)
    worker.error.connect(dialog.on_generation_error)
    worker.progress.connect(dialog.on_generation_progress)
    worker.log_message.connect(dialog.on_log_message)
    dialog.start_operation("Prompt Generation")
    worker.run()
    return worker


@pytest.fixture
def dialog(qapp, widgets):
    return widgets(PromptGenerationDialog(config={}))


@pytest.mark.parametrize("provider, api_key, model, expected_model, sends_key", PROVIDER_BRANCHES)
def test_each_provider_branch_routes_and_shows_the_reply(
        dialog, fake_completion, console_log, provider, api_key, model, expected_model, sends_key):
    fake_completion.reply = CANNED

    _run_worker(dialog, provider, api_key, model)

    kwargs = fake_completion.kwargs
    assert kwargs["model"] == expected_model
    assert ("api_key" in kwargs) is sends_key
    # the canned reply reached the result widget and the history
    assert [dialog.results_list.item(i).data(Qt.UserRole) for i in range(dialog.results_list.count())] == \
        ["canned prompt alpha", "canned prompt beta"]
    # status console: the widget names provider and model; the console feed
    # carries the routed model and the full reply
    widget_text = dialog.status_console.console.toPlainText()
    assert f"Model: {model}" in widget_text
    assert "Successfully generated 2 prompts" in widget_text
    feed = "\n".join(console_log)
    assert expected_model in feed
    assert "canned prompt alpha" in feed and "canned prompt beta" in feed


@pytest.mark.parametrize("provider", ["Ollama", "LM Studio"])
def test_local_providers_are_not_supported_by_this_worker(
        dialog, fake_completion, message_boxes, provider):
    _run_worker(dialog, provider, "", "llama-test")

    assert fake_completion.calls == []
    assert "coming soon" in dialog.status_console.console.toPlainText()
    assert message_boxes and message_boxes[0][0] == "critical"


def test_rate_limit_is_reported_not_raised(dialog, fake_completion, console_log,
                                           message_boxes, error_logged):
    fake_completion.error = chameleon_llm.RateLimitError("RateLimitError: slow down",
                                                         provider="test")

    _run_worker(dialog, "OpenAI", "test-key", "gpt-test-model")  # must not raise

    assert len(fake_completion.calls) == 1
    assert "RateLimitError: slow down" in dialog.status_console.console.toPlainText()
    assert any("RateLimitError: slow down" in line for line in console_log)
    assert message_boxes and "slow down" in message_boxes[0][2]
    assert error_logged()
    assert dialog.results_list.count() == 0
