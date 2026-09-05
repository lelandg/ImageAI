"""Optional backend tools and the Sprite chromakey video preview, without a GUI."""
from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import logging
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

from core.sprite import keying, matting, ml_install
from core.sprite.generation._common import redact_secrets
from core.sprite.pipeline import check, list_frames, stage_dir
from core.utils import sidecar_path, write_image_sidecar

logger = logging.getLogger(__name__)
UTILITY_OPERATIONS = ("key-preview", "ml-status", "ml-install")


def _virtual_environment():
    return sys.prefix != sys.base_prefix or hasattr(sys, "real_prefix")


def _module_status(module, distribution):
    try:
        available = module in sys.modules or importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        available = False
    try:
        version = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        version = None
    return {"available": available, "version": version, "distribution": distribution}


def _ml_status():
    specs, _index = ml_install.sprite_ml_packages()
    return {
        "python": {"executable": sys.executable, "version": sys.version.split()[0],
                   "environment": sys.prefix, "virtual_environment": _virtual_environment()},
        "backends": matting.available_backends(),
        "modules": {name: _module_status(name, distribution) for name, distribution in (
            ("mediapipe", "mediapipe"), ("rembg", "rembg"), ("onnxruntime", "onnxruntime"),
            ("cv2", "opencv-python"), ("numpy", "numpy"), ("PIL", "Pillow"))},
        "rembg_python_supported": ml_install.python_supports_rembg(),
        "rembg_models": matting.REMBG_MODELS,
        "installable_packages": specs,
        "installer": {"uv": shutil.which("uv"), "minimum_package_age_days": 7,
                      "requires_virtual_environment": True},
        "files": [],
    }


def _install_command(backends):
    if not _virtual_environment():
        raise ValueError("ML installation requires a virtual environment; run ImageAI with its .venv Python")
    if "rembg" in backends and not ml_install.python_supports_rembg():
        raise ValueError("rembg requires Python 3.11-3.13; this interpreter is unsupported")
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("The age-aware uv installer is unavailable. Install uv, then retry ml-install; "
                           "unrestricted pip fallback is disabled")
    available, _index = ml_install.sprite_ml_packages()
    packages = [spec for spec in available
                if spec.split("[", 1)[0].split(">", 1)[0] in backends]
    if len(packages) != len(backends):
        raise ValueError("A selected ML backend is not supported by this interpreter")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec="seconds")
    return [uv, "pip", "install", "--python", sys.executable, "--exclude-newer", cutoff,
            "--no-python-downloads", "--no-progress", "--no-config",
            "--default-index", "https://pypi.org/simple", *packages], packages


def _run_install(command, log, progress, token):
    # Ignore installer environment overrides that could redirect a venv install
    # or select an unreviewed index. No credentials are included in the command.
    environment = {name: value for name, value in os.environ.items()
                   if not name.upper().startswith(("UV_", "PIP_"))}
    environment["PYTHONNOUSERSITE"] = "1"
    messages = queue.Queue()
    tail = deque(maxlen=8)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace", env=environment)

    def receive():
        assert process.stdout is not None
        try:
            for line in process.stdout:
                messages.put(line.rstrip())
        finally:
            messages.put(None)

    reader = threading.Thread(target=receive, daemon=True)
    reader.start()
    try:
        ended = False
        while not ended or process.poll() is None:
            check(token)
            try:
                line = messages.get(timeout=0.1)
            except queue.Empty:
                continue
            if line is None:
                ended = True
            elif line:
                clean = redact_secrets(line)
                tail.append(clean)
                log(clean)
                progress("ml-install", 0, 0, clean)
        code = process.wait()
        if code:
            raise RuntimeError(f"ML installation failed (uv exit {code}): " + "\n".join(tail))
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        reader.join(timeout=2)
        if process.stdout is not None:
            process.stdout.close()


def _ml_install(data, log, progress, token):
    command, packages = _install_command(data["backends"])
    result = {"backends": data["backends"], "packages": packages, "command": command,
              "python": sys.executable, "minimum_package_age_days": 7,
              "dry_run": data.get("dry_run", False), "files": []}
    if result["dry_run"]:
        return result
    check(token)
    log(f"Installing Sprite ML backends into {sys.executable}: {', '.join(packages)}")
    progress("ml-install", 0, len(packages), "Installing packages at least seven days old")
    _run_install(command, log, progress, token)
    importlib.invalidate_caches()
    detected = matting.available_backends()
    missing = [name for name in data["backends"] if not detected[name]]
    if missing:
        raise RuntimeError("Installer completed but these modules are still unavailable: " + ", ".join(missing))
    progress("ml-install", len(packages), len(packages), "done")
    result.update(available_backends=detected, restart_required=True)
    return result


def _sample_color(project, action, tolerance, log):
    frames = list_frames(stage_dir(project, action, "extract"))
    if not frames:
        return None
    try:
        with Image.open(frames[0]) as image:
            estimate = keying.estimate_key_color(image, tolerance=tolerance)
    except (OSError, ValueError) as exc:
        message = f"Cannot sample chromakey preview color from {frames[0]}: {exc}"
        logger.warning(message)
        log(message)
        return None
    return estimate.color if estimate.uniformity >= keying.KEY_AUTO_MIN_UNIFORMITY else None


def _key_preview(project, data, log, progress, token):
    from cli.commands.sprite_generation import select_actions

    if project is None or project.project_dir is None:
        raise ValueError("key-preview requires a saved Sprite project")
    if project.background.mode == "original":
        raise ValueError("Original background skips chromakey; use preview for the preserved frames")
    action = select_actions(project, data["actions"], single=True)[0]
    if action.clip is None or not action.clip.path.is_file():
        raise ValueError("Render or import a video clip before key-preview")
    source = action.clip.path.resolve()
    tolerance = data.get("tolerance", project.key.tolerance)
    softness = data.get("softness", project.key.softness)
    color = (data.get("key_color") or project.key.key_color or
             _sample_color(project, action, tolerance, log) or project.plate_color)
    keying.parse_key_color(color, context="chromakey preview")
    default = project.project_dir / "exports" / "previews" / f"{action.id}_chromakey.mp4"
    output = Path(data.get("output", default)).expanduser().resolve()
    if output.suffix.lower() != ".mp4":
        raise ValueError("key-preview output must have an .mp4 extension")
    if output == source:
        raise ValueError("key-preview output must not replace its source clip")
    check(token)
    output.parent.mkdir(parents=True, exist_ok=True)
    progress("key-preview", 0, 1, f"Previewing {action.name} with {color}")
    with tempfile.TemporaryDirectory(prefix=".key-preview-", dir=output.parent) as directory:
        candidate = Path(directory) / output.name
        keying.ffmpeg_chromakey_preview(source, candidate, color, tolerance, softness)
        if not candidate.is_file() or not candidate.stat().st_size:
            raise RuntimeError("Chromakey preview produced no video")
        check(token)
        metadata = {"kind": "sprite_chromakey_preview", "source": str(source),
                    "action": action.id, "key_color": color,
                    "tolerance": max(0.01, tolerance), "softness": softness,
                    "background": "#7F7F7F", "audio": False}
        write_image_sidecar(candidate, metadata)
        if not sidecar_path(candidate).is_file():
            raise RuntimeError("Could not write chromakey preview metadata")
        os.replace(candidate, output)
        os.replace(sidecar_path(candidate), sidecar_path(output))
    log(f"Wrote chromakey preview {output}")
    progress("key-preview", 1, 1, "done")
    return {**metadata, "files": [str(output), str(sidecar_path(output))], "output": str(output)}


def execute_utility(operation, project, data, *, log, progress, token):
    """Execute utility operations; status and installation do not need a project."""
    from cli.sprite_schema import schemas, validate

    try:
        if operation not in UTILITY_OPERATIONS:
            raise ValueError(f"Unknown Sprite utility operation: {operation}")
        validate(data, schemas()[operation])
        check(token)
        if operation == "ml-status":
            return _ml_status()
        if operation == "key-preview":
            return _key_preview(project, data, log, progress, token)
        return _ml_install(data, log, progress, token)
    except Exception as exc:
        logger.error("Sprite %s failed: %s", operation, redact_secrets(str(exc)))
        raise
