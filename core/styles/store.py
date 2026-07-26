"""Persistence for custom styles.

Layout (per Plans/2026-07-26-custom-styles-design.md §3):
    <base_dir>/styles.json      index: {"styles": [record, ...]}
    <base_dir>/<id>/refs/*.jpg  copied, downscaled source images
base_dir defaults to get_user_data_dir()/"styles" — personal artifacts never
live in the repo (unlike data/prompts/custom_presets.json).
"""
import json
import logging
import re
import shutil
from pathlib import Path
from typing import List, Optional

from core.styles.models import Style

logger = logging.getLogger(__name__)

MAX_IMPORT_DIM = 2048
JPEG_QUALITY = 90
EXEMPLAR_DEFAULT_CAP = 3
MAX_IMPORT_BYTES = 50 * 1024 * 1024  # per-entry cap for zip-imported images

_SAFE_REL = re.compile(r"^refs/[A-Za-z0-9._-]+$")
_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _is_safe_rel(rel: str) -> bool:
    """True for 'refs/<plain-basename>' entries — no separators, no traversal."""
    return bool(_SAFE_REL.match(rel)) and "/" not in rel[len("refs/"):] and ".." not in rel


class StyleStore:
    """CRUD + reference-image management for styles (PresetLoader-shaped)."""

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            from core.constants import get_user_data_dir
            base_dir = get_user_data_dir() / "styles"
        self.base_dir = Path(base_dir)
        self.index_path = self.base_dir / "styles.json"

    # ---- index I/O -------------------------------------------------------

    def _read_index(self) -> List[dict]:
        if not self.index_path.exists():
            return []
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f).get("styles", [])
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to read style index {self.index_path}: {e}")
            return []

    def _write_index(self, records: List[dict]) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump({"styles": records}, f, indent=2, ensure_ascii=False)

    # ---- CRUD ------------------------------------------------------------

    def list_styles(self) -> List[Style]:
        out = []
        for rec in self._read_index():
            try:
                s = Style.from_dict(rec)
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"Skipping malformed style record: {e}")
                continue
            if not _SAFE_ID.match(s.id):
                logger.warning(f"Skipping style record with unsafe id: {s.id!r}")
                continue
            out.append(s)
        return out

    def get(self, style_id: str) -> Optional[Style]:
        for s in self.list_styles():
            if s.id == style_id:
                return s
        return None

    def get_by_name(self, name: str) -> Optional[Style]:
        """Match by display name or id, case-insensitively."""
        needle = (name or "").strip().lower()
        for s in self.list_styles():
            if s.name.lower() == needle or s.id.lower() == needle:
                return s
        return None

    def new_id(self, name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", (name or "style").lower()).strip("-") or "style"
        existing = {s.id for s in self.list_styles()}
        if slug not in existing:
            return slug
        n = 2
        while f"{slug}-{n}" in existing:
            n += 1
        return f"{slug}-{n}"

    def save(self, style: Style) -> None:
        records = self._read_index()
        rec = style.to_dict()
        for i, existing in enumerate(records):
            if existing.get("id") == style.id:
                records[i] = rec
                break
        else:
            records.append(rec)
        self._write_index(records)
        logger.info(f"Saved style '{style.name}' ({style.id})")

    def delete(self, style_id: str) -> bool:
        records = self._read_index()
        kept = [r for r in records if r.get("id") != style_id]
        if len(kept) == len(records):
            return False
        self._write_index(kept)
        d = self.style_dir(style_id)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        logger.info(f"Deleted style {style_id}")
        return True

    # ---- reference images ------------------------------------------------

    def style_dir(self, style_id: str) -> Path:
        if not _SAFE_ID.match(style_id):
            raise ValueError(f"Unsafe style id: {style_id!r}")
        return self.base_dir / style_id

    def add_reference_images(self, style: Style, paths: List[Path]) -> List[str]:
        """Copy images into <style>/refs/ downscaled to MAX_IMPORT_DIM JPEG.

        Appends relative paths to style.reference_images and returns them.
        Caller must save() afterwards. Unreadable files are skipped with a
        logged warning, never fatal.
        """
        from PIL import Image
        refs_dir = self.style_dir(style.id) / "refs"
        refs_dir.mkdir(parents=True, exist_ok=True)
        # Derive sequence number from actual files on disk, not list length
        existing_nums = []
        for f in refs_dir.glob("*.jpg"):
            try:
                num = int(f.stem)
                existing_nums.append(num)
            except ValueError:
                pass
        seq = max(existing_nums) if existing_nums else 0
        added: List[str] = []
        for src in paths:
            src = Path(src)
            try:
                with Image.open(src) as img:
                    img = img.convert("RGB")
                    img.thumbnail((MAX_IMPORT_DIM, MAX_IMPORT_DIM))
                    seq += 1
                    rel = f"refs/{seq:04d}.jpg"
                    img.save(refs_dir / f"{seq:04d}.jpg", "JPEG", quality=JPEG_QUALITY)
            except (OSError, ValueError) as e:
                logger.warning(f"Skipping unreadable image {src}: {e}")
                continue
            style.reference_images.append(rel)
            added.append(rel)
        logger.info(f"Added {len(added)} reference image(s) to style {style.id}")
        return added

    def remove_reference_image(self, style: Style, rel_path: str) -> None:
        if not _is_safe_rel(rel_path):
            logger.warning(
                f"Style {style.id}: refusing to remove unsafe reference path {rel_path!r}")
            return
        p = self.style_dir(style.id) / rel_path
        if p.exists():
            p.unlink()
        style.reference_images = [r for r in style.reference_images if r != rel_path]
        style.exemplars = [r for r in style.exemplars if r != rel_path]

    def resolve_refs(self, style: Style, exemplars_only: bool = False) -> List[Path]:
        """Absolute paths of (existing) reference images, in stored order."""
        rels = style.exemplars if exemplars_only else style.reference_images
        base = self.style_dir(style.id)
        out = []
        for rel in rels:
            if not _is_safe_rel(rel):
                logger.warning(f"Style {style.id}: skipping unsafe reference path {rel!r}")
                continue
            p = base / rel
            if p.exists():
                out.append(p)
            else:
                logger.warning(f"Style {style.id}: missing reference file {rel}")
        return out

    # ---- zip export / import --------------------------------------------

    def export_zip(self, style_id: str, out_path: Path) -> bool:
        """Write <out_path> as a zip: style.json + refs/*. Shareable bundle."""
        import zipfile
        style = self.get(style_id)
        if style is None:
            logger.error(f"Cannot export unknown style: {style_id}")
            return False
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("style.json", json.dumps(style.to_dict(), indent=2,
                                                 ensure_ascii=False))
            for p in self.resolve_refs(style):
                zf.write(p, f"refs/{p.name}")
        logger.info(f"Exported style {style_id} to {out_path}")
        return True

    def import_zip(self, zip_path: Path) -> Optional[Style]:
        """Import a style zip; assigns a fresh id on collision.

        Hardened against hostile bundles: only zip members whose basename is
        referenced by the sanitized reference_images list are ever extracted
        (unreferenced/orphan entries are ignored), oversized entries are
        skipped, and every extracted image is re-validated and re-encoded
        through PIL exactly like add_reference_images() -- unreadable bytes
        never reach disk and are dropped from reference_images/exemplars so
        the "exemplars is a subset of reference_images" invariant holds.
        """
        import io
        import zipfile
        from PIL import Image
        try:
            with zipfile.ZipFile(zip_path) as zf:
                data = json.loads(zf.read("style.json").decode("utf-8"))
                style = Style.from_dict(data)
                style.id = self.new_id(style.name)
                style.is_builtin = False

                safe_refs = []
                for rel in style.reference_images:
                    if _is_safe_rel(rel):
                        safe_refs.append(rel)
                    else:
                        logger.warning(
                            f"Rejected unsafe reference_images entry in imported "
                            f"style '{style.name}': {rel!r}")
                style.reference_images = safe_refs

                safe_exemplars = []
                for rel in style.exemplars:
                    if _is_safe_rel(rel) and rel in style.reference_images:
                        safe_exemplars.append(rel)
                    else:
                        logger.warning(
                            f"Rejected unsafe exemplars entry in imported "
                            f"style '{style.name}': {rel!r}")
                style.exemplars = safe_exemplars

                wanted = {Path(r).name for r in style.reference_images}
                members = {
                    Path(info.filename).name: info for info in zf.infolist()
                    if info.filename.startswith("refs/") and Path(info.filename).name}

                refs_dir = self.style_dir(style.id) / "refs"
                refs_dir.mkdir(parents=True, exist_ok=True)
                written = set()
                for name in wanted:
                    info = members.get(name)
                    if info is None:
                        logger.warning(
                            f"Style '{style.name}': referenced image {name!r} "
                            f"missing from zip; dropping")
                        continue
                    if info.file_size > MAX_IMPORT_BYTES:
                        logger.warning(
                            f"Style '{style.name}': skipping oversized zip entry "
                            f"{name!r} ({info.file_size} bytes > "
                            f"{MAX_IMPORT_BYTES} cap)")
                        continue
                    raw = zf.read(info)
                    try:
                        with Image.open(io.BytesIO(raw)) as img:
                            img = img.convert("RGB")
                            img.thumbnail((MAX_IMPORT_DIM, MAX_IMPORT_DIM))
                            img.save(refs_dir / name, "JPEG", quality=JPEG_QUALITY)
                    except (OSError, ValueError) as e:
                        logger.warning(
                            f"Style '{style.name}': skipping unreadable image "
                            f"{name!r} in zip: {e}")
                        continue
                    written.add(name)

                for orphan in sorted(set(members) - wanted):
                    logger.warning(
                        f"Style '{style.name}': ignoring unreferenced zip "
                        f"entry refs/{orphan}")

                style.reference_images = [
                    r for r in style.reference_images if Path(r).name in written]
                style.exemplars = [
                    r for r in style.exemplars if Path(r).name in written]
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to import style zip {zip_path}: {e}")
            return None
        self.save(style)
        logger.info(f"Imported style '{style.name}' as {style.id}")
        return style
