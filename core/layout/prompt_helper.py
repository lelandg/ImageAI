"""Per-region AI prompt help: draft an image-generation prompt from the project.

Phase 5a, spec §9 (F-AI) first bullet. Pure prompt-building + response parsing;
the production LLM call reuses ``core.layout.designer.run_completion`` (LiteLLM,
key resolution, logging) injected as ``completion_fn`` — so this module is fully
unit-testable headless with a fake completion.
"""
import logging
from math import gcd
from typing import Callable, Dict, List, Optional

from core.layout.models import DocumentSpec, PageSpec, Region

logger = logging.getLogger("imageai.layout.prompt_helper")

_SYSTEM = (
    "You write vivid, concrete image-generation prompts for a single illustration "
    "that fits one region of a page layout. You return ONE prompt only. Never put "
    "page dimensions, pixel sizes, or aspect-ratio tokens in the prompt text — the "
    "image pipeline handles size separately and would otherwise render them as "
    'literal text. Respond with a single JSON object: {"prompt": "..."}.'
)


def _aspect_ratio(bbox) -> str:
    """Reduced w:h ratio for *context only* (never a pixel token in the prompt)."""
    _, _, w, h = bbox
    w, h = int(round(w)), int(round(h))
    if w <= 0 or h <= 0:
        return "1:1"
    g = gcd(w, h) or 1
    return f"{w // g}:{h // g}"


def _find_page(document: DocumentSpec, region: Region) -> Optional[PageSpec]:
    for page in document.pages or []:
        for r in page.regions:
            if r is region or r.id == region.id:
                return page
    return None


def _neighbor_text(document: DocumentSpec, region: Region) -> List[str]:
    """Text from sibling text regions on the same page (scene context)."""
    page = _find_page(document, region)
    if page is None:
        return []
    return [r.text.strip() for r in page.regions
            if r.kind == "text" and r.id != region.id and (r.text or "").strip()]


def build_prompt_messages(document: DocumentSpec, region: Region,
                          hint: str = "") -> List[Dict[str, str]]:
    """Build the chat messages that ask the LLM for one image prompt."""
    style = document.style
    palette = (", ".join(f"{k}={v}" for k, v in style.palette.items())
               if style and style.palette else "(default)")
    name = region.name or region.id
    role = region.role or "(unspecified)"
    aspect = _aspect_ratio(region.bbox)

    neighbors = _neighbor_text(document, region)
    neighbor_block = ""
    if neighbors:
        joined = "\n".join(f"- {t}" for t in neighbors)
        neighbor_block = f"<page_text>\n{joined}\n</page_text>\n"
    hint_block = f"<user_hint>\n{hint.strip()}\n</user_hint>\n" if hint.strip() else ""

    user = (
        f"<context>\n"
        f"document_title: {document.title}\n"
        f"content_kind: {document.content_kind}\n"
        f"color_palette: {palette}\n"
        f"region_name: {name}\n"
        f"region_role: {role}\n"
        f"region_aspect: {aspect}\n"
        f"</context>\n"
        f"{neighbor_block}"
        f"{hint_block}"
        f"<instructions>\n"
        f"Write one vivid image-generation prompt for the '{name}' image region of "
        f"this {document.content_kind} page. Match the subject and mood to the page "
        f"text and user hint above when present. Keep it a single prompt of 1-3 "
        f'sentences. Return JSON: {{"prompt": "..."}}. Do NOT include pixel sizes or '
        f"aspect-ratio tokens in the prompt text.\n"
        f"</instructions>"
    )
    return [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        parts = t.split("```")
        if len(parts) >= 2:
            t = parts[1]
            for lang in ("json", "JSON"):
                if t.startswith(lang):
                    t = t[len(lang):]
                    break
            t = t.strip()
    return t


def parse_prompt_response(content: str) -> str:
    """Extract the prompt: JSON ``{"prompt": ...}`` first, else fenced/plain text.

    Empty or whitespace-only input returns ``""`` so the caller can keep the
    region's existing prompt and log the miss.
    """
    if not content or not content.strip():
        return ""
    from gui.llm_utils import LLMResponseParser
    data = LLMResponseParser.parse_json_response(content, expected_type=dict)
    if isinstance(data, dict):
        p = data.get("prompt")
        if isinstance(p, str) and p.strip():
            return p.strip()
    return _strip_fences(content)


def run_prompt_help(messages: List[Dict[str, str]],
                    completion_fn: Callable[[List[Dict[str, str]]], str]) -> str:
    """Run the LLM (injected) and parse out the suggested prompt."""
    content = completion_fn(messages)
    return parse_prompt_response(content or "")
