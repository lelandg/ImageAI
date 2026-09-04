# tests/sprite/test_named_configs.py
"""NamedConfigStore: named GenerationSettings in one JSON file (decision 9)."""
import json
import os

import pytest

from core.paths import get_data_paths
from core.sprite.configs import DEFAULT_NAME, NamedConfigStore, settings_from_dict
from core.sprite.project import GenerationSettings


def _store(tmp_path):
    return NamedConfigStore(tmp_path / "sprite_configs.json")


def test_default_path_comes_from_data_paths():
    assert NamedConfigStore().path == get_data_paths().sprite_configs()


def test_fresh_store_lists_only_default(tmp_path):
    store = _store(tmp_path)
    assert store.list_names() == [DEFAULT_NAME]
    assert not store.path.exists()  # nothing written until a save


def test_default_resolves_to_dataclass_defaults(tmp_path):
    settings = _store(tmp_path).get(DEFAULT_NAME)
    assert settings == GenerationSettings(config_name=DEFAULT_NAME)


def test_save_get_roundtrip_and_ordering(tmp_path):
    store = _store(tmp_path)
    custom = GenerationSettings(provider="veo", model="veo-3.1-fast-generate-001",
                                duration_s=6, include_audio=True, plate_color="#0000FF")
    store.save("Zed", custom)
    store.save("Alpha", GenerationSettings())
    assert store.list_names() == [DEFAULT_NAME, "Alpha", "Zed"]
    loaded = store.get("Zed")
    assert loaded.config_name == "Zed"
    assert loaded.provider == "veo" and loaded.duration_s == 6 and loaded.include_audio
    doc = json.loads(store.path.read_text(encoding="utf-8"))
    assert doc["version"] == 1 and set(doc["configs"]) == {"Zed", "Alpha"}


def test_default_can_be_overwritten_but_not_deleted(tmp_path):
    store = _store(tmp_path)
    store.save(DEFAULT_NAME, GenerationSettings(duration_s=4))
    assert store.get(DEFAULT_NAME).duration_s == 4
    with pytest.raises(ValueError):
        store.delete(DEFAULT_NAME)
    assert store.list_names() == [DEFAULT_NAME]


def test_delete_removes_and_unknown_raises(tmp_path):
    store = _store(tmp_path)
    store.save("Temp", GenerationSettings())
    store.delete("Temp")
    assert store.list_names() == [DEFAULT_NAME]
    with pytest.raises(KeyError):
        store.delete("Temp")
    with pytest.raises(KeyError):
        store.get("Nope")


def test_empty_name_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        _store(tmp_path).save("   ", GenerationSettings())


def test_unknown_keys_are_dropped_and_missing_keys_default():
    settings = settings_from_dict({"provider": "veo", "future_field": 1}, name="X")
    assert settings.provider == "veo" and settings.config_name == "X"
    assert settings.fps == GenerationSettings().fps


def test_corrupt_file_is_logged_and_treated_as_empty(tmp_path, caplog):
    store = _store(tmp_path)
    store.path.write_text("{ not json", encoding="utf-8")
    with caplog.at_level("ERROR"):
        assert store.list_names() == [DEFAULT_NAME]
    assert any("unreadable" in record.message for record in caplog.records)


def test_save_raises_and_leaves_file_unchanged_when_unreadable(tmp_path):
    """Minor 9: an OSError on read must not be swallowed into an overwrite."""
    store = _store(tmp_path)
    for i in range(5):
        store.save(f"c{i}", GenerationSettings())
    original_bytes = store.path.read_bytes()
    store.path.chmod(0o000)
    try:
        if os.access(store.path, os.R_OK):
            pytest.skip("this user can read a 0o000 file (e.g. root); can't exercise OSError")
        with pytest.raises(OSError):
            store.save("x", GenerationSettings())
    finally:
        store.path.chmod(0o644)
    assert store.path.read_bytes() == original_bytes
    assert store.list_names() == [DEFAULT_NAME, "c0", "c1", "c2", "c3", "c4"]


def test_save_quarantines_unparsable_file_and_preserves_old_bytes(tmp_path):
    """Minor 9: a file that exists but doesn't parse is quarantined, not overwritten blind."""
    store = _store(tmp_path)
    for i in range(5):
        store.save(f"c{i}", GenerationSettings())
    corrupt = store.path.with_name(store.path.name + ".corrupt")
    corrupt.write_text("stale quarantine from an earlier run", encoding="utf-8")
    store.path.write_text("{not json", encoding="utf-8")

    store.save("x", GenerationSettings())

    assert store.list_names() == [DEFAULT_NAME, "x"]
    doc = json.loads(store.path.read_text(encoding="utf-8"))
    assert set(doc["configs"]) == {"x"}
    assert corrupt.exists()
    assert corrupt.read_text(encoding="utf-8") == "{not json"  # the bad bytes, not the earlier stale one
