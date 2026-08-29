"""Tests for core/sprite/generation/prompts.py (chroma-prompt-injection)."""
import pytest

from core.sprite.generation.prompts import (
    CHROMA_SUFFIX,
    FORBIDDEN_WORDS,
    LOOP_SUFFIX,
    color_name,
    inject_chroma,
    strip_render_terms,
)


@pytest.mark.parametrize("hex_color,name", [
    ("#00FF00", "green"), ("#00B140", "green"), ("#0000FF", "blue"),
    ("#FF00FF", "magenta"), ("#FF0000", "red"), ("#FFFF00", "yellow"),
    ("#00FFFF", "cyan"), ("#FFFFFF", "white"), ("#000000", "black"),
    ("#808080", "gray"), ("00ff00", "green"),
])
def test_color_name(hex_color, name):
    assert color_name(hex_color) == name


def test_color_name_rejects_bad_hex():
    with pytest.raises(ValueError):
        color_name("#12")


def test_inject_appends_chroma_suffix_with_name_and_hex():
    out = inject_chroma("the hero walks", "#00ff00", loop=False)
    assert out.startswith("the hero walks, ")
    assert CHROMA_SUFFIX.format(color_name="green", hex="#00FF00") in out
    assert LOOP_SUFFIX not in out


def test_inject_appends_loop_suffix_when_looping():
    out = inject_chroma("the hero walks", "#00FF00", loop=True)
    assert out.endswith(", " + LOOP_SUFFIX)


def test_inject_strips_forbidden_words_case_insensitive():
    out = inject_chroma("Transparent background, ALPHA channel, checkerboard behind",
                        "#00FF00", loop=False)
    lowered = out.lower().replace(LOOP_SUFFIX, "")
    for word in FORBIDDEN_WORDS:
        assert word not in lowered.split(CHROMA_SUFFIX[:10].lower())[0]


def test_inject_strips_aspect_ratios_and_pixel_sizes():
    out = inject_chroma("side view 16:9 at 1920x1080, 512 px tall, 4:3 crop",
                        "#00FF00", loop=False)
    body = out.split(", solid chroma")[0]
    assert "16:9" not in body and "4:3" not in body
    assert "1920x1080" not in body and "512 px" not in body.lower()


def test_strip_render_terms_collapses_whitespace_and_punctuation():
    assert strip_render_terms("a  hero ,  transparent , walking ,") == "a hero, walking"


def test_inject_never_emits_aspect_or_pixels():
    out = inject_chroma("jump", "#0000FF", loop=True)
    assert ":" not in out.replace("chroma blue background", "")
    assert "px" not in out.lower()
