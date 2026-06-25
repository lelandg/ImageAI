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


def _doc_with_text(t):
    from core.layout.models import DocumentSpec, PageSpec, Region
    return DocumentSpec(title="D", pages=[PageSpec(page_size_px=(100, 100),
                        regions=[Region(id="r1", kind="text", text=t)])])


def test_history_append_snapshots_current_doc():
    from core.layout.history import History
    doc = _doc_with_text("v1")
    h = History(doc)
    s1 = h.append("first", snapshot_id="s1", timestamp="t1")
    assert s1.id == "s1" and s1.parent_id is None
    # snapshot captured the doc WITHOUT nesting history inside it
    assert "history" not in s1.document
    assert s1.document["pages"][0]["regions"][0]["text"] == "v1"
    assert len(h.snapshots()) == 1


def test_history_parent_chain_and_restore():
    from core.layout.history import History
    doc = _doc_with_text("v1")
    h = History(doc)
    h.append("first", snapshot_id="s1", timestamp="t1")
    # mutate the live doc, snapshot again
    doc.pages[0].regions[0].text = "v2"
    s2 = h.append("second", snapshot_id="s2", timestamp="t2")
    assert s2.parent_id == "s1"  # auto-parents to previous snapshot
    restored = h.restore("s1")
    assert restored.pages[0].regions[0].text == "v1"  # got s1 content
    assert len(restored.history) == 2  # timeline preserved on the restored doc


def test_history_get_missing_returns_none():
    from core.layout.history import History
    h = History(_doc_with_text("v1"))
    assert h.get("nope") is None


def test_branch_from_records_real_branch_topology():
    from core.layout.history import History
    doc = _doc_with_text("v1")
    h = History(doc)
    h.append("first", snapshot_id="s1", timestamp="t1")
    doc.pages[0].regions[0].text = "v2"
    h.append("second", snapshot_id="s2", timestamp="t2")
    # user restores s1 and keeps iterating -> a fresh History on the restored doc
    restored = h.restore("s1")
    h2 = History(restored)
    h2.branch_from("s1")
    s3 = h2.append("third", snapshot_id="s3", timestamp="t3")
    # parents to the restored branch point, NOT the timeline tail (s2)
    assert s3.parent_id == "s1"
    # and the next append chains from s3, not s1 again
    s4 = h2.append("fourth", snapshot_id="s4", timestamp="t4")
    assert s4.parent_id == "s3"
