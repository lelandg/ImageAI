"""Construction and wiring tests for the Storage Locations widget."""
import json

import pytest

import core.paths as paths_mod
from core.paths import DataPaths, Group


@pytest.fixture
def widget(tmp_path, monkeypatch, qapp):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))

    from gui.storage_settings_widget import StorageSettingsWidget

    return StorageSettingsWidget()


def test_widget_has_one_row_per_group(widget):
    assert set(widget.rows) == set(Group)


def test_each_row_has_move_and_open_buttons(widget):
    for group, row in widget.rows.items():
        assert row.move_button is not None, group
        assert row.open_button is not None, group


def test_rows_start_in_a_calculating_state(widget):
    for row in widget.rows.values():
        assert row.size_label.text() == "Calculating…"


def test_multi_tree_groups_are_labelled(widget, monkeypatch):
    """Models and Video can span two source trees before the first move."""
    assert widget.rows[Group.MODELS].path_label.toolTip()
    assert widget.rows[Group.VIDEO].path_label.toolTip()


def test_large_group_sizes_survive_the_signal(widget):
    """A group larger than 2 GB must not overflow the size signal."""
    from gui.storage_settings_widget import _SizeWorker

    received = []
    worker = _SizeWorker(Group.MODELS)
    worker.finished.connect(lambda name, total: received.append((name, total)))
    worker.finished.emit(Group.MODELS.value, 28_391_171_187)

    assert received == [("models", 28_391_171_187)]


def test_unreachable_root_shows_a_warning(tmp_path, monkeypatch, qapp):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"data_roots": {"images": str(tmp_path / "gone" / "x")}}),
                   encoding="utf-8")
    monkeypatch.setattr(paths_mod, "_INSTANCE", DataPaths(config_path=cfg))

    from gui.storage_settings_widget import StorageSettingsWidget

    widget = StorageSettingsWidget()
    assert "Unavailable" in widget.rows[Group.IMAGES].status_label.text()
