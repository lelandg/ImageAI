"""Public ``completion`` entry point: route, filter params, call the adapter."""

from __future__ import annotations

import importlib
import logging

from .errors import MissingSDKError
from .routing import resolve_route
from .types import Completion

logger = logging.getLogger("chameleon_llm")

DEFAULT_TIMEOUT = 600

# Top-level module of a missing SDK -> pip package to install.
_SDK_PIP_NAMES = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "google-genai",
}


def _load_adapter(adapter: str):
    try:
        return importlib.import_module(f"{__package__}.{adapter}_adapter")
    except ImportError as exc:
        missing = (getattr(exc, "name", None) or "").split(".")[0]
        pip_name = _SDK_PIP_NAMES.get(missing)
        if pip_name is None:
            raise
        raise MissingSDKError(
            f"The '{pip_name}' package is required for the '{adapter}' route; "
            f"install it with: pip install {pip_name}",
            provider=adapter,
        ) from exc


def completion(*, model: str, messages: list[dict], api_key: str | None = None,
               api_base: str | None = None, timeout: float | None = None,
               max_retries: int = 0, **params) -> Completion:
    """Run a chat completion through the adapter chosen by the model prefix."""
    route = resolve_route(model, api_base)
    module = _load_adapter(route.adapter)

    params = {k: v for k, v in params.items() if v is not None}
    accepted = module.ACCEPTED_PARAMS
    dropped = sorted(k for k in params if k not in accepted)
    if dropped:
        logger.warning(
            "chameleon_llm: dropping parameter(s) not accepted by the %s adapter: %s",
            route.adapter, ", ".join(dropped))
        params = {k: v for k, v in params.items() if k in accepted}

    if timeout is None:
        timeout = DEFAULT_TIMEOUT

    logger.debug("chameleon_llm request: route=%s model=%s params=%s",
                 route.route, route.model, sorted(params))
    return module.complete(
        route, messages, api_key=api_key, api_base=api_base, params=params,
        timeout=timeout, max_retries=max_retries)
