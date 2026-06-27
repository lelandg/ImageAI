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


def test_build_messages_instructs_role_with_kind_roles():
    msgs = designer.build_messages("comic", (1000, 800), "a page")
    joined = " ".join(m["content"] for m in msgs)
    assert '"role"' in joined
    assert "dialogue" in joined  # a comic role name is offered to the model


def test_resolve_provider_ids_known_names():
    cases = {
        "OpenAI": ("openai", "openai"),
        "Anthropic": ("anthropic", "anthropic"),
        "Claude": ("anthropic", "anthropic"),   # defensive alias
        "Google": ("google", "gemini"),          # api-key id vs registry id differ
        "Ollama": ("ollama", "ollama"),
        "LM Studio": ("lmstudio", "lmstudio"),
    }
    for display, expected in cases.items():
        assert designer.resolve_provider_ids(display) == expected


def test_every_provider_display_name_resolves_to_a_registry_id_with_models():
    # Regression guard for the Anthropic/Claude path: every display name shown in
    # the designer's provider combo must resolve to a registry id that actually
    # has models, else the production LLM call would fail at runtime.
    from core.llm_models import (
        get_all_provider_ids, get_provider_display_name, get_provider_models)
    for pid in get_all_provider_ids():
        display = get_provider_display_name(pid)
        _, registry_id = designer.resolve_provider_ids(display)
        assert get_provider_models(registry_id), \
            f"{display!r} -> {registry_id!r} resolves to no models"


def test_designer_result_overlays_defaults_empty():
    res = designer.parse_response(
        '{"layout": {"regions": [{"id":"a","kind":"image","bbox":[0,0,100,100]}]}}',
        (200, 200))
    assert res.overlays == []


def test_parse_overlay_raw_pixel_anchor():
    content = ('{"layout": {"regions": [{"id":"p1","kind":"image","bbox":[0,0,200,200]}],'
               ' "overlays": [{"id":"o1","kind":"speech","text":"Hi",'
               ' "anchor":[50,40],"tail_target":[50,120]}]}}')
    res = designer.parse_response(content, (300, 300))
    assert len(res.overlays) == 1
    ov = res.overlays[0]
    assert ov.kind == "speech" and ov.text == "Hi"
    assert ov.anchor == (50.0, 40.0)
    assert ov.tail_target == (50.0, 120.0)


def test_parse_overlay_region_relative_anchor_resolves_to_pixels():
    content = ('{"layout": {"regions": [{"id":"p1","kind":"image","bbox":[100,100,200,100]}],'
               ' "overlays": [{"id":"o1","kind":"speech","text":"Yo","anchor_region":"p1",'
               ' "anchor_offset":[0.5,0.5],"tail_to_region":"p1"}]}}')
    res = designer.parse_response(content, (500, 500))
    ov = res.overlays[0]
    assert ov.anchor == (200.0, 150.0)        # 100 + 0.5*200, 100 + 0.5*100
    assert ov.tail_target == (200.0, 150.0)   # region center


def test_parse_overlay_unknown_region_dropped_but_others_kept():
    content = ('{"layout": {"regions": [{"id":"p1","kind":"image","bbox":[0,0,100,100]}],'
               ' "overlays": [{"id":"bad","kind":"speech","text":"x","anchor_region":"nope"},'
               ' {"id":"ok","kind":"sfx","text":"BOOM","anchor":[50,50]}]}}')
    res = designer.parse_response(content, (200, 200))
    assert [o.id for o in res.overlays] == ["ok"]


def test_parse_overlay_unknown_kind_skipped():
    content = ('{"layout": {"regions": [{"id":"p1","kind":"image","bbox":[0,0,100,100]}],'
               ' "overlays": [{"id":"o1","kind":"bubble","text":"x","anchor":[10,10]}]}}')
    res = designer.parse_response(content, (200, 200))
    assert res.overlays == []


def test_parse_overlay_bad_z_degrades_to_zero():
    content = ('{"layout": {"regions": [{"id":"p1","kind":"image","bbox":[0,0,100,100]}],'
               ' "overlays": [{"id":"o1","kind":"sfx","text":"x","anchor":[10,10],"z":"top"},'
               ' {"id":"o2","kind":"sfx","text":"y","anchor":[20,20],"z":null}]}}')
    res = designer.parse_response(content, (200, 200))
    assert [o.id for o in res.overlays] == ["o1", "o2"]
    assert all(o.z == 0 for o in res.overlays)


def test_parse_svg_path_region():
    content = ('{"layout": {"regions": [{"id":"p1","kind":"image","shape":"path",'
               ' "svg":"M10 10 L90 10 L90 90 Z","bleed":true}]}}')
    res = designer.parse_response(content, (200, 200))
    r = res.regions[0]
    assert r.shape == "path"
    assert [s.type for s in r.segments] == ["move", "line", "line", "close"]
    assert r.bleed is True


def test_parse_region_stroke_px_maps_to_image_style():
    content = ('{"layout": {"regions": [{"id":"p1","kind":"image","shape":"rect",'
               ' "bbox":[0,0,100,100],"stroke_px":6}]}}')
    res = designer.parse_response(content, (200, 200))
    assert res.regions[0].image_style is not None
    assert res.regions[0].image_style.stroke_px == 6


def test_parse_tiling_preset_expands_to_panels():
    content = '{"layout": {"tiling": {"preset":"grid","params":{"rows":2,"cols":2,"gutter_px":10}}}}'
    res = designer.parse_response(content, (400, 400))
    assert res.regions is not None and len(res.regions) == 4
    assert all(r.shape == "path" for r in res.regions)


def test_unknown_tiling_preset_degrades_keeps_explicit_regions():
    content = ('{"layout": {"tiling": {"preset":"spiral"},'
               ' "regions":[{"id":"a","kind":"image","bbox":[0,0,50,50]}]}}')
    res = designer.parse_response(content, (200, 200))
    assert [r.id for r in res.regions] == ["a"]  # unknown preset ignored; explicit region kept


def test_tiling_and_explicit_regions_coexist():
    content = ('{"layout": {"tiling": {"preset":"three_tiers"},'
               ' "regions":[{"id":"x","kind":"text","bbox":[0,0,40,20],"role":"caption"}]}}')
    res = designer.parse_response(content, (300, 300))
    ids = [r.id for r in res.regions]
    assert "x" in ids and len(ids) == 4  # 3 tiers + 1 explicit region


def test_build_messages_documents_new_capabilities():
    msgs = designer.build_messages("comic", (1000, 800), "a dynamic comic page")
    joined = " ".join(m["content"] for m in msgs)
    for token in ("svg", "tiling", "grid", "overlays", "speech", "anchor_region", "bleed"):
        assert token in joined, token
