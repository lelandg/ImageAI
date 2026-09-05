"""Frame history must retain pixels across multiple archived stage generations."""
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pytest

from cli.commands.sprite import _execute
from core.sprite.pipeline import CancelToken
from core.sprite.project import ActionCard, BackgroundSettings, SpriteProject, SpriteProjectManager


def test_undo_redo_after_delete_and_insert_restores_every_original_pixel(tmp_path):
    root = tmp_path / "library"
    project = SpriteProjectManager(root).create_project("History")
    project.background = BackgroundSettings(mode="original")
    project.actions = [ActionCard("a1", "colors", "the colors change")]
    project.save()
    sources = []
    colors = [(255, 0, 0), (0, 128, 0), (0, 0, 255), (255, 255, 0)]
    for index, color in enumerate(colors):
        path = tmp_path / f"{index}.png"
        Image.new("RGB", (20, 20), color).save(path)
        sources.append(str(path))
    args = SimpleNamespace(sprite_project=str(project.project_file()), sprite_root=str(root))

    def run(operation, data=None):
        args.sprite = operation
        return _execute(args, data or {}, CancelToken())

    def pixels():
        loaded = SpriteProject.load(project.project_file())
        actual = []
        for frame in loaded.actions[0].frames:
            assert frame.source_path.is_file()
            with Image.open(frame.source_path) as image:
                actual.append(image.convert("RGB").getpixel((10, 10)))
        return actual

    run("import-frames", {"actions": ["a1"], "paths": sources[:3]})
    run("process", {"upto": "hd"})
    assert pixels() == colors[:3]
    run("frame-edit", {"action": "a1", "operation": "delete", "indices": [0]})
    assert pixels() == colors[1:3]
    run("frame-edit", {"action": "a1", "operation": "insert", "paths": [sources[3]]})
    assert pixels() == colors[1:]
    run("undo")
    assert pixels() == colors[1:3]
    run("undo")
    assert pixels() == colors[:3]
    run("redo")
    assert pixels() == colors[1:3]
    run("redo")
    assert pixels() == colors[1:]
    exported = run("export", {"profiles": ["hd"], "formats": ["gif"]})
    assert any(Path(path).suffix == ".gif" and Path(path).is_file() for path in exported["files"])


def test_redo_delete_all_does_not_resurrect_frames_on_forced_processing(tmp_path):
    from core.sprite.pipeline import PipelineError
    root = tmp_path / "library"
    project = SpriteProjectManager(root).create_project("Empty history")
    project.background = BackgroundSettings(mode="original")
    project.actions = [ActionCard("a1", "color", "the color holds")]
    project.save()
    source = tmp_path / "red.png"
    Image.new("RGB", (20, 20), "red").save(source)
    args = SimpleNamespace(sprite_project=str(project.project_file()), sprite_root=str(root))

    def run(operation, data=None):
        args.sprite = operation
        return _execute(args, data or {}, CancelToken())

    run("import-frames", {"actions": ["a1"], "paths": [str(source)]})
    run("process", {"upto": "hd"})
    run("frame-edit", {"action": "a1", "operation": "delete", "indices": [0]})
    assert SpriteProject.load(project.project_file()).actions[0].frames == []
    run("undo")
    assert len(SpriteProject.load(project.project_file()).actions[0].frames) == 1
    run("redo")
    assert SpriteProject.load(project.project_file()).actions[0].frames == []
    with pytest.raises(PipelineError, match="no clip and no imported frames"):
        run("process", {"upto": "hd", "force": True})
    assert SpriteProject.load(project.project_file()).actions[0].frames == []
