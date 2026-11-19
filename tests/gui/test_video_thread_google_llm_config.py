"""VideoGenerationThread builds its chat/LLM provider config from the
generation parameters, which carry the workspace's live auth mode.

With Google Cloud login the parameters' ``google_api_key`` is an OAuth access
token (the video providers use it). A chat call must not send it as an API key.

``chameleon_llm.completion`` is replaced by ``fake_completion``; nothing here
reaches a provider.
"""
import pytest

from core import llm_params
from gui.video.video_project_tab import VideoGenerationThread

TOKEN = "oauth-access-token-not-an-api-key"


class _Persisted:
    """What is on disk; it must lose against the parameters' auth mode."""

    def __init__(self, auth_mode):
        self._auth_mode = auth_mode
        self.key_lookups = []

    def get(self, key, default=None):
        return {"auth_mode": self._auth_mode,
                "gcloud_project_id": "persisted-project"}.get(key, default)

    def get_api_key(self, provider):
        self.key_lookups.append(provider)
        return "persisted-key"


def _thread(**kwargs):
    thread = VideoGenerationThread.__new__(VideoGenerationThread)
    thread.kwargs = kwargs
    return thread


@pytest.mark.parametrize("mode", ["gcloud", "Google Cloud Account"])
def test_google_cloud_login_drops_the_token(mode):
    config = _thread(auth_mode=mode, google_api_key=TOKEN,
                     gcloud_project_id="live-project")._google_llm_config()
    assert config == {"google_api_key": None, "auth_mode": "gcloud",
                      "gcloud_project_id": "live-project"}


def test_api_key_mode_keeps_the_key():
    config = _thread(auth_mode="api-key", google_api_key="live-key",
                     gcloud_project_id=None)._google_llm_config()
    assert config == {"google_api_key": "live-key", "auth_mode": "api-key",
                      "gcloud_project_id": None}


def test_parameters_without_a_mode_leave_it_to_saved_settings():
    assert _thread(google_api_key="k")._google_llm_config() == {"google_api_key": "k"}


@pytest.mark.parametrize("live_mode,persisted_mode,key,model,sends_key", [
    ("gcloud", "api-key", TOKEN, "vertex_ai/gemini-test-model", False),
    ("api-key", "gcloud", "live-key", "gemini/gemini-test-model", True),
])
def test_a_provider_built_from_it_follows_the_live_mode(
        fake_completion, monkeypatch, live_mode, persisted_mode, key, model,
        sends_key):
    """End to end through UnifiedLLMProvider, with disk saying the opposite."""
    from core.video.prompt_engine import UnifiedLLMProvider
    saved = _Persisted(persisted_mode)
    monkeypatch.setattr(llm_params, "_saved_settings", lambda: saved)
    fake_completion.reply = "a cat, golden hour"
    llm_config = {
        "openai_api_key": None, "anthropic_api_key": None,
        **_thread(auth_mode=live_mode, google_api_key=key,
                  gcloud_project_id="live-project")._google_llm_config(),
    }

    UnifiedLLMProvider(llm_config).enhance_prompt("a cat", "google",
                                                  "gemini-test-model")

    kwargs = fake_completion.kwargs
    assert kwargs["model"] == model
    assert kwargs.get("api_key") == ("live-key" if sends_key else None)
    assert TOKEN not in repr({k: v for k, v in kwargs.items() if k != "messages"})
    assert saved.key_lookups == []


# --- continuity analysis: the key comes from the same snapshot as the mode ---

def test_continuity_key_in_live_api_key_mode_ignores_gcloud_on_disk():
    """Saved Settings say Google Cloud login, so the persisted lookup would
    answer with an OAuth token; the live parameters say API key."""
    persisted = _Persisted("gcloud")
    thread = _thread(auth_mode="api-key", google_api_key="live-key",
                     gcloud_project_id=None)
    key, google_llm, cloud_login = thread._style_analysis_credentials(
        "google", persisted)
    assert key == "live-key"
    assert cloud_login is False
    assert google_llm["auth_mode"] == "api-key"
    assert persisted.key_lookups == []


def test_continuity_key_in_live_gcloud_mode_fetches_nothing():
    persisted = _Persisted("api-key")
    thread = _thread(auth_mode="gcloud", google_api_key=TOKEN,
                     gcloud_project_id="live-project")
    key, google_llm, cloud_login = thread._style_analysis_credentials(
        "google", persisted)
    assert key is None
    assert cloud_login is True
    assert persisted.key_lookups == []


def test_continuity_key_without_a_live_mode_falls_back_to_the_lookup():
    persisted = _Persisted("api-key")
    key, _google_llm, cloud_login = _thread()._style_analysis_credentials(
        "google", persisted)
    assert key == "persisted-key"
    assert cloud_login is False


def test_continuity_key_for_openai_uses_the_lookup():
    persisted = _Persisted("api-key")
    key, _google_llm, _cloud = _thread(auth_mode="gcloud")._style_analysis_credentials(
        "openai", persisted)
    assert key == "persisted-key"
    assert persisted.key_lookups == ["openai"]
