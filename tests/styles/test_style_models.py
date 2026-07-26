"""Tests for core/styles/models.py — Style record dataclasses."""
from core.styles.models import DESCRIPTOR_KEYS, Style, StyleDescriptor


def test_descriptor_keys():
    assert DESCRIPTOR_KEYS == (
        "summary", "medium", "palette", "lighting", "composition",
        "texture", "line_work", "mood", "negative",
    )


def test_descriptor_round_trip():
    d = StyleDescriptor(summary="Watercolor wash", palette="warm pastels")
    data = d.to_dict()
    assert set(data.keys()) == set(DESCRIPTOR_KEYS)
    assert data["summary"] == "Watercolor wash"
    assert StyleDescriptor.from_dict(data) == d


def test_descriptor_from_dict_tolerates_missing_and_extra():
    d = StyleDescriptor.from_dict({"summary": "x", "bogus": "y", "mood": None})
    assert d.summary == "x"
    assert d.mood == ""


def test_style_round_trip():
    s = Style(id="water", name="Water", prompt_text="soft washes",
              reference_images=["refs/0001.jpg"], exemplars=["refs/0001.jpg"],
              source={"provider": "openai", "image_count": 2})
    data = s.to_dict()
    s2 = Style.from_dict(data)
    assert s2 == s
    assert s2.placement == "suffix"
    assert s2.descriptor == StyleDescriptor()


def test_style_from_dict_defaults():
    s = Style.from_dict({"id": "a", "name": "A"})
    assert s.placement == "suffix"
    assert s.reference_images == [] and s.exemplars == []
    assert s.version == 1 and s.is_builtin is False
