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
