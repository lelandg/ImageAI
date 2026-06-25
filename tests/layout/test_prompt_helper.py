"""Phase 5a — per-region AI prompt help (pure core, injected completion)."""
from core.layout.models import DocumentSpec, PageSpec, Region
from core.layout import prompt_helper, styles


def _doc(regions, content_kind="children", title="My Story"):
    page = PageSpec(page_size_px=(1000, 1500), regions=regions)
    return DocumentSpec(title=title, pages=[page], content_kind=content_kind,
                        style=styles.default_style_for(content_kind))


def test_build_prompt_messages_includes_project_and_region_context():
    img = Region(id="img1", kind="image", name="hero illustration", bbox=(0, 0, 1000, 1000))
    txt = Region(id="t1", kind="text", bbox=(0, 1000, 1000, 200), text="Once upon a time")
    msgs = prompt_helper.build_prompt_messages(_doc([img, txt]), img, hint="cozy forest")
    assert msgs[0]["role"] == "system"
    joined = " ".join(m["content"] for m in msgs)
    assert "children" in joined           # content_kind seeds the style
    assert "My Story" in joined           # document title
    assert "hero illustration" in joined  # region name
    assert "Once upon a time" in joined   # sibling text gives scene context
    assert "cozy forest" in joined        # user hint


def test_build_prompt_messages_aspect_is_context_not_a_pixel_token():
    # Repo rule: never embed pixel/ratio tokens an image model would render
    # literally. A ratio may appear as context, but not "(1000x1000)".
    img = Region(id="img1", kind="image", bbox=(0, 0, 1000, 1000))
    joined = " ".join(m["content"] for m in prompt_helper.build_prompt_messages(_doc([img]), img))
    assert "1000x1000" not in joined
    assert "(1000" not in joined


def test_build_prompt_messages_asks_for_a_single_prompt():
    img = Region(id="img1", kind="image", bbox=(0, 0, 500, 500))
    joined = " ".join(m["content"] for m in prompt_helper.build_prompt_messages(_doc([img]), img))
    assert "prompt" in joined.lower()


def test_build_prompt_messages_tolerates_region_not_in_document():
    # A detached region (no page contains it) must not raise — just no neighbors.
    stray = Region(id="x", kind="image", bbox=(0, 0, 100, 100))
    msgs = prompt_helper.build_prompt_messages(_doc([]), stray)
    assert msgs and msgs[-1]["role"] == "user"


def test_parse_prompt_response_json():
    assert prompt_helper.parse_prompt_response('{"prompt": "a red fox"}') == "a red fox"


def test_parse_prompt_response_fenced_json():
    out = prompt_helper.parse_prompt_response('```json\n{"prompt": "a blue whale"}\n```')
    assert out == "a blue whale"


def test_parse_prompt_response_plain_text():
    assert prompt_helper.parse_prompt_response("a lone lighthouse at dusk") == "a lone lighthouse at dusk"


def test_parse_prompt_response_fenced_plain_text():
    assert prompt_helper.parse_prompt_response("```\na quiet harbor\n```") == "a quiet harbor"


def test_parse_prompt_response_empty():
    assert prompt_helper.parse_prompt_response("") == ""
    assert prompt_helper.parse_prompt_response("   ") == ""


def test_run_prompt_help_uses_injected_completion():
    captured = {}

    def fake(messages):
        captured["msgs"] = messages
        return '{"prompt": "a knight in a misty field"}'

    img = Region(id="img1", kind="image", bbox=(0, 0, 500, 500))
    msgs = prompt_helper.build_prompt_messages(_doc([img]), img)
    out = prompt_helper.run_prompt_help(msgs, fake)
    assert out == "a knight in a misty field"
    assert captured["msgs"] == msgs
