"""Tests for the pure (LLM-injected) style derivation pipeline."""
import json
from pathlib import Path

import pytest
from PIL import Image

from core.styles.analyzer import (
    ANALYZE_CHUNK_SIZE, MAX_LLM_IMAGE_DIM, StyleAnalysisError,
    build_chunk_messages, chunk_paths, derive_style_data,
    encode_image_for_llm, flatten_descriptor, merge_descriptors,
    parse_descriptor,
)
from core.styles.models import DESCRIPTOR_KEYS

DESC = {k: f"{k} value" for k in DESCRIPTOR_KEYS}


def _imgs(tmp_path, n, size=(64, 64)):
    out = []
    for i in range(n):
        p = tmp_path / f"img{i}.png"
        Image.new("RGB", size, (i * 10 % 255, 80, 80)).save(p)
        out.append(p)
    return out


def test_chunk_paths():
    paths = [Path(f"{i}.png") for i in range(20)]
    chunks = chunk_paths(paths)
    assert [len(c) for c in chunks] == [8, 8, 4]
    assert chunk_paths(paths[:8]) == [paths[:8]]
    assert chunk_paths([]) == []


def test_encode_image_downscales(tmp_path):
    (p,) = _imgs(tmp_path, 1, size=(4000, 500))
    mime, b64 = encode_image_for_llm(p)
    assert mime == "image/jpeg"
    import base64, io
    with Image.open(io.BytesIO(base64.b64decode(b64))) as img:
        assert max(img.size) <= MAX_LLM_IMAGE_DIM


def test_build_chunk_messages_shape(tmp_path):
    paths = _imgs(tmp_path, 2)
    messages = build_chunk_messages(paths)
    assert len(messages) == 1 and messages[0]["role"] == "user"
    parts = messages[0]["content"]
    assert parts[0]["type"] == "text"
    assert "JSON" in parts[0]["text"]
    assert "aspect" in parts[0]["text"].lower()  # forbids ratio tokens
    images = [p for p in parts if p.get("type") == "image_url"]
    assert len(images) == 2
    assert images[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_parse_descriptor_fenced_and_filtered():
    fenced = "```json\n" + json.dumps({**DESC, "extra": "x"}) + "\n```"
    d = parse_descriptor(fenced)
    assert d is not None and set(d.keys()) == set(DESCRIPTOR_KEYS)
    assert parse_descriptor("not json at all") is None
    assert parse_descriptor("") is None


def test_flatten_descriptor_caps_words():
    desc = dict(DESC)
    desc["summary"] = "word " * 200
    text = flatten_descriptor(desc)
    assert 0 < len(text.split()) <= 80
    assert "negative value" not in text  # negative excluded from prompt text


def test_merge_single_descriptor_skips_llm():
    calls = []
    def completion_fn(messages):
        calls.append(messages)
        return "{}"
    merged = merge_descriptors([DESC], completion_fn)
    assert calls == []  # single chunk: no reduce call
    assert merged["summary"] == DESC["summary"]
    assert merged["prompt_text"] == flatten_descriptor(DESC)


def test_merge_multiple_uses_llm():
    reply = json.dumps({**DESC, "prompt_text": "merged style text"})
    merged = merge_descriptors([DESC, DESC], lambda m: reply)
    assert merged["prompt_text"] == "merged style text"


def test_merge_multiple_llm_garbage_falls_back():
    merged = merge_descriptors([DESC, dict(DESC)], lambda m: "garbage")
    # fallback: first descriptor + deterministic flatten
    assert merged["summary"] == DESC["summary"]
    assert merged["prompt_text"] == flatten_descriptor(DESC)


def test_derive_style_data_two_chunks(tmp_path):
    paths = _imgs(tmp_path, ANALYZE_CHUNK_SIZE + 1)  # -> 2 chunks
    vision_calls = []
    def vision_fn(messages):
        vision_calls.append(messages)
        return json.dumps(DESC)
    def completion_fn(messages):
        return json.dumps({**DESC, "prompt_text": "final text"})
    progress = []
    result = derive_style_data(paths, vision_fn, completion_fn,
                               progress_cb=progress.append)
    assert len(vision_calls) == 2
    assert result["prompt_text"] == "final text"
    assert set(result["descriptor"].keys()) == set(DESCRIPTOR_KEYS)
    assert any("chunk" in p.lower() for p in progress)


def test_derive_style_data_unparseable_chunk_raises(tmp_path):
    paths = _imgs(tmp_path, 2)
    with pytest.raises(StyleAnalysisError):
        derive_style_data(paths, lambda m: "not json", lambda m: "{}")


def test_derive_style_data_no_paths_raises(tmp_path):
    with pytest.raises(StyleAnalysisError):
        derive_style_data([], lambda m: "{}", lambda m: "{}")
