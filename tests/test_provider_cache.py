"""Provider cache: a cache hit must apply new credentials to the live client.

Regression tests for the sprite-tab bug where ``get_provider('google', ...)``
returned a cached instance built with an empty key. The cache hit set
``api_key`` but never rebuilt the SDK client, so every later call failed
with "No client configured".
"""

import io
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import providers.google as google_mod
import providers.openai as openai_mod
from providers import clear_provider_cache, get_provider


def _png_bytes(w: int = 8, h: int = 8) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), "red").save(buf, format="PNG")
    return buf.getvalue()


def _fake_response(png: bytes) -> SimpleNamespace:
    part = SimpleNamespace(text=None, inline_data=SimpleNamespace(data=png))
    cand = SimpleNamespace(content=SimpleNamespace(parts=[part]),
                           finish_reason="STOP")
    return SimpleNamespace(candidates=[cand])


def _client_factory(built: list):
    """Return a Client(**kwargs) stand-in that records each built client."""

    def factory(**kwargs):
        client = MagicMock()
        client.api_key = kwargs.get("api_key")
        client.models.generate_content.return_value = _fake_response(_png_bytes())
        built.append(client)
        return client

    return factory


@pytest.fixture
def stub_genai(monkeypatch):
    """Empty the cache and replace the Google SDK with a recording stub."""
    clear_provider_cache()
    built = []
    monkeypatch.setattr(google_mod, "genai", SimpleNamespace(Client=_client_factory(built)))
    monkeypatch.setattr(google_mod, "GENAI_AVAILABLE", True)
    monkeypatch.setattr(google_mod, "rate_limiter", MagicMock())
    yield built
    clear_provider_cache()


@pytest.fixture
def stub_openai(monkeypatch):
    """Empty the cache and replace the OpenAI SDK with a recording stub."""
    clear_provider_cache()
    built = []
    monkeypatch.setattr(openai_mod, "OpenAIClient", _client_factory(built))
    monkeypatch.setattr(openai_mod, "OPENAI_AVAILABLE", True)
    yield built
    clear_provider_cache()


class TestGoogleCacheHit:
    def test_key_applied_on_cache_hit_and_edit_image_reaches_client(self, stub_genai):
        first = get_provider("google", {"api_key": ""})
        assert first.client is None
        second = get_provider("google", {"api_key": "k", "auth_mode": "api-key"})
        assert second is first

        texts, images = second.edit_image(_png_bytes(), "edit it", "gemini-2.5-flash-image")

        assert stub_genai and stub_genai[-1].api_key == "k"
        stub_genai[-1].models.generate_content.assert_called_once()
        assert images

    def test_new_key_on_cache_hit_rebuilds_client(self, stub_genai):
        first = get_provider("google", {"api_key": "k", "auth_mode": "api-key"})
        assert stub_genai[-1].api_key == "k"
        old_client = first.client

        same = get_provider("google", {"api_key": "k2", "auth_mode": "api-key"})
        assert same is first
        assert same.client is None

        same.edit_image(_png_bytes(), "edit it", "gemini-2.5-flash-image")
        assert same.client is not old_client
        assert stub_genai[-1].api_key == "k2"

    def test_empty_key_on_cache_hit_keeps_current_key_and_client(self, stub_genai):
        first = get_provider("google", {"api_key": "k", "auth_mode": "api-key"})
        old_client = first.client

        same = get_provider("google", {"api_key": ""})
        assert same is first
        assert same.api_key == "k"
        assert same.client is old_client

    def test_auth_mode_switch_on_cache_hit_rebuilds_client(self, stub_genai):
        first = get_provider("google", {"api_key": "k", "auth_mode": "gcloud"})
        sentinel = MagicMock()
        first.client = sentinel
        first._client_mode = "gcloud"

        same = get_provider("google", {"api_key": "k", "auth_mode": "api-key"})
        assert same is first
        assert same.auth_mode == "api-key"
        assert same.client is None

        same.edit_image(_png_bytes(), "edit it", "gemini-2.5-flash-image")
        assert same.client is not sentinel
        assert stub_genai[-1].api_key == "k"

    def test_underscore_auth_mode_spelling_is_not_a_credential_change(self, stub_genai):
        """``api_key`` and ``api-key`` name one mode; a cache hit must keep the client.

        ``ConfigManager.get_auth_mode()`` returned ``api_key`` when config.json
        had no ``auth_mode`` key, while the Image tab sent ``api-key``. A raw
        string compare in ``reconfigure()`` flipped the mode on every
        alternating call, dropped the client and the chat session, and logged
        a credential change with nothing changed.
        """
        first = get_provider("google", {"api_key": "k", "auth_mode": "api-key"})
        client = first.client
        assert client is not None
        chat_session = object()
        first._last_chat_session = chat_session

        assert first.reconfigure({"api_key": "k", "auth_mode": "api_key"}) is False
        assert first.auth_mode == "api-key"
        assert first.client is client
        assert first._last_chat_session is chat_session

        same = get_provider("google", {"api_key": "k", "auth_mode": "API Key"})
        assert same is first
        assert same.client is client
        assert same._last_chat_session is chat_session

    def test_auth_mode_is_canonical_after_construction(self, stub_genai):
        clear_provider_cache()
        assert get_provider("google", {"api_key": "k", "auth_mode": "api_key"}).auth_mode == "api-key"
        clear_provider_cache()
        assert get_provider("google", {"api_key": "k"}).auth_mode == "api-key"
        clear_provider_cache()
        provider = get_provider("google", {"api_key": "k", "auth_mode": "Google Cloud Account"})
        assert provider.auth_mode == "gcloud"
        # A real switch of mode still counts as a change.
        assert provider.reconfigure({"api_key": "k", "auth_mode": "api_key"}) is True
        assert provider.auth_mode == "api-key"


def test_config_default_auth_mode_is_the_canonical_spelling():
    """Every caller of get_auth_mode() sends the value the providers compare against."""
    from core.config import ConfigManager

    manager = ConfigManager.__new__(ConfigManager)  # no disk: only get_auth_mode's dict read
    manager.config = {}
    assert manager.get_auth_mode("google") == "api-key"
    assert manager.get_auth_mode("openai") == "api-key"


class TestOpenAICacheHit:
    def test_key_applied_on_cache_hit_and_validate_auth_reaches_client(self, stub_openai):
        first = get_provider("openai", {"api_key": ""})
        second = get_provider("openai", {"api_key": "k", "auth_mode": "api-key"})
        assert second is first

        ok, _msg = second.validate_auth()

        assert ok
        assert stub_openai and stub_openai[-1].api_key == "k"
        stub_openai[-1].models.list.assert_called_once()

    def test_new_key_on_cache_hit_rebuilds_client(self, stub_openai):
        first = get_provider("openai", {"api_key": "k", "auth_mode": "api-key"})
        first.validate_auth()
        old_client = first.client
        assert old_client.api_key == "k"

        same = get_provider("openai", {"api_key": "k2", "auth_mode": "api-key"})
        assert same is first
        assert same.client is None

        same.validate_auth()
        assert same.client is not old_client
        assert stub_openai[-1].api_key == "k2"

    def test_empty_key_on_cache_hit_keeps_current_key_and_client(self, stub_openai):
        first = get_provider("openai", {"api_key": "k", "auth_mode": "api-key"})
        first.validate_auth()
        old_client = first.client

        same = get_provider("openai", {"api_key": ""})
        assert same is first
        assert same.api_key == "k"
        assert same.client is old_client


class TestAuthModeSpellings:
    """Issue: two spellings of one auth mode flipped the mode on every cache hit."""

    def test_alternating_spellings_keep_client_and_log_no_change(self, stub_genai, caplog):
        caplog.set_level("INFO", logger="providers.google")
        first = get_provider("google", {"api_key": "k", "auth_mode": "api_key"})
        client = first.client
        assert client is not None
        chat_session = object()
        first._last_chat_session = chat_session

        for mode in ("api-key", "api_key", "api-key", "API Key", "api_key"):
            same = get_provider("google", {"api_key": "k", "auth_mode": mode})
            assert same is first
            assert same.auth_mode == "api-key"
            assert same.client is client
            assert same._last_chat_session is chat_session

        assert len(stub_genai) == 1
        assert "credentials changed" not in caplog.text

    @pytest.mark.parametrize("raw, canonical", [
        ("api_key", "api-key"),
        ("API Key", "api-key"),
        ("api-key", "api-key"),
        ("", "api-key"),
        (None, "api-key"),
        ("Google Cloud Account", "gcloud"),
        ("gcloud", "gcloud"),
        ("other", "other"),
    ])
    def test_normalize_auth_mode(self, raw, canonical):
        from providers.base import ImageProvider

        assert ImageProvider._normalize_auth_mode(raw) == canonical

    def test_provider_and_config_normalizers_agree(self):
        """core.config and providers.base map the same spellings to the same value."""
        from core.config import ConfigManager
        from providers.base import ImageProvider

        for raw in ("api_key", "API Key", "api-key", "Google Cloud Account", "gcloud"):
            manager = ConfigManager.__new__(ConfigManager)
            manager.config = {"auth_mode": raw}
            manager.save = lambda: None
            manager._normalize_auth_mode()
            assert manager.config["auth_mode"] == ImageProvider._normalize_auth_mode(raw)


class TestEnsureClientReturnsClient:
    """Issue: an in-flight call must keep its client if reconfigure() nulls self.client."""

    def test_google_ensure_client_returns_the_client(self, stub_genai):
        provider = get_provider("google", {"api_key": "k", "auth_mode": "api-key"})
        assert provider._ensure_client() is provider.client
        assert provider.client is stub_genai[-1]

    def test_google_edit_image_uses_returned_client(self, stub_genai, monkeypatch):
        provider = get_provider("google", {"api_key": "k", "auth_mode": "api-key"})
        client = provider._ensure_client()

        def racing_ensure():
            provider.client = None  # another thread called reconfigure()
            return client

        monkeypatch.setattr(provider, "_ensure_client", racing_ensure)
        texts, images = provider.edit_image(_png_bytes(), "edit it", "gemini-2.5-flash-image")
        client.models.generate_content.assert_called_once()
        assert images

    def test_openai_ensure_client_returns_the_client(self, stub_openai):
        provider = get_provider("openai", {"api_key": "k", "auth_mode": "api-key"})
        assert provider._ensure_client() is provider.client
        assert provider.client is stub_openai[-1]

    def test_openai_validate_auth_uses_returned_client(self, stub_openai, monkeypatch):
        provider = get_provider("openai", {"api_key": "k", "auth_mode": "api-key"})
        client = provider._ensure_client()

        def racing_ensure():
            provider.client = None  # another thread called reconfigure()
            return client

        monkeypatch.setattr(provider, "_ensure_client", racing_ensure)
        ok, _msg = provider.validate_auth()
        assert ok
        client.models.list.assert_called_once()


class TestGoogleInitErrorsAreLogged:
    """Issue: every raise in the client init methods needs a logger.error first."""

    @pytest.fixture
    def bare_provider(self, stub_genai):
        return get_provider("google", {"api_key": "", "auth_mode": "api-key"})

    def _errors(self, caplog):
        return [r for r in caplog.records if r.levelname == "ERROR"]

    def test_api_key_client_missing_sdk(self, bare_provider, monkeypatch, caplog):
        caplog.set_level("ERROR", logger="providers.google")
        monkeypatch.setattr(google_mod, "GENAI_AVAILABLE", False)
        with pytest.raises(ImportError):
            bare_provider._init_api_key_client()
        assert any("not installed" in r.getMessage() for r in self._errors(caplog))

    def test_gcloud_client_missing_sdk(self, bare_provider, monkeypatch, caplog):
        caplog.set_level("ERROR", logger="providers.google")
        monkeypatch.setattr(google_mod, "GCLOUD_AVAILABLE", False)
        with pytest.raises(ImportError):
            bare_provider._init_gcloud_client(raise_on_error=True)
        assert any("not installed" in r.getMessage() for r in self._errors(caplog))
        assert bare_provider._init_gcloud_client(raise_on_error=False) is False

    class FakeCredsError(Exception):
        """Stands in for google.auth.exceptions.DefaultCredentialsError."""

    def _stub_gcloud(self, monkeypatch, auth_default):
        # The lazy import in _init_gcloud_client sets these three together.
        # The module placeholder for the error class is ``Exception``.
        monkeypatch.setattr(google_mod, "GCLOUD_AVAILABLE", True)
        monkeypatch.setattr(google_mod, "aiplatform", MagicMock())
        monkeypatch.setattr(google_mod, "google_auth_default", auth_default)
        monkeypatch.setattr(google_mod, "DefaultCredentialsError", self.FakeCredsError)

    def test_gcloud_client_no_project(self, bare_provider, monkeypatch, caplog):
        caplog.set_level("ERROR", logger="providers.google")
        self._stub_gcloud(monkeypatch, lambda: (object(), None))
        monkeypatch.setattr(bare_provider, "_get_gcloud_project_id", lambda: None)
        with pytest.raises(ValueError):
            bare_provider._init_gcloud_client(raise_on_error=True)
        assert any("project" in r.getMessage() for r in self._errors(caplog))

    def test_gcloud_client_auth_failure_logs_short_form(self, bare_provider, monkeypatch, caplog):
        caplog.set_level("ERROR", logger="providers.google")

        def failing_default():
            raise self.FakeCredsError("no adc")

        self._stub_gcloud(monkeypatch, failing_default)
        with pytest.raises(RuntimeError) as excinfo:
            bare_provider._init_gcloud_client(raise_on_error=True)
        assert "gcloud auth application-default login" in str(excinfo.value)

        errors = self._errors(caplog)
        assert errors, "auth failure was not logged"
        message = errors[-1].getMessage()
        assert "authentication failed" in message
        assert "no adc" in message
        assert "\n" not in message
