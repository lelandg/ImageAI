"""Background loader for installed system font families.

Enumerating system fonts can stall the GUI thread on first access, so the
Layout tab pulls the family list off-thread via :class:`FontLoader` and caches
it for the rest of the process. The payload is plain strings, so handing the
result back to the GUI thread is safe.
"""
import logging
from typing import List, Optional

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger("imageai.layout.fonts")

# Process-wide cache: enumerate once, reuse for every widget that needs it.
_CACHE: Optional[List[str]] = None


def cached_families() -> Optional[List[str]]:
    """Return the cached family list, or ``None`` if it hasn't loaded yet."""
    return _CACHE


def _enumerate() -> List[str]:
    from PySide6.QtGui import QFontDatabase  # Qt6: fully static, query-safe off-thread
    families = [f for f in QFontDatabase.families() if f and not f.startswith((".", "@"))]
    return sorted(set(families), key=str.casefold)


class FontLoader(QThread):
    """Enumerate system font families off the GUI thread.

    Emits ``loaded(list_of_family_names)`` exactly once. On failure it logs and
    emits an empty list — font enumeration must never crash or hang the UI.
    """

    loaded = Signal(list)

    def run(self) -> None:  # noqa: D401 - QThread entry point
        global _CACHE
        try:
            families = _enumerate()
        except Exception as e:  # noqa: BLE001 - never let font loading take down the UI
            logger.error("System font enumeration failed: %s", e, exc_info=True)
            families = []
        if families:
            _CACHE = families
        self.loaded.emit(families)
