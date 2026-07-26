"""Derive a style from N reference images (map-reduce over vision LLM calls).

Pure pipeline: derive_style_data() takes injected callables so tests and the
GUI/CLI transports share one code path. Real transports live in Task 5's
StyleAnalysisService/build_completion_fn below.
Extraction prompt extends core/video/style_analyzer.py:71-89 (style, NOT
content) to N images + structured JSON.
"""
import base64
import io
import json
import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from core.styles.models import DESCRIPTOR_KEYS

logger = logging.getLogger(__name__)

ANALYZE_CHUNK_SIZE = 8
MAX_LLM_IMAGE_DIM = 1568  # Anthropic's hard cap; safe for all providers

_JSON_SHAPE = ", ".join(f'"{k}": "..."' for k in DESCRIPTOR_KEYS)

CHUNK_PROMPT = f"""Analyze these images TOGETHER and extract ONLY the visual style they SHARE, for replicating in new scenes.

CRITICAL - Identify the rendering/artistic style FIRST:
- Is it: photorealistic, 3D render, cartoon/animated, anime, hand-drawn, painterly, sketch, etc.?
- If animated/cartoon: what animation style? (Disney, anime, flat colors, cel-shaded, etc.)

Then describe the shared style elements:
- Lighting: direction, quality, color temperature, shadows
- Color palette: dominant colors, saturation level, contrast
- Composition: framing, camera angle, perspective tendencies
- Texture/detail level: smooth, detailed, stylized, etc.
- Line work: bold outlines, soft edges, clean lines, sketchy, etc.
- Mood and atmosphere
- Negative: anything to AVOID to stay on-style (or "")

Do NOT describe the content/subjects of the images, only the style.
Do NOT mention image dimensions, pixel sizes, or aspect ratios anywhere.

Return ONLY a JSON object (no prose, no markdown) with exactly these keys:
{{{_JSON_SHAPE}}}"""

MERGE_PROMPT = """You are merging style analyses of several batches of images from ONE visual style.

<chunk_descriptors>
{chunks_json}
</chunk_descriptors>

<instructions>
Merge them into one canonical style description. Resolve disagreements toward
the majority; keep only what the batches share. Do NOT mention image
dimensions, pixel sizes, or aspect ratios. Also write "prompt_text": a single
60-80 word style instruction (no subject/content words) suitable for appending
to any image prompt.
Return ONLY a JSON object with exactly these keys:
{{{json_shape}, "prompt_text": "..."}}
</instructions>"""

SMART_MERGE_NOTE = None  # smart merge lives in applicator.py (Task 6)


class StyleAnalysisError(Exception):
    """Style derivation failed; message is user-facing."""


def chunk_paths(paths: List[Path], size: int = ANALYZE_CHUNK_SIZE) -> List[List[Path]]:
    paths = list(paths)
    return [paths[i:i + size] for i in range(0, len(paths), size)]


def encode_image_for_llm(path: Path) -> Tuple[str, str]:
    """Downscale to MAX_LLM_IMAGE_DIM and return ("image/jpeg", base64 str)."""
    from PIL import Image
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((MAX_LLM_IMAGE_DIM, MAX_LLM_IMAGE_DIM))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90)
    return "image/jpeg", base64.b64encode(buf.getvalue()).decode("utf-8")


def build_chunk_messages(paths: List[Path]) -> List[Dict]:
    """One user message: CHUNK_PROMPT + each image as a data-URI part."""
    parts: List[Dict] = [{"type": "text", "text": CHUNK_PROMPT}]
    for p in paths:
        mime, b64 = encode_image_for_llm(p)
        parts.append({"type": "image_url",
                      "image_url": {"url": f"data:{mime};base64,{b64}"}})
    return [{"role": "user", "content": parts}]


def parse_descriptor(content: str) -> Optional[Dict[str, str]]:
    """Parse an LLM reply into a descriptor dict (keys filtered/defaulted)."""
    from gui.llm_utils import LLMResponseParser
    data = LLMResponseParser.parse_json_response(content or "", expected_type=dict)
    if not isinstance(data, dict):
        return None
    return {k: str(data.get(k) or "") for k in DESCRIPTOR_KEYS}


def flatten_descriptor(desc: Dict[str, str], max_words: int = 80) -> str:
    """Deterministic prompt_text: summary + non-empty fields (negative excluded)."""
    parts = [desc.get("summary", "").strip()]
    for k in ("medium", "palette", "lighting", "composition", "texture",
              "line_work", "mood"):
        v = (desc.get(k) or "").strip()
        if v:
            parts.append(v)
    words = " ".join(p.rstrip(".") + "." for p in parts if p).split()
    return " ".join(words[:max_words])


def merge_descriptors(descs: List[Dict[str, str]],
                      completion_fn: Callable[[List[Dict]], str]) -> Dict[str, str]:
    """Reduce chunk descriptors to one descriptor + prompt_text.

    Single chunk: no LLM call — flatten deterministically (spec §4 step 3).
    Multi chunk: one text-only LLM call; on unparseable reply fall back to the
    first descriptor + deterministic flatten (logged).
    """
    if not descs:
        raise StyleAnalysisError("No descriptors to merge")
    if len(descs) == 1:
        return {**descs[0], "prompt_text": flatten_descriptor(descs[0])}

    prompt = MERGE_PROMPT.format(chunks_json=json.dumps(descs, indent=2),
                                 json_shape=_JSON_SHAPE)
    logger.info(f"Style merge request over {len(descs)} chunk descriptors")
    try:
        reply = completion_fn([{"role": "user", "content": prompt}])
        logger.info(f"Style merge response ({len(reply or '')} chars): {reply}")
        from gui.llm_utils import LLMResponseParser
        data = LLMResponseParser.parse_json_response(reply or "", expected_type=dict)
    except Exception as e:  # noqa: BLE001 - fall back, never crash the reduce
        logger.warning(f"Style merge LLM call failed: {e}")
        data = None
    if isinstance(data, dict):
        merged = {k: str(data.get(k) or "") for k in DESCRIPTOR_KEYS}
        pt = str(data.get("prompt_text") or "").strip()
        merged["prompt_text"] = pt or flatten_descriptor(merged)
        return merged
    logger.warning("Style merge reply unparseable; using first chunk + flatten")
    return {**descs[0], "prompt_text": flatten_descriptor(descs[0])}


def derive_style_data(paths: List[Path],
                      vision_fn: Callable[[List[Dict]], str],
                      completion_fn: Callable[[List[Dict]], str],
                      progress_cb: Optional[Callable[[str], None]] = None) -> Dict:
    """Map-reduce: chunks of images -> descriptors -> one merged style.

    Returns {"descriptor": {<9 keys>}, "prompt_text": str}.
    Raises StyleAnalysisError on empty input or an unparseable chunk (no
    half-derived styles — spec §8).
    """
    def emit(msg: str) -> None:
        logger.info(msg)
        if progress_cb:
            progress_cb(msg)

    paths = [Path(p) for p in paths]
    if not paths:
        raise StyleAnalysisError("No images supplied for style analysis")

    chunks = chunk_paths(paths)
    descs: List[Dict[str, str]] = []
    for i, chunk in enumerate(chunks, start=1):
        emit(f"Analyzing chunk {i}/{len(chunks)} ({len(chunk)} image(s))...")
        messages = build_chunk_messages(chunk)
        reply = vision_fn(messages)
        logger.info(f"Style chunk {i} response ({len(reply or '')} chars): {reply}")
        desc = parse_descriptor(reply)
        if desc is None:
            raise StyleAnalysisError(
                f"Could not parse style analysis for chunk {i}/{len(chunks)}; "
                f"no style was saved. Raw reply logged.")
        descs.append(desc)

    if len(descs) > 1:
        emit(f"Merging {len(descs)} chunk analyses...")
    merged = merge_descriptors(descs, completion_fn)
    prompt_text = merged.pop("prompt_text")
    emit("Style analysis complete.")
    return {"descriptor": merged, "prompt_text": prompt_text}
