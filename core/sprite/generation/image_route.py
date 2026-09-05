"""Route B — image-model sprite generation: one horizontal sheet, or an edit-chain.

Both entry points take an already-built provider (GoogleProvider or
OpenAIProvider), write PNGs with JSON sidecars, log every request and
response in full, and raise ``SpriteGenerationError`` subclasses on failure.
"""
from __future__ import annotations

import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from PIL import Image

from core.sprite.generation._common import emit
from core.sprite.generation.errors import ProviderError, classify_provider_error
from core.sprite.generation.pose_steps import generate_pose_instructions  # noqa: F401 — re-export (design §4.6)
from core.sprite.generation.prompts import background_prompt
from core.sprite.models import Size
from core.sprite.pipeline import CancelToken
from core.sprite.project import ActionCard
from core.sprite.slicing import guess_grid, slice_sheet
from core.utils import write_image_sidecar

logger = logging.getLogger(__name__)
LogFn = Callable[[str], None]

SHEET_ASPECT_GEMINI = "21:9"      # widest ratio Gemini accepts (AGENTS.md list); kwarg only, never prompt text
SHEET_SIZE_CUSTOM = "3072x1024"   # 3:1 strip for OpenAI models with supports_custom_size
MIN_GRID_CONFIDENCE = 0.6

STEP_PROMPT = (
    "This is the same character. Change only the body pose: {instruction} "
    "Keep the identical character design, art style, scale, and position in the frame."
)


# --------------------------------------------------------------------------- shared helpers

def provider_kind(provider) -> str:
    """'openai' for OpenAIProvider instances, else 'google'."""
    from providers.openai import OpenAIProvider
    return "openai" if isinstance(provider, OpenAIProvider) else "google"


def default_openai_edit_model() -> str:
    """First MODEL_CAPS row that supports multi-reference edits with a mask (capability lookup, no literal)."""
    from providers.openai import MODEL_CAPS
    return next(mid for mid, caps in MODEL_CAPS.items() if caps["supports_multi_reference"] and caps["supports_mask"])


def _timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def first_image(texts: Sequence[str], images: Sequence[bytes], *, what: str) -> bytes:
    if images:
        return images[0]
    detail = " ".join(t.strip() for t in texts if t and t.strip())[:300]
    raise ProviderError(f"{what}: the model returned no image." + (f" Model text: {detail}" if detail else ""))


def save_png(data: bytes, out_png: Path) -> Path:
    """Decode any image bytes the model returned and store them as RGBA PNG."""
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(data)) as img:
        img.convert("RGBA").save(out_png, "PNG")
    return out_png


def log_request(log: LogFn, *, what: str, provider: str, model: Optional[str], prompt: str, params: Dict,
                logger: logging.Logger = logger) -> None:
    """Log one provider request in full.

    ``logger`` is the file logger that receives the line. A module that imports this
    helper passes its own logger. ``emit`` then skips a sink that is a bound method of
    that same logger, so a caller's default ``log=logger.info`` sink writes one line,
    not two.
    """
    message = (f"[image route] {what} request: provider={provider} model={model or 'default'} "
               f"params={params}\nprompt: {prompt}")
    emit(logger, log, message)


def log_response(log: LogFn, *, what: str, texts: Sequence[str], images: Sequence[bytes],
                 logger: logging.Logger = logger) -> None:
    """Log one provider response in full. ``logger`` follows the rule in ``log_request``."""
    text = " | ".join(t.strip() for t in texts if t and t.strip()) or "(none)"
    message = f"[image route] {what} response: {len(images)} image(s) {[len(b) for b in images]} bytes; text: {text}"
    emit(logger, log, message)


def call_provider(provider, method: str, *args, what: str, log: LogFn = logger.info,
                  logger: logging.Logger = logger, **kwargs) -> Tuple[List[str], List[bytes]]:
    """Call ``provider.<method>`` and map any exception to a SpriteGenerationError.

    ``logger`` follows the rule in ``log_request``.
    """
    try:
        return getattr(provider, method)(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 — classify_provider_error decides the subclass
        emit(logger, log, f"[image route] {what} failed: {exc}", level="error")
        raise classify_provider_error(exc) from exc


def openai_sheet_size(model: str) -> str:
    """3:1 custom size when the model allows it, else the widest preset size."""
    from core.image_size import parse_size_string, validate_custom_size
    from providers.openai import MODEL_CAPS
    caps = MODEL_CAPS.get(model) or MODEL_CAPS["gpt-image-1"]
    if caps.get("supports_custom_size"):
        w, h = parse_size_string(SHEET_SIZE_CUSTOM)
        ok, why = validate_custom_size(w, h, caps)
        if ok:
            return SHEET_SIZE_CUSTOM
        logger.warning("custom sheet size %s rejected for %s (%s); using preset sizes", SHEET_SIZE_CUSTOM, model, why)
    presets = [s for s in caps["valid_sizes"] if s != "auto"]
    return max(presets, key=lambda s: (lambda wh: wh[0] / wh[1])(parse_size_string(s)))


def openai_edit_size(model: str, size: Size) -> str:
    """Closest legal edit size for a source of ``size``; custom size when allowed and in range."""
    from core.image_size import parse_size_string, validate_custom_size
    from providers.openai import MODEL_CAPS
    caps = MODEL_CAPS.get(model) or MODEL_CAPS["gpt-image-1"]
    w, h = int(size[0]), int(size[1])
    if caps.get("supports_custom_size"):
        multiple = int(caps.get("custom_size_edge_multiple", 16))
        # Round half up (not Python's round-half-to-even) so an exact .5 edge grows to the
        # larger multiple, matching the closest-legal-size contract at the halfway point.
        cw = max(multiple, int(w / multiple + 0.5) * multiple)
        ch = max(multiple, int(h / multiple + 0.5) * multiple)
        ok, _why = validate_custom_size(cw, ch, caps)
        if ok:
            return f"{cw}x{ch}"
    presets = [s for s in caps["valid_sizes"] if s != "auto"]
    target = w / h

    def score(s: str) -> float:
        pw, ph = parse_size_string(s)
        return abs(pw / ph - target)

    return min(presets, key=score)


# --------------------------------------------------------------------------- sheet route

def sheet_prompt(action: ActionCard, frames: int, plate_color: str, *,
                 background_mode: str = "transparent") -> str:
    """Prompt for one horizontal strip; chroma suffix and loop hint come from inject_chroma."""
    label = action.name.replace("_", " ")
    base = (
        f"A {frames}-frame {label} animation of this exact character as one horizontal sprite sheet: "
        f"{frames} equal cells in a single row from left to right, one key pose per cell, in play order. "
        "Same character, same art style, same scale, and the same position inside every cell. "
        "No labels, no numbers, no cell borders, no text. "
        f"{action.prompt.strip()}"
    )
    return background_prompt(base, plate_color, loop=action.loop, background_mode=background_mode)


def generate_sheet(
    provider,
    character: Path,
    action: ActionCard,
    out_png: Path,
    *,
    frames: int,
    plate_color: str,
    background_mode: str = "transparent",
    model: Optional[str] = None,
    log: LogFn = logger.info,
    token: Optional[CancelToken] = None,
) -> Path:
    """Generate one horizontal sheet from the character image; returns the sheet PNG path."""
    if frames < 2:
        raise ValueError("frames must be >= 2 for a sheet")
    if token is not None:
        token.raise_if_cancelled()
    character = Path(character)
    if not character.exists():
        raise FileNotFoundError(character)
    kind = provider_kind(provider)
    model = model or provider.get_default_model()
    prompt = sheet_prompt(action, frames, plate_color, background_mode=background_mode)
    if kind == "openai":
        size = openai_sheet_size(model)
        params: Dict = {"size": size, "n": 1}
        log_request(log, what="sheet", provider=kind, model=model, prompt=prompt, params=params)
        texts, images = call_provider(provider, "edit_image", [character], prompt, what="sheet",
                                      log=log, model=model, size=size, n=1)
    else:
        params = {"aspect_ratio": SHEET_ASPECT_GEMINI}
        log_request(log, what="sheet", provider=kind, model=model, prompt=prompt, params=params)
        texts, images = call_provider(provider, "edit_image", character, prompt, what="sheet",
                                      log=log, model=model, aspect_ratio=SHEET_ASPECT_GEMINI)
    log_response(log, what="sheet", texts=texts, images=images)
    out = save_png(first_image(texts, images, what="sheet"), out_png)
    write_image_sidecar(out, {
        "prompt": prompt, "provider": kind, "model": model, "timestamp": _timestamp(),
        "route": "image_sheet", "action": action.name, "action_id": action.id,
        "frames": frames, "plate_color": plate_color, "params": params,
        "background_mode": background_mode,
        "reference_images": [str(character)],
    })
    emit(logger, log, f"[image route] sheet saved: {out}")
    return out


def slice_generated_sheet(
    sheet_png: Path,
    out_dir: Path,
    frames: int,
    plate_color: str,
    *,
    log: LogFn = logger.info,
    background_mode: str = "transparent",
) -> List[Path]:
    """Cut a generated sheet into ``frames`` PNGs (guess the grid; fall back to one row)."""
    sheet_png = Path(sheet_png)
    columns, rows = frames, 1
    if background_mode != "original":
        with Image.open(sheet_png) as img:
            guess = guess_grid(img.convert("RGBA"), key_color=plate_color)
        if guess.confidence >= MIN_GRID_CONFIDENCE and guess.columns * guess.rows == frames:
            columns, rows = guess.columns, guess.rows
            emit(logger, log, f"[image route] grid detected: {columns}x{rows} (confidence {guess.confidence:.2f})")
        else:
            emit(logger, log, f"[image route] grid guess {guess.columns}x{guess.rows} "
                              f"(confidence {guess.confidence:.2f}) rejected; slicing {frames}x1")
    else:
        # Scenery can contain the key color and must not be mistaken for cell gutters.
        emit(logger, log, f"[image route] preserving backgrounds in the requested {frames}x1 layout")
    paths = list(slice_sheet(sheet_png, Path(out_dir), columns, rows))
    for index, path in enumerate(paths, start=1):
        write_image_sidecar(path, {
            "route": "image_sheet", "source_sheet": str(sheet_png), "cell_index": index,
            "columns": columns, "rows": rows, "timestamp": _timestamp(),
            "background_mode": background_mode,
        })
    return paths


# --------------------------------------------------------------------------- edit-chain route

MATTE_PLATES = ("#FFFFFF", "#000000")


def edit_chain(
    provider,
    character: Path,
    action: ActionCard,
    out_dir: Path,
    *,
    frames: int,
    pose_instructions: Sequence[str],
    plate_color: str,
    background_mode: str = "transparent",
    model: Optional[str] = None,
    log: LogFn = logger.info,
    token: Optional[CancelToken] = None,
    matte_pairs: bool = False,
) -> List[Path]:
    """Render ``frames`` PNGs where frame k is an edit of [character, frame k-1].

    ``out_dir`` receives only the composed ``NNNN.png`` frames. In matte mode the white
    and black plates go into ``out_dir/plates``, because ``pipeline.list_frames`` globs
    ``*.png`` in the stage directory and must see the frames alone. Each plate keeps its
    own ``.json`` sidecar, and the composed frame's sidecar lists both plate paths.
    """
    if background_mode == "original":
        matte_pairs = False
    if frames < 1:
        raise ValueError("frames must be >= 1")
    if len(pose_instructions) != frames:
        raise ValueError(f"pose_instructions has {len(pose_instructions)} entries; expected {frames}")
    character = Path(character)
    if not character.exists():
        raise FileNotFoundError(character)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    kind = provider_kind(provider)
    model = model or (default_openai_edit_model() if kind == "openai" else provider.get_default_model())
    character_bytes = character.read_bytes()
    with Image.open(character) as img:
        char_size: Size = img.size
    session_started = False
    if kind == "google":
        session_started = bool(provider.start_edit_session(
            character_bytes, style_context="sprite animation frames; keep the exact character", model=model))
        if not session_started:
            emit(logger, log, "[image route] edit session did not start; continuing with single-shot edits",
                 level="warning")
    plates = list(MATTE_PLATES) if matte_pairs else [plate_color]
    outputs: List[Path] = []
    prev_bytes = character_bytes
    prev_reference_path: Path = character
    try:
        for k, instruction in enumerate(pose_instructions, start=1):
            if token is not None:
                token.raise_if_cancelled()
            what = f"edit-chain step {k}/{frames}"
            out_png = out_dir / f"{k:04d}.png"
            step_images: Dict[str, bytes] = {}
            prompts: Dict[str, str] = {}
            for color in plates:
                # Poll before every paid call, so a Cancel during the white plate never
                # buys the black one (same convention as retouch_frame).
                if token is not None:
                    token.raise_if_cancelled()
                prompt = background_prompt(STEP_PROMPT.format(instruction=instruction.strip()), color,
                                           loop=False, background_mode=background_mode)
                prompts[color] = prompt
                params: Dict = {"step": k, "plate": color, "background_mode": background_mode}
                refs = [character_bytes, prev_bytes]
                if kind == "openai":
                    size = openai_edit_size(model, char_size)
                    params["size"] = size
                    log_request(log, what=what, provider=kind, model=model, prompt=prompt, params=params)
                    texts, images = call_provider(provider, "edit_image", refs, prompt, what=what, log=log,
                                                  model=model, size=size, n=1)
                else:
                    log_request(log, what=what, provider=kind, model=model, prompt=prompt, params=params)
                    texts, images = call_provider(provider, "edit_image", refs, prompt, what=what, log=log,
                                                  model=model)
                log_response(log, what=what, texts=texts, images=images)
                step_images[color] = first_image(texts, images, what=what)
            plate_paths: List[str] = []
            if matte_pairs:
                from core.sprite.matting import difference_matte
                # The plates are inputs to the matte, not animation frames. They go into a
                # sibling "plates" directory, because pipeline.list_frames globs *.png in the
                # stage directory and would otherwise play the raw plates as frames.
                plates_dir = out_dir / "plates"
                white = save_png(step_images[MATTE_PLATES[0]], plates_dir / f"{k:04d}.white.png")
                black = save_png(step_images[MATTE_PLATES[1]], plates_dir / f"{k:04d}.black.png")
                for plate_path, plate_color_value in ((white, MATTE_PLATES[0]), (black, MATTE_PLATES[1])):
                    write_image_sidecar(plate_path, {
                        "prompt": prompts[plate_color_value], "provider": kind, "model": model,
                        "timestamp": _timestamp(), "route": "image_edit_chain_plate",
                        "action": action.name, "action_id": action.id, "step": k, "of": frames,
                        "pose": instruction, "plate_color": plate_color_value,
                    })
                with Image.open(white) as w_img, Image.open(black) as b_img:
                    matted = difference_matte(w_img.convert("RGB"), b_img.convert("RGB"))
                matted.convert("RGBA").save(out_png, "PNG")
                plate_paths = [str(white), str(black)]
                next_bytes = step_images[MATTE_PLATES[0]]
                next_reference_path = white
            else:
                save_png(step_images[plate_color], out_png)
                next_bytes = step_images[plate_color]
                next_reference_path = out_png
            write_image_sidecar(out_png, {
                "prompt": prompts[plates[0]], "prompts": prompts, "provider": kind, "model": model,
                "timestamp": _timestamp(), "route": "image_edit_chain",
                "action": action.name, "action_id": action.id, "step": k, "of": frames,
                "pose": instruction, "plate_color": plate_color, "matte_pairs": matte_pairs,
                "background_mode": background_mode,
                "plates": plate_paths,
                "reference_images": [str(character), str(prev_reference_path)],
            })
            outputs.append(out_png)
            prev_bytes = next_bytes
            prev_reference_path = next_reference_path
            emit(logger, log, f"[image route] step {k}/{frames} saved: {out_png}")
    finally:
        if kind == "google" and session_started:
            provider.reset_edit_session()
    return outputs
