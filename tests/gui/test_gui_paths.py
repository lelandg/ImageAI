"""GUI modules must resolve data paths through DataPaths."""
import json
import pathlib

import pytest

import core.paths as paths_mod
from core.paths import DataPaths


@pytest.fixture
def roots(tmp_path, monkeypatch):
    images = tmp_path / "I"
    settings = tmp_path / "S"
    for d in (images, settings):
        d.mkdir()
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"data_roots": {
        "images": str(images), "settings": str(settings),
    }}), encoding="utf-8")
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))
    return images, settings


def test_history_widget_uses_the_settings_root(roots, qapp):
    _images, settings = roots
    from gui.history_widget import DialogHistoryWidget

    widget = DialogHistoryWidget(dialog_name="unit_test")
    assert widget._history_path() == settings / "unit_test_history.json"


def test_no_gui_module_builds_a_platform_dir():
    """No GUI file may compute the platform data directory itself."""
    needles = ("AppData", "Application Support", "XDG_CONFIG_HOME", "APPDATA")
    allowed = {"gui/gcloud_help.py"}  # gcloud paths are not ours

    offenders = []
    for path in pathlib.Path("gui").rglob("*.py"):
        if str(path).replace("\\", "/") in allowed:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(n in line for n in needles) and "gcloud" not in line.lower():
                offenders.append(f"{path}:{lineno}: {line.strip()}")
    assert not offenders, "GUI files building platform dirs:\n" + "\n".join(offenders)
