"""Video generation route: Omni / Veo configs, render, refine, loop trim (design §4.2).

Route A of the sprite pipeline. ``render_action`` dispatches on
``GenerationSettings.provider`` and returns a ``ClipRecord`` with a sidecar.

The ``core.video`` clients (and the ``google.genai`` SDK they import) are
loaded lazily, inside the functions that need them, so importing this
package does not pull ``google.genai`` (or Qt) into a process that never
renders a clip — see ``test_import_does_not_load_cloud_video_clients``.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from core.sprite.extract import extract_frames
from core.sprite.generation._common import emit, now_iso
from core.sprite.generation.cost import estimate_action, price_per_second
from core.sprite.generation.errors import ProviderError, classify_provider_error
from core.sprite.generation.prompts import inject_chroma, strip_render_terms
from core.sprite.pipeline import CancelToken, Cancelled, ProgressFn, no_progress
from core.sprite.project import ActionCard, ClipRecord, ExtractionSettings, GenerationSettings
from core.sprite.timing import legal_aspect_ratios, snap_duration

if TYPE_CHECKING:
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


def validate_generation_settings(settings: GenerationSettings) -> Optional[str]:
    """One user-facing message when ``settings`` cannot render, else ``None``.

    The queue calls this before it starts a worker. The provider configs keep
    their own checks; this one runs first so the user sees the problem before
    any card leaves the ``queued`` state.
    """
    provider = (settings.provider or "").strip().lower()
    try:
        legal = legal_aspect_ratios(provider, settings.model)
    except ValueError as exc:
        return f"{exc} Open Generation Settings to change it."
    if settings.aspect_ratio in legal:
        return None
    target = f"{provider}/{settings.model}" if settings.model else provider
    return (f"Aspect ratio {settings.aspect_ratio} is not supported by {target}. "
            f"Use one of {', '.join(legal)}. Open Generation Settings to change it.")


def omni_prompt(req: RenderRequest, duration_s: int) -> str:
    """Chroma-injected prompt with a plain-language duration hint (Omni has no duration field)."""
    base = inject_chroma(req.action.prompt, req.settings.plate_color, loop=req.action.loop)
    return f"{base}, about {duration_s} seconds long"


def build_omni_config(req: RenderRequest, *,
                      log: Callable[[str], None] = logger.info) -> OmniGenerationConfig:
    """Omni config: plate first, then turnaround refs, capped at three."""
    from core.video.omni_client import OmniClient, OmniGenerationConfig
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
    from core.video.veo_client import VeoClient, VeoGenerationConfig, VeoModel
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


# --- clients (module-level so tests can substitute them) ----------------------

def _make_omni_client(api_key: Optional[str]) -> OmniClient:
    from core.video.omni_client import OmniClient
    return OmniClient(api_key=api_key)


def _make_veo_client(api_key: Optional[str], auth_mode: str) -> VeoClient:
    from core.video.veo_client import VeoClient
    if auth_mode == "gcloud":
        return VeoClient(auth_mode="gcloud", project_id=os.environ.get("GOOGLE_CLOUD_PROJECT"))
    return VeoClient(api_key=api_key, auth_mode="api-key")


# --- sidecars -----------------------------------------------------------------

def clip_sidecar_path(mp4: Path) -> Path:
    """``clips/<id>.json`` beside ``clips/<id>.mp4`` (same shape as the video CLI)."""
    return Path(mp4).with_suffix(".json")


def write_clip_sidecar(mp4: Path, payload: Dict[str, Any]) -> Path:
    import json
    sidecar = clip_sidecar_path(mp4)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str),
                       encoding="utf-8")
    return sidecar


def clip_record_payload(record: ClipRecord) -> Dict[str, Any]:
    return {
        "path": str(record.path),
        "provider": record.provider,
        "model": record.model,
        "operation_id": record.operation_id,
        "params": dict(record.params),
        "prompt": record.prompt,
        "generated_at": record.generated_at,
        "estimated_usd": record.estimated_usd,
        "actual_usd": record.actual_usd,
    }


def _log_request(log: Callable[[str], None], provider: str, model: str,
                 params: Dict[str, Any], prompt: str, action: ActionCard) -> None:
    import json
    emit(logger, log, f"=== Video render request: action '{action.name}' ({action.id}) ===")
    emit(logger, log, f"provider={provider} model={model}")
    emit(logger, log, f"params={json.dumps(params, default=str)}")
    emit(logger, log, f"Prompt (FULL, {len(prompt)} chars):\n{prompt}")
    emit(logger, log, "=== END video render request ===")


# --- render -------------------------------------------------------------------

def render_action(req: RenderRequest, *, api_key: Optional[str], auth_mode: str = "api-key",
                  progress: ProgressFn = no_progress, token: Optional[CancelToken] = None,
                  log: Callable[[str], None] = logger.info) -> ClipRecord:
    """Render one action card to ``req.out_mp4`` and return its ``ClipRecord``.

    Raises ``Cancelled`` when the token fires (the sidecar keeps the provider
    operation id), or a classified ``SpriteGenerationError`` on failure.
    """
    provider = (req.settings.provider or "").strip().lower()
    action = req.action
    if token is not None:
        token.raise_if_cancelled()
    cancel_check = (lambda: token.cancelled) if token is not None else None
    out_mp4 = Path(req.out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    if provider == "omni":
        cfg = build_omni_config(req, log=log)
        model_id = cfg.model
        params: Dict[str, Any] = {
            "provider": "omni",
            "model": cfg.model,
            "aspect_ratio": cfg.aspect_ratio,
            "task": cfg.task,
            "reference_images": [str(p) for p in cfg.reference_images],
            "delivery": cfg.delivery,
            "duration_s": snap_duration(action.duration_s, "omni", req.settings.model),
            "loop": action.loop,
        }
    elif provider == "veo":
        cfg = build_veo_config(req, log=log)
        model_id = cfg.model.value
        params = dict(cfg.to_dict())
        params.pop("prompt", None)
        params.update({
            "provider": "veo",
            "model": model_id,
            "duration_s": cfg.duration,
            "image": str(cfg.image) if cfg.image else None,
            "last_frame": str(cfg.last_frame) if cfg.last_frame else None,
            "reference_images": [str(p) for p in (cfg.reference_images or [])],
            "loop_conditioning": bool(req.settings.loop_conditioning),
            "loop": action.loop,
            "auth_mode": auth_mode,
        })
    else:
        raise ProviderError(f"Unknown sprite video provider {provider!r}. Use 'omni' or 'veo'.")

    _log_request(log, provider, model_id, params, cfg.prompt, action)
    progress("render", 0, 0, f"{provider}: rendering '{action.name}'")

    operation_id: Optional[str] = None
    try:
        if provider == "omni":
            client = _make_omni_client(api_key)
            result = client.generate_video(cfg, out_mp4, cancel_check=cancel_check)
            operation_id = getattr(result, "interaction_id", None)
        else:
            client = _make_veo_client(api_key, auth_mode)
            result = client.generate_video(cfg, cancel_check=cancel_check)
            operation_id = getattr(result, "operation_id", None)
    except Exception as exc:  # noqa: BLE001 - classified below
        err = classify_provider_error(exc, provider=provider, operation_id=operation_id)
        emit(logger, log, f"Render of '{action.name}' failed: {err.user_message}", level="error")
        raise err from exc

    base_payload = {"action_id": action.id, "action_name": action.name, "provider": provider,
                    "model": model_id, "operation_id": operation_id, "params": params,
                    "prompt": cfg.prompt, "generated_at": now_iso()}
    if not result.success:
        if result.error == "cancelled":
            sidecar = write_clip_sidecar(out_mp4, {**base_payload, "status": "cancelled"})
            emit(logger, log, f"Render of '{action.name}' cancelled; {provider} operation "
                              f"{operation_id} keeps running remotely. Id saved in {sidecar}.",
                 level="warning")
            raise Cancelled(f"render of '{action.name}' cancelled; {provider} operation "
                            f"{operation_id} keeps running remotely")
        err = classify_provider_error(RuntimeError(result.error or "unknown provider failure"),
                                      provider=provider, operation_id=operation_id)
        write_clip_sidecar(out_mp4, {**base_payload, "status": "failed", "error": result.error})
        emit(logger, log, f"Render of '{action.name}' failed ({provider}/{model_id}): "
                          f"{err.user_message}", level="error")
        raise err

    import json
    emit(logger, log, f"=== Video render response ({provider}/{model_id}) ===")
    emit(logger, log, f"operation_id={operation_id} video_path={getattr(result, 'video_path', None)} "
                      f"video_url={getattr(result, 'video_url', None)} "
                      f"generation_time={getattr(result, 'generation_time', None)} "
                      f"has_synthid={getattr(result, 'has_synthid', None)}")
    emit(logger, log, f"metadata={json.dumps(getattr(result, 'metadata', {}) or {}, default=str)}")
    emit(logger, log, "=== END video render response ===")

    if provider == "veo":
        native = Path(result.video_path) if getattr(result, "video_path", None) else None
        if native is None or not native.exists():
            raise ProviderError("Veo reported success but saved no video file.",
                                operation_id=operation_id)
        if native.resolve() != out_mp4.resolve():
            shutil.copy2(native, out_mp4)
    if not out_mp4.exists():
        raise ProviderError(f"The provider reported success but {out_mp4} does not exist.",
                            operation_id=operation_id)

    record = ClipRecord(path=out_mp4, provider=provider, model=model_id,
                        operation_id=operation_id, params=params, prompt=cfg.prompt,
                        generated_at=base_payload["generated_at"],
                        estimated_usd=estimate_action(req.settings, action), actual_usd=None)
    write_clip_sidecar(out_mp4, {**clip_record_payload(record), "status": "completed",
                                 "action_id": action.id, "action_name": action.name})
    emit(logger, log, f"Clip saved: {out_mp4} (operation {operation_id}, "
                      f"estimated ${record.estimated_usd})")
    progress("render", 1, 1, f"{provider}: '{action.name}' rendered")
    return record


# --- refine (Omni conversational edit) ---------------------------------------

def refine_action(clip: ClipRecord, instruction: str, out_mp4: Path, *,
                  api_key: Optional[str],
                  log: Callable[[str], None] = logger.info) -> ClipRecord:
    """Conversational edit of an Omni clip via ``previous_interaction_id``."""
    from core.video.omni_client import OmniGenerationConfig
    if (clip.provider or "").lower() != "omni":
        raise ProviderError("Refine works only for Omni clips. Re-render Veo clips instead.")
    if not clip.operation_id:
        raise ProviderError("Refine needs the Omni interaction id of the clip, and this clip has none.")
    out_mp4 = Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    prompt = strip_render_terms(instruction)
    aspect = clip.params.get("aspect_ratio", "16:9")
    try:
        cfg = OmniGenerationConfig(prompt=prompt, model=clip.model, aspect_ratio=aspect,
                                   previous_interaction_id=clip.operation_id)
    except ValueError as exc:
        raise ProviderError(f"Omni refine settings are invalid: {exc}") from exc
    params = {**clip.params, "provider": "omni", "task": cfg.task,
              "previous_interaction_id": clip.operation_id, "refined_from": str(clip.path)}

    import json
    emit(logger, log, f"=== Omni refine request (previous interaction {clip.operation_id}) ===")
    emit(logger, log, f"model={cfg.model} params={json.dumps(params, default=str)}")
    emit(logger, log, f"Instruction (FULL, {len(prompt)} chars):\n{prompt}")

    try:
        client = _make_omni_client(api_key)
        result = client.generate_video(cfg, out_mp4)
    except Exception as exc:  # noqa: BLE001 - classified below
        err = classify_provider_error(exc, provider="omni", operation_id=clip.operation_id)
        emit(logger, log, f"Refine failed: {err.user_message}", level="error")
        raise err from exc
    if not result.success:
        err = classify_provider_error(RuntimeError(result.error or "unknown provider failure"),
                                      provider="omni", operation_id=getattr(result, "interaction_id", None))
        emit(logger, log, f"Refine failed: {err.user_message}", level="error")
        raise err

    seconds = float(clip.params.get("duration_s", 0) or 0)
    rate = price_per_second("omni", clip.model, include_audio=False)
    estimated = round(rate * seconds, 4) if (rate is not None and seconds) else None
    record = ClipRecord(path=out_mp4, provider="omni", model=cfg.model,
                        operation_id=getattr(result, "interaction_id", None), params=params,
                        prompt=prompt, generated_at=now_iso(), estimated_usd=estimated,
                        actual_usd=None)
    write_clip_sidecar(out_mp4, {**clip_record_payload(record), "status": "completed"})
    emit(logger, log, f"Refined clip saved: {out_mp4} (interaction {record.operation_id})")
    return record


# --- loop seam trim -----------------------------------------------------------

def _load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as img:
        return np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0


def seam_scores(frames: Sequence[Path]) -> List[float]:
    """Mean absolute RGB difference (0..1) between each frame and the first frame."""
    if not frames:
        return []
    first = _load_rgb(Path(frames[0]))
    scores: List[float] = []
    for path in frames:
        arr = _load_rgb(Path(path))
        if arr.shape != first.shape:
            with Image.open(path) as img:
                resized = img.convert("RGB").resize((first.shape[1], first.shape[0]), Image.BILINEAR)
                arr = np.asarray(resized, dtype=np.float32) / 255.0
        scores.append(float(np.abs(arr - first).mean()))
    return scores


def _best_index(scores: Sequence[float], search_from: float) -> int:
    start = max(1, int(len(scores) * search_from))
    start = min(start, len(scores) - 1)
    return min(range(start, len(scores)), key=lambda i: scores[i])


def find_loop_seam(frames: Sequence[Path], *, search_from: float = 0.5) -> Tuple[int, float]:
    """Index (and score) of the frame in the tail half that best matches frame 0."""
    scores = seam_scores(frames)
    if len(scores) < 2:
        return (len(scores) - 1, scores[-1] if scores else 1.0)
    index = _best_index(scores, search_from)
    return index, scores[index]


def _cut_video(src: Path, dst: Path, end_s: float) -> None:
    from core.video.ffmpeg_utils import get_ffmpeg_path
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        raise ProviderError("ffmpeg is required to trim a clip. Install ffmpeg first.")
    cmd = [ffmpeg, "-y", "-i", str(src), "-t", f"{end_s:.3f}",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(dst)]
    logger.info("trim_to_loop: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ProviderError(f"ffmpeg trim failed: {proc.stderr[-400:]}")


def trim_to_loop(clip: Path, out_mp4: Path, *,
                 seam_threshold: float = 0.08) -> Tuple[Path, float]:
    """Tail-trim ``clip`` at the frame that best matches its first frame.

    Returns ``(out_mp4, seam_score)``. When the last frame already matches
    within ``seam_threshold`` (or no better seam exists), the clip is copied
    unchanged and the tail score is returned.
    """
    clip = Path(clip)
    out_mp4 = Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    def _copy() -> None:
        if clip.resolve() != out_mp4.resolve():
            shutil.copy2(clip, out_mp4)

    with tempfile.TemporaryDirectory(prefix="sprite_seam_") as tmp:
        extracted = extract_frames(clip, Path(tmp), ExtractionSettings(mode="every_n", every_n=1))
        frames = list(extracted.frames)
        if not frames:
            raise ProviderError("No frames could be extracted for the loop seam search.")
        scores = seam_scores(frames)
        tail = scores[-1]
        if tail <= seam_threshold or len(frames) < 3:
            _copy()
            logger.info("trim_to_loop: tail seam %.3f within %.3f; no trim", tail, seam_threshold)
            return out_mp4, tail
        index = _best_index(scores, 0.5)
        best = scores[index]
        if index >= len(frames) - 1:
            _copy()
            logger.info("trim_to_loop: no better seam than the tail (%.3f)", tail)
            return out_mp4, tail
        if index <= 0:
            _copy()
            logger.info("trim_to_loop: seam found at frame 0; nothing to trim")
            return out_mp4, tail
        fps = float(extracted.source_fps or 24.0)
        # Exclusive cut: keep frames 0..index-1. Frame ``index`` is the one that
        # best matches frame 0, so including it would play a near-duplicate frame
        # immediately before the loop restarts at frame 0.
        end_s = index / fps
        _cut_video(clip, out_mp4, end_s)
        logger.info("trim_to_loop: cut at frame %d (%.3fs), seam %.3f (tail was %.3f)",
                    index, end_s, best, tail)
        return out_mp4, best
