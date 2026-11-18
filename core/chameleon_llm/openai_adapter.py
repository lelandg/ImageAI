"""OpenAI-compatible adapter (OpenAI, Ollama, LM Studio): chat-completions path."""

from __future__ import annotations

import logging
import os

import openai  # top-level on purpose: dispatch turns an ImportError here into MissingSDKError

from .errors import AuthError, BadRequestError, wrap_sdk_error
from .routing import Route
from .types import Choice, Completion, Message, Usage

logger = logging.getLogger("chameleon_llm")

ACCEPTED_PARAMS = frozenset({
    "temperature", "top_p", "top_k", "max_tokens", "max_completion_tokens",
    "reasoning_effort", "verbosity", "response_format", "seed", "stop",
})

_LOCAL_ROUTES = frozenset({"ollama", "lm_studio"})
_PLACEHOLDER_KEY = "not-needed"
_DEFAULT_OLLAMA_BASE = "http://localhost:11434"


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
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    if route.route in _LOCAL_ROUTES or base_url:
        return _PLACEHOLDER_KEY
    raise AuthError(
        "No OpenAI API key: pass api_key or set OPENAI_API_KEY", provider="openai")


def _build_request(route: Route, messages: list[dict], params: dict,
                   base_url: str | None) -> dict:
    request = {"model": route.model, "messages": messages}
    params = dict(params)
    top_k = params.pop("top_k", None)
    request.update(params)
    if top_k is not None:
        if base_url:
            request["extra_body"] = {"top_k": top_k}
        else:
            logger.warning(
                "chameleon_llm: dropping parameter 'top_k': the OpenAI cloud "
                "API does not accept it")
    return request


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
        model=route.model,
        choices=choices,
        usage=Usage(
            getattr(usage, "prompt_tokens", 0) or 0,
            getattr(usage, "completion_tokens", 0) or 0,
            getattr(usage, "total_tokens", 0) or 0),
        raw=resp)


def complete(route: Route, messages: list[dict], *, api_key: str | None,
             api_base: str | None, params: dict, timeout: float,
             max_retries: int) -> Completion:
    base_url = _resolve_base_url(route, api_base)
    key = _resolve_key(route, api_key, base_url)
    request = _build_request(route, messages, params, base_url)

    client = openai.OpenAI(api_key=key, base_url=base_url, timeout=timeout,
                           max_retries=max_retries)
    logger.debug("chameleon_llm openai chat: route=%s model=%s base_url=%s "
                 "timeout=%s max_retries=%s", route.route, route.model,
                 base_url, timeout, max_retries)
    try:
        resp = client.chat.completions.create(**request)
    except Exception as exc:
        raise wrap_sdk_error(exc, "openai") from exc
    return _to_completion(route, resp)
