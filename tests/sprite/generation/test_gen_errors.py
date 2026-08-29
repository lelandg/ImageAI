"""Tests for core/sprite/generation/errors.py (design §1.3)."""
import logging

import pytest

from core.sprite.generation._common import emit, now_iso
from core.sprite.generation.errors import (
    ProviderError,
    QuotaExceeded,
    SafetyRefusal,
    SpriteGenerationError,
    classify_provider_error,
)


def test_base_error_carries_user_message_and_flags():
    err = SpriteGenerationError("Something failed", operation_id="op-9")
    assert str(err) == "Something failed"
    assert err.user_message == "Something failed"
    assert err.retryable is False
    assert err.operation_id == "op-9"


def test_quota_is_retryable_by_class_and_safety_is_not():
    assert QuotaExceeded("q").retryable is True
    assert SafetyRefusal("s").retryable is False
    assert ProviderError("p").retryable is False
    assert ProviderError("p", retryable=True).retryable is True


@pytest.mark.parametrize("message", [
    "Request blocked by Responsible AI (RAI) filters",
    "person_generation is not allowed for this request",
    "The prompt violates the content policy",
    "Blocked by safety settings: HARM_CATEGORY_DANGEROUS",
])
def test_classify_safety_messages(message):
    err = classify_provider_error(RuntimeError(message), provider="omni")
    assert isinstance(err, SafetyRefusal)
    assert err.retryable is False
    # The message names the other provider as an option.
    assert "Veo" in err.user_message


def test_safety_message_names_omni_when_veo_refused():
    err = classify_provider_error(RuntimeError("RAI filter triggered"), provider="veo")
    assert "Omni" in err.user_message


@pytest.mark.parametrize("message", [
    "429 Too Many Requests",
    "RESOURCE_EXHAUSTED: quota exceeded for this project",
    "Rate limit reached, retry later",
])
def test_classify_quota_messages(message):
    err = classify_provider_error(RuntimeError(message))
    assert isinstance(err, QuotaExceeded)
    assert err.retryable is True


def test_classify_status_code_attribute():
    exc = RuntimeError("boom")
    exc.status_code = 429
    assert isinstance(classify_provider_error(exc), QuotaExceeded)


@pytest.mark.parametrize("message", [
    "503 Service Unavailable",
    "Deadline exceeded: request timed out",
    "The model is overloaded, please try again",
])
def test_transient_provider_errors_are_retryable(message):
    err = classify_provider_error(RuntimeError(message))
    assert isinstance(err, ProviderError)
    assert err.retryable is True


def test_unknown_errors_are_non_retryable_provider_errors():
    err = classify_provider_error(ValueError("bad aspect ratio 4:3"))
    assert isinstance(err, ProviderError)
    assert err.retryable is False
    assert "bad aspect ratio" in err.user_message


def test_classify_passes_through_existing_errors_and_keeps_operation_id():
    original = QuotaExceeded("q", operation_id="op-1")
    assert classify_provider_error(original) is original
    err = classify_provider_error(RuntimeError("x"), operation_id="op-2")
    assert err.operation_id == "op-2"


def test_word_rai_does_not_match_inside_other_words():
    err = classify_provider_error(RuntimeError("terrain generation failed"))
    assert not isinstance(err, SafetyRefusal)


def test_emit_calls_sink_and_skips_duplicate_module_logger(caplog):
    logger = logging.getLogger("core.sprite.generation.test_emit")
    seen = []
    with caplog.at_level(logging.INFO, logger=logger.name):
        emit(logger, seen.append, "hello")
        emit(logger, logger.info, "again")
        emit(logger, None, "silent sink")
    assert seen == ["hello"]
    messages = [r.getMessage() for r in caplog.records]
    assert messages == ["hello", "again", "silent sink"]


def test_now_iso_is_second_precision():
    stamp = now_iso()
    assert "T" in stamp and len(stamp) == 19
