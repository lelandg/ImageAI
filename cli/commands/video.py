"""CLI handler for single-clip video generation (Gemini Omni + Veo)."""
import json
import logging
import shutil
import sys
from pathlib import Path

from core import sanitize_filename
from cli.runner import resolve_api_key

logger = logging.getLogger("imageai.cli.video")

OMNI_MAX_REFS = 1
VEO_MAX_REFS = 3


class VideoCliError(Exception):
    """User-facing CLI validation error (maps to exit code 2)."""


def _emit(msg: str) -> None:
    """Human-facing progress/result line -> stderr (keeps stdout pure for --json)."""
    print(msg, file=sys.stderr)


def _derive_output(args) -> Path:
    """Resolve the output .mp4 path: -o if given, else a slug from the prompt."""
    out = getattr(args, "out", None)
    if out:
        return Path(out).expanduser()
    name = sanitize_filename((getattr(args, "prompt", None) or "video")[:60]) or "video"
    return Path.cwd() / f"{name}.mp4"


def _ref_images(args):
    """Reference image paths from repeated --ref-image (empty list if none)."""
    return [Path(p).expanduser() for p in (getattr(args, "ref_image", None) or [])]


def build_omni_config(args):
    """Map CLI args to an OmniGenerationConfig (raises VideoCliError on misuse)."""
    from core.video.omni_client import OmniGenerationConfig
    if getattr(args, "extend", None):
        raise VideoCliError("--extend is only supported with --video-provider veo.")
    if getattr(args, "last_frame", None):
        raise VideoCliError("--last-frame is only supported with --video-provider veo.")
    refs = _ref_images(args)
    if len(refs) > OMNI_MAX_REFS:
        raise VideoCliError(
            f"Gemini Omni supports {OMNI_MAX_REFS} reference image; got {len(refs)}."
        )
    kwargs = dict(
        prompt=getattr(args, "prompt", None) or "",
        task="image_to_video" if refs else "text_to_video",
        aspect_ratio=getattr(args, "aspect", None) or "16:9",
    )
    if getattr(args, "video_model", None):
        kwargs["model"] = args.video_model
    if refs:
        kwargs["reference_image"] = refs[0]
    try:
        return OmniGenerationConfig(**kwargs)  # __post_init__ validates aspect/task
    except ValueError as e:
        raise VideoCliError(str(e))


def _veo_model(args):
    """Resolve --video-model to a VeoModel enum (default: Veo 3.1 GA)."""
    from core.video.veo_client import VeoModel
    val = getattr(args, "video_model", None)
    if not val:
        return VeoModel.VEO_3_1_GENERATE
    try:
        return VeoModel(val)
    except ValueError:
        choices = ", ".join(m.value for m in VeoModel)
        raise VideoCliError(f"Unknown Veo model {val!r}. Choices: {choices}")


def build_veo_config(args):
    """Map CLI args to a VeoGenerationConfig (raises VideoCliError on misuse)."""
    from core.video.veo_client import VeoGenerationConfig
    refs = _ref_images(args)
    if len(refs) > VEO_MAX_REFS:
        raise VideoCliError(
            f"Veo supports up to {VEO_MAX_REFS} reference images; got {len(refs)}."
        )
    kwargs = dict(
        model=_veo_model(args),
        prompt=getattr(args, "prompt", None) or "",
        aspect_ratio=getattr(args, "aspect", None) or "16:9",
    )
    if refs:
        kwargs["reference_images"] = refs
    if getattr(args, "last_frame", None):
        kwargs["last_frame"] = Path(args.last_frame).expanduser()
    try:
        return VeoGenerationConfig(**kwargs)  # __post_init__ validates model/refs
    except ValueError as e:
        raise VideoCliError(str(e))


def _run_omni(args, out_path):
    """Generate via Gemini Omni; writes directly to out_path. Returns normalized dict."""
    from core.video.omni_client import OmniClient
    if getattr(args, "auth_mode", "api-key") == "gcloud":
        raise VideoCliError(
            "Gemini Omni supports api-key auth only (not --auth-mode gcloud)."
        )
    key, _src = resolve_api_key(
        getattr(args, "api_key", None), getattr(args, "api_key_file", None), "google")
    if not key:
        raise VideoCliError(
            "No Google API key found. Use --api-key/--api-key-file or set GOOGLE_API_KEY.")
    cfg = build_omni_config(args)
    _emit(f"[omni] generating video (aspect={cfg.aspect_ratio}, model={cfg.model})...")
    result = OmniClient(api_key=key).generate_video(cfg, out_path)
    return {
        "success": bool(result.success),
        "output_path": str(result.video_path or out_path),
        "provider": "omni",
        "model": cfg.model,
        "aspect_ratio": cfg.aspect_ratio,
        "operation_id": getattr(result, "interaction_id", None),
        "error": getattr(result, "error", None),
    }


def _run_veo(args, out_path):
    """Generate or extend via Veo; copies Veo's saved file to out_path. Returns dict."""
    import os
    from core.video.veo_client import VeoClient
    cfg = build_veo_config(args)
    if getattr(args, "auth_mode", "api-key") == "gcloud":
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            raise VideoCliError(
                "--auth-mode gcloud requires GOOGLE_CLOUD_PROJECT to be set.")
        client = VeoClient(auth_mode="gcloud", project_id=project_id)
    else:
        key, _src = resolve_api_key(
            getattr(args, "api_key", None), getattr(args, "api_key_file", None), "google")
        if not key:
            raise VideoCliError(
                "No Google API key found. Use --api-key/--api-key-file or set GOOGLE_API_KEY.")
        client = VeoClient(api_key=key, auth_mode="api-key")

    extend = getattr(args, "extend", None)
    if extend:
        prev = Path(extend).expanduser()
        if not prev.exists():
            raise VideoCliError(f"--extend video not found: {prev}")
        _emit(f"[veo] extending {prev.name} (model={cfg.model.value})...")
        result = client.extend_video(previous_video_path=prev,
                                     prompt=getattr(args, "prompt", None) or "", config=cfg)
    else:
        _emit(f"[veo] generating video (aspect={cfg.aspect_ratio}, model={cfg.model.value})...")
        result = client.generate_video(cfg)

    final_path = out_path
    if result.success and result.video_path and Path(result.video_path) != out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(result.video_path, out_path)
    elif not result.success:
        final_path = Path(result.video_path) if result.video_path else out_path

    return {
        "success": bool(result.success),
        "output_path": str(final_path),
        "provider": "veo",
        "model": cfg.model.value,
        "aspect_ratio": cfg.aspect_ratio,
        "operation_id": getattr(result, "operation_id", None),
        "error": getattr(result, "error", None),
    }


def _status_payload(result):
    """Normalized result dict -> the documented JSON/sidecar shape."""
    return {
        "status": "completed" if result.get("success") else "failed",
        "output_path": result.get("output_path"),
        "provider": result.get("provider"),
        "model": result.get("model"),
        "aspect_ratio": result.get("aspect_ratio"),
        "operation_id": result.get("operation_id"),
        "error": result.get("error"),
    }


def _write_sidecar(out_path, payload):
    """Write the JSON sidecar next to the .mp4 (best-effort; logs on failure)."""
    sidecar = out_path.with_suffix(".json")
    try:
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning("Could not write sidecar %s: %s", sidecar, e)


def _report(result, as_json, exit_code):
    """Emit the result (stdout JSON if as_json, else stderr text) and return exit_code."""
    payload = _status_payload(result)
    if as_json:
        print(json.dumps(payload), file=sys.stdout)
    elif result.get("success"):
        _emit(f"✅ Video saved: {result.get('output_path')}")
    else:
        _emit(f"❌ Video generation failed: {result.get('error')}")
    return exit_code


def run_video_cmd(args, config=None) -> int:
    """Generate a single video clip via Gemini Omni or Veo. Returns an exit code."""
    provider = (getattr(args, "video_provider", None) or "veo").strip().lower()
    as_json = bool(getattr(args, "json", False))
    out_path = _derive_output(args)

    def _fail(message, code):
        logger.error("Video CLI: %s", message)
        return _report({
            "success": False, "output_path": str(out_path), "provider": provider,
            "model": getattr(args, "video_model", None),
            "aspect_ratio": getattr(args, "aspect", None),
            "operation_id": None, "error": message,
        }, as_json, code)

    try:
        if provider == "omni":
            result = _run_omni(args, out_path)
        elif provider == "veo":
            result = _run_veo(args, out_path)
        else:
            return _fail(f"Unknown --video-provider {provider!r}. Choices: omni, veo.", 2)
    except VideoCliError as e:
        return _fail(str(e), 2)
    except Exception as e:  # noqa: BLE001 - surface + log any client/runtime failure
        logger.error("Video generation failed: %s", e, exc_info=True)
        return _fail(str(e), 3)

    _write_sidecar(out_path, _status_payload(result))
    return _report(result, as_json, 0 if result["success"] else 1)
