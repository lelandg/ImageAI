"""Phase 5b — batch fill core (pure: request build + result mapping)."""
import base64
import json

from core.layout.models import DocumentSpec, PageSpec, Region
from core.layout import batch_fill


def _doc(regions):
    return DocumentSpec(title="D", pages=[PageSpec(page_size_px=(1000, 1000), regions=regions)])


def test_build_requests_only_prompted_image_regions():
    doc = _doc([
        Region(id="i1", kind="image", bbox=(0, 0, 100, 100), prompt="a cat"),
        Region(id="i2", kind="image", bbox=(0, 0, 50, 50), prompt=""),       # no prompt
        Region(id="t1", kind="text", bbox=(0, 0, 50, 50), text="hi", prompt="x"),  # text
        Region(id="i3", kind="image", bbox=(0, 0, 100, 100), prompt="a dog"),
    ])
    requests, skipped = batch_fill.build_requests(doc, model="gemini-3-pro-image-preview")
    assert [r.key for r in requests] == ["i1", "i3"]      # key = region id
    assert all(r.model == "gemini-3-pro-image-preview" for r in requests)
    assert requests[0].prompt == "a cat"
    assert skipped == ["i2"]                              # prompt-less image region


def test_build_requests_only_empty_skips_filled():
    doc = _doc([
        Region(id="i1", kind="image", bbox=(0, 0, 100, 100), prompt="a cat", image_ref="/x.png"),
        Region(id="i2", kind="image", bbox=(0, 0, 100, 100), prompt="a dog"),
    ])
    requests, _ = batch_fill.build_requests(doc, model="m", only_empty=True)
    assert [r.key for r in requests] == ["i2"]            # i1 already filled


def test_nearest_supported_ratio():
    assert batch_fill.nearest_supported_ratio(1000, 1000) == "1:1"
    assert batch_fill.nearest_supported_ratio(1920, 1080) == "16:9"
    assert batch_fill.nearest_supported_ratio(1080, 1920) == "9:16"
    assert batch_fill.nearest_supported_ratio(0, 0) == "1:1"     # degenerate guard
    # a 3:4-ish region snaps to a portrait ratio, never landscape
    assert batch_fill.nearest_supported_ratio(750, 1000) in {"3:4", "4:5"}


def _jsonl_line(key, raw_bytes):
    b64 = base64.b64encode(raw_bytes).decode("ascii")
    return json.dumps({
        "key": key,
        "response": {"candidates": [
            {"content": {"parts": [{"inline_data": {"data": b64}}]}}]},
    })


def test_parse_result_jsonl_keys_images():
    text = "\n".join([
        _jsonl_line("i1", b"IMG-1"),
        "not json",                                       # skipped
        json.dumps({"key": "i2", "response": {}}),        # no image -> skipped
        json.dumps({"response": {"candidates": []}}),     # no key -> skipped
        _jsonl_line("i3", b"IMG-3"),
    ])
    out = batch_fill.parse_result_jsonl(text)
    assert out == {"i1": b"IMG-1", "i3": b"IMG-3"}


def test_results_to_placements_filters_to_doc_regions():
    doc = _doc([Region(id="i1", kind="image", bbox=(0, 0, 10, 10), prompt="x")])
    placements = batch_fill.results_to_placements(doc, {"i1": b"A", "ghost": b"B"})
    assert placements == [("i1", b"A")]                   # 'ghost' not in the doc
