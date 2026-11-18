"""Gemini adapter tests against a fake ``genai.Client``.

SDK facts (google-genai 2.10.0, confirmed in the installed package):
``HttpOptions.timeout`` is an int in MILLISECONDS, so the adapter sends
``int(timeout * 1000)``; ``HttpOptions.retry_options=HttpRetryOptions(attempts=N)``
where N counts total attempts including the first, so ``max_retries`` maps to
``attempts = max_retries + 1`` (zero retries means attempts=1).
``genai.errors.APIError`` carries the HTTP status as ``.code`` (not
``.status_code``); ``errors._status_of`` reads it as a fallback.
"""

import base64
import logging
from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors
from google.genai import types

from core.chameleon_llm import gemini_adapter
from core.chameleon_llm.errors import AuthError, BadRequestError, RateLimitError
from core.chameleon_llm.routing import Route
from tests.chameleon_llm.conftest import make_genai_reply

MSGS = [{"role": "user", "content": "hi"}]
GEMINI = Route("gemini", "gemini", "test-model")
VERTEX = Route("gemini", "vertex_ai", "test-model")


def call(messages=MSGS, *, route=GEMINI, api_key="k", api_base=None,
         params=None, timeout=600, max_retries=0):
    return gemini_adapter.complete(
        route, messages, api_key=api_key, api_base=api_base,
        params=params or {}, timeout=timeout, max_retries=max_retries)


def config_of(state, index=0):
    return state.calls[index]["config"]


def test_accepted_params():
    assert gemini_adapter.ACCEPTED_PARAMS == {
        "temperature", "top_p", "top_k", "max_tokens", "response_format",
        "seed", "stop", "vertex_project", "vertex_location"}


def test_api_key_route_builds_key_client(fake_genai):
    resp = call(api_key="secret")
    kwargs = fake_genai.client_kwargs[0]
    assert kwargs["api_key"] == "secret"
    assert "vertexai" not in kwargs
    assert fake_genai.calls[0]["model"] == "test-model"
    assert resp.model == "test-model"
    assert resp.choices[0].message.role == "assistant"
    assert resp.choices[0].message.content == "hello"
    u = resp.usage
    assert (u.prompt_tokens, u.completion_tokens, u.total_tokens) == (3, 4, 7)


def test_google_api_key_env_fallback(fake_genai, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "g")
    call(api_key=None)
    assert fake_genai.client_kwargs[0]["api_key"] == "g"


def test_gemini_env_beats_google_env(fake_genai, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "g")
    monkeypatch.setenv("GEMINI_API_KEY", "m")
    call(api_key=None)
    assert fake_genai.client_kwargs[0]["api_key"] == "m"


def test_vertex_route_builds_vertex_client_with_defaults(fake_genai):
    call(route=VERTEX, api_key=None)
    kwargs = fake_genai.client_kwargs[0]
    assert kwargs["vertexai"] is True
    assert kwargs["project"] is None
    assert kwargs["location"] == "us-central1"
    assert "api_key" not in kwargs


def test_vertex_env_used(fake_genai, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-proj")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "env-loc")
    call(route=VERTEX, api_key=None)
    kwargs = fake_genai.client_kwargs[0]
    assert (kwargs["project"], kwargs["location"]) == ("env-proj", "env-loc")


def test_vertex_args_beat_env(fake_genai, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-proj")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "env-loc")
    call(route=VERTEX, api_key=None,
         params={"vertex_project": "p", "vertex_location": "l"})
    kwargs = fake_genai.client_kwargs[0]
    assert (kwargs["project"], kwargs["location"]) == ("p", "l")
    assert "vertex_project" not in config_of(fake_genai).model_dump(exclude_none=True)


def test_system_becomes_system_instruction_and_assistant_becomes_model(fake_genai):
    call([{"role": "system", "content": "A"},
          {"role": "user", "content": "q"},
          {"role": "developer", "content": "B"},
          {"role": "assistant", "content": "a"},
          {"role": "user", "content": "q2"}])
    sent = fake_genai.calls[0]
    assert config_of(fake_genai).system_instruction == "A\n\nB"
    assert [(c.role, c.parts[0].text) for c in sent["contents"]] == [
        ("user", "q"), ("model", "a"), ("user", "q2")]


def test_param_mapping(fake_genai):
    call(params={"temperature": 0.2, "top_p": 0.9, "top_k": 5, "seed": 7,
                 "max_tokens": 50, "stop": "END"})
    cfg = config_of(fake_genai)
    assert cfg.temperature == 0.2
    assert cfg.top_p == 0.9
    assert cfg.top_k == 5
    assert cfg.seed == 7
    assert cfg.max_output_tokens == 50
    assert cfg.stop_sequences == ["END"]


def test_stop_list_passes_through(fake_genai):
    call(params={"stop": ["a", "b"]})
    assert config_of(fake_genai).stop_sequences == ["a", "b"]


def test_json_mode_sets_mime_type(fake_genai, caplog):
    with caplog.at_level(logging.DEBUG, logger="chameleon_llm"):
        call(params={"response_format": {"type": "json_object"}})
    assert config_of(fake_genai).response_mime_type == "application/json"
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_other_response_format_dropped_with_warning(fake_genai, caplog):
    with caplog.at_level(logging.WARNING, logger="chameleon_llm"):
        call(params={"response_format": {"type": "json_schema"}})
    assert config_of(fake_genai).response_mime_type is None
    assert any("json_schema" in r.getMessage() and r.levelno == logging.WARNING
               for r in caplog.records)


def test_data_url_image_becomes_inline_data(fake_genai):
    raw = b"\x89PNGdata"
    b64 = base64.b64encode(raw).decode()
    call([{"role": "user", "content": [
        {"type": "text", "text": "look"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}])
    parts = fake_genai.calls[0]["contents"][0].parts
    assert parts[0].text == "look"
    assert parts[1].inline_data.mime_type == "image/png"
    assert parts[1].inline_data.data == raw


def test_http_image_url_rejected_before_network(fake_genai):
    with pytest.raises(BadRequestError):
        call([{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "https://x/y.png"}}]}])
    assert fake_genai.clients_built == 0 and fake_genai.calls == []


def test_no_user_turn_rejected_before_network(fake_genai):
    with pytest.raises(BadRequestError):
        call([{"role": "system", "content": "only system"}])
    assert fake_genai.clients_built == 0


def test_assistant_none_content_dropped_with_debug(fake_genai, caplog):
    with caplog.at_level(logging.DEBUG, logger="chameleon_llm"):
        call([{"role": "user", "content": "SECRETTEXT"},
              {"role": "assistant", "content": None},
              {"role": "user", "content": "q2"}])
    roles = [c.role for c in fake_genai.calls[0]["contents"]]
    assert roles == ["user", "user"]
    msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG]
    assert any("index 1" in m for m in msgs)
    assert not any("SECRETTEXT" in m for m in msgs)


@pytest.mark.parametrize("reason,expected", [
    ("STOP", "stop"), ("MAX_TOKENS", "length"),
    ("SAFETY", "content_filter"), ("RECITATION", "content_filter"),
    ("BLOCKLIST", "content_filter"), ("PROHIBITED_CONTENT", "content_filter"),
    (types.FinishReason.MAX_TOKENS, "length"),
    (types.FinishReason.SAFETY, "content_filter"),
    (None, "stop")])
def test_finish_reason_map(fake_genai, reason, expected):
    fake_genai.reply = make_genai_reply(finish_reason=reason)
    assert call().choices[0].finish_reason == expected


def test_no_candidates_gives_empty_content_filter(fake_genai):
    fake_genai.reply = SimpleNamespace(candidates=None, usage_metadata=None)
    resp = call()
    assert resp.choices[0].message.content == ""
    assert resp.choices[0].finish_reason == "content_filter"
    assert resp.usage.total_tokens == 0


def test_candidate_without_parts_gives_empty_content_filter(fake_genai):
    fake_genai.reply = SimpleNamespace(
        candidates=[SimpleNamespace(content=None, finish_reason="SAFETY")],
        usage_metadata=None)
    resp = call()
    assert resp.choices[0].message.content == ""
    assert resp.choices[0].finish_reason == "content_filter"


def test_multiple_text_parts_joined(fake_genai):
    fake_genai.reply = SimpleNamespace(
        candidates=[SimpleNamespace(
            content=SimpleNamespace(parts=[SimpleNamespace(text="a"),
                                           SimpleNamespace(text=None),
                                           SimpleNamespace(text="b")]),
            finish_reason="STOP")],
        usage_metadata=None)
    assert call().choices[0].message.content == "ab"


def test_usage_none_fields_become_zero(fake_genai):
    fake_genai.reply.usage_metadata = SimpleNamespace(
        prompt_token_count=None, candidates_token_count=5, total_token_count=None)
    u = call().usage
    assert (u.prompt_tokens, u.completion_tokens, u.total_tokens) == (0, 5, 5)


def test_retries_zero_by_default(fake_genai):
    call()
    opts = fake_genai.client_kwargs[0]["http_options"]
    assert opts.retry_options.attempts == 1
    assert opts.timeout == 600_000


def test_retries_map_to_total_attempts(fake_genai):
    call(max_retries=2, timeout=1.5)
    opts = fake_genai.client_kwargs[0]["http_options"]
    assert opts.retry_options.attempts == 3
    assert opts.timeout == 1500


def test_missing_key_names_env_var(fake_genai):
    with pytest.raises(AuthError, match="GEMINI_API_KEY"):
        call(api_key=None)
    assert fake_genai.clients_built == 0


def test_key_never_logged(fake_genai, caplog):
    with caplog.at_level(logging.DEBUG, logger="chameleon_llm"):
        call(api_key="sk-supersecret")
    assert "sk-supersecret" not in caplog.text


def test_unused_args_dropped_with_warning(fake_genai, caplog):
    with caplog.at_level(logging.WARNING, logger="chameleon_llm"):
        call(api_base="http://x", params={"vertex_project": "p"})
    assert "api_base" in caplog.text and "vertex_project" in caplog.text
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="chameleon_llm"):
        call(route=VERTEX, api_key="sk-secret")
    assert "api_key" in caplog.text and "sk-secret" not in caplog.text


def test_sdk_error_wrapped(fake_genai):
    fake_genai.raises = genai_errors.ClientError(
        429, {"error": {"message": "slow down", "status": "RESOURCE_EXHAUSTED"}})
    with pytest.raises(RateLimitError) as info:
        call()
    assert info.value.__cause__ is fake_genai.raises
    assert "slow down" in str(info.value)
