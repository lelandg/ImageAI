"""Tests for Overlay / OverlayStyle serialization in core.layout.schema."""
from core.layout.models import Overlay, OverlayStyle, TextStyle
from core.layout.schema import overlay_to_dict, overlay_from_dict


def _roundtrip(ov):
    return overlay_from_dict(overlay_to_dict(ov))


def test_speech_overlay_roundtrip_with_tail_and_style():
    ov = Overlay(id="o1", kind="speech", text="Hi!", anchor=(50.0, 40.0),
                 anchor_mode="center", tail_target=(50.0, 90.0), z=2, role="dialogue",
                 style=OverlayStyle(fill="#FFEE00", stroke_px=3.0, padding_px=12.0,
                                    radius_px=20.0, max_width_px=180.0))
    r = _roundtrip(ov)
    assert r.id == "o1" and r.kind == "speech" and r.text == "Hi!"
    assert r.anchor == (50.0, 40.0) and r.tail_target == (50.0, 90.0)
    assert r.z == 2 and r.role == "dialogue"
    assert r.style.fill == "#FFEE00" and r.style.stroke_px == 3.0
    assert r.style.padding_px == 12.0 and r.style.radius_px == 20.0
    assert r.style.max_width_px == 180.0


def test_overlay_roundtrip_each_kind():
    for kind in ("speech", "thought", "caption", "sfx"):
        ov = Overlay(id=kind, kind=kind, text="x", anchor=(1.0, 2.0))
        assert _roundtrip(ov).kind == kind


def test_overlay_roundtrip_with_text_style():
    ov = Overlay(id="t", kind="caption", text="cap", anchor=(0.0, 0.0),
                 text_style=TextStyle(family=["Arial"], size_px=30, color="#112233"))
    r = _roundtrip(ov)
    assert r.text_style is not None
    assert r.text_style.size_px == 30 and r.text_style.color == "#112233"


def test_overlay_from_dict_defaults_when_missing_optionals():
    r = overlay_from_dict({"id": "m", "kind": "sfx", "text": "BOOM", "anchor": [5.0, 6.0]})
    assert r.anchor == (5.0, 6.0)
    assert r.tail_target is None and r.role == ""
    assert isinstance(r.style, OverlayStyle) and r.style.fill == "#FFFFFF"


def test_pagespec_without_overlays_loads_empty():
    # an older page dict (no "overlays" key) must deserialize to overlays == []
    from core.layout.schema import page_from_dict
    page = page_from_dict({"page_size_px": [100, 100], "regions": []})
    assert page.overlays == []
