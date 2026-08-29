"""Frame extraction from video clips via ffmpeg (design section 4.1).

Modes: ``every_n`` keeps one frame in N; ``target_fps`` resamples with the
``fps`` filter; ``exact_n`` extracts every frame to a temp dir, then keeps N
evenly spaced frames. Output is ``0001.png``, ``0002.png``, ... in ``out_dir``.
"""

from __future__ import annotations

import json
import logging
import math
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

from .pipeline import CancelToken, Cancelled, ProgressFn, check, no_progress
from .project import ExtractionSettings

logger = logging.getLogger(__name__)

FFMPEG_TIMEOUT_S = 600
STDERR_TAIL = 800
FFMPEG_POLL_S = 0.15


class FFmpegError(Exception):
    """ffmpeg/ffprobe failed. ``user_message`` is safe to show in the UI."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


@dataclass
class ExtractResult:
    frames: List[Path]
    source_fps: float
    source_frames: int
    duration_s: float


def _ffmpeg() -> str:
    # Imported here on purpose: core.video's package import pulls in the
    # cloud video clients (several seconds); the GUI tab and CLI must not pay
    # that on ``import core.sprite``.
    from core.video.ffmpeg_utils import get_ffmpeg_path

    path = get_ffmpeg_path()
    if not path:
        raise FFmpegError("ffmpeg is not available. Install ffmpeg or the imageio-ffmpeg package.")
    return path


def _ffprobe() -> Optional[str]:
    from core.video.ffmpeg_utils import get_ffmpeg_manager

    manager = get_ffmpeg_manager()
    if manager.ffprobe_path:
        return manager.ffprobe_path
    if manager.ffmpeg_path:
        sibling = Path(manager.ffmpeg_path).parent / "ffprobe"
        if sibling.exists():
            return str(sibling)
    found = shutil.which("ffprobe")
    return found


def _parse_rate(text: str) -> float:
    if not text or text == "0/0":
        return 0.0
    if "/" in text:
        num, den = text.split("/", 1)
        try:
            return float(num) / float(den) if float(den) else 0.0
        except ValueError:
            return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _probe_with_ffprobe(ffprobe: str, path: Path) -> Dict[str, Any]:
    cmd = [ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    logger.info(f"ffprobe: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise FFmpegError(f"ffprobe failed on {path.name}: {result.stderr[-STDERR_TAIL:]}")
    data = json.loads(result.stdout or "{}")
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if video is None:
        raise FFmpegError(f"No video stream in {path.name}")
    fps = _parse_rate(str(video.get("avg_frame_rate") or video.get("r_frame_rate") or ""))
    duration = 0.0
    for holder in (video, data.get("format", {})):
        try:
            duration = float(holder.get("duration"))
            if duration > 0:
                break
        except (TypeError, ValueError):
            continue
    try:
        nb_frames = int(video.get("nb_frames"))
    except (TypeError, ValueError):
        nb_frames = int(round(duration * fps)) if fps else 0
    return {
        "fps": fps,
        "nb_frames": nb_frames,
        "duration": duration,
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "source": "ffprobe",
    }


def _probe_with_opencv(path: Path) -> Dict[str, Any]:
    import cv2

    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise FFmpegError(f"Cannot open video: {path}")
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        nb_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    finally:
        cap.release()
    duration = nb_frames / fps if fps else 0.0
    return {"fps": fps, "nb_frames": nb_frames, "duration": duration,
            "width": width, "height": height, "source": "opencv"}


def probe_video(path: Path) -> Dict[str, Any]:
    """Return fps, nb_frames, duration, width, height for a video.

    Uses ffprobe when one is installed. The imageio-ffmpeg package ships no
    ffprobe, so the fallback reads the same numbers through OpenCV.
    """
    path = Path(path)
    if not path.exists():
        raise FFmpegError(f"Video not found: {path}")
    ffprobe = _ffprobe()
    if ffprobe:
        try:
            return _probe_with_ffprobe(ffprobe, path)
        except (FFmpegError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
            logger.warning(f"ffprobe failed ({exc}); falling back to OpenCV")
    return _probe_with_opencv(path)


def _usable_span(probe: Dict[str, Any], settings: ExtractionSettings) -> float:
    duration = float(probe.get("duration") or 0.0)
    span = duration - max(0.0, settings.trim_start_s) - max(0.0, settings.trim_end_s)
    return max(0.0, span)


def estimate_frame_count(probe: Dict[str, Any], settings: ExtractionSettings) -> int:
    """Predict how many frames ``extract_frames`` will write."""
    fps = float(probe.get("fps") or 0.0)
    span = _usable_span(probe, settings)
    if span <= 0 or fps <= 0:
        return 0
    in_range = max(1, int(round(span * fps)))
    if settings.mode == "every_n":
        return math.ceil(in_range / max(1, settings.every_n))
    if settings.mode == "target_fps":
        return max(1, int(round(span * max(1, settings.target_fps))))
    if settings.mode == "exact_n":
        return min(max(1, settings.exact_n), in_range)
    raise ValueError(f"Unknown extraction mode: {settings.mode!r}")


def _terminate(proc: subprocess.Popen) -> None:
    """Best-effort stop of a still-running ffmpeg process."""
    proc.terminate()
    try:
        proc.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            pass


def _run_ffmpeg(cmd: List[str], token: Optional[CancelToken] = None) -> None:
    """Run ffmpeg, polling ``token`` so a cancel stops the subprocess promptly.

    Uses ``Popen`` + a ``communicate(timeout=...)`` poll loop rather than a
    single blocking ``subprocess.run`` so a mid-run cancel does not have to
    wait for ffmpeg to finish (up to ``FFMPEG_TIMEOUT_S``). Retrying
    ``communicate()`` after a ``TimeoutExpired`` is safe and loses no output
    (documented ``subprocess`` behaviour since Python 3.3) and avoids the
    pipe-fills-up deadlock a bare ``proc.wait()`` poll loop would risk.
    """
    logger.info(f"ffmpeg: {' '.join(cmd)}")
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except OSError as exc:
        raise FFmpegError(f"ffmpeg could not start: {exc}") from exc

    start = time.monotonic()
    stderr = ""
    while True:
        try:
            _, stderr = proc.communicate(timeout=FFMPEG_POLL_S)
            break
        except subprocess.TimeoutExpired:
            pass
        if token is not None and token.cancelled:
            _terminate(proc)
            raise Cancelled()
        if time.monotonic() - start > FFMPEG_TIMEOUT_S:
            _terminate(proc)
            raise FFmpegError(f"ffmpeg timed out after {FFMPEG_TIMEOUT_S}s")

    if proc.returncode != 0:
        tail = (stderr or "").strip()[-STDERR_TAIL:]
        raise FFmpegError(f"ffmpeg failed (exit {proc.returncode}): {tail}")


def _renumber(paths: List[Path], out_dir: Path) -> List[Path]:
    """Move ``paths`` into ``out_dir`` as 0001.png, 0002.png, ..."""
    out_dir.mkdir(parents=True, exist_ok=True)
    staged: List[Path] = []
    for index, src in enumerate(paths, start=1):
        tmp = out_dir / f".tmp_{index:04d}.png"
        shutil.move(str(src), str(tmp))
        staged.append(tmp)
    final: List[Path] = []
    for index, tmp in enumerate(staged, start=1):
        dest = out_dir / f"{index:04d}.png"
        tmp.replace(dest)
        final.append(dest)
    return final


def cull_duplicates(frames: List[Path], threshold: float) -> List[Path]:
    """Drop frames whose mean absolute RGB difference to the last kept frame is < threshold.

    ``threshold`` is on a 0..1 scale. The first frame is always kept. Files
    are not deleted; the caller decides what to do with the dropped paths.
    """
    kept: List[Path] = []
    last: Optional[np.ndarray] = None
    for path in frames:
        with Image.open(path) as im:
            arr = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
        if last is not None and arr.shape == last.shape:
            if float(np.mean(np.abs(arr - last))) < threshold:
                continue
        kept.append(path)
        last = arr
    return kept


def extract_frames(video: Path, out_dir: Path, settings: ExtractionSettings, *,
                   progress: ProgressFn = no_progress,
                   token: Optional[CancelToken] = None) -> ExtractResult:
    """Extract frames from ``video`` into ``out_dir`` per ``settings``."""
    video = Path(video)
    out_dir = Path(out_dir)
    ffmpeg = _ffmpeg()
    probe = probe_video(video)
    span = _usable_span(probe, settings)
    check(token)
    progress("extract", 0, 0, f"extract: probing {video.name}")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    cmd: List[str] = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    if settings.trim_start_s > 0:
        cmd += ["-ss", f"{settings.trim_start_s:.3f}"]
    cmd += ["-i", str(video)]
    if settings.trim_end_s > 0 and span > 0:
        cmd += ["-t", f"{span:.3f}"]

    if settings.mode == "every_n":
        n = max(1, int(settings.every_n))
        cmd += ["-vf", f"select=not(mod(n\\,{n}))", "-fps_mode", "vfr", str(out_dir / "%04d.png")]
        _run_ffmpeg(cmd, token)
        frames = sorted(out_dir.glob("*.png"))
    elif settings.mode == "target_fps":
        cmd += ["-vf", f"fps={max(1, int(settings.target_fps))}", str(out_dir / "%04d.png")]
        _run_ffmpeg(cmd, token)
        frames = sorted(out_dir.glob("*.png"))
    elif settings.mode == "exact_n":
        n = max(1, int(settings.exact_n))
        temp = Path(tempfile.mkdtemp(prefix="extract_all_", dir=out_dir.parent))
        try:
            cmd += [str(temp / "%04d.png")]
            _run_ffmpeg(cmd, token)
            everything = sorted(temp.glob("*.png"))
            count = len(everything)
            if count == 0:
                raise FFmpegError(f"ffmpeg produced no frames from {video.name}")
            n_eff = min(n, count)
            if n_eff == 1 or count == 1:
                picks = [0]
            else:
                picks = sorted({int(round(i * (count - 1) / (n_eff - 1))) for i in range(n_eff)})
            frames = _renumber([everything[i] for i in picks], out_dir)
        finally:
            shutil.rmtree(temp, ignore_errors=True)
    else:
        raise ValueError(f"Unknown extraction mode: {settings.mode!r}")

    check(token)
    if not frames:
        raise FFmpegError(f"ffmpeg produced no frames from {video.name}")

    if settings.cull_duplicates and len(frames) > 1:
        kept = cull_duplicates(frames, settings.duplicate_threshold)
        if len(kept) != len(frames):
            for path in frames:
                if path not in kept:
                    path.unlink()
            frames = _renumber(kept, out_dir)

    progress("extract", len(frames), len(frames), f"extract: {len(frames)} frames")
    return ExtractResult(
        frames=frames,
        source_fps=float(probe.get("fps") or 0.0),
        source_frames=int(probe.get("nb_frames") or 0),
        duration_s=float(probe.get("duration") or 0.0),
    )
