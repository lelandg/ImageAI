"""OpenAI adapter, Responses path.

Step 1 fact check (installed openai SDK 2.54.0, resources/responses/responses.py
and types/responses/):
  instructions      -> create(instructions=str)              responses.py:141
  input             -> create(input=str | list)              responses.py:140
  output-token cap  -> create(max_output_tokens=int)         responses.py:142
  reasoning effort  -> create(reasoning={"effort": ...})     responses.py:153,
                       shared_params/reasoning.py:30
  verbosity         -> create(text={"verbosity": ...})       response_text_config_param.py:38
  JSON mode         -> create(text={"format": {"type": "json_object"}})
                       response_text_config_param.py:21,33
  input parts       -> {"type": "input_text", "text": ...}   response_input_text_param.py:23,26
                       {"type": "input_image", "image_url": ..., "detail": ...}
                       response_input_image_param.py:27,33,39 (detail is required)
  status            -> Response.status: completed|failed|in_progress|cancelled|
                       queued|incomplete                     response_status.py
  incomplete reason -> Response.incomplete_details.reason: max_output_tokens |
                       content_filter                        response.py:48
  usage             -> input_tokens / output_tokens / total_tokens
                       response_usage.py:34,40,46
  text out          -> Response.output_text property         response.py:476
The Responses endpoint has no seed, stop or top_k parameter (grep of
responses.py), so the adapter drops them with a WARNING.

Which models are Responses-only (OpenAI docs via Context7, 2026-11-18):
  o3, o3-mini, gpt-4.1: listed as Chat Completions models -> NOT Responses-only.
  o1-pro, o3-pro: UNCONFIRMED by documentation reachable from here; kept on the
    pattern list as the design says. A paid live test later must prove them.
  resolve_model("openai", "gpt-pro") returns an id of the shape "gpt-N.N-pro":
    UNCONFIRMED as Responses-only for the same reason; kept on the pattern list.
"""

import logging
from types import SimpleNamespace

import pytest

from core.chameleon_llm import openai_adapter
from core.chameleon_llm.openai_adapter import uses_responses_api
from core.chameleon_llm.routing import Route

OPENAI = Route("openai", "openai", "o3-pro")
MSGS = [{"role": "user", "content": "hi"}]


def call(route=OPENAI, messages=MSGS, *, api_base=None, params=None):
    return openai_adapter.complete(
        route, messages, api_key="k", api_base=api_base, params=params or {},
        timeout=600, max_retries=0)


def make_responses_reply(text="hi", status="completed", usage=(3, 4, 7), reason=None):
    use = None if usage is None else SimpleNamespace(
        input_tokens=usage[0], output_tokens=usage[1], total_tokens=usage[2])
    details = SimpleNamespace(reason=reason) if reason else None
    return SimpleNamespace(output_text=text, status=status, usage=use,
                           incomplete_details=details)


@pytest.mark.parametrize("model,expected", [
    ("o1-pro", True), ("o3-pro", True), ("o3-pro-2025-06-10", True),
    ("o3", False), ("o3-mini", False), ("gpt-4.1", False)])
def test_uses_responses_api(model, expected):
    assert uses_responses_api(model) is expected


def test_gpt_pro_family_id_uses_responses_api():
    assert uses_responses_api("gpt-5.5-pro") is True
    assert uses_responses_api("gpt-5-pro") is True
    assert uses_responses_api("gpt-5.5") is False


def test_patterns_exposed():
    assert isinstance(openai_adapter.RESPONSES_ONLY_PATTERNS, tuple)


def test_responses_request_translation(fake_openai):
    fake_openai.responses_reply = make_responses_reply()
    msgs = [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": [
            {"type": "text", "text": "what is this"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}]},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "more"},
    ]
    call(messages=msgs, params={"max_tokens": 10, "reasoning_effort": "low",
                                "verbosity": "high", "temperature": 0.5,
                                "response_format": {"type": "json_object"}})
    assert fake_openai.chat_calls == []
    sent, = fake_openai.responses_calls
    assert sent == {
        "model": "o3-pro",
        "instructions": "be brief",
        "input": [
            {"role": "user", "content": [
                {"type": "input_text", "text": "what is this"},
                {"type": "input_image", "image_url": "data:image/png;base64,AAAA",
                 "detail": "auto"}]},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": [{"type": "input_text", "text": "more"}]},
        ],
        "max_output_tokens": 10,
        "reasoning": {"effort": "low"},
        "text": {"verbosity": "high", "format": {"type": "json_object"}},
        "temperature": 0.5,
    }


def test_max_completion_tokens_also_maps(fake_openai):
    fake_openai.responses_reply = make_responses_reply()
    call(params={"max_completion_tokens": 77})
    assert fake_openai.responses_calls[0]["max_output_tokens"] == 77


def test_json_schema_format_translated(fake_openai):
    fake_openai.responses_reply = make_responses_reply()
    call(params={"response_format": {"type": "json_schema", "json_schema": {
        "name": "n", "schema": {"type": "object"}, "strict": True}}})
    assert fake_openai.responses_calls[0]["text"] == {"format": {
        "type": "json_schema", "name": "n", "schema": {"type": "object"},
        "strict": True}}


def test_unsupported_params_dropped_with_warning(fake_openai, caplog):
    fake_openai.responses_reply = make_responses_reply()
    with caplog.at_level(logging.WARNING, logger="chameleon_llm"):
        call(params={"seed": 1, "stop": ["x"], "top_k": 3})
    sent = fake_openai.responses_calls[0]
    assert not {"seed", "stop", "top_k"} & set(sent)
    text = " ".join(r.getMessage() for r in caplog.records
                    if r.levelno == logging.WARNING)
    assert all(name in text for name in ("seed", "stop", "top_k"))


def test_responses_reply_normalised(fake_openai):
    fake_openai.responses_reply = make_responses_reply("hi")
    resp = call()
    assert resp.model == "o3-pro"
    assert resp.choices[0].message.role == "assistant"
    assert resp.choices[0].message.content == "hi"
    assert resp.choices[0].finish_reason == "stop"
    u = resp.usage
    assert (u.prompt_tokens, u.completion_tokens, u.total_tokens) == (3, 4, 7)
    fake_openai.responses_reply = make_responses_reply(status="incomplete",
                                                       reason="max_output_tokens")
    assert call().choices[0].finish_reason == "length"


def test_responses_empty_output_is_empty_string(fake_openai):
    fake_openai.responses_reply = make_responses_reply(text=None, usage=None)
    resp = call()
    assert resp.choices[0].message.content == ""
    assert resp.usage.total_tokens == 0
    fake_openai.responses_reply = SimpleNamespace()
    assert call().choices[0].message.content == ""


def test_responses_sdk_error_wrapped(fake_openai):
    from core.chameleon_llm.errors import LLMError
    fake_openai.raises = RuntimeError("boom")
    with pytest.raises(LLMError):
        call()


def test_local_server_never_uses_responses(fake_openai):
    call(api_base="http://localhost:1234/v1")
    assert fake_openai.responses_calls == []
    assert len(fake_openai.chat_calls) == 1
    call(Route("openai", "ollama", "o3-pro"))
    assert fake_openai.responses_calls == []


def test_assistant_none_content_sent_as_empty_string(fake_openai):
    fake_openai.responses_reply = make_responses_reply()
    call(messages=[{"role": "user", "content": "a"},
                   {"role": "assistant", "content": None},
                   {"role": "assistant", "content": [
                       {"type": "text", "text": "x"}, {"type": "text", "text": "y"}]},
                   {"role": "user", "content": "b"}])
    inp = fake_openai.responses_calls[0]["input"]
    assert inp[1] == {"role": "assistant", "content": ""}
    assert inp[2] == {"role": "assistant", "content": "x\n\ny"}
