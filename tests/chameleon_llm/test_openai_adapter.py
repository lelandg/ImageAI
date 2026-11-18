import logging
from types import SimpleNamespace

import pytest

from core.chameleon_llm import openai_adapter
from core.chameleon_llm.errors import (
    AuthError, BadRequestError, LLMError, RateLimitError,
)
from core.chameleon_llm.routing import Route
from tests.chameleon_llm.conftest import make_chat_reply

MSGS = [{"role": "user", "content": "hi"}]
OPENAI = Route("openai", "openai", "test-model")
OLLAMA = Route("openai", "ollama", "test-model")
LMSTUDIO = Route("openai", "lm_studio", "test-model")


def call(route=OPENAI, messages=MSGS, *, api_key="k", api_base=None, params=None,
         timeout=600, max_retries=0):
    return openai_adapter.complete(
        route, messages, api_key=api_key, api_base=api_base,
        params=params or {}, timeout=timeout, max_retries=max_retries)


def test_accepted_params():
    assert openai_adapter.ACCEPTED_PARAMS == {
        "temperature", "top_p", "top_k", "max_tokens", "max_completion_tokens",
        "reasoning_effort", "verbosity", "response_format", "seed", "stop"}


def test_plain_call_builds_client_and_request(fake_openai):
    resp = call(params={"temperature": 0.2})
    assert fake_openai.client_kwargs == [
        {"api_key": "k", "base_url": None, "timeout": 600, "max_retries": 0}]
    assert fake_openai.chat_calls == [
        {"model": "test-model", "messages": MSGS, "temperature": 0.2}]
    assert resp.model == "echoed-model"  # the model the provider reports
    assert resp.choices[0].message.role == "assistant"
    assert resp.choices[0].message.content == "hello"
    assert resp.choices[0].finish_reason == "stop"
    assert (resp.usage.prompt_tokens, resp.usage.completion_tokens,
            resp.usage.total_tokens) == (3, 4, 7)


def test_caller_max_retries_passed_through(fake_openai):
    call(max_retries=3, timeout=12.5)
    assert fake_openai.client_kwargs[0]["max_retries"] == 3
    assert fake_openai.client_kwargs[0]["timeout"] == 12.5


def test_one_client_per_call(fake_openai):
    call()
    call()
    assert fake_openai.clients_built == 2


def test_key_from_env(fake_openai, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    call(api_key=None)
    assert fake_openai.client_kwargs[0]["api_key"] == "env-key"


def test_argument_key_beats_env(fake_openai, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    call(api_key="arg-key")
    assert fake_openai.client_kwargs[0]["api_key"] == "arg-key"


def test_ollama_base_url_default_and_v1_suffix(fake_openai, monkeypatch):
    call(OLLAMA, api_key=None)
    assert fake_openai.client_kwargs[-1]["base_url"] == "http://localhost:11434/v1"
    assert fake_openai.client_kwargs[-1]["api_key"] == "not-needed"
    monkeypatch.setenv("OLLAMA_API_BASE", "http://h:1")
    call(OLLAMA, api_key=None)
    assert fake_openai.client_kwargs[-1]["base_url"] == "http://h:1/v1"
    call(OLLAMA, api_key=None, api_base="http://x:2/")
    assert fake_openai.client_kwargs[-1]["base_url"] == "http://x:2/v1"
    call(OLLAMA, api_key=None, api_base="http://x:2/v1/")
    assert fake_openai.client_kwargs[-1]["base_url"] == "http://x:2/v1"


def test_lm_studio_requires_base(fake_openai):
    with pytest.raises(BadRequestError):
        call(LMSTUDIO, api_key=None)
    assert fake_openai.clients_built == 0


def test_lm_studio_uses_base_and_placeholder_key(fake_openai, monkeypatch):
    call(LMSTUDIO, api_key=None, api_base="http://lm:1234/v1")
    assert fake_openai.client_kwargs[0]["base_url"] == "http://lm:1234/v1"
    assert fake_openai.client_kwargs[0]["api_key"] == "not-needed"
    monkeypatch.setenv("OPENAI_API_BASE", "http://env:9/v1")
    call(LMSTUDIO, api_key=None)
    assert fake_openai.client_kwargs[1]["base_url"] == "http://env:9/v1"


def test_openai_api_base_env_used(fake_openai, monkeypatch):
    monkeypatch.setenv("OPENAI_API_BASE", "http://proxy/v1")
    call()
    assert fake_openai.client_kwargs[0]["base_url"] == "http://proxy/v1"


def test_api_base_argument_beats_env_and_allows_missing_key(fake_openai, monkeypatch):
    monkeypatch.setenv("OPENAI_API_BASE", "http://env/v1")
    call(api_key=None, api_base="http://arg/v1")
    assert fake_openai.client_kwargs[0]["base_url"] == "http://arg/v1"
    assert fake_openai.client_kwargs[0]["api_key"] == "not-needed"


def test_top_k_in_extra_body_for_local_and_dropped_for_cloud(fake_openai, caplog):
    call(OLLAMA, api_key=None, params={"top_k": 40, "temperature": 0.1})
    assert fake_openai.chat_calls[-1]["extra_body"] == {"top_k": 40}
    assert "top_k" not in fake_openai.chat_calls[-1]
    call(api_base="http://proxy/v1", params={"top_k": 5})
    assert fake_openai.chat_calls[-1]["extra_body"] == {"top_k": 5}
    with caplog.at_level(logging.WARNING, logger="chameleon_llm"):
        call(params={"top_k": 40})
    assert "top_k" not in fake_openai.chat_calls[-1]
    assert "extra_body" not in fake_openai.chat_calls[-1]
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1 and "top_k" in warnings[0].getMessage()


def test_missing_key_raises_auth_error_before_network(fake_openai):
    with pytest.raises(AuthError) as info:
        call(api_key=None)
    assert "OPENAI_API_KEY" in str(info.value)
    assert fake_openai.clients_built == 0
    assert fake_openai.chat_calls == []


def test_empty_key_counts_as_missing(fake_openai):
    with pytest.raises(AuthError):
        call(api_key="")


def test_key_never_logged(fake_openai, caplog):
    with caplog.at_level(logging.DEBUG):
        call(api_key="sk-test-123", params={"temperature": 0.1})
        fake_openai.raises = RuntimeError("boom")
        with pytest.raises(LLMError):
            call(api_key="sk-test-123")
    assert "sk-test-123" not in caplog.text
    assert all("sk-test-123" not in str(r.args) for r in caplog.records)


def test_none_content_becomes_empty_string(fake_openai):
    fake_openai.chat_reply = make_chat_reply(content=None)
    assert call().choices[0].message.content == ""


def test_empty_choices_gives_empty_reply(fake_openai):
    fake_openai.chat_reply.choices = []
    resp = call()
    assert resp.choices[0].message.content == ""
    assert resp.choices[0].finish_reason == "stop"


def test_none_finish_reason_becomes_stop_and_others_pass_through(fake_openai):
    fake_openai.chat_reply = make_chat_reply(finish_reason=None)
    assert call().choices[0].finish_reason == "stop"
    fake_openai.chat_reply = make_chat_reply(finish_reason="length")
    assert call().choices[0].finish_reason == "length"


def test_missing_usage_becomes_zeros(fake_openai):
    fake_openai.chat_reply = make_chat_reply(usage=None)
    u = call().usage
    assert (u.prompt_tokens, u.completion_tokens, u.total_tokens) == (0, 0, 0)


def test_list_content_and_image_parts_pass_through_unchanged(fake_openai):
    msgs = [{"role": "user", "content": [
        {"type": "text", "text": "what is this"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
    ]}]
    call(messages=msgs)
    assert fake_openai.chat_calls[0]["messages"] == msgs


def test_assistant_none_and_empty_content_pass_through(fake_openai):
    msgs = [{"role": "user", "content": "hi"},
            {"role": "assistant", "content": None},
            {"role": "assistant", "content": ""},
            {"role": "user", "content": "again"}]
    call(messages=msgs)
    assert fake_openai.chat_calls[0]["messages"] == msgs


def test_params_forwarded_verbatim(fake_openai):
    params = {"max_completion_tokens": 50, "reasoning_effort": "low", "seed": 1,
              "stop": ["x"], "response_format": {"type": "json_object"}}
    call(params=params)
    sent = fake_openai.chat_calls[0]
    for k, v in params.items():
        assert sent[k] == v


def test_sdk_error_wrapped(fake_openai):
    class FakeRateLimit(Exception):
        status_code = 429
    err = FakeRateLimit("slow down")
    fake_openai.raises = err
    with pytest.raises(RateLimitError) as info:
        call()
    assert info.value.__cause__ is err
    assert info.value.provider == "openai"
    assert info.value.status_code == 429


# --- I2: a base URL in effect never receives the environment OpenAI key -----

def test_env_openai_key_not_sent_to_ollama(fake_openai, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-cloud-key")
    call(OLLAMA, api_key=None)
    assert fake_openai.client_kwargs[0]["api_key"] == "not-needed"


def test_env_openai_key_not_sent_to_lm_studio(fake_openai, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-cloud-key")
    call(LMSTUDIO, api_key=None, api_base="http://lm:1234/v1")
    assert fake_openai.client_kwargs[0]["api_key"] == "not-needed"


def test_env_openai_key_not_sent_to_custom_base(fake_openai, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-cloud-key")
    call(api_key=None, api_base="http://compat/v1")
    assert fake_openai.client_kwargs[-1]["api_key"] == "not-needed"
    monkeypatch.setenv("OPENAI_API_BASE", "http://env-compat/v1")
    call(api_key=None)
    assert fake_openai.client_kwargs[-1]["api_key"] == "not-needed"


def test_explicit_key_sent_to_local_route(fake_openai, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-cloud-key")
    call(OLLAMA, api_key="local-key")
    assert fake_openai.client_kwargs[0]["api_key"] == "local-key"


def test_plain_openai_route_still_reads_env_key(fake_openai, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-cloud-key")
    call(api_key=None)
    assert fake_openai.client_kwargs[0]["api_key"] == "sk-real-cloud-key"
    assert fake_openai.client_kwargs[0]["base_url"] is None


# --- M2: response.model reports the model the provider says it used ---------

def test_response_model_is_provider_reported(fake_openai):
    assert call().model == "echoed-model"


def test_response_model_falls_back_to_requested(fake_openai):
    fake_openai.chat_reply.model = None
    assert call().model == "test-model"


# --- I5a: a Responses-only model unknown to the pattern list ----------------

class _NotChatError(Exception):
    def __init__(self, msg, status_code):
        super().__init__(msg)
        self.status_code = status_code


@pytest.mark.parametrize("status,msg", [
    (404, "This model is only supported in v1/responses and not in v1/chat/completions."),
    (400, "This model is only available through the Responses API."),
])
def test_chat_error_pointing_at_responses_retries_once_there(
        fake_openai, caplog, status, msg):
    fake_openai.chat_raises = _NotChatError(msg, status)
    fake_openai.responses_reply = SimpleNamespace(
        output_text="from responses", status="completed", usage=None,
        incomplete_details=None, model="served-model")
    with caplog.at_level(logging.WARNING, logger="chameleon_llm"):
        resp = call(Route("openai", "openai", "new-pro-model"),
                    params={"max_tokens": 9})
    assert len(fake_openai.chat_calls) == 1
    assert len(fake_openai.responses_calls) == 1
    assert fake_openai.responses_calls[0]["max_output_tokens"] == 9
    assert resp.choices[0].message.content == "from responses"
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "new-pro-model" in warnings[0] and "RESPONSES_ONLY_PATTERNS" in warnings[0]


def test_responses_retry_failure_is_wrapped(fake_openai):
    class Boom(Exception):
        status_code = 500
    fake_openai.chat_raises = _NotChatError("use the Responses API", 404)
    fake_openai.responses_raises = Boom("down")
    with pytest.raises(LLMError) as info:
        call(Route("openai", "openai", "new-pro-model"))
    assert info.value.status_code == 500
    assert len(fake_openai.chat_calls) == 1
    assert len(fake_openai.responses_calls) == 1


@pytest.mark.parametrize("status,msg", [
    (400, "Invalid value for temperature."),     # 400 without the hint
    (500, "v1/responses is down"),              # hint but wrong status
])
def test_other_chat_errors_are_not_retried(fake_openai, status, msg):
    fake_openai.raises = _NotChatError(msg, status)
    with pytest.raises(LLMError):
        call()
    assert len(fake_openai.chat_calls) == 1
    assert fake_openai.responses_calls == []


def test_responses_retry_not_attempted_on_local_base(fake_openai):
    fake_openai.raises = _NotChatError("use the Responses API", 404)
    with pytest.raises(BadRequestError):
        call(OLLAMA, api_key=None)
    assert fake_openai.responses_calls == []


# --- L2 defense: max_tokens refused in favour of max_completion_tokens --------

_TOKENS_MSG = ("Unsupported parameter: 'max_tokens' is not supported with this "
               "model. Use 'max_completion_tokens' instead.")


class _OneShotChat:
    """Patches chat.completions.create: raise ``first`` once, then ``then``."""

    def __init__(self, monkeypatch, state, first, then=None):
        orig = openai_adapter.openai.OpenAI
        outer = self
        self.calls = state.chat_calls
        self.first, self.then = first, then

        def build(**kwargs):
            client = orig(**kwargs)

            def create(**kw):
                outer.calls.append(kw)
                if len(outer.calls) == 1:
                    raise outer.first
                if outer.then is not None:
                    raise outer.then
                return state.chat_reply
            client.chat.completions.create = create
            return client
        monkeypatch.setattr(openai_adapter.openai, "OpenAI", build)


def test_max_tokens_refusal_retries_once_renamed(fake_openai, monkeypatch, caplog):
    _OneShotChat(monkeypatch, fake_openai, _NotChatError(_TOKENS_MSG, 400))
    with caplog.at_level(logging.WARNING, logger="chameleon_llm"):
        resp = call(Route("openai", "openai", "new-model"),
                    params={"max_tokens": 64, "temperature": 1})
    assert len(fake_openai.chat_calls) == 2
    first, second = fake_openai.chat_calls
    assert first["max_tokens"] == 64 and "max_completion_tokens" not in first
    assert second["max_completion_tokens"] == 64 and "max_tokens" not in second
    assert resp.choices[0].message.content == "hello"
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1 and "new-model" in warnings[0]


def test_max_tokens_retry_failure_carries_both_errors(fake_openai, monkeypatch):
    class Boom(Exception):
        status_code = 500
    _OneShotChat(monkeypatch, fake_openai, _NotChatError(_TOKENS_MSG, 400),
                 then=Boom("down"))
    with pytest.raises(LLMError) as info:
        call(Route("openai", "openai", "new-model"), params={"max_tokens": 64})
    assert len(fake_openai.chat_calls) == 2  # one retry, no loop
    assert info.value.status_code == 500
    assert "down" in str(info.value) and "max_completion_tokens" in str(info.value)
    assert isinstance(info.value.__cause__, Boom)


def test_max_tokens_refusal_without_max_tokens_is_not_retried(fake_openai):
    fake_openai.chat_raises = _NotChatError(_TOKENS_MSG, 400)
    with pytest.raises(BadRequestError):
        call(params={"temperature": 1})
    assert len(fake_openai.chat_calls) == 1


# --- R3: a failed Responses retry also reports the chat error ----------------

def test_responses_retry_failure_includes_the_chat_error(fake_openai):
    class Boom(Exception):
        status_code = 500
    fake_openai.chat_raises = _NotChatError("use the Responses API please", 404)
    fake_openai.responses_raises = Boom("down")
    with pytest.raises(LLMError) as info:
        call(Route("openai", "openai", "new-pro-model"))
    assert "down" in str(info.value)
    assert "use the Responses API please" in str(info.value)
    assert isinstance(info.value.__cause__, Boom)
