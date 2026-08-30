# tests/sprite/test_image_route.py
import json
import re
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image

from core.image_size import parse_size_string
from core.sprite.generation import image_route
from core.sprite.generation.errors import ProviderError, SpriteGenerationError
from core.sprite.generation.image_route import (
    generate_sheet, openai_sheet_size, sheet_prompt, slice_generated_sheet,
)
from core.sprite.generation.prompts import FORBIDDEN_WORDS
from core.sprite.pipeline import CancelToken, Cancelled
from core.sprite.project import ActionCard
from core.sprite.slicing import GridGuess
from providers.google import GoogleProvider
from providers.openai import MODEL_CAPS, OpenAIProvider


def png_bytes(w=48, h=16, color=(0, 255, 0, 255), squares=3) -> bytes:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[...] = color
    cell = w // squares
    for i in range(squares):
        x0 = i * cell + 3
        arr[4:12, x0:x0 + 8] = (200, 40 + 40 * i, 60, 255)
    buf = BytesIO()
    Image.fromarray(arr, "RGBA").save(buf, "PNG")
    return buf.getvalue()


def _action() -> ActionCard:
    return ActionCard(id="a1", name="walk", prompt="walks briskly to the right", duration_s=4,
                      loop=True, target_frames=3, fps=12)


def _character(tmp_path: Path) -> Path:
    p = tmp_path / "character.png"
    p.write_bytes(png_bytes(w=16, h=16, squares=1))
    return p


def _google(reply=None):
    provider = MagicMock(spec=GoogleProvider)
    provider.get_default_model.return_value = "default-google-image-model"
    provider.edit_image.return_value = ([], [reply or png_bytes()])
    return provider


def _openai(reply=None):
    provider = MagicMock(spec=OpenAIProvider)
    provider.get_default_model.return_value = next(m for m, c in MODEL_CAPS.items() if c["supports_custom_size"])
    provider.edit_image.return_value = ([], [reply or png_bytes()])
    return provider


def test_sheet_prompt_is_clean():
    text = sheet_prompt(_action(), 6, "#00FF00")
    lowered = text.lower()
    assert "horizontal" in lowered and "6" in text and "#00FF00" in text
    assert not re.search(r"\d+\s*[x×]\s*\d+", text), "no pixel dimensions"
    assert not re.search(r"\b\d+:\d+\b", text), "no aspect ratio"
    for word in FORBIDDEN_WORDS:
        assert word not in lowered
    assert "seamless loop" in lowered


def test_generate_sheet_google_uses_aspect_kwarg_not_prompt(tmp_path):
    provider = _google()
    out = generate_sheet(provider, _character(tmp_path), _action(), tmp_path / "sheet.png",
                         frames=3, plate_color="#00FF00")
    assert out.exists()
    args, kwargs = provider.edit_image.call_args
    assert kwargs["aspect_ratio"] == image_route.SHEET_ASPECT_GEMINI
    assert kwargs["model"] == "default-google-image-model"
    assert image_route.SHEET_ASPECT_GEMINI not in args[1]
    sidecar = json.loads((tmp_path / "sheet.png.json").read_text(encoding="utf-8"))
    assert sidecar["route"] == "image_sheet" and sidecar["frames"] == 3 and sidecar["provider"] == "google"
    assert Image.open(out).mode == "RGBA"


def test_generate_sheet_openai_uses_custom_3to1_size(tmp_path):
    provider = _openai()
    model = provider.get_default_model()
    generate_sheet(provider, _character(tmp_path), _action(), tmp_path / "sheet.png",
                   frames=4, plate_color="#00FF00", model=model)
    args, kwargs = provider.edit_image.call_args
    w, h = parse_size_string(kwargs["size"])
    assert w / h == 3.0 and w % 16 == 0 and h % 16 == 0
    assert kwargs["model"] == model and kwargs["n"] == 1
    assert isinstance(args[0], list) and Path(args[0][0]).name == "character.png"


def test_openai_sheet_size_without_custom_size_picks_widest_preset():
    model = next(m for m, c in MODEL_CAPS.items() if not c["supports_custom_size"] and c["supports_multi_reference"])
    size = openai_sheet_size(model)
    widths = {parse_size_string(s) for s in MODEL_CAPS[model]["valid_sizes"] if s != "auto"}
    assert parse_size_string(size) == max(widths, key=lambda wh: wh[0] / wh[1])


def test_generate_sheet_no_image_raises_provider_error(tmp_path):
    provider = _google()
    provider.edit_image.return_value = (["I cannot draw that."], [])
    with pytest.raises(ProviderError) as info:
        generate_sheet(provider, _character(tmp_path), _action(), tmp_path / "s.png", frames=3, plate_color="#00FF00")
    assert "cannot draw" in str(info.value)


def test_generate_sheet_wraps_provider_exception(tmp_path):
    provider = _google()
    provider.edit_image.side_effect = RuntimeError("Google image editing failed: 429 RESOURCE_EXHAUSTED")
    with pytest.raises(SpriteGenerationError):
        generate_sheet(provider, _character(tmp_path), _action(), tmp_path / "s.png", frames=3, plate_color="#00FF00")


def test_generate_sheet_logs_request_and_response(tmp_path):
    lines = []
    generate_sheet(_google(), _character(tmp_path), _action(), tmp_path / "s.png",
                   frames=3, plate_color="#00FF00", log=lines.append)
    assert any("request" in l and "prompt:" in l for l in lines)
    assert any("response" in l and "1 image" in l for l in lines)


def test_generate_sheet_honors_cancel_token(tmp_path):
    token = CancelToken()
    token.cancel()
    provider = _google()
    with pytest.raises(Cancelled):
        generate_sheet(provider, _character(tmp_path), _action(), tmp_path / "s.png",
                       frames=3, plate_color="#00FF00", token=token)
    provider.edit_image.assert_not_called()


def test_generate_sheet_rejects_fewer_than_two_frames(tmp_path):
    with pytest.raises(ValueError):
        generate_sheet(_google(), _character(tmp_path), _action(), tmp_path / "s.png", frames=1, plate_color="#00FF00")


def test_slice_uses_guess_when_confident(tmp_path, monkeypatch):
    sheet = tmp_path / "sheet.png"
    sheet.write_bytes(png_bytes(w=48, h=16, squares=3))
    monkeypatch.setattr(image_route, "guess_grid", lambda img, key_color=None: GridGuess(columns=3, rows=1, cell=(16, 16), confidence=0.95))
    frames = slice_generated_sheet(sheet, tmp_path / "frames", 3, "#00FF00")
    assert [p.name for p in frames] == ["0001.png", "0002.png", "0003.png"]
    assert all(Image.open(p).size == (16, 16) for p in frames)
    assert (tmp_path / "frames" / "0001.png.json").exists()


def test_slice_falls_back_to_one_row_when_guess_disagrees(tmp_path, monkeypatch):
    sheet = tmp_path / "sheet.png"
    sheet.write_bytes(png_bytes(w=48, h=16, squares=3))
    monkeypatch.setattr(image_route, "guess_grid", lambda img, key_color=None: GridGuess(columns=2, rows=2, cell=(24, 8), confidence=0.9))
    logged = []
    frames = slice_generated_sheet(sheet, tmp_path / "frames", 3, "#00FF00", log=logged.append)
    assert len(frames) == 3 and Image.open(frames[0]).size == (16, 16)
    assert any("rejected" in l for l in logged)
