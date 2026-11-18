import logging
from types import SimpleNamespace

import pytest

from core.chameleon_llm import anthropic_adapter
from core.chameleon_llm.anthropic_adapter import JSON_INSTRUCTION
from core.chameleon_llm.errors import AuthError, BadRequestError, RateLimitError
from core.chameleon_llm.routing import Route
from tests.chameleon_llm.conftest import make_anthropic_reply

MSGS = [{"role": "user", "content": "hi"}]
ROUTE = Route("anthropic", "anthropic", "test-model")


def call(messages=MSGS, *, api_key="k", api_base=None, params=None,
         timeout=600, max_retries=0):
    return anthropic_adapter.complete(
        ROUTE, messages, api_key=api_key, api_base=api_base,
        params=params or {}, timeout=timeout, max_retries=max_retries)


def test_accepted_params():
    assert anthropic_adapter.ACCEPTED_PARAMS == {
        "temperature", "top_p", "top_k", "max_tokens", "response_format", "stop"}


def test_plain_call_and_reply(fake_anthropic):
    resp = call(params={"temperature": 0.2})
    assert fake_anthropic.calls == [{
        "model": "test-model", "messages": MSGS, "max_tokens": 4096,
        "temperature": 0.2}]
    assert resp.model == "test-model"
    assert resp.choices[0].message.role == "assistant"
    assert resp.choices[0].message.content == "hello"
    assert resp.choices[0].finish_reason == "stop"
    u = resp.usage
    assert (u.prompt_tokens, u.completion_tokens, u.total_tokens) == (3, 4, 7)


def test_system_lifted_and_joined(fake_anthropic):
    call([{"role": "system", "content": "A"}, {"role": "user", "content": "hi"},
          {"role": "system", "content": "B"}])
    sent = fake_anthropic.calls[0]
    assert sent["system"] == "A\n\nB"
    assert sent["messages"] == [{"role": "user", "content": "hi"}]


def test_max_tokens_defaults_to_4096(fake_anthropic):
    call()
    assert fake_anthropic.calls[0]["max_tokens"] == 4096
    call(params={"max_tokens": 50})
    assert fake_anthropic.calls[1]["max_tokens"] == 50


def test_data_url_image_becomes_base64_block(fake_anthropic):
    call([{"role": "user", "content": [
        {"type": "text", "text": "look"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}]}])
    assert fake_anthropic.calls[0]["messages"][0]["content"] == [
        {"type": "text", "text": "look"},
        {"type": "image", "source": {
            "type": "base64", "media_type": "image/png", "data": "AAAA"}}]


def test_https_image_becomes_url_source(fake_anthropic):
    call([{"role": "user", "content": [
        {"type": "image_url", "image_url": "https://x.test/a.png"}]}])
    assert fake_anthropic.calls[0]["messages"][0]["content"] == [
        {"type": "image", "source": {"type": "url", "url": "https://x.test/a.png"}}]


def test_native_image_block_passes_through(fake_anthropic):
    block = {"type": "image", "source": {
        "type": "base64", "media_type": "image/jpeg", "data": "QQ=="}}
    call([{"role": "user", "content": [block]}])
    assert fake_anthropic.calls[0]["messages"][0]["content"] == [block]


def test_unsupported_image_url_raises(fake_anthropic):
    with pytest.raises(BadRequestError):
        call([{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "ftp://x/a.png"}}]}])
    assert fake_anthropic.clients_built == 0


@pytest.mark.parametrize("with_system", [False, True])
def test_json_mode_appends_instruction(fake_anthropic, with_system):
    msgs = ([{"role": "system", "content": "Be brief."}] if with_system else []) + MSGS
    call(msgs, params={"response_format": {"type": "json_object"}})
    expected = f"Be brief.\n\n{JSON_INSTRUCTION}" if with_system else JSON_INSTRUCTION
    assert fake_anthropic.calls[0]["system"] == expected
    assert "response_format" not in fake_anthropic.calls[0]


def test_other_response_format_dropped_with_warning(fake_anthropic, caplog):
    with caplog.at_level(logging.WARNING, logger="chameleon_llm"):
        call(params={"response_format": {"type": "text"}})
    assert "system" not in fake_anthropic.calls[0]
    assert "response_format" in caplog.text


def test_stop_string_becomes_list(fake_anthropic):
    call(params={"stop": "END"})
    assert fake_anthropic.calls[0]["stop_sequences"] == ["END"]
    call(params={"stop": ["a", "b"]})
    assert fake_anthropic.calls[1]["stop_sequences"] == ["a", "b"]
    assert "stop" not in fake_anthropic.calls[1]


def test_sampling_params_forwarded(fake_anthropic):
    call(params={"top_p": 0.9, "top_k": 5})
    sent = fake_anthropic.calls[0]
    assert sent["top_p"] == 0.9 and sent["top_k"] == 5


def test_client_built_with_zero_retries_and_timeout(fake_anthropic):
    call(timeout=12, max_retries=0)
    assert fake_anthropic.client_kwargs == [
        {"api_key": "k", "timeout": 12, "max_retries": 0}]


def test_api_base_becomes_base_url(fake_anthropic):
    call(api_base="http://proxy.test")
    assert fake_anthropic.client_kwargs[0]["base_url"] == "http://proxy.test"


@pytest.mark.parametrize("reason,expected", [
    ("end_turn", "stop"), ("stop_sequence", "stop"), ("max_tokens", "length"),
    ("refusal", "content_filter"), ("tool_use", "stop"), (None, "stop")])
def test_finish_reason_map(fake_anthropic, reason, expected):
    fake_anthropic.reply = make_anthropic_reply(stop_reason=reason)
    assert call().choices[0].finish_reason == expected


def test_text_blocks_joined_and_non_text_ignored(fake_anthropic):
    fake_anthropic.reply = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="a"),
                 SimpleNamespace(type="thinking", thinking="hmm"),
                 SimpleNamespace(type="text", text="b")],
        stop_reason="end_turn", usage=None)
    resp = call()
    assert resp.choices[0].message.content == "ab"
    assert resp.usage.total_tokens == 0


def test_no_text_blocks_gives_empty_string(fake_anthropic):
    fake_anthropic.reply = make_anthropic_reply(text=None)
    assert call().choices[0].message.content == ""


def test_assistant_none_content_dropped_not_sent(fake_anthropic):
    call([{"role": "user", "content": "a"},
          {"role": "assistant", "content": None},
          {"role": "user", "content": "b"}])
    assert fake_anthropic.calls[0]["messages"] == [
        {"role": "user", "content": "a"}, {"role": "user", "content": "b"}]


def test_assistant_empty_string_dropped_not_sent(fake_anthropic):
    call([{"role": "user", "content": "a"},
          {"role": "assistant", "content": ""}])
    assert fake_anthropic.calls[0]["messages"] == [{"role": "user", "content": "a"}]


def test_no_user_turn_raises_before_network(fake_anthropic):
    with pytest.raises(BadRequestError, match="user"):
        call([{"role": "system", "content": "only system"}])
    assert fake_anthropic.clients_built == 0


def test_missing_key_names_env_var(fake_anthropic):
    with pytest.raises(AuthError, match="ANTHROPIC_API_KEY"):
        call(api_key=None)
    assert fake_anthropic.clients_built == 0


def test_env_key_used(fake_anthropic, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
    call(api_key=None)
    assert fake_anthropic.client_kwargs[0]["api_key"] == "from-env"


def test_key_never_logged(fake_anthropic, caplog):
    with caplog.at_level(logging.DEBUG, logger="chameleon_llm"):
        call(api_key="sk-secret-123", params={"top_p": 0.5})
    assert "sk-secret-123" not in caplog.text


def test_sdk_error_wrapped(fake_anthropic):
    err = RuntimeError("slow down")
    err.status_code = 429
    fake_anthropic.raises = err
    with pytest.raises(RateLimitError) as info:
        call()
    assert info.value.provider == "anthropic"
    assert info.value.__cause__ is err
