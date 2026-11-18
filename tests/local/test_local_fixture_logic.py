"""Tests for the local-tier fixture logic. No server needed; always runs."""

import pytest

from local_logic import parse_listing, pick_lmstudio_model, pick_ollama_model

SKIP = pytest.skip.Exception
FAIL = pytest.fail.Exception


def _v1(*entries):
    return {"models": list(entries)}


def test_empty_list_skips():
    with pytest.raises(SKIP):
        pick_lmstudio_model(parse_listing(_v1()))


def test_only_embedding_models_skips():
    models = parse_listing(_v1({"key": "e", "type": "embedding"}))
    with pytest.raises(SKIP, match="only embedding"):
        pick_lmstudio_model(models)


def test_unrecognised_types_fail_and_name_them():
    models = parse_listing(_v1({"key": "a", "type": "chat-thing", "extra": 1}))
    with pytest.raises(FAIL) as err:
        pick_lmstudio_model(models)
    assert "chat-thing" in str(err.value)
    assert "extra" in str(err.value)


def test_missing_type_field_fails_not_skips():
    models = parse_listing(_v1({"key": "a"}))
    with pytest.raises(FAIL):
        pick_lmstudio_model(models)


def test_unknown_top_level_key_fails_and_names_keys():
    with pytest.raises(FAIL) as err:
        parse_listing({"things": [], "count": 0})
    assert "things" in str(err.value) and "count" in str(err.value)


def test_non_dict_body_fails():
    with pytest.raises(FAIL):
        parse_listing([1, 2])


def test_named_model_missing_fails():
    models = parse_listing(_v1({"key": "a", "type": "llm"}))
    with pytest.raises(FAIL, match="IMAGEAI_LMSTUDIO_MODEL"):
        pick_lmstudio_model(models, "nope")


def test_named_model_found():
    models = parse_listing(_v1({"key": "a", "type": "llm"},
                               {"key": "b", "type": "llm"}))
    assert pick_lmstudio_model(models, "b").key == "b"


def test_loaded_model_beats_larger_unloaded_one():
    models = parse_listing(_v1(
        {"key": "small", "type": "llm", "size_bytes": 1},
        {"key": "big", "type": "llm", "size_bytes": 99,
         "loaded_instances": [{"id": "big"}]}))
    assert pick_lmstudio_model(models).key == "big"


def test_smallest_chat_model_when_none_loaded():
    models = parse_listing(_v1(
        {"key": "big", "type": "llm", "size_bytes": 99},
        {"key": "small", "type": "llm", "size_bytes": 5},
        {"key": "emb", "type": "embedding", "size_bytes": 1}))
    assert pick_lmstudio_model(models).key == "small"


def test_vision_flag_read_when_present():
    models = parse_listing(_v1(
        {"key": "a", "type": "llm", "capabilities": {"vision": True}},
        {"key": "b", "type": "llm", "capabilities": {"vision": False}}))
    assert [m.vision for m in models] == [True, False]


def test_vision_unknown_when_absent():
    models = parse_listing(_v1({"key": "a", "type": "llm"}))
    assert models[0].vision is None


def test_v0_listing_marks_vision_by_type_and_loaded_by_state():
    models = parse_listing({"object": "list", "data": [
        {"id": "v", "type": "vlm", "state": "loaded"},
        {"id": "t", "type": "llm", "state": "not-loaded"}]})
    assert [(m.key, m.vision, m.loaded) for m in models] == [
        ("v", True, True), ("t", False, False)]


def test_ollama_picks_smallest_completion_model_and_reads_vision():
    caps = {"emb": ["embedding"], "small": ["completion", "vision"],
            "big": ["completion"]}
    name, vision = pick_ollama_model(
        ["big", "emb", "small"], {"big": 9, "emb": 1, "small": 4}, None, caps.get)
    assert (name, vision) == ("small", True)


def test_ollama_unreadable_capabilities_trusts_name_vision_unknown():
    assert pick_ollama_model(["a"], {}, None, lambda n: None) == ("a", None)


def test_ollama_named_model_missing_fails():
    with pytest.raises(FAIL, match="IMAGEAI_OLLAMA_MODEL"):
        pick_ollama_model(["a"], {}, "zzz", lambda n: ["completion"])


def test_ollama_no_completion_model_skips():
    with pytest.raises(SKIP):
        pick_ollama_model(["e"], {}, None, lambda n: ["embedding"])
