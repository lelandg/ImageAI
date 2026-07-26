"""Tests for core/styles/store.py — persistence, slugs, image import."""
from pathlib import Path

from PIL import Image

from core.styles.models import Style
from core.styles.store import (
    EXEMPLAR_DEFAULT_CAP, JPEG_QUALITY, MAX_IMPORT_DIM, StyleStore,
)


def _make_image(path: Path, size=(64, 64), color=(200, 30, 30)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return path


def test_store_starts_empty(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    assert store.list_styles() == []
    assert store.get("nope") is None


def test_save_get_delete_round_trip(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    s = Style(id=store.new_id("Watercolor Storybook"), name="Watercolor Storybook",
              prompt_text="soft washes")
    store.save(s)
    assert s.id == "watercolor-storybook"
    got = store.get("watercolor-storybook")
    assert got is not None and got.name == "Watercolor Storybook"
    # fresh instance reads the same file
    assert StyleStore(base_dir=tmp_path / "styles").get_by_name("watercolor storybook").id == s.id
    assert store.get_by_name("WATERCOLOR-STORYBOOK").id == s.id  # id match too
    assert store.delete(s.id) is True
    assert store.get(s.id) is None
    assert store.delete(s.id) is False


def test_new_id_collision_gets_suffix(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    store.save(Style(id=store.new_id("Neon!"), name="Neon!"))
    second = store.new_id("Neon!")
    assert second == "neon-2"


def test_add_reference_images_copies_and_downscales(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    s = Style(id=store.new_id("Big"), name="Big")
    store.save(s)
    src = _make_image(tmp_path / "src" / "huge.png", size=(4096, 1024))
    added = store.add_reference_images(s, [src])
    assert added == ["refs/0001.jpg"]
    assert s.reference_images == ["refs/0001.jpg"]
    copied = store.style_dir(s.id) / "refs" / "0001.jpg"
    assert copied.exists()
    with Image.open(copied) as img:
        assert max(img.size) <= MAX_IMPORT_DIM
    assert src.exists()  # original untouched


def test_resolve_refs_filters_missing_and_exemplars(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    s = Style(id=store.new_id("R"), name="R")
    store.save(s)
    imgs = [_make_image(tmp_path / f"i{n}.png") for n in range(3)]
    store.add_reference_images(s, imgs)
    s.exemplars = [s.reference_images[0], s.reference_images[2]]
    store.save(s)
    assert len(store.resolve_refs(s)) == 3
    assert len(store.resolve_refs(s, exemplars_only=True)) == 2
    (store.style_dir(s.id) / "refs" / "0001.jpg").unlink()
    assert len(store.resolve_refs(s)) == 2  # missing file silently dropped


def test_remove_reference_image(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    s = Style(id=store.new_id("Rm"), name="Rm")
    store.save(s)
    store.add_reference_images(s, [_make_image(tmp_path / "a.png")])
    rel = s.reference_images[0]
    s.exemplars = [rel]
    store.remove_reference_image(s, rel)
    assert s.reference_images == [] and s.exemplars == []
    assert not (store.style_dir(s.id) / "refs" / "0001.jpg").exists()


def test_delete_removes_style_dir(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    s = Style(id=store.new_id("Gone"), name="Gone")
    store.save(s)
    store.add_reference_images(s, [_make_image(tmp_path / "g.png")])
    d = store.style_dir(s.id)
    assert d.exists()
    store.delete(s.id)
    assert not d.exists()


def test_add_after_middle_removal_does_not_overwrite(tmp_path):
    store = StyleStore(base_dir=tmp_path / "styles")
    s = Style(id=store.new_id("Seq"), name="Seq")
    store.save(s)
    imgs = [_make_image(tmp_path / f"s{n}.png", color=(n * 40, 0, 0)) for n in range(3)]
    store.add_reference_images(s, imgs)
    store.remove_reference_image(s, "refs/0002.jpg")
    survivor_bytes = (store.style_dir(s.id) / "refs" / "0003.jpg").read_bytes()
    store.add_reference_images(s, [_make_image(tmp_path / "new.png", color=(9, 9, 9))])
    # survivor untouched, new file got a fresh number, no duplicate entries
    assert (store.style_dir(s.id) / "refs" / "0003.jpg").read_bytes() == survivor_bytes
    assert len(set(s.reference_images)) == len(s.reference_images)
    assert "refs/0004.jpg" in s.reference_images
