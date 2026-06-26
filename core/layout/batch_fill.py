"""Batch fill: keyed BatchRequests from a layout + result→region mapping (Phase 5b).

Google Batch API only (``core.batch_manager.BatchManager`` wraps the genai batch
client). These are **pure** helpers so request construction and result mapping are
unit-testable; the live submission/polling/placement is wired in the GUI later
(it needs a Google client, is async — up to 24h — and must be GUI-verified).

Each request's ``key`` is the region id, so a completed job's results map straight
back to the regions that produced them — order-independent and robust to errors.
"""
import base64
import json
import logging
from typing import Dict, List, Optional, Tuple

from core.layout.models import DocumentSpec

logger = logging.getLogger("imageai.layout.batch_fill")

# Google image aspect ratios (AGENTS.md §9): the request carries a ratio, not px.
_SUPPORTED_RATIOS = ["1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]


def nearest_supported_ratio(width: float, height: float) -> str:
    """Closest Google-supported aspect ratio to ``width:height`` (by value)."""
    if width <= 0 or height <= 0:
        return "1:1"
    target = width / height
    best = min(_SUPPORTED_RATIOS,
               key=lambda r: abs(target - _ratio_value(r)))
    return best


def _ratio_value(ratio: str) -> float:
    a, b = ratio.split(":")
    return int(a) / int(b)


def build_requests(document: DocumentSpec, model: str, only_empty: bool = False):
    """Build (requests, skipped_ids) for image regions carrying a prompt.

    ``key=region.id``; aspect ratio is snapped to the nearest supported value
    (never a pixel token — repo rule). ``only_empty`` skips already-filled regions.
    Returns ``(List[BatchRequest], List[str])`` — the second is regions skipped
    for having no prompt (surfaced to the user).
    """
    from core.batch_manager import BatchRequest
    requests = []
    skipped: List[str] = []
    for page in document.pages:
        for r in page.regions:
            if r.kind != "image":
                continue
            if only_empty and r.image_ref:
                continue
            if not (r.prompt or "").strip():
                skipped.append(r.id)
                continue
            _, _, w, h = r.bbox
            requests.append(BatchRequest(
                key=r.id, prompt=r.prompt, model=model,
                aspect_ratio=nearest_supported_ratio(w, h),
                width=int(w), height=int(h)))
    return requests, skipped


def _first_image_bytes(response: Dict) -> Optional[bytes]:
    for candidate in response.get("candidates", []):
        content = candidate.get("content", {}) or {}
        for part in content.get("parts", []) or []:
            inline = part.get("inline_data") or part.get("inlineData") or {}
            data = inline.get("data")
            if data:
                try:
                    return base64.b64decode(data)
                except Exception:  # noqa: BLE001 - skip a malformed part, keep scanning
                    continue
    return None


def parse_result_jsonl(text: str) -> Dict[str, bytes]:
    """Map each result line's ``key`` → decoded image bytes (first image part).

    Feed this the downloaded batch result file (JSONL). Lines without a key, a
    parseable body, or an image are skipped. Robust to errors in other lines.
    """
    out: Dict[str, bytes] = {}
    for line in (text or "").strip().split("\n"):
        if not line.strip():
            continue
        try:
            result = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = result.get("key")
        if not key:
            continue
        img = _first_image_bytes(result.get("response") or {})
        if img is not None:
            out[key] = img
    return out


def results_to_placements(document: DocumentSpec,
                          keyed_results: Dict[str, bytes]) -> List[Tuple[str, bytes]]:
    """(region_id, bytes) for each result whose key is an image region in ``doc``."""
    ids = {r.id for page in document.pages for r in page.regions if r.kind == "image"}
    return [(k, v) for k, v in keyed_results.items() if k in ids]
