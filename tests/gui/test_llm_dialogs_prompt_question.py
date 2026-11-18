"""PromptQuestionDialog and its QuestionWorker, offscreen, with a fake completion.

Only the OpenAI branch goes through ``chameleon_llm``: the Google branch calls
the ``google.generativeai`` SDK directly and the Anthropic provider has no
branch in this worker, so neither is reachable through the fake.
"""
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
