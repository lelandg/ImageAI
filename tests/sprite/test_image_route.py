# tests/sprite/test_image_route.py
import json
import logging
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
    Image.fromarray(arr).save(buf, "PNG")
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


def test_generate_sheet_default_log_writes_each_full_content_message_once(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="core.sprite.generation.image_route")

    generate_sheet(_google(), _character(tmp_path), _action(), tmp_path / "s.png",
                   frames=3, plate_color="#00FF00")

    messages = [r.getMessage() for r in caplog.records]
    request_lines = [m for m in messages if m.startswith("[image route] sheet request:")]
    response_lines = [m for m in messages if m.startswith("[image route] sheet response:")]
    assert len(request_lines) == 1
    assert len(response_lines) == 1


def test_generate_sheet_provider_failure_emits_error_to_log(tmp_path, caplog):
    caplog.set_level(logging.ERROR, logger="core.sprite.generation.image_route")
    provider = _google()
    provider.edit_image.side_effect = RuntimeError("boom")
    logged = []
    with pytest.raises(SpriteGenerationError):
        generate_sheet(provider, _character(tmp_path), _action(), tmp_path / "s.png",
                       frames=3, plate_color="#00FF00", log=logged.append)
    assert any("failed" in l and "boom" in l for l in logged)
    assert any(r.levelname == "ERROR" and "failed" in r.getMessage() for r in caplog.records)


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


from core.sprite.generation.image_route import default_openai_edit_model, edit_chain, openai_edit_size


def _distinct_replies(n):
    return [png_bytes(w=16, h=16, squares=1, color=(0, 255, 0, 255)) if i % 2 == 0
            else png_bytes(w=16, h=16, squares=1, color=(0, 250, 5, 255)) for i in range(n)]


def test_edit_chain_google_chains_previous_frame(tmp_path):
    provider = _google()
    provider.start_edit_session.return_value = True
    replies = _distinct_replies(3)
    provider.edit_image.side_effect = [([], [r]) for r in replies]
    character = _character(tmp_path)
    out = edit_chain(provider, character, _action(), tmp_path / "chain", frames=3,
                     pose_instructions=["pose one", "pose two", "pose three"], plate_color="#00FF00")
    assert [p.name for p in out] == ["0001.png", "0002.png", "0003.png"]
    calls = provider.edit_image.call_args_list
    assert calls[0].args[0] == [character.read_bytes(), character.read_bytes()]
    assert calls[1].args[0] == [character.read_bytes(), replies[0]]
    assert calls[2].args[0] == [character.read_bytes(), replies[1]]
    assert all(c.kwargs["model"] == "default-google-image-model" for c in calls)
    assert "pose two" in calls[1].args[1] and "#00FF00" in calls[1].args[1]
    provider.start_edit_session.assert_called_once()
    provider.reset_edit_session.assert_called_once()
    sidecar = json.loads((tmp_path / "chain" / "0002.png.json").read_text(encoding="utf-8"))
    assert sidecar["step"] == 2 and sidecar["of"] == 3 and sidecar["route"] == "image_edit_chain"
    assert sidecar["reference_images"][1].endswith("0001.png")


def test_edit_chain_openai_passes_size_and_default_model(tmp_path):
    provider = _openai()
    provider.edit_image.side_effect = [([], [r]) for r in _distinct_replies(2)]
    out = edit_chain(provider, _character(tmp_path), _action(), tmp_path / "chain", frames=2,
                     pose_instructions=["a", "b"], plate_color="#00FF00")
    assert len(out) == 2
    kwargs = provider.edit_image.call_args_list[0].kwargs
    assert kwargs["model"] == default_openai_edit_model()
    assert kwargs["size"] == openai_edit_size(default_openai_edit_model(), (16, 16)) and kwargs["n"] == 1
    # OpenAIProvider has no start_edit_session/reset_edit_session at all (only GoogleProvider does),
    # so MagicMock(spec=OpenAIProvider) has no such attribute -- the google-only branch in edit_chain
    # structurally cannot touch it here; asserting non-attendance on a spec'd-out attribute would raise
    # AttributeError rather than assert anything.


def test_openai_edit_size_prefers_custom_when_legal_else_closest_preset():
    model = next(m for m, c in MODEL_CAPS.items() if c["supports_custom_size"])
    assert openai_edit_size(model, (1024, 1024)) == "1024x1024"
    assert openai_edit_size(model, (1000, 1010)) == "1008x1008"
    small = openai_edit_size(model, (200, 200))          # below the pixel floor -> preset
    assert small in MODEL_CAPS[model]["valid_sizes"]
    legacy = next(m for m, c in MODEL_CAPS.items() if not c["supports_custom_size"] and c["supports_mask"])
    assert openai_edit_size(legacy, (300, 100)) == max(
        (s for s in MODEL_CAPS[legacy]["valid_sizes"] if s != "auto"),
        key=lambda s: parse_size_string(s)[0] / parse_size_string(s)[1])


def test_edit_chain_matte_pairs(tmp_path, monkeypatch):
    provider = _google()
    provider.start_edit_session.return_value = True
    provider.edit_image.side_effect = [([], [r]) for r in _distinct_replies(4)]
    seen = []

    def fake_matte(on_white, on_black):
        seen.append((on_white.size, on_black.size))
        return Image.new("RGBA", on_white.size, (10, 20, 30, 128))

    monkeypatch.setattr("core.sprite.matting.difference_matte", fake_matte)
    out = edit_chain(provider, _character(tmp_path), _action(), tmp_path / "chain", frames=2,
                     pose_instructions=["a", "b"], plate_color="#00FF00", matte_pairs=True)
    assert len(out) == 2 and len(seen) == 2
    plates_dir = tmp_path / "chain" / "plates"
    assert (plates_dir / "0001.white.png").exists() and (plates_dir / "0001.black.png").exists()
    assert Image.open(out[0]).getchannel("A").getextrema() == (128, 128)
    prompts = [c.args[1].lower() for c in provider.edit_image.call_args_list]
    assert "#ffffff" in prompts[0] and "#000000" in prompts[1]
    sidecar = json.loads((tmp_path / "chain" / "0001.png.json").read_text(encoding="utf-8"))
    assert sidecar["matte_pairs"] is True and len(sidecar["plates"]) == 2
    # every artifact written by this route gets a .json sidecar (AGENTS.md hard rule) --
    # the white/black plates are no exception, and they carry the same provenance fields
    # (provider, model, prompt, plate colour, step index) as the merged frame's sidecar.
    white_sidecar_path = plates_dir / "0001.white.png.json"
    black_sidecar_path = plates_dir / "0001.black.png.json"
    assert white_sidecar_path.exists() and black_sidecar_path.exists()
    white_sidecar = json.loads(white_sidecar_path.read_text(encoding="utf-8"))
    black_sidecar = json.loads(black_sidecar_path.read_text(encoding="utf-8"))
    assert white_sidecar["plate_color"] == "#FFFFFF" and white_sidecar["step"] == 1 and white_sidecar["of"] == 2
    assert white_sidecar["provider"] == "google" and white_sidecar["model"] == "default-google-image-model"
    assert "#ffffff" in white_sidecar["prompt"].lower()
    assert black_sidecar["plate_color"] == "#000000" and "#000000" in black_sidecar["prompt"].lower()
    # in matte mode the chain actually feeds the previous WHITE plate bytes into the next
    # step, not the merged RGBA -- the second frame's sidecar must cite that true source.
    sidecar2 = json.loads((tmp_path / "chain" / "0002.png.json").read_text(encoding="utf-8"))
    assert sidecar2["reference_images"][1].endswith("0001.white.png")


def test_matte_plates_stay_out_of_the_pipeline_stage_directory(tmp_path, monkeypatch):
    """pipeline.list_frames globs *.png in the stage directory, so a plate left there
    would play as an animation frame. The plates live in a sibling "plates" directory
    and keep both their sidecars and their entry in the composed frame's sidecar."""
    from core.sprite import pipeline

    provider = _google()
    provider.start_edit_session.return_value = True
    provider.edit_image.side_effect = [([], [r]) for r in _distinct_replies(4)]
    monkeypatch.setattr("core.sprite.matting.difference_matte",
                        lambda on_white, on_black: Image.new("RGBA", on_white.size, (10, 20, 30, 128)))

    extract_dir = tmp_path / "stages" / "a1" / "extract"
    out = edit_chain(provider, _character(tmp_path), _action(), extract_dir, frames=2,
                     pose_instructions=["a", "b"], plate_color="#00FF00", matte_pairs=True)

    assert pipeline.list_frames(extract_dir) == [extract_dir / "0001.png", extract_dir / "0002.png"]
    assert pipeline.list_frames(extract_dir) == out
    for step in (1, 2):
        for color in ("white", "black"):
            plate = extract_dir / "plates" / f"{step:04d}.{color}.png"
            assert plate.exists() and plate.with_suffix(".png.json").exists()
        sidecar = json.loads((extract_dir / f"{step:04d}.png.json").read_text(encoding="utf-8"))
        assert [Path(p).parent.name for p in sidecar["plates"]] == ["plates", "plates"]
        assert all(Path(p).exists() for p in sidecar["plates"])


def test_edit_chain_cancel_during_the_white_plate_does_not_buy_the_black_one(tmp_path):
    """The token is polled before every paid call, so a Cancel that lands while the white
    plate is in flight stops the step instead of paying for the black plate too."""
    provider = _google()
    provider.start_edit_session.return_value = True
    token = CancelToken()

    def cancel_during_the_call(*args, **kwargs):
        token.cancel()
        return ([], [png_bytes(w=16, h=16, squares=1)])

    provider.edit_image.side_effect = cancel_during_the_call
    with pytest.raises(Cancelled):
        edit_chain(provider, _character(tmp_path), _action(), tmp_path / "chain", frames=2,
                   pose_instructions=["a", "b"], plate_color="#00FF00", matte_pairs=True, token=token)
    assert provider.edit_image.call_count == 1
    assert not (tmp_path / "chain" / "plates").exists()


def test_edit_chain_cancels_between_steps(tmp_path):
    provider = _google()
    provider.start_edit_session.return_value = True
    token = CancelToken()

    def first_then_cancel(*args, **kwargs):
        token.cancel()
        return ([], [png_bytes(w=16, h=16, squares=1)])

    provider.edit_image.side_effect = first_then_cancel
    with pytest.raises(Cancelled):
        edit_chain(provider, _character(tmp_path), _action(), tmp_path / "chain", frames=3,
                   pose_instructions=["a", "b", "c"], plate_color="#00FF00", token=token)
    assert sorted(p.name for p in (tmp_path / "chain").glob("*.png")) == ["0001.png"]
    provider.reset_edit_session.assert_called_once()


def test_edit_chain_length_mismatch(tmp_path):
    with pytest.raises(ValueError):
        edit_chain(_google(), _character(tmp_path), _action(), tmp_path / "chain", frames=3,
                   pose_instructions=["a"], plate_color="#00FF00")


def test_edit_chain_session_failure_is_logged_not_fatal(tmp_path):
    provider = _google()
    provider.start_edit_session.return_value = False
    provider.edit_image.side_effect = [([], [r]) for r in _distinct_replies(1)]
    logged = []
    out = edit_chain(provider, _character(tmp_path), _action(), tmp_path / "chain", frames=1,
                     pose_instructions=["a"], plate_color="#00FF00", log=logged.append)
    assert len(out) == 1 and any("session" in l for l in logged)
    provider.reset_edit_session.assert_not_called()


def test_edit_chain_session_failure_survives_raising_log_sink(tmp_path):
    """The session-start-failure warning goes through _common.emit, which swallows a
    raising sink (never breaks generation; the failure goes to DEBUG) -- so a console
    sink that raises on that specific message must not abort the chain."""
    provider = _google()
    provider.start_edit_session.return_value = False
    provider.edit_image.side_effect = [([], [r]) for r in _distinct_replies(1)]

    session_message = "[image route] edit session did not start; continuing with single-shot edits"

    def flaky_log(message):
        if message == session_message:
            raise RuntimeError("console sink exploded")

    out = edit_chain(provider, _character(tmp_path), _action(), tmp_path / "chain", frames=1,
                     pose_instructions=["a"], plate_color="#00FF00", log=flaky_log)
    assert len(out) == 1
    provider.reset_edit_session.assert_not_called()



def test_original_background_sheet_keeps_source_background_instruction(tmp_path):
    provider = _google()
    out = generate_sheet(provider, _character(tmp_path), _action(), tmp_path / "sheet.png",
                         frames=3, plate_color="#00FF00", background_mode="original")
    prompt = provider.edit_image.call_args.args[1]
    assert "Preserve the original reference image background" in prompt
    assert "#00FF00" not in prompt and "chroma" not in prompt
    assert "seamless loop" in prompt
    meta = json.loads(out.with_suffix(".png.json").read_text())
    assert meta["background_mode"] == "original"


def test_original_background_edit_chain_skips_matte_pairs(tmp_path):
    provider = _google()
    paths = image_route.edit_chain(provider, _character(tmp_path), _action(), tmp_path / "frames",
                                  frames=2, pose_instructions=["raise hand", "lower hand"],
                                  plate_color="#00FF00", matte_pairs=True, background_mode="original")
    assert len(paths) == provider.edit_image.call_count == 2
    for call in provider.edit_image.call_args_list:
        assert "Preserve the original reference image background" in call.args[1]
        assert "chroma" not in call.args[1]
    meta = json.loads(paths[0].with_suffix(".png.json").read_text())
    assert meta["background_mode"] == "original" and meta["matte_pairs"] is False
    assert meta["plates"] == []



def test_original_background_sheet_slicing_ignores_chroma_grid(tmp_path, monkeypatch):
    sheet = tmp_path / "scenery.png"
    sheet.write_bytes(png_bytes())
    monkeypatch.setattr(image_route, "guess_grid", MagicMock(side_effect=AssertionError("chroma grid used")))
    paths = slice_generated_sheet(sheet, tmp_path / "frames", 3, "#00FF00", background_mode="original")
    assert len(paths) == 3
    with Image.open(sheet) as source:
        for index, path in enumerate(paths):
            with Image.open(path) as cell:
                assert cell.size == (16, 16)
                assert cell.tobytes() == source.crop((index * 16, 0, (index + 1) * 16, 16)).tobytes()
