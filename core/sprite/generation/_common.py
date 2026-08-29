"""Small helpers shared by the sprite generation modules. Private."""
import logging
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
