"""Exercise persisted CLI projects rather than mocking their implementation."""
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from cli.commands.sprite import run_sprite_cmd
from cli.parser import build_arg_parser
from cli.sprite_schema import schemas, validate
from core.sprite.project import SpriteProject, SpriteProjectManager


def invoke(monkeypatch, capsys, root, operation, data=None, project=None):
    argv = ["--sprite", operation, "--sprite-root", str(root), "--sprite-data", "-", "--json"]
    if project:
        argv += ["--sprite-project", str(project)]
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data or {})))
    code = run_sprite_cmd(build_arg_parser().parse_args(argv))
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result["exit_code"] == code
    return code, result


def test_new_edit_actions_undo_and_copy(monkeypatch, capsys, tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (48, 32), "white").save(source)
    root = tmp_path / "library"
    code, result = invoke(monkeypatch, capsys, root, "new", {
        "name": "Curious Lantern", "source": str(source),
        "settings": {"background": {"mode": "original"}}})
    assert code == 0
    project = Path(result["project"])
    assert SpriteProject.load(project).character_source.is_file()
    code, result = invoke(monkeypatch, capsys, root, "action-edit", {
        "operation": "add", "values": {"name": "wonder", "prompt": "orbit", "fps": 8}}, project)
    assert code == 0
    action_id = result["action"]["id"]
    code, _ = invoke(monkeypatch, capsys, root, "edit", {
        "background": {"mode": "solid", "color": "#ffcc00"},
        "profiles": [{"name": "pixel", "cell_size": [32, 48]}]}, project)
    assert code == 0
    loaded = SpriteProject.load(project)
    assert loaded.background.color == "#FFCC00"
    assert loaded.profile("pixel").cell_size == (32, 48)
    assert loaded.actions[0].id == action_id
    assert invoke(monkeypatch, capsys, root, "undo", project=project)[0] == 0
    assert SpriteProject.load(project).background.mode == "original"
    assert invoke(monkeypatch, capsys, root, "redo", project=project)[0] == 0
    assert SpriteProject.load(project).background.mode == "solid"
    code, result = invoke(monkeypatch, capsys, root, "copy", {"name": "Independent"}, project)
    assert code == 0
    copied = SpriteProject.load(Path(result["project"]))
    assert copied.character_source != loaded.character_source
    assert copied.character_source.is_relative_to(copied.project_dir)


@pytest.mark.parametrize("data", [
    {"key": {"tolerance": "0.2"}}, {"unknown": True},
    {"generation": {"fps": 0}}, {"background": {"mode": "paper"}},
    {"profiles": [{"name": "pixel", "cell_size": [0, 20]}]},
    {"key": {"softness": float("nan")}}, {"generation": {"fps": True}},
])
def test_invalid_edit_does_not_change_project(monkeypatch, capsys, tmp_path, data):
    project = SpriteProjectManager(tmp_path).create_project("Keep")
    before = project.project_file().read_bytes()
    code, result = invoke(monkeypatch, capsys, tmp_path, "edit", data, project.project_file())
    assert code == 2, result
    assert project.project_file().read_bytes() == before


def test_undo_refuses_intervening_gui_edit(monkeypatch, capsys, tmp_path):
    project = SpriteProjectManager(tmp_path).create_project("Original")
    assert invoke(monkeypatch, capsys, tmp_path, "edit", {"name": "CLI"}, project.project_file())[0] == 0
    gui = SpriteProject.load(project.project_file())
    gui.name = "GUI"
    gui.save()
    assert invoke(monkeypatch, capsys, tmp_path, "undo", project=project.project_file())[0] == 2
    assert SpriteProject.load(project.project_file()).name == "GUI"


def test_frame_edits_survive_reload_and_undo(monkeypatch, capsys, tmp_path):
    from core.sprite.models import FrameMeta
    from core.sprite.project import ActionCard
    project = SpriteProjectManager(tmp_path).create_project("Frames")
    project.actions = [ActionCard("idle", "idle", "", frames=[
        FrameMeta("one", None, (0, 0, 8, 8)), FrameMeta("two", None, (0, 0, 8, 8))])]
    project.save()
    common = {"action": "idle"}
    code, _ = invoke(monkeypatch, capsys, tmp_path, "frame-edit", {
        **common, "operation": "update", "indices": [1], "values": {"duration_ms": 250, "pivot": [0.2, 0.3]}}, project.project_file())
    assert code == 0
    assert invoke(monkeypatch, capsys, tmp_path, "frame-edit", {
        **common, "operation": "reorder", "order": [1, 0]}, project.project_file())[0] == 0
    loaded = SpriteProject.load(project.project_file())
    assert loaded.actions[0].frames[0].duration_ms == 250
    assert loaded.actions[0].frames[0].name == "two"
    assert invoke(monkeypatch, capsys, tmp_path, "undo", project=project.project_file())[0] == 0
    assert SpriteProject.load(project.project_file()).actions[0].frames[0].name == "one"


def test_discovery_is_valid_json_schema(monkeypatch, capsys, tmp_path):
    jsonschema = pytest.importorskip("jsonschema")
    code, result = invoke(monkeypatch, capsys, tmp_path, "schema")
    assert code == 0
    for schema in result["operations"].values():
        jsonschema.Draft202012Validator.check_schema(schema)
    validate({"name": "new"}, schemas()["new"])


def test_ambiguous_project_names_fail(monkeypatch, capsys, tmp_path):
    manager = SpriteProjectManager(tmp_path)
    manager.create_project("same")
    manager.create_project("same")
    code, result = invoke(monkeypatch, capsys, tmp_path, "inspect", project="same")
    assert code == 2
    assert "matched 2 projects" in result["error"]


def test_provider_prints_do_not_pollute_stdout(monkeypatch, capsys, tmp_path):
    def execute(*args):
        print("noisy library")
        return {"result": "fine"}
    monkeypatch.setattr("cli.commands.sprite._execute", execute)
    code, result = invoke(monkeypatch, capsys, tmp_path, "inspect")
    assert code == 0
    assert result["result"] == "fine"


def test_cancellation_and_redacted_errors(monkeypatch, capsys, tmp_path):
    def cancel(*args):
        raise KeyboardInterrupt
    monkeypatch.setattr("cli.commands.sprite._execute", cancel)
    assert invoke(monkeypatch, capsys, tmp_path, "inspect")[0] == 130
    def error(*args):
        raise RuntimeError("Bearer secret-token-value")
    monkeypatch.setattr("cli.commands.sprite._execute", error)
    code, result = invoke(monkeypatch, capsys, tmp_path, "inspect")
    assert code == 1
    assert "secret-token-value" not in json.dumps(result)


def test_insert_export_undo_redo(monkeypatch, capsys, tmp_path, alpha_frames):
    from core.sprite.project import ActionCard
    project = SpriteProjectManager(tmp_path / "library").create_project("Insertion")
    project.key.method = "none"
    project.actions = [ActionCard("idle", "idle", "")]
    project.save()
    root, path = tmp_path / "library", project.project_file()
    assert invoke(monkeypatch, capsys, root, "import-frames", {
        "actions": ["idle"], "paths": [str(p) for p in alpha_frames]}, path)[0] == 0
    assert invoke(monkeypatch, capsys, root, "process", {"actions": ["idle"]}, path)[0] == 0
    code, result = invoke(monkeypatch, capsys, root, "frame-edit", {
        "action": "idle", "operation": "insert", "at": 1,
        "paths": [str(alpha_frames[0])]}, path)
    assert code == 0, result
    assert len(SpriteProject.load(path).actions[0].frames) == len(alpha_frames) + 1
    for operation, expected in (("export", len(alpha_frames) + 1),
                                ("undo", len(alpha_frames)), ("redo", len(alpha_frames) + 1)):
        data = {"actions": ["idle"], "profiles": ["hd"], "formats": ["gif"]} if operation == "export" else {}
        code, result = invoke(monkeypatch, capsys, root, operation, data, path)
        assert code == 0, result
        assert len(SpriteProject.load(path).actions[0].frames) == expected
    assert invoke(monkeypatch, capsys, root, "process", {"actions": ["idle"], "force": True}, path)[0] == 0
    assert len(SpriteProject.load(path).actions[0].frames) == len(alpha_frames) + 1


def test_delete_respects_writer_lock(monkeypatch, capsys, tmp_path):
    from cli.commands.sprite import _project_lock
    project = SpriteProjectManager(tmp_path).create_project("Locked")
    with _project_lock(project):
        code, result = invoke(monkeypatch, capsys, tmp_path, "delete", {"confirm": True}, project.project_file())
        assert code == 2
        assert "Another Sprite CLI" in result["error"]
        assert project.project_file().is_file()
