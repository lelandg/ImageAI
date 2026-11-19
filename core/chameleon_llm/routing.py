"""Split a ``prefix/model`` string into an adapter route and a bare model id."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .errors import BadRequestError, UnsupportedRouteError


@dataclass(frozen=True)
class Route:
    adapter: str  # "openai" | "anthropic" | "gemini"
    route: str    # "openai" | "ollama" | "lm_studio" | "anthropic" | "gemini" | "vertex_ai"
    model: str


# prefix -> (adapter, route)
_PREFIXES: dict[str, tuple[str, str]] = {
    "openai": ("openai", "openai"),
    "ollama": ("openai", "ollama"),
    "ollama_chat": ("openai", "ollama"),
    "lm_studio": ("openai", "lm_studio"),
    "anthropic": ("anthropic", "anthropic"),
    "gemini": ("gemini", "gemini"),
    "vertex_ai": ("gemini", "vertex_ai"),
}
_UNSUPPORTED = frozenset({"azure", "bedrock"})

_GEMINI_HINT = "'gemini/' (API key) or 'vertex_ai/' (Google Cloud login)"
# Lower-cased first segments that look like a route but are not one -> the
# prefix to use instead. Without an api_base they would reach OpenAI.
_MISNAMED_PREFIXES: dict[str, str] = {
    "claude": "'anthropic/'",
    "google": _GEMINI_HINT,
    "vertex": "'vertex_ai/'",
    "vertexai": "'vertex_ai/'",
    "lmstudio": "'lm_studio/' (with an api_base)",
    "lm-studio": "'lm_studio/' (with an api_base)",
}
# Model families that never live on the OpenAI route -> the prefix to add.
_BARE_FAMILIES: dict[str, str] = {
    "claude": "'anthropic/'",
    "gemini": _GEMINI_HINT,
}


def _refuse_silent_misroute(model: str, head: str, sep: str) -> None:
    """Raise when an id with no route prefix (and no api_base) would
    silently reach OpenAI. ``head``/``sep`` come from ``model.partition("/")``
    and ``head`` is known not to be a route prefix."""
    if sep:
        lowered = head.lower()
        hint = _MISNAMED_PREFIXES.get(lowered)
        if hint is None and lowered in _PREFIXES:  # a known prefix, wrong case
            hint = f"'{lowered}/'"
        if hint is not None:
            raise BadRequestError(
                f"'{head}/' in model '{model}' is not a chameleon_llm route; "
                f"use {hint}")
    for family, hint in _BARE_FAMILIES.items():
        if model.lower().startswith(family):
            raise BadRequestError(
                f"Model '{model}' has no route prefix and would be sent to "
                f"OpenAI; add {hint} (chameleon_llm does not guess a "
                f"provider from a model name)")


def resolve_route(model: str, api_base: str | None = None) -> Route:
    """Resolve ``model`` to a Route. Only the first segment can be a prefix.

    Without ``api_base`` (argument or a non-empty ``OPENAI_API_BASE``
    environment variable), an id that would silently reach OpenAI (a bare
    ``claude*``/``gemini*`` id, or a misnamed or miscased prefix such as
    ``google/`` or ``Anthropic/``) raises ``BadRequestError``. With an
    ``api_base`` any name is accepted: a local server may host any model.
    """
    if not model or not model.strip():
        raise BadRequestError("model must not be empty")
    model = model.strip()
    head, sep, rest = model.partition("/")
    if sep:
        if head in _UNSUPPORTED:
            raise UnsupportedRouteError(
                f"Route '{head}/' is not supported by chameleon_llm (model '{model}')")
        if head in _PREFIXES:
            if not rest.strip():
                raise BadRequestError(f"model id missing after '{head}/'")
            adapter, route = _PREFIXES[head]
            return Route(adapter, route, rest)
    # The OpenAI adapter also honors OPENAI_API_BASE, so a base URL from the
    # environment counts here too: the call then goes to that server.
    if not (api_base or os.environ.get("OPENAI_API_BASE")):
        _refuse_silent_misroute(model, head, sep)
    return Route("openai", "openai", model)
