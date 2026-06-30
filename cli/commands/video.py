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


def run_video_cmd(args, config=None) -> int:
    """Generate a single video clip via Gemini Omni or Veo. Returns an exit code."""
    # Full implementation lands in Tasks 2-4.
    _emit("Video CLI not yet implemented.")
    return 0
