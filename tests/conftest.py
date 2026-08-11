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


@pytest.fixture(scope="session", autouse=True)
def _sandboxed_user_data_dir(tmp_path_factory):
    """Point every unqualified data path at a session temp directory.

    ``core.paths.get_data_paths()`` returns a process-wide singleton. A test
    that builds it without an explicit config path resolves it against the
    developer's real user directory, and it stays that way for the rest of the
    session: ``DataPaths`` caches both the config path and each resolved root.
    A later test that writes through the singleton then writes into the real
    directory. ``providers/google.py`` saves a ``DEBUG_RAW_GEMINI_*`` image on
    every generate call, so running the suite dropped one of those files in the
    developer's ``~/.config/ImageAI/generated`` on each run.

    A per-test ``Path.home`` patch cannot prevent it, because the singleton has
    already cached the real path by then. Patching ``platform_default_dir``
    does, and it also survives ``reset_data_paths()``: a rebuilt singleton
    lands in the sandbox too. A test that needs its own root still overrides
    ``_INSTANCE`` or ``platform_default_dir`` with ``monkeypatch``, and
    ``monkeypatch`` restores this sandbox at the end of that test.
    """
    import core.paths as paths_mod

    sandbox = tmp_path_factory.mktemp("user_data")
    patch = pytest.MonkeyPatch()
    patch.setattr(paths_mod, "platform_default_dir", lambda: sandbox)
    paths_mod.reset_data_paths()
    yield sandbox
    patch.undo()
    paths_mod.reset_data_paths()


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
