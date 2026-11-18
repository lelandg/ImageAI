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


# --- Start Prompt: the configured Google auth mode reaches the dialog ---------

@pytest.fixture
def start_prompt_calls(workspace, monkeypatch):
    """Replace StartPromptDialog with a recorder and give the workspace one scene."""
    from types import SimpleNamespace
    import gui.video.start_prompt_dialog as dialog_module

    calls = []

    class _Dialog:
        def __init__(self, *args, **kwargs):
            calls.append((args, kwargs))

        def exec_(self):
            return False

    monkeypatch.setattr(dialog_module, "StartPromptDialog", _Dialog)
    scene = SimpleNamespace(source="rainy street", prompt="", approved_image=None,
                            images=[])
    workspace.current_project = SimpleNamespace(scenes=[scene])
    return calls


def _select_google(workspace):
    workspace.llm_provider_combo.setCurrentText("Google")
    assert workspace.llm_provider_combo.currentText() == "Google"
    workspace.llm_model_combo.clear()
    workspace.llm_model_combo.addItem("gemini-test-model")
    workspace.llm_model_combo.setCurrentText("gemini-test-model")


def test_start_prompt_in_gcloud_mode_skips_the_key_check(
        workspace, start_prompt_calls, fake_config, message_boxes):
    values = {"auth_mode": "gcloud", "gcloud_project_id": "saved-project"}
    fake_config.get.side_effect = lambda key, default=None: values.get(key, default)

    def _no_google_key(provider):
        assert provider != "google", "gcloud mode must not fetch a Google key or token"
        return "test-key"

    fake_config.get_api_key.side_effect = _no_google_key
    _select_google(workspace)

    workspace._show_start_prompt_llm_dialog(0)

    assert len(start_prompt_calls) == 1, message_boxes
    args, kwargs = start_prompt_calls[0]
    assert args[3] == "google" and args[4] == "gemini-test-model"
    assert args[5] is None  # no key, and no OAuth token standing in for one
    assert kwargs["auth_mode"] == "gcloud"
    assert kwargs["vertex_project"] == "saved-project"


def test_start_prompt_in_gcloud_mode_accepts_the_legacy_setting_value(
        workspace, start_prompt_calls, fake_config):
    values = {"auth_mode": "Google Cloud Account"}
    fake_config.get.side_effect = lambda key, default=None: values.get(key, default)
    fake_config.get_api_key.return_value = None
    _select_google(workspace)

    workspace._show_start_prompt_llm_dialog(0)

    assert len(start_prompt_calls) == 1
    assert start_prompt_calls[0][1]["auth_mode"] == "gcloud"


def test_start_prompt_in_api_key_mode_passes_the_stored_key(
        workspace, start_prompt_calls, fake_config):
    _select_google(workspace)

    workspace._show_start_prompt_llm_dialog(0)

    assert len(start_prompt_calls) == 1
    args, kwargs = start_prompt_calls[0]
    assert args[5] == "test-key"
    assert kwargs["auth_mode"] == "api-key"


def test_start_prompt_in_api_key_mode_still_requires_a_key(
        workspace, start_prompt_calls, fake_config, monkeypatch):
    warnings = []
    import gui.common.dialog_manager as dm

    class _Manager:
        def show_warning(self, title, text):
            warnings.append((title, text))

    monkeypatch.setattr(dm, "get_dialog_manager", lambda parent: _Manager())
    fake_config.get_api_key.return_value = None
    fake_config.get_api_key.side_effect = None
    _select_google(workspace)

    workspace._show_start_prompt_llm_dialog(0)

    assert start_prompt_calls == []
    assert warnings and warnings[0][0] == "API Key Missing"
