"""OpenAI-compatible adapter (OpenAI, Ollama, LM Studio): chat-completions and Responses paths."""

from __future__ import annotations

import logging
import os
import re

import openai  # top-level on purpose: dispatch turns an ImportError here into MissingSDKError

from .endpoint import display_url, warn_if_cleartext_key
from .errors import (
    AuthError, BadRequestError, LLMError, RateLimitError, ServerError,
    TimeoutError_, wrap_sdk_error,
)
from .routing import Route
from .types import Choice, Completion, Message, Usage

logger = logging.getLogger("chameleon_llm")

ACCEPTED_PARAMS = frozenset({
    "temperature", "top_p", "top_k", "max_tokens", "max_completion_tokens",
    "reasoning_effort", "verbosity", "response_format", "seed", "stop",
})

# Models served only by the Responses API (patterns, matched on the bare id).
RESPONSES_ONLY_PATTERNS: tuple[str, ...] = (
    r"^o\d+-pro(-|$)",
    r"^gpt-\d+(\.\d+)*-pro(-|$)",
)

_LOCAL_ROUTES = frozenset({"ollama", "lm_studio"})
_PLACEHOLDER_KEY = "not-needed"
_DEFAULT_OLLAMA_BASE = "http://localhost:11434"


def uses_responses_api(model: str) -> bool:
    return any(re.search(p, model) for p in RESPONSES_ONLY_PATTERNS)


def _resolve_base_url(route: Route, api_base: str | None) -> str | None:
    if route.route == "ollama":
        base = (api_base or os.environ.get("OLLAMA_API_BASE")
                or _DEFAULT_OLLAMA_BASE).rstrip("/")
        return base if base.endswith("/v1") else base + "/v1"
    if route.route == "lm_studio":
        base = api_base or os.environ.get("OPENAI_API_BASE")
        if not base:
            raise BadRequestError(
                "The lm_studio route needs a base URL: pass api_base or set "
                "OPENAI_API_BASE", provider="openai")
        return base
    return api_base or os.environ.get("OPENAI_API_BASE") or None


def _resolve_key(route: Route, api_key: str | None, base_url: str | None) -> str:
    if route.route in _LOCAL_ROUTES or base_url:
        # A local or compatible endpoint never receives the cloud key from the
        # environment: only a key the caller passed for it, else a placeholder.
        return api_key or _PLACEHOLDER_KEY
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    raise AuthError(
        "No OpenAI API key: pass api_key or set OPENAI_API_KEY", provider="openai")


def _build_request(route: Route, messages: list[dict], params: dict,
                   base_url: str | None) -> dict:
    request = {"model": route.model, "messages": messages}
    params = dict(params)
    top_k = params.pop("top_k", None)
    request.update(params)
    if top_k is not None:
        if route.route == "ollama":
            # Ollama's OpenAI-compatible endpoint has no top_k field; in
            # extra_body it would be ignored without a trace.
            logger.warning(
                "chameleon_llm: dropping parameter 'top_k': Ollama's "
                "OpenAI-compatible endpoint does not accept it")
        elif base_url:
            request["extra_body"] = {"top_k": top_k}
        else:
            logger.warning(
                "chameleon_llm: dropping parameter 'top_k': the OpenAI cloud "
                "API does not accept it")
    return request


def _served_model(route: Route, resp) -> str:
    """The model the provider reports it used, else the requested id."""
    served = getattr(resp, "model", None)
    return served if isinstance(served, str) and served else route.model


def _to_completion(route: Route, resp) -> Completion:
    choices = []
    for i, ch in enumerate(getattr(resp, "choices", None) or []):
        msg = getattr(ch, "message", None)
        content = getattr(msg, "content", None)
        choices.append(Choice(
            index=getattr(ch, "index", i) or 0,
            message=Message("assistant", content if isinstance(content, str) else ""),
            finish_reason=getattr(ch, "finish_reason", None) or "stop"))
    if not choices:
        choices = [Choice(0, Message("assistant", ""), "stop")]
    usage = getattr(resp, "usage", None)
    return Completion(
        model=_served_model(route, resp),
        choices=choices,
        usage=Usage(
            getattr(usage, "prompt_tokens", 0) or 0,
            getattr(usage, "completion_tokens", 0) or 0,
            getattr(usage, "total_tokens", 0) or 0),
        raw=resp)


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    return "\n\n".join(p.get("text", "") for p in content or []
                       if isinstance(p, dict) and p.get("type") == "text")


def _response_part(part) -> dict:
    if part.get("type") == "image_url":
        img = part.get("image_url")
        url = img.get("url") if isinstance(img, dict) else img
        detail = (img.get("detail") if isinstance(img, dict) else None) or "auto"
        return {"type": "input_image", "image_url": url, "detail": detail}
    return {"type": "input_text", "text": part.get("text", "")}


def _build_responses_request(route: Route, messages: list[dict],
                             params: dict) -> dict:
    instructions, items = [], []
    for m in messages:
        role, content = m.get("role"), m.get("content")
        if role in ("system", "developer"):
            instructions.append(_text_of(content))
            continue
        if role == "assistant":  # EasyInputMessage allows only plain text here
            items.append({"role": role, "content": _text_of(content)})
            continue
        parts = ([{"type": "text", "text": content}] if isinstance(content, str)
                 else list(content or []))
        parts = [_response_part(p) for p in parts if p
                 and not (p.get("type") == "text" and not p.get("text"))]
        if parts:
            items.append({"role": role, "content": parts})
    request: dict = {"model": route.model, "input": items}
    if instructions:
        request["instructions"] = "\n\n".join(t for t in instructions if t)
    params = dict(params)
    for name in ("seed", "stop", "top_k"):
        if params.pop(name, None) is not None:
            logger.warning("chameleon_llm: dropping parameter '%s': the OpenAI "
                           "Responses API does not accept it", name)
    cap = params.pop("max_tokens", None)
    cap = params.pop("max_completion_tokens", None) or cap
    if cap is not None:
        request["max_output_tokens"] = cap
    effort = params.pop("reasoning_effort", None)
    if effort is not None:
        request["reasoning"] = {"effort": effort}
    text: dict = {}
    verbosity = params.pop("verbosity", None)
    if verbosity is not None:
        text["verbosity"] = verbosity
    fmt = params.pop("response_format", None)
    if fmt:
        if fmt.get("type") == "json_schema" and "json_schema" in fmt:
            fmt = {"type": "json_schema", **fmt["json_schema"]}
        text["format"] = fmt
    if text:
        request["text"] = text
    request.update(params)  # temperature, top_p
    return request


def _failed_response_error(status: str, resp) -> LLMError:
    """The error for a Responses reply whose status is failed or cancelled.

    HTTP 200 carries these, so no SDK exception is raised; the class comes
    from ``resp.error.code`` (ResponseError in the SDK)."""
    err = getattr(resp, "error", None)
    code = getattr(err, "code", None)
    message = getattr(err, "message", None)
    code = code if isinstance(code, str) and code else None
    cls: type[LLMError]
    if code is None:
        cls = LLMError
    elif code == "rate_limit_exceeded":
        cls = RateLimitError
    elif code == "server_error":
        cls = ServerError
    elif "timeout" in code:
        cls = TimeoutError_
    else:  # invalid_prompt, invalid_image, image_too_large, ...
        cls = BadRequestError
    detail = f"status={status}" + (f", code={code}" if code else "")
    text = f"OpenAI Responses request did not complete ({detail})"
    if isinstance(message, str) and message:
        text += f": {message}"
    return cls(text, provider="openai")


def _responses_to_completion(route: Route, resp) -> Completion:
    text = getattr(resp, "output_text", None)
    status = getattr(resp, "status", None)
    if status in ("failed", "cancelled"):
        raise _failed_response_error(status, resp)
    if status == "incomplete":
        reason = getattr(getattr(resp, "incomplete_details", None), "reason", None)
        finish = "content_filter" if reason == "content_filter" else "length"
    else:
        finish = "stop"
    usage = getattr(resp, "usage", None)
    prompt = getattr(usage, "input_tokens", 0) or 0
    completion = getattr(usage, "output_tokens", 0) or 0
    return Completion(
        model=_served_model(route, resp),
        choices=[Choice(0, Message("assistant", text if isinstance(text, str) else ""),
                        finish)],
        usage=Usage(prompt, completion,
                    getattr(usage, "total_tokens", 0) or prompt + completion),
        raw=resp)


def complete(route: Route, messages: list[dict], *, api_key: str | None,
             api_base: str | None, params: dict, timeout: float,
             max_retries: int) -> Completion:
    base_url = _resolve_base_url(route, api_base)
    key = _resolve_key(route, api_key, base_url)
    warn_if_cleartext_key(None if key == _PLACEHOLDER_KEY else key, base_url,
                          "openai")
    use_responses = not base_url and uses_responses_api(route.model)
    if use_responses:
        request = _build_responses_request(route, messages, params)
    else:
        request = _build_request(route, messages, params, base_url)

    client = openai.OpenAI(api_key=key, base_url=base_url, timeout=timeout,
                           max_retries=max_retries)
    logger.debug("chameleon_llm openai %s: route=%s model=%s base_url=%s "
                 "timeout=%s max_retries=%s",
                 "responses" if use_responses else "chat", route.route,
                 route.model, display_url(base_url), timeout, max_retries)
    if use_responses:
        return _send_responses(client, route, request)
    try:
        resp = client.chat.completions.create(**request)
    except Exception as exc:
        error = wrap_sdk_error(exc, "openai")
        if not base_url and _points_at_responses(error):
            logger.warning(
                "chameleon_llm: model '%s' rejected chat completions and asked for "
                "the Responses API; retrying once on the Responses path. Add it to "
                "openai_adapter.RESPONSES_ONLY_PATTERNS so the pattern list learns it",
                route.model)
            return _send_responses(
                client, route, _build_responses_request(route, messages, params),
                first_error=error)
        if "max_tokens" in request and _wants_completion_tokens(error):
            logger.warning(
                "chameleon_llm: model '%s' rejected max_tokens and asked for "
                "max_completion_tokens; retrying once with it renamed. Its "
                "parameter rule in core/llm_params.py should learn the model",
                route.model)
            renamed = dict(request)
            renamed["max_completion_tokens"] = renamed.pop("max_tokens")
            try:
                resp = client.chat.completions.create(**renamed)
            except Exception as retry_exc:
                raise _retry_error(retry_exc, error) from retry_exc
            return _to_completion(route, resp)
        raise error from exc
    return _to_completion(route, resp)


def _points_at_responses(error) -> bool:
    """True for a 400/404 whose message says to use the Responses API."""
    text = str(error).lower()
    return (error.status_code in (400, 404)
            and ("v1/responses" in text or "responses api" in text))


def _wants_completion_tokens(error) -> bool:
    """True for a 400 saying max_tokens is unsupported, use max_completion_tokens."""
    text = str(error).lower()
    return (error.status_code == 400 and "max_tokens" in text
            and "max_completion_tokens" in text
            and ("unsupported" in text or "not supported" in text))


def _retry_error(retry_exc: Exception, first_error):
    """The retry's error, with the first attempt's error text appended."""
    error = wrap_sdk_error(retry_exc, "openai")
    return type(error)(
        f"{error} (single retry; the first attempt failed with: {first_error})",
        provider=error.provider, status_code=error.status_code)


def _send_responses(client, route: Route, request: dict,
                    first_error=None) -> Completion:
    try:
        resp = client.responses.create(**request)
    except Exception as exc:
        if first_error is not None:
            raise _retry_error(exc, first_error) from exc
        raise wrap_sdk_error(exc, "openai") from exc
    return _responses_to_completion(route, resp)
