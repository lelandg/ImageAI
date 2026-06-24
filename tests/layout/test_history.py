from core.layout.models import Snapshot, DocumentSpec, PageSpec, Region
from core.layout import schema


def test_snapshot_roundtrip_via_schema():
    snap = Snapshot(id="s1", parent_id=None, timestamp="2026-06-24 12:00",
                    prompt="a 9-panel comic", document={"title": "X", "pages": []})
    d = schema.snapshot_to_dict(snap)
    again = schema.snapshot_from_dict(d)
    assert again.id == "s1"
    assert again.prompt == "a 9-panel comic"
    assert again.document == {"title": "X", "pages": []}


def test_document_history_roundtrip():
    doc = DocumentSpec(title="Doc", pages=[PageSpec(page_size_px=(100, 100),
                       regions=[Region(id="r1", kind="text", text="hi")])])
    doc.history.append(Snapshot(id="s1", parent_id=None, timestamp="t",
                                prompt="p", document={"k": "v"}))
    again = schema.document_from_dict(schema.document_to_dict(doc))
    assert len(again.history) == 1
    assert again.history[0].id == "s1"
    assert again.history[0].document == {"k": "v"}
    # content still intact
    assert again.pages[0].regions[0].text == "hi"
