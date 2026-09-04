"""Small helpers shared by the sprite generation modules. Private."""
import logging
import re
from datetime import datetime
from typing import Callable, Optional

LogFn = Callable[[str], None]


def emit(logger: logging.Logger, log: Optional[LogFn], message: str,
         level: str = "info") -> None:
    """Write ``message`` to the file logger and to the injected sink.

    The sink is skipped when it is a bound method of ``logger`` itself, so a
    module default of ``log=logger.info`` does not write every line twice.
    A sink that raises never breaks generation; the failure goes to DEBUG.
    """
    getattr(logger, level, logger.info)(message)
    if log is None:
        return
    if getattr(log, "__self__", None) is logger:
        return
    try:
        log(message)
    except Exception:  # noqa: BLE001 - a broken console must not stop a render
        logger.debug("log sink raised", exc_info=True)


def now_iso() -> str:
    """Local time as ISO-8601 with second precision (sidecars, ledger rows)."""
    return datetime.now().isoformat(timespec="seconds")


_BEARER_RE = re.compile(r"(?i)\bBearer\s+\S+")
_KV_SECRET_RE = re.compile(r'(?i)\b(api_key|apikey|key|token)=[^&\s"\']+')
_GOOGLE_KEY_RE = re.compile(r"AIza[0-9A-Za-z_-]{20,}")
_OPENAI_KEY_RE = re.compile(r"sk-[A-Za-z0-9_-]{16,}")
_HF_KEY_RE = re.compile(r"hf_[A-Za-z0-9]{16,}")


def redact_secrets(text: str) -> str:
    """Mask bearer tokens, key/token parameters, and known API key formats.

    Every match is replaced with ``***`` so provider error text is safe to
    show in a ``user_message``. The full raw text may still go to the
    module logger, which is not redacted.
    """
    text = _BEARER_RE.sub("Bearer ***", text)
    text = _KV_SECRET_RE.sub(lambda m: f"{m.group(1)}=***", text)
    text = _GOOGLE_KEY_RE.sub("***", text)
    text = _OPENAI_KEY_RE.sub("***", text)
    text = _HF_KEY_RE.sub("***", text)
    return text
