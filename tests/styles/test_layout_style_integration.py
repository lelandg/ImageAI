"""Styled prompts in layout batch requests."""
from core.styles.models import Style


def test_build_requests_applies_style():
    from core.layout.batch_fill import build_requests
    from core.layout.models import DocumentSpec, PageSpec, Region
    region = Region(id="r1", kind="image", bbox=(0, 0, 100, 100), prompt="a fox")
    doc = DocumentSpec(title="T", content_kind="storybook",
                        pages=[PageSpec(page_size_px=(1000, 1000), regions=[region])])
    style = Style(id="w", name="W", prompt_text="washes")
    reqs_plain, _ = build_requests(doc, "m")
    reqs_styled, _ = build_requests(doc, "m", style=style)
    assert reqs_plain[0].prompt == "a fox"
    assert reqs_styled[0].prompt == "a fox. In this style: washes"
