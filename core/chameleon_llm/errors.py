"""Error family raised by chameleon_llm."""

from __future__ import annotations


class LLMError(Exception):
    """Base class. Carries the provider name and HTTP status when known."""

    def __init__(self, message: str = "", *, provider: str = "chameleon_llm",
                 status_code: int | None = None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class AuthError(LLMError):
    pass


class RateLimitError(LLMError):
    pass


class BadRequestError(LLMError):
    pass


class TimeoutError_(LLMError):
    pass


class ConnectionError_(LLMError):
    pass


class ServerError(LLMError):
    pass


class UnsupportedRouteError(LLMError):
    pass


class MissingSDKError(LLMError):
    pass


def _status_of(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if status is None:
        status = getattr(exc, "code", None)  # google.genai.errors.APIError
    return status if isinstance(status, int) else None


def wrap_sdk_error(exc: Exception, provider: str) -> LLMError:
    """Map an SDK exception to the LLMError family. Caller raises ``from exc``."""
    message = f"{type(exc).__name__}: {exc}"
    status = _status_of(exc)
    cls: type[LLMError]
    if status is not None:
        if status in (401, 403):
            cls = AuthError
        elif status == 429:
            cls = RateLimitError
        elif status in (400, 404, 409, 422):
            cls = BadRequestError
        elif status >= 500:
            cls = ServerError
        else:
            cls = LLMError
    else:
        cls = _transport_class(exc)
    return cls(message, provider=provider, status_code=status)


def _transport_class(exc: Exception) -> type[LLMError]:
    """Classify an error that carries no HTTP status (timeouts, dropped links).

    google-genai lets httpx errors (ConnectError, ReadError,
    RemoteProtocolError, ReadTimeout) propagate unwrapped, so httpx's own
    hierarchy is checked first; httpx is imported lazily and is optional.
    """
    try:
        import httpx
    except ImportError:  # pragma: no cover - httpx ships with every SDK we use
        httpx = None
    if httpx is not None:
        if isinstance(exc, httpx.TimeoutException):
            return TimeoutError_
        if isinstance(exc, httpx.TransportError):
            return ConnectionError_
    name = type(exc).__name__.lower()
    if "timeout" in name:
        return TimeoutError_
    if any(word in name for word in ("connect", "network", "protocol")):
        return ConnectionError_
    return LLMError
