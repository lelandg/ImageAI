"""Phase 5a — .iaibundle export/import (project + images + fonts, self-contained)."""
import json
import zipfile
from pathlib import Path

from core.layout.models import DocumentSpec, PageSpec, Region
from core.layout import bundle_io, styles


def _doc(regions, content_kind="children", title="Story"):
    page = PageSpec(page_size_px=(1000, 1500), regions=regions)
    return DocumentSpec(title=title, pages=[page], content_kind=content_kind,
                        style=styles.default_style_for(content_kind))


def test_export_bundle_contains_project_images_and_manifest(tmp_path):
    img1 = tmp_path / "a.png"; img1.write_bytes(b"PNG-A")
    img2 = tmp_path / "b.png"; img2.write_bytes(b"PNG-B")
    doc = _doc([
        Region(id="i1", kind="image", bbox=(0, 0, 500, 500), image_ref=str(img1)),
        Region(id="i2", kind="image", bbox=(0, 500, 500, 500), image_ref=str(img2)),
    ])
    out = tmp_path / "bundle.iaibundle"
    bundle_io.export_bundle(doc, str(out))
    assert out.exists()
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert bundle_io._PROJECT_NAME in names
        assert bundle_io._MANIFEST_NAME in names
        assert len([n for n in names if n.startswith("images/")]) == 2
        proj = json.loads(zf.read(bundle_io._PROJECT_NAME))
    refs = [r["image_ref"] for r in proj["pages"][0]["regions"]]
    assert all(ref.startswith("images/") for ref in refs)  # rewritten to relative
    # the live document must not be mutated by export
    assert doc.pages[0].regions[0].image_ref == str(img1)


def test_export_import_round_trip(tmp_path):
    img = tmp_path / "pic.png"; img.write_bytes(b"DATA")
    doc = _doc([
        Region(id="i1", kind="image", bbox=(0, 0, 100, 100), image_ref=str(img)),
        Region(id="t1", kind="text", bbox=(0, 110, 100, 40), text="Hi", role="title"),
    ])
    out = tmp_path / "b.iaibundle"
    bundle_io.export_bundle(doc, str(out))

    dest = tmp_path / "extracted"
    doc2 = bundle_io.import_bundle(str(out), str(dest))
    r = doc2.pages[0].regions[0]
    assert Path(r.image_ref).is_absolute() and Path(r.image_ref).exists()
    assert Path(r.image_ref).read_bytes() == b"DATA"
    assert doc2.pages[0].regions[1].text == "Hi"
    assert doc2.title == "Story"


def test_missing_image_is_warned_not_fatal(tmp_path):
    doc = _doc([Region(id="i1", kind="image", bbox=(0, 0, 100, 100),
                       image_ref="/does/not/exist.png")])
    out = tmp_path / "b.iaibundle"
    manifest = bundle_io.export_bundle(doc, str(out))
    assert any("exist.png" in w for w in manifest.warnings)
    assert out.exists()
    with zipfile.ZipFile(out) as zf:
        proj = json.loads(zf.read(bundle_io._PROJECT_NAME))
    # missing ref preserved as-is (no rewrite)
    assert proj["pages"][0]["regions"][0]["image_ref"] == "/does/not/exist.png"


def test_shared_image_is_embedded_once(tmp_path):
    img = tmp_path / "shared.png"; img.write_bytes(b"S")
    doc = _doc([
        Region(id="i1", kind="image", bbox=(0, 0, 100, 100), image_ref=str(img)),
        Region(id="i2", kind="image", bbox=(0, 100, 100, 100), image_ref=str(img)),
    ])
    out = tmp_path / "b.iaibundle"
    bundle_io.export_bundle(doc, str(out))
    with zipfile.ZipFile(out) as zf:
        assert len([n for n in zf.namelist() if n.startswith("images/")]) == 1
        proj = json.loads(zf.read(bundle_io._PROJECT_NAME))
    refs = {r["image_ref"] for r in proj["pages"][0]["regions"]}
    assert len(refs) == 1  # both regions share the single embedded image


def test_font_embedding_records_resolved_path(tmp_path):
    font_file = tmp_path / "MyFont.ttf"; font_file.write_bytes(b"TTF")
    doc = _doc([Region(id="t1", kind="text", bbox=(0, 0, 100, 40), text="x", role="title")])
    out = tmp_path / "b.iaibundle"
    manifest = bundle_io.export_bundle(doc, str(out), font_resolver=lambda families: font_file)
    assert any(v.startswith("fonts/") for v in manifest.fonts.values())
    with zipfile.ZipFile(out) as zf:
        assert any(n.startswith("fonts/") for n in zf.namelist())


def test_font_unresolved_recorded_by_name(tmp_path):
    doc = _doc([Region(id="t1", kind="text", bbox=(0, 0, 100, 40), text="x", role="title")])
    out = tmp_path / "b.iaibundle"
    manifest = bundle_io.export_bundle(doc, str(out), font_resolver=lambda families: None)
    assert manifest.fonts                                   # roles produced families
    assert all(v == "by-name" for v in manifest.fonts.values())


def test_import_rejects_zip_slip(tmp_path):
    # A malicious member escaping the destination must be refused.
    evil = tmp_path / "evil.iaibundle"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr(bundle_io._PROJECT_NAME, "{}")
        zf.writestr("../escape.txt", "pwned")
    import pytest
    with pytest.raises(ValueError):
        bundle_io.import_bundle(str(evil), str(tmp_path / "dest"))
