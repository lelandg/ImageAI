"""AI layout designer: prompt building, response parsing, and the LLM call."""
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Callable

from core.layout.models import Region, Overlay
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
    from core.layout import styles
    role_names = sorted(styles.default_style_for(content_kind).font_roles.keys())
    roles = ", ".join(role_names)
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
        f"Return a SINGLE JSON object with optional keys:\n"
        f'  "questions": [strings]   // ask for missing detail if needed\n'
        f'  "layout": {{\n'
        f'    "tiling": {{ "preset": "grid"|"three_tiers"|"splash_with_strip"|'
        f'"diagonal_action"|"feature_L",\n'
        f'                "params": {{ "rows": int, "cols": int, "gutter_px": number,'
        f' "margin_px": number }} }},\n'
        f"        // optional; generates gap-free panels. rows/cols apply to \"grid\".\n"
        f'    "regions": [ {{ "id": string, "kind": "image"|"text",\n'
        f'        "shape": "rect"|"polygon"|"path",\n'
        f'        "bbox": [x,y,w,h], "points": [[x,y],...] (polygon only),\n'
        f'        "svg": "M.. L.. C.. Z" (path only; SVG path data in page pixels),\n'
        f'        "bleed": bool, "stroke_px": number,\n'
        f'        "z": int, "role": string, "text": string (text only) }} ],\n'
        f'    "overlays": [ {{ "id": string,\n'
        f'        "kind": "speech"|"thought"|"caption"|"sfx", "text": string,\n'
        f'        "anchor_region": string, "anchor_offset": [fx,fy] (0..1 within region),\n'
        f'        "tail_to_region": string,            // tail points at that region center\n'
        f'        "anchor": [x,y], "tail_target": [x,y], // raw-pixel alternative\n'
        f'        "role": string }} ]\n'
        f'  }}\n'
        f"All coordinates MUST be within the page ({pw} x {ph}). Prefer \"rect\" for simple\n"
        f"panels; use \"tiling\" for clean gap-free grids/strips; use \"shape\":\"path\" with\n"
        f"\"svg\" for curved or angled panels; use \"polygon\" for straight-edged non-rect panels.\n"
        f"Each text region MUST set \"role\" to one of: {roles}.\n"
        f"Overlays float above panels: prefer \"anchor_region\"+\"anchor_offset\" (and\n"
        f"\"tail_to_region\") so balloons sit inside a panel; use raw \"anchor\"/\"tail_target\"\n"
        f"pixels only for free placement. You may return questions, a layout, or both.\n"
        f"</instructions>"
    )
    return [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]


def resolve_provider_ids(provider: str) -> Tuple[str, str]:
    """Map a provider *display name* (or id/alias) to ``(api_key_id, registry_id)``.

    ``api_key_id`` is the id the app stores the key under (Google's key lives
    under ``"google"``); ``registry_id`` is the id ``core.llm_models`` knows
    (Google → ``"gemini"``). They intentionally differ only for Google. This is
    the single source of truth shared by the designer panel (model listing) and
    ``run_completion`` (the production call) so the two can't drift apart.
    """
    p = (provider or "").strip().lower()
    table = {
        "openai": ("openai", "openai"),
        "anthropic": ("anthropic", "anthropic"),
        "claude": ("anthropic", "anthropic"),   # defensive: display name is "Anthropic"
        "google": ("google", "gemini"),
        "gemini": ("google", "gemini"),
        "ollama": ("ollama", "ollama"),
        "lm studio": ("lmstudio", "lmstudio"),
        "lmstudio": ("lmstudio", "lmstudio"),
    }
    return table.get(p, (p, p))


@dataclass
class DesignerResult:
    questions: List[str] = field(default_factory=list)
    regions: Optional[List[Region]] = None
    overlays: List[Overlay] = field(default_factory=list)
    raw: str = ""


def fallback_result(page_px: Tuple[int, int]) -> DesignerResult:
    pw, ph = page_px
    region = Region(id="region1", kind="image", shape="rect",
                    bbox=(0, 0, pw, ph), name="full page")
    return DesignerResult(
        questions=["I couldn't parse a layout — here's a single full-page frame. "
                   "Tell me how to divide it."],
        regions=[region], raw="")


def _resolve_overlay_anchor(od: Dict, regions_by_id: Dict, page_px: Tuple[int, int]):
    """Resolve an overlay dict's placement to (anchor_px, anchor_mode, tail_px|None).

    Raw-pixel "anchor"/"tail_target" win; otherwise "anchor_region"+"anchor_offset"
    (0..1 within the region bbox) and "tail_to_region" (region center) are resolved
    against the already-parsed regions. Returns None (drop the overlay) if no anchor
    can be resolved. All resolution is logged on failure; never raises.
    """
    pw, ph = page_px
    anchor_mode = od.get("anchor_mode", "center")
    anchor = None
    raw = od.get("anchor")
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        anchor = (float(raw[0]), float(raw[1]))
    else:
        rid = od.get("anchor_region")
        if rid is not None and rid in regions_by_id:
            bx, by, bw, bh = regions_by_id[rid].bbox
            off = od.get("anchor_offset", [0.5, 0.5])
            if isinstance(off, (list, tuple)) and len(off) == 2:
                ox, oy = float(off[0]), float(off[1])
            else:
                ox, oy = 0.5, 0.5
            anchor = (bx + ox * bw, by + oy * bh)
        elif rid is not None:
            logger.warning("Designer overlay %r: unknown anchor_region %r; skipped",
                           od.get("id"), rid)
            return None
    if anchor is None:
        logger.warning("Designer overlay %r: no anchor or anchor_region; skipped", od.get("id"))
        return None
    anchor = (min(max(anchor[0], 0.0), float(pw)), min(max(anchor[1], 0.0), float(ph)))

    tail = None
    traw = od.get("tail_target")
    if isinstance(traw, (list, tuple)) and len(traw) == 2:
        tail = (float(traw[0]), float(traw[1]))
    else:
        trid = od.get("tail_to_region")
        if trid is not None and trid in regions_by_id:
            bx, by, bw, bh = regions_by_id[trid].bbox
            tail = (bx + bw / 2.0, by + bh / 2.0)
        elif trid is not None:
            logger.warning("Designer overlay %r: unknown tail_to_region %r; tail dropped",
                           od.get("id"), trid)
    return anchor, anchor_mode, tail


def _build_overlay(od: Dict, regions_by_id: Dict, page_px: Tuple[int, int], idx: int):
    """Build one Overlay from an LLM overlay dict, or None to skip it."""
    kind = od.get("kind")
    if kind not in ("speech", "thought", "caption", "sfx"):
        logger.warning("Designer overlay %r: unknown kind %r; skipped", od.get("id"), kind)
        return None
    resolved = _resolve_overlay_anchor(od, regions_by_id, page_px)
    if resolved is None:
        return None
    anchor, anchor_mode, tail = resolved
    try:
        z = int(od.get("z", 0))
    except (TypeError, ValueError):
        z = 0
    return Overlay(
        id=od.get("id", f"ov{idx + 1}"), kind=kind, text=str(od.get("text", "")),
        anchor=anchor, anchor_mode=anchor_mode, tail_target=tail,
        z=z, role=od.get("role", ""),
    )


def _regions_from_tiling(tspec, page_px: Tuple[int, int]) -> List[Region]:
    """Expand a tiling-preset request into gap-free panel Regions (or [] on failure)."""
    if not isinstance(tspec, dict):
        return []
    from core.layout import tiling
    preset = tspec.get("preset")
    params = tspec.get("params") or {}
    pw, ph = page_px
    try:
        if preset == "grid":
            tree = tiling.grid(int(params.get("rows", 2)), int(params.get("cols", 2)))
        elif preset == "three_tiers":
            tree = tiling.three_tiers()
        elif preset == "splash_with_strip":
            tree = tiling.splash_with_strip()
        elif preset == "diagonal_action":
            tree = tiling.diagonal_action()
        elif preset == "feature_L":
            tree = tiling.feature_L()
        else:
            logger.warning("Designer: unknown tiling preset %r; ignored", preset)
            return []
        gutter = float(params.get("gutter_px", 12))
        margin = float(params.get("margin_px", 24))
        return tiling.tile(tree, (0, 0, pw, ph), gutter=gutter, margin=margin)
    except Exception as e:  # noqa: BLE001 - degrade, never crash
        logger.warning("Designer: tiling preset %r failed: %s", preset, e)
        return []


def _normalize_region_dict(rd: Dict) -> Dict:
    """Map LLM region shorthands onto schema.region_from_dict's expected keys.

    "svg" -> shape="path" + "segments"; top-level "stroke_px" -> image_style.stroke_px.
    Returns a new dict; the caller's parsed dict is not mutated.
    """
    rd = dict(rd)
    svg = rd.pop("svg", None)
    if svg:
        from core.layout.svg_path import svg_to_segments
        segs = svg_to_segments(str(svg))
        rd["shape"] = "path"
        rd["segments"] = [{"type": s.type, "pts": [list(p) for p in s.pts]} for s in segs]
    stroke = rd.pop("stroke_px", None)
    if stroke is not None:
        istyle = dict(rd.get("image_style") or {})
        istyle.setdefault("stroke_px", stroke)
        rd["image_style"] = istyle
    return rd


def parse_response(content: str, page_px: Tuple[int, int]) -> DesignerResult:
    from gui.llm_utils import LLMResponseParser
    data = LLMResponseParser.parse_json_response(content, expected_type=dict)
    if not isinstance(data, dict):
        logger.warning("Designer: unparseable response, using fallback")
        return fallback_result(page_px)
    raw_questions = data.get("questions", [])
    questions = ([str(q) for q in raw_questions if str(q).strip()]
                 if isinstance(raw_questions, list) else [])
    regions = None
    overlays: List[Overlay] = []
    layout = data.get("layout")
    if isinstance(layout, dict):
        collected = []
        collected.extend(_regions_from_tiling(layout.get("tiling"), page_px))
        if isinstance(layout.get("regions"), list):
            for i, rd in enumerate(layout["regions"]):
                if not isinstance(rd, dict):
                    continue
                rd = _normalize_region_dict(rd)
                rd.setdefault("id", f"region{i + 1}")
                rd.setdefault("kind", "image")
                region = schema.region_from_dict(rd)
                collected.append(schema.normalize_region(region, page_px))
        if collected:
            regions = collected
        if isinstance(layout.get("overlays"), list):
            by_id = {r.id: r for r in (regions or [])}
            for i, od in enumerate(layout["overlays"]):
                if isinstance(od, dict):
                    ov = _build_overlay(od, by_id, page_px, i)
                    if ov is not None:
                        overlays.append(ov)
    if regions is None and not questions and not overlays:
        return fallback_result(page_px)
    return DesignerResult(questions=questions, regions=regions, overlays=overlays, raw=content)


def run_design(messages: List[Dict], page_px: Tuple[int, int],
               completion_fn: Callable[[List[Dict]], str]) -> DesignerResult:
    content = completion_fn(messages)
    return parse_response(content or "", page_px)


def run_completion(config, provider: str, model: str, messages: List[Dict],
                   temperature: float = 0.4) -> str:
    """Real LLM call (mirrors TextGenerationWorker). Not unit-tested (network)."""
    from gui.llm_utils import LiteLLMHandler
    from core.llm_models import get_provider_models, get_provider_prefix
    ok, litellm = LiteLLMHandler.setup_litellm(enable_console_logging=True)
    if not ok or litellm is None:
        raise RuntimeError("Failed to initialize LiteLLM")
    provider = provider or (config.get_layout_llm_provider() if config else "google")
    pid_api, pid = resolve_provider_ids(provider)
    api_key = None
    auth_mode = "api-key"
    if pid_api == "google" and config is not None:
        am = config.get("auth_mode", "api-key")
        auth_mode = "gcloud" if am in ("gcloud", "Google Cloud Account") else "api-key"
    if auth_mode == "api-key" and config is not None:
        api_key = config.get_api_key(pid_api)
    models = get_provider_models(pid)
    model_name = model or (models[0] if models else None)
    if not model_name:
        raise RuntimeError(f"No models available for provider {provider!r}")
    prefix = get_provider_prefix(pid)
    full_model = f"{prefix}{model_name}" if prefix else model_name
    logger.info("Designer LLM request: provider=%s model=%s temperature=%s\nmessages=%s",
                provider, full_model, temperature, messages)
    kwargs = {"model": full_model, "messages": messages, "temperature": temperature}
    if api_key:
        kwargs["api_key"] = api_key
    resp = litellm.completion(**kwargs)
    if not resp or not resp.choices:
        raise RuntimeError("Empty LLM response")
    content = resp.choices[0].message.content or ""
    logger.info("Designer LLM response:\n%s", content)
    return content
