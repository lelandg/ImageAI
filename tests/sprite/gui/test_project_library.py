"""Project-name UI and last-project restoration, with real temporary projects."""
from pathlib import Path

from gui.sprite import SpriteTab
from gui.sprite.prefs import sprite_settings


def test_last_project_restored_after_workspace_is_wired(qapp, fake_config):
    first = SpriteTab(fake_config)
    project = first.new_project_named("Space Ranger")
    first.shutdown()
    second = SpriteTab(fake_config)
    assert second.current_project is not None
    assert second.current_project.project_dir == project.project_dir
    assert second.frames_workspace.panel.project() is second.current_project
    assert second.title_label.text() == "Space Ranger"
    second.shutdown()


def test_missing_last_project_is_logged_without_blocking(qapp, fake_config, tmp_path):
    sprite_settings().setValue("sprite/last_project", str(tmp_path / "gone.iasprite.json"))
    tab = SpriteTab(fake_config)
    assert tab.current_project is None
    assert "Could not restore" in tab.console.console.toPlainText()
    assert sprite_settings().contains("sprite/last_project")


def test_title_and_save_confirmation_only_show_project_name(qapp, fake_config):
    tab = SpriteTab(fake_config)
    project = tab.new_project_named("Space Ranger")
    tab.save_project()
    assert tab.title_label.text() == "Space Ranger"
    assert str(project.project_dir) not in tab.console.console.toPlainText()


def test_picker_uses_names_and_distinguishes_duplicate_projects(qapp, tmp_path):
    from core.sprite.project import SpriteProjectManager
    from gui.sprite.project_dialog import SpriteProjectDialog

    manager = SpriteProjectManager(tmp_path)
    first = manager.create_project("Space Ranger")
    second = manager.create_project("Space Ranger")
    dialog = SpriteProjectDialog(manager)
    assert dialog.project_list.count() == 2
    labels = [dialog.project_list.item(i).text() for i in range(2)]
    assert all("Space Ranger" in label for label in labels)
    assert labels[0] != labels[1]
    assert all(str(tmp_path) not in label for label in labels)
    selected = set()
    for index in range(2):
        dialog.project_list.setCurrentRow(index)
        selected.add(Path(dialog.selected_path()))
    assert selected == {first.project_file(), second.project_file()}


def test_named_save_as_copies_media_and_remembers_copy(qapp, fake_config, png):
    tab = SpriteTab(fake_config)
    original = tab.new_project_named("Original")
    source = original.project_dir / "source" / "character.png"
    source.write_bytes(png.read_bytes())
    original.character_source = source
    copied = tab.save_project_as_named("Second version")
    assert copied is tab.current_project
    assert copied.name == "Second version"
    assert copied.project_dir != original.project_dir
    assert copied.character_source.read_bytes() == png.read_bytes()
    assert source.exists()
    assert not Path(sprite_settings().value("sprite/last_project")).is_absolute()
    second = SpriteTab(fake_config)
    assert second.current_project.project_dir == copied.project_dir


def test_failed_manual_open_keeps_last_successful_project(qapp, fake_config, monkeypatch, tmp_path):
    tab = SpriteTab(fake_config)
    original = tab.new_project_named("Good project")
    saved = sprite_settings().value("sprite/last_project")
    monkeypatch.setattr(tab, "_report_error", lambda *args: None)
    assert tab.open_project_from(tmp_path / "missing.json") is None
    assert tab.current_project is original
    assert sprite_settings().value("sprite/last_project") == saved


def test_relative_last_project_follows_new_library_root(qapp, fake_config, tmp_path, monkeypatch):
    import shutil
    from core.sprite.project import SpriteProjectManager

    tab = SpriteTab(fake_config)
    original = tab.new_project_named("Moving project")
    moved_library = tmp_path / "moved"
    shutil.copytree(original.project_dir, moved_library / original.project_dir.name)
    monkeypatch.setattr("gui.sprite.sprite_tab.SpriteProjectManager",
                        lambda: SpriteProjectManager(moved_library))
    second = SpriteTab(fake_config)
    assert second.current_project.project_dir == moved_library / original.project_dir.name


def test_picker_skips_invalid_metadata_and_keeps_valid_projects(qapp, tmp_path, caplog):
    from core.sprite.project import SpriteProjectManager
    from gui.sprite.project_dialog import SpriteProjectDialog

    manager = SpriteProjectManager(tmp_path)
    good = manager.create_project("Good project")
    for index, content in enumerate(('[]', '{"actions": null}', '{"name": []}', '{broken')):
        broken = manager.create_project(f"Broken {index}")
        broken.project_file().write_text(content, encoding="utf-8")
    dialog = SpriteProjectDialog(manager)
    assert dialog.project_list.count() == 1
    assert dialog.selected_path() == good.project_file()
    assert "Failed to read sprite project" in caplog.text


def test_picker_search_and_cancel_do_not_open_a_project(qapp, tmp_path):
    from PySide6.QtWidgets import QDialog, QDialogButtonBox
    from core.sprite.project import SpriteProjectManager
    from gui.sprite.project_dialog import SpriteProjectDialog

    manager = SpriteProjectManager(tmp_path)
    good = manager.create_project("Space Ranger")
    dialog = SpriteProjectDialog(manager)
    dialog.search.setText("missing")
    assert dialog.selected_path() is None
    assert not dialog.buttons.button(QDialogButtonBox.Open).isEnabled()
    dialog.search.setText("ranger")
    assert dialog.selected_path() == good.project_file()
    dialog.reject()
    assert dialog.result() == QDialog.DialogCode.Rejected
