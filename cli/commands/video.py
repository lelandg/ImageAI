"""CLI handler for single-clip video generation (Gemini Omni + Veo)."""
import logging
import sys
from pathlib import Path

from core import sanitize_filename

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


def run_video_cmd(args, config=None) -> int:
    """Generate a single video clip via Gemini Omni or Veo. Returns an exit code."""
    # Full implementation lands in Tasks 2-4.
    _emit("Video CLI not yet implemented.")
    return 0
