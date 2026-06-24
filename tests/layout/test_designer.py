from core.layout.models import Region
from core.layout import designer


def test_build_messages_includes_context_and_json_instruction():
    msgs = designer.build_messages("comic", (1000, 800), "9 panels that flow into each other")
    assert isinstance(msgs, list) and msgs[0]["role"] == "system"
    joined = " ".join(m["content"] for m in msgs)
    assert "comic" in joined
    assert "1000" in joined and "800" in joined
    assert "9 panels that flow into each other" in joined
    assert "JSON" in joined or "json" in joined
    assert "regions" in joined  # tells the model our schema key


def test_build_messages_includes_current_layout_when_iterating():
    regions = [Region(id="r1", kind="image", bbox=(0, 0, 500, 500))]
    msgs = designer.build_messages("comic", (1000, 800), "make the top panel bigger", regions)
    joined = " ".join(m["content"] for m in msgs)
    assert "r1" in joined  # current layout passed back for modification


def test_parse_response_with_regions_and_questions():
    content = (
        "```json\n"
        '{"questions": ["What palette?"],'
        ' "layout": {"regions": [{"id": "p1", "kind": "image", "shape": "rect",'
        ' "bbox": [0,0,500,400]}, {"id": "t1", "kind": "text", "bbox": [0,420,500,80],'
        ' "text": "Title"}]}}'
        "\n```"
    )
    res = designer.parse_response(content, (1000, 800))
    assert res.questions == ["What palette?"]
    assert [r.id for r in res.regions] == ["p1", "t1"]
    assert res.regions[0].kind == "image"
    # out-of-nothing clamp safety: bbox stays within page
    x, y, w, h = res.regions[1].bbox
    assert x + w <= 1000 and y + h <= 800


def test_parse_response_questions_only():
    res = designer.parse_response('{"questions": ["how many pages?"]}', (1000, 800))
    assert res.questions == ["how many pages?"]
    assert res.regions is None


def test_parse_response_garbage_falls_back():
    res = designer.parse_response("the model rambled with no json", (1000, 800))
    assert res.regions is not None and len(res.regions) >= 1  # fallback layout
    assert res.regions[0].bbox[2] > 0


def test_run_design_uses_injected_completion():
    captured = {}

    def fake_completion(messages):
        captured["msgs"] = messages
        return '{"layout": {"regions": [{"id":"a","kind":"image","bbox":[0,0,100,100]}]}}'

    msgs = designer.build_messages("comic", (200, 200), "one panel")
    res = designer.run_design(msgs, (200, 200), fake_completion)
    assert captured["msgs"] == msgs
    assert [r.id for r in res.regions] == ["a"]


def test_parse_response_non_list_questions_does_not_split():
    res = designer.parse_response('{"questions": "why"}', (100, 100))
    assert "w" not in res.questions          # not iterated char-by-char
    assert res.regions is not None and len(res.regions) >= 1  # falls back to a layout
