from core.layout.models import PathSegment
from core.layout.svg_path import svg_to_segments, segments_to_svg


def test_parse_basic_absolute_commands():
    segs = svg_to_segments("M10 10 L90 10 L90 90 Z")
    assert [s.type for s in segs] == ["move", "line", "line", "close"]
    assert segs[0].pts == [(10.0, 10.0)]
    assert segs[2].pts == [(90.0, 90.0)]


def test_h_and_v_commands():
    segs = svg_to_segments("M10 10 H50 V40")
    assert segs[1].type == "line" and segs[1].pts == [(50.0, 10.0)]
    assert segs[2].type == "line" and segs[2].pts == [(50.0, 40.0)]


def test_relative_commands_accumulate():
    segs = svg_to_segments("m10 10 l20 0 l0 20 z")
    assert segs[0].pts == [(10.0, 10.0)]
    assert segs[1].pts == [(30.0, 10.0)]
    assert segs[2].pts == [(30.0, 30.0)]
    assert segs[3].type == "close"


def test_implicit_line_after_moveto():
    # extra coordinate pairs after M are implicit L
    segs = svg_to_segments("M0 0 10 0 10 10")
    assert [s.type for s in segs] == ["move", "line", "line"]
    assert segs[2].pts == [(10.0, 10.0)]


def test_cubic_command():
    segs = svg_to_segments("M0 0 C1 2 3 4 5 6")
    assert segs[1].type == "cubic"
    assert segs[1].pts == [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]


def test_quad_command():
    segs = svg_to_segments("M0 0 Q1 2 3 4")
    assert segs[1].type == "quad"
    assert segs[1].pts == [(1.0, 2.0), (3.0, 4.0)]


def test_round_trip_segments_to_svg_to_segments():
    segs = [
        PathSegment(type="move", pts=[(10.0, 10.0)]),
        PathSegment(type="line", pts=[(90.0, 10.0)]),
        PathSegment(type="cubic", pts=[(95.0, 10.0), (95.0, 15.0), (95.0, 20.0)]),
        PathSegment(type="quad", pts=[(50.0, 80.0), (10.0, 20.0)]),
        PathSegment(type="close", pts=[]),
    ]
    assert svg_to_segments(segments_to_svg(segs)) == segs


def test_malformed_input_degrades_without_raising():
    # 'C' needs 6 args; only 3 given -> keep the valid move, stop, no crash
    segs = svg_to_segments("M0 0 C1 2 3")
    assert segs == [PathSegment(type="move", pts=[(0.0, 0.0)])]


def test_number_before_command_returns_empty():
    assert svg_to_segments("10 10 L20 20") == []


def test_empty_string_returns_empty():
    assert svg_to_segments("") == []
