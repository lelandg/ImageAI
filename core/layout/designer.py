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


@dataclass
class DesignerResult:
    questions: List[str] = field(default_factory=list)
    regions: Optional[List[Region]] = None
    raw: str = ""


def fallback_result(page_px: Tuple[int, int]) -> DesignerResult:
    pw, ph = page_px
    region = Region(id="region1", kind="image", shape="rect",
                    bbox=(0, 0, pw, ph), name="full page")
    return DesignerResult(
        questions=["I couldn't parse a layout — here's a single full-page frame. "
                   "Tell me how to divide it."],
        regions=[region], raw="")


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
    layout = data.get("layout")
    if isinstance(layout, dict) and isinstance(layout.get("regions"), list):
        regions = []
        for i, rd in enumerate(layout["regions"]):
            if not isinstance(rd, dict):
                continue
            rd = dict(rd)  # don't mutate the parsed dict
            rd.setdefault("id", f"region{i + 1}")
            rd.setdefault("kind", "image")
            region = schema.region_from_dict(rd)
            regions.append(schema.normalize_region(region, page_px))
        if not regions:
            regions = None
    if regions is None and not questions:
        return fallback_result(page_px)
    return DesignerResult(questions=questions, regions=regions, raw=content)


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
    provider_map = {"google": "google", "anthropic": "anthropic", "openai": "openai",
                    "ollama": "ollama", "lm studio": "lmstudio"}
    pid_api = provider_map.get(provider.lower(), provider.lower())
    pid = "gemini" if pid_api == "google" else pid_api
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
