"""LLM contract "Sprite Action Cards — Strict v1.0" (design §4.2).

Turns a brief plus a genre checklist into action cards. Follows
``Docs/LLM-Contracts.md``: a versioned system prompt, a user prompt that
restates the constraints, and a strict validator with a tolerant parser.
Request and response are logged in full (``Docs/LLM-Logging-Full-Content.md``).
"""
import json
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from core.llm_models import resolve_model
from core.llm_params import LLMParams, build_completion_kwargs, normalize_provider
from core.llm_parsing import LLMResponseParser
from core.sprite.generation._common import emit
from core.sprite.generation.errors import ProviderError, classify_provider_error
from core.sprite.generation.prompts import color_name, normalize_hex, strip_render_terms
from core.sprite.project import ActionCard

logger = logging.getLogger(__name__)

CONTRACT_NAME = "Sprite Action Cards — Strict v1.0"
CONTRACT_VERSION = "1.0"
ALLOWED_FPS = (8, 12, 24)
MIN_DURATION_S, MAX_DURATION_S = 1, 15
MIN_FRAMES, MAX_FRAMES = 2, 64
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")

GENRE_CHECKLISTS: Dict[str, List[str]] = {
    "sidescroller": ["idle", "walk", "run", "jump", "fall", "attack", "hurt", "death"],
    "top_down": ["idle", "walk_down", "walk_up", "walk_side", "attack", "hurt", "death"],
    "fighting": ["idle", "walk_forward", "walk_back", "crouch", "jump", "light_punch",
                 "heavy_kick", "block", "hurt", "knockdown"],
}

ACTION_CARDS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["version", "cards"],
    "properties": {
        "version": {"type": "string", "const": CONTRACT_VERSION},
        "cards": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["name", "prompt", "duration_s", "loop", "target_frames", "fps"],
                "properties": {
                    "name": {"type": "string", "pattern": _NAME_RE.pattern},
                    "prompt": {"type": "string", "minLength": 1},
                    "duration_s": {"type": "integer", "minimum": MIN_DURATION_S,
                                   "maximum": MAX_DURATION_S},
                    "loop": {"type": "boolean"},
                    "target_frames": {"type": "integer", "minimum": MIN_FRAMES,
                                      "maximum": MAX_FRAMES},
                    "fps": {"type": "integer", "enum": list(ALLOWED_FPS)},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

SYSTEM_PROMPT = f"""You are "{CONTRACT_NAME}".
You design animation action cards for a 2D game sprite.
Output must be a single JSON object that conforms exactly to the Sprite Action Cards Output Contract v{CONTRACT_VERSION}.
Do not include commentary, Markdown, or code fences.

Contract v{CONTRACT_VERSION}:
{{"version": "{CONTRACT_VERSION}", "cards": [{{"name": string, "prompt": string, "duration_s": integer, "loop": boolean, "target_frames": integer, "fps": integer}}]}}

Rules:
- name: snake_case ASCII, unique, 2-32 characters (examples: idle, walk, attack_heavy).
- prompt: one paragraph that describes the motion of the character only, in the present tense. Start with "the character". Never describe the background, the camera, the aspect ratio, the resolution, or transparency. Never use the words "transparent", "checkerboard", or "alpha".
- duration_s: integer {MIN_DURATION_S}..{MAX_DURATION_S}.
- loop: true for cycles (idle, walk, run), false for one-shot actions (attack, hurt, death).
- target_frames: integer {MIN_FRAMES}..{MAX_FRAMES}.
- fps: one of {", ".join(str(f) for f in ALLOWED_FPS)}.
- Cover every action in the genre checklist first, in the given order, then add up to 4 more that fit the brief.
"""

USER_PROMPT_TEMPLATE = """TASK: Create action cards for this character.
Return exactly one JSON object per the Sprite Action Cards Output Contract v{version}.

BRIEF: {brief}
GENRE: {genre}
GENRE CHECKLIST (required, in this order): {checklist}
CHARACTER NOTES: {character_notes}
BACKGROUND: the application appends the background instruction (a solid {color_name} plate) after your prompt. Do not mention the background.

CONSTRAINTS:
- One card per checklist item, then optional extras.
- name in snake_case; duration_s integer {min_s}..{max_s}; fps in [{fps_list}].
- No fields beyond the contract.
"""


@dataclass
class ActionCardDraft:
    name: str
    prompt: str
    duration_s: int
    loop: bool
    target_frames: int
    fps: int


def build_messages(brief: str, genre: str, plate_color: str,
                   character_notes: str) -> List[Dict[str, str]]:
    """System + user messages for the contract. Raises ``ValueError`` on an unknown genre."""
    if genre not in GENRE_CHECKLISTS:
        raise ValueError(f"Unknown genre {genre!r}. Use one of {sorted(GENRE_CHECKLISTS)}.")
    user = USER_PROMPT_TEMPLATE.format(
        version=CONTRACT_VERSION,
        brief=brief.strip(),
        genre=genre,
        checklist=", ".join(GENRE_CHECKLISTS[genre]),
        character_notes=character_notes.strip() or "(none)",
        color_name=color_name(normalize_hex(plate_color)),
        min_s=MIN_DURATION_S, max_s=MAX_DURATION_S,
        fps_list=", ".join(str(f) for f in ALLOWED_FPS),
    )
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user}]


def _extract_json(text: str) -> Optional[Any]:
    parsed = LLMResponseParser.parse_json_response(text, expected_type=dict)
    if parsed is None:
        parsed = LLMResponseParser.parse_json_response(text, expected_type=list)
    if parsed is not None:
        return parsed
    # Fences or prose around the object: take the outermost braces / brackets.
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if 0 <= start < end:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    return None


def _as_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    return None


def _as_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def parse_action_cards(text: str) -> List[ActionCardDraft]:
    """Validate a contract response. Tolerates fences and prose.

    Invalid cards are dropped with a logged warning: bad snake_case names,
    duration outside 1..15, empty prompts, duplicate names (first wins).
    ``target_frames`` is clamped to 2..64 and ``fps`` snaps to 8/12/24.
    Raises ``ValueError`` when no valid card remains.
    """
    data = _extract_json(text or "")
    if data is None:
        raise ValueError("Response contained no JSON object.")
    if isinstance(data, dict):
        version = data.get("version")
        if version is not None and str(version) != CONTRACT_VERSION:
            logger.warning("Action cards: contract version %r, expected %r", version, CONTRACT_VERSION)
        cards = data.get("cards")
    else:
        cards = data
    if not isinstance(cards, list):
        raise ValueError("Response JSON has no 'cards' list.")

    drafts: List[ActionCardDraft] = []
    seen = set()
    for index, item in enumerate(cards):
        if not isinstance(item, dict):
            logger.warning("Action card %d is not an object; dropped", index)
            continue
        name = str(item.get("name", "")).strip()
        if not _NAME_RE.match(name):
            logger.warning("Action card %d: name %r is not snake_case; dropped", index, name)
            continue
        if name in seen:
            logger.warning("Action card %d: duplicate name %r; dropped", index, name)
            continue
        prompt = strip_render_terms(str(item.get("prompt", "")))
        if not prompt:
            logger.warning("Action card %d (%s): empty prompt; dropped", index, name)
            continue
        duration = _as_int(item.get("duration_s"))
        if duration is None or not MIN_DURATION_S <= duration <= MAX_DURATION_S:
            logger.warning("Action card %d (%s): duration_s %r outside %d..%d; dropped",
                           index, name, item.get("duration_s"), MIN_DURATION_S, MAX_DURATION_S)
            continue
        loop = _as_bool(item.get("loop"))
        if loop is None:
            loop = True
            logger.warning("Action card %d (%s): loop missing; assumed true", index, name)
        frames = _as_int(item.get("target_frames"))
        if frames is None:
            frames = 8
        frames = max(MIN_FRAMES, min(MAX_FRAMES, frames))
        fps_value = _as_int(item.get("fps"))
        if fps_value is None:
            fps_value = 12
        fps_value = min(ALLOWED_FPS, key=lambda f: abs(f - fps_value))
        seen.add(name)
        drafts.append(ActionCardDraft(name=name, prompt=prompt, duration_s=duration,
                                      loop=loop, target_frames=frames, fps=fps_value))
    if not drafts:
        raise ValueError("Response contained no valid action card.")
    return drafts


# Registry family per chat provider; static defaults are offline fallbacks only.
_CHAT_FAMILY = {
    "openai": ("openai", "chat", "gpt-4o"),
    "anthropic": ("anthropic", "sonnet", "claude-sonnet-4-6"),
    "gemini": ("gemini", "flash", "gemini-2.5-flash"),
}


def default_chat_model(provider: str) -> str:
    """Current chat model id for ``provider`` via the model registry."""
    provider_id = normalize_provider(provider)
    if provider_id not in _CHAT_FAMILY:
        raise ValueError(f"No default chat model for provider {provider!r}.")
    registry_provider, family, static = _CHAT_FAMILY[provider_id]
    return resolve_model(registry_provider, family, static_default=static)


def _response_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        choices = response.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            return str(message.get("content") or "")
        return ""
    choices = getattr(response, "choices", None) or []
    if choices:
        message = getattr(choices[0], "message", None)
        return str(getattr(message, "content", "") or "")
    return str(response)


def generate_action_cards(brief: str, genre: str, *, provider: str, model: Optional[str],
                          api_key: Optional[str], plate_color: str, character_notes: str = "",
                          auth_mode: Optional[str] = None,
                          completion_fn: Optional[Callable[..., Any]] = None,
                          log: Callable[[str], None] = logger.info) -> List[ActionCardDraft]:
    """Run the contract against a chat model and return validated drafts.

    ``completion_fn`` defaults to ``litellm.completion``. Kwargs come from
    ``build_completion_kwargs`` (temperature 0.2, max_tokens 4000, JSON mode
    where the model supports it). The model defaults to
    ``default_chat_model(provider)``.
    """
    provider_id = normalize_provider(provider)
    model_id = model or default_chat_model(provider_id)
    messages = build_messages(brief, genre, plate_color, character_notes)
    params = LLMParams(temperature=0.2, max_tokens=4000,
                       response_format={"type": "json_object"})
    kwargs = build_completion_kwargs(provider_id, model_id, messages, params,
                                     api_key=api_key, auth_mode=auth_mode,
                                     on_warning=lambda m: emit(logger, log, m, level="warning"))

    shown = {k: v for k, v in kwargs.items() if k not in ("messages", "api_key")}
    emit(logger, log, f"=== LLM REQUEST ({CONTRACT_NAME}) ===")
    emit(logger, log, f"provider={provider_id} model={kwargs['model']} params={json.dumps(shown, default=str)}")
    for message in messages:
        emit(logger, log, f"{message['role']} (FULL, {len(message['content'])} chars):\n{message['content']}")
    emit(logger, log, "=== END LLM REQUEST ===")

    if completion_fn is None:
        import litellm
        litellm.drop_params = True
        completion_fn = litellm.completion

    try:
        response = completion_fn(**kwargs)
    except Exception as exc:  # noqa: BLE001 - classified below
        err = classify_provider_error(exc, provider=provider_id)
        emit(logger, log, f"Action cards failed: {err.user_message}", level="error")
        raise err from exc

    text = _response_text(response)
    emit(logger, log, "=== LLM RESPONSE ===")
    emit(logger, log, f"Response length: {len(text)} characters")
    emit(logger, log, f"Full response:\n{text}")
    emit(logger, log, "=== END LLM RESPONSE ===")

    try:
        drafts = parse_action_cards(text)
    except ValueError as exc:
        err = ProviderError(f"The model did not follow the {CONTRACT_NAME} contract: {exc} "
                            "Try again or pick another model.")
        emit(logger, log, err.user_message, level="error")
        raise err from exc
    emit(logger, log, f"Action cards: {len(drafts)} valid card(s): "
                      f"{', '.join(d.name for d in drafts)}")
    return drafts


def draft_to_card(draft: ActionCardDraft) -> ActionCard:
    """Promote a draft to a project ``ActionCard`` with a fresh id."""
    return ActionCard(id=uuid.uuid4().hex, name=draft.name, prompt=draft.prompt,
                      duration_s=draft.duration_s, loop=draft.loop,
                      target_frames=draft.target_frames, fps=draft.fps)
