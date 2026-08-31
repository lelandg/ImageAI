### Task 5: LLM contract "Sprite Pose Steps — Strict v1.0"

**Files:**
- Create: `core/sprite/generation/pose_steps.py`
- Test: `tests/sprite/test_pose_steps.py`

**Interfaces:**
- Consumes: `resolve_model(provider_id, family, static_default=None)` (`core/llm_models.py:63`); `LLMParams` (`core/llm_params.py:66-73`), `build_completion_kwargs(provider, model, messages, params, *, api_key, api_base, auth_mode, strict, on_warning)` (`core/llm_params.py:473`); `LLMResponseParser.parse_json_response(content, expected_type)` (`core/llm_parsing.py:19`); `FORBIDDEN_WORDS` (`core/sprite/generation/prompts.py`); `classify_provider_error` (`core/sprite/generation/errors.py`); `ActionCard` (`core/sprite/project.py`).
- Produces: `CONTRACT_NAME`, `POSE_STEPS_SCHEMA`, `SYSTEM_PROMPT`, `PoseStepsContractError(ValueError)`, `build_pose_messages(action, frames, character_notes="") -> List[Dict[str, str]]`, `parse_pose_steps(text, frames) -> List[str]`, `fallback_pose_steps(action, frames) -> List[str]`, `generate_pose_instructions(action, frames, *, provider="google", model=None, api_key=None, auth_mode=None, character_notes="", completion_fn=None, log=logger.info) -> List[str]`.

Contract (per `Docs/LLM-Contracts.md`): the system prompt names the contract and embeds the JSON Schema; the user prompt carries the action and reiterates `frames`; the code handler validates version, count, order, and non-empty poses, strips forbidden words, and falls back to generic evenly spaced poses on any contract violation. `completion_fn` is called as `completion_fn(**kwargs)` with the litellm kwargs (same convention as `action_cards.generate_action_cards`).

- [ ] **Step 1: Write the failing test**

Create `tests/sprite/test_pose_steps.py`:

```python
# tests/sprite/test_pose_steps.py
import json
from types import SimpleNamespace

import pytest

from core.sprite.generation.errors import SpriteGenerationError
from core.sprite.generation.pose_steps import (
    CONTRACT_NAME, PoseStepsContractError, build_pose_messages, fallback_pose_steps,
    generate_pose_instructions, parse_pose_steps,
)
from core.sprite.project import ActionCard


def _action(loop=True) -> ActionCard:
    return ActionCard(id="a1", name="walk", prompt="walks briskly to the right", duration_s=4,
                      loop=loop, target_frames=4, fps=12)


def _reply(frames=4, version="1.0"):
    steps = [{"index": k, "pose": f"Pose {k}: left foot forward, arms swing.", "change": f"step {k}"} for k in range(1, frames + 1)]
    return json.dumps({"version": version, "action": "walk", "frames": frames, "steps": steps})


def _fake_response(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def test_messages_name_contract_and_frames():
    msgs = build_pose_messages(_action(), 4, "red scarf")
    assert msgs[0]["role"] == "system" and CONTRACT_NAME in msgs[0]["content"]
    assert "Exactly 4 steps" in msgs[0]["content"]
    assert "frames=4" in msgs[1]["content"] and "red scarf" in msgs[1]["content"]
    for m in msgs:
        assert "transparent" not in m["content"].lower().replace("transparency", "")


def test_parse_valid_and_fenced():
    assert len(parse_pose_steps(_reply(), 4)) == 4
    fenced = "```json\n" + _reply() + "\n```"
    steps = parse_pose_steps(fenced, 4)
    assert steps[0].startswith("Pose 1") and steps[0].endswith("Change: step 1.")


def test_parse_rejects_wrong_count_version_order_and_empty():
    with pytest.raises(PoseStepsContractError):
        parse_pose_steps(_reply(frames=3), 4)
    with pytest.raises(PoseStepsContractError):
        parse_pose_steps(_reply(version="0.9"), 4)
    bad_order = json.loads(_reply())
    bad_order["steps"][0]["index"] = 2
    with pytest.raises(PoseStepsContractError):
        parse_pose_steps(json.dumps(bad_order), 4)
    empty = json.loads(_reply())
    empty["steps"][1]["pose"] = "  "
    with pytest.raises(PoseStepsContractError):
        parse_pose_steps(json.dumps(empty), 4)
    with pytest.raises(PoseStepsContractError):
        parse_pose_steps("not json", 4)


def test_parse_strips_forbidden_words():
    data = json.loads(_reply())
    data["steps"][0]["pose"] = "Jumps on a transparent checkerboard floor"
    steps = parse_pose_steps(json.dumps(data), 4)
    assert "transparent" not in steps[0].lower() and "checkerboard" not in steps[0].lower()
    assert "Jumps on a floor" in steps[0]


def test_fallback_steps_count_and_loop_hint():
    steps = fallback_pose_steps(_action(loop=True), 3)
    assert len(steps) == 3 and "walk" in steps[0] and "starting pose" in steps[-1]
    assert "starting pose" not in fallback_pose_steps(_action(loop=False), 3)[-1]


def test_generate_uses_completion_fn_and_logs_request(monkeypatch):
    seen = {}
    logged = []

    def fake_completion(**kwargs):
        seen.update(kwargs)
        return _fake_response(_reply())

    steps = generate_pose_instructions(_action(), 4, provider="google", model="test-chat-model",
                                       api_key="k", auth_mode="api-key", completion_fn=fake_completion,
                                       log=logged.append)
    assert len(steps) == 4
    assert seen["model"].endswith("test-chat-model") and seen["api_key"] == "k"
    assert seen["messages"][1]["content"].startswith("TASK:")
    assert any("request" in line and "test-chat-model" in line for line in logged)
    assert any("response" in line for line in logged)
    assert not any("api_key': 'k'" in line for line in logged)


def test_generate_accepts_plain_string_reply():
    steps = generate_pose_instructions(_action(), 4, model="m", completion_fn=lambda **kw: _reply())
    assert len(steps) == 4


def test_generate_falls_back_on_contract_violation():
    steps = generate_pose_instructions(_action(), 4, model="m", completion_fn=lambda **kw: "garbage")
    assert steps == fallback_pose_steps(_action(), 4)


def test_generate_wraps_provider_errors():
    def boom(**kw):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")
    with pytest.raises(SpriteGenerationError):
        generate_pose_instructions(_action(), 4, model="m", completion_fn=boom)


def test_generate_resolves_model_when_missing(monkeypatch):
    monkeypatch.setattr("core.sprite.generation.pose_steps.resolve_model", lambda p, f: "resolved-model")
    seen = {}

    def fake(**kw):
        seen.update(kw)
        return _reply()

    generate_pose_instructions(_action(), 4, provider="openai", completion_fn=fake)
    assert seen["model"].endswith("resolved-model")
```

- [ ] **Step 2: Run the test to see it fail**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pose_steps.py -v` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement the contract**

Create `core/sprite/generation/pose_steps.py`:

```python
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

from core.llm_models import resolve_model
from core.llm_params import LLMParams, build_completion_kwargs
from core.llm_parsing import LLMResponseParser
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
    model = model or resolve_model(provider, "chat")
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
    logger.info(request_log)
    log(request_log)
    try:
        response = completion_fn(**kwargs)
    except Exception as exc:  # noqa: BLE001 — every provider failure becomes a SpriteGenerationError
        logger.error("[pose steps] completion failed: %s", exc)
        log(f"[pose steps] completion failed: {exc}")
        raise classify_provider_error(exc) from exc
    text = _response_text(response)
    logger.info("[pose steps] response:\n%s", text)
    log(f"[pose steps] response:\n{text}")
    try:
        return parse_pose_steps(text, frames)
    except PoseStepsContractError as exc:
        logger.warning("[pose steps] contract violation (%s); using fallback steps", exc)
        log(f"[pose steps] contract violation: {exc}; using generic fallback steps")
        return fallback_pose_steps(action, frames)
```

- [ ] **Step 4: Run the test to see it pass**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pose_steps.py -v` → 10 passed.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/generation/pose_steps.py tests/sprite/test_pose_steps.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): Sprite Pose Steps strict v1.0 LLM contract with fallback"
```

---

