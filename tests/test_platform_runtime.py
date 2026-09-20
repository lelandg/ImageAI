"""The WMI workaround must remain specific to the reproduced runtime."""
from types import SimpleNamespace

import pytest

from core import platform_runtime as runtime


@pytest.mark.parametrize("system,version,implementation,enabled", [
    ("win32", (3, 12), "cpython", True),
    ("win32", (3, 13), "cpython", False),
    ("linux", (3, 12), "cpython", False),
    ("win32", (3, 12), "pypy", False),
])
def test_guard_scope(monkeypatch, system, version, implementation, enabled):
    query = lambda: "original"
    fake_platform = SimpleNamespace(_wmi_query=query)
    monkeypatch.setattr(runtime, "platform", fake_platform)
    monkeypatch.setattr(runtime, "sys", SimpleNamespace(
        platform=system, version_info=version, implementation=SimpleNamespace(name=implementation)))
    runtime.initialize_platform_runtime()
    if enabled:
        with pytest.raises(OSError, match="Windows platform fallback"):
            fake_platform._wmi_query()
    else:
        assert fake_platform._wmi_query is query
