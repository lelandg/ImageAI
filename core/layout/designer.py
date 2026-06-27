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
        f"Return a JSON object with optional keys:\n"
        f'  "questions": [strings]   // ask for missing detail if needed\n'
        f'  "layout": {{ "regions": [ {{\n'
        f'      "id": string, "kind": "image"|"text", "shape": "rect"|"polygon",\n'
        f'      "bbox": [x,y,w,h], "points": [[x,y],...] (polygon only),\n'
        f'      "z": int, "role": string, "text": string (text only) }} ] }}\n'
        f"All coordinates MUST be within the page ({pw} x {ph}). Prefer 'rect' unless the\n"
        f"Each text region MUST set \"role\" to one of: {roles}.\n"
        f"request implies panels that flow into each other (then use 'polygon'). You may\n"
        f"return questions, a layout, or both.\n"
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
    return Overlay(
        id=od.get("id", f"ov{idx + 1}"), kind=kind, text=str(od.get("text", "")),
        anchor=anchor, anchor_mode=anchor_mode, tail_target=tail,
        z=int(od.get("z", 0)), role=od.get("role", ""),
    )


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
        if isinstance(layout.get("regions"), list):
            collected = []
            for i, rd in enumerate(layout["regions"]):
                if not isinstance(rd, dict):
                    continue
                rd = dict(rd)  # don't mutate the parsed dict
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
