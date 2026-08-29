"""Cost estimates and the per-action cost ledger (design §4.2, G12).

Veo rates reuse ``VeoClient.estimate_cost`` so the sprite feature never
restates them. The Omni rate is a module constant that the implementer
verifies against the Google Gemini API pricing page on the day of
implementation; ``PRICE_TABLE_VERIFIED`` records that date. When no verified
rate exists the estimator returns ``None`` and the UI shows "unknown". The
config key ``sprite.price_overrides`` (config.json) lets the user correct any
rate without a release.

Verification note (2026-08-29): the Gemini API pricing page bills Omni Flash
video output per output token (5,792 tokens/sec of 720p video; $17.50 per 1M
output tokens under standard pricing), not per second. The page's own
"approximately $0.10 per second" note is a derived convenience figure, not a
stated per-second rate, so per Step 1 of the brief this counts as a
per-token price and the rate stays unverified.
"""
import logging
from typing import Dict, Optional, Tuple

from core.sprite.generation._common import now_iso
from core.sprite.project import ActionCard, CostEntry, GenerationSettings, SpriteProject
from core.sprite.timing import snap_duration

logger = logging.getLogger(__name__)

# Date the implementer verified the Omni rate below ("YYYY-MM-DD"), or
# "unverified" when no per-second rate could be confirmed.
PRICE_TABLE_VERIFIED = "unverified"
# USD per second of Gemini Omni video output. None = unknown; never a guess.
OMNI_USD_PER_SECOND: Optional[float] = None

PRICE_OVERRIDES_KEY = "sprite.price_overrides"


def _config_manager():
    """Late import so tests can substitute a fake reader."""
    from core.config import ConfigManager
    return ConfigManager()


def price_overrides() -> Dict[str, float]:
    """User rate overrides from config.json.

    Accepts a top-level ``"sprite.price_overrides"`` key or a nested
    ``{"sprite": {"price_overrides": {...}}}`` block. Keys are
    ``"<provider>"`` or ``"<provider>/<model>"``; values are USD per second.
    Non-numeric values are dropped with a logged warning.
    """
    try:
        config = _config_manager()
        raw = config.get(PRICE_OVERRIDES_KEY)
        if raw is None:
            sprite_block = config.get("sprite") or {}
            raw = sprite_block.get("price_overrides") if isinstance(sprite_block, dict) else None
    except Exception as exc:  # noqa: BLE001 - a broken config must not break estimates
        logger.warning("price_overrides: could not read config: %s", exc)
        return {}
    result: Dict[str, float] = {}
    for key, value in (raw or {}).items():
        try:
            result[str(key).strip().lower()] = float(value)
        except (TypeError, ValueError):
            logger.warning("price_overrides: ignoring non-numeric rate for %r: %r", key, value)
    return result


def _veo_rate(model: str, include_audio: bool) -> Optional[float]:
    from core.video.veo_client import VeoClient, VeoGenerationConfig, VeoModel
    try:
        veo_model = VeoModel(model) if model else VeoModel.VEO_3_1_GENERATE
    except ValueError:
        logger.warning("price_per_second: unknown Veo model %r", model)
        return None
    duration = 8  # legal for every Veo 3.1 model
    config = VeoGenerationConfig(model=veo_model, duration=duration, include_audio=include_audio)
    # estimate_cost reads only its config argument; a bare instance is enough.
    stub = VeoClient.__new__(VeoClient)
    return VeoClient.estimate_cost(stub, config) / duration


def price_per_second(provider: str, model: str, *, include_audio: bool) -> Optional[float]:
    """USD per second of generated video, or ``None`` when unknown."""
    name = (provider or "").strip().lower()
    model_id = (model or "").strip()
    overrides = price_overrides()
    for key in (f"{name}/{model_id.lower()}", name):
        if key in overrides:
            return overrides[key]
    if name == "veo":
        return _veo_rate(model_id, include_audio)
    if name == "omni":
        return OMNI_USD_PER_SECOND
    return None


def estimate_action(settings: GenerationSettings, action: ActionCard) -> Optional[float]:
    """Estimated USD for one action under ``settings``; ``None`` when unknown."""
    rate = price_per_second(settings.provider, settings.model, include_audio=settings.include_audio)
    if rate is None:
        return None
    try:
        seconds = snap_duration(action.duration_s, settings.provider, settings.model,
                                loop_conditioning=settings.loop_conditioning)
    except ValueError:
        return None
    return round(rate * seconds, 4)


def estimate_project(project: SpriteProject) -> Tuple[Optional[float], int]:
    """``(usd, unknown_count)`` over every action. ``usd`` is ``None`` when all are unknown."""
    total = 0.0
    unknown = 0
    for action in project.actions:
        value = estimate_action(project.generation, action)
        if value is None:
            unknown += 1
        else:
            total += value
    if project.actions and unknown == len(project.actions):
        return None, unknown
    return round(total, 4), unknown


def record_actual(project: SpriteProject, action: ActionCard, usd: Optional[float],
                  note: str = "", *, provider: Optional[str] = None,
                  model: Optional[str] = None, seconds: Optional[float] = None,
                  estimated_usd: Optional[float] = None) -> CostEntry:
    """Append a ledger row for ``action`` and copy ``usd`` onto its clip.

    Defaults come from ``action.clip`` (video route) or from the project's
    video settings. The keyword overrides let another route (image route,
    retouch) record its own provider, model, unit count, and estimate.
    """
    clip = action.clip
    if clip is not None:
        default_provider, default_model = clip.provider, clip.model
        default_seconds = float(clip.params.get("duration_s", action.duration_s))
        default_estimate = clip.estimated_usd
    else:
        default_provider, default_model = project.generation.provider, project.generation.model
        default_seconds = float(snap_duration(action.duration_s, default_provider, default_model,
                                              loop_conditioning=project.generation.loop_conditioning))
        default_estimate = estimate_action(project.generation, action)
    if provider is None:
        provider = default_provider
    if model is None:
        model = default_model
    if seconds is None:
        seconds = default_seconds
    if estimated_usd is None and provider == default_provider and model == default_model:
        estimated_usd = default_estimate
    entry = CostEntry(action_id=action.id, action_name=action.name, provider=provider,
                      model=model, seconds=float(seconds), estimated_usd=estimated_usd,
                      actual_usd=usd, timestamp=now_iso(), note=note)
    project.cost_ledger.append(entry)
    if clip is not None:
        clip.actual_usd = usd
    logger.info("Cost ledger: %s (%s/%s) %.1fs est=%s actual=%s %s",
                action.name, provider, model, seconds, estimated_usd, usd, note)
    return entry
