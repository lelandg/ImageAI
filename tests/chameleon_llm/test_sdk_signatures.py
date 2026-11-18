"""The adapters' requests bind to the REAL installed SDK signatures (L1, residual patch).

Each test builds a real SDK client with a fake key (construction sends
nothing) and checks with ``inspect.signature(...).bind(**kwargs)`` that the
kwargs the adapter would send are accepted, using the fullest parameter set the
adapter can produce. No request method is ever called, and sockets are
blocked for the whole module, so a future SDK signature change fails here
instead of in a live call.
"""
import inspect
import socket

import pytest

from core.chameleon_llm import anthropic_adapter, openai_adapter
from core.chameleon_llm.routing import Route

MSGS = [
    {"role": "system", "content": "be brief"},
    {"role": "user", "content": [
        {"type": "text", "text": "what is this"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgo="}},
    ]},
    {"role": "assistant", "content": "a picture"},
    {"role": "user", "content": "and again"},
]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _blocked(*_a, **_k):
        raise OSError("network is disabled in SDK signature tests")
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)


def _bind(fn, kwargs):
    inspect.signature(fn).bind(**kwargs)  # raises TypeError on a mismatch


def test_anthropic_request_binds_to_real_messages_create():
    anthropic = pytest.importorskip("anthropic")
    client = anthropic.Anthropic(api_key="test", timeout=5, max_retries=0,
                                 base_url="http://localhost:1")
    request = anthropic_adapter._build_request(
        Route("anthropic", "anthropic", "test-model"), MSGS,
        {"temperature": 0.3, "top_p": 0.9, "top_k": 5, "max_tokens": 9,
         "response_format": {"type": "json_object"}, "stop": ["END"]})
    fitted = anthropic_adapter._fit_to_sdk(request, client.messages)
    _bind(client.messages.create, fitted)
    sent = {**fitted, **(fitted.get("extra_body") or {})}
    for name in ("temperature", "top_p", "top_k", "max_tokens", "stop_sequences",
                 "system", "messages", "model"):
        assert name in sent, name


def test_openai_chat_request_binds_to_real_create():
    openai = pytest.importorskip("openai")
    client = openai.OpenAI(api_key="test", base_url="http://localhost:1/v1",
                           timeout=5, max_retries=0)
    request = openai_adapter._build_request(
        Route("openai", "openai", "test-model"), MSGS,
        {"temperature": 0.3, "top_p": 0.9, "top_k": 5, "max_tokens": 9,
         "max_completion_tokens": 9, "reasoning_effort": "low", "verbosity": "low",
         "response_format": {"type": "json_object"}, "seed": 1, "stop": ["END"]},
        "http://localhost:1/v1")
    assert request["extra_body"] == {"top_k": 5}
    _bind(client.chat.completions.create, request)


def test_openai_responses_request_binds_to_real_create():
    openai = pytest.importorskip("openai")
    client = openai.OpenAI(api_key="test", timeout=5, max_retries=0)
    request = openai_adapter._build_responses_request(
        Route("openai", "openai", "test-pro-model"), MSGS,
        {"temperature": 0.3, "top_p": 0.9, "max_completion_tokens": 9,
         "reasoning_effort": "low", "verbosity": "low",
         "response_format": {"type": "json_object"}})
    _bind(client.responses.create, request)


def test_gemini_request_binds_to_real_generate_content():
    pytest.importorskip("google.genai")
    from google import genai
    from core.chameleon_llm import gemini_adapter
    route = Route("gemini", "gemini", "test-model")
    params = {"temperature": 0.3, "top_p": 0.9, "top_k": 5, "max_tokens": 9,
              "seed": 1, "stop": ["END"], "response_format": {"type": "json_object"}}
    client_kwargs = gemini_adapter._build_client_kwargs(
        route, "test", None, params, timeout=5, max_retries=0)
    client = genai.Client(**client_kwargs)  # API-key route: no credential lookup
    request = gemini_adapter._build_request(route, MSGS, params)
    _bind(client.models.generate_content, request)
