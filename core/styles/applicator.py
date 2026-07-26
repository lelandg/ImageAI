"""Apply a saved style to a generation request.

One function, four seams (GUI image gen, CLI image gen, video scenes, layout
fill). Plain concat is the default; smart merge is opt-in and can never fail
a generation (falls back to plain with a logged warning). Providers that
accept multiple reference images additionally get the style's exemplars,
user references first. Spec: Plans/2026-07-26-custom-styles-design.md §5.
"""
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core.styles.models import Style

logger = logging.getLogger(__name__)

# Mirrors gui/imagen_reference_widget.py:449 MODEL_REF_LIMITS (core must not
# import gui). Update both together if a model's limit changes.
GOOGLE_REF_LIMITS = {
    "gemini-2.5-flash-image": 5,
    "gemini-3.1-flash-image-preview": 8,
    "gemini-3-pro-image-preview": 14,
}
GOOGLE_DEFAULT_REF_LIMIT = 3
OPENAI_REF_LIMIT = 10
_OPENAI_IMAGE_MODEL_PREFIXES = ("gpt-image-",)  # gpt-image-1/1.5/1-mini/2

SMART_MERGE_PROMPT = """<user_prompt>
{prompt}
</user_prompt>

<style>
{descriptor_json}
</style>

<instructions>
Rewrite the user prompt as ONE image-generation prompt that fully adopts the
style above. Keep every subject/content element of the user prompt; express
the style through concrete visual language; resolve conflicts in favor of the
style (e.g. "photograph" becomes the style's rendering instead). 2-4
sentences. Do NOT mention image dimensions, pixel sizes, or aspect ratios.
Return JSON: {{"prompt": "..."}}
</instructions>"""


@dataclass
class StyledRequest:
    prompt: str
    extra_kwargs: Dict = field(default_factory=dict)
    meta: Dict = field(default_factory=dict)


def style_ref_limit(provider: str, model: str) -> int:
    """How many total reference images this provider/model accepts (0 = none)."""
    provider = (provider or "").strip().lower()
    model = (model or "").strip()
    if provider == "google":
        return GOOGLE_REF_LIMITS.get(model, GOOGLE_DEFAULT_REF_LIMIT)
    if provider == "openai":
        if any(model.startswith(p) for p in _OPENAI_IMAGE_MODEL_PREFIXES):
            return OPENAI_REF_LIMIT
        return 0
    return 0  # stability (img2img only), local_sd, video, layout, unknown


def _plain_apply(prompt: str, style: Style) -> str:
    text = (style.prompt_text or "").strip()
    if not text:
        return prompt
    if style.placement == "prefix":
        return f"In this style: {text}. {prompt}"
    return f"{prompt}. In this style: {text}"


def _smart_merge(prompt: str, style: Style,
                 completion_fn: Callable[[List[Dict]], str]) -> Optional[str]:
    """One LLM call to fuse prompt + descriptor. None on any failure."""
    payload = SMART_MERGE_PROMPT.format(
        prompt=prompt,
        descriptor_json=json.dumps(
            {**style.descriptor.to_dict(), "prompt_text": style.prompt_text},
            indent=2))
    try:
        logger.info(f"Smart-merge request for style '{style.name}'")
        reply = completion_fn([{"role": "user", "content": payload}])
        logger.info(f"Smart-merge response ({len(reply or '')} chars): {reply}")
        from gui.llm_utils import LLMResponseParser
        data = LLMResponseParser.parse_json_response(reply or "", expected_type=dict)
        if isinstance(data, dict):
            merged = str(data.get("prompt") or "").strip()
            if merged:
                return merged
    except Exception as e:  # noqa: BLE001 - smart merge must never block generation
        logger.warning(f"Smart merge failed ({e}); falling back to plain concat")
        return None
    logger.warning("Smart merge reply unusable; falling back to plain concat")
    return None


def apply_style(prompt: str, style: Style, provider: str, model: str, *,
                smart: bool = False,
                completion_fn: Optional[Callable[[List[Dict]], str]] = None,
                exemplar_paths: Optional[List[Path]] = None,
                existing_references: Optional[List[bytes]] = None) -> StyledRequest:
    """Apply `style` to `prompt` for the given provider/model.

    Returns StyledRequest(prompt, extra_kwargs, meta). extra_kwargs contains a
    merged "reference_images" list (existing user refs first, then exemplar
    bytes) ONLY when at least one exemplar was attached — callers replace
    their kwargs entry with it in that case and leave kwargs untouched
    otherwise.
    """
    meta = {"style_id": style.id, "style_name": style.name,
            "smart_merge_used": False, "exemplars_attached": 0,
            "exemplars_dropped": 0}

    styled = None
    if smart and completion_fn is not None:
        styled = _smart_merge(prompt, style, completion_fn)
        meta["smart_merge_used"] = styled is not None
    if styled is None:
        styled = _plain_apply(prompt, style)

    extra: Dict = {}
    wanted = [Path(p) for p in (exemplar_paths or [])]
    available = [p for p in wanted if p.exists()]
    for p in set(wanted) - set(available):
        logger.warning(f"Style '{style.name}': exemplar missing on disk: {p}")
    limit = style_ref_limit(provider, model)
    if limit and available:
        existing = list(existing_references or [])
        slots = max(0, limit - len(existing))
        attach = available[:slots]
        meta["exemplars_attached"] = len(attach)
        meta["exemplars_dropped"] = len(available) - len(attach)
        if meta["exemplars_dropped"]:
            logger.warning(
                f"Style '{style.name}': dropped {meta['exemplars_dropped']} "
                f"exemplar(s) over the {provider}/{model} limit of {limit}")
        if attach:
            extra["reference_images"] = existing + [p.read_bytes() for p in attach]
    elif available:
        logger.info(f"Style '{style.name}': {provider}/{model} takes no style "
                    f"references; applying text only")

    return StyledRequest(prompt=styled, extra_kwargs=extra, meta=meta)
