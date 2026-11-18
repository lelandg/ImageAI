import pytest

from core.chameleon_llm.errors import (
    AuthError, BadRequestError, ConnectionError_, LLMError, RateLimitError,
    ServerError, TimeoutError_, wrap_sdk_error,
)


class _StatusExc(Exception):
    def __init__(self, msg, status_code):
        super().__init__(msg)
        self.status_code = status_code


@pytest.mark.parametrize("status,cls", [
    (401, AuthError), (403, AuthError), (429, RateLimitError),
    (400, BadRequestError), (404, BadRequestError), (409, BadRequestError),
    (422, BadRequestError), (500, ServerError), (503, ServerError),
])
def test_wrap_by_status(status, cls):
    err = wrap_sdk_error(_StatusExc("boom", status), "openai")
    assert type(err) is cls
    assert err.status_code == status
    assert err.provider == "openai"


def test_wrap_timeout_by_class_name():
    class APITimeoutError(Exception):
        pass
    assert type(wrap_sdk_error(APITimeoutError("slow"), "anthropic")) is TimeoutError_


def test_wrap_connection_by_class_name():
    class APIConnectionError(Exception):
        pass
    err = wrap_sdk_error(APIConnectionError("down"), "gemini")
    assert type(err) is ConnectionError_
    assert err.status_code is None


def test_wrap_unknown_is_plain_llm_error():
    err = wrap_sdk_error(ValueError("odd"), "openai")
    assert type(err) is LLMError


def test_wrapped_message_keeps_original_text_and_type_name():
    err = wrap_sdk_error(_StatusExc("the original text", 401), "openai")
    assert str(err) == "_StatusExc: the original text"


def test_all_errors_are_exceptions():
    assert issubclass(LLMError, Exception)


# --- I4: httpx transport errors (google-genai lets them propagate) ----------

httpx = pytest.importorskip("httpx")


@pytest.mark.parametrize("exc,cls", [
    (httpx.ConnectError("refused"), ConnectionError_),
    (httpx.ReadError("reset"), ConnectionError_),
    (httpx.RemoteProtocolError("closed"), ConnectionError_),
    (httpx.ReadTimeout("slow"), TimeoutError_),
    (httpx.ConnectTimeout("slow"), TimeoutError_),
])
def test_wrap_httpx_transport_errors(exc, cls):
    err = wrap_sdk_error(exc, "gemini")
    assert type(err) is cls
    assert err.status_code is None


@pytest.mark.parametrize("name", ["NetworkError", "ProtocolError", "ConnectFailed"])
def test_wrap_connection_family_by_class_name(name):
    exc = type(name, (Exception,), {})("x")
    assert type(wrap_sdk_error(exc, "gemini")) is ConnectionError_


# --- Addendum: classify by class name along the MRO (httpx, httpx2, SDKs) ----
# Local stand-ins shaped like httpx/httpx2's hierarchy; no library needed.

class TransportError(Exception):
    pass


class NetworkError(TransportError):
    pass


class ReadError(NetworkError):
    pass


class TimeoutException(TransportError):
    pass


class ReadTimeout(TimeoutException):
    pass


class ProtocolError(TransportError):
    pass


class RemoteProtocolError(ProtocolError):
    pass


class WriteError(Exception):
    pass


class CloseError(Exception):
    pass


class SDKTransportFailure(TransportError):  # name alone says nothing
    pass


@pytest.mark.parametrize("exc,cls", [
    (ReadError("reset"), ConnectionError_),
    (ReadTimeout("slow"), TimeoutError_),
    (RemoteProtocolError("closed"), ConnectionError_),
    (SDKTransportFailure("x"), ConnectionError_),
    (WriteError("x"), ConnectionError_),
    (CloseError("x"), ConnectionError_),
])
def test_wrap_by_class_name_along_mro(exc, cls):
    err = wrap_sdk_error(exc, "gemini")
    assert type(err) is cls
    assert err.status_code is None


def test_wrap_unrelated_value_error_stays_plain():
    assert type(wrap_sdk_error(ValueError("odd"), "gemini")) is LLMError


def test_status_code_wins_over_a_connect_name():
    class APIConnectionStatusError(Exception):
        status_code = 429
    err = wrap_sdk_error(APIConnectionStatusError("busy"), "openai")
    assert type(err) is RateLimitError
    assert err.status_code == 429
