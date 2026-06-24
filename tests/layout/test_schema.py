from core.layout.models import Region, PageSpec, DocumentSpec, PageSize
from core.layout import schema


def _doc():
    page = PageSpec(page_size_px=(1000, 800), page_size=PageSize(1000, 800, "px"),
                    regions=[
                        Region(id="r1", kind="text", bbox=(10, 10, 200, 50), text="Title"),
                        Region(id="r2", kind="image", shape="polygon",
                               points=[(0, 0), (300, 0), (150, 300)]),
                    ])
    return DocumentSpec(title="T", content_kind="comic", pages=[page])


def test_document_roundtrip():
    doc = _doc()
    again = schema.document_from_dict(schema.document_to_dict(doc))
    assert again.title == "T"
    assert again.content_kind == "comic"
    assert again.pages[0].regions[0].text == "Title"
    assert again.pages[0].regions[1].shape == "polygon"
    assert again.pages[0].regions[1].points == [(0, 0), (300, 0), (150, 300)]


def test_document_from_dict_migrates_legacy_blocks():
    legacy = {
        "title": "Old", "pages": [{
            "page_size_px": [500, 500],
            "blocks": [
                {"type": "text", "id": "t1", "rect": [0, 0, 100, 30], "text": "Hi"},
                {"type": "image", "id": "i1", "rect": [0, 40, 100, 100], "image_path": "/a.png"},
            ],
        }],
    }
    doc = schema.document_from_dict(legacy)
    kinds = [r.kind for r in doc.pages[0].regions]
    assert kinds == ["text", "image"]
    assert doc.pages[0].regions[1].image_ref == "/a.png"


def test_normalize_region_clamps_and_sets_polygon_bbox():
    r = Region(id="r", kind="image", bbox=(900, 700, 500, 500))  # overflows 1000x800
    n = schema.normalize_region(r, (1000, 800))
    x, y, w, h = n.bbox
    assert x + w <= 1000 and y + h <= 800

    poly = Region(id="p", kind="image", shape="polygon", points=[(10, 20), (110, 20), (60, 120)])
    np = schema.normalize_region(poly, (1000, 800))
    assert np.bbox == (10, 20, 100, 100)  # bbox computed from points


def test_validate_document_flags_empty_pages():
    doc = DocumentSpec(title="x", pages=[])
    issues = schema.validate_document(doc)
    assert any("page" in i.lower() for i in issues)


def test_normalize_region_origin_at_or_beyond_boundary():
    r = Region(id="r", kind="image", bbox=(1100, 900, 200, 200))
    n = schema.normalize_region(r, (1000, 800))
    x, y, w, h = n.bbox
    assert x + w <= 1000 and y + h <= 800
    assert w >= 1 and h >= 1
    # input Region must not be mutated
    assert r.bbox == (1100, 900, 200, 200)
