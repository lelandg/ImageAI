"""Reject unusable Sprite settings before they reach a saved project."""
import io
import json

import pytest

from cli.commands.sprite import run_sprite_cmd
from cli.parser import build_arg_parser
from cli.sprite_schema import schemas, validate
from core.sprite.project import SpriteProject, SpriteProjectManager


@pytest.mark.parametrize("settings", [
    {"name": []},
    {"name": "  "},
    {"generation": {"resolution": "giant"}},
    {"generation": {"fps": 61}},
    {"generation": {"duration_s": 16}},
    {"extraction": {"every_n": 121}},
    {"extraction": {"exact_n": 513}},
    {"extraction": {"trim_end_s": 601}},
    {"key": {"despill": "green"}},
    {"key": {"ml_backend": "unknown"}},
    {"key": {"ml_model": "unknown"}},
    {"key": {"choke_px": 17}},
    {"stabilize": {"anchor": "left"}},
    {"stabilize": {"dejitter_method": "magic"}},
    {"stabilize": {"pad_px": 257}},
    {"profiles": [{"name": "pixel", "defringe_px": -1}]},
    {"profiles": [{"name": "pixel", "dither": "random"}]},
    {"profiles": [{"name": "pixel", "upscale_method": "unknown"}]},
    {"profiles": [{"name": "hd", "cell_size": [4097, 64]}]},
    {"profiles": [{"name": "pixel", "locked_palette": ["red"]}]},
    {"profiles": [{"name": "pixel", "locked_palette": ["#000000"] * 257}]},
])
def test_invalid_settings_leave_saved_project_untouched(monkeypatch, capsys, tmp_path, settings):
    project = SpriteProjectManager(tmp_path).create_project("Accepted settings")
    original = project.project_file().read_bytes()
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(settings)))
    args = build_arg_parser().parse_args([
        "--sprite", "edit", "--sprite-project", str(project.project_file()),
        "--sprite-data", "-", "--json",
    ])
    assert run_sprite_cmd(args) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error"
    assert project.project_file().read_bytes() == original


def test_gui_boundary_settings_and_single_color_palette_are_accepted(monkeypatch, capsys, tmp_path):
    project = SpriteProjectManager(tmp_path).create_project("GUI boundary settings")
    settings = {
        "generation": {"fps": 60, "duration_s": 15, "resolution": "1080p"},
        "extraction": {"every_n": 120, "target_fps": 60, "exact_n": 512,
                       "trim_start_s": 600, "trim_end_s": 600},
        "key": {"method": "ml", "despill": "limit", "ml_backend": "rembg",
                "ml_model": "bria-rmbg", "choke_px": 16, "feather_px": 16,
                "despeckle_px": 16},
        "stabilize": {"anchor": "bottom_left", "dejitter_method": "centroid", "pad_px": 256},
        "profiles": [{"name": "pixel", "cell_size": [4096, 1], "defringe_px": 16,
                      "palette_size": 1, "locked_palette": ["#12abEF"],
                      "dither": "floyd", "upscale_method": "stability_api"}],
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(settings)))
    args = build_arg_parser().parse_args([
        "--sprite", "edit", "--sprite-project", str(project.project_file()),
        "--sprite-data", "-", "--json",
    ])
    assert run_sprite_cmd(args) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
    loaded = SpriteProject.load(project.project_file())
    assert loaded.profile("pixel").palette_size == 1
    assert loaded.profile("pixel").cell_size == (4096, 1)
    assert loaded.key.ml_model == "bria-rmbg"


def test_palette_can_be_cleared_to_rebuild_or_disable_quantization():
    for profile in ({"name": "pixel", "locked_palette": None},
                    {"name": "pixel", "palette_size": None},
                    {"name": "pixel", "locked_palette": []}):
        validate({"profiles": [profile]}, schemas()["edit"])


@pytest.mark.parametrize("view", ["front", "side", "back", "three_quarter"])
def test_import_and_generation_accept_the_same_turnaround_views(view):
    validate({"path": "reference.png", "kind": "turnaround", "view": view}, schemas()["source"])
    validate({"views": [view]}, schemas()["turnaround"])


@pytest.mark.parametrize("operation,payload", [
    ("source", {"path": "reference.png", "kind": "turnaround", "view": "left"}),
    ("turnaround", {"views": ["front", "front"]}),
    ("frame-edit", {"operation": "update", "action": "idle", "indices": [0],
                    "values": {"pivot": [2, 0]}}),
    ("action-edit", {"operation": "add", "values": {"name": "idle", "target_frames": 65}}),
    ("export", {"grid": {"columns": 257}}),
    ("render", {"frames": 65}),
    ("retouch", {"actions": ["idle"], "frame": 0, "instruction": "Repair", "attempts": 6}),
])
def test_non_edit_requests_expose_actual_supported_bounds(operation, payload):
    with pytest.raises(ValueError):
        validate(payload, schemas()[operation])
