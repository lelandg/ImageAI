"""Gemini adapter (API key and Vertex AI): OpenAI-style messages in, Completion out."""

from __future__ import annotations

import base64
import binascii
import logging
import os
import re

from google import genai  # top-level on purpose: dispatch turns an ImportError into MissingSDKError
from google.genai import types

from .errors import AuthError, BadRequestError, wrap_sdk_error
from .routing import Route
from .types import Choice, Completion, Message, Usage

logger = logging.getLogger("chameleon_llm")

ACCEPTED_PARAMS = frozenset({
    "temperature", "top_p", "top_k", "max_tokens", "response_format", "seed",
    "stop", "vertex_project", "vertex_location",
})

# "global": recent Gemini models answer 404 NOT_FOUND in us-central1 (live run
# 2026-11-18) and are served from the global endpoint.
DEFAULT_VERTEX_LOCATION = "global"

# FinishReason names that mean the reply was blocked or withheld.
_CONTENT_FILTER = frozenset({
    "SAFETY", "RECITATION", "LANGUAGE", "BLOCKLIST", "PROHIBITED_CONTENT",
    "SPII", "IMAGE_SAFETY", "IMAGE_PROHIBITED_CONTENT", "IMAGE_RECITATION",
})
_DATA_URL = re.compile(r"^data:([^;,]+);base64,(.*)$", re.DOTALL)


def _resolve_key(api_key: str | None) -> str:
    key = (api_key or os.environ.get("GEMINI_API_KEY")
           or os.environ.get("GOOGLE_API_KEY"))
    if key:
        return key
    raise AuthError(
        "No Gemini API key: pass api_key or set GEMINI_API_KEY (or GOOGLE_API_KEY)",
        provider="gemini")


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    return "\n\n".join(p.get("text", "") for p in content or []
                       if isinstance(p, dict) and p.get("type") == "text")


def _image_part(part: dict):
    img = part.get("image_url")
    url = img.get("url") if isinstance(img, dict) else img
    if isinstance(url, str):
        match = _DATA_URL.match(url)
        if match:
            try:
                data = base64.b64decode(match.group(2), validate=True)
            except (binascii.Error, ValueError):
                raise BadRequestError("Invalid base64 in image_url data: URL",
                                      provider="gemini") from None
            return types.Part.from_bytes(data=data, mime_type=match.group(1))
        if url.startswith(("http://", "https://")):
            raise BadRequestError(
                "The Gemini adapter does not fetch remote images: pass a "
                "base64 data: URL instead of an http(s) URL", provider="gemini")
    raise BadRequestError(
        "Unsupported image_url for Gemini: expected a base64 data: URL",
        provider="gemini")


def _parts_of(content) -> list:
    if content is None:
        return []
    if isinstance(content, str):
        return [types.Part.from_text(text=content)] if content else []
    parts = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "image_url":
            parts.append(_image_part(part))
        elif part.get("type") == "text" and part.get("text"):  # API rejects empty text
            parts.append(types.Part.from_text(text=part["text"]))
    return parts


def _build_request(route: Route, messages: list[dict], params: dict) -> dict:
    system: list[str] = []
    contents: list = []
    for index, m in enumerate(messages):
        role = m.get("role")
        if role in ("system", "developer"):
            text = _text_of(m.get("content"))
            if text:
                system.append(text)
            continue
        parts = _parts_of(m.get("content"))
        if not parts:
            logger.debug("chameleon_llm: dropping empty %s message at index %d: "
                         "the Gemini API rejects empty content", role, index)
            continue
        contents.append(types.Content(
            role="model" if role == "assistant" else "user", parts=parts))
    if not any(c.role == "user" for c in contents):
        raise BadRequestError(
            "Gemini requires at least one user message", provider="gemini")

    config: dict = {}
    if system:
        config["system_instruction"] = "\n\n".join(system)
    for name in ("temperature", "top_p", "top_k", "seed"):
        if name in params:
            config[name] = params[name]
    if "max_tokens" in params:
        config["max_output_tokens"] = params["max_tokens"]
    if params.get("stop") is not None:
        stop = params["stop"]
        config["stop_sequences"] = [stop] if isinstance(stop, str) else list(stop)
    fmt = params.get("response_format")
    if fmt:
        if fmt.get("type") == "json_object":
            config["response_mime_type"] = "application/json"
        else:
            logger.warning("chameleon_llm: dropping parameter 'response_format' "
                           "(type=%r): the Gemini adapter supports only "
                           "json_object", fmt.get("type"))
    return {"model": route.model, "contents": contents,
            "config": types.GenerateContentConfig(**config)}


def _build_client_kwargs(route: Route, api_key: str | None, api_base: str | None,
                         params: dict, timeout: float, max_retries: int) -> dict:
    # HttpOptions.timeout is in milliseconds; retry attempts include the first try.
    kwargs: dict = {"http_options": types.HttpOptions(
        timeout=int(timeout * 1000),
        retry_options=types.HttpRetryOptions(attempts=max_retries + 1))}
    if api_base:
        logger.warning("chameleon_llm: dropping parameter 'api_base': the Gemini "
                       "adapter does not support a custom endpoint")
    if route.route == "vertex_ai":
        if api_key:
            logger.warning("chameleon_llm: dropping parameter 'api_key': the "
                           "vertex_ai route uses Google Cloud login")
        kwargs.update(
            vertexai=True,
            project=(params.get("vertex_project")
                     or os.environ.get("GOOGLE_CLOUD_PROJECT") or None),
            location=(params.get("vertex_location")
                      or os.environ.get("GOOGLE_CLOUD_LOCATION")
                      or DEFAULT_VERTEX_LOCATION))
    else:
        ignored = [n for n in ("vertex_project", "vertex_location") if n in params]
        if ignored:
            logger.warning("chameleon_llm: dropping parameter(s) %s: only the "
                           "vertex_ai route uses them", ", ".join(ignored))
        kwargs["api_key"] = _resolve_key(api_key)
    return kwargs


def _finish_name(reason) -> str | None:
    if reason is None:
        return None
    return getattr(reason, "name", None) or str(reason)


def _to_completion(route: Route, resp) -> Completion:
    candidates = getattr(resp, "candidates", None) or []
    text = ""
    finish = "content_filter"
    if candidates:
        cand = candidates[0]
        parts = getattr(getattr(cand, "content", None), "parts", None) or []
        text = "".join(getattr(p, "text", None) or "" for p in parts)
        name = _finish_name(getattr(cand, "finish_reason", None))
        if name == "MAX_TOKENS":
            finish = "length"
        elif name in _CONTENT_FILTER:
            finish = "content_filter"
        elif name == "STOP" or parts:
            finish = "stop"
        else:  # no parts and no known reason: treat the reply as withheld
            finish = "content_filter"
    usage = getattr(resp, "usage_metadata", None)
    prompt = getattr(usage, "prompt_token_count", 0) or 0
    completion = getattr(usage, "candidates_token_count", 0) or 0
    total = getattr(usage, "total_token_count", 0) or (prompt + completion)
    served = getattr(resp, "model_version", None)  # the model the API says it used
    return Completion(
        model=served if isinstance(served, str) and served else route.model,
        choices=[Choice(0, Message("assistant", text), finish)],
        usage=Usage(prompt, completion, total),
        raw=resp)


def complete(route: Route, messages: list[dict], *, api_key: str | None,
             api_base: str | None, params: dict, timeout: float,
             max_retries: int) -> Completion:
    request = _build_request(route, messages, params)
    client_kwargs = _build_client_kwargs(
        route, api_key, api_base, params, timeout, max_retries)
    client = genai.Client(**client_kwargs)  # looked up at call time (test patch)
    logger.debug("chameleon_llm gemini: route=%s model=%s timeout=%s "
                 "max_retries=%s", route.route, route.model, timeout, max_retries)
    try:
        resp = client.models.generate_content(**request)
    except Exception as exc:
        raise wrap_sdk_error(exc, "gemini") from exc
    return _to_completion(route, resp)
