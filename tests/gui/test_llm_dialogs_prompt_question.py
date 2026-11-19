"""PromptQuestionDialog and its QuestionWorker, offscreen, with a fake completion.

The OpenAI and Google branches go through ``chameleon_llm``. The Anthropic
provider has no branch in this worker, so it is not reachable through the fake.
"""
import builtins
from unittest.mock import MagicMock

import pytest

from core import chameleon_llm
from gui.prompt_question_dialog import PromptQuestionDialog, QuestionWorker

CANNED = "Add rim lighting and a shallow depth of field."


def _run_worker(dialog):
    worker = QuestionWorker("a cat on a roof", "How can I improve this?", "OpenAI",
                            "gpt-test-model", "test-key", temperature=0.7)
    worker.finished.connect(dialog.on_answer_received)
    worker.error.connect(dialog.on_error)
    worker.progress.connect(lambda msg: dialog.status_console.log(msg, "INFO"))
    worker.log_message.connect(dialog.status_console.log)
    dialog.current_prompt = "a cat on a roof"
    dialog.question_input.setPlainText("How can I improve this?")
    dialog.start_operation("LLM Question")
    worker.run()


@pytest.fixture
def dialog(qapp, widgets):
    return widgets(PromptQuestionDialog(config=None, current_prompt="a cat on a roof"))


def test_openai_question_routes_and_shows_the_answer(dialog, fake_completion, console_log):
    fake_completion.reply = CANNED

    _run_worker(dialog)

    kwargs = fake_completion.kwargs
    assert kwargs["model"] == "gpt-test-model"
    assert kwargs["api_key"] == "test-key"
    assert kwargs["messages"][-1]["content"].endswith("How can I improve this?")
    assert CANNED in dialog.conversation_display.toPlainText()
    widget_text = dialog.status_console.console.toPlainText()
    assert "Model: gpt-test-model" in widget_text
    assert CANNED in widget_text
    assert CANNED in "\n".join(console_log)


def test_rate_limit_is_reported_not_raised(dialog, fake_completion, console_log,
                                           message_boxes, error_logged):
    fake_completion.error = chameleon_llm.RateLimitError("RateLimitError: slow down",
                                                         provider="test")

    _run_worker(dialog)  # must not raise

    assert len(fake_completion.calls) == 1
    assert "RateLimitError: slow down" in dialog.status_console.console.toPlainText()
    assert message_boxes and message_boxes[0][0] == "critical"
    assert error_logged()
    assert dialog.conversation_display.toPlainText() == ""


# --- the Google branch uses the vendored client ------------------------------

@pytest.fixture
def no_legacy_sdk(monkeypatch, message_boxes):
    """``google.generativeai`` is not a dependency: importing it must fail."""
    real_import = builtins.__import__

    def _import(name, *args, **kwargs):
        if name == "google.generativeai" or name.startswith("google.generativeai."):
            raise ImportError("google.generativeai is not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _import)


def _google_worker(dialog, api_key, history=None, **kwargs):
    worker = QuestionWorker("a cat on a roof", "How can I improve this?", "Google",
                            "gemini-test-model", api_key, temperature=0.7,
                            conversation_history=history, **kwargs)
    worker.finished.connect(dialog.on_answer_received)
    worker.error.connect(dialog.on_error)
    worker.log_message.connect(dialog.status_console.log)
    dialog.current_prompt = "a cat on a roof"
    dialog.question_input.setPlainText("How can I improve this?")
    dialog.start_operation("LLM Question")
    worker.run()


def test_google_api_key_mode_uses_the_gemini_route(
        dialog, fake_completion, console_log, no_legacy_sdk):
    fake_completion.reply = CANNED
    history = [{"prompt": "a dog", "question": "Is it good?", "answer": "Yes."}]

    _google_worker(dialog, "test-key", history=history, auth_mode="api-key",
                   vertex_project="saved-project")

    kwargs = fake_completion.kwargs
    assert kwargs["model"] == "gemini/gemini-test-model"
    assert kwargs["api_key"] == "test-key"
    assert kwargs["temperature"] == 0.7
    assert "vertex_project" not in kwargs
    # the assembled conversation, not just the last question
    roles = [m["role"] for m in kwargs["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
    assert kwargs["messages"][-1]["content"].endswith("How can I improve this?")
    assert CANNED in dialog.conversation_display.toPlainText()


@pytest.mark.parametrize("api_key", [None, "", "oauth-access-token-not-an-api-key"])
def test_google_cloud_mode_uses_vertex_and_never_sends_a_key(
        dialog, fake_completion, no_legacy_sdk, api_key):
    fake_completion.reply = CANNED

    _google_worker(dialog, api_key, auth_mode="gcloud",
                   vertex_project="saved-project")

    kwargs = fake_completion.kwargs
    assert kwargs["model"] == "vertex_ai/gemini-test-model"
    assert "api_key" not in kwargs
    assert kwargs["vertex_project"] == "saved-project"
    assert CANNED in dialog.conversation_display.toPlainText()


def test_google_without_auth_mode_follows_the_key(dialog, fake_completion, no_legacy_sdk):
    fake_completion.reply = CANNED
    _google_worker(dialog, "test-key")
    assert fake_completion.kwargs["model"] == "gemini/gemini-test-model"


def test_google_without_auth_mode_or_key_uses_vertex(dialog, fake_completion, no_legacy_sdk):
    fake_completion.reply = CANNED
    _google_worker(dialog, None)
    assert fake_completion.kwargs["model"] == "vertex_ai/gemini-test-model"


def test_google_request_and_reply_are_logged_in_full(
        dialog, fake_completion, console_log, no_legacy_sdk, caplog):
    import logging
    fake_completion.reply = CANNED
    with caplog.at_level(logging.INFO, logger="gui.prompt_question_dialog"):
        _google_worker(dialog, "test-key", auth_mode="api-key")

    for feed in ("\n".join(console_log), caplog.text):
        assert "gemini/gemini-test-model" in feed          # routed model
        assert "temperature" in feed                       # params
        assert "expert prompt engineer" in feed            # system prompt, in full
        assert "How can I improve this?" in feed           # user prompt
        assert CANNED in feed                              # complete response
        assert "test-key" not in feed                      # never the key


def test_dialog_passes_the_auth_mode_and_project_to_its_worker(
        qapp, widgets, fake_completion, monkeypatch, message_boxes):
    """Drive the real Ask action; the thread and worker are recorders."""
    import gui.prompt_question_dialog as module

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

        def deleteLater(self):
            pass

    monkeypatch.setattr(module, "QuestionWorker", _Worker)
    monkeypatch.setattr(module, "QThread", _Thread)
    dialog = widgets(PromptQuestionDialog(config=config, current_prompt="a cat"))
    index = dialog.llm_provider_combo.findText("Google")
    assert index >= 0
    dialog.llm_provider_combo.setCurrentIndex(index)
    dialog.question_input.setPlainText("How can I improve this?")

    dialog.ask_question()
    dialog.thread = dialog.worker = None

    assert len(built) == 1
    args, kwargs = built[0]
    assert kwargs.get("auth_mode") == "gcloud"
    assert kwargs.get("vertex_project") == "saved-project"
    assert not args[4]  # api_key
