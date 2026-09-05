"""A named copy has independent media paths and leaves the source intact."""
import pytest

from core.sprite.project import ActionCard, ClipRecord, SpriteProjectManager
from core.sprite.project_copy import copy_project


def test_copy_repoints_media_and_preserves_original(tmp_path):
    manager = SpriteProjectManager(tmp_path)
    original = manager.create_project("Hero")
    source = original.project_dir / "source" / "character.png"
    source.write_bytes(b"image")
    original.character_source = source
    original.actions = [ActionCard(
        id="idle", name="idle", prompt="", clip=ClipRecord.from_dict({"path": str(source)}))]
    copied = copy_project(original, "Other Hero", manager)
    assert copied.name == "Other Hero"
    assert copied.character_source != source
    assert copied.character_source.read_bytes() == b"image"
    assert copied.actions[0].clip.path == copied.character_source
    assert original.character_source == source
    assert original.actions[0].clip.path == source
    assert manager.load_project(copied.project_file()).character_source == copied.character_source


def test_failed_copy_removes_only_its_partial_project(tmp_path, monkeypatch):
    manager = SpriteProjectManager(tmp_path)
    original = manager.create_project("Hero")
    source = original.project_dir / "source" / "character.png"
    source.write_bytes(b"image")
    def fail(*args, **kwargs):
        raise OSError("disk full")
    monkeypatch.setattr("core.sprite.project_copy.shutil.copytree", fail)
    with pytest.raises(OSError, match="disk full"):
        copy_project(original, "Other Hero", manager)
    assert source.read_bytes() == b"image"
    assert [entry["name"] for entry in manager.list_projects()] == ["Hero"]
