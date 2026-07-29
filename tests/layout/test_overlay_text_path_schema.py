from core.layout.models import Overlay, PathSegment, TextStyle
from core.layout.schema import overlay_to_dict, overlay_from_dict


def _tp():
    return [PathSegment(type="move", pts=[(100.0, 200.0)]),
            PathSegment(type="quad", pts=[(300.0, 120.0), (500.0, 200.0)])]


def test_round_trip_text_path():
    ov = Overlay(id="t", kind="caption", text="TITLE", anchor=(300.0, 200.0),
                 text_path=_tp())
    d = overlay_to_dict(ov)
    assert d["text_path"] == "M 100 200 Q 300 120 500 200"
    back = overlay_from_dict(d)
    assert back.text_path is not None
    assert back.text_path[0].type == "move"
    assert back.text_path[1].pts == [(300.0, 120.0), (500.0, 200.0)]


def test_none_text_path_key_omitted():
    ov = Overlay(id="t", kind="caption", text="x", anchor=(0.0, 0.0))
    d = overlay_to_dict(ov)
    assert "text_path" not in d
    assert overlay_from_dict(d).text_path is None


def test_malformed_text_path_dropped_with_warning(caplog):
    d = overlay_to_dict(Overlay(id="t", kind="sfx", text="x", anchor=(0.0, 0.0)))
    d["text_path"] = "M 0 0 L 10 10"  # line, not quad -> invalid contract
    with caplog.at_level("WARNING"):
        back = overlay_from_dict(d)
    assert back.text_path is None
    assert any("text_path" in r.message for r in caplog.records)


def test_garbage_text_path_dropped():
    d = overlay_to_dict(Overlay(id="t", kind="sfx", text="x", anchor=(0.0, 0.0)))
    d["text_path"] = "not a path"
    assert overlay_from_dict(d).text_path is None


def test_text_style_outline_round_trip():
    ts = TextStyle(family=["DejaVu Sans"], outline_px=3.0, outline_color="#442200")
    ov = Overlay(id="t", kind="caption", text="x", anchor=(0.0, 0.0), text_style=ts)
    back = overlay_from_dict(overlay_to_dict(ov))
    assert back.text_style.outline_px == 3.0
    assert back.text_style.outline_color == "#442200"


def test_old_file_without_outline_fields_loads():
    ov = Overlay(id="t", kind="caption", text="x", anchor=(0.0, 0.0),
                 text_style=TextStyle(family=["DejaVu Sans"]))
    d = overlay_to_dict(ov)
    del d["text_style"]["outline_px"]
    del d["text_style"]["outline_color"]
    back = overlay_from_dict(d)
    assert back.text_style.outline_px == 0.0
    assert back.text_style.outline_color == "#000000"
