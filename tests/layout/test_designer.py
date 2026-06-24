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
