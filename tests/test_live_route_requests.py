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
