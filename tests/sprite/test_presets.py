import pytest

from core.sprite import presets


def test_cell_presets_cover_the_design_list():
    sizes = [size for _, size in presets.CELL_PRESETS]
    for expected in [(8, 8), (16, 16), (16, 24), (24, 24), (16, 32), (32, 32), (48, 48),
                     (64, 64), (96, 96), (128, 128), (256, 256), (512, 512), (720, 720), (1024, 1024)]:
        assert expected in sizes
    assert presets.DEFAULT_CELL == (64, 64)


def test_canvas_and_fps_and_genre_presets():
    assert [s for _, s in presets.CANVAS_PRESETS] == [(320, 180), (384, 216), (400, 240), (480, 270), (640, 360)]
    assert [f for f, _ in presets.FPS_PRESETS] == [8, 12, 24, 30, 60]
    assert presets.DEFAULT_FPS == 12
    assert presets.GENRE_PRESETS == ("sidescroller", "top_down", "fighting")


def test_integer_scale_calculator():
    assert presets.integer_scale((320, 180), (1280, 720)) == 4
    assert presets.integer_scale((640, 360), (1920, 1080)) == 3
    assert presets.integer_scale((384, 216), (3840, 2160)) == 10
    assert presets.integer_scale((400, 240), (1280, 720)) == 3
    assert presets.integer_scale_table((320, 180)) == {"720p": 4, "1080p": 6, "4K": 12}


@pytest.mark.parametrize("text,expected", [
    ("64", (64, 64)), ("16x24", (16, 24)), ("16×24", (16, 24)), (" 720 X 720 ", (720, 720)),
])
def test_parse_cell_size(text, expected):
    assert presets.parse_cell_size(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "0", "16x0", "16x"])
def test_parse_cell_size_rejects_bad_input(text):
    with pytest.raises(ValueError):
        presets.parse_cell_size(text)
