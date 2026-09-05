"""Frame history must retain pixels across multiple archived stage generations."""
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pytest

from cli.commands.sprite import _execute
from core.sprite.pipeline import CancelToken
from core.sprite.project import ActionCard, BackgroundSettings, SpriteProject, SpriteProjectManager


@pytest.fixture
def history_project(tmp_path):
    root = tmp_path / "library"
    project = SpriteProjectManager(root).create_project("Source history")
    project.actions = [ActionCard("a1", "motion", "the square moves")]
    project.key.key_color = "#00FF00"
    project.save()
    args = SimpleNamespace(sprite_project=str(project.project_file()), sprite_root=str(root))

    def run(operation, data=None):
        args.sprite = operation
        return _execute(args, data or {}, CancelToken())

    def load():
        return SpriteProject.load(project.project_file())

    return project, run, load


@pytest.mark.parametrize("values", [
    {"duration_ms": 321}, {"pivot": [0.25, 0.75]}, {"overrides": {"tolerance": 0.12}},
    {"name": "renamed frame"},
])
def test_metadata_undo_redo_retains_video_and_never_restores_media(
        history_project, synthetic_mp4, monkeypatch, values):
    project, run, load = history_project
    run("import-video", {"actions": ["a1"], "path": str(synthetic_mp4),
                         "extraction": {"mode": "exact_n", "exact_n": 3}})
    run("process", {"upto": "hd"})
    original = load().actions[0].to_dict()

    def unexpected_restore(*args, **kwargs):
        pytest.fail("Metadata-only history must not restore or bake media")

    monkeypatch.setattr("cli.commands.sprite._restore_generation", unexpected_restore)
    monkeypatch.setattr("cli.commands.sprite_generation.bake_working_frames", unexpected_restore)
    run("frame-edit", {"action": "a1", "operation": "update", "indices": [0], "values": values})
    changed = load().actions[0].to_dict()
    run("undo")
    assert load().actions[0].to_dict() == original
    run("redo")
    assert load().actions[0].to_dict() == changed
    assert list((project.project_dir / "stages").glob("a1.prev-*")) == []


@pytest.mark.parametrize("source_kind", ["video", "frames"])
def test_structural_undo_restores_raw_sources_and_processing_contract(
        history_project, synthetic_mp4, green_frames, source_kind):
    from core.sprite.pipeline import stage_dir, is_stage_current

    project, run, load = history_project
    if source_kind == "video":
        run("import-video", {"actions": ["a1"], "path": str(synthetic_mp4),
                             "extraction": {"mode": "exact_n", "exact_n": 3}})
    else:
        run("import-frames", {"actions": ["a1"], "paths": [str(path) for path in green_frames[:3]]})
    run("process", {"upto": "hd"})
    run("frame-edit", {"action": "a1", "operation": "update", "indices": [0],
                       "values": {"overrides": {"tolerance": 0.12}}})
    run("process", {"upto": "hd"})
    before = load()
    original_action = before.actions[0].to_dict()
    original_fingerprints = before.stage_fingerprints
    extract = stage_dir(project, before.actions[0], "extract")
    raw_sources = {path.name: path.read_bytes() for path in extract.glob("*.png")}

    run("frame-edit", {"action": "a1", "operation": "delete", "indices": [0]})
    assert load().actions[0].clip is None
    run("undo")
    restored = load()
    assert restored.actions[0].to_dict() == original_action
    assert restored.stage_fingerprints == original_fingerprints
    assert {path.name: path.read_bytes() for path in extract.glob("*.png")} == raw_sources
    assert is_stage_current(restored, restored.actions[0], "hd")
    run("export", {"profiles": ["hd"], "formats": ["gif"]})
    run("redo")
    assert len(load().actions[0].frames) == 2
    assert all(frame.overrides.get("baked_rgba") for frame in load().actions[0].frames)
    run("undo")
    run("process", {"upto": "hd", "force": True})
    restored = load()
    assert restored.actions[0].clip == before.actions[0].clip
    assert restored.actions[0].frames[0].overrides == {"tolerance": 0.12}
    with Image.open(stage_dir(restored, restored.actions[0], "key") / "0001.png") as keyed:
        assert keyed.getpixel((0, 0))[3] == 0

    # Switching back to the original background must recover the raw green
    # canvas for imported PNGs too, rather than treating keyed RGBA as raw input.
    run("edit", {"background": {"mode": "original"}})
    run("process", {"upto": "hd", "force": True})
    restored = load()
    with Image.open(stage_dir(restored, restored.actions[0], "key") / "0001.png") as image:
        red, green, blue, alpha = image.convert("RGBA").getpixel((0, 0))
        assert alpha == 255 and green > 200 and red < 20 and blue < 20


def test_metadata_undo_after_structural_undo_does_not_restore_media_again(
        history_project, green_frames, monkeypatch):
    _, run, load = history_project
    run("import-frames", {"actions": ["a1"], "paths": [str(path) for path in green_frames[:3]]})
    run("process", {"upto": "hd"})
    original_duration = load().actions[0].frames[0].duration_ms
    run("frame-edit", {"action": "a1", "operation": "update", "indices": [0],
                       "values": {"duration_ms": 321}})
    run("frame-edit", {"action": "a1", "operation": "delete", "indices": [0]})
    run("undo")
    assert load().actions[0].frames[0].duration_ms == 321

    def unexpected_restore(*args, **kwargs):
        pytest.fail("History snapshots sharing a restored generation must use its live paths")

    monkeypatch.setattr("cli.commands.sprite._restore_generation", unexpected_restore)
    run("undo")
    assert load().actions[0].frames[0].duration_ms == original_duration
    run("redo")
    assert load().actions[0].frames[0].duration_ms == 321


def test_undo_insert_before_first_process_restores_unprocessed_import(history_project, green_frames):
    from core.sprite.pipeline import stage_dir

    project, run, load = history_project
    run("import-frames", {"actions": ["a1"], "paths": [str(path) for path in green_frames[:3]]})
    assert load().actions[0].frames == []
    extract = stage_dir(project, load().actions[0], "extract")
    raw_sources = {path.name: path.read_bytes() for path in extract.glob("*.png")}
    run("frame-edit", {"action": "a1", "operation": "insert", "paths": [str(green_frames[3])]})
    run("undo")
    assert load().actions[0].frames == []
    assert {path.name: path.read_bytes() for path in extract.glob("*.png")} == raw_sources
    run("process", {"upto": "hd"})
    assert len(load().actions[0].frames) == 3


def test_cancel_during_structural_restore_keeps_accepted_project_and_history(
        history_project, green_frames, monkeypatch):
    import shutil
    from cli.commands.sprite import _undo, _history_path
    from core.sprite.pipeline import Cancelled

    project, run, load = history_project
    run("import-frames", {"actions": ["a1"], "paths": [str(path) for path in green_frames[:3]]})
    run("process", {"upto": "hd"})
    run("frame-edit", {"action": "a1", "operation": "delete", "indices": [0]})
    project_bytes = project.project_file().read_bytes()
    history_bytes = _history_path(project).read_bytes()
    pixels = [frame.source_path.read_bytes() for frame in load().actions[0].frames]
    token = CancelToken()
    original_copy = shutil.copy2

    def cancel_after_copy(src, dest):
        result = original_copy(src, dest)
        token.cancel()
        return result

    monkeypatch.setattr(shutil, "copy2", cancel_after_copy)
    with pytest.raises(Cancelled):
        _undo(load(), "undo", token)
    assert project.project_file().read_bytes() == project_bytes
    assert _history_path(project).read_bytes() == history_bytes
    assert [frame.source_path.read_bytes() for frame in load().actions[0].frames] == pixels


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
