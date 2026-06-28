"""Tests for _assemble_document (CLI layout DocumentSpec builder)."""
from cli.commands.layout import _assemble_document
from core.layout.designer import DesignerResult
from core.layout.models import Region


def test_assemble_builds_single_page_with_regions_and_style():
    regions = [Region(id="r1", kind="image", bbox=(0, 0, 100, 100))]
    result = DesignerResult(questions=[], regions=regions, overlays=[], raw="")
    doc = _assemble_document(result, "Letter", "portrait", 300, "comic", "MyBook")
    assert doc.title == "MyBook"
    assert doc.content_kind == "comic"
    assert len(doc.pages) == 1
    assert doc.pages[0].page_size_px == (2550, 3300)
    assert [r.id for r in doc.pages[0].regions] == ["r1"]
    # comic style provides a "dialogue" role
    assert "dialogue" in doc.style.font_roles


def test_assemble_uses_fallback_region_when_none():
    result = DesignerResult(questions=["need detail"], regions=None, overlays=[], raw="")
    doc = _assemble_document(result, "Letter", "portrait", 300, "custom", "X")
    assert len(doc.pages[0].regions) == 1  # full-page fallback frame
