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


# Class names (anywhere in the MRO) that mark a transport failure. They match
# httpx and httpx2 alike, and SDK subclasses of either, without importing them.
_TIMEOUT_NAMES = frozenset({"TimeoutException"})
_CONNECTION_NAMES = frozenset({
    "TransportError", "NetworkError", "ProtocolError",
    "ReadError", "WriteError", "CloseError",
})
_CONNECTION_WORDS = ("connect", "network", "protocol")


def _transport_class(exc: Exception) -> type[LLMError]:
    """Classify an error that carries no HTTP status (timeouts, dropped links).

    The SDKs let their HTTP library's errors (httpx at older versions, httpx2
    at the versions requirements.txt installs) propagate unwrapped, e.g.
    ConnectError, ReadError, RemoteProtocolError, ReadTimeout. The decision
    is made by class NAME along ``type(exc).__mro__``, so it does not depend
    on which library raised; the guarded isinstance checks are a backstop.
    """
    names = [klass.__name__ for klass in type(exc).__mro__]
    if any(n in _TIMEOUT_NAMES or "timeout" in n.lower() for n in names):
        return TimeoutError_
    if any(n in _CONNECTION_NAMES
           or any(word in n.lower() for word in _CONNECTION_WORDS)
           for n in names):
        return ConnectionError_
    for module_name in ("httpx", "httpx2"):
        try:
            module = __import__(module_name)
        except ImportError:
            continue
        timeout_cls = getattr(module, "TimeoutException", None)
        transport_cls = getattr(module, "TransportError", None)
        if isinstance(timeout_cls, type) and isinstance(exc, timeout_cls):
            return TimeoutError_
        if isinstance(transport_cls, type) and isinstance(exc, transport_cls):
            return ConnectionError_
    return LLMError
