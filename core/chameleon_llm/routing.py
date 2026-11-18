"""Split a ``prefix/model`` string into an adapter route and a bare model id."""

from __future__ import annotations

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


def resolve_route(model: str, api_base: str | None = None) -> Route:
    """Resolve ``model`` to a Route. Only the first segment can be a prefix."""
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
    return Route("openai", "openai", model)
