"""ActionCardsPanel "Generate cards" (sprite tab), offscreen, with a fake completion.

``inline_threads`` runs the panel's real ``SpriteWorker`` in the test thread.
"""
import json
from types import SimpleNamespace

import pytest

from core import chameleon_llm
from gui.sprite.action_cards_panel import ActionCardsPanel

CANNED = json.dumps({"version": "1.0", "cards": [
    {"name": "idle", "prompt": "stands and breathes", "duration_s": 2, "loop": True,
     "target_frames": 8, "fps": 12},
    {"name": "walk", "prompt": "walks right", "duration_s": 2, "loop": True,
     "target_frames": 8, "fps": 12},
]})

# (provider id in the panel's combo, expected model, expects api_key)
BRANCHES = [
    pytest.param("openai", "gpt-test-model", True, id="openai"),
    pytest.param("anthropic", "anthropic/claude-test-model", True, id="anthropic"),
    pytest.param("gemini", "gemini/gemini-test-model", True, id="google-api-key"),
]
_CHAT_MODELS = {"openai": "gpt-test-model", "anthropic": "claude-test-model",
                "gemini": "gemini-test-model"}


@pytest.fixture
def panel(qapp, widgets, fake_completion, fake_config, message_boxes, monkeypatch,
          inline_threads):
    # default_chat_model asks the model registry; answer without it
    monkeypatch.setattr("core.sprite.generation.action_cards.resolve_model",
                        lambda provider, family, static_default=None: _CHAT_MODELS[
                            "gemini" if provider == "google" else provider])
    panel = widgets(ActionCardsPanel(fake_config))
    panel.set_project(SimpleNamespace(actions=[], brief="", genre_preset="", plate_color="#00FF00",
                                      generation=None))
    panel.lines = []
    panel.logMessage.connect(lambda message, level: panel.lines.append((level, message)))
    panel.brief_edit.setText("a small armored knight")
    return panel


@pytest.mark.parametrize("provider_id, expected_model, sends_key", BRANCHES)
def test_generate_cards_routes_each_provider_and_adds_cards(
        panel, fake_completion, provider_id, expected_model, sends_key):
    fake_completion.reply = CANNED
    panel.llm_combo.setCurrentIndex(panel.llm_combo.findData(provider_id))

    panel.generate_cards()

    kwargs = fake_completion.kwargs
    assert kwargs["model"] == expected_model
    assert ("api_key" in kwargs) is sends_key
    assert [card.name for card in panel.project.actions] == ["idle", "walk"]
    assert panel.table.rowCount() == 2
    # the panel's status feed carries the request, the routed model and the reply
    feed = "\n".join(message for _, message in panel.lines)
    assert expected_model in feed
    assert "stands and breathes" in feed
    assert "Added 2 action card(s)" in feed


def test_google_cloud_login_uses_the_vertex_route(panel, fake_completion, fake_config):
    fake_completion.reply = CANNED
    fake_config.get_api_key.return_value = None
    fake_config.get_auth_mode.return_value = "gcloud"
    panel.llm_combo.setCurrentIndex(panel.llm_combo.findData("gemini"))

    panel.generate_cards()

    assert fake_completion.kwargs["model"] == "vertex_ai/gemini-test-model"
    assert "api_key" not in fake_completion.kwargs
    assert len(panel.project.actions) == 2


def test_rate_limit_is_reported_not_raised(panel, fake_completion, message_boxes, error_logged):
    fake_completion.error = chameleon_llm.RateLimitError("RateLimitError: slow down",
                                                         provider="test")
    panel.llm_combo.setCurrentIndex(panel.llm_combo.findData("openai"))

    panel.generate_cards()  # must not raise

    assert len(fake_completion.calls) == 1
    assert panel.project.actions == []
    errors = [message for level, message in panel.lines if level == "ERROR"]
    assert errors and "slow down" in errors[0]
    assert message_boxes and message_boxes[0][0] == "critical"
    assert error_logged()
