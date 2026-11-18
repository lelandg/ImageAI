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
