"""PromptGenerationDialog and its LLMWorker, offscreen, with a fake completion.

The worker's ``run()`` is called directly in the test thread and its signals are
wired to the dialog's own slots, so nothing starts a QThread or an event loop.
"""
import json
from unittest.mock import MagicMock

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


# --- the Google Cloud project saved in Settings reaches Vertex calls ----------

def test_worker_sends_the_saved_project_on_the_vertex_route(dialog, fake_completion):
    fake_completion.reply = CANNED
    worker = LLMWorker("generate", "a lighthouse at dawn", 2, "Google",
                       "gemini-test-model", "", vertex_project="saved-project")
    worker.run()

    kwargs = fake_completion.kwargs
    assert kwargs["model"] == "vertex_ai/gemini-test-model"
    assert kwargs["vertex_project"] == "saved-project"
    assert "api_key" not in kwargs


@pytest.mark.parametrize("provider, api_key, model", [
    ("Google", "test-key", "gemini-test-model"),
    ("OpenAI", "test-key", "gpt-test-model"),
    ("Anthropic", "test-key", "claude-test-model"),
])
def test_worker_keeps_the_project_off_other_routes(
        dialog, fake_completion, provider, api_key, model):
    fake_completion.reply = CANNED
    worker = LLMWorker("generate", "a lighthouse at dawn", 2, provider, model,
                       api_key, vertex_project="saved-project")
    worker.run()

    assert "vertex_project" not in fake_completion.kwargs


def test_dialog_hands_the_saved_project_to_its_worker(
        qapp, widgets, fake_completion, monkeypatch):
    """Drive the real Generate action; the thread and worker are recorders, so
    nothing runs and nothing can reach a provider."""
    import gui.prompt_generation_dialog as module

    values = {"auth_mode": "gcloud", "gcloud_project_id": "saved-project"}

    config = MagicMock()
    config.get.side_effect = lambda key, default=None: values.get(key, default)
    config.get_api_key.side_effect = AssertionError(
        "gcloud mode must not look up an API key")

    built = []

    class _Signal:
        def connect(self, *_a):
            pass

    class _Worker:
        finished = error = progress = log_message = _Signal()

        def __init__(self, *args, **kwargs):
            built.append((args, kwargs))

        def moveToThread(self, _thread):
            pass

        def run(self):
            pass

    class _Thread:
        started = finished = _Signal()

        def start(self):
            pass

        def quit(self):
            pass

    monkeypatch.setattr(module, "LLMWorker", _Worker)
    monkeypatch.setattr(module, "QThread", _Thread)
    dialog = widgets(PromptGenerationDialog(config=config))
    dialog.input_text.setPlainText("a lighthouse at dawn")
    index = dialog.llm_provider_combo.findText("Google")
    assert index >= 0
    dialog.llm_provider_combo.setCurrentIndex(index)

    dialog.generate_prompts()
    dialog.thread = dialog.worker = None  # nothing real to clean up

    assert len(built) == 1
    args, kwargs = built[0]
    assert kwargs.get("vertex_project") == "saved-project"
    assert not args[5]  # api_key: none in gcloud mode
