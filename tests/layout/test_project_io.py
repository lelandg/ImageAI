import json
from core.layout.models import Region, PageSpec, DocumentSpec
from core.layout import project_io


def test_save_load_roundtrip(tmp_path):
    doc = DocumentSpec(title="Proj", content_kind="comic", pages=[
        PageSpec(page_size_px=(500, 500),
                 regions=[Region(id="r1", kind="text", text="Hi", bbox=(0, 0, 100, 30))])
    ])
    p = tmp_path / "x.iaiproj.json"
    project_io.save_project(doc, str(p))
    loaded = project_io.load_project(str(p))
    assert loaded.title == "Proj"
    assert loaded.content_kind == "comic"
    assert loaded.pages[0].regions[0].text == "Hi"


def test_render_on_top_roundtrip(tmp_path):
    doc = DocumentSpec(title="Proj", pages=[PageSpec(page_size_px=(500, 500))],
                       render_on_top=True)
    p = tmp_path / "x.iaiproj.json"
    project_io.save_project(doc, str(p))
    assert project_io.load_project(str(p)).render_on_top is True


def test_render_on_top_defaults_none_for_legacy(tmp_path):
    # Projects saved before this field existed load with no stored override.
    legacy = {"title": "Old", "pages": [{"page_size_px": [400, 400]}]}
    p = tmp_path / "old.iaiproj.json"
    p.write_text(json.dumps(legacy), encoding="utf-8")
    assert project_io.load_project(str(p)).render_on_top is None


def _image_project(tmp_path, image_ref):
    doc = DocumentSpec(title="P", pages=[
        PageSpec(page_size_px=(500, 500),
                 regions=[Region(id="i1", kind="image", bbox=(0, 0, 100, 100),
                                 image_ref=image_ref)])
    ])
    p = tmp_path / "proj.iaiproj.json"
    project_io.save_project(doc, str(p))
    return p


def test_load_resolves_relative_ref_against_project_dir(tmp_path):
    (tmp_path / "images").mkdir()
    img = tmp_path / "images" / "a.png"
    img.write_bytes(b"png")
    p = _image_project(tmp_path, "images/a.png")
    loaded = project_io.load_project(str(p))
    assert loaded.pages[0].regions[0].image_ref == str(img.resolve())


def test_load_dead_absolute_ref_falls_back_to_project_images(tmp_path):
    # e.g. a project saved under WSL (/home/...) opened on Windows
    (tmp_path / "images").mkdir()
    img = tmp_path / "images" / "b.png"
    img.write_bytes(b"png")
    p = _image_project(tmp_path, "/home/nobody/.config/ImageAI/images/b.png")
    loaded = project_io.load_project(str(p))
    assert loaded.pages[0].regions[0].image_ref == str(img.resolve())


def test_load_dead_windows_ref_falls_back_by_filename(tmp_path):
    img = tmp_path / "c.png"
    img.write_bytes(b"png")
    p = _image_project(tmp_path, "C:\\Users\\x\\AppData\\Roaming\\ImageAI\\images\\c.png")
    loaded = project_io.load_project(str(p))
    assert loaded.pages[0].regions[0].image_ref == str(img.resolve())


def test_load_keeps_existing_absolute_ref(tmp_path):
    img = tmp_path / "keep.png"
    img.write_bytes(b"png")
    p = _image_project(tmp_path, str(img))
    loaded = project_io.load_project(str(p))
    assert loaded.pages[0].regions[0].image_ref == str(img)


def test_load_leaves_unresolvable_ref_untouched(tmp_path):
    p = _image_project(tmp_path, "/nowhere/missing.png")
    loaded = project_io.load_project(str(p))
    assert loaded.pages[0].regions[0].image_ref == "/nowhere/missing.png"


def test_load_legacy_layout_json(tmp_path):
    legacy = {"title": "Legacy", "pages": [{
        "page_size_px": [400, 400],
        "blocks": [{"type": "image", "id": "i1", "rect": [0, 0, 100, 100],
                    "image_path": "/p.png"}]}]}
    p = tmp_path / "old.layout.json"
    p.write_text(json.dumps(legacy), encoding="utf-8")
    loaded = project_io.load_project(str(p))
    assert loaded.pages[0].regions[0].kind == "image"
    assert loaded.pages[0].regions[0].image_ref == "/p.png"
