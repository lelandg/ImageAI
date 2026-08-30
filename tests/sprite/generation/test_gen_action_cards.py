"""Tests for the 'Sprite Action Cards — Strict v1.0' LLM contract."""
import json
from types import SimpleNamespace

import pytest

from core.sprite.generation.action_cards import (
    ACTION_CARDS_SCHEMA,
    CONTRACT_NAME,
    GENRE_CHECKLISTS,
    SYSTEM_PROMPT,
    ActionCardDraft,
    build_messages,
    default_chat_model,
    draft_to_card,
    generate_action_cards,
    parse_action_cards,
)
from core.sprite.generation.errors import ProviderError, QuotaExceeded
from core.sprite.pipeline import Cancelled, CancelToken

VALID = {
    "version": "1.0",
    "cards": [
        {"name": "idle", "prompt": "the hero breathes slowly", "duration_s": 4,
         "loop": True, "target_frames": 6, "fps": 12},
        {"name": "attack", "prompt": "the hero swings a sword", "duration_s": 3,
         "loop": False, "target_frames": 8, "fps": 12},
    ],
}


def _response(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def test_contract_text_and_schema():
    assert "Sprite Action Cards — Strict v1.0" in SYSTEM_PROMPT
    assert CONTRACT_NAME in SYSTEM_PROMPT
    assert "code fences" in SYSTEM_PROMPT
    assert ACTION_CARDS_SCHEMA["properties"]["cards"]["items"]["required"] == [
        "name", "prompt", "duration_s", "loop", "target_frames", "fps"]
    assert ACTION_CARDS_SCHEMA["properties"]["cards"]["items"]["properties"]["duration_s"] == {
        "type": "integer", "minimum": 1, "maximum": 15}


def test_genre_checklists():
    assert set(GENRE_CHECKLISTS) == {"sidescroller", "top_down", "fighting"}
    assert GENRE_CHECKLISTS["sidescroller"] == [
        "idle", "walk", "run", "jump", "fall", "attack", "hurt", "death"]
    for names in GENRE_CHECKLISTS.values():
        assert names[0] == "idle" and len(names) == len(set(names))


def test_build_messages_shape_and_hygiene():
    messages = build_messages("a knight with a red cape", "sidescroller", "#00FF00", "cape flows")
    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[0]["content"] == SYSTEM_PROMPT
    user = messages[1]["content"]
    assert "BRIEF: a knight with a red cape" in user
    assert "idle, walk, run, jump, fall, attack, hurt, death" in user
    assert "CHARACTER NOTES: cape flows" in user
    assert "green" in user
    assert "16:9" not in user and "transparent" not in user.lower().replace('"transparent"', "")


def test_build_messages_rejects_unknown_genre():
    with pytest.raises(ValueError):
        build_messages("x", "rts", "#00FF00", "")


def test_parse_plain_json():
    cards = parse_action_cards(json.dumps(VALID))
    assert [c.name for c in cards] == ["idle", "attack"]
    assert cards[0] == ActionCardDraft("idle", "the hero breathes slowly", 4, True, 6, 12)


def test_parse_tolerates_fences_and_prose():
    fence = "`" * 3  # built at runtime so the Markdown plan file keeps its own fence intact
    text = f"Here you go:\n{fence}json\n" + json.dumps(VALID) + f"\n{fence}\nEnjoy."
    assert len(parse_action_cards(text)) == 2


def test_parse_accepts_bare_list():
    assert len(parse_action_cards(json.dumps(VALID["cards"]))) == 2


def test_parse_drops_invalid_names_durations_and_duplicates():
    data = {"version": "1.0", "cards": [
        {"name": "Walk Cycle", "prompt": "p", "duration_s": 4, "loop": True, "target_frames": 8, "fps": 12},
        {"name": "walk", "prompt": "p", "duration_s": 0, "loop": True, "target_frames": 8, "fps": 12},
        {"name": "walk", "prompt": "p", "duration_s": 16, "loop": True, "target_frames": 8, "fps": 12},
        {"name": "walk", "prompt": "p", "duration_s": 5, "loop": "true", "target_frames": 100, "fps": 13},
        {"name": "walk", "prompt": "dup", "duration_s": 5, "loop": True, "target_frames": 8, "fps": 12},
        {"name": "run", "prompt": "", "duration_s": 5, "loop": True, "target_frames": 8, "fps": 12},
    ]}
    cards = parse_action_cards(json.dumps(data))
    assert len(cards) == 1
    card = cards[0]
    assert card.name == "walk" and card.duration_s == 5 and card.loop is True
    assert card.target_frames == 64 and card.fps == 12


def test_parse_strips_forbidden_words_from_prompts():
    data = {"cards": [{"name": "idle", "prompt": "idle on a transparent 16:9 background",
                       "duration_s": 4, "loop": True, "target_frames": 8, "fps": 12}]}
    card = parse_action_cards(json.dumps(data))[0]
    assert "transparent" not in card.prompt and "16:9" not in card.prompt


def test_parse_raises_when_nothing_valid():
    with pytest.raises(ValueError):
        parse_action_cards("no json here")
    with pytest.raises(ValueError):
        parse_action_cards(json.dumps({"cards": []}))


def test_default_chat_model_resolves_per_provider():
    for provider in ("openai", "anthropic", "gemini", "google"):
        assert default_chat_model(provider)
    with pytest.raises(ValueError):
        default_chat_model("nope")


def test_generate_action_cards_logs_request_and_response(monkeypatch):
    calls = []
    def fake_completion(**kwargs):
        calls.append(kwargs)
        return _response(json.dumps(VALID))
    seen = []
    cards = generate_action_cards("a knight", "sidescroller", provider="openai",
                                  model="gpt-4o", api_key="sk-test", plate_color="#00FF00",
                                  completion_fn=fake_completion, log=seen.append)
    assert [c.name for c in cards] == ["idle", "attack"]
    kwargs = calls[0]
    assert kwargs["model"] == "gpt-4o" and kwargs["api_key"] == "sk-test"
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["temperature"] == 0.2
    joined = "\n".join(seen)
    assert "=== LLM REQUEST" in joined and "=== LLM RESPONSE" in joined
    assert "sk-test" not in joined
    assert SYSTEM_PROMPT in joined
    assert json.dumps(VALID) in joined


def test_generate_action_cards_resolves_default_model(monkeypatch):
    monkeypatch.setattr("core.sprite.generation.action_cards.default_chat_model",
                        lambda provider: "resolved-model")
    calls = []
    def fake_completion(**kwargs):
        calls.append(kwargs)
        return _response(json.dumps(VALID))
    generate_action_cards("a knight", "top_down", provider="openai", model=None,
                          api_key="k", plate_color="#00FF00", completion_fn=fake_completion)
    assert calls[0]["model"] == "resolved-model"


def test_generate_action_cards_classifies_provider_errors():
    def boom(**kwargs):
        raise RuntimeError("429 rate limit")
    with pytest.raises(QuotaExceeded):
        generate_action_cards("a knight", "fighting", provider="openai", model="gpt-4o",
                              api_key="k", plate_color="#00FF00", completion_fn=boom)


def test_generate_action_cards_wraps_malformed_response():
    def bad(**kwargs):
        return _response("not json")
    with pytest.raises(ProviderError, match="contract"):
        generate_action_cards("a knight", "fighting", provider="openai", model="gpt-4o",
                              api_key="k", plate_color="#00FF00", completion_fn=bad)


def test_draft_to_card():
    card = draft_to_card(ActionCardDraft("idle", "p", 4, True, 6, 12))
    assert card.name == "idle" and card.prompt == "p" and card.duration_s == 4
    assert card.loop is True and card.target_frames == 6 and card.fps == 12
    assert card.status == "draft" and len(card.id) == 32


def test_generate_action_cards_raises_before_the_completion_when_cancelled():
    """Minor 2: a cancelled token stops the contract before the LLM is called."""
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return _response(json.dumps(VALID))

    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        generate_action_cards("a knight", "fighting", provider="openai", model="gpt-4o",
                              api_key="k", plate_color="#00FF00",
                              completion_fn=fake_completion, token=token)
    assert calls == []


def test_generate_action_cards_raises_after_the_completion_when_cancelled():
    """Cancel during a slow chat call is honored as soon as the call returns."""
    token = CancelToken()
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        token.cancel()  # the user clicks Cancel while the chat call runs
        return _response(json.dumps(VALID))

    with pytest.raises(Cancelled):
        generate_action_cards("a knight", "fighting", provider="openai", model="gpt-4o",
                              api_key="k", plate_color="#00FF00",
                              completion_fn=fake_completion, token=token)
    assert len(calls) == 1
