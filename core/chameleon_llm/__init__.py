"""chameleon_llm: a small vendored chat-completion shim (OpenAI, Anthropic, Gemini)."""

from .dispatch import completion
from .errors import (
    AuthError,
    BadRequestError,
    ConnectionError_,
    LLMError,
    MissingSDKError,
    RateLimitError,
    ServerError,
    TimeoutError_,
    UnsupportedRouteError,
)
from .routing import Route, resolve_route
from .types import Choice, Completion, Message, Usage

# This package's own version, separate from ImageAI's (core/constants.py).
# Kept as a tuple so release tooling that looks for a literal
# __version__ string does not take it for the application version.
__version_info__ = (0, 1, 0)
__version__ = ".".join(str(part) for part in __version_info__)

__all__ = [
    "completion", "Completion", "Choice", "Message", "Usage", "Route",
    "resolve_route", "LLMError", "AuthError", "RateLimitError",
    "BadRequestError", "TimeoutError_", "ConnectionError_", "ServerError",
    "UnsupportedRouteError", "MissingSDKError", "__version__",
]
