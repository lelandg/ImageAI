from core.layout.balloons import caption_body, speech_body, overlay_to_segments
from core.layout.models import OverlayStyle
from core.layout.geometry import validate_segments, segments_bbox


INNER = (10.0, 20.0, 80.0, 40.0)  # x, y, w, h


def _contains(bbox, inner, tol=1e-6):
    bx, by, bw, bh = bbox
    ix, iy, iw, ih = inner
    return (bx <= ix + tol and by <= iy + tol
            and bx + bw >= ix + iw - tol and by + bh >= iy + ih - tol)


def test_caption_body_is_rectangle():
    segs = caption_body(INNER)
    assert validate_segments(segs) == []
    assert [s.type for s in segs] == ["move", "line", "line", "line", "close"]
    assert _contains(segments_bbox(segs), INNER)


def test_speech_body_valid_rounded_and_contains_inner():
    segs = speech_body(INNER, radius=12.0)
    assert validate_segments(segs) == []
    assert any(s.type == "cubic" for s in segs)        # rounded corners
    bbox = segments_bbox(segs)
    assert _contains(bbox, INNER)
    # rounded rect bbox equals inner bounds (corner controls stay inside)
    assert abs(bbox[2] - INNER[2]) < 1e-6 and abs(bbox[3] - INNER[3]) < 1e-6


def test_speech_radius_clamped_to_half_extent():
    # radius larger than half the smaller side must not invert the body
    segs = speech_body((0.0, 0.0, 20.0, 10.0), radius=999.0)
    assert validate_segments(segs) == []
    assert segments_bbox(segs)[2:] == (20.0, 10.0)


def test_overlay_to_segments_caption_and_speech_and_sfx():
    style = OverlayStyle(radius_px=10.0)
    assert overlay_to_segments("caption", INNER, None, style) == caption_body(INNER)
    speech = overlay_to_segments("speech", INNER, None, style)
    assert validate_segments(speech) == []
    assert any(s.type == "cubic" for s in speech)      # speech uses rounded body
    assert overlay_to_segments("sfx", INNER, None, style) == []  # sfx has no body


def test_overlay_to_segments_degenerate_logs_and_empty(caplog):
    import logging
    style = OverlayStyle()
    with caplog.at_level(logging.WARNING):
        assert overlay_to_segments("speech", (0.0, 0.0, 0.0, 30.0), None, style) == []
    assert any("degenerate" in r.message.lower() or "non-positive" in r.message.lower()
               for r in caplog.records)


def _all_points(segs):
    return [p for s in segs for p in s.pts]


def test_speech_tail_reaches_target_below():
    style = OverlayStyle(radius_px=10.0)
    target = (50.0, 120.0)  # well below INNER (which ends at y=60)
    segs = overlay_to_segments("speech", INNER, target, style)
    assert validate_segments(segs) == []
    # the tail tip is an exact vertex on the outline
    assert any(abs(px - target[0]) < 1e-6 and abs(py - target[1]) < 1e-6
               for px, py in _all_points(segs))
    # bbox now extends below the body to reach the target
    bbox = segments_bbox(segs)
    assert bbox[1] + bbox[3] >= target[1] - 1e-6


def test_speech_tail_target_above():
    style = OverlayStyle(radius_px=10.0)
    target = (50.0, -30.0)  # above the body
    segs = overlay_to_segments("speech", INNER, target, style)
    assert validate_segments(segs) == []
    assert any(abs(py - target[1]) < 1e-6 for _, py in _all_points(segs))
    assert segments_bbox(segs)[1] <= target[1] + 1e-6  # bbox reaches up to target


def test_speech_no_target_has_no_tail():
    style = OverlayStyle(radius_px=10.0)
    segs = overlay_to_segments("speech", INNER, None, style)
    # bbox stays within the inner bounds (no tail protrusion)
    bbox = segments_bbox(segs)
    assert bbox[1] >= INNER[1] - 1e-6
    assert bbox[1] + bbox[3] <= INNER[1] + INNER[3] + 1e-6


def test_speech_tail_single_closed_ring():
    style = OverlayStyle(radius_px=10.0)
    segs = overlay_to_segments("speech", INNER, (50.0, 120.0), style)
    assert sum(1 for s in segs if s.type == "move") == 1   # one subpath
    assert sum(1 for s in segs if s.type == "close") == 1
