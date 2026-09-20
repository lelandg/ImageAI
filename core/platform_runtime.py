"""Early compatibility guard for CPython 3.12 Windows scientific imports."""
from __future__ import annotations

import platform
import sys
from typing import Any


def _without_wmi(*args: Any, **kwargs: Any) -> Any:
    # platform catches OSError and uses the native Windows fallback.
    raise OSError("Use the standard Windows platform fallback")


def initialize_platform_runtime() -> None:
    """Avoid the native WMI/COM crash before keyring, NumPy or PortAudio imports.

    Restricted to CPython 3.12 on Windows, where the failure was reproduced.
    Reassess this workaround when that interpreter is no longer supported.
    """
    if (sys.platform == "win32" and sys.version_info[:2] == (3, 12)
            and sys.implementation.name == "cpython"
            and hasattr(platform, "_wmi_query")):
        platform._wmi_query = _without_wmi
