"""Video WorkspaceWidget "Suggest Scenes" (its LLM action), offscreen, with a fake completion.

The action delegates to ``core.video.scene_suggester.SceneSuggester`` on a QThread
defined inside the method; ``inline_threads`` runs it in the test thread.
"""
import pytest

from core import chameleon_llm

# google-cloud-aiplatform warns about its storage dependency when first imported
pytestmark = pytest.mark.filterwarnings("ignore:Support for google-cloud-storage:FutureWarning")

LYRICS = "line one of the song\nline two of the song"
CANNED = "{scene: neon city}\nline one of the song\nline two of the song"


@pytest.fixture
def workspace(qapp, widgets, fake_completion, fake_config, message_boxes, monkeypatch,
              inline_threads):
    from gui.video import workspace_widget as ww

    # no gcloud / registry / Ollama probing while the widget builds
    monkeypatch.setattr(ww, "get_default_llm_provider", lambda config: "Anthropic")
    widget = widgets(ww.WorkspaceWidget(fake_config, {}))
    widget.llm_model_combo.setEnabled(True)
    widget.llm_provider_combo.setCurrentText("Anthropic")
    widget.llm_model_combo.clear()
    widget.llm_model_combo.addItem("claude-test-model")
    widget.llm_model_combo.setCurrentText("claude-test-model")
    widget.input_text.setPlainText(LYRICS)
    widget.console_lines = []
    monkeypatch.setattr(widget, "_log_to_console",
                        lambda message, level="INFO": widget.console_lines.append((level, message)))
    return widget


def test_suggest_scenes_routes_the_model_and_shows_the_reply(workspace, fake_completion):
    fake_completion.reply = CANNED

    workspace._suggest_scenes()

    kwargs = fake_completion.kwargs
    assert kwargs["model"] == "anthropic/claude-test-model"
    shown = workspace.input_text.toPlainText()
    assert "{scene: neon city}" in shown and LYRICS in shown
    feed = "\n".join(message for _, message in workspace.console_lines)
    assert "anthropic/claude-test-model" in feed
    assert "Added" in feed and "tags" in feed
    assert workspace.suggest_scenes_btn.isEnabled()


def test_rate_limit_is_reported_not_raised(workspace, fake_completion, error_logged):
    fake_completion.error = chameleon_llm.RateLimitError("RateLimitError: slow down",
                                                         provider="test")

    workspace._suggest_scenes()  # must not raise

    assert len(fake_completion.calls) == 1
    assert workspace.input_text.toPlainText() == LYRICS
    feed = "\n".join(message for _, message in workspace.console_lines)
    assert "RateLimitError: slow down" in feed
    assert error_logged()
    assert workspace.suggest_scenes_btn.isEnabled()
