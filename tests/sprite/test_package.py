"""The core.sprite package exports the whole sub-project 1 API (design 4.1)."""
import importlib

import core.sprite as sprite


def test_every_exported_name_resolves():
    for name in sprite.__all__:
        assert hasattr(sprite, name), name


def test_spec_symbols_are_exported():
    expected = {
        "FrameMeta", "TagMeta", "SheetMeta", "SpriteProject", "SpriteProjectManager",
        "GenerationSettings", "ExtractionSettings", "KeySettings", "StabilizeSettings",
        "OutputProfile", "ActionCard", "ClipRecord", "CostEntry",
        "FrameListSnapshot", "SnapshotStack",
        "CancelToken", "Cancelled", "ProgressFn", "no_progress", "STAGES", "STAGE_CODE_VERSION",
        "STAGE_RUNNERS", "STAGE_SETTINGS", "StageRunner", "SettingsFn", "register_stage",
        "identity_runner", "stage_fingerprint", "run_pipeline", "stage_dir",
        "ExtractResult", "probe_video", "extract_frames", "estimate_frame_count", "cull_duplicates",
        "FFmpegError", "GridGuess", "guess_grid", "slice_sheet", "import_png_sequence",
        "union_alpha_bbox", "solid_border_bbox", "crop_and_pad",
        "GridOptions", "export_grid", "export_aseprite_json", "export_texturepacker_json",
        "export_png_sequence", "export_single_frame", "export_gif",
    }
    missing = expected - set(sprite.__all__)
    assert not missing, missing


def test_import_does_not_load_the_cloud_video_clients():
    """core.video's package import costs seconds (google.genai); core.sprite must not pay it."""
    import subprocess
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    code = "import sys, core.sprite; sys.exit(1 if 'core.video' in sys.modules else 0)"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                            timeout=120, cwd=repo_root)
    assert result.returncode == 0, result.stderr[-500:]


def test_submodules_import_cleanly():
    for module in ("models", "project", "presets", "undo", "pipeline", "extract", "slicing",
                   "stabilize", "exporters", "exporters.grid", "exporters.aseprite_json",
                   "exporters.texturepacker_json", "exporters.png_sequence", "exporters.gif"):
        importlib.import_module(f"core.sprite.{module}")
