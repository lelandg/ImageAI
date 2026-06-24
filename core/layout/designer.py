"""AI layout designer: prompt building, response parsing, and the LLM call."""
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Callable

from core.layout.models import Region
from core.layout import schema

logger = logging.getLogger("imageai.layout.designer")

_SYSTEM = (
    "You are a page-layout designer. You design the GEOMETRY of a single page as "
    "regions (image or text placeholders). You never write the actual content. "
    "Respond with a SINGLE JSON object and nothing else."
)


def build_messages(content_kind: str, page_px: Tuple[int, int], user_text: str,
                   current_regions: Optional[List[Region]] = None) -> List[Dict[str, str]]:
    pw, ph = page_px
    current = ""
    if current_regions:
        current = (
            "<current_layout>\n"
            + json.dumps([schema.region_to_dict(r) for r in current_regions], indent=0)
            + "\n</current_layout>\n"
        )
    user = (
        f"<context>\n"
        f"content_kind: {content_kind}\n"
        f"page_pixels: {pw} x {ph} (x,y origin top-left; all coordinates in pixels)\n"
        f"</context>\n"
        f"{current}"
        f"<request>\n{user_text}\n</request>\n"
        f"<instructions>\n"
        f"Return a JSON object with optional keys:\n"
        f'  "questions": [strings]   // ask for missing detail if needed\n'
        f'  "layout": {{ "regions": [ {{\n'
        f'      "id": string, "kind": "image"|"text", "shape": "rect"|"polygon",\n'
        f'      "bbox": [x,y,w,h], "points": [[x,y],...] (polygon only),\n'
        f'      "z": int, "text": string (text only) }} ] }}\n'
        f"All coordinates MUST be within the page ({pw} x {ph}). Prefer 'rect' unless the\n"
        f"request implies panels that flow into each other (then use 'polygon'). You may\n"
        f"return questions, a layout, or both.\n"
        f"</instructions>"
    )
    return [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]
