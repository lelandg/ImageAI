"""Anthropic adapter: OpenAI-style messages in, Messages API call, Completion out."""

from __future__ import annotations

import inspect
import logging
import os
import re
import weakref

import anthropic  # top-level on purpose: dispatch turns an ImportError here into MissingSDKError

from .endpoint import warn_if_cleartext_key
from .errors import AuthError, BadRequestError, wrap_sdk_error
from .routing import Route
from .types import Choice, Completion, Message, Usage

logger = logging.getLogger("chameleon_llm")

ACCEPTED_PARAMS = frozenset({
    "temperature", "top_p", "top_k", "max_tokens", "response_format", "stop",
})

JSON_INSTRUCTION = "Respond with a single valid JSON object and no other text."
DEFAULT_MAX_TOKENS = 4096

_FINISH_REASONS = {"max_tokens": "length", "refusal": "content_filter"}
_DATA_URL = re.compile(r"^data:([^;,]+);base64,(.*)$", re.DOTALL)


def _resolve_key(api_key: str | None) -> str:
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    raise AuthError(
        "No Anthropic API key: pass api_key or set ANTHROPIC_API_KEY",
        provider="anthropic")


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    return "\n\n".join(p.get("text", "") for p in content or []
                       if isinstance(p, dict) and p.get("type") == "text")


def _image_block(part: dict) -> dict:
    img = part.get("image_url")
    url = img.get("url") if isinstance(img, dict) else img
    if isinstance(url, str):
        match = _DATA_URL.match(url)
        if match:
            return {"type": "image", "source": {
                "type": "base64", "media_type": match.group(1),
                "data": match.group(2)}}
        if url.startswith(("http://", "https://")):
            return {"type": "image", "source": {"type": "url", "url": url}}
    raise BadRequestError(
        "Unsupported image_url for Anthropic: expected a base64 data: URL or "
        "an http(s) URL", provider="anthropic")


def _convert_content(content):
    if isinstance(content, str) or content is None:
        return content or ""
    blocks = []
    for part in content:
        if not isinstance(part, dict):
            continue
        kind = part.get("type")
        if kind == "image_url":
            blocks.append(_image_block(part))
        elif kind == "text":
            if part.get("text"):  # the API rejects empty text blocks
                blocks.append(part)
        else:
            blocks.append(part)  # native image (or other) blocks pass through
    return blocks


def _build_request(route: Route, messages: list[dict], params: dict) -> dict:
    system: list[str] = []
    turns: list[dict] = []
    for index, m in enumerate(messages):
        role = m.get("role")
        if role in ("system", "developer"):
            text = _text_of(m.get("content"))
            if text:
                system.append(text)
            continue
        content = _convert_content(m.get("content"))
        if role == "assistant" and not content:
            logger.debug("chameleon_llm: dropping empty assistant message at "
                         "index %d: the Anthropic API rejects empty content", index)
            continue
        turns.append({"role": role, "content": content})
    if not any(t["role"] == "user" for t in turns):
        raise BadRequestError(
            "Anthropic requires at least one user message", provider="anthropic")

    params = dict(params)
    fmt = params.pop("response_format", None)
    if fmt:
        if fmt.get("type") == "json_object":
            system.append(JSON_INSTRUCTION)
            logger.debug("chameleon_llm: approximating response_format json_object "
                         "with a system instruction")
        else:
            logger.warning("chameleon_llm: dropping parameter 'response_format' "
                           "(type=%r): the Anthropic adapter supports only "
                           "json_object", fmt.get("type"))
    stop = params.pop("stop", None)

    request: dict = {"model": route.model, "messages": turns,
                     "max_tokens": params.pop("max_tokens", None) or DEFAULT_MAX_TOKENS}
    if system:
        request["system"] = "\n\n".join(system)
    if stop is not None:
        request["stop_sequences"] = [stop] if isinstance(stop, str) else list(stop)
    request.update(params)  # temperature, top_p, top_k
    return request


def _to_completion(route: Route, resp) -> Completion:
    text = "".join(
        getattr(b, "text", "") or "" for b in getattr(resp, "content", None) or []
        if getattr(b, "type", None) == "text")
    finish = _FINISH_REASONS.get(getattr(resp, "stop_reason", None), "stop")
    usage = getattr(resp, "usage", None)
    prompt = getattr(usage, "input_tokens", 0) or 0
    completion = getattr(usage, "output_tokens", 0) or 0
    served = getattr(resp, "model", None)  # the model the API says it used
    return Completion(
        model=served if isinstance(served, str) and served else route.model,
        choices=[Choice(0, Message("assistant", text), finish)],
        usage=Usage(prompt, completion, prompt + completion),
        raw=resp)


# Sampling parameters and the installed SDK.
#
# With anthropic SDK 0.x, Messages.create() names temperature/top_p/top_k and
# they are passed through. With anthropic SDK 2.x, create() no longer names
# them, and the Messages API version that SDK speaks accepts no sampling
# parameter for any model (sending one in extra_body is answered with
# "400 ... Extra inputs are not permitted"). So a sampling parameter the
# installed create() does not name is dropped, never sent.
_SAMPLING_PARAMS = ("temperature", "top_p", "top_k")

# messages-resource class -> names its create() accepts (None = any name).
_CREATE_PARAMS: "weakref.WeakKeyDictionary[type, frozenset | None]" = (
    weakref.WeakKeyDictionary())

# Sampling parameter names already reported at WARNING in this process.
_WARNED_DROPS: set[str] = set()


def _reset_drop_warnings() -> None:
    """Forget which drops were reported (for tests)."""
    _WARNED_DROPS.clear()


def _create_params(resource_cls: type) -> frozenset | None:
    """Parameter names of ``resource_cls.create`` (cached per class). ``None``
    means it takes ``**kwargs`` or cannot be inspected."""
    if resource_cls not in _CREATE_PARAMS:
        try:
            params = inspect.signature(resource_cls.create).parameters
        except (AttributeError, TypeError, ValueError):
            names = None
        else:
            names = (None if any(p.kind is p.VAR_KEYWORD for p in params.values())
                     else frozenset(params))
        _CREATE_PARAMS[resource_cls] = names
    return _CREATE_PARAMS[resource_cls]


def sdk_accepts(name: str) -> bool:
    """Whether the installed anthropic SDK's ``messages.create`` takes ``name``."""
    from anthropic.resources.messages import Messages
    params = _create_params(Messages)
    return params is None or name in params


def _fit_to_sdk(request: dict, messages_resource) -> dict:
    """Drop the sampling parameters the installed SDK's create() does not name
    (see the note above). One WARNING per name per process, then DEBUG."""
    accepted = _create_params(type(messages_resource))
    if accepted is None:
        return request
    dropped = [k for k in _SAMPLING_PARAMS if k in request and k not in accepted]
    if not dropped:
        return request
    for name in dropped:
        level = logging.DEBUG if name in _WARNED_DROPS else logging.WARNING
        _WARNED_DROPS.add(name)
        logger.log(level, "chameleon_llm: dropping parameter '%s': the installed "
                   "anthropic SDK no longer accepts this sampling parameter, so "
                   "it is not sent", name)
    return {k: v for k, v in request.items() if k not in dropped}


def complete(route: Route, messages: list[dict], *, api_key: str | None,
             api_base: str | None, params: dict, timeout: float,
             max_retries: int) -> Completion:
    key = _resolve_key(api_key)
    request = _build_request(route, messages, params)

    kwargs = {"api_key": key, "timeout": timeout, "max_retries": max_retries}
    if api_base:
        kwargs["base_url"] = api_base
        warn_if_cleartext_key(key, api_base, "anthropic")
    client = anthropic.Anthropic(**kwargs)
    logger.debug("chameleon_llm anthropic: model=%s base_url=%s timeout=%s "
                 "max_retries=%s max_tokens=%s", route.model, api_base, timeout,
                 max_retries, request["max_tokens"])
    request = _fit_to_sdk(request, client.messages)
    try:
        resp = client.messages.create(**request)
    except Exception as exc:
        raise wrap_sdk_error(exc, "anthropic") from exc
    return _to_completion(route, resp)
