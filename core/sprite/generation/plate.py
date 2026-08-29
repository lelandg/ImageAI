"""Chroma plate preparation via an image edit (design §4.2).

Places the character on a flat solid plate color so the video model starts
from a keyable frame. Uses ``ImageProvider.edit_image`` (Google Gemini by
default). The prompt never mentions transparency, aspect, or pixel sizes.
"""
import io
import logging
from pathlib import Path
from typing import Callable, Optional

from PIL import Image

from core.sprite.generation._common import emit, now_iso
from core.sprite.generation.errors import ProviderError, classify_provider_error
from core.sprite.generation.prompts import color_name, normalize_hex
from core.utils import write_image_sidecar

logger = logging.getLogger(__name__)

PLATE_PROMPT = ("Place this exact character on a flat solid {color_name} background {hex}. "
                "Remove all shadows and reflections. Do not change the character.")


def make_chroma_plate(provider, character: Path, out_png: Path,
                      plate_color: str = "#00FF00", *, model: Optional[str] = None,
                      aspect_ratio: str = "16:9",
                      log: Callable[[str], None] = logger.info) -> Path:
    """Render ``character`` onto a solid ``plate_color`` plate and save ``out_png``."""
    character = Path(character)
    out_png = Path(out_png)
    if not character.exists():
        raise FileNotFoundError(f"Character image not found: {character}")

    hex_color = normalize_hex(plate_color)
    prompt = PLATE_PROMPT.format(color_name=color_name(hex_color), hex=hex_color)
    model_id = model or provider.get_default_model()
    provider_name = type(provider).__name__

    emit(logger, log, "=== Chroma plate request ===")
    emit(logger, log, f"provider={provider_name} model={model_id} aspect_ratio={aspect_ratio} "
                      f"plate_color={hex_color} image={character}")
    emit(logger, log, f"Prompt (FULL, {len(prompt)} chars):\n{prompt}")

    try:
        texts, images = provider.edit_image(character, prompt, model_id, aspect_ratio=aspect_ratio)
    except Exception as exc:  # noqa: BLE001 - classified below
        err = classify_provider_error(exc, provider="gemini")
        emit(logger, log, f"Chroma plate failed: {err.user_message}", level="error")
        raise err from exc

    emit(logger, log, f"=== Chroma plate response: {len(images)} image(s), {len(texts)} text(s) ===")
    for text in texts:
        emit(logger, log, f"Response text (FULL, {len(text)} chars):\n{text}")

    if not images:
        err = ProviderError("The image model returned no image for the chroma plate. "
                            "Try again or use another image model.")
        emit(logger, log, err.user_message, level="error")
        raise err

    with Image.open(io.BytesIO(images[0])) as img:
        rgba = img.convert("RGBA")
        out_png.parent.mkdir(parents=True, exist_ok=True)
        rgba.save(out_png, format="PNG")
        size = list(rgba.size)

    write_image_sidecar(out_png, {
        "kind": "chroma_plate",
        "prompt": prompt,
        "provider": provider_name,
        "model": model_id,
        "aspect_ratio": aspect_ratio,
        "plate_color": hex_color,
        "source": str(character),
        "size": size,
        "response_texts": list(texts),
        "timestamp": now_iso(),
    })
    emit(logger, log, f"Chroma plate saved: {out_png} ({size[0]}x{size[1]})")
    return out_png
