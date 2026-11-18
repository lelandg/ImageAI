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

__version__ = "0.1.0"

__all__ = [
    "completion", "Completion", "Choice", "Message", "Usage", "Route",
    "resolve_route", "LLMError", "AuthError", "RateLimitError",
    "BadRequestError", "TimeoutError_", "ConnectionError_", "ServerError",
    "UnsupportedRouteError", "MissingSDKError", "__version__",
]
