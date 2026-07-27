import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session", autouse=True)
def _isolated_qsettings(tmp_path_factory):
    """Redirect every QSettings("ImageAI", ...) write into a session temp dir.

    Dialog tests exercise real close paths that persist geometry, splitter
    state, and LLM combo selections — without this, running the suite
    overwrites the developer's actual saved dialog settings (PR #38 review).
    """
    try:
        from PySide6.QtCore import QSettings
    except ImportError:
        yield
        return
    settings_dir = str(tmp_path_factory.mktemp("qsettings"))
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    # The (org, app) constructor uses NativeFormat regardless of the default
    # format, so redirect BOTH formats (on Linux they're the same backend but
    # separately-registered paths).
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      settings_dir)
    QSettings.setPath(QSettings.Format.NativeFormat, QSettings.Scope.UserScope,
                      settings_dir)
    yield


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
