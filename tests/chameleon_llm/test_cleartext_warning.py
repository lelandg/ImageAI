"""A real API key sent to a cleartext, non-loopback api_base is reported once."""

import logging

import pytest

from core.chameleon_llm import anthropic_adapter, endpoint, openai_adapter
from core.chameleon_llm.routing import Route

MSGS = [{"role": "user", "content": "hi"}]
OPENAI = Route("openai", "openai", "test-model")
OLLAMA = Route("openai", "ollama", "test-model")
LMSTUDIO = Route("openai", "lm_studio", "test-model")
ANTHROPIC = Route("anthropic", "anthropic", "test-model")
SECRET = "sk-secret-value-123"


@pytest.fixture(autouse=True)
def _fresh_warnings():
    endpoint._reset_cleartext_warnings()
    yield
    endpoint._reset_cleartext_warnings()


def _openai(route, api_base, api_key=SECRET):
    return openai_adapter.complete(route, MSGS, api_key=api_key, api_base=api_base,
                                   params={}, timeout=600, max_retries=0)


def _anthropic(api_base, api_key=SECRET):
    return anthropic_adapter.complete(ANTHROPIC, MSGS, api_key=api_key,
                                      api_base=api_base, params={}, timeout=600,
                                      max_retries=0)


def _cleartext(caplog):
    return [r for r in caplog.records
            if r.levelno == logging.WARNING and "unencrypted" in r.getMessage()]


@pytest.mark.parametrize("url,expected", [
    ("http://example.test:8080/v1", True),
    ("http://192.168.0.20:1234/v1", True),
    ("HTTP://Example.test/v1", True),
    ("ws://example.test/v1", True),
    ("example.test:8080/v1", True),          # no scheme: not known to be https
    ("https://example.test/v1", False),
    ("HTTPS://example.test/v1", False),
    ("http://localhost:1234/v1", False),
    ("http://LOCALHOST/v1", False),
    ("http://127.0.0.1:11434/v1", False),
    ("http://127.8.9.10/v1", False),
    ("http://[::1]:1234/v1", False),
    ("http://localhost.example.test/v1", True),   # a name that only starts like it
    ("http://127.0.0.1.example.test/v1", True),
])
def test_is_cleartext_remote(url, expected):
    assert endpoint.is_cleartext_remote(url) is expected


def test_openai_route_warns_once_per_base_url(fake_openai, caplog):
    with caplog.at_level(logging.WARNING, logger="chameleon_llm"):
        _openai(OPENAI, "http://example.test:8080/v1")
        _openai(OPENAI, "http://example.test:8080/v1")
    records = _cleartext(caplog)
    assert len(records) == 1
    assert "http://example.test:8080/v1" in records[0].getMessage()
    assert SECRET not in caplog.text
    assert len(fake_openai.chat_calls) == 2  # warned, not rejected


def test_each_distinct_base_url_warns(fake_openai, caplog):
    with caplog.at_level(logging.WARNING, logger="chameleon_llm"):
        _openai(OPENAI, "http://one.test/v1")
        _openai(LMSTUDIO, "http://two.test/v1")
    assert len(_cleartext(caplog)) == 2


def test_ollama_remote_cleartext_with_key_warns(fake_openai, caplog):
    with caplog.at_level(logging.WARNING, logger="chameleon_llm"):
        _openai(OLLAMA, "http://ollama.example.test:11434")
    assert len(_cleartext(caplog)) == 1


@pytest.mark.parametrize("route,base", [
    (OPENAI, "https://proxy.example.test/v1"),
    (LMSTUDIO, "http://localhost:1234/v1"),
    (OLLAMA, None),                              # default http://localhost:11434
    (OLLAMA, "http://127.0.0.1:11434"),
    (OPENAI, None),                              # the SDK's own https endpoint
])
def test_no_warning_for_https_or_loopback(fake_openai, caplog, route, base):
    with caplog.at_level(logging.WARNING, logger="chameleon_llm"):
        _openai(route, base)
    assert not _cleartext(caplog)


def test_no_warning_when_only_the_placeholder_key_is_sent(fake_openai, caplog):
    with caplog.at_level(logging.WARNING, logger="chameleon_llm"):
        _openai(LMSTUDIO, "http://192.168.0.20:1234/v1", api_key=None)
    assert fake_openai.client_kwargs[-1]["api_key"] == "not-needed"
    assert not _cleartext(caplog)


def test_env_base_url_is_checked_too(fake_openai, caplog, monkeypatch):
    monkeypatch.setenv("OPENAI_API_BASE", "http://env.example.test/v1")
    with caplog.at_level(logging.WARNING, logger="chameleon_llm"):
        _openai(OPENAI, None)
    assert len(_cleartext(caplog)) == 1


def test_anthropic_warns_once_and_still_sends(fake_anthropic, caplog):
    with caplog.at_level(logging.WARNING, logger="chameleon_llm"):
        _anthropic("http://gateway.example.test")
        _anthropic("http://gateway.example.test")
    records = _cleartext(caplog)
    assert len(records) == 1
    assert "http://gateway.example.test" in records[0].getMessage()
    assert SECRET not in caplog.text
    assert len(fake_anthropic.calls) == 2


@pytest.mark.parametrize("base", [None, "https://gateway.example.test",
                                  "http://localhost:8080"])
def test_anthropic_no_warning_for_default_https_or_loopback(
        fake_anthropic, caplog, base):
    with caplog.at_level(logging.WARNING, logger="chameleon_llm"):
        _anthropic(base)
    assert not _cleartext(caplog)


def test_userinfo_and_query_are_not_logged(fake_openai, caplog):
    with caplog.at_level(logging.WARNING, logger="chameleon_llm"):
        _openai(OPENAI, "http://user:pw-in-url@example.test/v1?token=q-secret")
    records = _cleartext(caplog)
    assert len(records) == 1
    assert "pw-in-url" not in caplog.text and "q-secret" not in caplog.text
    assert "example.test" in records[0].getMessage()
