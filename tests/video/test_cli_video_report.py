import json
from argparse import Namespace
from unittest.mock import patch
from cli.commands.video import run_video_cmd


def _ns(**kw):
    base = dict(prompt="p", out=None, aspect="16:9", ref_image=None, last_frame=None,
                extend=None, video_model=None, api_key="k", api_key_file=None,
                auth_mode="api-key", video_provider="veo", json=False)
    base.update(kw)
    return Namespace(**base)


def _ok(out):
    return {"success": True, "output_path": str(out), "provider": "veo",
            "model": "veo-3.1-generate-001", "aspect_ratio": "16:9",
            "operation_id": "op-1", "error": None}


def test_success_writes_sidecar_and_returns_zero(tmp_path):
    out = tmp_path / "v.mp4"
    with patch("cli.commands.video._run_veo", return_value=_ok(out)):
        rc = run_video_cmd(_ns(out=str(out)))
    assert rc == 0
    sidecar = out.with_suffix(".json")
    assert sidecar.exists()
    data = json.loads(sidecar.read_text())
    assert data["status"] == "completed"
    assert data["provider"] == "veo"


def test_json_mode_prints_one_object_to_stdout(tmp_path, capsys):
    out = tmp_path / "v.mp4"
    with patch("cli.commands.video._run_veo", return_value=_ok(out)):
        rc = run_video_cmd(_ns(out=str(out), json=True))
    captured = capsys.readouterr()
    assert rc == 0
    obj = json.loads(captured.out)  # exactly one JSON object, nothing else on stdout
    assert obj["status"] == "completed"
    assert obj["operation_id"] == "op-1"


def test_non_json_mode_keeps_stdout_empty(tmp_path, capsys):
    out = tmp_path / "v.mp4"
    with patch("cli.commands.video._run_veo", return_value=_ok(out)):
        run_video_cmd(_ns(out=str(out), json=False))
    captured = capsys.readouterr()
    assert captured.out == ""           # human text goes to stderr only
    assert "Video saved" in captured.err


def test_validation_error_returns_two(tmp_path, capsys):
    # omni + --extend is a VideoCliError raised inside _run_omni
    out = tmp_path / "v.mp4"
    rc = run_video_cmd(_ns(out=str(out), video_provider="omni",
                           extend="prev.mp4", json=True))
    captured = capsys.readouterr()
    assert rc == 2
    obj = json.loads(captured.out)
    assert obj["status"] == "failed"
    assert "extend" in obj["error"]
    # Sidecar must NOT be written on validation errors (no generation attempted)
    assert not out.with_suffix(".json").exists()


def _failed_result(out):
    """Normalized dispatcher dict representing a client-side failure (all 7 keys)."""
    return {
        "success": False,
        "output_path": str(out),
        "provider": "veo",
        "model": "veo-3.1-generate-001",
        "aspect_ratio": "16:9",
        "operation_id": None,
        "error": "upstream quota exceeded",
    }


def test_client_failure_returns_one(tmp_path):
    """Client returns success=False → exit 1, sidecar written with status='failed'."""
    out = tmp_path / "v.mp4"
    with patch("cli.commands.video._run_veo", return_value=_failed_result(out)):
        rc = run_video_cmd(_ns(out=str(out)))
    assert rc == 1
    sidecar = out.with_suffix(".json")
    assert sidecar.exists()
    data = json.loads(sidecar.read_text())
    assert data["status"] == "failed"


def test_unexpected_exception_returns_three(tmp_path):
    """Unhandled exception in _run_veo → exit 3, NO sidecar written."""
    out = tmp_path / "v.mp4"
    with patch("cli.commands.video._run_veo", side_effect=Exception("boom")):
        rc = run_video_cmd(_ns(out=str(out)))
    assert rc == 3
    assert not out.with_suffix(".json").exists()


def test_json_stdout_pure_with_setup_logging(tmp_path, capsys):
    """Regression: console log handler must route to stderr so --json stdout stays clean.

    The existing tests never call setup_logging(), which is why this bug hid.
    Once setup_logging() is called, logger.error() inside _fail() must not bleed
    into stdout and break json.loads().
    """
    from core.logging_config import setup_logging
    setup_logging(log_to_file=False)
    out = tmp_path / "v.mp4"
    # omni + --extend → VideoCliError → _fail() calls logger.error() + emits JSON
    rc = run_video_cmd(_ns(out=str(out), video_provider="omni",
                           extend="prev.mp4", json=True))
    captured = capsys.readouterr()
    assert rc == 2
    # Must parse as exactly one JSON object — no log text mixed into stdout
    obj = json.loads(captured.out)
    assert obj["status"] == "failed"
