# tests/sprite/test_pose_steps.py
import json
import logging
from types import SimpleNamespace

import pytest

from core.sprite.generation.action_cards import default_chat_model
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


def test_generate_default_log_writes_each_full_content_message_once(caplog):
    caplog.set_level(logging.INFO, logger="core.sprite.generation.pose_steps")

    generate_pose_instructions(_action(), 4, model="m", completion_fn=lambda **kw: _reply())

    messages = [r.getMessage() for r in caplog.records]
    request_lines = [m for m in messages if m.startswith("[pose steps] request:")]
    response_lines = [m for m in messages if m.startswith("[pose steps] response:")]
    assert len(request_lines) == 1
    assert len(response_lines) == 1


def test_generate_resolves_model_when_missing(monkeypatch):
    monkeypatch.setattr("core.sprite.generation.pose_steps.default_chat_model", lambda p: "resolved-model")
    seen = {}

    def fake(**kw):
        seen.update(kw)
        return _reply()

    generate_pose_instructions(_action(), 4, provider="openai", completion_fn=fake)
    assert seen["model"].endswith("resolved-model")


def test_generate_default_model_resolves_to_a_real_model_not_the_family_name():
    """No monkeypatch of the resolver: exercise the real default_chat_model() path."""
    seen = {}

    def fake(**kw):
        seen.update(kw)
        return _reply()

    generate_pose_instructions(_action(), 4, provider="gemini", completion_fn=fake)
    resolved = seen["model"].rsplit("/", 1)[-1]
    assert resolved != "chat"
    assert resolved == default_chat_model("gemini")
