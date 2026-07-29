from core.layout.designer import _build_overlay


def _base(**kw):
    d = {"id": "o1", "kind": "caption", "text": "TITLE", "anchor": [100, 100]}
    d.update(kw)
    return d


def test_valid_text_path_parsed():
    ov = _build_overlay(_base(text_path="M 50 100 Q 100 60 150 100"),
                        {}, (400, 400), 0)
    assert ov is not None and ov.text_path is not None
    assert ov.text_path[1].pts == [(100.0, 60.0), (150.0, 100.0)]


def test_invalid_text_path_dropped_overlay_kept():
    ov = _build_overlay(_base(text_path="M 0 0 L 10 10"), {}, (400, 400), 0)
    assert ov is not None and ov.text_path is None


def test_text_path_ignored_for_speech():
    d = _base(kind="speech", text_path="M 50 100 Q 100 60 150 100",
              tail_target=[10, 10])
    ov = _build_overlay(d, {}, (400, 400), 0)
    assert ov is not None and ov.text_path is None


def test_rotation_passthrough():
    ov = _build_overlay(_base(rotation=15), {}, (400, 400), 0)
    assert ov is not None and abs(ov.rotation - 15.0) < 1e-9


def test_bad_rotation_defaults_zero():
    ov = _build_overlay(_base(rotation="sideways"), {}, (400, 400), 0)
    assert ov is not None and ov.rotation == 0.0
