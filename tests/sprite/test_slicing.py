import numpy as np
import pytest
from PIL import Image

from core.sprite.slicing import GridGuess, guess_grid, import_png_sequence, slice_sheet
from tests.sprite.synth import draw_frame


def _sheet(columns=4, rows=2, cell=32, alpha=True, margin=0, spacing=0):
    w = 2 * margin + columns * cell + (columns - 1) * spacing
    h = 2 * margin + rows * cell + (rows - 1) * spacing
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    if not alpha:
        arr[..., 1] = 255
        arr[..., 3] = 255
    for r in range(rows):
        for c in range(columns):
            x = margin + c * (cell + spacing) + 8
            y = margin + r * (cell + spacing) + 8
            arr[y:y + 16, x:x + 16] = (200, 40, 40, 255)
    return Image.fromarray(arr)


def test_guess_grid_on_a_transparent_sheet():
    guess = guess_grid(_sheet())
    assert isinstance(guess, GridGuess)
    assert (guess.columns, guess.rows, guess.cell) == (4, 2, (32, 32))
    assert guess.confidence >= 0.6


def test_guess_grid_on_a_chroma_sheet_with_and_without_key_color():
    sheet = _sheet(alpha=False)
    assert guess_grid(sheet, key_color="#00FF00").columns == 4
    assert guess_grid(sheet).rows == 2


def test_guess_grid_low_confidence_for_a_single_sprite():
    guess = guess_grid(_sheet(columns=1, rows=1))
    assert (guess.columns, guess.rows) == (1, 1)
    assert guess.confidence < 0.6


def test_slice_sheet_writes_row_major_frames(tmp_path):
    sheet = tmp_path / "sheet.png"
    _sheet(columns=3, rows=2, cell=32).save(sheet)
    frames = slice_sheet(sheet, tmp_path / "out", columns=3, rows=2)
    assert [p.name for p in frames] == [f"{i:04d}.png" for i in range(1, 7)]
    with Image.open(frames[0]) as im:
        assert im.size == (32, 32) and im.mode == "RGBA"
        assert im.getpixel((8, 8)) == (200, 40, 40, 255)


def test_slice_sheet_with_margin_and_spacing(tmp_path):
    sheet = tmp_path / "sheet.png"
    _sheet(columns=2, rows=2, cell=32, margin=4, spacing=2).save(sheet)
    frames = slice_sheet(sheet, tmp_path / "out", columns=2, rows=2, margin=4, spacing=2)
    assert len(frames) == 4
    with Image.open(frames[3]) as im:
        assert im.size == (32, 32)
        assert im.getpixel((8, 8)) == (200, 40, 40, 255)


def test_slice_sheet_rejects_cells_outside_the_sheet(tmp_path):
    sheet = tmp_path / "sheet.png"
    _sheet(columns=2, rows=1, cell=32).save(sheet)
    with pytest.raises(ValueError):
        slice_sheet(sheet, tmp_path / "out", columns=3, rows=1, cell=(32, 32))
    with pytest.raises(ValueError):
        slice_sheet(sheet, tmp_path / "out", columns=0, rows=1)


def test_import_png_sequence_copies_in_order_and_renumbers(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    paths = []
    for name, index in (("b.png", 1), ("a.jpg", 0)):
        path = src / name
        draw_frame(index, alpha=name.endswith(".png")).convert("RGBA" if name.endswith(".png") else "RGB").save(path)
        paths.append(path)
    out = import_png_sequence(paths, tmp_path / "out")
    assert [p.name for p in out] == ["0001.png", "0002.png"]
    with Image.open(out[1]) as im:
        assert im.mode == "RGBA"
