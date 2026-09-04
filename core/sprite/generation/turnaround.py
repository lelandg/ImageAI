"""Character turnaround pack: front / side / back / three-quarter (design §4.2).

Each view is an image edit of the character on the plate color. The views
serve as reference images for every video render so the character stays
consistent across clips.
"""
import io
import logging
from pathlib import Path
from typing import Callable, Dict, Optional, Sequence

from PIL import Image

from core.sprite.generation._common import emit, now_iso
from core.sprite.generation.errors import ProviderError, classify_provider_error
from core.sprite.generation.prompts import color_name, normalize_hex
from core.sprite.pipeline import CancelToken
from core.utils import write_image_sidecar

logger = logging.getLogger(__name__)

VIEWS = ("front", "side", "back", "three_quarter")

VIEW_PHRASES: Dict[str, str] = {
    "front": "front view, facing the camera",
    "side": "side profile view, facing right",
    "back": "back view, facing away from the camera",
    "three_quarter": "three-quarter view, turned 45 degrees to the right",
}

TURNAROUND_PROMPT = (
    "Show this exact character from the {view_phrase}, standing in a neutral pose, "
    "on a flat solid {color_name} background {hex}. Do not change the {keep}. "
    "Same art style, same colors, same scale. No shadows, no reflections."
)


def _join_keep(items: Sequence[str]) -> str:
    items = [str(i).strip() for i in items if str(i).strip()]
    if not items:
        return "character"
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + ", and " + items[-1]


def build_view_prompt(view: str, plate_color: str, do_not_change: Sequence[str]) -> str:
    """Prompt for one turnaround view. Raises ``ValueError`` on an unknown view."""
    if view not in VIEW_PHRASES:
        raise ValueError(f"Unknown turnaround view {view!r}. Use one of {VIEWS}.")
    hex_color = normalize_hex(plate_color)
    return TURNAROUND_PROMPT.format(view_phrase=VIEW_PHRASES[view],
                                    color_name=color_name(hex_color), hex=hex_color,
                                    keep=_join_keep(do_not_change))


def generate_turnaround(provider, character: Path, out_dir: Path,
                        views: Sequence[str] = VIEWS, *, plate_color: str,
                        do_not_change: Sequence[str] = ("face", "hair", "proportions", "outfit"),
                        model: Optional[str] = None, aspect_ratio: str = "1:1",
                        log: Callable[[str], None] = logger.info,
                        token: Optional[CancelToken] = None) -> Dict[str, Path]:
    """Render each view in ``views`` to ``out_dir/<view>.png`` with a sidecar."""
    character = Path(character)
    out_dir = Path(out_dir)
    if not character.exists():
        raise FileNotFoundError(f"Character image not found: {character}")
    model_id = model or provider.get_default_model()
    provider_name = type(provider).__name__
    hex_color = normalize_hex(plate_color)
    results: Dict[str, Path] = {}

    for view in views:
        if token is not None:
            token.raise_if_cancelled()
        prompt = build_view_prompt(view, hex_color, do_not_change)
        emit(logger, log, f"=== Turnaround request: {view} ===")
        emit(logger, log, f"provider={provider_name} model={model_id} aspect_ratio={aspect_ratio} "
                          f"plate_color={hex_color} image={character}")
        emit(logger, log, f"Prompt (FULL, {len(prompt)} chars):\n{prompt}")
        try:
            texts, images = provider.edit_image(character, prompt, model_id,
                                                aspect_ratio=aspect_ratio)
        except Exception as exc:  # noqa: BLE001 - classified below
            err = classify_provider_error(exc, provider="gemini")
            emit(logger, log, f"Turnaround view '{view}' failed: {err.user_message}", level="error")
            raise err from exc

        emit(logger, log, f"=== Turnaround response ({view}): {len(images)} image(s), "
                          f"{len(texts)} text(s) ===")
        for text in texts:
            emit(logger, log, f"Response text (FULL, {len(text)} chars):\n{text}")
        if not images:
            err = ProviderError(f"The image model returned no image for the '{view}' view.")
            emit(logger, log, err.user_message, level="error")
            raise err

        out_png = out_dir / f"{view}.png"
        with Image.open(io.BytesIO(images[0])) as img:
            rgba = img.convert("RGBA")
            out_dir.mkdir(parents=True, exist_ok=True)
            rgba.save(out_png, format="PNG")
            size = list(rgba.size)
        write_image_sidecar(out_png, {
            "kind": "turnaround",
            "view": view,
            "prompt": prompt,
            "provider": provider_name,
            "model": model_id,
            "aspect_ratio": aspect_ratio,
            "plate_color": hex_color,
            "do_not_change": list(do_not_change),
            "source": str(character),
            "size": size,
            "response_texts": list(texts),
            "timestamp": now_iso(),
        })
        results[view] = out_png
        emit(logger, log, f"Turnaround view saved: {out_png}")
    return results
