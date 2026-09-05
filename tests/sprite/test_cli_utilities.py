"""Exercise utility outputs and install safeguards without installing packages."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cli.commands import sprite_utilities as utilities
from core.sprite.pipeline import CancelToken, Cancelled
from core.sprite.project import ActionCard, ClipRecord, SpriteProjectManager
from core.utils import sidecar_path


def invoke(operation, data=None, project=None, token=None):
    return utilities.execute_utility(operation, project, data or {}, log=lambda message: None,
                                     progress=lambda *args: None, token=token or CancelToken())


def test_status_reports_current_python_without_installing(monkeypatch):
    monkeypatch.setattr(utilities.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("install called"))
    result = invoke("ml-status")
    assert result["python"]["executable"] == sys.executable
    assert set(result["backends"]) == {"mediapipe", "rembg"}
    assert "onnxruntime" in result["modules"]
    assert result["installer"]["minimum_package_age_days"] == 7


@pytest.mark.parametrize("payload", [
    {"backends": ["mediapipe"]},
    {"backends": ["mediapipe"], "confirm": False},
    {"backends": ["arbitrary-package"], "confirm": True},
    {"backends": ["mediapipe", "mediapipe"], "confirm": True},
])
def test_install_requires_explicit_supported_selection(monkeypatch, payload):
    monkeypatch.setattr(utilities, "_run_install", lambda *args: pytest.fail("install called"))
    with pytest.raises(ValueError):
        invoke("ml-install", payload)


def test_install_refuses_system_python(monkeypatch):
    monkeypatch.setattr(utilities, "_virtual_environment", lambda: False)
    monkeypatch.setattr(utilities, "_run_install", lambda *args: pytest.fail("install called"))
    with pytest.raises(ValueError, match="virtual environment"):
        invoke("ml-install", {"backends": ["mediapipe"], "confirm": True})


def test_install_refuses_unavailable_age_aware_installer(monkeypatch):
    monkeypatch.setattr(utilities, "_virtual_environment", lambda: True)
    monkeypatch.setattr(utilities.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="unrestricted pip fallback is disabled"):
        invoke("ml-install", {"backends": ["mediapipe"], "confirm": True})


def test_install_refuses_unsupported_rembg_python(monkeypatch):
    monkeypatch.setattr(utilities, "_virtual_environment", lambda: True)
    monkeypatch.setattr(utilities.ml_install, "python_supports_rembg", lambda: False)
    with pytest.raises(ValueError, match="Python 3.11-3.13"):
        invoke("ml-install", {"backends": ["rembg"], "confirm": True})


def test_dry_run_targets_only_current_venv_with_seven_day_cutoff(monkeypatch):
    monkeypatch.setattr(utilities, "_virtual_environment", lambda: True)
    monkeypatch.setattr(utilities.shutil, "which", lambda name: "uv-test")
    monkeypatch.setattr(utilities, "_run_install", lambda *args: pytest.fail("dry run installed"))
    result = invoke("ml-install", {"backends": ["mediapipe"], "confirm": True, "dry_run": True})
    command = result["command"]
    assert command[command.index("--python") + 1] == sys.executable
    cutoff = datetime.fromisoformat(command[command.index("--exclude-newer") + 1])
    assert timedelta(days=7) <= datetime.now(timezone.utc) - cutoff < timedelta(days=7, seconds=10)
    assert "--no-python-downloads" in command
    assert "--no-config" in command
    assert result["packages"] == [utilities.ml_install.MEDIAPIPE_SPEC]
    assert utilities.ml_install.REMBG_SPEC not in command


def test_install_uses_selected_core_specs_and_checks_result(monkeypatch):
    commands = []
    monkeypatch.setattr(utilities, "_virtual_environment", lambda: True)
    monkeypatch.setattr(utilities.shutil, "which", lambda name: "uv-test")
    monkeypatch.setattr(utilities, "_run_install", lambda command, *args: commands.append(command))
    monkeypatch.setattr(utilities.matting, "available_backends", lambda: {"mediapipe": True, "rembg": False})
    result = invoke("ml-install", {"backends": ["mediapipe"], "confirm": True})
    assert len(commands) == 1
    assert result["restart_required"]
    assert not result["dry_run"]


def test_installer_exit_success_with_missing_module_is_failure(monkeypatch):
    monkeypatch.setattr(utilities, "_virtual_environment", lambda: True)
    monkeypatch.setattr(utilities.shutil, "which", lambda name: "uv-test")
    monkeypatch.setattr(utilities, "_run_install", lambda *args: None)
    monkeypatch.setattr(utilities.matting, "available_backends", lambda: {"mediapipe": False, "rembg": False})
    with pytest.raises(RuntimeError, match="still unavailable: mediapipe"):
        invoke("ml-install", {"backends": ["mediapipe"], "confirm": True})


def test_subprocess_sanitizes_install_redirects_and_reports_failures(monkeypatch):
    monkeypatch.setenv("PIP_TARGET", "not-the-current-environment")
    monkeypatch.setenv("UV_SYSTEM_PYTHON", "1")
    lines = []
    script = ("import os; assert 'PIP_TARGET' not in os.environ; "
              "assert 'UV_SYSTEM_PYTHON' not in os.environ; "
              "print('install diagnostic'); raise SystemExit(9)")
    with pytest.raises(RuntimeError, match="uv exit 9.*install diagnostic"):
        utilities._run_install([sys.executable, "-c", script], lines.append,
                               lambda *args: None, CancelToken())
    assert lines == ["install diagnostic"]


def clip_project(tmp_path, clip):
    project = SpriteProjectManager(tmp_path / "library").create_project("Key preview")
    action = ActionCard("idle", "idle", "")
    action.clip = ClipRecord(clip, "import", "", None, {}, "", "", None, None)
    project.actions = [action]
    project.save()
    return project


def test_real_key_preview_produces_video_and_metadata_without_changing_clip(tmp_path, synthetic_mp4):
    project = clip_project(tmp_path, synthetic_mp4)
    original_clip = synthetic_mp4.read_bytes()
    original_project = project.project_file().read_bytes()
    result = invoke("key-preview", {"actions": ["idle"]}, project)
    output = Path(result["output"])
    assert output.is_file() and output.stat().st_size > 0
    metadata = json.loads(sidecar_path(output).read_text(encoding="utf-8"))
    assert metadata["key_color"] == project.plate_color
    assert metadata["source"] == str(synthetic_mp4.resolve())
    assert synthetic_mp4.read_bytes() == original_clip
    assert project.project_file().read_bytes() == original_project


def test_failed_key_preview_preserves_previous_output(monkeypatch, tmp_path):
    clip = tmp_path / "source.mp4"
    clip.write_bytes(b"source")
    project = clip_project(tmp_path, clip)
    output = tmp_path / "accepted.mp4"
    output.write_bytes(b"accepted")

    def fail(_source, candidate, *_args):
        candidate.write_bytes(b"partial")
        raise RuntimeError("encoder failed")

    monkeypatch.setattr(utilities.keying, "ffmpeg_chromakey_preview", fail)
    with pytest.raises(RuntimeError, match="encoder failed"):
        invoke("key-preview", {"actions": ["idle"], "output": str(output)}, project)
    assert output.read_bytes() == b"accepted"


def test_key_preview_cannot_replace_clip_or_bypass_original_background(tmp_path):
    clip = tmp_path / "source.mp4"
    clip.write_bytes(b"source")
    project = clip_project(tmp_path, clip)
    with pytest.raises(ValueError, match="source clip"):
        invoke("key-preview", {"actions": ["idle"], "output": str(clip)}, project)
    project.background.mode = "original"
    with pytest.raises(ValueError, match="Original background"):
        invoke("key-preview", {"actions": ["idle"]}, project)


def test_cancelled_utility_does_not_start_installer(monkeypatch):
    monkeypatch.setattr(utilities, "_run_install", lambda *args: pytest.fail("install called"))
    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        invoke("ml-install", {"backends": ["mediapipe"], "confirm": True}, token=token)
