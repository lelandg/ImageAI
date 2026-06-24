from core.layout.models import (
    Region, PageSpec, DocumentSpec, PageSize,
    TextBlock, ImageBlock, TextStyle, ImageStyle, migrate_legacy_blocks,
)


def test_region_defaults():
    r = Region(id="r1", kind="image")
    assert r.shape == "rect"
    assert r.bbox == (0, 0, 100, 100)
    assert r.points == []
    assert r.image_ref is None


def test_pagespec_holds_regions_and_pagesize():
    p = PageSpec(page_size_px=(100, 100), page_size=PageSize(8.5, 11, "in"),
                 regions=[Region(id="r1", kind="text", text="hi")])
    assert p.regions[0].text == "hi"
    assert p.page_size.to_pixels() == (2550, 3300)


def test_documentspec_content_kind_default():
    d = DocumentSpec(title="Doc")
    assert d.content_kind == "custom"
    assert d.schema_version == "2.0"


def test_migrate_legacy_blocks():
    blocks = [
        TextBlock(id="t1", rect=(0, 0, 50, 20), text="Hello", style=TextStyle(family=["Arial"])),
        ImageBlock(id="i1", rect=(0, 30, 80, 80), image_path="/tmp/x.png", style=ImageStyle()),
    ]
    regions = migrate_legacy_blocks(blocks)
    assert [r.kind for r in regions] == ["text", "image"]
    assert regions[0].text == "Hello"
    assert regions[0].bbox == (0, 0, 50, 20)
    assert regions[1].image_ref == "/tmp/x.png"
    assert regions[1].bbox == (0, 30, 80, 80)
