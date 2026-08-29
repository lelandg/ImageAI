"""Failure classes for the sprite generation route (design §1.3).

Every error carries a ``user_message`` that the GUI and the CLI show, and a
``retryable`` flag that the queue reads. ``classify_provider_error`` maps a
raw provider exception onto one of these classes by message and status code.
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class SpriteGenerationError(Exception):
    """Base class for generation failures with a user-facing message."""

    retryable: bool = False

    def __init__(self, user_message: str, *, retryable: Optional[bool] = None,
                 operation_id: Optional[str] = None) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        if retryable is not None:
            self.retryable = retryable
        self.operation_id = operation_id


class SafetyRefusal(SpriteGenerationError):
    """RAI / safety / person_generation refusal. Never retried."""

    retryable = False


class QuotaExceeded(SpriteGenerationError):
    """429 / RESOURCE_EXHAUSTED / rate limit. Retried with backoff."""

    retryable = True


class ProviderError(SpriteGenerationError):
    """Any other provider failure. ``retryable`` is True for transient codes."""

    retryable = False


_SAFETY_PATTERNS = (
    r"\brai\b", r"responsible ai", r"safety", r"person_generation",
    r"person generation", r"content policy", r"violat", r"harm_category",
    r"usage guidelines", r"prohibited", r"blocked",
)
_QUOTA_PATTERNS = (
    r"\b429\b", r"resource_exhausted", r"resource exhausted", r"quota",
    r"rate limit", r"rate_limit", r"too many requests",
)
_TRANSIENT_PATTERNS = (
    r"\b50[0234]\b", r"\b529\b", r"timeout", r"timed out", r"unavailable",
    r"overloaded", r"connection", r"deadline", r"internal error",
    r"try again", r"temporarily",
)

_OTHER_PROVIDER = {"omni": "Veo", "veo": "Gemini Omni"}


def _status_code(exc: BaseException) -> Optional[int]:
    for attr in ("status_code", "code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    return None


def _matches(text: str, patterns) -> bool:
    return any(re.search(p, text) for p in patterns)


def classify_provider_error(exc: BaseException, *, provider: str = "",
                            operation_id: Optional[str] = None) -> SpriteGenerationError:
    """Map a provider exception onto a ``SpriteGenerationError`` subclass.

    Order: an existing ``SpriteGenerationError`` passes through; then safety
    refusal; then quota; then transient provider errors (retryable); then a
    non-retryable ``ProviderError``. The full exception text is logged.
    """
    if isinstance(exc, SpriteGenerationError):
        return exc

    raw = f"{type(exc).__name__}: {exc}"
    text = raw.lower()
    code = _status_code(exc)
    logger.error("Provider error (%s): %s", provider or "unknown", raw)

    if _matches(text, _SAFETY_PATTERNS):
        other = _OTHER_PROVIDER.get(provider.lower(), "the other video provider")
        message = (f"The provider refused this request for safety reasons: {exc}. "
                   f"Try {other}, or change the character image or the prompt.")
        return SafetyRefusal(message, operation_id=operation_id)

    if code == 429 or _matches(text, _QUOTA_PATTERNS):
        message = f"The provider quota or rate limit was reached: {exc}. The queue retries."
        return QuotaExceeded(message, operation_id=operation_id)

    if (code is not None and code >= 500) or _matches(text, _TRANSIENT_PATTERNS):
        message = f"The provider had a temporary failure: {exc}. The queue retries."
        return ProviderError(message, retryable=True, operation_id=operation_id)

    return ProviderError(f"The provider returned an error: {exc}", operation_id=operation_id)
