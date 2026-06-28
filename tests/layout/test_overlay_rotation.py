from core.layout.models import Overlay
from core.layout.schema import overlay_to_dict, overlay_from_dict


def _ov(**kw):
    base = dict(id="o1", kind="sfx", text="BOOM", anchor=(100.0, 100.0))
    base.update(kw)
    return Overlay(**base)


def test_rotation_defaults_to_zero():
    assert _ov().rotation == 0.0


def test_rotation_round_trips():
    d = overlay_to_dict(_ov(rotation=37.5))
    assert d["rotation"] == 37.5
    assert overlay_from_dict(d).rotation == 37.5


def test_rotation_missing_key_loads_zero():
    d = overlay_to_dict(_ov())
    del d["rotation"]
    assert overlay_from_dict(d).rotation == 0.0


def test_rotation_non_numeric_degrades_to_zero():
    d = overlay_to_dict(_ov())
    d["rotation"] = None
    assert overlay_from_dict(d).rotation == 0.0
