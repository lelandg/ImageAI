"""Video generation route: Omni / Veo configs, render, refine, loop trim (design §4.2).

Route A of the sprite pipeline. ``render_action`` dispatches on
``GenerationSettings.provider`` and returns a ``ClipRecord`` with a sidecar.
"""
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from core.sprite.extract import extract_frames
from core.sprite.generation._common import emit, now_iso
from core.sprite.generation.cost import estimate_action, price_per_second
from core.sprite.generation.errors import ProviderError, classify_provider_error
from core.sprite.generation.prompts import inject_chroma
from core.sprite.pipeline import CancelToken, Cancelled, ProgressFn, no_progress
from core.sprite.project import ActionCard, ClipRecord, ExtractionSettings, GenerationSettings
from core.sprite.timing import snap_duration
from core.video.omni_client import OmniClient, OmniGenerationConfig
from core.video.veo_client import VeoClient, VeoGenerationConfig, VeoModel

logger = logging.getLogger(__name__)

MAX_REFERENCE_IMAGES = 3  # both Omni and Veo 3.1 accept at most three


@dataclass
class RenderRequest:
    action: ActionCard
    plate: Path
    refs: List[Path]
    settings: GenerationSettings
    out_mp4: Path


def omni_prompt(req: RenderRequest, duration_s: int) -> str:
    """Chroma-injected prompt with a plain-language duration hint (Omni has no duration field)."""
    base = inject_chroma(req.action.prompt, req.settings.plate_color, loop=req.action.loop)
    return f"{base}, about {duration_s} seconds long"


def build_omni_config(req: RenderRequest, *,
                      log: Callable[[str], None] = logger.info) -> OmniGenerationConfig:
    """Omni config: plate first, then turnaround refs, capped at three."""
    duration = snap_duration(req.action.duration_s, "omni", req.settings.model)
    if duration != req.action.duration_s:
        emit(logger, log, f"Omni: duration {req.action.duration_s}s snapped to {duration}s "
                          f"(legal range {OmniClient.MODEL_CONSTRAINTS['duration_range']})")
    refs = [Path(req.plate)] + [Path(p) for p in req.refs]
    refs = refs[:MAX_REFERENCE_IMAGES]
    if len(req.refs) + 1 > MAX_REFERENCE_IMAGES:
        emit(logger, log, f"Omni: {len(req.refs)} reference image(s) plus the plate exceed "
                          f"{MAX_REFERENCE_IMAGES}; using the first {MAX_REFERENCE_IMAGES - 1} refs")
    kwargs: Dict[str, Any] = dict(prompt=omni_prompt(req, duration),
                                  aspect_ratio=req.settings.aspect_ratio,
                                  reference_images=refs)
    if req.settings.model:
        kwargs["model"] = req.settings.model
    try:
        return OmniGenerationConfig(**kwargs)
    except ValueError as exc:
        raise ProviderError(f"Omni settings are invalid: {exc}") from exc


def build_veo_config(req: RenderRequest, *,
                     log: Callable[[str], None] = logger.info) -> VeoGenerationConfig:
    """Veo config. Loop conditioning sets image=last_frame=plate and forces 8 s."""
    model_id = req.settings.model or VeoModel.VEO_3_1_GENERATE.value
    try:
        model = VeoModel(model_id)
    except ValueError as exc:
        choices = ", ".join(m.value for m in VeoModel)
        raise ProviderError(f"Unknown Veo model {model_id!r}. Choices: {choices}") from exc

    loop_conditioning = bool(req.settings.loop_conditioning)
    duration = snap_duration(req.action.duration_s, "veo", model.value,
                             loop_conditioning=loop_conditioning)
    if loop_conditioning:
        emit(logger, log, f"Veo: loop conditioning is on; the plate is the first and the last "
                          f"frame, so the clip duration is forced to 8s (requested "
                          f"{req.action.duration_s}s). Veo FIRST&LAST only works at 8s.")
    elif duration != req.action.duration_s:
        emit(logger, log, f"Veo: duration {req.action.duration_s}s snapped to {duration}s "
                          f"for {model.value}")

    allowed = VeoClient.MODEL_CONSTRAINTS[model]["resolutions"]
    resolution = req.settings.resolution
    if resolution not in allowed:
        emit(logger, log, f"Veo: resolution {resolution} not supported by {model.value}; "
                          f"using {allowed[0]}")
        resolution = allowed[0]

    refs = [Path(p) for p in req.refs][:MAX_REFERENCE_IMAGES]
    prompt = inject_chroma(req.action.prompt, req.settings.plate_color, loop=req.action.loop)
    try:
        return VeoGenerationConfig(
            model=model,
            prompt=prompt,
            aspect_ratio=req.settings.aspect_ratio,
            resolution=resolution,
            duration=duration,
            fps=req.settings.fps,
            include_audio=bool(req.settings.include_audio),
            image=Path(req.plate) if loop_conditioning else None,
            last_frame=Path(req.plate) if loop_conditioning else None,
            reference_images=refs or None,
        )
    except ValueError as exc:
        raise ProviderError(f"Veo settings are invalid: {exc}") from exc
