"""LLM contract "Sprite Pose Steps — Strict v1.0" (pattern: Docs/LLM-Contracts.md).

Turns one action card into N per-frame pose sentences for the edit-chain
image route. The handler validates the reply and falls back to generic
evenly spaced poses, so the caller always gets exactly ``frames`` strings.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional

from core.llm_params import LLMParams, build_completion_kwargs
from core.llm_parsing import LLMResponseParser
from core.sprite.generation._common import emit
from core.sprite.generation.action_cards import default_chat_model
from core.sprite.generation.errors import classify_provider_error
from core.sprite.generation.prompts import FORBIDDEN_WORDS
from core.sprite.project import ActionCard

logger = logging.getLogger(__name__)

CONTRACT_NAME = "Sprite Pose Steps — Strict v1.0"
CONTRACT_VERSION = "1.0"
MAX_POSE_CHARS = 240

POSE_STEPS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["version", "action", "frames", "steps"],
    "properties": {
        "version": {"const": CONTRACT_VERSION},
        "action": {"type": "string"},
        "frames": {"type": "integer", "minimum": 1},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["index", "pose"],
                "properties": {
                    "index": {"type": "integer", "minimum": 1},
                    "pose": {"type": "string", "minLength": 1, "maxLength": MAX_POSE_CHARS},
                    "change": {"type": "string"},
                },
            },
        },
    },
}

SYSTEM_PROMPT = (
    f'You are "{CONTRACT_NAME}".\n'
    'Output must be a single JSON object that conforms exactly to the "Sprite Pose Steps Output Contract v1.0".\n'
    "Do not include commentary, Markdown, or code fences.\n\n"
    "Contract (JSON Schema):\n"
    f"{json.dumps(POSE_STEPS_SCHEMA, indent=2)}\n\n"
    "Rules:\n"
    "- Exactly FRAMES steps, index 1..FRAMES, in play order.\n"
    "- Every pose shows the same character, in the same view, at the same position in the frame. Only the body pose changes.\n"
    '- "pose" is one present-tense sentence about the full body (feet, legs, torso, arms, head).\n'
    '- "change" is one short phrase: what moved since the previous step.\n'
    "- Never mention the background, the camera, lighting, image size, or pixel dimensions.\n"
    "- For a looping action, the last step leads back into step 1.\n"
)

_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in FORBIDDEN_WORDS) + r")\b", re.IGNORECASE)


class PoseStepsContractError(ValueError):
    """The LLM reply does not satisfy the contract."""


def build_pose_messages(action: ActionCard, frames: int, character_notes: str = "") -> List[Dict[str, str]]:
    system = SYSTEM_PROMPT.replace("FRAMES", str(frames))
    user = (
        f"TASK: Break the action below into {frames} key poses for a sprite animation.\n"
        f"ACTION: name={action.name}; loop={'true' if action.loop else 'false'}; "
        f"duration_s={action.duration_s}; fps={action.fps}\n"
        f"DESCRIPTION: {action.prompt.strip()}\n"
        f"CHARACTER NOTES: {character_notes.strip() or '(none)'}\n"
        f"Return exactly one JSON object per the Sprite Pose Steps Output Contract v1.0 with frames={frames}."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_pose_steps(text: str, frames: int) -> List[str]:
    """Validate a reply against the contract and return ``frames`` pose sentences."""
    data = LLMResponseParser.parse_json_response(text, dict)
    if data is None:
        raise PoseStepsContractError("reply is not a JSON object")
    if str(data.get("version")) != CONTRACT_VERSION:
        raise PoseStepsContractError(f"version {data.get('version')!r} != {CONTRACT_VERSION!r}")
    steps = data.get("steps")
    if not isinstance(steps, list) or len(steps) != frames:
        got = len(steps) if isinstance(steps, list) else type(steps).__name__
        raise PoseStepsContractError(f"expected {frames} steps, got {got}")
    out: List[str] = []
    for k, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise PoseStepsContractError(f"step {k} is not an object")
        try:
            index = int(step.get("index", k))
        except (TypeError, ValueError):
            raise PoseStepsContractError(f"step {k} has a non-integer index")
        if index != k:
            raise PoseStepsContractError(f"step {k} has index {index}")
        pose = str(step.get("pose", "")).strip()
        if not pose:
            raise PoseStepsContractError(f"step {k} has an empty pose")
        change = str(step.get("change", "")).strip()
        sentence = pose if pose.endswith((".", "!")) else pose + "."
        if change:
            sentence += f" Change: {change.rstrip('.')}."
        sentence = _FORBIDDEN_RE.sub("", sentence)
        sentence = re.sub(r"\s{2,}", " ", sentence).strip()
        out.append(sentence[: MAX_POSE_CHARS * 2])
    return out


def fallback_pose_steps(action: ActionCard, frames: int) -> List[str]:
    """Generic evenly spaced poses when the LLM reply breaks the contract."""
    label = action.name.replace("_", " ")
    steps: List[str] = []
    for k in range(1, frames + 1):
        text = f"Key pose {k} of {frames} in the {label} cycle."
        if action.loop and k == frames:
            text += " The body returns toward the starting pose."
        steps.append(text)
    return steps


def _response_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    try:
        return response.choices[0].message.content or ""
    except (AttributeError, IndexError, TypeError):
        return str(response)


def generate_pose_instructions(
    action: ActionCard,
    frames: int,
    *,
    provider: str = "google",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    auth_mode: Optional[str] = None,
    character_notes: str = "",
    completion_fn: Optional[Callable[..., Any]] = None,
    log: Callable[[str], None] = logger.info,
) -> List[str]:
    """Ask the chat model for ``frames`` pose sentences; always returns ``frames`` strings."""
    if frames < 1:
        raise ValueError("frames must be >= 1")
    messages = build_pose_messages(action, frames, character_notes)
    model = model or default_chat_model(provider)
    if completion_fn is None:
        import litellm
        completion_fn = litellm.completion
    kwargs = build_completion_kwargs(
        provider, model, messages, LLMParams(temperature=0.4, max_tokens=2000),
        api_key=api_key, auth_mode=auth_mode,
    )
    redacted = {k: v for k, v in kwargs.items() if k not in ("api_key", "messages")}
    request_log = (
        f"[pose steps] request: provider={provider} model={kwargs.get('model')} params={redacted}\n"
        + "\n".join(f"--- {m['role']} ---\n{m['content']}" for m in messages)
    )
    emit(logger, log, request_log)
    try:
        response = completion_fn(**kwargs)
    except Exception as exc:  # noqa: BLE001 — every provider failure becomes a SpriteGenerationError
        emit(logger, log, f"[pose steps] completion failed: {exc}", level="error")
        raise classify_provider_error(exc) from exc
    text = _response_text(response)
    emit(logger, log, f"[pose steps] response:\n{text}")
    try:
        return parse_pose_steps(text, frames)
    except PoseStepsContractError as exc:
        emit(logger, log, f"[pose steps] contract violation: {exc}; using generic fallback steps",
             level="warning")
        return fallback_pose_steps(action, frames)
