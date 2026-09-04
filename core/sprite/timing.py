"""Clip timing hints for the sprite feature (design §4.2).

Pure arithmetic. Provider duration tables are read from the video clients
at call time so the sprite feature never restates them.
"""
import logging
import math
from functools import reduce
from typing import List, Sequence, Tuple

from core.sprite.project import ExtractionSettings

logger = logging.getLogger(__name__)

DEFAULT_FPS = 12
MAX_FPS = 60


def loop_seconds(target_frames: int, fps: int) -> float:
    """Seconds one loop of ``target_frames`` takes at ``fps``."""
    if fps <= 0:
        raise ValueError(f"fps must be positive, got {fps}")
    return target_frames / float(fps)


def legal_durations(provider: str, model: str) -> Tuple[int, ...]:
    """Integer clip durations the provider accepts for ``model``."""
    name = (provider or "").strip().lower()
    if name == "veo":
        from core.video.veo_client import VeoModel
        if not model or model == VeoModel.VEO_3_1_GENERATE.value:
            return (8,)
        if model == VeoModel.VEO_3_1_FAST.value:
            return (4, 6, 8)
        return (8,)
    if name == "omni":
        from core.video.omni_client import OmniClient
        low, high = OmniClient.MODEL_CONSTRAINTS["duration_range"]
        return tuple(range(int(low), int(high) + 1))
    raise ValueError(f"Unknown sprite video provider {provider!r}. Use 'omni' or 'veo'.")


def legal_aspect_ratios(provider: str, model: str) -> Tuple[str, ...]:
    """Aspect ratios the provider accepts for ``model``.

    Veo: an empty or unknown model id falls back to the standard model's
    list, the same way ``legal_durations`` does.
    """
    name = (provider or "").strip().lower()
    if name == "veo":
        from core.video.veo_client import VeoClient, VeoModel
        try:
            veo_model = VeoModel(model) if model else VeoModel.VEO_3_1_GENERATE
        except ValueError:
            veo_model = VeoModel.VEO_3_1_GENERATE
        constraints = VeoClient.MODEL_CONSTRAINTS.get(veo_model) \
            or VeoClient.MODEL_CONSTRAINTS[VeoModel.VEO_3_1_GENERATE]
        return tuple(constraints["aspect_ratios"])
    if name == "omni":
        from core.video.omni_client import OmniClient
        return tuple(OmniClient.MODEL_CONSTRAINTS["aspect_ratios"])
    raise ValueError(f"Unknown sprite video provider {provider!r}. Use 'omni' or 'veo'.")


def suggest_clip_duration(target_frames: int, fps: int, provider: str, model: str) -> int:
    """Shortest legal duration that holds at least two loops, else the longest."""
    needed = 2.0 * loop_seconds(target_frames, fps)
    legal = legal_durations(provider, model)
    candidates = [d for d in legal if d >= needed]
    chosen = min(candidates) if candidates else max(legal)
    logger.debug("suggest_clip_duration: %d frames @ %d fps needs %.2fs -> %ds (%s/%s)",
                 target_frames, fps, needed, chosen, provider, model)
    return chosen


def snap_duration(duration_s: int, provider: str, model: str, *,
                  loop_conditioning: bool = False) -> int:
    """Nearest legal duration. Veo loop conditioning (first+last frame) forces 8 s."""
    if (provider or "").strip().lower() == "veo" and loop_conditioning:
        return 8
    legal = legal_durations(provider, model)
    return min(legal, key=lambda d: (abs(d - duration_s), -d))


def frames_per_clip(duration_s: float, source_fps: float, settings: ExtractionSettings) -> int:
    """Frames the extractor will produce from a clip of ``duration_s``."""
    effective = max(0.0, float(duration_s) - settings.trim_start_s - settings.trim_end_s)
    total = int(round(effective * source_fps))
    if settings.mode == "every_n":
        step = max(1, int(settings.every_n))
        return int(math.ceil(total / step)) if total else 0
    if settings.mode == "target_fps":
        return int(round(effective * settings.target_fps))
    if settings.mode == "exact_n":
        return int(settings.exact_n)
    raise ValueError(f"Unknown extraction mode {settings.mode!r}")


def ms_to_fps(durations_ms: Sequence[int]) -> Tuple[int, List[float]]:
    """GCD-based frame rate plus per-frame multipliers.

    Returns ``(fps, multipliers)`` where ``multiplier[i] * (1000 / fps)``
    reproduces ``durations_ms[i]``. Multipliers are integers when the
    durations share an exact base; otherwise they carry the rounding drift,
    which is also logged.
    """
    values = [max(1, int(d)) for d in durations_ms]
    if not values:
        return DEFAULT_FPS, []
    base = reduce(math.gcd, values)
    fps = int(round(1000.0 / base))
    fps = max(1, min(MAX_FPS, fps))
    multipliers = [d * fps / 1000.0 for d in values]
    drift = max(abs(m - round(m)) for m in multipliers)
    if drift > 1e-6:
        logger.info("ms_to_fps: base %d ms -> %d fps; rounding drift %.3f frame", base, fps, drift)
    return fps, multipliers
