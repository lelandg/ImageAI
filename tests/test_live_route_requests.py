"""Offline check of the live tier's request building (L4, residual patch).

``tests/test_live_llm_params.py::TestRoutes`` must build every route's
request with ``build_completion_kwargs`` exactly as the app does. This runs
its request builder with fake model ids and fake keys; nothing is sent.
"""
import pytest

from tests import test_live_llm_params as live

_FAKE_MODELS = {
    ("openai", "gpt-mini"): "gpt-6.1-test",
    ("openai", "gpt-pro"): "gpt-5.5-pro",
    ("anthropic", "haiku"): "claude-test-haiku",
    ("gemini", "flash-lite"): "gemini-test-lite",
}

_KEYS = {"openai": "test-key", "anthropic": "test-key", "google": "test-key"}


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr(live, "resolve_model",
                        lambda provider, family, **_: _FAKE_MODELS[(provider, family)])
    monkeypatch.setattr(live, "_adc_project", lambda: (True, "test-project"))


def _build(route_id, params):
    (param,) = [p for p in live._ROUTES if p.id == route_id]
    _name, provider, key_provider, resolver, auth_mode = param.values
    return live._route_request(_KEYS, provider, key_provider, resolver, auth_mode,
                               live._MSGS, params)


@pytest.mark.parametrize("route_id,model,has_key", [
    ("openai-chat", "gpt-6.1-test", True),
    ("openai-responses", "gpt-5.5-pro", True),
    ("anthropic", "anthropic/claude-test-haiku", True),
    ("gemini-api-key", "gemini/gemini-test-lite", True),
    ("vertex", "vertex_ai/gemini-test-lite", False),
])
def test_route_requests_are_built_like_the_app(route_id, model, has_key):
    kwargs = _build(route_id, {"max_tokens": 1024})
    assert kwargs["model"] == model
    assert ("api_key" in kwargs) is has_key
    assert kwargs["timeout"] == live._TIMEOUT


@pytest.mark.parametrize("route_id", ["openai-chat", "openai-responses"])
def test_openai_reasoning_routes_send_max_completion_tokens(route_id):
    kwargs = _build(route_id, {"max_tokens": 1024})
    assert kwargs["max_completion_tokens"] == 1024 and "max_tokens" not in kwargs


def test_vertex_route_sends_project_and_no_location():
    kwargs = _build("vertex", {"max_tokens": 1024})
    assert kwargs["vertex_project"] == "test-project"
    assert "vertex_location" not in kwargs


def test_json_mode_passes_response_format():
    kwargs = _build("anthropic", {"max_tokens": 64,
                                  "response_format": {"type": "json_object"}})
    assert kwargs["response_format"] == {"type": "json_object"}


# --- Last patch: Anthropic helpers of the live file ---------------------------

def test_older_claude_candidates_exclude_no_sampling_models(monkeypatch):
    # the resolved haiku is a 5-line model: it takes no temperature
    monkeypatch.setattr(live, "resolve_model",
                        lambda provider, family, **_: "claude-haiku-5-5")
    candidates = live._older_claude_candidates()
    assert "claude-haiku-5-5" not in candidates
    for model in candidates:
        params, _ = live.validate_params("anthropic", model, {"temperature": 1.5})
        assert params.get("temperature") == 1.0, model


def test_older_claude_candidates_put_an_older_resolved_haiku_first(monkeypatch):
    monkeypatch.setattr(live, "resolve_model",
                        lambda provider, family, **_: "claude-haiku-4-5-test")
    assert live._older_claude_candidates()[0] == "claude-haiku-4-5-test"


def _not_found(model):
    return live.chameleon_llm.BadRequestError(
        f"NotFoundError: Error code: 404 - {{'type': 'error', 'error': "
        f"{{'type': 'not_found_error', 'message': 'model: {model}'}}}}",
        provider="anthropic", status_code=404)


def test_pick_available_skips_retired_models():
    def probe(model):
        if model == "retired":
            raise _not_found(model)
    assert live._pick_available(["retired", "current"], probe) == "current"


def test_pick_available_skips_the_class_when_all_are_retired():
    def probe(model):
        raise _not_found(model)
    with pytest.raises(pytest.skip.Exception,
                       match="no current Claude model accepts sampling parameters"):
        live._pick_available(["a", "b"], probe)
    with pytest.raises(pytest.skip.Exception,
                       match="no current Claude model accepts sampling parameters"):
        live._pick_available([], probe)


def test_pick_available_raises_other_bad_requests():
    def probe(model):
        raise live.chameleon_llm.BadRequestError("invalid_request_error: bad",
                                                 provider="anthropic", status_code=400)
    with pytest.raises(live.chameleon_llm.BadRequestError):
        live._pick_available(["a"], probe)


def test_sdk_sends_skips_exactly_when_the_sdk_drops_the_param():
    from core.chameleon_llm.anthropic_adapter import sdk_accepts
    if sdk_accepts("temperature"):
        live._sdk_sends("temperature")  # must not skip
    else:
        with pytest.raises(pytest.skip.Exception, match="drops sampling parameters"):
            live._sdk_sends("temperature")


# --- the gemini/ route uses a stored API key, never a Google Cloud token ------

class _FakeConfig:
    """ConfigManager.get_api_key as the app implements it: in gcloud mode the
    Google lookup answers with an OAuth access token before any stored key."""

    def __init__(self, auth_mode, stored):
        self.config = {"auth_mode": auth_mode}
        self._stored = stored
        self.saved = False

    def get_auth_mode(self, provider="google"):
        return self.config.get("auth_mode", "api-key") if provider == "google" else "api-key"

    def get_api_key(self, provider):
        if provider == "google" and self.get_auth_mode("google") == "gcloud":
            return "oauth-access-token"
        return self._stored.get(provider)

    def save(self):
        self.saved = True


def test_stored_google_key_in_api_key_mode():
    config = _FakeConfig("api-key", {"google": "stored-key"})
    assert live._stored_google_key(config) == "stored-key"


def test_stored_google_key_in_gcloud_mode_is_the_stored_key_not_the_token():
    config = _FakeConfig("gcloud", {"google": "stored-key"})
    assert live._stored_google_key(config) == "stored-key"
    assert config.config["auth_mode"] == "gcloud"  # left as it was
    assert not config.saved


def test_stored_google_key_in_gcloud_mode_without_a_stored_key_is_none():
    config = _FakeConfig("gcloud", {})
    assert live._stored_google_key(config) is None
    assert config.config["auth_mode"] == "gcloud"
    assert not config.saved


def test_stored_google_key_restores_the_mode_when_the_lookup_raises():
    class _Boom(_FakeConfig):
        def get_api_key(self, provider):
            if self.get_auth_mode("google") != "gcloud":
                raise RuntimeError("keyring unavailable")
            return "oauth-access-token"

    config = _Boom("gcloud", {})
    with pytest.raises(RuntimeError):
        live._stored_google_key(config)
    assert config.config["auth_mode"] == "gcloud"


def test_load_keys_never_holds_a_google_cloud_token():
    keys = live._load_keys(_FakeConfig("gcloud", {"openai": "o", "anthropic": "a"}))
    assert keys == {"anthropic": "a", "openai": "o", "google": None}


def test_gemini_api_key_route_skips_in_gcloud_mode_without_a_stored_key():
    keys = live._load_keys(_FakeConfig("gcloud", {}))
    (param,) = [p for p in live._ROUTES if p.id == "gemini-api-key"]
    _name, provider, key_provider, resolver, auth_mode = param.values
    with pytest.raises(pytest.skip.Exception, match="no google API key"):
        live._route_request(keys, provider, key_provider, resolver, auth_mode,
                            live._MSGS, {"max_tokens": 16})


def test_gemini_api_key_route_uses_the_stored_key_in_gcloud_mode():
    keys = live._load_keys(_FakeConfig("gcloud", {"google": "stored-key"}))
    (param,) = [p for p in live._ROUTES if p.id == "gemini-api-key"]
    _name, provider, key_provider, resolver, auth_mode = param.values
    kwargs = live._route_request(keys, provider, key_provider, resolver, auth_mode,
                                 live._MSGS, {"max_tokens": 16})
    assert kwargs["model"] == "gemini/gemini-test-lite"
    assert kwargs["api_key"] == "stored-key"


def test_vertex_route_sends_no_key_in_gcloud_mode():
    keys = live._load_keys(_FakeConfig("gcloud", {"google": "stored-key"}))
    (param,) = [p for p in live._ROUTES if p.id == "vertex"]
    _name, provider, key_provider, resolver, auth_mode = param.values
    kwargs = live._route_request(keys, provider, key_provider, resolver, auth_mode,
                                 live._MSGS, {"max_tokens": 16})
    assert kwargs["model"] == "vertex_ai/gemini-test-lite"
    assert "api_key" not in kwargs
