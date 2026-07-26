"""Zip export/import round-trip for StyleStore."""
import json
import zipfile
from pathlib import Path

from PIL import Image

from core.styles.models import Style
from core.styles.store import StyleStore


def _store_with_style(tmp_path, name="Zippy"):
    store = StyleStore(base_dir=tmp_path / "styles")
    s = Style(id=store.new_id(name), name=name, prompt_text="zip style")
    store.save(s)
    img = tmp_path / "img.png"
    Image.new("RGB", (32, 32), (0, 128, 0)).save(img)
    store.add_reference_images(s, [img])
    s.exemplars = list(s.reference_images)
    store.save(s)
    return store, s


def test_export_import_round_trip(tmp_path):
    store, s = _store_with_style(tmp_path)
    zip_path = tmp_path / "zippy.zip"
    assert store.export_zip(s.id, zip_path) is True
    assert zip_path.exists()

    other = StyleStore(base_dir=tmp_path / "other")
    imported = other.import_zip(zip_path)
    assert imported is not None
    assert imported.name == "Zippy"
    assert imported.prompt_text == "zip style"
    assert len(other.resolve_refs(imported)) == 1
    assert imported.exemplars == imported.reference_images


def test_import_collision_gets_new_id(tmp_path):
    store, s = _store_with_style(tmp_path)
    zip_path = tmp_path / "z.zip"
    store.export_zip(s.id, zip_path)
    imported = store.import_zip(zip_path)  # same store -> id collision
    assert imported.id == "zippy-2"
    assert store.get("zippy") is not None and store.get("zippy-2") is not None


def test_export_unknown_style_returns_false(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    assert store.export_zip("missing", tmp_path / "x.zip") is False


def test_import_bad_zip_returns_none(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    assert store.import_zip(bad) is None


def test_import_zip_rejects_traversal_refs(tmp_path):
    """A crafted style.json with '../' entries must not escape the style dir."""
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")

    zip_path = tmp_path / "malicious.zip"
    style_json = {
        "id": "evil", "name": "Evil", "prompt_text": "",
        "reference_images": ["refs/../../../outside.txt", "refs/0001.jpg"],
        "exemplars": ["refs/../../../outside.txt"],
    }
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("style.json", json.dumps(style_json))
        zf.writestr("refs/0001.jpg", b"fake-jpeg-bytes")

    store = StyleStore(base_dir=tmp_path / "styles")
    imported = store.import_zip(zip_path)
    assert imported is not None
    assert imported.reference_images == ["refs/0001.jpg"]
    assert imported.exemplars == []
    assert outside.read_text() == "secret"


def test_resolve_and_remove_reject_traversal(tmp_path):
    """A hand-edited styles.json with a traversal rel must be a no-op at use time."""
    outside = tmp_path / "outside2.txt"
    outside.write_text("still here")

    store = StyleStore(base_dir=tmp_path / "styles")
    s = Style(id=store.new_id("Guard"), name="Guard",
              reference_images=["refs/../../../outside2.txt"],
              exemplars=["refs/../../../outside2.txt"])
    store.save(s)

    assert store.resolve_refs(s) == []
    store.remove_reference_image(s, "refs/../../../outside2.txt")
    assert outside.read_text() == "still here"
